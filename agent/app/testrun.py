"""Run the backend test suite before and after the fix.

The gate is "no new failures", not "all green": if main already has a
failing test (e.g. one that needs the d2 binary), the agent shouldn't be
blocked by it, but it must not break anything that passed before.
"""

import logging
import os
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    __test__ = False  # not a pytest test class
    ran: int
    failed: set[str]
    error: str = ""  # pytest itself couldn't run / collect

    @property
    def summary(self) -> str:
        if self.error:
            return f"pytest error: {self.error}"
        return f"{self.ran - len(self.failed)}/{self.ran} passed"


def parse_junit(xml_text: str) -> tuple[int, set[str]]:
    root = ET.fromstring(xml_text)
    ran, failed = 0, set()
    for case in root.iter("testcase"):
        if case.find("skipped") is not None:
            continue
        ran += 1
        if case.find("failure") is not None or case.find("error") is not None:
            failed.add(f"{case.get('classname')}::{case.get('name')}")
    return ran, failed


# Tests run code the model just edited: keep the PAT and LLM key out of reach
SECRET_ENV = ("GITHUB_TOKEN", "GH_TOKEN", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV}


def new_failures(before: TestResult, after: TestResult) -> set[str]:
    return after.failed - before.failed


def setup_venv(repo: Path, venv: Path) -> None:
    """Install the backend's own requirements from the cloned commit, so the
    image doesn't go stale every time backend/requirements.txt changes."""
    subprocess.run(["python", "-m", "venv", str(venv)], check=True, env=clean_env())
    pip = [str(venv / "bin" / "pip"), "install", "--quiet", "--disable-pip-version-check"]
    subprocess.run([*pip, "-r", str(repo / "backend" / "requirements.txt"), "pytest"], check=True, env=clean_env())


def run_tests(repo: Path, venv: Path, junit: Path, timeout: int) -> TestResult:
    cmd = [str(venv / "bin" / "python"), "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
    try:
        proc = subprocess.run(
            cmd, cwd=repo / "backend", capture_output=True, text=True, timeout=timeout, env=clean_env()
        )
    except subprocess.TimeoutExpired:
        return TestResult(0, set(), error=f"timed out after {timeout}s")
    logger.info("pytest exit %s\n%s", proc.returncode, proc.stdout[-3000:])
    # Exit codes: 0 ok, 1 tests failed, 5 none collected; anything else = broken run
    if proc.returncode not in (0, 1, 5) or not junit.exists():
        return TestResult(0, set(), error=f"exit {proc.returncode}: {proc.stderr[-500:]}")
    ran, failed = parse_junit(junit.read_text())
    return TestResult(ran, failed)
