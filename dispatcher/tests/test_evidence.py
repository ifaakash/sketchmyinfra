import asyncio
import json

from app import evidence
from app.config import settings
from app.evidence import UNTRUSTED_NOTE, build_incident, redact
from app.schemas import Alert


def _alert():
    return Alert(status="firing", labels={"alertname": "A", "agent": "true"}, annotations={"summary": "s"})


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def test_redacts_secrets_and_ips():
    text = (
        "Authorization: Bearer abc.def.ghi key=AIza" + "x" * 35
        + " ghp_" + "a" * 36 + " sk-ant-" + "b" * 30
        + " postgresql://smi:hunter2@db:5432/x password=hunter2 from 203.0.113.7"
    )
    out = redact(text)
    for secret in ["abc.def.ghi", "AIza", "ghp_", "sk-ant-", "hunter2", "203.0.113.7"]:
        assert secret not in out


def test_redact_keeps_ordinary_text():
    line = "2026-11-07 ERROR GeminiError: quota exceeded for model gemini-2.5-flash"
    assert redact(line) == line


# ---------------------------------------------------------------------------
# Incident assembly
# ---------------------------------------------------------------------------

def test_incident_is_marked_untrusted_and_redacted():
    rows = [{"created_at": "t", "status": "gemini_error", "renderer": None, "category": None,
             "error_message": "bad key AIza" + "x" * 35, "puml_code": None}]
    incident = json.loads(build_incident("A", [_alert()], rows, "log line", {}, 200_000))

    assert incident["_note"] == UNTRUSTED_NOTE
    assert "AIza" not in incident["failed_generations"][0]["error_message"]
    assert incident["api_logs"] == "log line"
    assert incident["truncated"] is False


def test_incident_never_contains_prompt_columns():
    assert "prompt" not in evidence.FAILED_GENERATIONS_SQL
    assert "ip_address" not in evidence.FAILED_GENERATIONS_SQL
    assert "user_id" not in evidence.FAILED_GENERATIONS_SQL


def test_incident_is_capped_keeping_newest_logs():
    logs = "\n".join(f"line {i} " + "x" * 80 for i in range(5000))
    out = build_incident("A", [_alert()], [], logs, {}, 20_000)
    incident = json.loads(out)

    assert len(out.encode()) <= 20_000
    assert incident["truncated"] is True
    assert incident["api_logs"].endswith("line 4999 " + "x" * 80)
    assert "line 0 " not in incident["api_logs"]


def test_incident_drops_oldest_rows_when_still_too_big():
    rows = [{"created_at": str(i), "status": "autofix_failed", "renderer": "d2", "category": None,
             "error_message": "e" * 900, "puml_code": "p" * 1900} for i in range(20)]
    out = build_incident("A", [_alert()], rows, "", {}, 10_000)
    incident = json.loads(out)

    assert len(out.encode()) <= 10_000
    kept = [r["created_at"] for r in incident["failed_generations"]]
    assert kept and kept == [str(i) for i in range(len(kept))]  # newest-first prefix kept


# ---------------------------------------------------------------------------
# Best-effort collection
# ---------------------------------------------------------------------------

def test_collector_survives_evidence_failures(monkeypatch):
    monkeypatch.setattr(settings, "evidence_database_url", "postgresql://ro@db/x")

    async def _db_down():
        raise ConnectionError("db unreachable")

    def _no_docker():
        raise RuntimeError("proxy unreachable")

    monkeypatch.setattr(evidence, "fetch_failed_generations", _db_down)
    monkeypatch.setattr(evidence, "fetch_api_logs", _no_docker)

    incident = json.loads(asyncio.run(evidence.EvidenceCollector().collect("A", [_alert()])))
    assert incident["evidence_errors"] == {
        "failed_generations": "db unreachable",
        "api_logs": "proxy unreachable",
    }
    assert incident["alertname"] == "A"
