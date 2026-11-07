// Run with: npm test  (node's built-in runner, no extra deps)
import { test } from "node:test";
import assert from "node:assert/strict";
import { irToSkeletons } from "./irLayout.js";

const AWS_THREE_TIER = {
  category: "cloud_architecture",
  track: "graph",
  cloud_provider: "aws",
  graph: {
    direction: "TB",
    nodes: [
      { id: "users", label: "Users", type: "actor" },
      { id: "alb", label: "ALB", icon: "aws:alb" },
      { id: "ecs", label: "ECS Service", icon: "aws:ecs" },
      { id: "rds", label: "RDS", type: "database", icon: "aws:rds", technology: "PostgreSQL 16" },
    ],
    edges: [
      { source: "users", target: "alb", label: "HTTPS" },
      { source: "alb", target: "ecs" },
      { source: "ecs", target: "rds", style: "dashed", arrow: "both" },
    ],
    groups: [
      { id: "vpc", label: "VPC", type: "vpc", children: ["public", "private"] },
      { id: "public", label: "Public subnet", type: "subnet", children: ["alb"] },
      { id: "private", label: "Private subnet", type: "subnet", children: ["ecs", "rds"] },
    ],
  },
};

const byId = (skeletons, id) => skeletons.find((s) => s.id === id);
const contains = (outer, inner) =>
  inner.x >= outer.x &&
  inner.y >= outer.y &&
  inner.x + inner.width <= outer.x + outer.width &&
  inner.y + inner.height <= outer.y + outer.height;

test("emits one shape per node, a box + label per group, an arrow per edge", async () => {
  const s = await irToSkeletons(AWS_THREE_TIER);
  assert.equal(s.filter((e) => e.id?.startsWith("n:")).length, 4);
  assert.equal(s.filter((e) => e.id?.startsWith("g:")).length, 3);
  assert.equal(s.filter((e) => e.type === "text").length, 3);
  assert.equal(s.filter((e) => e.type === "arrow").length, 3);
});

test("coordinates are finite numbers", async () => {
  for (const e of await irToSkeletons(AWS_THREE_TIER)) {
    for (const k of ["x", "y", "width", "height"]) {
      if (k in e) assert.ok(Number.isFinite(e[k]), `${e.id ?? e.type}.${k} = ${e[k]}`);
    }
  }
});

test("nested groups contain their children", async () => {
  const s = await irToSkeletons(AWS_THREE_TIER);
  assert.ok(contains(byId(s, "g:vpc"), byId(s, "g:private")));
  assert.ok(contains(byId(s, "g:private"), byId(s, "n:rds")));
  assert.ok(contains(byId(s, "g:public"), byId(s, "n:alb")));
  assert.ok(!contains(byId(s, "g:vpc"), byId(s, "n:users")));
});

test("groups are emitted before nodes so they render underneath", async () => {
  const s = await irToSkeletons(AWS_THREE_TIER);
  const lastGroup = s.findLastIndex((e) => e.id?.startsWith("g:"));
  const firstNode = s.findIndex((e) => e.id?.startsWith("n:"));
  assert.ok(lastGroup < firstNode);
  // ...and outer groups before inner ones
  assert.ok(s.indexOf(byId(s, "g:vpc")) < s.indexOf(byId(s, "g:private")));
});

test("arrows bind to their nodes and carry style", async () => {
  const arrows = (await irToSkeletons(AWS_THREE_TIER)).filter((e) => e.type === "arrow");
  assert.deepEqual(arrows[0].start, { id: "n:users" });
  assert.deepEqual(arrows[0].end, { id: "n:alb" });
  assert.equal(arrows[0].label.text, "HTTPS");
  assert.equal(arrows[2].strokeStyle, "dashed");
  assert.equal(arrows[2].startArrowhead, "arrow");
});

test("node styling follows provider and type", async () => {
  const s = await irToSkeletons(AWS_THREE_TIER);
  assert.equal(byId(s, "n:rds").type, "ellipse");
  assert.equal(byId(s, "n:rds").label.text, "RDS\nPostgreSQL 16");
  assert.equal(byId(s, "n:alb").backgroundColor, "#ffe8cc");
});

test("flowchart without groups lays out left to right", async () => {
  const s = await irToSkeletons({
    category: "flowchart",
    graph: {
      direction: "LR",
      nodes: [{ id: "a", label: "Start" }, { id: "b", label: "End" }],
      edges: [{ source: "a", target: "b" }],
    },
  });
  assert.ok(byId(s, "n:b").x > byId(s, "n:a").x);
});

test("tolerates inconsistent model output", async () => {
  const s = await irToSkeletons({
    graph: {
      nodes: [{ id: "a", label: "A" }, { id: "b", label: "B", color: "not-a-colour" }],
      edges: [
        { source: "a", target: "ghost" }, // unknown node
        { source: "a", target: "a" }, // self-loop
        { source: "a", target: "b" },
      ],
      groups: [
        { id: "g1", label: "G1", children: ["g2", "a", "missing"] },
        { id: "g2", label: "G2", children: ["g1", "a", "b"] }, // cycle + double-claimed "a"
        { id: "empty", label: "Empty", children: [] },
      ],
    },
  });
  assert.equal(s.filter((e) => e.type === "arrow").length, 1);
  assert.equal(byId(s, "n:b").backgroundColor, "#f1f3f5");
  assert.ok(contains(byId(s, "g:g1"), byId(s, "n:a")));
  assert.ok(contains(byId(s, "g:g1"), byId(s, "g:g2")));
});

