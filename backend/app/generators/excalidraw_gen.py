"""Deterministic Excalidraw JSON generator from SpatialIR.

Converts positioned shapes, dimensions and groups into Excalidraw-compatible
element JSON that can be loaded directly into the draw-app.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from app.ir.schema import DiagramIR, SpatialDimension, SpatialElement, SpatialIR

# Default styling
_DEFAULTS = {
    "strokeColor": "#1e1e1e",
    "backgroundColor": "transparent",
    "fillStyle": "solid",
    "strokeWidth": 2,
    "strokeStyle": "solid",
    "roughness": 0,
    "opacity": 100,
    "roundness": {"type": 3},
}


def _make_id(seed: str) -> str:
    """Generate a deterministic ID from a seed string."""
    return hashlib.md5(seed.encode()).hexdigest()[:16]


def _seed_from_id(element_id: str) -> int:
    """Generate a deterministic seed number from an element ID."""
    return int(hashlib.md5(element_id.encode()).hexdigest()[:8], 16)


def _base_element(
    element_id: str,
    element_type: str,
    x: float,
    y: float,
    width: float,
    height: float,
    stroke_color: str = "#1e1e1e",
    background_color: str = "transparent",
    stroke_width: float = 2,
    angle: float = 0,
) -> dict[str, Any]:
    """Create a base Excalidraw element with all required fields."""
    eid = _make_id(element_id)
    return {
        "id": eid,
        "type": element_type,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": angle,
        "strokeColor": stroke_color,
        "backgroundColor": background_color,
        "fillStyle": "solid",
        "strokeWidth": stroke_width,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "seed": _seed_from_id(eid),
        "version": 1,
        "versionNonce": _seed_from_id(eid + "_nonce"),
        "isDeleted": False,
        "groupIds": [],
        "frameId": None,
        "boundElements": None,
        "updated": int(time.time() * 1000),
        "link": None,
        "locked": False,
        "roundness": {"type": 3} if element_type in ("rectangle", "diamond", "ellipse") else None,
    }


def _make_text_element(
    element_id: str,
    x: float,
    y: float,
    text: str,
    font_size: float = 16,
    color: str = "#1e1e1e",
    container_id: str | None = None,
    width: float | None = None,
    height: float | None = None,
) -> dict[str, Any]:
    """Create a text element, optionally bound to a container."""
    # Estimate dimensions from text if not provided
    if width is None:
        width = len(text) * font_size * 0.6
    if height is None:
        lines = text.count("\n") + 1
        height = lines * font_size * 1.4

    elem = _base_element(element_id, "text", x, y, width, height, stroke_color=color)
    elem.update({
        "text": text,
        "fontSize": font_size,
        "fontFamily": 1,  # Virgil (hand-drawn)
        "textAlign": "center",
        "verticalAlign": "middle" if container_id else "top",
        "containerId": _make_id(container_id) if container_id else None,
        "originalText": text,
        "autoResize": True,
        "lineHeight": 1.25,
        "backgroundColor": "transparent",
        "roundness": None,
    })
    return elem


def _make_arrow_element(
    element_id: str,
    x: float,
    y: float,
    points: list[list[float]],
    stroke_color: str = "#1e1e1e",
    stroke_width: float = 2,
    start_arrowhead: str | None = None,
    end_arrowhead: str | None = "arrow",
) -> dict[str, Any]:
    """Create an arrow/line element."""
    # Calculate bounding box from points
    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        width = max(xs) - min(xs) if len(xs) > 1 else 0
        height = max(ys) - min(ys) if len(ys) > 1 else 0
    else:
        width = 0
        height = 0

    elem = _base_element(element_id, "arrow", x, y, width, height, stroke_color=stroke_color, stroke_width=stroke_width)
    elem.update({
        "points": points,
        "lastCommittedPoint": None,
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": start_arrowhead,
        "endArrowhead": end_arrowhead,
        "roundness": {"type": 2},
    })
    return elem


def _make_line_element(
    element_id: str,
    x: float,
    y: float,
    points: list[list[float]],
    stroke_color: str = "#1e1e1e",
    stroke_width: float = 2,
) -> dict[str, Any]:
    """Create a line element (no arrowheads)."""
    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        width = max(xs) - min(xs) if len(xs) > 1 else 0
        height = max(ys) - min(ys) if len(ys) > 1 else 0
    else:
        width = 0
        height = 0

    elem = _base_element(element_id, "line", x, y, width, height, stroke_color=stroke_color, stroke_width=stroke_width)
    elem.update({
        "points": points,
        "lastCommittedPoint": None,
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": None,
        "roundness": {"type": 2},
    })
    return elem


def _convert_spatial_element(elem: SpatialElement) -> list[dict[str, Any]]:
    """Convert a SpatialElement to one or more Excalidraw elements.

    Returns a list because shapes with labels produce both a shape and a text element.
    """
    results: list[dict[str, Any]] = []

    stroke_color = elem.color or "#1e1e1e"
    fill_color = elem.fill or "transparent"
    stroke_width = elem.stroke_width

    if elem.type == "text":
        text_elem = _make_text_element(
            elem.id,
            elem.x,
            elem.y,
            elem.label or "",
            font_size=elem.font_size,
            color=stroke_color,
        )
        results.append(text_elem)

    elif elem.type == "arrow":
        points = elem.points or [[0, 0], [elem.width, 0]]
        arrow_elem = _make_arrow_element(
            elem.id,
            elem.x,
            elem.y,
            points,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
        )
        results.append(arrow_elem)

    elif elem.type == "line":
        points = elem.points or [[0, 0], [elem.width, 0]]
        line_elem = _make_line_element(
            elem.id,
            elem.x,
            elem.y,
            points,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
        )
        results.append(line_elem)

    else:
        # Rectangle, ellipse, diamond
        exc_type = elem.type  # these map 1:1
        shape_elem = _base_element(
            elem.id,
            exc_type,
            elem.x,
            elem.y,
            elem.width,
            elem.height,
            stroke_color=stroke_color,
            background_color=fill_color,
            stroke_width=stroke_width,
            angle=elem.rotation,
        )

        # If there's a label, add bound text
        if elem.label:
            text_id = f"{elem.id}_text"
            text_elem = _make_text_element(
                text_id,
                elem.x + elem.width / 2,
                elem.y + elem.height / 2,
                elem.label,
                font_size=elem.font_size,
                color=stroke_color,
                container_id=elem.id,
            )
            # Register the text binding on the shape
            shape_elem["boundElements"] = [
                {"id": _make_id(text_id), "type": "text"}
            ]
            results.append(shape_elem)
            results.append(text_elem)
        else:
            results.append(shape_elem)

    return results


def _convert_dimension(dim: SpatialDimension, index: int) -> list[dict[str, Any]]:
    """Convert a dimension annotation to Excalidraw elements (line + text label).

    Since we don't have actual element positions here, dimensions are rendered
    as standalone text annotations. The frontend can adjust positions.
    """
    # Create a text annotation for the dimension
    text_id = f"dim_{index}"
    text_elem = _make_text_element(
        text_id,
        50,  # default x
        50 + index * 30,  # stack vertically
        f"{dim.value}",
        font_size=14,
        color="#666666",
    )
    return [text_elem]


def generate_excalidraw(ir: DiagramIR) -> dict[str, Any]:
    """Generate Excalidraw scene JSON from a DiagramIR with spatial variant.

    Returns a dict compatible with Excalidraw's initialData format:
    {elements: [...], appState: {...}, files: {}}
    """
    spatial = ir.spatial
    if spatial is None:
        raise ValueError("DiagramIR.spatial must be populated for Excalidraw generation")

    elements: list[dict[str, Any]] = []

    # Convert spatial elements
    for elem in spatial.elements:
        elements.extend(_convert_spatial_element(elem))

    # Convert dimensions
    for i, dim in enumerate(spatial.dimensions):
        elements.extend(_convert_dimension(dim, i))

    # Handle groups — set groupIds on elements
    for group in spatial.groups:
        group_id = _make_id(f"group_{group.id}")
        for child_id in group.children:
            target_exc_id = _make_id(child_id)
            for elem in elements:
                if elem["id"] == target_exc_id:
                    elem["groupIds"].append(group_id)
                    break

    # Build scene
    scene: dict[str, Any] = {
        "elements": elements,
        "appState": {
            "viewBackgroundColor": "#ffffff",
            "gridSize": 20,
        },
        "files": {},
    }

    return scene
