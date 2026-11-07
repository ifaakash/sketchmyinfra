from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.k8s import DryRunLauncher
from app.main import app, get_collector, get_launcher

TOKEN = "test-token"


class FakeCollector:
    def __init__(self):
        self.calls = []

    async def collect(self, alertname, alerts):
        self.calls.append(alertname)
        return '{"alertname": "%s"}' % alertname


def payload(alertname="GenerationFailuresSpike", status="firing", agent="true", **labels):
    alert_labels = {"alertname": alertname, **labels}
    if agent is not None:
        alert_labels["agent"] = agent
    return {
        "version": "4",
        "status": status,
        "receiver": "agent-dispatcher",
        "groupLabels": {"alertname": alertname},
        "commonLabels": alert_labels,
        "alerts": [
            {
                "status": status,
                "labels": alert_labels,
                "annotations": {"summary": "3 failures in 10m"},
                "startsAt": datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc).isoformat(),
                "fingerprint": "abc123",
            }
        ],
    }


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    path = tmp_path / "token"
    path.write_text(TOKEN + "\n")
    monkeypatch.setattr(settings, "dispatcher_token_file", str(path))
    return path


@pytest.fixture
def launcher():
    return DryRunLauncher()


@pytest.fixture
def collector():
    return FakeCollector()


@pytest.fixture
def client(token_file, launcher, collector):
    app.dependency_overrides[get_launcher] = lambda: launcher
    app.dependency_overrides[get_collector] = lambda: collector
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {TOKEN}"}
