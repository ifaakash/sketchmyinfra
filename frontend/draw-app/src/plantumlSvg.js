// Read element positions and icons out of a PlantUML SVG, keyed by IR id.
//
// PlantUML tags each node and group with the alias it was declared with, and
// plantuml_gen.py declares everything with its IR id:
//   <g class="entity"  data-qualified-name="vpc.private.api"> ... </g>
//   <g class="cluster" data-qualified-name="vpc"> ... </g>
// The last dotted segment is the IR id. Cloud icons are embedded inside the
// group as <image href="data:image/png;base64,...">.
//
// Browser-only: getBBox() needs the SVG mounted in a live document.

const XLINK = "http://www.w3.org/1999/xlink";
const HEX = /^#[0-9a-f]{3,8}$/i;

// PlantUML writes stroke in a style attribute (style="stroke:#8C4FFF;...")
// and fill as an attribute; accept either form for both
function paint(el, prop) {
  const fromStyle = new RegExp(`(?:^|;)\\s*${prop}\\s*:\\s*([^;]+)`).exec(el.getAttribute("style") || "");
  const value = (fromStyle ? fromStyle[1] : el.getAttribute(prop) || "").trim();
  return HEX.test(value) ? value : undefined;
}

// Border colour, fill and dash of the element's own outline. Only rects:
// actors and other glyphs are drawn as paths and keep the converter's shapes.
function outline(g) {
  const rect = g.querySelector(":scope > rect");
  if (!rect) return {};
  const style = rect.getAttribute("style") || "";
  return {
    stroke: paint(rect, "stroke"),
    fill: paint(rect, "fill"),
    dashed: style.includes("stroke-dasharray") || rect.hasAttribute("stroke-dasharray"),
  };
}

function decodeDataUri(uri) {
  const comma = uri.indexOf(",");
  const meta = uri.slice(0, comma);
  const payload = uri.slice(comma + 1);
  if (!meta.endsWith(";base64")) return decodeURIComponent(payload);
  // atob yields bytes as Latin-1; labels may be UTF-8 (CJK, accents)
  const bytes = Uint8Array.from(atob(payload), (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

/**
 * @returns {{ boxes: Map<string, {x,y,width,height,stroke?,fill?,dashed?}>, icons: Map<string, {dataURL,width,height}> }}
 * Both maps are empty if the SVG can't be read; callers then lay out themselves.
 */
export function readPlantumlSvg(dataUri) {
  const boxes = new Map();
  const icons = new Map();
  if (typeof dataUri !== "string" || !dataUri.startsWith("data:image/svg")) return { boxes, icons };

  let host;
  try {
    const doc = new DOMParser().parseFromString(decodeDataUri(dataUri), "image/svg+xml");
    if (doc.querySelector("parsererror") || doc.documentElement.nodeName !== "svg") return { boxes, icons };

    // Off-screen but rendered: visibility:hidden still lays out, display:none would not
    host = document.createElement("div");
    host.style.cssText = "position:absolute;left:-100000px;top:0;visibility:hidden;pointer-events:none";
    host.appendChild(document.importNode(doc.documentElement, true));
    document.body.appendChild(host);

    for (const g of host.querySelectorAll("g.entity[data-qualified-name], g.cluster[data-qualified-name]")) {
      const id = g.getAttribute("data-qualified-name").split(".").pop();
      const b = g.getBBox();
      if (!b.width || !b.height) continue;
      boxes.set(id, { x: b.x, y: b.y, width: b.width, height: b.height, ...outline(g) });

      const img = g.querySelector("image");
      const href = img && (img.getAttribute("href") || img.getAttributeNS(XLINK, "href"));
      if (href?.startsWith("data:image/")) {
        icons.set(id, {
          dataURL: href,
          width: Number(img.getAttribute("width")) || 0,
          height: Number(img.getAttribute("height")) || 0,
        });
      }
    }
  } catch (err) {
    console.warn("Could not read PlantUML SVG, falling back to auto layout:", err);
    boxes.clear();
    icons.clear();
  } finally {
    host?.remove();
  }
  return { boxes, icons };
}
