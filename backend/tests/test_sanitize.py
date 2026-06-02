"""Unit tests for PlantUML sanitization pipeline.

Every test case here represents a real production failure or a known
PlantUML parser quirk. If Gemini generates bad output, the sanitizer
should catch it BEFORE it hits the PlantUML server.

Run: cd backend && pip install pytest && pytest tests/ -v
"""

import pytest

from app.services.gemini import (
    _build_fix_prompt,
    _build_iteration_prompt,
    _fix_nested_skinparam,
    _normalize_gemini_text,
    _post_process_puml,
    _remove_invalid_skinparams,
    _resolve_variables,
    _sanitize_label,
    _sanitize_puml,
)


# ---------------------------------------------------------------------------
# _sanitize_label: special characters inside quoted labels
# ---------------------------------------------------------------------------


class TestSanitizeLabel:
    """Characters that PlantUML misinterprets inside quoted strings."""

    def test_ampersand_replaced(self):
        assert _sanitize_label("Output & Error") == "Output and Error"

    def test_multiple_ampersands(self):
        assert _sanitize_label("A & B & C") == "A and B and C"

    def test_html_amp_entity(self):
        assert _sanitize_label("Output &amp; Error") == "Output and Error"

    def test_html_lt_gt_entities(self):
        assert _sanitize_label("Size &lt; 10 &gt; 5") == "Size < 10 > 5"

    def test_html_quot_entity(self):
        assert _sanitize_label("Say &quot;hello&quot;") == "Say 'hello'"

    def test_html_numeric_entity(self):
        assert _sanitize_label("It&#39;s fine") == "It's fine"

    def test_tilde_replaced(self):
        assert _sanitize_label("~50% complete") == "-50% complete"

    def test_pipe_replaced(self):
        assert _sanitize_label("Input | Output") == "Input / Output"

    def test_en_dash_replaced(self):
        assert _sanitize_label("CI\u2013CD") == "CI-CD"

    def test_em_dash_replaced(self):
        assert _sanitize_label("CI\u2014CD") == "CI-CD"

    def test_clean_label_unchanged(self):
        assert _sanitize_label("Load Balancer") == "Load Balancer"

    def test_combined_special_chars(self):
        result = _sanitize_label("Input & Output | ~50% \u2014 done")
        assert "&" not in result
        assert "|" not in result
        assert "~" not in result
        assert "\u2014" not in result


# ---------------------------------------------------------------------------
# _normalize_gemini_text: global Unicode cleanup
# ---------------------------------------------------------------------------


class TestNormalizeGeminiText:
    """Unicode issues in raw Gemini output that affect parsing."""

    def test_nbsp_replaced(self):
        assert _normalize_gemini_text("hello\u00a0world") == "hello world"

    def test_smart_double_quotes(self):
        result = _normalize_gemini_text('\u201chello\u201d')
        assert result == '"hello"'

    def test_smart_single_quotes(self):
        result = _normalize_gemini_text("\u2018hello\u2019")
        assert result == "'hello'"

    def test_zero_width_space_removed(self):
        assert _normalize_gemini_text("hel\u200blo") == "hello"

    def test_zero_width_non_joiner_removed(self):
        assert _normalize_gemini_text("hel\u200clo") == "hello"

    def test_zero_width_joiner_removed(self):
        assert _normalize_gemini_text("hel\u200dlo") == "hello"

    def test_bom_removed(self):
        assert _normalize_gemini_text("\ufeffhello") == "hello"

    def test_crlf_normalized(self):
        assert _normalize_gemini_text("a\r\nb\rc") == "a\nb\nc"

    def test_clean_text_unchanged(self):
        text = '@startuml\nrectangle "Foo"\n@enduml'
        assert _normalize_gemini_text(text) == text


# ---------------------------------------------------------------------------
# _fix_nested_skinparam: structural fix for invalid nesting
# ---------------------------------------------------------------------------


