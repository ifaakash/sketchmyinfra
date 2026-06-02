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
    """Keyword-based fallback classifier. PlantUML is the default."""

    # --- PlantUML (default for most things) ---

    def test_aws_keywords(self):
        assert classify_prompt("Deploy a Lambda function with S3 trigger") == "plantuml"

    def test_gcp_keywords(self):
        assert classify_prompt("Cloud Run service with Cloud SQL") == "plantuml"

    def test_azure_keywords(self):
        assert classify_prompt("Azure Functions with Cosmos DB") == "plantuml"

    def test_generic_flowchart_defaults_plantuml(self):
        assert classify_prompt("User authentication flowchart") == "plantuml"

    def test_generic_system_design_defaults_plantuml(self):
        assert classify_prompt("Design a microservices architecture for an e-commerce platform") == "plantuml"

    def test_physical_layout_defaults_plantuml(self):
        assert classify_prompt("PVC air cannon with trigger mechanism") == "plantuml"

    def test_empty_prompt_defaults_plantuml(self):
        assert classify_prompt("") == "plantuml"

    def test_chinese_prompt_defaults_plantuml(self):
        assert classify_prompt("数据采集层架构图") == "plantuml"

    def test_vpc_keyword(self):
        assert classify_prompt("Show me a VPC with subnets") == "plantuml"

    # --- Mermaid (only 4 specific diagram types) ---

    def test_sequence_diagram(self):
        assert classify_prompt("Show the sequence diagram for login API flow") == "mermaid"

    def test_auth_flow(self):
        assert classify_prompt("Show the auth flow between client and server") == "mermaid"

    def test_er_diagram(self):
        assert classify_prompt("Database schema for a blog with users and posts") == "mermaid"

    def test_entity_relationship(self):
        assert classify_prompt("Entity relationship diagram for e-commerce") == "mermaid"

    def test_class_diagram(self):
        assert classify_prompt("Class diagram for the payment module") == "mermaid"

    def test_class_hierarchy(self):
        assert classify_prompt("Show the class hierarchy of the animal kingdom") == "mermaid"

    def test_state_machine(self):
        assert classify_prompt("State machine for order processing") == "mermaid"

    def test_state_diagram(self):
        assert classify_prompt("State diagram for a traffic light") == "mermaid"

    def test_lifecycle(self):
        assert classify_prompt("Pod lifecycle in Kubernetes") == "mermaid"


