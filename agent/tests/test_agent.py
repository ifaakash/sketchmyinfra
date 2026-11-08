from pathlib import Path

import pytest

from app import main
from app.edits import Edit, EditError, apply_edits, check_path
from app.testrun import TestResult, new_failures, parse_junit

ALLOWED = ("backend/app/", "backend/tests/")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "backend/app").mkdir(parents=True)
    (tmp_path / "backend/app/svc.py").write_text("def f():\n    return 1\n")
    (tmp_path / "Dockerfile").write_text("FROM x\n")
    return tmp_path


@pytest.mark.parametrize(
    "path",
    ["Dockerfile", ".github/workflows/ci.yml", "/etc/passwd", "backend/app/../../Dockerfile",
     "../backend/app/x.py", "dispatcher/app/main.py", "", "backend\\app\\x.py"],
)
def test_check_path_rejects(path):
    with pytest.raises(EditError):
        check_path(path, ALLOWED)


def test_check_path_normalises():
    assert check_path("backend/app/./svc.py", ALLOWED) == "backend/app/svc.py"


def test_apply_edits(repo):
    changed = apply_edits(repo, [Edit(path="backend/app/svc.py", old="return 1", new="return 2")], ALLOWED, 5)
    assert changed == ["backend/app/svc.py"]
    assert "return 2" in (repo / "backend/app/svc.py").read_text()


def test_apply_edits_all_or_nothing(repo):
    edits = [
        Edit(path="backend/app/svc.py", old="return 1", new="return 2"),
        Edit(path="backend/app/svc.py", old="not there", new="x"),
    ]
    with pytest.raises(EditError, match="0 times"):
        apply_edits(repo, edits, ALLOWED, 5)
    assert "return 1" in (repo / "backend/app/svc.py").read_text()


def test_apply_edits_ambiguous(repo):
    (repo / "backend/app/svc.py").write_text("x = 1\nx = 1\n")
    with pytest.raises(EditError, match="2 times"):
        apply_edits(repo, [Edit(path="backend/app/svc.py", old="x = 1", new="x = 2")], ALLOWED, 5)


def test_apply_edits_refuses_symlink_out(repo):
    (repo / "backend/app/link.py").symlink_to(repo / "Dockerfile")
    with pytest.raises(EditError, match="not a regular file"):
        apply_edits(repo, [Edit(path="backend/app/link.py", old="FROM", new="X")], ALLOWED, 5)


def test_apply_edits_limits(repo):
    with pytest.raises(EditError):
        apply_edits(repo, [], ALLOWED, 5)
    many = [Edit(path="backend/app/svc.py", old="a", new="b")] * 3
    with pytest.raises(EditError, match="max"):
        apply_edits(repo, many, ALLOWED, 2)


JUNIT = """<testsuites><testsuite>
<testcase classname="tests.test_a" name="test_ok"/>
<testcase classname="tests.test_a" name="test_bad"><failure message="x"/></testcase>
<testcase classname="tests.test_b" name="test_err"><error message="x"/></testcase>
<testcase classname="tests.test_b" name="test_skip"><skipped/></testcase>
</testsuite></testsuites>"""


def test_parse_junit():
    ran, failed = parse_junit(JUNIT)
    assert ran == 3
    assert failed == {"tests.test_a::test_bad", "tests.test_b::test_err"}


def test_new_failures_ignores_preexisting():
    before = TestResult(3, {"a::x"})
    assert new_failures(before, TestResult(3, {"a::x"})) == set()
    assert new_failures(before, TestResult(3, {"a::x", "b::y"})) == {"b::y"}


def test_slugify_matches_dispatcher():
    assert main.slugify("GenerationFailuresSpike") == "generationfailuresspike"
    assert main.slugify("Api 5xx/Rate") == "api-5xx-rate"
    assert main.slugify("!!!") == "alert"


def test_pr_body_has_no_raw_evidence():
    incident = {
        "alertname": "Api5xxRate",
        "alerts": [{"startsAt": "2026-11-08T10:00:00+00:00"}],
        "failed_generations": [{"error_message": "SECRET USER PROMPT"}],
        "api_logs": "line1\nTraceback SECRET\n",
        "evidence_errors": {},
        "truncated": False,
    }

    class Fix:
        root_cause = "rc"
        summary = "sum"

    body = main.pr_body(incident, Fix(), ["backend/app/svc.py"], TestResult(5, set()), TestResult(6, set()))
    assert "SECRET" not in body
    assert "1 failed generation rows, 2 api log lines" in body
    assert "6/6 passed" in body


def test_clean_env_drops_secrets(monkeypatch):
    from app.testrun import clean_env

    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "y")
    monkeypatch.setenv("HOME", "/work")
    env = clean_env()
    assert "GITHUB_TOKEN" not in env and "GEMINI_API_KEY" not in env
    assert env["HOME"] == "/work"


def test_gemini_retries_transport_errors(monkeypatch):
    import httpx

    from app import llm

    monkeypatch.setattr(llm, "RETRY_DELAYS", (0, 0))
    g = llm.Gemini.__new__(llm.Gemini)
    calls = []

    def flaky(prompt, schema):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("[Errno 101] Network is unreachable")
        return "ok"

    g._ask_once = flaky
    assert g._ask("p", llm.FilePick) == "ok"
    assert len(calls) == 3


def test_gemini_gives_up_after_retries(monkeypatch):
    import httpx

    from app import llm

    monkeypatch.setattr(llm, "RETRY_DELAYS", (0,))
    g = llm.Gemini.__new__(llm.Gemini)

    def down(prompt, schema):
        raise httpx.ConnectError("down")

    g._ask_once = down
    with pytest.raises(httpx.ConnectError):
        g._ask("p", llm.FilePick)
