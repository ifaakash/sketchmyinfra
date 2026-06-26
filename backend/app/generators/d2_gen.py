"""Deterministic D2 code generator from IR variants.

Supports: GraphIR, ERDiagramIR, SequenceDiagramIR, ClassDiagramIR, StateDiagramIR.
"""

from __future__ import annotations

from app.ir.schema import (
    ClassDiagramIR,
    DiagramIR,
    ERDiagramIR,
    GraphIR,
    IREdge,
    IRGroup,
    IRNode,
    SequenceDiagramIR,
    StateDiagramIR,
)

from .icons import get_d2_icon

# D2 shape mapping from IR node types
_SHAPE_MAP: dict[str, str] = {
    "rectangle": "rectangle",
    "database": "cylinder",
    "queue": "queue",
    "cloud": "cloud",
    "actor": "person",
    "component": "rectangle",
    "node": "rectangle",
    "frame": "rectangle",
    "storage": "stored_data",
    "package": "package",
    "diamond": "diamond",
    "oval": "oval",
    "hexagon": "hexagon",
    "circle": "circle",
}

# Edge style to D2 stroke-dash value (0 = solid)
_STROKE_DASH: dict[str, int] = {
    "solid": 0,
    "dotted": 3,
    "dashed": 5,
}


def _safe_label(text: str) -> str:
    """Escape characters that could break D2 labels."""
    # D2 labels in quotes are generally safe, but backslash and quotes need escaping
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    return text


def _safe_id(text: str) -> str:
    """Ensure an ID is valid for D2 (no spaces, special chars)."""
    return text.replace(" ", "_").replace("-", "_").replace(".", "_")


# ---------------------------------------------------------------------------
# Graph IR → D2
# ---------------------------------------------------------------------------

def _render_graph_node(node: IRNode, indent: int = 0) -> list[str]:
    """Render a node with its properties."""
    lines: list[str] = []
    prefix = "  " * indent
    nid = _safe_id(node.id)
    label = _safe_label(node.label)
    shape = _SHAPE_MAP.get(node.type, "rectangle")
    icon_url = get_d2_icon(node.icon) if node.icon else None

    lines.append(f'{prefix}{nid}: "{label}" {{')
    lines.append(f"{prefix}  shape: {shape}")

    if icon_url:
        lines.append(f"{prefix}  icon: {icon_url}")

    if node.color:
        lines.append(f"{prefix}  style.fill: \"{node.color}\"")

    if node.technology:
        tech = _safe_label(node.technology)
        lines.append(f'{prefix}  near: top-center')
        # Use tooltip or a nested label for technology
        lines[-1] = f"{prefix}  # {tech}"  # D2 comment for tech info

    lines.append(f"{prefix}}}")
    return lines


def _render_graph_edge(edge: IREdge) -> str:
    """Render an edge connection."""
    src = _safe_id(edge.source)
    tgt = _safe_id(edge.target)

    # Arrow direction
    if edge.arrow == "forward":
        arrow = "->"
    elif edge.arrow == "back":
        arrow = "<-"
    elif edge.arrow == "both":
        arrow = "<->"
    else:
        arrow = "--"

    if edge.label:
        label = _safe_label(edge.label)
        line = f'{src} {arrow} {tgt}: "{label}"'
    else:
        line = f"{src} {arrow} {tgt}"

    # Add style block for non-solid edges
    if edge.style != "solid":
        dash = _STROKE_DASH.get(edge.style, 0)
        line += f" {{\n  style.stroke-dash: {dash}\n}}"

    return line


def _render_group_recursive(
    group: IRGroup,
    groups_by_id: dict[str, IRGroup],
    group_children_map: dict[str, list[str]],
    nodes_by_id: dict[str, IRNode],
    indent: int = 0,
) -> list[str]:
    """Render a D2 container (group) recursively."""
    lines: list[str] = []
    prefix = "  " * indent
    gid = _safe_id(group.id)
    label = _safe_label(group.label)

    lines.append(f'{prefix}{gid}: "{label}" {{')

    if group.color:
        lines.append(f'{prefix}  style.fill: "{group.color}"')

    all_group_ids = set(groups_by_id.keys())

    # Render nested groups
    for child_id in group_children_map.get(group.id, []):
        if child_id in groups_by_id:
            lines.extend(
                _render_group_recursive(
                    groups_by_id[child_id],
                    groups_by_id,
                    group_children_map,
                    nodes_by_id,
                    indent + 1,
                )
            )

    # Render child nodes
    for child_id in group.children:
        if child_id not in all_group_ids and child_id in nodes_by_id:
            lines.extend(_render_graph_node(nodes_by_id[child_id], indent + 1))

    lines.append(f"{prefix}}}")
    return lines


