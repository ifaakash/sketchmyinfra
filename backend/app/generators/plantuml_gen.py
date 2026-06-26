"""Deterministic PlantUML code generator from GraphIR.

Converts structured IR into valid PlantUML syntax. No AI involved —
every character is controlled by this code, eliminating the need for
sanitisation.
"""

from __future__ import annotations

from app.ir.schema import DiagramIR, GraphIR, IREdge, IRGroup, IRNode

from .icons import (
    AWS_PLANTUML_BASE,
    AWS_PLANTUML_GROUPS,
    AWS_PLANTUML_ICONS,
    AZURE_PLANTUML_BASE,
    AZURE_PLANTUML_ICONS,
    GCP_PLANTUML_BASE,
    GCP_PLANTUML_ICONS,
    get_plantuml_icon,
)

# Shape mapping: IR node type → PlantUML element keyword
_SHAPE_MAP: dict[str, str] = {
    "rectangle": "rectangle",
    "database": "database",
    "queue": "queue",
    "cloud": "cloud",
    "actor": "actor",
    "component": "component",
    "node": "node",
    "frame": "frame",
    "storage": "storage",
    "package": "package",
    "folder": "folder",
    "collections": "collections",
}

# Arrow syntax for edge styles
_ARROW_STYLE: dict[str, str] = {
    "solid": "-->",
    "dotted": "..>",
    "dashed": "..>",
}

_ARROW_BACK: dict[str, str] = {
    "solid": "<--",
    "dotted": "<..",
    "dashed": "<..",
}

_ARROW_BOTH: dict[str, str] = {
    "solid": "<-->",
    "dotted": "<..>",
    "dashed": "<..>",
}

_ARROW_NONE: dict[str, str] = {
    "solid": "--",
    "dotted": "..",
    "dashed": "..",
}


def _safe_label(text: str) -> str:
    """Escape characters that break PlantUML labels."""
    text = text.replace("&", "and")
    text = text.replace("~", "-")
    text = text.replace("|", "/")
    return text


def _collect_cloud_icons(ir: DiagramIR) -> tuple[str | None, dict[str, tuple[str, str]]]:
    """Determine which cloud provider's icon set to use, return (base_url, icon_table)."""
    provider = ir.cloud_provider
    if provider == "aws":
        return AWS_PLANTUML_BASE, AWS_PLANTUML_ICONS
    if provider == "azure":
        return AZURE_PLANTUML_BASE, AZURE_PLANTUML_ICONS
    if provider == "gcp":
        return GCP_PLANTUML_BASE, GCP_PLANTUML_ICONS
    if provider == "multi":
        # Multi-cloud: we'll handle includes per-icon
        return None, {}
    return None, {}


def _get_base_for_icon(icon_id: str) -> str | None:
    """Return the CDN base URL for a given icon id."""
    if icon_id.startswith("aws:"):
        return AWS_PLANTUML_BASE
    if icon_id.startswith("azure:"):
        return AZURE_PLANTUML_BASE
    if icon_id.startswith("gcp:"):
        return GCP_PLANTUML_BASE
    return None


def _collect_includes(ir: DiagramIR, graph: GraphIR) -> list[str]:
    """Build the !define and !include lines needed for all icons in the graph."""
    lines: list[str] = []
    provider = ir.cloud_provider

    # Collect all unique icon ids from nodes
    icon_ids: set[str] = set()
    for node in graph.nodes:
        if node.icon:
            icon_ids.add(node.icon)

    if not icon_ids:
        return lines

    # Determine which bases are needed
    bases_needed: dict[str, str] = {}  # define_name -> base_url
    for icon_id in icon_ids:
        base = _get_base_for_icon(icon_id)
        if base and base not in bases_needed.values():
            if icon_id.startswith("aws:"):
                bases_needed["AWSPuml"] = base
            elif icon_id.startswith("azure:"):
                bases_needed["AzurePuml"] = base
            elif icon_id.startswith("gcp:"):
                bases_needed["GCPPuml"] = base

    # Emit defines and common includes
    for define_name, base_url in sorted(bases_needed.items()):
        lines.append(f"!define {define_name} {base_url}")

    for define_name in sorted(bases_needed.keys()):
        if define_name == "AWSPuml":
            lines.append(f"!include {define_name}/AWSCommon.puml")
        elif define_name == "AzurePuml":
            lines.append(f"!include {define_name}/AzureCommon.puml")
        elif define_name == "GCPPuml":
            lines.append(f"!include {define_name}/GCPCommon.puml")

    # Collect group includes for AWS
    group_types_needed: set[str] = set()
    for group in graph.groups:
        if group.type in AWS_PLANTUML_GROUPS:
            group_types_needed.add(group.type)

    # Always include basic groups for AWS if we have AWS icons
    if "AWSPuml" in bases_needed:
        group_types_needed.update(["aws_cloud", "region"])

    for gtype in sorted(group_types_needed):
        if gtype in AWS_PLANTUML_GROUPS:
            path, _ = AWS_PLANTUML_GROUPS[gtype]
            lines.append(f"!include AWSPuml/{path}")

    # Emit icon includes
    for icon_id in sorted(icon_ids):
        icon_info = get_plantuml_icon(icon_id)
        if icon_info:
            path, _ = icon_info
            base = _get_base_for_icon(icon_id)
            if icon_id.startswith("aws:"):
                lines.append(f"!include AWSPuml/{path}")
            elif icon_id.startswith("azure:"):
                lines.append(f"!include AzurePuml/{path}")
            elif icon_id.startswith("gcp:"):
                lines.append(f"!include GCPPuml/{path}")

    return lines


