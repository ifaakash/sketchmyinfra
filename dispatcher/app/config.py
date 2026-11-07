from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # "dry-run" logs the incident + Job manifest instead of calling k8s
    dispatch_mode: Literal["k8s", "dry-run"] = "dry-run"

    # Shared secret Alertmanager sends as "Authorization: Bearer <token>".
    # Read on every request, so rotating the file needs no restart.
    dispatcher_token_file: str = "/run/secrets/dispatcher_token"

    # Kubeconfig for the `dispatcher` ServiceAccount (see k8s/agent/)
    kubeconfig: str = "/run/secrets/kubeconfig"

    # Agent Job
    agent_namespace: str = "agent"
    agent_image: str = "busybox:1.37"
    # Empty = use the image's own entrypoint. JSON list in env, e.g.
    # AGENT_COMMAND='["cat", "/incident/incident.json"]'
    agent_command: list[str] = []
    agent_service_account: str = "agent"
    agent_secret_name: str = "agent-secrets"
    agent_run_as_user: int = 1000
    job_deadline_seconds: int = 900
    # Finished Jobs are kept this long; the cooldown check reads them
    job_ttl_seconds: int = 86400

    # Guards
    cooldown_seconds: int = 3600
    max_active_jobs: int = 1

    # Evidence. DOCKER_HOST (e.g. tcp://docker-proxy:2375) is read by the
    # docker SDK itself.
    api_service_name: str = "api"
    # Read-only role; empty disables DB evidence
    evidence_database_url: str = ""
    evidence_window_minutes: int = 30
    failed_rows_limit: int = 20
    log_tail: int = 300
    # ConfigMaps cap out at 1MiB; leave plenty of headroom
    evidence_max_bytes: int = 200_000

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