class TestFixNestedSkinparam:
    """Gemini generates nested skinparam blocks — PlantUML rejects them."""

    def test_basic_nested_skinparam(self):
        bad = (
            "skinparam {\n"
            "  shadowing false\n"
            "  rectangle {\n"
            "    BackgroundColor #fff\n"
            "  }\n"
            "}"
        )
        result = _fix_nested_skinparam(bad)
        assert "skinparam shadowing false" in result
        assert "skinparam rectangle {" in result
        assert "BackgroundColor #fff" in result
        # Should NOT have bare "skinparam {"
        assert "skinparam {" not in result or "skinparam {\n" not in result

    def test_multiple_nested_blocks(self):
        bad = (
            "skinparam {\n"
            "  shadowing false\n"
            "  rectangle {\n"
            "    BackgroundColor #ddd\n"
            "  }\n"
            "  component {\n"
            "    BackgroundColor #eee\n"
            "  }\n"
            "}"
        )
        result = _fix_nested_skinparam(bad)
        assert "skinparam shadowing false" in result
        assert "skinparam rectangle {" in result
        assert "skinparam component {" in result

    def test_already_flat_skinparam_unchanged(self):
        good = (
            "skinparam shadowing false\n"
            "skinparam rectangle {\n"
            "  BackgroundColor #fff\n"
            "}"
        )
        assert _fix_nested_skinparam(good) == good

    def test_no_skinparam_unchanged(self):
        text = "rectangle \"Foo\" as foo\nfoo --> bar"
        assert _fix_nested_skinparam(text) == text


# ---------------------------------------------------------------------------
# _resolve_variables: inline !$var definitions
# ---------------------------------------------------------------------------


class TestResolveVariables:
    """Preprocessor variables that don't interpolate in #color positions."""

    def test_basic_variable_resolution(self):
        text = '!$color = "#D3D3D3"\nrectangle "Foo" as foo #$color'
        result = _resolve_variables(text)
        assert "#D3D3D3" in result
        assert "$color" not in result
        assert "!$color" not in result

    def test_multiple_variables(self):
        text = (
            '!$pvc = "#D3D3D3"\n'
            '!$wood = "#DEB887"\n'
            'rectangle "Pipe" as p #$pvc\n'
            'rectangle "Base" as b #$wood'
        )
        result = _resolve_variables(text)
        assert "#D3D3D3" in result
        assert "#DEB887" in result
        assert "$pvc" not in result
        assert "$wood" not in result

    def test_variable_with_trailing_comment(self):
        text = '!$fill = "#D3D3D3" \' Light Gray\nrectangle "X" as x #$fill'
        result = _resolve_variables(text)
        assert "#D3D3D3" in result

    def test_no_variables_unchanged(self):
        text = 'rectangle "Foo" as foo #D3D3D3'
        assert _resolve_variables(text) == text


# ---------------------------------------------------------------------------
# _remove_invalid_skinparams: strip unsupported skinparam targets
# ---------------------------------------------------------------------------


class TestRemoveInvalidSkinparams:
    """skinparam targets like 'line' that PlantUML doesn't recognize."""

    def test_skinparam_line_removed(self):
        text = (
            "skinparam line {\n"
            "  Thickness 2\n"
            "  Color black\n"
            "}\n"
            'rectangle "Foo" as foo'
        )
        result = _remove_invalid_skinparams(text)
        assert "skinparam line" not in result
        assert "Thickness" not in result
        assert "Foo" in result

    def test_valid_skinparam_preserved(self):
        text = (
            "skinparam rectangle {\n"
            "  BackgroundColor #fff\n"
            "}\n"
        )
        result = _remove_invalid_skinparams(text)
        assert "skinparam rectangle" in result
        assert "BackgroundColor" in result

    def test_no_skinparam_unchanged(self):
        text = 'rectangle "Foo" as foo'
        assert _remove_invalid_skinparams(text) == text


# ---------------------------------------------------------------------------
# _sanitize_puml: full pipeline (line-level fixes)
# ---------------------------------------------------------------------------


