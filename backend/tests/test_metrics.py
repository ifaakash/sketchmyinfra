"""Tests for Prometheus metrics: /metrics exposure and generation counters.

No database harness exists (see test_admin.py), so the generate handler is
called directly with a stub session and Gemini/rate-limit patched out.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.main import app
from app.routers import generate_v2
from app.schemas import GenerateRequest, RenderErrorReport
from app.services.gemini import GeminiError


class _StubSession:
    """Accepts add/commit like AsyncSession without touching a database."""

    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


def _count(status: str, renderer: str, source: str = "server") -> float:
    value = REGISTRY.get_sample_value(
        "smi_generations_total",
        {"status": status, "renderer": renderer, "source": source},
    )
    return value or 0.0


def _request():
    return SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.7"))


@pytest.fixture
def no_rate_limit(monkeypatch):
    async def _allow(*args, **kwargs):
        return None

    monkeypatch.setattr(generate_v2, "_check_rate_limit", _allow)


# ---------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------

def test_metrics_endpoint_exposes_http_and_generation_metrics():
    client = TestClient(app)
    client.get("/api/health")

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
    assert "smi_generations_total" in resp.text


def test_health_and_metrics_are_not_instrumented():
    """Probes and scrapes would otherwise dominate http_requests_total."""
    client = TestClient(app)
    client.get("/api/health")
    client.get("/metrics")

    body = client.get("/metrics").text
    assert 'handler="/api/health"' not in body
    assert 'handler="/metrics"' not in body


def test_metrics_endpoint_hidden_from_openapi():
    paths = {route.path for route in app.routes if getattr(route, "include_in_schema", False)}
    assert "/metrics" not in paths


# ---------------------------------------------------------------------------
# Generation counters
# ---------------------------------------------------------------------------

def test_gemini_failure_increments_failure_counter(monkeypatch, no_rate_limit):
    async def _fail(prompt):
        raise GeminiError("quota exceeded")

    monkeypatch.setattr(generate_v2, "extract_diagram_ir", _fail)
    before = _count("gemini_error", "unknown")
    db = _StubSession()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(generate_v2.generate(
            GenerateRequest(prompt="three tier app on aws"), _request(), None, db,
        ))

    assert exc.value.status_code == 502
    assert _count("gemini_error", "unknown") == before + 1
    # The DB row is still written — metrics add to it, they don't replace it
    assert db.added[0].status == "gemini_error"


def test_client_render_error_is_labelled_client():
    """The public render-error endpoint must not inflate server-side failures."""
    before_client = _count("render_error", "plantuml", source="client")
    before_server = _count("render_error", "plantuml", source="server")

    asyncio.run(generate_v2.report_render_error(
        RenderErrorReport(prompt="x", renderer="plantuml", error_message="boom"),
        _request(), None, _StubSession(),
    ))

    assert _count("render_error", "plantuml", source="client") == before_client + 1
    assert _count("render_error", "plantuml", source="server") == before_server
