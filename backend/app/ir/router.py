"""Deterministic category-to-renderer routing.

Maps each DiagramCategory to a (track, renderer) pair.  No AI involved —
this is pure configuration.
"""

from .schema import DiagramCategory, DiagramIR, DiagramTrack

# (track, renderer) for each category
_ROUTING: dict[DiagramCategory, tuple[DiagramTrack, str]] = {
    # Graph track — PlantUML (cloud icons)
    DiagramCategory.CLOUD_ARCHITECTURE: (DiagramTrack.GRAPH, "plantuml"),
    # Graph track — D2
    DiagramCategory.SYSTEM_ARCHITECTURE: (DiagramTrack.GRAPH, "d2"),
    DiagramCategory.NETWORK_TOPOLOGY:   (DiagramTrack.GRAPH, "d2"),
    DiagramCategory.FLOWCHART:          (DiagramTrack.GRAPH, "d2"),
    DiagramCategory.ER_DIAGRAM:         (DiagramTrack.GRAPH, "d2"),
    DiagramCategory.SEQUENCE:           (DiagramTrack.GRAPH, "d2"),
    DiagramCategory.CLASS_DIAGRAM:      (DiagramTrack.GRAPH, "d2"),
    DiagramCategory.STATE_DIAGRAM:      (DiagramTrack.GRAPH, "d2"),
    # Spatial track — Excalidraw
    DiagramCategory.BUILDING_PLAN:          (DiagramTrack.SPATIAL, "excalidraw"),
    DiagramCategory.CIRCUIT_DIAGRAM:        (DiagramTrack.SPATIAL, "excalidraw"),
    DiagramCategory.SITE_LAYOUT:            (DiagramTrack.SPATIAL, "excalidraw"),
    DiagramCategory.TECHNICAL_ILLUSTRATION: (DiagramTrack.SPATIAL, "excalidraw"),
}

# Cloud-provider overrides for cloud_architecture
_CLOUD_RENDERER: dict[str, str] = {
    "aws":   "plantuml",
    "azure": "plantuml",
    "gcp":   "d2",
    "multi": "plantuml",  # broadest icon coverage
}


def route(ir: DiagramIR) -> tuple[DiagramTrack, str]:
    """Return (track, renderer) for the given IR.

    Cloud-provider overrides apply when the category is cloud_architecture.
    """
    track, renderer = _ROUTING[ir.category]

    if ir.category == DiagramCategory.CLOUD_ARCHITECTURE and ir.cloud_provider:
        renderer = _CLOUD_RENDERER.get(ir.cloud_provider, renderer)

    return track, renderer
