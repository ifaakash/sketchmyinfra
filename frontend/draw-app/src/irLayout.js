// GraphIR -> Excalidraw element skeletons.
//
// Positions come from one of two places:
//   - boxes read from the PlantUML SVG the user already saw (plantumlSvg.js),
//     so the editor opens on the same picture;
//   - otherwise ELK. The IR carries no coordinates and D2 doesn't expose its
//     layout, so ELK's layered algorithm with INCLUDE_CHILDREN lays out
//     nested groups (VPC -> subnet -> node) itself.
// Either way the IR supplies the meaning: node types, groups and which edge
// connects what, so arrows stay bound when nodes are dragged.
//
// Kept free of @excalidraw imports so it runs under plain Node for tests;
// irToExcalidraw.js turns the skeletons into real elements.
import ELK from "elkjs/lib/elk.bundled.js";

const NODE_W = 180;
const NODE_H = 72;
// Icon nodes need room for the icon above the label
const ICON_NODE_H = 130;
const ICON_MAX = 64;
// Top padding leaves room for the group's label above its children
const GROUP_PADDING = "[top=44,left=24,bottom=24,right=24]";
const GROUP_PAD = { top: 44, left: 24, bottom: 24, right: 24 };
// Space between an arrow's end and the shape it points at
const ARROW_GAP = 8;

const DIRECTIONS = { TB: "DOWN", BT: "UP", LR: "RIGHT", RL: "LEFT" };

// Fill per cloud provider (light tints so black text stays readable)
const PROVIDER_FILL = {
  aws: "#ffe8cc",
  gcp: "#d0ebff",
  azure: "#c5f6fa",
};
const DEFAULT_FILL = "#f1f3f5";

// Stroke per group type; network boundaries are dashed like in AWS diagrams
const GROUP_STROKE = {
  vpc: "#2f9e44",
  subnet: "#1971c2",
  region: "#868e96",
  cloud: "#f08c00",
};
const DASHED_GROUPS = new Set(["vpc", "subnet", "region"]);

const NODE_SHAPE = {
  database: "ellipse",
  storage: "ellipse",
  actor: "ellipse",
};

// Gemini output is free text; only trust colours we know Excalidraw can parse
const isHex = (c) => typeof c === "string" && /^#[0-9a-f]{3,8}$/i.test(c);

const nodeKey = (id) => `n:${id}`;
const groupKey = (id) => `g:${id}`;
export const iconFileId = (id) => `icon:${id}`;

function providerOf(node, fallback) {
  const prefix = node.icon?.split(":")[0];
  return PROVIDER_FILL[prefix] ? prefix : fallback;
}

// Assign each node/group a single parent group. The IR lists children per
// group; a child claimed twice keeps its first parent, and a group can't end
// up inside itself.
function buildTree(graph) {
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const groups = new Map((graph.groups || []).map((g) => [g.id, g]));
  const parentOf = new Map();

  for (const g of groups.values()) {
    for (const childId of g.children || []) {
      const key = nodes.has(childId) ? nodeKey(childId) : groups.has(childId) ? groupKey(childId) : null;
      if (!key || parentOf.has(key) || key === groupKey(g.id)) continue;
      // Reject a link that would make g its own ancestor
      let up = groupKey(g.id);
      let cycle = false;
      while (parentOf.has(up)) {
        up = parentOf.get(up);
        if (up === key) cycle = true;
      }
      if (!cycle) parentOf.set(key, groupKey(g.id));
    }
  }
  return { nodes, groups, parentOf };
}

function validEdges(graph, tree) {
  const edges = [];
  graph.edges.forEach((e, i) => {
    if (!tree.nodes.has(e.source) || !tree.nodes.has(e.target)) {
      console.warn(`Skipping edge ${e.source} -> ${e.target}: unknown node`);
      return;
    }
    if (e.source === e.target) {
      console.warn(`Skipping self-loop on ${e.source}`);
      return;
    }
    edges.push({ ...e, id: `e:${i}` });
  });
  return edges;
}

function toElkGraph(graph, tree, edges, icons) {
  const elkNodes = new Map();
  for (const n of tree.nodes.values()) {
    const height = icons.has(n.id) ? ICON_NODE_H : NODE_H;
    elkNodes.set(nodeKey(n.id), { id: nodeKey(n.id), width: NODE_W, height });
  }
  for (const g of tree.groups.values()) {
    elkNodes.set(groupKey(g.id), {
      id: groupKey(g.id),
      children: [],
      layoutOptions: { "elk.padding": GROUP_PADDING },
    });
  }

  const root = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": DIRECTIONS[graph.direction] || "DOWN",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      "elk.spacing.nodeNode": "48",
      "elk.layered.spacing.nodeNodeBetweenLayers": "72",
      "elk.padding": "[top=24,left=24,bottom=24,right=24]",
    },
    children: [],
    // With INCLUDE_CHILDREN, edges may live at the root even when they
    // connect nodes inside different groups
    edges: edges.map((e) => ({ id: e.id, sources: [nodeKey(e.source)], targets: [nodeKey(e.target)] })),
  };

  for (const [key, elkNode] of elkNodes) {
    const parent = tree.parentOf.get(key);
    (parent ? elkNodes.get(parent).children : root.children).push(elkNode);
  }

  // An empty group has no size of its own; give it one so ELK can place it
  for (const elkNode of elkNodes.values()) {
    if (elkNode.children && !elkNode.children.length) {
      elkNode.width = NODE_W;
      elkNode.height = NODE_H;
    }
  }

  return root;
}

