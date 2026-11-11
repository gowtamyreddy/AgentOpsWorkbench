"""Guardrail tests, one file per rule the workbench promises."""
import pytest

from agentopsworkbench.approval import always_approve, always_deny
from agentopsworkbench.executor import run_plan
from agentopsworkbench.policy import TASKS, build_plan
from agentopsworkbench.registry import get_tool
from agentopsworkbench.store import CustomerStore


def email_plan(email="asha.new@example.com"):
    steps, allow_list, verify = build_plan(
        "update_customer_email",
        {"customer_id": "C1001", "new_email": email},
    )
    return steps, allow_list, verify


def test_registry_side_effect_classes():
    assert not get_tool("get_customer").needs_approval()
    assert not get_tool("search_customers").needs_approval()
    assert get_tool("update_customer_email").needs_approval()
    assert get_tool("delete_customer").needs_approval()


def test_dispatcher_rejects_unknown_task_and_missing_input():
    with pytest.raises(ValueError):
        build_plan("no_such_task", {})
    with pytest.raises(ValueError):
        build_plan("update_customer_email", {"customer_id": "C1001"})


def test_allow_list_refuses_before_any_call():
    store = CustomerStore()
    steps = [{"tool": "delete_customer", "args": {"customer_id": "C1001"}}]
    result = run_plan(steps, ["get_customer", "update_customer_email"],
                      store, always_approve)
    assert result.status == "refused"
    assert result.tool_calls("delete_customer") == 0
    assert "C1001" in store.snapshot()


def test_normal_update_succeeds_and_verifies():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify)
    assert result.status == "succeeded"
    assert store.snapshot()["C1001"]["email"] == "asha.new@example.com"


def test_transient_failure_recovers_inside_budget():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify,
                      faults={"update_customer_email": {"fail_times": 2}})
    assert result.status == "succeeded"
    attempts = max(e.attempts for e in result.trace
                   if e.kind == "tool" and e.tool == "update_customer_email")
    assert attempts == 3


def test_persistent_failure_stops_after_budget():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify,
                      faults={"update_customer_email": {"fail_times": 5}})
    assert result.status == "failed"
    assert store.snapshot()["C1001"]["email"] == "asha@example.com"
    attempts = max(e.attempts for e in result.trace
                   if e.kind == "tool" and e.tool == "update_customer_email")
    assert attempts == 3


def test_denied_approval_means_no_mutation_and_no_tool_call():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_deny,
                      verify_spec=verify)
    assert result.status == "denied"
    assert result.tool_calls("update_customer_email") == 0
    assert store.snapshot()["C1001"]["email"] == "asha@example.com"


def test_read_only_task_never_asks_for_approval():
    store = CustomerStore()
    steps, allow_list, verify = build_plan(
        "lookup_customer", {"customer_id": "C1002"})
    calls = []
    result = run_plan(steps, allow_list, store,
                      lambda t, a: calls.append(t) or True,
                      verify_spec=verify)
    assert result.status == "succeeded"
    assert calls == []


def test_verification_catches_wrong_write():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify,
                      faults={"update_customer_email":
                              {"write_wrong": "wrong@example.com"}})
    assert result.status == "verification_failed"
    assert store.snapshot()["C1001"]["email"] == "wrong@example.com"


def test_verification_catches_side_mutation():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify,
                      faults={"update_customer_email":
                              {"write_extra": {"address": "1 Wrong Rd"}}})
    assert result.status == "verification_failed"
    assert "address" in result.trace[-1].detail
    assert store.snapshot()["C1001"]["address"] == "1 Wrong Rd"


def test_verification_catches_wrong_target_write():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify,
                      faults={"update_customer_email":
                              {"write_target": "C1002"}})
    assert result.status == "verification_failed"
    assert store.snapshot()["C1002"]["email"] == "asha.new@example.com"
    assert store.snapshot()["C1001"]["email"] == "asha@example.com"


def test_verification_passes_when_only_expected_field_changes():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify)
    assert result.status == "succeeded"
    assert store.snapshot()["C1001"]["email"] == "asha.new@example.com"


def test_denial_is_terminal_even_when_tool_would_fail():
    store = CustomerStore()
    steps, allow_list, verify = email_plan()
    result = run_plan(steps, allow_list, store, always_deny,
                      verify_spec=verify,
                      faults={"update_customer_email": {"fail_times": 2}})
    assert result.status == "denied"
    assert result.tool_calls("update_customer_email") == 0
    assert result.approver_calls() == 1


def test_trace_records_every_stage():
    store = CustomerStore()
    steps, allow_list, verify = build_plan(
        "update_customer_address",
        {"customer_id": "C1002", "new_address": "77 New Blvd, Sunnyvale, CA"})
    result = run_plan(steps, allow_list, store, always_approve,
                      verify_spec=verify)
    assert result.status == "succeeded"
    kinds = {e.kind for e in result.trace}
    assert {"tool", "approval", "verify"} <= kinds
    assert any(e.tool == "update_customer_address" for e in result.trace)


def test_every_task_has_an_allow_list():
    for name, task in TASKS.items():
        assert task["allowed_tools"], name
        for step in task["steps"]:
            assert step["tool"] in task["allowed_tools"], (name, step)
