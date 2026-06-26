"""Tests for the IR schema models and category router."""

import pytest
from pydantic import ValidationError

from app.ir.schema import (
    ClassDiagramIR,
    ClassEntity,
    ClassRelationship,
    DiagramCategory,
    DiagramIR,
    DiagramTrack,
    ERAttribute,
    ERDiagramIR,
    EREntity,
    ERRelationship,
    GraphIR,
    IREdge,
    IRGroup,
    IRNode,
    SequenceDiagramIR,
    SequenceMessage,
    SequenceParticipant,
    SpatialElement,
    SpatialIR,
    StateDiagramIR,
    StateNode,
    StateTransition,
)
from app.ir.router import route


# ---------------------------------------------------------------------------
# GraphIR
# ---------------------------------------------------------------------------


class TestGraphIR:
    def test_minimal(self):
        ir = GraphIR(nodes=[IRNode(id="a", label="A")], edges=[])
        assert len(ir.nodes) == 1
        assert ir.direction == "TB"

    def test_full(self):
        ir = GraphIR(
            nodes=[
                IRNode(id="alb", label="ALB", type="component", icon="aws:alb", technology="HTTP", color="#3b82f6"),
                IRNode(id="ecs", label="ECS", icon="aws:ecs"),
            ],
            edges=[IREdge(source="alb", target="ecs", label="Routes Traffic", style="solid")],
            groups=[IRGroup(id="vpc", label="VPC", type="vpc", children=["alb", "ecs"])],
            direction="LR",
            title="AWS Architecture",
        )
        assert ir.nodes[0].icon == "aws:alb"
        assert ir.edges[0].arrow == "forward"
        assert ir.groups[0].children == ["alb", "ecs"]

    def test_defaults(self):
        node = IRNode(id="x", label="X")
        assert node.type == "rectangle"
        assert node.icon is None
        edge = IREdge(source="a", target="b")
        assert edge.style == "solid"
        assert edge.arrow == "forward"

    def test_edge_invalid_style(self):
        with pytest.raises(ValidationError):
            IREdge(source="a", target="b", style="wavy")


# ---------------------------------------------------------------------------
# ERDiagramIR
# ---------------------------------------------------------------------------


class TestERDiagramIR:
    def test_valid(self):
        ir = ERDiagramIR(
            entities=[
                EREntity(
                    id="users",
                    name="Users",
                    attributes=[
                        ERAttribute(name="id", type="UUID", pk=True, nullable=False),
                        ERAttribute(name="email", type="VARCHAR(255)"),
                        ERAttribute(name="org_id", type="UUID", fk="orgs.id"),
                    ],
                ),
                EREntity(id="orgs", name="Organizations", attributes=[]),
            ],
            relationships=[
                ERRelationship(from_entity="users", to_entity="orgs", label="belongs to", cardinality="N:1"),
            ],
        )
        assert len(ir.entities) == 2
        assert ir.entities[0].attributes[0].pk is True
        assert ir.entities[0].attributes[2].fk == "orgs.id"

    def test_invalid_cardinality(self):
        with pytest.raises(ValidationError):
            ERRelationship(from_entity="a", to_entity="b", label="x", cardinality="many-to-many")


# ---------------------------------------------------------------------------
# SequenceDiagramIR
# ---------------------------------------------------------------------------


class TestSequenceDiagramIR:
    def test_valid(self):
        ir = SequenceDiagramIR(
            participants=[
                SequenceParticipant(id="client", label="Client", type="actor"),
                SequenceParticipant(id="api", label="API Server"),
                SequenceParticipant(id="db", label="Database", type="database"),
            ],
            messages=[
                SequenceMessage(from_id="client", to_id="api", label="POST /login"),
                SequenceMessage(from_id="api", to_id="db", label="SELECT user", type="sync"),
                SequenceMessage(from_id="db", to_id="api", label="user row", type="reply"),
                SequenceMessage(from_id="api", to_id="client", label="JWT token", type="reply"),
            ],
            title="Auth Flow",
        )
        assert len(ir.participants) == 3
        assert ir.messages[0].type == "sync"  # default

    def test_invalid_message_type(self):
        with pytest.raises(ValidationError):
            SequenceMessage(from_id="a", to_id="b", label="x", type="broadcast")


# ---------------------------------------------------------------------------
# ClassDiagramIR
# ---------------------------------------------------------------------------


class TestClassDiagramIR:
    def test_valid(self):
        ir = ClassDiagramIR(
            classes=[
                ClassEntity(id="animal", name="Animal", stereotype="abstract"),
                ClassEntity(id="dog", name="Dog"),
            ],
            relationships=[
                ClassRelationship(from_class="dog", to_class="animal", type="inheritance"),
            ],
        )
        assert ir.classes[0].stereotype == "abstract"

    def test_invalid_relationship_type(self):
        with pytest.raises(ValidationError):
            ClassRelationship(from_class="a", to_class="b", type="friend")


