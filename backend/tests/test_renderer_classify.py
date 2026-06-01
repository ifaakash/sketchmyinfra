"""Tests for the dual-renderer classification, routing, and Mermaid sanitization."""

import pytest

from app.services.gemini import (
    classify_prompt,
    _parse_renderer_tag,
    _post_process_mermaid,
    _post_process_puml,
    _sanitize_mermaid,
)


class TestClassifyPrompt:
    """Keyword-based fallback classifier."""

    def test_aws_keywords(self):
        assert classify_prompt("Deploy a Lambda function with S3 trigger") == "plantuml"

    def test_gcp_keywords(self):
        assert classify_prompt("Cloud Run service with Cloud SQL") == "plantuml"

    def test_azure_keywords(self):
        assert classify_prompt("Azure Functions with Cosmos DB") == "plantuml"

    def test_generic_flowchart(self):
        assert classify_prompt("User authentication flowchart") == "mermaid"

    def test_generic_system_design(self):
        assert classify_prompt("Design a microservices architecture for an e-commerce platform") == "mermaid"

    def test_sequence_diagram(self):
        assert classify_prompt("Show the login flow between client and server") == "mermaid"

    def test_er_diagram(self):
        assert classify_prompt("Database schema for a blog with users and posts") == "mermaid"

    def test_mixed_cloud_and_generic(self):
        assert classify_prompt("Flowchart showing EC2 instance lifecycle") == "plantuml"

    def test_case_insensitive(self):
        assert classify_prompt("AWS LAMBDA with DynamoDB") == "plantuml"

    def test_empty_prompt(self):
        assert classify_prompt("") == "mermaid"

    def test_chinese_prompt_no_cloud(self):
        assert classify_prompt("数据采集层架构图") == "mermaid"

    def test_vpc_keyword(self):
        assert classify_prompt("Show me a VPC with subnets") == "plantuml"


class TestParseRendererTag:
    """Parse :::renderer=X::: tag from Gemini output."""

    def test_plantuml_tag(self):
        text = ":::renderer=plantuml:::\n@startuml\nrectangle \"Foo\"\n@enduml"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"
        assert "@startuml" in code
        assert ":::renderer" not in code

    def test_mermaid_tag(self):
        text = ":::renderer=mermaid:::\ngraph TD\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"
        assert "graph TD" in code
        assert ":::renderer" not in code

    def test_no_tag_with_startuml(self):
        text = "@startuml\nrectangle \"Foo\"\n@enduml"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"
        assert code == text

    def test_no_tag_with_mermaid_content(self):
        text = "graph TD\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"
        assert code == text

    def test_no_tag_with_flowchart(self):
        text = "flowchart LR\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_no_tag_with_sequence(self):
        text = "sequenceDiagram\n  Alice->>Bob: Hello"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_no_tag_with_init_directive(self):
        text = "%%{init: {'theme': 'base'}}%%\ngraph TD\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_tag_with_leading_whitespace(self):
        text = "  :::renderer=mermaid:::  \ngraph TD\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_unknown_content_defaults_mermaid(self):
        text = "some random text"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"


# ---------------------------------------------------------------------------
# _sanitize_mermaid: fix common Gemini Mermaid syntax issues
# ---------------------------------------------------------------------------


