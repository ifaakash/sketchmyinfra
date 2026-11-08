"""git + gh. The token is passed to git through an inline credential helper
that reads $GITHUB_TOKEN, so it never lands in .git/config, a remote URL or
the logs.

The helper is scoped to https://github.com and hooks are disabled: the test
run executes model-edited code, which could plant a hook or rewrite a remote
(url.insteadOf) to leak the token. main.py also pushes from a fresh clone.
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Shell snippet run by git; $GITHUB_TOKEN is expanded at call time
CREDENTIAL_HELPER = '!f() { echo username=x-access-token; echo "password=$GITHUB_TOKEN"; }; f'
GIT_AUTH = [
    "-c", "credential.helper=",
    "-c", f"credential.https://github.com.helper={CREDENTIAL_HELPER}",
    "-c", "core.hooksPath=/dev/null",
]

BOT_NAME = "smi-agent"
BOT_EMAIL = "smi-agent@users.noreply.github.com"


def run(cmd: list[str], cwd: Path | None = None) -> str:
    logger.info("$ %s", " ".join(c if ".helper=!" not in c else "credential.helper=<env>" for c in cmd))
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} {cmd[1]} failed ({proc.returncode}): {proc.stderr.strip()[-1000:]}")
    return proc.stdout


def clone(repo: str, base: str, dest: Path) -> None:
    run(["git", *GIT_AUTH, "clone", "--depth", "1", "--branch", base, f"https://github.com/{repo}.git", str(dest)])
    run(["git", "config", "user.name", BOT_NAME], cwd=dest)
    run(["git", "config", "user.email", BOT_EMAIL], cwd=dest)


def tracked_files(repo_dir: Path, prefix: str = "backend/") -> list[str]:
    out = run(["git", "ls-files", prefix], cwd=repo_dir)
    return [p for p in out.splitlines() if p.endswith((".py", ".txt", ".ini", ".toml", ".cfg"))]


def open_agent_prs(repo: str, branch_prefix: str) -> list[str]:
    """Open PRs from an earlier run for the same alert: don't stack duplicates."""
    out = run(["gh", "pr", "list", "--repo", repo, "--state", "open", "--json", "headRefName,url", "--limit", "100"])
    return [pr["url"] for pr in json.loads(out) if pr["headRefName"].startswith(branch_prefix)]


def diff(repo_dir: Path) -> str:
    return run(["git", "diff"], cwd=repo_dir)


def commit_and_push(repo_dir: Path, branch: str, files: list[str], message: str) -> None:
    run(["git", "checkout", "-b", branch], cwd=repo_dir)
    run(["git", "add", "--", *files], cwd=repo_dir)
    run(["git", "-c", "core.hooksPath=/dev/null", "commit", "-m", message], cwd=repo_dir)
    run(["git", *GIT_AUTH, "push", "origin", branch], cwd=repo_dir)


def create_pr(repo: str, base: str, branch: str, title: str, body: str) -> str:
    out = run(["gh", "pr", "create", "--repo", repo, "--base", base, "--head", branch, "--title", title, "--body", body])
    return out.strip().splitlines()[-1]
