"""Tests for PlantUML error detection — no false positives, no missed errors."""

import pytest

from app.services.plantuml import _extract_error


# Sample SVG fragments mimicking PlantUML output


def _make_error_svg(error_text: str) -> str:
    """Build a minimal SVG that looks like a PlantUML error response."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        f'<text fill="#CC0000" font-size="14">{error_text}</text>'
        '<text fill="#000000">[From string (line 5)]</text>'
        '</svg>'
    )


def _make_success_svg(*labels: str) -> str:
    """Build a minimal SVG that looks like a successful PlantUML render."""
    texts = "".join(f'<text fill="#1e293b">{l}</text>' for l in labels)
    return f'<svg xmlns="http://www.w3.org/2000/svg">{texts}</svg>'


# ---------------------------------------------------------------------------
# Should detect real errors
# ---------------------------------------------------------------------------


class TestRealErrors:
    def test_red_error_text(self):
        svg = _make_error_svg("Syntax Error?")
        assert _extract_error(svg) is not None
        assert "Syntax Error?" in _extract_error(svg)

    def test_not_found_with_line_marker(self):
        svg = (
            '<svg><text fill="#000000">some icon not found</text>'
            '<text fill="#000000">[From string (line 3)]</text></svg>'
        )
        assert _extract_error(svg) is not None

    def test_syntax_error_with_line_marker(self):
        svg = (
            '<svg><text fill="#000000">syntax error in line</text>'
            '<text fill="#000000">[From string (line 7)]</text></svg>'
        )
        # Our fallback checks for "syntax error" (two words), not just "syntax"
        assert _extract_error(svg) is not None

    def test_red_fill_case_insensitive(self):
        svg = '<svg><text fill="red" font-size="14">Some error</text></svg>'
        assert _extract_error(svg) is not None


# ---------------------------------------------------------------------------
# Should NOT detect these as errors (false positives)
# ---------------------------------------------------------------------------


class TestFalsePositives:
    """Labels that contain trigger words but are NOT errors."""

    def test_label_with_error_word(self):
        svg = _make_success_svg("Error Handler", "Input Module")
        assert _extract_error(svg) is None

    def test_label_with_syntax_word(self):
        svg = _make_success_svg("Syntax Parser", "Output Module")
        assert _extract_error(svg) is None

    def test_label_with_not_found_word(self):
        svg = _make_success_svg("Not Found Page", "404 Handler")
        assert _extract_error(svg) is None

    def test_output_and_error_reporting(self):
        """The exact label that caused the original false positive."""
        svg = _make_success_svg("Output and Error Reporting")
        assert _extract_error(svg) is None

    def test_label_with_error_and_syntax(self):
        svg = _make_success_svg("Syntax Error Logging Module")
        assert _extract_error(svg) is None

    def test_empty_svg(self):
        assert _extract_error("<svg></svg>") is None

    def test_normal_diagram_labels(self):
        svg = _make_success_svg(
            "Load Balancer", "API Gateway", "Database",
            "Cache Layer", "Message Queue"
        )
        assert _extract_error(svg) is None
