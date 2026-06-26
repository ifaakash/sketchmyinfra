"""Intermediate Representation (IR) schema for diagram generation.

All diagram types are normalised into a structured IR before code generation.
Gemini extracts structure into these models; deterministic code generators
consume them to produce PlantUML, D2, or Excalidraw JSON.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DiagramCategory(str, Enum):
    CLOUD_ARCHITECTURE = "cloud_architecture"
    SYSTEM_ARCHITECTURE = "system_architecture"
    NETWORK_TOPOLOGY = "network_topology"
    FLOWCHART = "flowchart"
    SEQUENCE = "sequence"
    ER_DIAGRAM = "er_diagram"
    CLASS_DIAGRAM = "class_diagram"
    STATE_DIAGRAM = "state_diagram"
    BUILDING_PLAN = "building_plan"
    CIRCUIT_DIAGRAM = "circuit_diagram"
    SITE_LAYOUT = "site_layout"
    TECHNICAL_ILLUSTRATION = "technical_illustration"


class DiagramTrack(str, Enum):
    GRAPH = "graph"
    SPATIAL = "spatial"


# ---------------------------------------------------------------------------
# Graph Track — general nodes/edges/groups
# ---------------------------------------------------------------------------

class IRNode(BaseModel):
    """A single node in a graph-based diagram."""
    id: str = Field(..., description="Unique snake_case identifier")
    label: str = Field(..., description="Human-readable display label")
    type: str = Field(
        default="rectangle",
        description="Shape hint: rectangle, database, queue, cloud, actor, component, node, frame, storage",
    )
    icon: str | None = Field(
        default=None,
        description="Namespaced icon id, e.g. 'aws:lambda', 'gcp:cloud_run', 'azure:app_service'",
    )
    technology: str | None = Field(default=None, description="Technology label, e.g. 'PostgreSQL 16'")
    color: str | None = Field(default=None, description="Hex colour for styling, e.g. '#3b82f6'")


class IREdge(BaseModel):
    """A connection between two nodes."""
    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    label: str | None = Field(default=None, description="Edge label text")
    style: Literal["solid", "dotted", "dashed"] = "solid"
    arrow: Literal["forward", "back", "both", "none"] = "forward"


class IRGroup(BaseModel):
    """A logical grouping of nodes (e.g. VPC, subnet, region)."""
    id: str
    label: str
    type: str = Field(
        default="rectangle",
        description="Group semantics: vpc, subnet, region, cloud, package, frame, cluster",
    )
    children: list[str] = Field(default_factory=list, description="Node ids or nested group ids")
    color: str | None = None
    icon: str | None = None


class GraphIR(BaseModel):
    """IR for generic graph-based diagrams (cloud arch, system arch, network, flowchart)."""
    nodes: list[IRNode]
    edges: list[IREdge]
    groups: list[IRGroup] = Field(default_factory=list)
    direction: Literal["TB", "LR", "RL", "BT"] = "TB"
    title: str | None = None


# ---------------------------------------------------------------------------
# ER Diagram IR (graph variant)
# ---------------------------------------------------------------------------

class ERAttribute(BaseModel):
    name: str
    type: str
    pk: bool = False
    fk: str | None = Field(default=None, description="FK reference, e.g. 'users.id'")
    nullable: bool = True


class EREntity(BaseModel):
    id: str
    name: str
    attributes: list[ERAttribute]


class ERRelationship(BaseModel):
    from_entity: str
    to_entity: str
    label: str
    cardinality: Literal["1:1", "1:N", "N:1", "M:N"]


class ERDiagramIR(BaseModel):
    """IR for Entity-Relationship diagrams."""
    entities: list[EREntity]
    relationships: list[ERRelationship]
    title: str | None = None


# ---------------------------------------------------------------------------
# Sequence Diagram IR (graph variant)
# ---------------------------------------------------------------------------

class SequenceParticipant(BaseModel):
    id: str
    label: str
    type: Literal["actor", "participant", "database", "queue"] = "participant"


class SequenceMessage(BaseModel):
    from_id: str
    to_id: str
    label: str
    type: Literal["sync", "async", "reply", "self"] = "sync"


class SequenceDiagramIR(BaseModel):
    """IR for sequence diagrams."""
    participants: list[SequenceParticipant]
    messages: list[SequenceMessage]
    title: str | None = None


# ---------------------------------------------------------------------------
# Class Diagram IR (graph variant)
# ---------------------------------------------------------------------------

class ClassMethod(BaseModel):
    name: str
    visibility: Literal["public", "private", "protected"] = "public"
    return_type: str | None = None
    parameters: str | None = None


class ClassAttribute(BaseModel):
    name: str
    type: str
    visibility: Literal["public", "private", "protected"] = "public"


class ClassEntity(BaseModel):
    id: str
    name: str
    attributes: list[ClassAttribute] = Field(default_factory=list)
    methods: list[ClassMethod] = Field(default_factory=list)
    stereotype: str | None = None  # e.g. "abstract", "interface"


class ClassRelationship(BaseModel):
    from_class: str
    to_class: str
    type: Literal["inheritance", "composition", "aggregation", "association", "dependency", "implementation"]
    label: str | None = None


class ClassDiagramIR(BaseModel):
    """IR for class diagrams."""
    classes: list[ClassEntity]
    relationships: list[ClassRelationship] = Field(default_factory=list)
    title: str | None = None


# ---------------------------------------------------------------------------
# State Diagram IR (graph variant)
# ---------------------------------------------------------------------------

class StateNode(BaseModel):
    id: str  # "[*]" for start/end pseudo-states
    label: str
    type: Literal["state", "choice", "fork", "join", "start", "end"] = "state"
    children: list["StateNode"] = Field(default_factory=list)  # nested (composite) states


class StateTransition(BaseModel):
    from_state: str
    to_state: str
    label: str | None = None
    guard: str | None = None


class StateDiagramIR(BaseModel):
    """IR for state machine diagrams."""
    states: list[StateNode]
    transitions: list[StateTransition]
    title: str | None = None


# ---------------------------------------------------------------------------
# Spatial Track — positioned shapes for technical drawings
# ---------------------------------------------------------------------------

class SpatialElement(BaseModel):
    """A positioned shape on a 2D canvas."""
    id: str
    type: Literal["rectangle", "ellipse", "diamond", "text", "line", "arrow"]
    x: float
    y: float
    width: float = 100
    height: float = 50
    label: str | None = None
    color: str | None = Field(default=None, description="Stroke colour hex")
    fill: str | None = Field(default=None, description="Fill colour hex")
    stroke_width: float = 1
    font_size: float = 16
    rotation: float = 0
    points: list[list[float]] | None = Field(
        default=None,
        description="For line/arrow: list of [x, y] waypoints relative to element origin",
    )


class SpatialDimension(BaseModel):
    """A measurement annotation on a spatial diagram."""
    from_element: str
    to_element: str | None = None
    value: str  # e.g. "3m", "50cm", "12 inches"
    side: Literal["top", "bottom", "left", "right"]


class SpatialGroup(BaseModel):
    """A logical grouping in a spatial diagram (e.g. a room, a wall section)."""
    id: str
    label: str
    children: list[str] = Field(default_factory=list)
    color: str | None = None


class SpatialIR(BaseModel):
    """IR for spatial/technical diagrams (building plans, circuits, illustrations)."""
    elements: list[SpatialElement]
    dimensions: list[SpatialDimension] = Field(default_factory=list)
    groups: list[SpatialGroup] = Field(default_factory=list)
    canvas_width: float = 1200
    canvas_height: float = 800
    title: str | None = None


# ---------------------------------------------------------------------------
# Master IR — discriminated by category
# ---------------------------------------------------------------------------

class DiagramIR(BaseModel):
    """Top-level IR container. Exactly one of the variant fields is populated."""
    category: DiagramCategory
    track: DiagramTrack
    cloud_provider: Literal["aws", "gcp", "azure", "multi"] | None = None
    title: str | None = None

    # Graph-track variants (populate exactly one):
    graph: GraphIR | None = None
    er: ERDiagramIR | None = None
    sequence: SequenceDiagramIR | None = None
    class_diagram: ClassDiagramIR | None = None
    state: StateDiagramIR | None = None

    # Spatial-track variant:
    spatial: SpatialIR | None = None
