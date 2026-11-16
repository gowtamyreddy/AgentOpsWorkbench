"""Execution paths across saved runs, and the Sankey view over them.

A run record already holds everything needed: the trace lists every
tool call in order, and store_before/store_after hold the full store
on both sides of the run. From that:

- execution_path: the ordered tool names from the trace.
- changed_fields: which fields actually changed, per customer.
- extra_fields: changed fields the request never asked for. A
  change to another customer is extra by definition.
- group_runs: runs grouped by their path, with outcomes and a
  count of runs that changed an extra field.
- sankey_data + render_sankey_svg: the diagram. Nodes are
  (depth, label) pairs so the same tool at a different depth is a
  different node; links carry run counts. No new dependency: the
  SVG is built by hand.
"""
from __future__ import annotations

from collections import Counter

# What the request asked to change, by input name.
INPUT_TO_FIELD = {"new_email": "email", "new_address": "address"}

STATUS_COLORS = {
    "succeeded": "#2e7d32",
    "refused": "#b58900",
    "denied": "#b58900",
    "failed": "#b00020",
    "verification_failed": "#b00020",
}
TOOL_COLOR = "#5b7fa6"
START_COLOR = "#888888"


def execution_path(record):
    """Ordered tool names from the trace, ignoring policy/approval/verify."""
    return tuple(
        e["tool"] for e in record.get("trace", []) if e.get("kind") == "tool"
    )


def changed_fields(record):
    """Fields that differ between store_before and store_after.

    Returns {customer_id: sorted list of changed field names}.
    """
    before = record.get("store_before") or {}
    after = record.get("store_after") or {}
    changed = {}
    for cid in set(before) | set(after):
        b, a = before.get(cid) or {}, after.get(cid) or {}
        diff = sorted({k for k in set(b) | set(a) if b.get(k) != a.get(k)})
        if diff:
            changed[cid] = diff
    return changed


def expected_fields(record):
    """Fields the request asked to change, for the target customer."""
    inputs = record.get("inputs") or {}
    customer = inputs.get("customer_id")
    if not customer:
        return {}, set()
    fields = {
        INPUT_TO_FIELD[k] for k in inputs if k in INPUT_TO_FIELD
    }
    return customer, fields


def extra_fields(record):
    """Changed fields the request never asked for.

    Returns {customer_id: sorted list of extra field names}. Any
    change to a customer other than the target counts as extra.
    """
    changed = changed_fields(record)
    if not changed:
        return {}
    customer, expected = expected_fields(record)
    extra = {}
    for cid, fields in changed.items():
        if cid == customer:
            rest = sorted(set(fields) - expected)
        else:
            rest = fields
        if rest:
            extra[cid] = rest
    return extra


def group_runs(records):
    """Group records by execution path.

    Returns a list of groups, most runs first. Each group has the
    path tuple, the run count, an outcome counter, and how many of
    its runs changed an extra field.
    """
    groups = {}
    for record in records:
        path = execution_path(record)
        group = groups.setdefault(path, {
            "path": path,
            "count": 0,
            "outcomes": Counter(),
            "extra_runs": 0,
        })
        group["count"] += 1
        group["outcomes"][record.get("status", "unknown")] += 1
        if extra_fields(record):
            group["extra_runs"] += 1
    return sorted(groups.values(), key=lambda g: -g["count"])


def sankey_data(records):
    """Nodes and links for the Sankey diagram.

    Nodes are (depth, label) pairs. Every run flows start -> first
    tool -> ... -> last tool -> outcome; a run with no tool calls
    flows start -> outcome. Link values are run counts.
    """
    node_index = {}
    nodes = []
    links = Counter()

    def node(depth, label):
        key = (depth, label)
        if key not in node_index:
            node_index[key] = len(nodes)
            nodes.append({"depth": depth, "label": label, "value": 0})
        return node_index[key]

    for record in records:
        path = execution_path(record)
        status = record.get("status", "unknown")
        chain = [(0, "run")]
        chain += [(i + 1, tool) for i, tool in enumerate(path)]
        chain.append((len(path) + 1, status))
        prev = None
        for depth, label in chain:
            idx = node(depth, label)
            nodes[idx]["value"] += 1
            if prev is not None:
                links[(prev, idx)] += 1
            prev = idx
    return {
        "nodes": nodes,
        "links": [
            {"source": s, "target": t, "value": v}
            for (s, t), v in links.items()
        ],
    }


