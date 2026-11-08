"""Agent settings, all from env (the Job injects INCIDENT_FILE/WORK_DIR/HOME,
the agent-secrets Secret injects GITHUB_TOKEN/GEMINI_API_KEY)."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    incident_file: Path = field(default_factory=lambda: Path(os.environ.get("INCIDENT_FILE", "/incident/incident.json")))
    work_dir: Path = field(default_factory=lambda: Path(os.environ.get("WORK_DIR", "/work")))
    repo: str = field(default_factory=lambda: os.environ.get("AGENT_REPO", "ifaakash/sketchmyinfra"))
    base_branch: str = field(default_factory=lambda: os.environ.get("AGENT_BASE_BRANCH", "main"))
    model: str = field(default_factory=lambda: os.environ.get("AGENT_MODEL", "gemini-2.5-flash"))
    # Dry run: do everything except push + open the PR (diff goes to the log)
    dry_run: bool = field(default_factory=lambda: _bool("AGENT_DRY_RUN", False))
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))

    # The model may only edit these. Keeps a prompt-injected fix away from
    # CI (.github/), Dockerfiles, k8s manifests, the dispatcher and this agent.
    allowed_prefixes: tuple[str, ...] = ("backend/app/", "backend/tests/")
    max_files_to_read: int = 8
    max_file_bytes: int = 60_000
    max_edits: int = 10
    test_timeout_seconds: int = 300

    @property
    def repo_dir(self) -> Path:
        return self.work_dir / "repo"

    @property
    def venv_dir(self) -> Path:
        return self.work_dir / "venv"


settings = Settings()
