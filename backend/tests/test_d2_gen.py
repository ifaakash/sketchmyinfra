"""Tests for the D2 code generator."""

from app.ir.schema import (
    ClassAttribute,
    ClassDiagramIR,
    ClassEntity,
    ClassMethod,
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
    StateDiagramIR,
    StateNode,
    StateTransition,
)
from app.generators.d2_gen import generate_d2


class TestGraphGeneration:
    def test_minimal(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="Node A")],
                edges=[],
            ),
        )
        code = generate_d2(ir)
        assert "direction: down" in code
        assert 'a: "Node A"' in code
        assert "shape: rectangle" in code

    def test_edge_with_label(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A"), IRNode(id="b", label="B")],
                edges=[IREdge(source="a", target="b", label="connects to")],
            ),
        )
        code = generate_d2(ir)
        assert 'a -> b: "connects to"' in code

    def test_dotted_edge(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A"), IRNode(id="b", label="B")],
                edges=[IREdge(source="a", target="b", style="dotted")],
            ),
        )
        code = generate_d2(ir)
        assert "stroke-dash: 3" in code

    def test_back_arrow(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A"), IRNode(id="b", label="B")],
                edges=[IREdge(source="a", target="b", arrow="back")],
            ),
        )
        code = generate_d2(ir)
        assert "a <- b" in code

    def test_groups(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[
                    IRNode(id="svc", label="Service", type="component"),
                    IRNode(id="db", label="DB", type="database"),
                ],
                edges=[IREdge(source="svc", target="db")],
                groups=[IRGroup(id="cluster", label="K8s Cluster", children=["svc", "db"])],
            ),
        )
        code = generate_d2(ir)
        assert 'cluster: "K8s Cluster"' in code
        assert 'svc: "Service"' in code
        assert "shape: cylinder" in code  # database -> cylinder

    def test_direction_lr(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A")],
                edges=[],
                direction="LR",
            ),
        )
        code = generate_d2(ir)
        assert "direction: right" in code

    def test_node_with_icon(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="gcp",
            graph=GraphIR(
                nodes=[IRNode(id="run", label="Cloud Run", icon="gcp:cloud_run")],
                edges=[],
            ),
        )
        code = generate_d2(ir)
        assert "icon:" in code
        assert "terrastruct.com" in code

    def test_node_with_color(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A", color="#3b82f6")],
                edges=[],
            ),
        )
        code = generate_d2(ir)
        assert 'style.fill: "#3b82f6"' in code


class TestERGeneration:
    def test_basic_er(self):
        ir = DiagramIR(
            category=DiagramCategory.ER_DIAGRAM,
            track=DiagramTrack.GRAPH,
            er=ERDiagramIR(
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
                    EREntity(
                        id="orgs",
                        name="Organizations",
                        attributes=[
                            ERAttribute(name="id", type="UUID", pk=True, nullable=False),
                            ERAttribute(name="name", type="VARCHAR(255)"),
                        ],
                    ),
                ],
                relationships=[
                    ERRelationship(from_entity="users", to_entity="orgs", label="belongs to", cardinality="N:1"),
                ],
            ),
        )
        code = generate_d2(ir)
        assert "shape: sql_table" in code
        assert "primary_key" in code
        assert "foreign_key" in code
        assert 'belongs to (N:1)' in code

    def test_multiple_constraints(self):
        ir = DiagramIR(
            category=DiagramCategory.ER_DIAGRAM,
            track=DiagramTrack.GRAPH,
            er=ERDiagramIR(
                entities=[
                    EREntity(
                        id="t",
                        name="T",
                        attributes=[
                            ERAttribute(name="id", type="int", pk=True, nullable=False),
                        ],
                    ),
                ],
                relationships=[],
            ),
        )
        code = generate_d2(ir)
        # PK + not_null would be redundant, but PK implies not null, so only PK
        assert "primary_key" in code