# ---------------------------------------------------------------------------
# StateDiagramIR
# ---------------------------------------------------------------------------


class TestStateDiagramIR:
    def test_valid(self):
        ir = StateDiagramIR(
            states=[
                StateNode(id="idle", label="Idle"),
                StateNode(id="running", label="Running"),
            ],
            transitions=[
                StateTransition(from_state="idle", to_state="running", label="start", guard="ready"),
            ],
        )
        assert ir.transitions[0].guard == "ready"


# ---------------------------------------------------------------------------
# SpatialIR
# ---------------------------------------------------------------------------


class TestSpatialIR:
    def test_valid(self):
        ir = SpatialIR(
            elements=[
                SpatialElement(id="wall", type="rectangle", x=0, y=0, width=400, height=200, label="Wall"),
                SpatialElement(id="fan", type="ellipse", x=50, y=50, width=30, height=30, label="Fan 1"),
                SpatialElement(
                    id="wire",
                    type="line",
                    x=100,
                    y=100,
                    points=[[0, 0], [50, 50]],
                ),
            ],
            canvas_width=800,
            canvas_height=600,
        )
        assert len(ir.elements) == 3
        assert ir.elements[2].points == [[0, 0], [50, 50]]

    def test_invalid_element_type(self):
        with pytest.raises(ValidationError):
            SpatialElement(id="x", type="hexagon", x=0, y=0)


# ---------------------------------------------------------------------------
# DiagramIR (master container)
# ---------------------------------------------------------------------------


class TestDiagramIR:
    def test_cloud_architecture(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="aws",
            title="My AWS Arch",
            graph=GraphIR(
                nodes=[IRNode(id="alb", label="ALB", icon="aws:alb")],
                edges=[],
            ),
        )
        assert ir.cloud_provider == "aws"
        assert ir.graph is not None
        assert ir.er is None

    def test_er_diagram(self):
        ir = DiagramIR(
            category=DiagramCategory.ER_DIAGRAM,
            track=DiagramTrack.GRAPH,
            er=ERDiagramIR(entities=[], relationships=[]),
        )
        assert ir.er is not None
        assert ir.graph is None

    def test_spatial(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(elements=[]),
        )
        assert ir.spatial is not None

    def test_invalid_category(self):
        with pytest.raises(ValidationError):
            DiagramIR(category="pie_chart", track=DiagramTrack.GRAPH)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class TestRouter:
    def test_aws_routes_to_plantuml(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="aws",
            graph=GraphIR(nodes=[], edges=[]),
        )
        track, renderer = route(ir)
        assert track == DiagramTrack.GRAPH
        assert renderer == "plantuml"

    def test_gcp_routes_to_d2(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="gcp",
            graph=GraphIR(nodes=[], edges=[]),
        )
        track, renderer = route(ir)
        assert renderer == "d2"

    def test_azure_routes_to_plantuml(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="azure",
            graph=GraphIR(nodes=[], edges=[]),
        )
        _, renderer = route(ir)
        assert renderer == "plantuml"

    def test_multi_cloud_routes_to_plantuml(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="multi",
            graph=GraphIR(nodes=[], edges=[]),
        )
        _, renderer = route(ir)
        assert renderer == "plantuml"

    def test_flowchart_routes_to_d2(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(nodes=[], edges=[]),
        )
        track, renderer = route(ir)
        assert track == DiagramTrack.GRAPH
        assert renderer == "d2"

    def test_er_routes_to_d2(self):
        ir = DiagramIR(
            category=DiagramCategory.ER_DIAGRAM,
            track=DiagramTrack.GRAPH,
        )
        _, renderer = route(ir)
        assert renderer == "d2"

    def test_building_plan_routes_to_excalidraw(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
        )
        track, renderer = route(ir)
        assert track == DiagramTrack.SPATIAL
        assert renderer == "excalidraw"

    def test_circuit_routes_to_excalidraw(self):
        ir = DiagramIR(
            category=DiagramCategory.CIRCUIT_DIAGRAM,
            track=DiagramTrack.SPATIAL,
        )
        _, renderer = route(ir)
        assert renderer == "excalidraw"

    def test_all_categories_routed(self):
        """Every category in the enum has a routing entry."""
        for cat in DiagramCategory:
            ir = DiagramIR(category=cat, track=DiagramTrack.GRAPH)
            track, renderer = route(ir)
            assert renderer in ("plantuml", "d2", "excalidraw")
