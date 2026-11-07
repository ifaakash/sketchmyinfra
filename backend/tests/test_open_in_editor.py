"""Tests for the Open in Editor contract: the generate response carries the
graph IR + generation id, and the opened-in-editor endpoint is idempotent.

Same approach as test_metrics.py: no database harness, so handlers are called
directly with stub sessions and the Gemini/render calls patched out.
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from prometheus_client import REGISTRY

from app.ir.schema import (
    DiagramCategory,
    DiagramIR,
    DiagramTrack,
    GraphIR,
    IREdge,
    IRNode,
    SpatialElement,
    SpatialIR,
)
from app.routers import generate_v2
from app.schemas import GenerateRequest


class _StubSession:
    """Accepts add/commit like AsyncSession without touching a database."""

    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


class _ScriptedSession:
    """Returns queued scalar results from execute(), one per call."""

    def __init__(self, *scalars):
        self._scalars = list(scalars)
        self.commits = 0

    async def execute(self, stmt):
        value = self._scalars.pop(0)
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    async def commit(self):
        self.commits += 1


def _request():
    return SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.7"))


def _opens(renderer: str) -> float:
    return REGISTRY.get_sample_value("smi_editor_opens_total", {"renderer": renderer}) or 0.0


@pytest.fixture
def no_rate_limit(monkeypatch):
    async def _allow(*args, **kwargs):
        return None

    monkeypatch.setattr(generate_v2, "_check_rate_limit", _allow)


def _use_ir(monkeypatch, ir: DiagramIR):
    async def _extract(prompt):
        return ir

    async def _render(code, fmt):
        return "data:image/svg+xml;base64,"

    monkeypatch.setattr(generate_v2, "extract_diagram_ir", _extract)
    monkeypatch.setattr(generate_v2, "render_d2", _render)
    monkeypatch.setattr(generate_v2, "render_puml", _render)


# ---------------------------------------------------------------------------
# Generate response
# ---------------------------------------------------------------------------

def test_graph_response_includes_ir_and_generation_id(monkeypatch, no_rate_limit):
    ir = DiagramIR(
        category=DiagramCategory.SYSTEM_ARCHITECTURE,
        track=DiagramTrack.GRAPH,
        graph=GraphIR(
            nodes=[IRNode(id="api", label="API"), IRNode(id="db", label="DB", type="database")],
            edges=[IREdge(source="api", target="db")],
        ),
    )
    _use_ir(monkeypatch, ir)
    db = _StubSession()

    resp = asyncio.run(generate_v2.generate(
        GenerateRequest(prompt="api talks to a db"), _request(), None, db,
    ))

    assert resp.ir["graph"]["nodes"][0]["id"] == "api"
    # The id returned is the id of the row written, so the editor can mark it
    assert resp.generation_id == db.added[0].id


def test_spatial_response_has_no_ir(monkeypatch, no_rate_limit):
    ir = DiagramIR(
        category=DiagramCategory.BUILDING_PLAN,
        track=DiagramTrack.SPATIAL,
        spatial=SpatialIR(elements=[
            SpatialElement(id="room", type="rectangle", x=0, y=0, width=100, height=100),
        ]),
    )
    _use_ir(monkeypatch, ir)

    resp = asyncio.run(generate_v2.generate(
        GenerateRequest(prompt="a single room"), _request(), None, _StubSession(),
    ))

    assert resp.renderer == "excalidraw"
    assert resp.ir is None
    assert resp.generation_id is not None


# ---------------------------------------------------------------------------
# opened-in-editor
# ---------------------------------------------------------------------------

def test_first_open_is_recorded_and_counted():
    db = _ScriptedSession("d2")  # UPDATE ... RETURNING renderer hit a row
    before = _opens("d2")

    asyncio.run(generate_v2.record_opened_in_editor(uuid.uuid4(), db))

    assert db.commits == 1
    assert _opens("d2") == before + 1


def test_repeat_open_is_a_no_op():
    gid = uuid.uuid4()
    db = _ScriptedSession(None, gid)  # UPDATE matched nothing; row exists
    before = _opens("d2")

    asyncio.run(generate_v2.record_opened_in_editor(gid, db))

    assert db.commits == 0
    assert _opens("d2") == before


def test_unknown_generation_is_404():
    db = _ScriptedSession(None, None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(generate_v2.record_opened_in_editor(uuid.uuid4(), db))

    assert exc.value.status_code == 404