// ELK child coordinates are relative to their parent; flatten to absolute
function absolutePositions(laidOut) {
  const pos = new Map();
  const walk = (node, ox, oy) => {
    for (const child of node.children || []) {
      const x = ox + child.x;
      const y = oy + child.y;
      pos.set(child.id, { x, y, width: child.width, height: child.height });
      walk(child, x, y);
    }
  };
  walk(laidOut, 0, 0);
  return pos;
}

async function elkPositions(graph, tree, edges, icons) {
  const laidOut = await new ELK().layout(toElkGraph(graph, tree, edges, icons));
  return absolutePositions(laidOut);
}

// Positions straight from the rendered SVG. Groups PlantUML didn't draw
// (e.g. an empty one) get the bounding box of their children.
function boxPositions(tree, boxes) {
  const pos = new Map();
  const geometry = ({ x, y, width, height }) => ({ x, y, width, height });
  for (const id of tree.nodes.keys()) pos.set(nodeKey(id), geometry(boxes.get(id)));

  const resolve = (g, seen = new Set()) => {
    const key = groupKey(g.id);
    if (pos.has(key) || seen.has(key)) return pos.get(key);
    seen.add(key);
    if (boxes.has(g.id)) {
      pos.set(key, geometry(boxes.get(g.id)));
      return pos.get(key);
    }
    const kids = [...tree.parentOf]
      .filter(([, parent]) => parent === key)
      .map(([child]) => (child.startsWith("g:") ? resolve(tree.groups.get(child.slice(2)), seen) : pos.get(child)))
      .filter(Boolean);
    if (!kids.length) return undefined;
    const x = Math.min(...kids.map((b) => b.x)) - GROUP_PAD.left;
    const y = Math.min(...kids.map((b) => b.y)) - GROUP_PAD.top;
    const right = Math.max(...kids.map((b) => b.x + b.width)) + GROUP_PAD.right;
    const bottom = Math.max(...kids.map((b) => b.y + b.height)) + GROUP_PAD.bottom;
    pos.set(key, { x, y, width: right - x, height: bottom - y });
    return pos.get(key);
  };
  for (const g of tree.groups.values()) resolve(g);
  return pos;
}

// Where the ray from a box's centre towards (tx, ty) leaves the box, pushed
// out by ARROW_GAP. Ellipses use their bounding box: close enough, and the
// arrow is bound so Excalidraw re-snaps it on the first drag.
function exitPoint(box, tx, ty) {
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const dx = tx - cx;
  const dy = ty - cy;
  const len = Math.hypot(dx, dy) || 1;
  const sx = dx ? box.width / 2 / Math.abs(dx) : Infinity;
  const sy = dy ? box.height / 2 / Math.abs(dy) : Infinity;
  const s = Math.min(sx, sy);
  return { x: cx + dx * s + (dx / len) * ARROW_GAP, y: cy + dy * s + (dy / len) * ARROW_GAP };
}

function arrowheads(arrow) {
  switch (arrow) {
    case "both":
      return { startArrowhead: "arrow", endArrowhead: "arrow" };
    case "back":
      return { startArrowhead: "arrow", endArrowhead: null };
    case "none":
      return { startArrowhead: null, endArrowhead: null };
    default:
      return { startArrowhead: null, endArrowhead: "arrow" };
  }
}

// Fit an icon inside ICON_MAX, keeping its aspect ratio
function iconSize(icon) {
  const w = icon.width || ICON_MAX;
  const h = icon.height || ICON_MAX;
  const scale = Math.min(1, ICON_MAX / Math.max(w, h));
  return { width: w * scale, height: h * scale };
}

/**
 * Lay out a DiagramIR (graph variant) and return Excalidraw element skeletons.
 *
 * `boxes` (IR id -> {x, y, width, height}) mirrors an existing render; it is
 * used only when it covers every node, so two layouts are never mixed.
 * `icons` (IR id -> {dataURL, width, height}) adds an image to that node or
 * group; the caller registers the files under iconFileId(id).
 *
 * Groups come first so they render beneath the nodes they contain.
 */
