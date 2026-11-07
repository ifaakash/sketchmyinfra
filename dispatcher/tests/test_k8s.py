from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.config import settings
from app.k8s import (
    JobInfo,
    K8sLauncher,
    build_configmap,
    build_job,
    check_guard,
    make_job_name,
    slugify,
)

NOW = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)


def _job(alertname="generationfailuresspike", minutes_ago=0, finished=True):
    return JobInfo("j", alertname, NOW - timedelta(minutes=minutes_ago), finished)


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------

def test_job_name_is_dns_safe_and_short():
    name = make_job_name("Very_Long.Alert Name " * 10, NOW)
    assert len(name) <= 63
    assert name == name.lower()
    assert all(c.isalnum() or c == "-" for c in name)
    assert name.endswith("-20261107100000")


def test_slugify_never_empty():
    assert slugify("!!!") == "alert"


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

def test_guard_allows_when_no_jobs():
    assert check_guard([], "GenerationFailuresSpike", NOW, 3600, 1) is None


def test_guard_busy_when_a_job_is_running():
    jobs = [_job("api5xxrate", minutes_ago=120, finished=False)]
    assert check_guard(jobs, "GenerationFailuresSpike", NOW, 3600, 1) == "busy"


def test_guard_cooldown_within_window():
    jobs = [_job(minutes_ago=30)]
    assert check_guard(jobs, "GenerationFailuresSpike", NOW, 3600, 1) == "cooldown"


def test_guard_allows_after_cooldown():
    jobs = [_job(minutes_ago=61)]
    assert check_guard(jobs, "GenerationFailuresSpike", NOW, 3600, 1) is None


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

def test_job_is_one_shot_and_bounded():
    spec = build_job("agent-x-1", "GenerationFailuresSpike")["spec"]
    assert spec["backoffLimit"] == 0
    assert spec["activeDeadlineSeconds"] == settings.job_deadline_seconds
    assert spec["ttlSecondsAfterFinished"] == settings.job_ttl_seconds
    assert spec["template"]["spec"]["restartPolicy"] == "Never"


def test_job_pod_is_locked_down():
    pod = build_job("agent-x-1", "GenerationFailuresSpike")["spec"]["template"]["spec"]
    container = pod["containers"][0]

    assert pod["automountServiceAccountToken"] is False
    assert pod["serviceAccountName"] == settings.agent_service_account
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["securityContext"]["seccompProfile"] == {"type": "RuntimeDefault"}
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }
    assert "limits" in container["resources"]


def test_job_mounts_incident_configmap():
    pod = build_job("agent-x-1", "A")["spec"]["template"]["spec"]
    volumes = {v["name"]: v for v in pod["volumes"]}
    assert volumes["incident"]["configMap"]["name"] == "agent-x-1-incident"


def test_job_command_only_set_when_configured(monkeypatch):
    assert "command" not in build_job("j", "A")["spec"]["template"]["spec"]["containers"][0]
    monkeypatch.setattr(settings, "agent_command", ["cat", "/incident/incident.json"])
    container = build_job("j", "A")["spec"]["template"]["spec"]["containers"][0]
    assert container["command"] == ["cat", "/incident/incident.json"]


def test_configmap_is_owned_by_job():
    cm = build_configmap("agent-x-1", "uid-123", "A", "{}")
    owner = cm["metadata"]["ownerReferences"][0]
    assert owner == {"apiVersion": "batch/v1", "kind": "Job", "name": "agent-x-1", "uid": "uid-123"}
    assert cm["data"]["incident.json"] == "{}"


# ---------------------------------------------------------------------------
# K8sLauncher against fake API objects
# ---------------------------------------------------------------------------

class _FakeBatch:
    def __init__(self, items=()):
        self.items = list(items)
        self.created = []
        self.deleted = []

    def list_namespaced_job(self, namespace, label_selector):
        assert label_selector == "app=smi-agent"
        return SimpleNamespace(items=self.items)

    def create_namespaced_job(self, namespace, body):
        self.created.append(body)
        return SimpleNamespace(metadata=SimpleNamespace(uid="uid-123"))

    def delete_namespaced_job(self, name, namespace, propagation_policy):
        self.deleted.append(name)


class _FakeCore:
    def __init__(self, fail=False):
        self.fail = fail
        self.created = []

    def create_namespaced_config_map(self, namespace, body):
        if self.fail:
            raise RuntimeError("forbidden")
        self.created.append(body)


def _launcher(batch, core):
    launcher = K8sLauncher.__new__(K8sLauncher)
    launcher.batch, launcher.core = batch, core
    return launcher


def _k8s_job(name, alertname, conditions):
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, labels={"alertname": alertname}, creation_timestamp=NOW),
        status=SimpleNamespace(conditions=conditions),
    )


def test_recent_jobs_reads_finished_state():
    done = SimpleNamespace(type="Complete", status="True")
    batch = _FakeBatch([_k8s_job("a", "x", [done]), _k8s_job("b", "y", None)])
    jobs = _launcher(batch, _FakeCore()).recent_jobs()
    assert [(j.name, j.alertname, j.finished) for j in jobs] == [("a", "x", True), ("b", "y", False)]


def test_launch_creates_job_then_owned_configmap():
    batch, core = _FakeBatch(), _FakeCore()
    _launcher(batch, core).launch("agent-x-1", "A", '{"k": 1}')
    assert batch.created[0]["metadata"]["name"] == "agent-x-1"
    assert core.created[0]["metadata"]["ownerReferences"][0]["uid"] == "uid-123"


def test_launch_rolls_back_job_when_configmap_fails():
    batch = _FakeBatch()
    with pytest.raises(RuntimeError):
        _launcher(batch, _FakeCore(fail=True)).launch("agent-x-1", "A", "{}")
    assert batch.deleted == ["agent-x-1"]