test("rejects an IR with no graph", async () => {
  await assert.rejects(irToSkeletons({ spatial: {} }), /no nodes/);
});

// ---------------------------------------------------------------------------
// Mirroring a rendered PlantUML layout
// ---------------------------------------------------------------------------

// Boxes as plantumlSvg.js would read them (deliberately not ELK-like)
const BOXES = new Map([
  ["users", { x: 500, y: 10, width: 60, height: 80 }],
  ["alb", { x: 40, y: 200, width: 100, height: 110 }],
  ["ecs", { x: 300, y: 400, width: 120, height: 110 }],
  ["rds", { x: 300, y: 600, width: 120, height: 110 }],
  ["vpc", { x: 10, y: 150, width: 600, height: 700 }],
]);
const PNG = "data:image/png;base64,AAAA";

test("uses rendered boxes when they cover every node", async () => {
  const s = await irToSkeletons(AWS_THREE_TIER, { boxes: BOXES });
  for (const id of ["users", "alb", "ecs", "rds"]) {
    const { x, y, width, height } = byId(s, `n:${id}`);
    assert.deepEqual({ x, y, width, height }, BOXES.get(id));
  }
  assert.deepEqual(
    (({ x, y, width, height }) => ({ x, y, width, height }))(byId(s, "g:vpc")),
    BOXES.get("vpc"),
  );
  // Groups PlantUML didn't report wrap their children
  assert.ok(contains(byId(s, "g:private"), byId(s, "n:ecs")));
  assert.ok(contains(byId(s, "g:private"), byId(s, "n:rds")));
});

test("falls back to ELK when rendered boxes miss a node", async () => {
  const partial = new Map([...BOXES].filter(([id]) => id !== "rds"));
  const s = await irToSkeletons(AWS_THREE_TIER, { boxes: partial });
  assert.notEqual(byId(s, "n:alb").x, BOXES.get("alb").x);
});

test("icon nodes are an invisible bind target + image, grouped together", async () => {
  const icons = new Map([["alb", { dataURL: PNG, width: 64, height: 64 }]]);
  const s = await irToSkeletons(AWS_THREE_TIER, { boxes: BOXES, icons });
  const rect = byId(s, "n:alb");
  const img = s.find((e) => e.type === "image" && e.fileId === "icon:alb");
  assert.equal(rect.strokeColor, "transparent");
  assert.equal(rect.label.verticalAlign, "top");
  assert.ok(img, "image element emitted");
  assert.deepEqual(img.groupIds, rect.groupIds);
  assert.ok(contains(rect, img));
  // Arrows still bind to the rectangle, not the image
  const arrow = s.find((e) => e.type === "arrow" && e.end?.id === "n:alb");
  assert.ok(arrow);
});

test("oversized icons are scaled down, keeping aspect ratio", async () => {
  const icons = new Map([["ecs", { dataURL: PNG, width: 128, height: 96 }]]);
  const s = await irToSkeletons(AWS_THREE_TIER, { boxes: BOXES, icons });
  const img = s.find((e) => e.fileId === "icon:ecs");
  assert.equal(img.width, 64);
  assert.equal(img.height, 48);
});

test("arrows start and end outside their shapes, not at the centre", async () => {
  const s = await irToSkeletons(AWS_THREE_TIER, { boxes: BOXES });
  const inside = (b, p) => p.x > b.x && p.x < b.x + b.width && p.y > b.y && p.y < b.y + b.height;
  for (const a of s.filter((e) => e.type === "arrow")) {
    const start = { x: a.x, y: a.y };
    const end = { x: a.x + a.width, y: a.y + a.height };
    assert.ok(!inside(byId(s, a.start.id), start), `${a.start.id} start inside`);
    assert.ok(!inside(byId(s, a.end.id), end), `${a.end.id} end inside`);
  }
});

test("mirrors the render's outline colours and dashes", async () => {
  const styled = new Map(BOXES);
  styled.set("vpc", { ...BOXES.get("vpc"), stroke: "#8C4FFF", fill: "#FFF", dashed: false });
  styled.set("alb", { ...BOXES.get("alb"), stroke: "#F90", fill: "#FFF" });
  const icons = new Map([["alb", { dataURL: PNG, width: 64, height: 64 }]]);
  const s = await irToSkeletons(AWS_THREE_TIER, { boxes: styled, icons });
  assert.equal(byId(s, "g:vpc").strokeColor, "#8C4FFF");
  assert.equal(byId(s, "g:vpc").strokeStyle, "solid"); // render wins over "vpc is dashed"
  assert.equal(byId(s, "n:alb").strokeColor, "#F90");
  assert.equal(byId(s, "n:users").backgroundColor !== undefined, true);
  // Styling never leaks into geometry
  assert.equal(byId(s, "n:alb").stroke, undefined);
});
