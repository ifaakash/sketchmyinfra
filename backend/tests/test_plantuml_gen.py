"""Tests for the PlantUML code generator."""

from app.ir.schema import (
    DiagramCategory,
    DiagramIR,
    DiagramTrack,
    GraphIR,
    IREdge,
    IRGroup,
    IRNode,
)
from app.generators.plantuml_gen import generate_plantuml


class TestBasicGeneration:
    def test_minimal_graph(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="app", label="App Server")],
                edges=[],
            ),
        )
        code = generate_plantuml(ir)
        assert code.startswith("@startuml")
        assert code.endswith("@enduml")
        assert '"App Server" as app' in code

    def test_direction(self):
        ir = DiagramIR(
            category=DiagramCategory.FLOWCHART,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A")],
                edges=[],
                direction="LR",
            ),
        )
        code = generate_plantuml(ir)
        assert "left to right direction" in code


class TestEdges:
    def test_solid_edge_with_label(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A"), IRNode(id="b", label="B")],
                edges=[IREdge(source="a", target="b", label="sends data")],
            ),
        )
        code = generate_plantuml(ir)
        assert "a --> b : sends data" in code

    def test_dotted_edge(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A"), IRNode(id="b", label="B")],
                edges=[IREdge(source="a", target="b", style="dotted")],
            ),
        )
        code = generate_plantuml(ir)
        assert "a ..> b" in code

    def test_back_arrow(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A"), IRNode(id="b", label="B")],
                edges=[IREdge(source="a", target="b", arrow="back")],
            ),
        )
        code = generate_plantuml(ir)
        assert "a <-- b" in code

    def test_no_arrow(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="A"), IRNode(id="b", label="B")],
                edges=[IREdge(source="a", target="b", arrow="none")],
            ),
        )
        code = generate_plantuml(ir)
        assert "a -- b" in code


class TestGroups:
    def test_simple_group(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[
                    IRNode(id="svc1", label="Service 1"),
                    IRNode(id="svc2", label="Service 2"),
                ],
                edges=[],
                groups=[
                    IRGroup(id="cluster", label="K8s Cluster", children=["svc1", "svc2"]),
                ],
            ),
        )
        code = generate_plantuml(ir)
        assert '"K8s Cluster" as cluster' in code
        assert '"Service 1" as svc1' in code

    def test_nested_groups(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="app", label="App")],
                edges=[],
                groups=[
                    IRGroup(id="outer", label="Outer", children=["inner"]),
                    IRGroup(id="inner", label="Inner", children=["app"]),
                ],
            ),
        )
        code = generate_plantuml(ir)
        assert '"Outer" as outer' in code
        assert '"Inner" as inner' in code
        assert '"App" as app' in code


class TestAWSIcons:
    def test_aws_architecture(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="aws",
            graph=GraphIR(
                nodes=[
                    IRNode(id="alb", label="ALB", icon="aws:alb", technology="HTTP"),
                    IRNode(id="ecs", label="ECS", icon="aws:ecs", technology="App"),
                    IRNode(id="rds", label="RDS", icon="aws:rds", technology="PostgreSQL"),
                ],
                edges=[
                    IREdge(source="alb", target="ecs", label="Routes Traffic"),
                    IREdge(source="ecs", target="rds", label="SQL Queries"),
                ],
                groups=[
                    IRGroup(id="vpc", label="VPC", type="vpc", children=["alb", "ecs", "rds"]),
                ],
            ),
        )
        code = generate_plantuml(ir)
        # Check AWS setup
        assert "allow_mixing" in code
        assert "!define AWSPuml" in code
        assert "!include AWSPuml/AWSCommon.puml" in code
        # Check icon includes
        assert "ElasticLoadBalancingApplicationLoadBalancer.puml" in code
        assert "ElasticContainerService.puml" in code
        assert "RDS.puml" in code
        # Check icon macros used
        assert 'ElasticLoadBalancingApplicationLoadBalancer(alb, "ALB", "HTTP")' in code
        assert 'ElasticContainerService(ecs, "ECS", "App")' in code
        # Check VPC group macro
        assert "VPCGroup(vpc" in code

    def test_unknown_icon_falls_back_to_rectangle(self):
        ir = DiagramIR(
            category=DiagramCategory.CLOUD_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            cloud_provider="aws",
            graph=GraphIR(
                nodes=[IRNode(id="custom", label="Custom Service", icon="aws:unknown_service")],
                edges=[],
            ),
        )
        code = generate_plantuml(ir)
        # Should fall back to plain rectangle
        assert '"Custom Service" as custom' in code


class TestLabelSafety:
    def test_ampersand_escaped(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="Auth & Auth")],
                edges=[],
            ),
        )
        code = generate_plantuml(ir)
        assert "Auth and Auth" in code
        assert "&" not in code.split('"')[1]  # Inside the label

    def test_pipe_escaped(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="Input|Output")],
                edges=[],
            ),
        )
        code = generate_plantuml(ir)
        assert "Input/Output" in code

    def test_tilde_escaped(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
            graph=GraphIR(
                nodes=[IRNode(id="a", label="Home~Dir")],
                edges=[],
            ),
        )
        code = generate_plantuml(ir)
        assert "Home-Dir" in code


class TestNoGraphRaises:
    def test_raises_without_graph(self):
        ir = DiagramIR(
            category=DiagramCategory.SYSTEM_ARCHITECTURE,
            track=DiagramTrack.GRAPH,
        )
        try:
            generate_plantuml(ir)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "graph" in str(e).lower()
