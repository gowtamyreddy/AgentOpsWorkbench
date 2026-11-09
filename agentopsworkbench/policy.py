"""Tasks and the deterministic dispatcher.

A task declares exactly which tools it may use (the allow-list) and the
steps to run. The dispatcher only builds plans from the declaration;
it never invents a step. The executor re-checks every step against the
allow-list anyway, so a bad plan is refused at run time too.
"""
from __future__ import annotations


TASKS = {
    "update_customer_email": {
        "allowed_tools": ["get_customer", "update_customer_email"],
        "steps": [
            {"tool": "get_customer", "args": {"customer_id": "{customer_id}"}},
            {
                "tool": "update_customer_email",
                "args": {"customer_id": "{customer_id}", "new_email": "{new_email}"},
            },
        ],
        "verify": {
            "tool": "get_customer",
            "args": {"customer_id": "{customer_id}"},
            "expect": {"email": "{new_email}"},
        },
    },
    "update_customer_address": {
        "allowed_tools": ["get_customer", "update_customer_address"],
        "steps": [
            {"tool": "get_customer", "args": {"customer_id": "{customer_id}"}},
            {
                "tool": "update_customer_address",
                "args": {
                    "customer_id": "{customer_id}",
                    "new_address": "{new_address}",
                },
            },
        ],
        "verify": {
            "tool": "get_customer",
            "args": {"customer_id": "{customer_id}"},
            "expect": {"address": "{new_address}"},
        },
    },
    "lookup_customer": {
        "allowed_tools": ["get_customer", "search_customers"],
        "steps": [
            {"tool": "get_customer", "args": {"customer_id": "{customer_id}"}},
        ],
        "verify": None,
    },
}


def _fill(template, inputs):
    if isinstance(template, dict):
        return {k: _fill(v, inputs) for k, v in template.items()}
    if isinstance(template, str) and template.startswith("{") and template.endswith("}"):
        key = template[1:-1]
        if key not in inputs:
            raise ValueError(f"missing task input: {key}")
        return inputs[key]
    return template


def build_plan(task_name, inputs):
    """Return (plan_steps, allow_list, verify_spec) for a named task."""
    task = TASKS.get(task_name)
    if task is None:
        raise ValueError(f"unknown task {task_name}")
    steps = [
        {"tool": s["tool"], "args": _fill(s["args"], inputs)}
        for s in task["steps"]
    ]
    verify = None
    if task.get("verify"):
        verify = {
            "tool": task["verify"]["tool"],
            "args": _fill(task["verify"]["args"], inputs),
            "expect": _fill(task["verify"]["expect"], inputs),
        }
    return steps, list(task["allowed_tools"]), verify
