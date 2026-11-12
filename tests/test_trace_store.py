"""Run records: saving, loading, and replaying a run."""
import pytest

from agentopsworkbench.approval import always_approve, always_deny
from agentopsworkbench.cli import replay
from agentopsworkbench.executor import run_plan
from agentopsworkbench.policy import build_plan
from agentopsworkbench.store import CustomerStore
from agentopsworkbench.trace_store import (
    build_record, list_runs, load_run, save_run,
)


def _run_id(path):
    return path.stem[len("run-"):]


def _saved_rule_run(base, approver=always_approve):
    store = CustomerStore()
    before = store.snapshot()
    steps, allow_list, verify = build_plan(
        "update_customer_email",
        {"customer_id": "C1001", "new_email": "asha.new@example.com"},
    )
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify)
    record = build_record(
        source="cli", brain="rule", task="update_customer_email",
        inputs={"customer_id": "C1001",
                "new_email": "asha.new@example.com"},
        plan=steps, status=result.status, trace=result.trace,
        store_before=before, store_after=result.store_snapshot)
    return save_run(record, base=base)


def test_save_load_round_trip(tmp_path):
    record = build_record(source="cli", brain="rule",
                          task="lookup_customer",
                          inputs={"customer_id": "C1002"},
                          status="succeeded")
    path = save_run(record, base=tmp_path)
    loaded = load_run(_run_id(path), base=tmp_path)
    assert loaded["task"] == "lookup_customer"
    assert loaded["status"] == "succeeded"
    assert loaded["run_id"] == record["run_id"]


def test_list_runs_finds_saved_runs(tmp_path):
    _saved_rule_run(tmp_path)
    _saved_rule_run(tmp_path)
    assert len(list_runs(base=tmp_path)) == 2


def test_load_missing_run_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_run("does-not-exist", base=tmp_path)


def test_replay_rule_run_matches(tmp_path):
    path = _saved_rule_run(tmp_path)
    assert replay(_run_id(path), base=tmp_path) == 0


def test_replay_denied_run_matches(tmp_path):
    # A denied run replays denied: the recorded approval decisions
    # are honored instead of auto-approving.
    path = _saved_rule_run(tmp_path, approver=always_deny)
    assert replay(_run_id(path), base=tmp_path) == 0


def test_replay_refused_rule_record_matches(tmp_path):
    # A refusal from bad inputs replays refused, not a crash.
    store = CustomerStore()
    record = build_record(
        source="cli", brain="rule", task="update_customer_email",
        inputs={"customer_id": "C1001"},
        refusal_reason="missing new_email", status="refused",
        store_before=store.snapshot(), store_after=store.snapshot())
    path = save_run(record, base=tmp_path)
    assert replay(_run_id(path), base=tmp_path) == 0