class TestSanitizePuml:
    """End-to-end sanitization covering all known failure patterns."""

    def test_trailing_inline_comment_slashes(self):
        puml = 'rectangle "Foo" as foo // this is a comment'
        result = _sanitize_puml(puml)
        assert "//" not in result
        assert '"Foo"' in result

    def test_trailing_inline_comment_apostrophe(self):
        puml = "rectangle \"Foo\" as foo { ' a comment"
        result = _sanitize_puml(puml)
        assert "a comment" not in result

    def test_full_line_comment_preserved(self):
        puml = "' This is a valid full-line comment"
        assert _sanitize_puml(puml) == puml

    def test_trailing_semicolons_stripped(self):
        puml = 'rectangle "DB" as db;'
        result = _sanitize_puml(puml)
        assert not result.rstrip().endswith(";")

    def test_ampersand_in_label_fixed(self):
        puml = 'rectangle "Input & Output" as io'
        result = _sanitize_puml(puml)
        assert "&" not in result
        assert "Input and Output" in result

    def test_arrow_color_inside_skinparam_stripped(self):
        puml = (
            "skinparam rectangle {\n"
            "  BackgroundColor #fff\n"
            "  ArrowColor #333\n"
            "  FontColor #000\n"
            "}"
        )
        result = _sanitize_puml(puml)
        assert "ArrowColor" not in result
        assert "BackgroundColor" in result
        assert "FontColor" in result

    def test_nested_skinparam_flattened(self):
        puml = (
            "skinparam {\n"
            "  shadowing false\n"
            "  rectangle {\n"
            "    BackgroundColor #dbeafe\n"
            "    ArrowColor #333\n"
            "  }\n"
            "}"
        )
        result = _sanitize_puml(puml)
        assert "skinparam shadowing false" in result
        assert "skinparam rectangle {" in result
        assert "ArrowColor" not in result

    def test_cjk_labels_pass_through(self):
        puml = 'rectangle "数据采集层" as data_layer'
        result = _sanitize_puml(puml)
        assert "数据采集层" in result

    def test_pipe_in_label_fixed(self):
        puml = 'rectangle "A | B" as ab'
        result = _sanitize_puml(puml)
        assert "|" not in result.split('"')[1]

    def test_html_entities_in_label_decoded(self):
        puml = 'rectangle "Output &amp; Error" as oe'
        result = _sanitize_puml(puml)
        assert "&amp;" not in result
        assert "Output and Error" in result


# ---------------------------------------------------------------------------
# Regression tests: exact PUML snippets that caused production 502s
# ---------------------------------------------------------------------------