def _render_node(node: IRNode) -> str:
    """Render a single node declaration."""
    icon_info = get_plantuml_icon(node.icon) if node.icon else None

    if icon_info:
        _, macro = icon_info
        tech = _safe_label(node.technology or "")
        label = _safe_label(node.label)
        return f'{macro}({node.id}, "{label}", "{tech}")'

    # Fallback: plain shape
    shape = _SHAPE_MAP.get(node.type, "rectangle")
    label = _safe_label(node.label)
    color_suffix = f" #{node.color.lstrip('#')}" if node.color else ""
    return f'{shape} "{label}" as {node.id}{color_suffix}'


def _render_edge(edge: IREdge) -> str:
    """Render a single edge."""
    if edge.arrow == "back":
        arrow_map = _ARROW_BACK
    elif edge.arrow == "both":
        arrow_map = _ARROW_BOTH
    elif edge.arrow == "none":
        arrow_map = _ARROW_NONE
    else:
        arrow_map = _ARROW_STYLE

    arrow = arrow_map.get(edge.style, "-->")

    if edge.label:
        label = _safe_label(edge.label)
        return f"{edge.source} {arrow} {edge.target} : {label}"
    return f"{edge.source} {arrow} {edge.target}"


def _build_group_tree(groups: list[IRGroup]) -> dict[str, list[str]]:
    """Build a mapping of group_id -> child group_ids for nesting."""
    all_group_ids = {g.id for g in groups}
    children_map: dict[str, list[str]] = {}
    for group in groups:
        child_groups = [c for c in group.children if c in all_group_ids]
        children_map[group.id] = child_groups
    return children_map


def _render_group_recursive(
    group: IRGroup,
    groups_by_id: dict[str, IRGroup],
    group_children: dict[str, list[str]],
    nodes_by_id: dict[str, IRNode],
    indent: int = 0,
) -> list[str]:
    """Render a group and its contents recursively."""
    lines: list[str] = []
    prefix = "  " * indent

    # Use AWS group macros if available
    if group.type in AWS_PLANTUML_GROUPS:
        _, macro = AWS_PLANTUML_GROUPS[group.type]
        label = _safe_label(group.label)
        lines.append(f'{prefix}{macro}({group.id}, "{label}") {{')
    else:
        label = _safe_label(group.label)
        color = f" #{group.color.lstrip('#')}" if group.color else ""
        lines.append(f'{prefix}rectangle "{label}" as {group.id}{color} {{')

    all_group_ids = set(groups_by_id.keys())

    # Render child groups first
    for child_id in group_children.get(group.id, []):
        if child_id in groups_by_id:
            child_group = groups_by_id[child_id]
            lines.extend(
                _render_group_recursive(
                    child_group, groups_by_id, group_children, nodes_by_id, indent + 1
                )
            )

    # Render child nodes (those not in nested groups)
    for child_id in group.children:
        if child_id not in all_group_ids and child_id in nodes_by_id:
            lines.append(f"{prefix}  {_render_node(nodes_by_id[child_id])}")

    lines.append(f"{prefix}}}")
    return lines


def generate_plantuml(ir: DiagramIR) -> str:
    """Generate PlantUML code from a DiagramIR with a graph variant.

    Returns syntactically valid PlantUML code ready for rendering.
    """
    graph = ir.graph
    if graph is None:
        raise ValueError("DiagramIR.graph must be populated for PlantUML generation")

    lines: list[str] = ["@startuml"]

    # allow_mixing for cloud diagrams
    if ir.cloud_provider:
        lines.append("allow_mixing")

    # Includes
    includes = _collect_includes(ir, graph)
    if includes:
        lines.extend(includes)

    # Skinparam
    has_actors = any(n.type == "actor" for n in graph.nodes)
    if has_actors:
        lines.append("skinparam actorStyle awesome")

    # Direction
    direction_map = {"TB": "top to bottom", "LR": "left to right", "RL": "right to left", "BT": "bottom to top"}
    lines.append(f"{direction_map.get(graph.direction, 'top to bottom')} direction")

    lines.append("")

    # Build lookup maps
    nodes_by_id = {n.id: n for n in graph.nodes}
    groups_by_id = {g.id: g for g in graph.groups}
    group_children = _build_group_tree(graph.groups)

    # Find root groups (not children of any other group)
    all_child_groups: set[str] = set()
    for children in group_children.values():
        all_child_groups.update(children)
    root_groups = [g for g in graph.groups if g.id not in all_child_groups]

    # Track which nodes are inside groups
    grouped_node_ids: set[str] = set()
    for group in graph.groups:
        for child in group.children:
            if child in nodes_by_id:
                grouped_node_ids.add(child)

    # Render groups (recursive)
    for group in root_groups:
        lines.extend(_render_group_recursive(group, groups_by_id, group_children, nodes_by_id))
        lines.append("")

    # Render ungrouped nodes
    for node in graph.nodes:
        if node.id not in grouped_node_ids:
            lines.append(_render_node(node))

    lines.append("")

    # Render edges
    for edge in graph.edges:
        lines.append(_render_edge(edge))

    lines.append("@enduml")

    return "\n".join(lines)
