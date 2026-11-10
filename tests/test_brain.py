"""Tests for the brains. No model needed: parsing, validation, and the
rule brain are pure functions. The LLM itself is measured by the v2
golden set (scripts/run_golden_llm.py), not by unit tests.
"""
from __future__ import annotations

from agentopsworkbench.brain import (
    RuleBrain,
    build_messages,
    parse_plan_output,
    validate_proposal,
)


def test_valid_plan_parses():
    p = parse_plan_output(
        '{"task": "update_customer_email", "customer_id": "C1001", '
        '"new_email": "asha.new@example.com"}'
    )
    assert p.ok
    assert p.task == "update_customer_email"
    assert p.inputs["new_email"] == "asha.new@example.com"


def test_fenced_json_parses():
    p = parse_plan_output(
        '```json\n{"task": "lookup_customer", "customer_id": "C1002"}\n```'
    )
    assert p.ok
    assert p.task == "lookup_customer"


def test_trailing_chatter_ignored():
    p = parse_plan_output(
        '{"task": "lookup_customer", "customer_id": "C1002"} '
        "Let me know if you need anything else."
    )
    assert p.ok


def test_garbage_is_unparseable():
    p = parse_plan_output("I think you should update the email.")
    assert not p.ok
    assert "unparseable" in p.error


def test_unknown_task_refused():
    p = parse_plan_output(
        '{"task": "delete_customer", "customer_id": "C1001"}'
    )
    assert not p.ok
    assert "unknown task" in p.error


def test_null_task_is_a_decline():
    p = parse_plan_output('{"task": null}')
    assert not p.ok
    assert "no matching task" in p.error


def test_missing_input_refused():
    p = parse_plan_output(
        '{"task": "update_customer_email", "customer_id": "C1001"}'
    )
    assert not p.ok
    assert "missing inputs" in p.error


def test_unknown_customer_refused():
    p = parse_plan_output(
        '{"task": "lookup_customer", "customer_id": "C9999"}'
    )
    assert not p.ok
    assert "unknown customer" in p.error


def test_validate_proposal_happy_path():
    p = validate_proposal(
        "update_customer_address",
        {"customer_id": "C1002", "new_address": "77 New Blvd"},
    )
    assert p.ok


def test_rule_brain_valid():
    p = RuleBrain().plan_task(
        "update_customer_email",
        {"customer_id": "C1001", "new_email": "a@b.c"},
    )
    assert p.ok


def test_rule_brain_unknown_task():
    p = RuleBrain().plan_task("delete_customer", {"customer_id": "C1001"})
    assert not p.ok


def test_prompt_lists_customers_and_tasks():
    messages = build_messages("Look up Ben Ortiz")
    system = messages[0]["content"]
    assert "C1001" in system and "Asha Verma" in system
    assert "update_customer_email" in system
    assert "no delete task" in system
    assert messages[1]["content"] == "Look up Ben Ortiz"