class TestProductionRegressions:
    """Each test is a real failure that hit production. Never regress."""

    def test_ampersand_in_output_module(self):
        """May 31 2026: '&' in label caused PlantUML parallel operator error."""
        puml = (
            '@startuml\n'
            'rectangle "Output & Error Reporting" as output_module #D3D3D3\n'
            '@enduml'
        )
        result = _sanitize_puml(puml)
        assert "&" not in result
        assert "Output and Error Reporting" in result

    def test_error_word_in_label_no_false_positive(self):
        """May 31 2026: label containing 'error' triggered false positive
        in _extract_error(). Sanitizer shouldn't mangle the word 'error'."""
        puml = 'rectangle "Error Handler" as eh'
        result = _sanitize_puml(puml)
        assert "Error Handler" in result

    def test_nested_skinparam_component_diagram(self):
        """Jun 1 2026: Gemini wrapped skinparams in invalid global block."""
        puml = (
            "@startuml\n"
            "skinparam {\n"
            "  shadowing false\n"
            "  rectangle {\n"
            "    BackgroundColor #f8fafc\n"
            "    BorderColor #334155\n"
            "    ArrowColor #334155\n"
            "    FontColor #1e293b\n"
            "  }\n"
            "  component {\n"
            "    BackgroundColor #dbeafe\n"
            "    BorderColor #2563eb\n"
            "    ArrowColor #2563eb\n"
            "    FontColor #1e293b\n"
            "  }\n"
            "}\n"
            "top to bottom direction\n"
            'component "Bike Valve" as bv\n'
            "@enduml"
        )
        result = _sanitize_puml(puml)
        # Nested skinparam should be flattened
        lines = result.split("\n")
        skinparam_lines = [l.strip() for l in lines if l.strip().startswith("skinparam")]
        assert any("skinparam shadowing false" in l for l in skinparam_lines)
        assert any("skinparam rectangle" in l for l in skinparam_lines)
        assert any("skinparam component" in l for l in skinparam_lines)
        # ArrowColor should be stripped
        assert "ArrowColor" not in result

    def test_cjk_truncation_has_enduml(self):
        """Jun 1 2026: CJK diagrams exceeded token limit, output truncated.
        This tests sanitizer doesn't break valid CJK — truncation detection
        is in generate_puml() not the sanitizer."""
        puml = (
            "@startuml\n"
            'rectangle "数据处理层\\n(ETL/数据仓库)" as dp\n'
            'rectangle "智能计算层\\n(自研调度算法)" as ic\n'
            "dp --> ic\n"
            "@enduml"
        )
        result = _sanitize_puml(puml)
        assert "数据处理层" in result
        assert "智能计算层" in result
        assert "@enduml" in result

    def test_fix_prompt_with_braces_no_crash(self):
        """Jun 1 2026: str.format() crashed on PUML containing { } characters.
        ValueError: unexpected '{' in field name."""
        puml = (
            "@startuml\n"
            "frame \"Board\" as board {\n"
            "  component \"Valve\" as v\n"
            "}\n"
            "rectangle \"Lever\" as lv <<wood>>\n"
            "@enduml"
        )
        # Should not raise ValueError
        result = _build_fix_prompt(puml, "Syntax Error?")
        assert "Syntax Error?" in result
        assert "frame" in result
        assert "<<wood>>" in result

    def test_iteration_prompt_with_braces_no_crash(self):
        """Same crash for iteration prompts with PUML containing braces."""
        context = (
            "@startuml\n"
            "rectangle \"Group\" as g {\n"
            "  component \"A\" as a\n"
            "}\n"
            "@enduml"
        )
        result = _build_iteration_prompt(context)
        assert "rectangle" in result
        assert "{" in result

    def test_variable_colors_and_skinparam_line(self):
        """Jun 1 2026: !$variable colors + skinparam line caused 400."""
        puml = (
            "@startuml\n"
            "skinparam shadowing false\n"
            "skinparam line {\n"
            "  Thickness 2\n"
            "  Color black\n"
            "}\n"
            "!$pvc_fill = \"#D3D3D3\" ' Light Gray\n"
            "!$wood_fill = \"#DEB887\"\n"
            "rectangle \"Wood Base\" as wb #$wood_fill {\n"
            "  rectangle \"Air Chamber\" as ac #$pvc_fill\n"
            "}\n"
            "@enduml"
        )
        result = _sanitize_puml(puml)
        # Variables should be inlined
        assert "#D3D3D3" in result
        assert "#DEB887" in result
        assert "$pvc_fill" not in result
        assert "$wood_fill" not in result
        # Invalid skinparam line should be removed
        assert "skinparam line" not in result
        # Valid content preserved
        assert "Wood Base" in result
        assert "Air Chamber" in result

    def test_css_color_syntax_line_fill(self):
        """Jun 2 2026: #line:green;fill:#aaffaa is invalid PlantUML."""
        puml = '@startuml\nframe "School" as sg #line:green;fill:#aaffaa {\n}\n@enduml'
        result = _post_process_puml(puml)
        assert "#line:" not in result
        assert "fill:" not in result
        assert "#aaffaa" in result

    def test_css_color_syntax_fill_only(self):
        puml = '@startuml\nrectangle "Box" as b #fill:#e0c0e0\n@enduml'
        result = _post_process_puml(puml)
        assert "#fill:" not in result
        assert "#e0c0e0" in result

    def test_css_color_syntax_line_only(self):
        puml = '@startuml\nrectangle "Box" as b #line:purple\n@enduml'
        result = _post_process_puml(puml)
        assert "#line:" not in result
        assert "purple" in result

    def test_double_hash_color(self):
        puml = '@startuml\nrectangle "Box" as b ##deb887\n@enduml'
        result = _post_process_puml(puml)
        assert "##" not in result
        assert "#deb887" in result

    def test_renderer_tag_stripped(self):
        puml = ':::renderer=plantuml:::\n@startuml\nrectangle "Foo"\n@enduml'
        result = _post_process_puml(puml)
        assert ":::renderer" not in result
        assert "@startuml" in result