def render_sankey_svg(data, width=760, height=360):
    """Render Sankey data as an SVG string. No dependency, pure layout.

    Columns are depths, left to right. Inside a column, nodes stack
    by flow, largest first, with heights proportional to flow.
    Links are bezier ribbons whose widths match their counts.
    """
    nodes, links = data["nodes"], data["links"]
    if not nodes:
        return "<p>No saved runs yet.</p>"
    max_depth = max(n["depth"] for n in nodes)
    node_w = 16
    gap = 14
    pad = 8
    step = ((width - 2 * pad - node_w) / max_depth) if max_depth else 0
    columns = {}
    for i, n in enumerate(nodes):
        columns.setdefault(n["depth"], []).append(i)
    # One scale for all columns, so the tallest column fits.
    scale = min(
        (height - 2 * pad - gap * (len(col) - 1))
        / max(sum(nodes[i]["value"] for i in col), 1)
        for col in columns.values()
    )
    # Node rectangles: (x, y, height) per node.
    rects = {}
    for depth, idxs in columns.items():
        idxs = sorted(idxs, key=lambda i: -nodes[i]["value"])
        x = pad + depth * step
        y = pad
        for i in idxs:
            h = max(nodes[i]["value"] * scale, 4)
            rects[i] = (x, y, h)
            y += h + gap
    # Link vertical spans: stack links per node, source order then target.
    out_spans, in_spans = {}, {}
    for link in sorted(links, key=lambda l: (l["source"], l["target"])):
        s, t, v = link["source"], link["target"], link["value"]
        sx, sy, sh = rects[s]
        tx, ty, th = rects[t]
        so = out_spans.get(s, 0)
        ti = in_spans.get(t, 0)
        out_spans[s] = so + v * scale
        in_spans[t] = ti + v * scale
        link["y0"] = sy + so
        link["y1"] = ty + ti
        link["h"] = v * scale
    parts = [f'<svg width="{width}" height="{height}" '
             f'xmlns="http://www.w3.org/2000/svg" '
             f'font-family="sans-serif" font-size="12">']
    for link in links:
        s, t = link["source"], link["target"]
        sx = rects[s][0] + node_w
        tx = rects[t][0]
        y0, y1, h = link["y0"], link["y1"], link["h"]
        mx = (sx + tx) / 2
        color = node_color(nodes[t]) if nodes[t]["label"] in STATUS_COLORS else TOOL_COLOR
        parts.append(
            f'<path d="M{sx},{y0} C{mx},{y0} {mx},{y1} {tx},{y1} '
            f'L{tx},{y1 + h} C{mx},{y1 + h} {mx},{y0 + h} {sx},{y0 + h} Z" '
            f'fill="{color}" fill-opacity="0.25" />'
        )
    for i, n in enumerate(nodes):
        x, y, h = rects[i]
        color = node_color(n)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{node_w}" height="{h}" '
            f'fill="{color}" rx="2" />'
        )
        label = f"{n['label']} ({n['value']})"
        if n["depth"] == max_depth:
            parts.append(
                f'<text x="{x - 6}" y="{y + h / 2 + 4}" '
                f'text-anchor="end" fill="#333">{label}</text>'
            )
        else:
            parts.append(
                f'<text x="{x + node_w + 6}" y="{y + h / 2 + 4}" '
                f'fill="#333">{label}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def node_color(node):
    if node["label"] in STATUS_COLORS:
        return STATUS_COLORS[node["label"]]
    if node["label"] == "run":
        return START_COLOR
    return TOOL_COLOR
