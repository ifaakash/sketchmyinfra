"""Agent dispatcher: Alertmanager webhook -> evidence -> k8s agent Job.

POST /alert   Alertmanager webhook receiver (Bearer token)
GET  /healthz liveness for the compose healthcheck
GET  /metrics Prometheus scrape
"""

import asyncio
import hmac
import logging
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings
from app.evidence import EvidenceCollector
from app.k8s import DryRunLauncher, K8sLauncher, check_guard, make_job_name
from app.metrics import record
from app.schemas import Alert, AlertmanagerPayload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="SketchMyInfra Agent Dispatcher", docs_url=None, redoc_url=None, openapi_url=None)

# Guard check + launch must be atomic, or two webhooks arriving together
# would both pass the cooldown check
_dispatch_lock = asyncio.Lock()


@lru_cache
def get_launcher():
    if settings.dispatch_mode == "k8s":
        return K8sLauncher()
    return DryRunLauncher()


def get_collector() -> EvidenceCollector:
    return EvidenceCollector()


def require_token(authorization: str | None = Header(default=None)) -> None:
    try:
        with open(settings.dispatcher_token_file) as f:
            expected = f.read().strip()
    except OSError:
        expected = ""
    if not expected:
        # Fail closed: no configured token means nobody gets in
        logger.error("Dispatcher token file %s missing or empty", settings.dispatcher_token_file)
    presented = (authorization or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(presented.encode(), expected.encode()):
        record("unauthorized")
        raise HTTPException(status_code=401, detail="unauthorized")


def select_alerts(payload: AlertmanagerPayload) -> tuple[dict[str, list[Alert]], str]:
    """Group firing, agent-enabled alerts by alertname.

    Returns (groups, skip_reason). Only rules labelled agent="true" are
    code-bug candidates; e.g. ApiMetricsDown is an infra problem.
    """
    firing = [a for a in payload.alerts if a.status == "firing"]
    if not firing:
        return {}, "resolved"
    groups: dict[str, list[Alert]] = {}
    for a in firing:
        if a.labels.get("agent") == "true":
            groups.setdefault(a.labels.get("alertname", "unknown"), []).append(a)
    return groups, "" if groups else "not-agent"


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "mode": settings.dispatch_mode}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/alert", dependencies=[Depends(require_token)])
async def alert(
    payload: AlertmanagerPayload,
    launcher=Depends(get_launcher),
    collector: EvidenceCollector = Depends(get_collector),
):
    groups, skip_reason = select_alerts(payload)
    if not groups:
        record("ignored")
        return {"skipped": skip_reason, "results": []}

    results = []
    for alertname, alerts in groups.items():
        async with _dispatch_lock:
            results.append(await _dispatch_one(launcher, collector, alertname, alerts))

    if any(r["result"] == "error" for r in results):
        # Non-2xx makes Alertmanager retry; the cooldown stops a double launch
        status = 503
    elif any(r["result"] == "dispatched" for r in results):
        status = 202
    else:
        status = 200
    return JSONResponse(status_code=status, content={"results": results})


async def _dispatch_one(launcher, collector: EvidenceCollector, alertname: str, alerts: list[Alert]) -> dict:
    now = datetime.now(timezone.utc)
    try:
        jobs = await asyncio.to_thread(launcher.recent_jobs)
    except Exception as e:
        logger.exception("Listing agent jobs failed")
        record("error")
        return {"alertname": alertname, "result": "error", "detail": f"list jobs: {e}"}

    reason = check_guard(jobs, alertname, now, settings.cooldown_seconds, settings.max_active_jobs)
    if reason:
        logger.info("Skipping %s: %s", alertname, reason)
        record(reason)
        return {"alertname": alertname, "result": reason}

    incident = await collector.collect(alertname, alerts)
    job_name = make_job_name(alertname, now)
    try:
        await asyncio.to_thread(launcher.launch, job_name, alertname, incident)
    except Exception as e:
        logger.exception("Launching agent job failed")
        record("error")
        return {"alertname": alertname, "result": "error", "detail": f"launch: {e}"}

    logger.info("Dispatched %s for %s", job_name, alertname)
    record("dispatched")
    return {"alertname": alertname, "result": "dispatched", "job": job_name}