class TestSequenceGeneration:
    def test_basic_sequence(self):
        ir = DiagramIR(
            category=DiagramCategory.SEQUENCE,
            track=DiagramTrack.GRAPH,
            sequence=SequenceDiagramIR(
                participants=[
                    SequenceParticipant(id="client", label="Client"),
                    SequenceParticipant(id="api", label="API"),
                    SequenceParticipant(id="db", label="Database", type="database"),
                ],
                messages=[
                    SequenceMessage(from_id="client", to_id="api", label="POST /login"),
                    SequenceMessage(from_id="api", to_id="db", label="SELECT user"),
                    SequenceMessage(from_id="db", to_id="api", label="user row", type="reply"),
                    SequenceMessage(from_id="api", to_id="client", label="JWT token", type="reply"),
                ],
            ),
        )
        code = generate_d2(ir)
        assert "shape: sequence_diagram" in code
        assert 'client: "Client"' in code
        assert 'api: "API"' in code
        assert 'client -> api: "POST /login"' in code
        # Reply: same direction as IR specifies, dashed style
        assert 'db -> api' in code
        assert "stroke-dash: 5" in code

    def test_self_message(self):
        ir = DiagramIR(
            category=DiagramCategory.SEQUENCE,
            track=DiagramTrack.GRAPH,
            sequence=SequenceDiagramIR(
                participants=[SequenceParticipant(id="a", label="A")],
                messages=[SequenceMessage(from_id="a", to_id="a", label="validate", type="self")],
            ),
        )
        code = generate_d2(ir)
        assert 'a -> a: "validate"' in code


class TestClassGeneration:
    def test_basic_class(self):
        ir = DiagramIR(
            category=DiagramCategory.CLASS_DIAGRAM,
            track=DiagramTrack.GRAPH,
            class_diagram=ClassDiagramIR(
                classes=[
                    ClassEntity(
                        id="animal",
                        name="Animal",
                        stereotype="abstract",
                        attributes=[ClassAttribute(name="name", type="str", visibility="protected")],
                        methods=[ClassMethod(name="speak", return_type="str", visibility="public")],
                    ),
                    ClassEntity(
                        id="dog",
                        name="Dog",
                        methods=[ClassMethod(name="speak", return_type="str")],
                    ),
                ],
                relationships=[
                    ClassRelationship(from_class="dog", to_class="animal", type="inheritance"),
                ],
            ),
        )
        code = generate_d2(ir)
        assert "shape: class" in code
        assert "#name: str" in code  # protected
        assert "+speak(): str" in code  # public
        assert "inheritance" in code

    def test_private_method(self):
        ir = DiagramIR(
            category=DiagramCategory.CLASS_DIAGRAM,
            track=DiagramTrack.GRAPH,
            class_diagram=ClassDiagramIR(
                classes=[
                    ClassEntity(
                        id="foo",
                        name="Foo",
                        methods=[ClassMethod(name="helper", visibility="private", parameters="x: int")],
                    ),
                ],
            ),
        )
        code = generate_d2(ir)
        assert "-helper(x: int)" in code


class TestStateGeneration:
    def test_basic_state(self):
        ir = DiagramIR(
            category=DiagramCategory.STATE_DIAGRAM,
            track=DiagramTrack.GRAPH,
            state=StateDiagramIR(
                states=[
                    StateNode(id="idle", label="Idle"),
                    StateNode(id="running", label="Running"),
                ],
                transitions=[
                    StateTransition(from_state="idle", to_state="running", label="start"),
                ],
            ),
        )
        code = generate_d2(ir)
        assert 'idle: "Idle"' in code
        assert 'running: "Running"' in code
        assert 'idle -> running: "start"' in code

    def test_transition_with_guard(self):
        ir = DiagramIR(
            category=DiagramCategory.STATE_DIAGRAM,
            track=DiagramTrack.GRAPH,
            state=StateDiagramIR(
                states=[
                    StateNode(id="a", label="A"),
                    StateNode(id="b", label="B"),
                ],
                transitions=[
                    StateTransition(from_state="a", to_state="b", label="go", guard="ready"),
                ],
            ),
        )
        code = generate_d2(ir)
        assert 'go [ready]' in code


class TestNoVariantRaises:
    def test_raises_without_variant(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
        )
        try:
            generate_d2(ir)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
