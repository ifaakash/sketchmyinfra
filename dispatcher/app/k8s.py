"""Launch agent Jobs on k3s, and decide whether we're allowed to.

k3s is the only state store: cooldown and concurrency are derived from the
Jobs that already exist (label app=smi-agent), so restarting the dispatcher
can't reset a cooldown. Finished Jobs are kept for job_ttl_seconds for that.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import yaml

from app.config import settings

logger = logging.getLogger(__name__)

APP_LABEL = "smi-agent"
INCIDENT_KEY = "incident.json"


@dataclass
class JobInfo:
    name: str
    alertname: str
    created_at: datetime
    finished: bool


def slugify(alertname: str, max_len: int = 42) -> str:
    """DNS-1123 / label-value safe: lowercase alnum and '-'."""
    slug = re.sub(r"[^a-z0-9]+", "-", alertname.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "alert"


def make_job_name(alertname: str, now: datetime) -> str:
    # agent-(6) + slug(<=42) + -(1) + timestamp(14) <= 63 chars
    return f"agent-{slugify(alertname)}-{now:%Y%m%d%H%M%S}"


def check_guard(
    jobs: list[JobInfo],
    alertname: str,
    now: datetime,
    cooldown_seconds: int,
    max_active_jobs: int,
) -> str | None:
    """Return a skip reason ("busy" / "cooldown"), or None if we may dispatch."""
    if sum(1 for j in jobs if not j.finished) >= max_active_jobs:
        return "busy"
    slug = slugify(alertname)
    cutoff = now - timedelta(seconds=cooldown_seconds)
    if any(j.alertname == slug and j.created_at >= cutoff for j in jobs):
        return "cooldown"
    return None


def configmap_name(job_name: str) -> str:
    return f"{job_name}-incident"


def build_job(job_name: str, alertname: str) -> dict:
    labels = {"app": APP_LABEL, "alertname": slugify(alertname)}
    uid = settings.agent_run_as_user
    container = {
        "name": "agent",
        "image": settings.agent_image,
        "env": [
            {"name": "INCIDENT_FILE", "value": f"/incident/{INCIDENT_KEY}"},
            {"name": "WORK_DIR", "value": "/work"},
            # Root FS is read-only: git/gh/pip need a writable HOME
            {"name": "HOME", "value": "/work"},
        ],
        # optional: the placeholder image runs before the secret exists
        "envFrom": [{"secretRef": {"name": settings.agent_secret_name, "optional": True}}],
        "resources": {
            "requests": {"cpu": "500m", "memory": "512Mi"},
            "limits": {"cpu": "1", "memory": "1Gi"},
        },
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        "volumeMounts": [
            {"name": "incident", "mountPath": "/incident", "readOnly": True},
            {"name": "work", "mountPath": "/work"},
            {"name": "tmp", "mountPath": "/tmp"},
        ],
    }
    if settings.agent_command:
        container["command"] = settings.agent_command

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": job_name, "namespace": settings.agent_namespace, "labels": labels},
        "spec": {
            # One shot: a failed fix attempt is not retried (no surprise LLM bills)
            "backoffLimit": 0,
            "activeDeadlineSeconds": settings.job_deadline_seconds,
            "ttlSecondsAfterFinished": settings.job_ttl_seconds,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": settings.agent_service_account,
                    # The agent never talks to the k8s API
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": uid,
                        "runAsGroup": uid,
                        "fsGroup": uid,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [container],
                    "volumes": [
                        {"name": "incident", "configMap": {"name": configmap_name(job_name)}},
                        {"name": "work", "emptyDir": {"sizeLimit": "2Gi"}},
                        {"name": "tmp", "emptyDir": {"sizeLimit": "256Mi"}},
                    ],
                },
            },
        },
    }


def build_configmap(job_name: str, job_uid: str, alertname: str, incident: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": configmap_name(job_name),
            "namespace": settings.agent_namespace,
            "labels": {"app": APP_LABEL, "alertname": slugify(alertname)},
            # Garbage-collected together with its Job (after the Job's TTL)
            "ownerReferences": [
                {"apiVersion": "batch/v1", "kind": "Job", "name": job_name, "uid": job_uid}
            ],
        },
        "data": {INCIDENT_KEY: incident},
    }


def _is_finished(job) -> bool:
    for cond in (job.status.conditions or []) if job.status else []:
        if cond.type in ("Complete", "Failed") and cond.status == "True":
            return True
    return False


class K8sLauncher:
    def __init__(self, api_client=None):
        from kubernetes import client, config

        api_client = api_client or config.new_client_from_config(config_file=settings.kubeconfig)
        self.batch = client.BatchV1Api(api_client)
        self.core = client.CoreV1Api(api_client)

    def recent_jobs(self) -> list[JobInfo]:
        jobs = self.batch.list_namespaced_job(
            settings.agent_namespace, label_selector=f"app={APP_LABEL}"
        )
        return [
            JobInfo(
                name=j.metadata.name,
                alertname=(j.metadata.labels or {}).get("alertname", ""),
                created_at=j.metadata.creation_timestamp,
                finished=_is_finished(j),
            )
            for j in jobs.items
        ]

    def launch(self, job_name: str, alertname: str, incident: str) -> None:
        # Job first so the ConfigMap can point its ownerReference at the Job's
        # uid. The pod waits in ContainerCreating until the ConfigMap exists.
        created = self.batch.create_namespaced_job(
            settings.agent_namespace, build_job(job_name, alertname)
        )
        try:
            self.core.create_namespaced_config_map(
                settings.agent_namespace,
                build_configmap(job_name, created.metadata.uid, alertname, incident),
            )
        except Exception:
            # Don't leave a Job stuck waiting for a ConfigMap that never comes
            logger.exception("ConfigMap create failed; deleting Job %s", job_name)
            self.batch.delete_namespaced_job(
                job_name, settings.agent_namespace, propagation_policy="Background"
            )
            raise


class DryRunLauncher:
    """Logs what would be created. Keeps an in-memory job list so the
    cooldown is still exercised locally (it resets on restart — fine for dev)."""

    def __init__(self):
        self.jobs: list[JobInfo] = []

    def recent_jobs(self) -> list[JobInfo]:
        return list(self.jobs)

    def launch(self, job_name: str, alertname: str, incident: str) -> None:
        manifests = [
            build_job(job_name, alertname),
            build_configmap(job_name, "<job-uid>", alertname, incident),
        ]
        logger.info("[dry-run] would create:\n%s", yaml.safe_dump_all(manifests, sort_keys=False))
        self.jobs.append(
            JobInfo(
                name=job_name,
                alertname=slugify(alertname),
                created_at=datetime.now(timezone.utc),
                # Nothing actually runs, so only the cooldown applies
                finished=True,
            )
        )
