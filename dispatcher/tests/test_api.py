from prometheus_client import REGISTRY

from tests.conftest import payload


def _count(result: str) -> float:
    return REGISTRY.get_sample_value("smi_dispatcher_alerts_total", {"result": result}) or 0.0


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_missing_token_is_rejected(client):
    resp = client.post("/alert", json=payload())
    assert resp.status_code == 401


def test_wrong_token_is_rejected(client):
    resp = client.post("/alert", json=payload(), headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_auth_checked_before_body_validation(client):
    """An unauthenticated caller learns nothing about the payload schema."""
    resp = client.post("/alert", json={"garbage": True})
    assert resp.status_code == 401


def test_missing_token_file_fails_closed(client, token_file, auth):
    token_file.unlink()
    resp = client.post("/alert", json=payload(), headers=auth)
    assert resp.status_code == 401


def test_healthz_needs_no_auth(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def test_resolved_alert_is_ignored(client, auth, collector):
    resp = client.post("/alert", json=payload(status="resolved"), headers=auth)
    assert resp.status_code == 200
    assert resp.json()["skipped"] == "resolved"
    assert collector.calls == []


def test_alert_without_agent_label_is_ignored(client, auth, collector):
    resp = client.post("/alert", json=payload("ApiMetricsDown", agent=None), headers=auth)
    assert resp.status_code == 200
    assert resp.json()["skipped"] == "not-agent"
    assert collector.calls == []


# ---------------------------------------------------------------------------
# Dispatch + guards
# ---------------------------------------------------------------------------

def test_firing_agent_alert_is_dispatched(client, auth, launcher, collector):
    before = _count("dispatched")
    resp = client.post("/alert", json=payload(), headers=auth)

    assert resp.status_code == 202
    result = resp.json()["results"][0]
    assert result["result"] == "dispatched"
    assert result["job"].startswith("agent-generationfailuresspike-")
    assert collector.calls == ["GenerationFailuresSpike"]
    assert len(launcher.jobs) == 1
    assert _count("dispatched") == before + 1


def test_repeat_alert_hits_cooldown(client, auth, collector):
    client.post("/alert", json=payload(), headers=auth)
    resp = client.post("/alert", json=payload(), headers=auth)

    assert resp.status_code == 200
    assert resp.json()["results"][0]["result"] == "cooldown"
    # Evidence isn't collected for a skipped dispatch
    assert collector.calls == ["GenerationFailuresSpike"]


def test_cooldown_is_per_alertname(client, auth):
    client.post("/alert", json=payload("GenerationFailuresSpike"), headers=auth)
    resp = client.post("/alert", json=payload("Api5xxRate"), headers=auth)
    assert resp.json()["results"][0]["result"] == "dispatched"


def test_launch_failure_returns_503_so_alertmanager_retries(client, auth, launcher):
    def _boom(*args):
        raise RuntimeError("k8s api down")

    launcher.launch = _boom
    resp = client.post("/alert", json=payload(), headers=auth)

    assert resp.status_code == 503
    assert resp.json()["results"][0]["result"] == "error"


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "smi_dispatcher_alerts_total" in resp.text
