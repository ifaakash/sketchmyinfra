"""smi-agent: incident.json -> Gemini fix -> tests -> PR.

Runs once inside the k3s Job the dispatcher creates. Exit 0 = done (PR
opened, or nothing safe to do); exit 1 = something broke (the Job shows
Failed, `kubectl -n agent logs job/<name>` says why). Never merges.
"""

import json
import logging
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone

from app import repo
from app.config import Settings, settings
from app.edits import EditError, apply_edits, check_path
from app.llm import Gemini
from app.testrun import TestResult, new_failures, run_tests, setup_venv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logger = logging.getLogger("smi-agent")


def slugify(alertname: str, max_len: int = 42) -> str:
    # Same rule as the dispatcher, so branch names match Job names
    slug = re.sub(r"[^a-z0-9]+", "-", alertname.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "alert"


def evidence_stats(incident: dict) -> str:
    return (
        f"{len(incident.get('failed_generations') or [])} failed generation rows, "
        f"{len((incident.get('api_logs') or '').splitlines())} api log lines, "
        f"truncated={incident.get('truncated')}, "
        f"evidence_errors={json.dumps(incident.get('evidence_errors') or {})}"
    )


def pr_body(incident: dict, fix, files: list[str], before: TestResult, after: TestResult) -> str:
    # Raw evidence stays out of the PR: the repo is public and logs/rows can
    # contain user text. Only the model's summary goes in.
    starts = ", ".join(a.get("startsAt") or "?" for a in incident.get("alerts", []))
    changed = "\n".join(f"- `{f}`" for f in files)
    return f"""## Incident
- Alert: `{incident.get('alertname')}` (started {starts})
- Evidence: {evidence_stats(incident)}

## Root cause
{fix.root_cause}

## Change
{fix.summary}

{changed}

## Tests
- Before: {before.summary}
- After: {after.summary}
- New failures: none

---
Opened automatically by smi-agent (pod `{os.environ.get('HOSTNAME', '?')}`).
The evidence it worked from is untrusted production data: review the diff
carefully before merging.
"""


def read_files(cfg: Settings, picks: list[str], tree: set[str]) -> dict[str, str]:
    files = {}
    for p in picks:
        if p not in tree or p in files:
            continue
        files[p] = (cfg.repo_dir / p).read_text(encoding="utf-8", errors="replace")[: cfg.max_file_bytes]
        if len(files) >= cfg.max_files_to_read:
            break
    return files


NETWORK_HOSTS = ("github.com", "api.github.com", "generativelanguage.googleapis.com")


def wait_for_network(timeout: float = 60, interval: float = 1) -> float:
    """Block until every host resolves; return the seconds waited.

    k3s (kube-router) programs NetworkPolicy rules for a new pod shortly
    after it starts, so the first DNS lookups can be dropped. Seen in drills
    as "Could not resolve host" in the first second of the pod's life.
    """
    start = time.monotonic()
    while True:
        try:
            for host in NETWORK_HOSTS:
                socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            return time.monotonic() - start
        except OSError as e:
            if time.monotonic() - start >= timeout:
                raise RuntimeError(f"network not ready after {timeout:.0f}s: {e}") from e
            time.sleep(interval)


def run(cfg: Settings) -> int:
    missing = [n for n, v in (("GITHUB_TOKEN", cfg.github_token), ("GEMINI_API_KEY", cfg.gemini_api_key)) if not v]
    if missing:
        logger.error("Missing env: %s (agent-secrets Secret)", ", ".join(missing))
        return 1

    incident = json.loads(cfg.incident_file.read_text())
    alertname = incident.get("alertname", "unknown")
    branch_prefix = f"agent/{slugify(alertname)}-"
    logger.info("Incident %s: %s", alertname, evidence_stats(incident))
    logger.info("Network ready after %.1fs", wait_for_network())

    if not cfg.dry_run and (existing := repo.open_agent_prs(cfg.repo, branch_prefix)):
        logger.info("Open agent PR already exists for %s, skipping: %s", alertname, existing)
        return 0

    repo.clone(cfg.repo, cfg.base_branch, cfg.repo_dir)
    tree = repo.tracked_files(cfg.repo_dir)
    llm = Gemini(cfg.gemini_api_key, cfg.model)

    pick = llm.pick_files(incident, tree, cfg.max_files_to_read)
    logger.info("Files picked: %s (%s)", pick.files, pick.reasoning)
    files = read_files(cfg, pick.files, set(tree))
    if not files:
        logger.error("Model picked no valid files")
        return 1

    fix = llm.propose_fix(incident, files, cfg.allowed_prefixes)
    logger.info("Root cause: %s", fix.root_cause)
    if not fix.fixable or not fix.edits:
        logger.info("Not a code fix (fixable=%s, %d edits). Nothing to do.", fix.fixable, len(fix.edits))
        return 0
    for e in fix.edits:
        check_path(e.path, cfg.allowed_prefixes)  # refuse before spending time on tests

    setup_venv(cfg.repo_dir, cfg.venv_dir)
    before = run_tests(cfg.repo_dir, cfg.venv_dir, cfg.work_dir / "junit-before.xml", cfg.test_timeout_seconds)
    logger.info("Baseline tests: %s", before.summary)
    if before.error:
        logger.error("Can't establish a test baseline; refusing to open an unverified PR")
        return 1

    try:
        changed = apply_edits(cfg.repo_dir, fix.edits, cfg.allowed_prefixes, cfg.max_edits)
    except EditError as e:
        logger.error("Edits rejected: %s", e)
        return 1
    logger.info("Diff:\n%s", repo.diff(cfg.repo_dir))

    after = run_tests(cfg.repo_dir, cfg.venv_dir, cfg.work_dir / "junit-after.xml", cfg.test_timeout_seconds)
    logger.info("Tests after fix: %s", after.summary)
    if after.error or (broken := new_failures(before, after)):
        logger.error("Fix breaks tests: %s", after.error or sorted(broken))
        return 1

    if cfg.dry_run:
        logger.info("AGENT_DRY_RUN: not pushing. Would open PR: %s", fix.title)
        return 0

    # Push from a fresh clone: the test run executed model-edited code with
    # write access to repo_dir/.git (hooks, config), so don't trust that one
    branch = f"{branch_prefix}{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    push_dir = cfg.work_dir / "push"
    repo.clone(cfg.repo, cfg.base_branch, push_dir)
    apply_edits(push_dir, fix.edits, cfg.allowed_prefixes, cfg.max_edits)
    repo.commit_and_push(push_dir, branch, changed, f"{fix.title}\n\n{fix.root_cause}")
    url = repo.create_pr(cfg.repo, cfg.base_branch, branch, fix.title, pr_body(incident, fix, changed, before, after))
    logger.info("Opened PR: %s", url)
    return 0


def main() -> None:
    try:
        sys.exit(run(settings))
    except Exception:
        logger.exception("Agent failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