export async function irToSkeletons(ir, { boxes = new Map(), icons = new Map() } = {}) {
  const graph = ir?.graph;
  if (!graph?.nodes?.length) throw new Error("Diagram has no nodes to lay out");

  const tree = buildTree(graph);
  const edges = validEdges(graph, tree);
  const mirrored = graph.nodes.every((n) => boxes.has(n.id));
  const pos = mirrored ? boxPositions(tree, boxes) : await elkPositions(graph, tree, edges, icons);

  const skeletons = [];

  // Parents before children, so nested groups stack in the right order
  const depth = (key) => {
    let d = 0;
    for (let k = key; tree.parentOf.has(k); k = tree.parentOf.get(k)) d++;
    return d;
  };
  const groups = [...tree.groups.values()]
    .filter((g) => pos.has(groupKey(g.id)))
    .sort((a, b) => depth(groupKey(a.id)) - depth(groupKey(b.id)));

  // Outline colours copied from the render, when mirroring one
  const look = (id) => (mirrored ? boxes.get(id) || {} : {});

  for (const g of groups) {
    const p = pos.get(groupKey(g.id));
    const { stroke: renderedStroke, dashed: renderedDashed } = look(g.id);
    const stroke = renderedStroke || (isHex(g.color) ? g.color : GROUP_STROKE[g.type] || "#495057");
    const dashed = renderedStroke ? renderedDashed : DASHED_GROUPS.has(g.type);
    const elementGroup = [`grp:${g.id}`];
    skeletons.push({
      type: "rectangle",
      id: groupKey(g.id),
      x: p.x,
      y: p.y,
      width: p.width,
      height: p.height,
      strokeColor: stroke,
      backgroundColor: "transparent",
      strokeStyle: dashed ? "dashed" : "solid",
      roughness: 0,
      roundness: { type: 3 },
    });
    // Badge icon (e.g. the VPC logo) in the top-left corner, label beside it
    let labelX = p.x + 12;
    const icon = icons.get(g.id);
    if (icon) {
      const size = { width: 24, height: 24 };
      skeletons.push({ type: "image", fileId: iconFileId(g.id), x: p.x + 8, y: p.y + 8, ...size, groupIds: elementGroup });
      labelX = p.x + 8 + size.width + 8;
    }
    // A free text element, not a bound label: bound labels are centred and
    // would sit underneath the group's children
    skeletons.push({
      type: "text",
      x: labelX,
      y: p.y + 10,
      text: g.label,
      fontSize: 16,
      strokeColor: stroke,
      ...(icon ? { groupIds: elementGroup } : {}),
    });
  }

  for (const n of tree.nodes.values()) {
    const p = pos.get(nodeKey(n.id));
    const text = n.technology ? `${n.label}\n${n.technology}` : n.label;
    const icon = icons.get(n.id);

    const { stroke: renderedStroke, fill: renderedFill } = look(n.id);

    if (icon) {
      // Icon nodes follow PlantUML's: the name on top, the icon beneath it.
      // The rectangle is what arrows bind to (borderless unless the render
      // had one); it shares a group with the image so they drag as one.
      const elementGroup = [`node:${n.id}`];
      const size = iconSize(icon);
      skeletons.push({
        type: "rectangle",
        id: nodeKey(n.id),
        x: p.x,
        y: p.y,
        width: p.width,
        height: p.height,
        strokeColor: renderedStroke || "transparent",
        backgroundColor: "transparent",
        roughness: 0,
        groupIds: elementGroup,
        // Bound text inherits the container's stroke, which may be transparent
        label: { text, fontSize: 14, verticalAlign: "top", strokeColor: "#1e1e1e" },
      });
      skeletons.push({
        type: "image",
        fileId: iconFileId(n.id),
        x: p.x + (p.width - size.width) / 2,
        // Below the label, centred in the space that's left
        y: p.y + 28 + Math.max(0, (p.height - 28 - size.height) / 2),
        ...size,
        groupIds: elementGroup,
      });
      continue;
    }

    const provider = providerOf(n, ir.cloud_provider);
    skeletons.push({
      type: NODE_SHAPE[n.type] || "rectangle",
      id: nodeKey(n.id),
      x: p.x,
      y: p.y,
      width: p.width,
      height: p.height,
      ...(renderedStroke ? { strokeColor: renderedStroke } : {}),
      backgroundColor: renderedFill || (isHex(n.color) ? n.color : PROVIDER_FILL[provider] || DEFAULT_FILL),
      fillStyle: "solid",
      roughness: 0,
      roundness: { type: 3 },
      label: { text, fontSize: 16 },
    });
  }

  for (const e of edges) {
    const s = pos.get(nodeKey(e.source));
    const t = pos.get(nodeKey(e.target));
    // Straight line between the two borders; binding keeps it attached
    const start = exitPoint(s, t.x + t.width / 2, t.y + t.height / 2);
    const end = exitPoint(t, s.x + s.width / 2, s.y + s.height / 2);
    skeletons.push({
      type: "arrow",
      x: start.x,
      y: start.y,
      width: end.x - start.x,
      height: end.y - start.y,
      start: { id: nodeKey(e.source) },
      end: { id: nodeKey(e.target) },
      strokeStyle: e.style === "dotted" || e.style === "dashed" ? e.style : "solid",
      roughness: 0,
      ...arrowheads(e.arrow),
      ...(e.label ? { label: { text: e.label, fontSize: 14 } } : {}),
    });
  }

  return skeletons;
}