def _generate_graph(ir: DiagramIR) -> str:
    """Generate D2 from GraphIR."""
    graph = ir.graph
    if graph is None:
        raise ValueError("DiagramIR.graph must be populated")

    lines: list[str] = []

    # Direction
    dir_map = {"TB": "down", "LR": "right", "RL": "left", "BT": "up"}
    lines.append(f"direction: {dir_map.get(graph.direction, 'down')}")
    lines.append("")

    # Title
    if graph.title:
        title = _safe_label(graph.title)
        lines.append(f'title: "{title}" {{')
        lines.append("  near: top-center")
        lines.append("  style.font-size: 24")
        lines.append("  style.underline: true")
        lines.append("}")
        lines.append("")

    nodes_by_id = {n.id: n for n in graph.nodes}
    groups_by_id = {g.id: g for g in graph.groups}

    # Build group children map
    all_group_ids = set(groups_by_id.keys())
    group_children_map: dict[str, list[str]] = {}
    for group in graph.groups:
        group_children_map[group.id] = [c for c in group.children if c in all_group_ids]

    # Find root groups
    all_child_groups: set[str] = set()
    for children in group_children_map.values():
        all_child_groups.update(children)
    root_groups = [g for g in graph.groups if g.id not in all_child_groups]

    # Track grouped nodes
    grouped_node_ids: set[str] = set()
    for group in graph.groups:
        for child in group.children:
            if child in nodes_by_id:
                grouped_node_ids.add(child)

    # Render groups
    for group in root_groups:
        lines.extend(_render_group_recursive(group, groups_by_id, group_children_map, nodes_by_id))
        lines.append("")

    # Render ungrouped nodes
    for node in graph.nodes:
        if node.id not in grouped_node_ids:
            lines.extend(_render_graph_node(node))
            lines.append("")

    # Render edges
    for edge in graph.edges:
        lines.append(_render_graph_edge(edge))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ER Diagram IR → D2
# ---------------------------------------------------------------------------

def _generate_er(ir: DiagramIR) -> str:
    """Generate D2 from ERDiagramIR using sql_table shapes."""
    er = ir.er
    if er is None:
        raise ValueError("DiagramIR.er must be populated")

    lines: list[str] = []
    lines.append("direction: right")
    lines.append("")

    if er.title:
        title = _safe_label(er.title)
        lines.append(f'title: "{title}" {{')
        lines.append("  near: top-center")
        lines.append("  style.font-size: 24")
        lines.append("}")
        lines.append("")

    # Render entities as sql_table
    for entity in er.entities:
        eid = _safe_id(entity.id)
        lines.append(f"{eid}: {entity.name} {{")
        lines.append("  shape: sql_table")

        for attr in entity.attributes:
            constraint_parts: list[str] = []
            if attr.pk:
                constraint_parts.append("primary_key")
            if attr.fk:
                constraint_parts.append("foreign_key")
            if not attr.nullable and not attr.pk:
                constraint_parts.append("not_null")

            if len(constraint_parts) == 1:
                lines.append(f"  {attr.name}: {attr.type} {{constraint: {constraint_parts[0]}}}")
            elif len(constraint_parts) > 1:
                constraints = "; ".join(constraint_parts)
                lines.append(f"  {attr.name}: {attr.type} {{constraint: [{constraints}]}}")
            else:
                lines.append(f"  {attr.name}: {attr.type}")

        lines.append("}")
        lines.append("")

    # Render relationships
    for rel in er.relationships:
        from_id = _safe_id(rel.from_entity)
        to_id = _safe_id(rel.to_entity)
        label = _safe_label(rel.label)
        card = rel.cardinality
        lines.append(f'{from_id} -> {to_id}: "{label} ({card})"')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sequence Diagram IR → D2
# ---------------------------------------------------------------------------

def _generate_sequence(ir: DiagramIR) -> str:
    """Generate D2 from SequenceDiagramIR."""
    seq = ir.sequence
    if seq is None:
        raise ValueError("DiagramIR.sequence must be populated")

    lines: list[str] = []
    lines.append("diagram: {")
    lines.append("  shape: sequence_diagram")
    lines.append("")

    # Declare participants
    for p in seq.participants:
        pid = _safe_id(p.id)
        label = _safe_label(p.label)
        lines.append(f'  {pid}: "{label}"')

    lines.append("")

    # Render messages
    for msg in seq.messages:
        from_id = _safe_id(msg.from_id)
        to_id = _safe_id(msg.to_id)
        label = _safe_label(msg.label)

        if msg.type == "async":
            # D2 doesn't have a native async arrow; use dashed style
            lines.append(f'  {from_id} -> {to_id}: "{label}" {{')
            lines.append("    style.stroke-dash: 3")
            lines.append("  }")
        elif msg.type == "reply":
            lines.append(f'  {from_id} -> {to_id}: "{label}" {{')
            lines.append("    style.stroke-dash: 5")
            lines.append("  }")
        elif msg.type == "self":
            lines.append(f'  {from_id} -> {from_id}: "{label}"')
        else:
            # sync (default)
            lines.append(f'  {from_id} -> {to_id}: "{label}"')

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Class Diagram IR → D2
# ---------------------------------------------------------------------------