class TestParseRendererTag:
    """Parse :::renderer=X::: tag from Gemini output."""

    def test_plantuml_tag(self):
        text = ":::renderer=plantuml:::\n@startuml\nrectangle \"Foo\"\n@enduml"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"
        assert "@startuml" in code
        assert ":::renderer" not in code

    def test_mermaid_tag(self):
        text = ":::renderer=mermaid:::\nsequenceDiagram\n  Alice->>Bob: Hello"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"
        assert "sequenceDiagram" in code
        assert ":::renderer" not in code

    def test_no_tag_with_startuml(self):
        text = "@startuml\nrectangle \"Foo\"\n@enduml"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"
        assert code == text

    def test_no_tag_with_sequence_diagram(self):
        text = "sequenceDiagram\n  Alice->>Bob: Hello"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_no_tag_with_class_diagram(self):
        text = "classDiagram\n  Animal <|-- Dog"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_no_tag_with_er_diagram(self):
        text = "erDiagram\n  USER ||--o{ ORDER : places"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_no_tag_with_state_diagram(self):
        text = "stateDiagram\n  [*] --> Active"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_no_tag_with_flowchart_defaults_plantuml(self):
        """Flowcharts go to PlantUML now — Mermaid only for 4 types."""
        text = "flowchart LR\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"

    def test_no_tag_with_graph_defaults_plantuml(self):
        text = "graph TD\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"

    def test_no_tag_with_init_directive_defaults_plantuml(self):
        text = "%%{init: {'theme': 'base'}}%%\ngraph TD\n  A-->B"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"

    def test_tag_with_leading_whitespace(self):
        text = "  :::renderer=mermaid:::  \nsequenceDiagram\n  A->>B: Hello"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "mermaid"

    def test_unknown_content_defaults_plantuml(self):
        text = "some random text"
        renderer, code = _parse_renderer_tag(text)
        assert renderer == "plantuml"


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

    def test_trailing_semicolons_stripped(self):
        code = 'classDef blue fill:#dbeafe,stroke:#3b82f6;'
        result = _sanitize_mermaid(code)
        assert not result.rstrip().endswith(';')

    def test_trailing_comma_in_style(self):
        code = 'style mynode fill:#eee,stroke:#333,'
        result = _sanitize_mermaid(code)
        assert not result.rstrip().endswith(',')

    def test_node_id_starting_with_digit(self):
        code = '1_node["First Node"]'
        result = _sanitize_mermaid(code)
        assert result.strip().startswith('n_1_node')

    def test_digit_node_in_arrow_source(self):
        code = "123 --> 456"
        result = _sanitize_mermaid(code)
        assert "n_123" in result
        assert "n_456" in result
        assert result.strip().startswith("n_")

    def test_digit_node_in_dotted_arrow(self):
        code = "1a -.-> 2b"
        result = _sanitize_mermaid(code)
        assert "n_1a" in result
        assert "n_2b" in result

    def test_non_digit_node_unchanged(self):
        code = "nodeA --> nodeB"
        result = _sanitize_mermaid(code)
        assert result == code

    def test_subgraph_name_starting_with_digit(self):
        code = 'subgraph "1st Floor"\n  A-->B\nend'
        result = _sanitize_mermaid(code)
        assert 'subgraph s_1st_floor["1st Floor"]' in result

    def test_classdef_space_after_colon(self):
        code = "classDef myclass fill: #dbeafe,stroke: #3b82f6,stroke-width: 2px"
        result = _sanitize_mermaid(code)
        assert "fill:#dbeafe" in result
        assert "stroke:#3b82f6" in result
        assert "stroke-width:2px" in result

    def test_full_production_regression(self):
        """Jun 2 2026: stroke-width:2px followed by classDef caused parse error."""
        code = (
            "graph TD\n"
            "    classDef pvc fill:#bfdffb,stroke:#000,stroke-width:2px;\n"
            "    classDef valve fill:#a0a0a0,stroke:#000,stroke-width:2px;\n"
            "    1_air[\"Air Chamber\"]:::pvc\n"
            "    1_air --> 2_barrel\n"
            "    2_barrel[\"Barrel\"]:::pvc\n"
        )
        result = _sanitize_mermaid(code)
        # Semicolons stripped
        assert "2px;" not in result
        # Digit node IDs prefixed
        assert "n_1_air" in result
        assert "n_2_barrel" in result

    def test_unquoted_parens_in_square_label(self):
        """Jun 2 2026: [Air Chamber<br/>(2in PVC)] parsed ( as shape start."""
        code = 'air_chamber[Air Chamber<br/>(2in PVC, 12in)]:::pvc_pipe'
        result = _sanitize_mermaid(code)
        # Should be quoted now
        assert '["Air Chamber<br/>(2in PVC, 12in)"]' in result

    def test_unquoted_parens_multiple_nodes(self):
        code = (
            'barrel[Barrel<br/>(1.25in PVC, 24in)]:::pvc\n'
            'trigger[Trigger Lever<br/>(Wood)]:::mech'
        )
        result = _sanitize_mermaid(code)
        assert '["Barrel<br/>(1.25in PVC, 24in)"]' in result
        assert '["Trigger Lever<br/>(Wood)"]' in result

    def test_already_quoted_label_unchanged(self):
        code = 'node["Already Quoted (with parens)"]'
        result = _sanitize_mermaid(code)
        assert '["Already Quoted (with parens)"]' in result

    def test_simple_label_no_parens_unchanged(self):
        code = 'node[Simple Label]'
        result = _sanitize_mermaid(code)
        assert '[Simple Label]' in result

    def test_curly_brace_in_label_quoted(self):
        code = 'node[Config {key: val}]'
        result = _sanitize_mermaid(code)
        assert '["Config {key: val}"]' in result

    def test_linkstyle_dasharray_space(self):
        """linkStyle with stroke-dasharray should not break."""
        code = "linkStyle 6 stroke-dasharray: 5 5"
        result = _sanitize_mermaid(code)
        assert "linkStyle" in result

    def test_parens_in_pipe_arrow_label(self):
        """Jun 2 2026: (Zip tie & rubber band) in |...| broke parser."""
        code = 'trigger -.->|Pull to rotate<br/>(Zip tie & rubber band)| ball_valve'
        result = _sanitize_mermaid(code)
        assert "(" not in result.split("|")[1]
        assert ")" not in result.split("|")[1]
        assert "&" not in result.split("|")[1]
        assert "and" in result

    def test_ampersand_in_pipe_label(self):
        code = "A -->|save & load| B"
        result = _sanitize_mermaid(code)
        assert "-->|save and load|" in result

    def test_clean_pipe_label_unchanged(self):
        code = "A -->|sends data| B"
        result = _sanitize_mermaid(code)
        assert "-->|sends data|" in result

    def test_pipe_in_pipe_label(self):
        code = "A -->|input | output| B"
        result = _sanitize_mermaid(code)
        assert "|" not in result.split("-->")[1].split("|")[1] or "/" in result

    # --- Round label (stadium) with nested parens ---

    def test_round_label_with_nested_parens(self):
        """(Server (main)) → ["Server (main)"] to avoid shape conflict."""
        code = 'my_node(Server (main))'
        result = _sanitize_mermaid(code)
        assert '["Server (main)"]' in result
        assert "my_node" in result

    def test_round_label_no_parens_unchanged(self):
        code = 'my_node(Simple Text)'
        result = _sanitize_mermaid(code)
        assert 'my_node(Simple Text)' in result

    def test_round_quoted_label_unchanged(self):
        code = 'my_node("Already Quoted (parens)")'
        result = _sanitize_mermaid(code)
        assert '("Already Quoted (parens)")' in result

    # --- Double-circle labels ((...)) ---

    def test_double_circle_with_nested_parens(self):
        code = 'hub((Hub (v2)))'
        result = _sanitize_mermaid(code)
        assert "((" in result
        assert "))" in result
        # Inner parens stripped
        assert "Hub v2" in result

    def test_double_circle_clean_unchanged(self):
        code = 'hub((Simple Hub))'
        result = _sanitize_mermaid(code)
        assert 'hub((Simple Hub))' in result

    # --- Diamond labels {...} ---

    def test_diamond_with_nested_parens(self):
        code = 'decision{Decision (yes/no)}'
        result = _sanitize_mermaid(code)
        assert "(" not in result.split("{")[1]

    def test_diamond_with_pipe(self):
        code = 'decision{A | B}'
        result = _sanitize_mermaid(code)
        assert "|" not in result.split("{")[1].split("}")[0] or "/" in result

    def test_diamond_clean_unchanged(self):
        code = 'decision{Is Valid}'
        result = _sanitize_mermaid(code)
        assert 'decision{Is Valid}' in result

    # --- Square labels with -- (arrow-like) ---

    def test_square_label_with_dashes(self):
        """[CI--CD] looks like an arrow to Mermaid."""
        code = 'pipeline[CI--CD Pipeline]'
        result = _sanitize_mermaid(code)
        assert '["CI--CD Pipeline"]' in result

    # --- direction outside subgraph ---

    def test_direction_outside_subgraph_stripped(self):
        code = 'graph TD\n  direction LR\n  A-->B'
        result = _sanitize_mermaid(code)
        assert 'direction LR' not in result
        assert 'A-->B' in result

    def test_direction_inside_subgraph_kept(self):
        code = 'graph TD\n  subgraph sg["Group"]\n    direction LR\n    A-->B\n  end'
        result = _sanitize_mermaid(code)
        assert 'direction LR' in result

    # --- Hash in pipe label ---

    def test_hash_in_pipe_label_stripped(self):
        code = 'A -->|Step #1| B'
        result = _sanitize_mermaid(code)
        assert "#" not in result.split("|")[1]

    # --- Inline label arrow syntax: -- text --> ---

    def test_double_dash_text_arrow(self):
        """A -- Connects --> B should become A -->|Connects| B."""
        code = "air_chamber -- Connects --> reducer"
        result = _sanitize_mermaid(code)
        assert "-->|Connects|" in result
        assert "-- Connects -->" not in result

    def test_double_dash_text_line(self):
        """A -- Label --- B should become A ---|Label| B."""
        code = "A -- My Label --- B"
        result = _sanitize_mermaid(code)
        assert "---|My Label|" in result

    def test_double_dash_text_with_parens(self):
        """Parens in inline label get stripped by pipe sanitizer."""
        code = "ball_valve -- Rubber Band (return) --> trigger"
        result = _sanitize_mermaid(code)
        assert "-->|" in result
        # Parens stripped by pipe label sanitizer
        assert "(" not in result.split("|")[1] if "|" in result else True

    def test_double_dash_text_multiple_words(self):
        code = "barrel -- Taped to muzzle --> lighter"
        result = _sanitize_mermaid(code)
        assert "-->|Taped to muzzle|" in result

    def test_normal_arrow_unchanged(self):
        code = "A --> B"
        result = _sanitize_mermaid(code)
        assert result.strip() == "A --> B"

    def test_pipe_label_arrow_unchanged(self):
        code = "A -->|correct| B"
        result = _sanitize_mermaid(code)
        assert "-->|correct|" in result


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