class TestSanitizeMermaid:
    """Mermaid sanitization for Gemini output issues."""

    def test_subgraph_without_id_gets_id(self):
        code = 'subgraph "School Grounds"\n  A-->B\nend'
        result = _sanitize_mermaid(code)
        assert 'subgraph school_grounds["School Grounds"]' in result
        assert 'subgraph "School Grounds"' not in result

    def test_style_quoted_name_replaced_with_id(self):
        code = (
            'subgraph "Main Building"\n'
            '  A-->B\n'
            'end\n'
            'style "Main Building" fill:#eee,stroke:#333'
        )
        result = _sanitize_mermaid(code)
        assert 'style main_building fill:#eee,stroke:#333' in result
        assert 'style "Main Building"' not in result

    def test_stray_br_removed(self):
        code = 'A["Note"]<br>\nB-->C'
        result = _sanitize_mermaid(code)
        assert "<br>" not in result
        assert "B-->C" in result

    def test_stray_br_self_closing_removed(self):
        code = 'A["Note"]<br/>\nB-->C'
        result = _sanitize_mermaid(code)
        assert "<br/>" not in result

    def test_standalone_br_line_removed(self):
        code = 'A-->B\n<br>\nC-->D'
        result = _sanitize_mermaid(code)
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        assert "<br>" not in lines

    def test_space_after_colon_in_style(self):
        code = 'style my_id fill: #eee,stroke: #333,stroke-dasharray: 5 5'
        result = _sanitize_mermaid(code)
        assert "fill:#eee" in result
        assert "stroke:#333" in result
        assert "stroke-dasharray:5 5" in result

    def test_clean_mermaid_unchanged(self):
        code = 'graph TD\n  A-->B\n  B-->C'
        assert _sanitize_mermaid(code) == code

    def test_multiple_subgraphs_tracked(self):
        code = (
            'subgraph "Group A"\n  A-->B\nend\n'
            'subgraph "Group B"\n  C-->D\nend\n'
            'style "Group A" fill:#aaa\n'
            'style "Group B" fill:#bbb'
        )
        result = _sanitize_mermaid(code)
        assert 'subgraph group_a["Group A"]' in result
        assert 'subgraph group_b["Group B"]' in result
        assert 'style group_a fill:#aaa' in result
        assert 'style group_b fill:#bbb' in result

    def test_nested_subgraph_ids(self):
        code = (
            'subgraph "Outer"\n'
            '  subgraph "Inner"\n'
            '    A-->B\n'
            '  end\n'
            'end\n'
            'style "Outer" fill:#eee\n'
            'style "Inner" fill:#ddd'
        )
        result = _sanitize_mermaid(code)
        assert 'subgraph outer["Outer"]' in result
        assert 'subgraph inner["Inner"]' in result
        assert 'style outer fill:#eee' in result
        assert 'style inner fill:#ddd' in result

    def test_escaped_quotes_in_square_labels(self):
        """Jun 2 2026: 2\" PVC broke Mermaid parser — \" not supported inside ["..."]."""
        code = r'A["Air Chamber<br/>(2\" PVC, 12\")"]:::pvc_style'
        result = _sanitize_mermaid(code)
        assert '\\"' not in result
        assert '&quot;' in result
        assert 'pvc_style' in result

    def test_raw_quotes_in_square_labels(self):
        code = 'A["2" PVC Pipe"]'
        result = _sanitize_mermaid(code)
        assert '&quot;' in result

    def test_quotes_in_round_labels(self):
        code = 'A("2\\" inch pipe")'
        result = _sanitize_mermaid(code)
        assert '\\"' not in result

    def test_no_quotes_label_unchanged(self):
        code = 'A["Normal Label"]'
        result = _sanitize_mermaid(code)
        assert result == code

    def test_colon_arrow_label_to_pipe_syntax(self):
        """Jun 2 2026: Gemini used PlantUML colon syntax for arrow labels."""
        code = "erp --> collect_layer : 采集数据"
        result = _sanitize_mermaid(code)
        assert ":" not in result or "&quot;" in result
        assert "-->|采集数据|" in result

    def test_colon_arrow_label_english(self):
        code = "A --> B : sends data"
        result = _sanitize_mermaid(code)
        assert "-->|sends data|" in result
        assert ": sends data" not in result

    def test_dotted_arrow_colon_label(self):
        code = "A -.-> B : async"
        result = _sanitize_mermaid(code)
        assert "-.->|async|" in result

    def test_pipe_label_unchanged(self):
        code = "A -->|already correct| B"
        result = _sanitize_mermaid(code)
        assert result == code


class TestPostProcessMermaid:
    """Mermaid post-processing."""

    def test_clean_mermaid_passes(self):
        code = "graph TD\n  A-->B"
        result = _post_process_mermaid(code)
        assert "graph TD" in result

    def test_strips_startuml(self):
        code = "@startuml\ngraph TD\n  A-->B\n@enduml"
        result = _post_process_mermaid(code)
        assert "@startuml" not in result
        assert "@enduml" not in result
        assert "graph TD" in result

    def test_empty_raises(self):
        with pytest.raises(Exception):
            _post_process_mermaid("")

    def test_normalizes_unicode(self):
        code = "graph TD\n  A[\u201cHello\u201d]-->B"
        result = _post_process_mermaid(code)
        assert "\u201c" not in result

    def test_sanitizes_subgraph_ids(self):
        """Full pipeline: post-process applies sanitization."""
        code = 'graph TD\n  subgraph "My Group"\n    A-->B\n  end'
        result = _post_process_mermaid(code)
        assert 'subgraph my_group["My Group"]' in result


class TestPostProcessPuml:
    """PlantUML post-processing (validates @startuml/@enduml)."""

    def test_valid_puml_passes(self):
        code = "@startuml\nrectangle \"Foo\"\n@enduml"
        result = _post_process_puml(code)
        assert "@startuml" in result

    def test_missing_startuml_raises(self):
        with pytest.raises(Exception):
            _post_process_puml("rectangle \"Foo\"\n@enduml")

    def test_missing_enduml_raises(self):
        with pytest.raises(Exception):
            _post_process_puml("@startuml\nrectangle \"Foo\"")