def _generate_class(ir: DiagramIR) -> str:
    """Generate D2 from ClassDiagramIR using class shapes."""
    cd = ir.class_diagram
    if cd is None:
        raise ValueError("DiagramIR.class_diagram must be populated")

    lines: list[str] = []
    lines.append("direction: down")
    lines.append("")

    if cd.title:
        title = _safe_label(cd.title)
        lines.append(f'title: "{title}" {{')
        lines.append("  near: top-center")
        lines.append("  style.font-size: 24")
        lines.append("}")
        lines.append("")

    visibility_map = {"public": "+", "private": "-", "protected": "#"}

    for cls in cd.classes:
        cid = _safe_id(cls.id)
        lines.append(f"{cid}: {cls.name} {{")
        lines.append("  shape: class")

        # Attributes
        for attr in cls.attributes:
            vis = visibility_map.get(attr.visibility, "+")
            lines.append(f"  {vis}{attr.name}: {attr.type}")

        # Methods
        for method in cls.methods:
            vis = visibility_map.get(method.visibility, "+")
            params = method.parameters or ""
            ret = f": {method.return_type}" if method.return_type else ""
            lines.append(f"  {vis}{method.name}({params}){ret}")

        lines.append("}")
        lines.append("")

    # Relationships
    rel_arrow_map = {
        "inheritance": "->",
        "implementation": "->",
        "composition": "->",
        "aggregation": "->",
        "association": "->",
        "dependency": "->",
    }

    for rel in cd.relationships:
        from_id = _safe_id(rel.from_class)
        to_id = _safe_id(rel.to_class)
        arrow = rel_arrow_map.get(rel.type, "->")
        if rel.label:
            label = _safe_label(rel.label)
            lines.append(f'{from_id} {arrow} {to_id}: "{label} ({rel.type})"')
        else:
            lines.append(f'{from_id} {arrow} {to_id}: "{rel.type}"')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# State Diagram IR → D2
# ---------------------------------------------------------------------------

def _generate_state(ir: DiagramIR) -> str:
    """Generate D2 from StateDiagramIR."""
    sd = ir.state
    if sd is None:
        raise ValueError("DiagramIR.state must be populated")

    lines: list[str] = []
    lines.append("direction: right")
    lines.append("")

    if sd.title:
        title = _safe_label(sd.title)
        lines.append(f'title: "{title}" {{')
        lines.append("  near: top-center")
        lines.append("  style.font-size: 24")
        lines.append("}")
        lines.append("")

    # Render states
    for state in sd.states:
        sid = _safe_id(state.id)
        label = _safe_label(state.label)
        if state.type in ("start", "end"):
            # D2 doesn't have start/end pseudo-states natively; use a small circle
            lines.append(f'{sid}: "{label}" {{')
            lines.append("  shape: circle")
            lines.append("  style.fill: \"#000000\"")
            lines.append("  width: 30")
            lines.append("  height: 30")
            lines.append("}")
        elif state.type == "choice":
            lines.append(f'{sid}: "{label}" {{')
            lines.append("  shape: diamond")
            lines.append("}")
        else:
            lines.append(f'{sid}: "{label}"')

        # Composite states (nested children)
        if state.children:
            # Re-declare as container
            lines[-1] = f'{sid}: "{label}" {{'
            for child in state.children:
                child_id = _safe_id(child.id)
                child_label = _safe_label(child.label)
                lines.append(f'  {child_id}: "{child_label}"')
            lines.append("}")

        lines.append("")

    # Render transitions
    for trans in sd.transitions:
        from_id = _safe_id(trans.from_state)
        to_id = _safe_id(trans.to_state)
        if trans.label:
            label = _safe_label(trans.label)
            if trans.guard:
                guard = _safe_label(trans.guard)
                lines.append(f'{from_id} -> {to_id}: "{label} [{guard}]"')
            else:
                lines.append(f'{from_id} -> {to_id}: "{label}"')
        else:
            lines.append(f"{from_id} -> {to_id}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_d2(ir: DiagramIR) -> str:
    """Generate D2 code from a DiagramIR.

    Dispatches to the appropriate sub-generator based on which IR variant
    is populated.
    """
    if ir.er is not None:
        return _generate_er(ir)
    if ir.sequence is not None:
        return _generate_sequence(ir)
    if ir.class_diagram is not None:
        return _generate_class(ir)
    if ir.state is not None:
        return _generate_state(ir)
    if ir.graph is not None:
        return _generate_graph(ir)
    raise ValueError("No IR variant populated for D2 generation")
