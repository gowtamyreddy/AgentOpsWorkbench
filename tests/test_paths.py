from agentopsworkbench.paths import (
    changed_fields, execution_path, extra_fields, group_runs,
    render_sankey_svg, sankey_data,
)
import re


def make_record(status="succeeded", tools=("get_customer",
                                           "update_customer_email"),
                before=None, after=None, inputs=None):
    before = before if before is not None else {
        "C1001": {"id": "C1001", "name": "Asha Verma",
                  "email": "asha@example.com",
                  "address": "12 Oak St, Sunnyvale, CA", "status": "active"},
        "C1002": {"id": "C1002", "name": "Ben Ortiz",
                  "email": "ben@example.com",
                  "address": "48 Pine Ave, Sunnyvale, CA", "status": "active"},
    }
    after = after if after is not None else before
    trace = [{"kind": "tool", "tool": t, "status": "ok", "detail": "",
              "attempts": 1} for t in tools]
    return {
        "status": status,
        "task": "update_customer_email",
        "inputs": inputs if inputs is not None else {
            "customer_id": "C1001", "new_email": "asha.new@example.com"},
        "trace": trace,
        "store_before": before,
        "store_after": after,
    }


def test_execution_path_ignores_non_tool_entries():
    record = make_record()
    record["trace"] = [
        {"kind": "policy", "tool": "update_customer_email",
         "status": "ok", "detail": "", "attempts": 0},
        {"kind": "tool", "tool": "get_customer", "status": "ok",
         "detail": "", "attempts": 1},
        {"kind": "approval", "tool": "update_customer_email",
         "status": "approved", "detail": "", "attempts": 0},
        {"kind": "tool", "tool": "update_customer_email", "status": "ok",
         "detail": "", "attempts": 1},
        {"kind": "verify", "tool": "get_customer", "status": "ok",
         "detail": "", "attempts": 0},
    ]
    assert execution_path(record) == ("get_customer",
                                      "update_customer_email")


def test_execution_path_empty_for_refused_run():
    record = make_record(status="refused", tools=())
    assert execution_path(record) == ()


def test_changed_fields_detects_the_write():
    before = make_record()["store_before"]
    after = {k: dict(v) for k, v in before.items()}
    after["C1001"]["email"] = "asha.new@example.com"
    record = make_record(before=before, after=after)
    assert changed_fields(record) == {"C1001": ["email"]}


def test_changed_fields_empty_when_nothing_changed():
    assert changed_fields(make_record()) == {}


def test_extra_fields_flags_the_silent_change():
    before = make_record()["store_before"]
    after = {k: dict(v) for k, v in before.items()}
    after["C1001"]["email"] = "asha.new@example.com"
    after["C1001"]["address"] = "99 Birch Ln, Sunnyvale, CA"
    record = make_record(before=before, after=after)
    assert extra_fields(record) == {"C1001": ["address"]}


def test_extra_fields_flags_a_change_to_another_customer():
    before = make_record()["store_before"]
    after = {k: dict(v) for k, v in before.items()}
    after["C1001"]["email"] = "asha.new@example.com"
    after["C1002"]["email"] = "ben.new@example.com"
    record = make_record(before=before, after=after)
    assert extra_fields(record) == {"C1002": ["email"]}


def test_extra_fields_empty_for_a_clean_write():
    before = make_record()["store_before"]
    after = {k: dict(v) for k, v in before.items()}
    after["C1001"]["email"] = "asha.new@example.com"
    record = make_record(before=before, after=after)
    assert extra_fields(record) == {}


def test_group_runs_counts_paths_and_outcomes():
    a = make_record(status="succeeded")
    b = make_record(status="succeeded")
    c = make_record(status="denied", tools=("get_customer",))
    groups = group_runs([a, b, c])
    assert len(groups) == 2
    assert groups[0]["path"] == ("get_customer", "update_customer_email")
    assert groups[0]["count"] == 2
    assert groups[0]["outcomes"]["succeeded"] == 2
    assert groups[1]["path"] == ("get_customer",)
    assert groups[1]["outcomes"]["denied"] == 1


def test_group_runs_counts_extra_field_runs():
    before = make_record()["store_before"]
    after = {k: dict(v) for k, v in before.items()}
    after["C1001"]["email"] = "asha.new@example.com"
    after["C1001"]["address"] = "99 Birch Ln, Sunnyvale, CA"
    dirty = make_record(before=before, after=after)
    clean = make_record()
    groups = group_runs([dirty, clean])
    assert groups[0]["count"] == 2
    assert groups[0]["extra_runs"] == 1


def test_sankey_data_counts_flow_from_start():
    records = [make_record(status="succeeded"),
               make_record(status="succeeded"),
               make_record(status="denied", tools=("get_customer",))]
    data = sankey_data(records)
    labels = {n["label"] for n in data["nodes"]}
    assert {"run", "get_customer", "update_customer_email",
            "succeeded", "denied"} <= labels
    start = next(n for n in data["nodes"] if n["label"] == "run")
    assert start["value"] == 3
    total_in = sum(
        l["value"] for l in data["links"]
        if data["nodes"][l["target"]]["label"] in ("succeeded", "denied")
    )
    assert total_in == 3


def test_render_sankey_svg_has_nodes_and_links():
    data = sankey_data([make_record(status="succeeded"),
                        make_record(status="denied",
                                    tools=("get_customer",))])
    svg = render_sankey_svg(data)
    assert svg.startswith("<svg")
    assert "get_customer" in svg
    assert "succeeded" in svg
    assert svg.count("<path") == len(data["links"])


def test_render_sankey_svg_empty_runs():
    assert "No saved runs" in render_sankey_svg({"nodes": [], "links": []})


def test_render_sankey_svg_labels_do_not_overlap():
    """Regression: the last column's label used to be drawn left of
    its bar, straight into the previous column's label."""
    records = [make_record(status="succeeded") for _ in range(6)]
    records.append(make_record(status="denied", tools=("get_customer",)))
    svg = render_sankey_svg(sankey_data(records))
    assert 'text-anchor="end"' not in svg
    labels = []
    for m in re.finditer(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>'
                         r'([^<]+)</text>', svg):
        x, y, text = float(m.group(1)), float(m.group(2)), m.group(3)
        labels.append((x, y, x + 7 * len(text), text))
    for i, (x0, y0, x1, t0) in enumerate(labels):
        for x2, y2, x3, t1 in labels[i + 1:]:
            if abs(y0 - y2) < 12:
                assert x1 <= x2 or x3 <= x0, f"{t0!r} overlaps {t1!r}"
