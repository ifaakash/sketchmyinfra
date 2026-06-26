"""Tests for the Excalidraw JSON generator."""

from app.ir.schema import (
    DiagramCategory,
    DiagramIR,
    DiagramTrack,
    SpatialDimension,
    SpatialElement,
    SpatialGroup,
    SpatialIR,
)
from app.generators.excalidraw_gen import generate_excalidraw


class TestBasicGeneration:
    def test_returns_valid_scene(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(elements=[]),
        )
        scene = generate_excalidraw(ir)
        assert "elements" in scene
        assert "appState" in scene
        assert "files" in scene
        assert isinstance(scene["elements"], list)
        assert scene["files"] == {}

    def test_rectangle_element(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="wall", type="rectangle", x=100, y=200, width=400, height=300),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        elems = scene["elements"]
        assert len(elems) == 1
        elem = elems[0]
        assert elem["type"] == "rectangle"
        assert elem["x"] == 100
        assert elem["y"] == 200
        assert elem["width"] == 400
        assert elem["height"] == 300
        assert elem["isDeleted"] is False

    def test_rectangle_with_label(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="room", type="rectangle", x=0, y=0, width=200, height=100, label="Bedroom"),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        elems = scene["elements"]
        # Should produce shape + text
        assert len(elems) == 2
        shape = elems[0]
        text = elems[1]
        assert shape["type"] == "rectangle"
        assert text["type"] == "text"
        assert text["text"] == "Bedroom"
        assert text["containerId"] == shape["id"]  # bound to container

    def test_text_element(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="label1", type="text", x=50, y=50, label="3 meters"),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        elems = scene["elements"]
        assert len(elems) == 1
        assert elems[0]["type"] == "text"
        assert elems[0]["text"] == "3 meters"

    def test_arrow_element(self):
        ir = DiagramIR(
            category=DiagramCategory.CIRCUIT_DIAGRAM,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(
                        id="wire1",
                        type="arrow",
                        x=100,
                        y=100,
                        points=[[0, 0], [200, 0]],
                    ),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        elems = scene["elements"]
        assert len(elems) == 1
        assert elems[0]["type"] == "arrow"
        assert elems[0]["points"] == [[0, 0], [200, 0]]
        assert elems[0]["endArrowhead"] == "arrow"

    def test_line_element(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(
                        id="wall_line",
                        type="line",
                        x=0,
                        y=0,
                        points=[[0, 0], [100, 0], [100, 50]],
                    ),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        elems = scene["elements"]
        assert len(elems) == 1
        assert elems[0]["type"] == "line"
        assert elems[0]["endArrowhead"] is None  # no arrowheads on lines

    def test_ellipse_element(self):
        ir = DiagramIR(
            category=DiagramCategory.CIRCUIT_DIAGRAM,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="fan", type="ellipse", x=50, y=50, width=30, height=30, fill="#cccccc"),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        elems = scene["elements"]
        assert len(elems) == 1
        assert elems[0]["type"] == "ellipse"
        assert elems[0]["backgroundColor"] == "#cccccc"


class TestStyling:
    def test_stroke_color(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="wall", type="rectangle", x=0, y=0, color="#ff0000"),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        assert scene["elements"][0]["strokeColor"] == "#ff0000"

    def test_fill_color(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="floor", type="rectangle", x=0, y=0, fill="#e0e0e0"),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        assert scene["elements"][0]["backgroundColor"] == "#e0e0e0"

    def test_stroke_width(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="thick", type="rectangle", x=0, y=0, stroke_width=4),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        assert scene["elements"][0]["strokeWidth"] == 4


class TestDimensions:
    def test_dimension_generates_text(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[],
                dimensions=[
                    SpatialDimension(from_element="wall", value="3m", side="top"),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        # Dimension should create a text annotation
        assert len(scene["elements"]) == 1
        assert scene["elements"][0]["type"] == "text"
        assert "3m" in scene["elements"][0]["text"]


class TestGroups:
    def test_group_sets_group_ids(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="w1", type="rectangle", x=0, y=0),
                    SpatialElement(id="w2", type="rectangle", x=100, y=0),
                ],
                groups=[
                    SpatialGroup(id="walls", label="Walls", children=["w1", "w2"]),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        # Both elements should have groupIds set
        for elem in scene["elements"]:
            if elem["type"] == "rectangle":
                assert len(elem["groupIds"]) == 1


class TestElementIds:
    def test_ids_are_deterministic(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[SpatialElement(id="test", type="rectangle", x=0, y=0)],
            ),
        )
        scene1 = generate_excalidraw(ir)
        scene2 = generate_excalidraw(ir)
        assert scene1["elements"][0]["id"] == scene2["elements"][0]["id"]

    def test_ids_are_unique(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[
                    SpatialElement(id="a", type="rectangle", x=0, y=0),
                    SpatialElement(id="b", type="rectangle", x=100, y=0),
                ],
            ),
        )
        scene = generate_excalidraw(ir)
        ids = [e["id"] for e in scene["elements"]]
        assert len(ids) == len(set(ids))


class TestRequiredFields:
    def test_all_excalidraw_fields_present(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
            spatial=SpatialIR(
                elements=[SpatialElement(id="test", type="rectangle", x=10, y=20, width=100, height=50)],
            ),
        )
        scene = generate_excalidraw(ir)
        elem = scene["elements"][0]
        required_fields = [
            "id", "type", "x", "y", "width", "height", "angle",
            "strokeColor", "backgroundColor", "fillStyle", "strokeWidth",
            "strokeStyle", "roughness", "opacity", "seed", "version",
            "versionNonce", "isDeleted", "groupIds", "frameId",
            "boundElements", "updated", "link", "locked",
        ]
        for field in required_fields:
            assert field in elem, f"Missing field: {field}"


class TestNoSpatialRaises:
    def test_raises_without_spatial(self):
        ir = DiagramIR(
            category=DiagramCategory.BUILDING_PLAN,
            track=DiagramTrack.SPATIAL,
        )
        try:
            generate_excalidraw(ir)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "spatial" in str(e).lower()
