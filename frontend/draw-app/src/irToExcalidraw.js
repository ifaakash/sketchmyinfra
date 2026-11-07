import { convertToExcalidrawElements, FONT_FAMILY } from "@excalidraw/excalidraw";
import { iconFileId, irToSkeletons } from "./irLayout";
import { readPlantumlSvg } from "./plantumlSvg";

// Helvetica is a system font, so text is measured correctly on first paint.
// The default hand-drawn font loads late, and labels measured before it
// arrives come out clipped.
function useSystemFont(skeleton) {
  if (skeleton.type === "text") return { ...skeleton, fontFamily: FONT_FAMILY.Helvetica };
  if (skeleton.label) return { ...skeleton, label: { ...skeleton.label, fontFamily: FONT_FAMILY.Helvetica } };
  return skeleton;
}

/**
 * Build an Excalidraw initialData scene from a generated diagram's IR.
 * With the PlantUML SVG the user saw, the scene mirrors its layout and
 * icons; without it (D2, or an unreadable SVG) ELK lays it out.
 */
export async function irToScene(ir, svg = null) {
  const { boxes, icons } = svg ? readPlantumlSvg(svg) : { boxes: new Map(), icons: new Map() };
  const skeletons = await irToSkeletons(ir, { boxes, icons });

  const created = Date.now();
  const files = {};
  for (const [id, icon] of icons) {
    const fileId = iconFileId(id);
    const mimeType = icon.dataURL.slice(5, icon.dataURL.indexOf(";"));
    files[fileId] = { id: fileId, dataURL: icon.dataURL, mimeType, created };
  }

  return {
    elements: convertToExcalidrawElements(skeletons.map(useSystemFont)),
    appState: { viewBackgroundColor: "#ffffff" },
    files,
    scrollToContent: true,
  };
}
