"""Integration tests: send tricky PUML to the PlantUML server.

These tests require a running PlantUML server. Skip gracefully if unavailable.
Run: cd backend && pytest tests/test_plantuml_render.py -v

Configure PLANTUML_SERVER_URL env var or defaults to http://localhost:8080.
"""

import os

import httpx
import pytest

PLANTUML_URL = os.getenv("PLANTUML_SERVER_URL", "http://localhost:8080")


def _render(puml: str) -> httpx.Response:
    """POST raw PUML to the PlantUML server."""
    return httpx.post(
        f"{PLANTUML_URL}/svg/",
        content=puml.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        timeout=30.0,
    )


def _is_error_svg(response: httpx.Response) -> bool:
    """Check if the SVG response contains a PlantUML error."""
    import re

    text = response.text
    # Red error text
    if re.search(r'fill="#CC0000"', text):
        return True
    # Error marker
    if "[From string (line" in text:
        return True
    return False


@pytest.fixture(autouse=True)
def _check_server():
    """Skip all tests if PlantUML server is unreachable."""
    try:
        httpx.get(PLANTUML_URL, timeout=5.0)
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip(f"PlantUML server not reachable at {PLANTUML_URL}")


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------


class TestBasicRendering:
    def test_simple_rectangle_diagram(self):
        puml = '@startuml\nrectangle "Hello" as h\n@enduml'
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_component_diagram(self):
        puml = (
            "@startuml\n"
            'component "API" as api\n'
            'component "DB" as db\n'
            "api --> db\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)


# ---------------------------------------------------------------------------
# CJK / International characters
# ---------------------------------------------------------------------------


class TestInternationalCharacters:
    """Non-Latin scripts that broke before charset=utf-8 fix."""

    def test_chinese_labels(self):
        puml = (
            "@startuml\n"
            'rectangle "数据采集层" as dc\n'
            'rectangle "数据处理层" as dp\n'
            "dc --> dp\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_japanese_labels(self):
        puml = (
            "@startuml\n"
            'rectangle "データベース" as db\n'
            'rectangle "アプリケーション" as app\n'
            "app --> db\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_korean_labels(self):
        puml = (
            "@startuml\n"
            'rectangle "데이터베이스" as db\n'
            'rectangle "애플리케이션" as app\n'
            "app --> db\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_hindi_labels(self):
        puml = (
            "@startuml\n"
            'rectangle "डेटाबेस" as db\n'
            'rectangle "एप्लिकेशन" as app\n'
            "app --> db\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_arabic_labels(self):
        puml = (
            "@startuml\n"
            'rectangle "قاعدة البيانات" as db\n'
            'rectangle "التطبيق" as app\n'
            "app --> db\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_mixed_cjk_and_english(self):
        puml = (
            "@startuml\n"
            'rectangle "ERP 系统" as erp\n'
            'rectangle "Data Layer" as dl\n'
            "erp --> dl\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_chinese_arrow_labels(self):
        puml = (
            "@startuml\n"
            'rectangle "A" as a\n'
            'rectangle "B" as b\n'
            'a --> b : 原始数据输入\n'
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)


# ---------------------------------------------------------------------------
# Characters that needed sanitization
# ---------------------------------------------------------------------------


class TestSanitizedCharacters:
    """These should FAIL without sanitization. Test the raw chars
    to confirm PlantUML actually rejects them — validates our sanitizer
    is protecting against real issues, not phantom ones."""

    def test_ampersand_in_label_fails_raw(self):
        """Confirm & actually breaks PlantUML (justifies our sanitizer)."""
        puml = '@startuml\nrectangle "A & B" as ab\n@enduml'
        resp = _render(puml)
        # This SHOULD fail — if it passes, PlantUML fixed it upstream
        # and we can simplify our sanitizer
        is_error = _is_error_svg(resp) or resp.status_code != 200
        if not is_error:
            pytest.skip("PlantUML now accepts & in labels — sanitizer rule may be removable")

    def test_sanitized_ampersand_renders(self):
        """After sanitization, 'and' should render fine."""
        puml = '@startuml\nrectangle "A and B" as ab\n@enduml'
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)


# ---------------------------------------------------------------------------
# Skinparam patterns
# ---------------------------------------------------------------------------


class TestSkinparamRendering:
    """Verify that flattened skinparam blocks render correctly."""

    def test_flat_skinparam_renders(self):
        puml = (
            "@startuml\n"
            "skinparam shadowing false\n"
            "skinparam rectangle {\n"
            "  BackgroundColor #dbeafe\n"
            "  BorderColor #3b82f6\n"
            "  FontColor #1e40af\n"
            "}\n"
            'rectangle "Foo" as foo\n'
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_global_arrow_color_renders(self):
        puml = (
            "@startuml\n"
            "skinparam ArrowColor #333333\n"
            'rectangle "A" as a\n'
            'rectangle "B" as b\n'
            "a --> b\n"
            "@enduml"
        )
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)


# ---------------------------------------------------------------------------
# Labels containing "error", "syntax", "not found" — false positive traps
# ---------------------------------------------------------------------------


class TestFalsePositiveLabels:
    """Labels with words our error detector used to match on."""

    def test_label_with_error_word(self):
        puml = '@startuml\nrectangle "Error Handler" as eh\n@enduml'
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_label_with_syntax_word(self):
        puml = '@startuml\nrectangle "Syntax Parser" as sp\n@enduml'
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_label_with_not_found_phrase(self):
        puml = '@startuml\nrectangle "404 Not Found Handler" as nf\n@enduml'
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)

    def test_label_output_and_error_reporting(self):
        """The exact label that started it all."""
        puml = '@startuml\nrectangle "Output and Error Reporting" as oer\n@enduml'
        resp = _render(puml)
        assert resp.status_code == 200
        assert not _is_error_svg(resp)
