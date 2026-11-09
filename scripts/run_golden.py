"""Golden set runner. Exit code 0 only if every scenario passes and
there are zero unauthorized mutations.

An unauthorized mutation is any change to the store that the scenario
did not declare in expect_store. Scenario 08 declares the wrong write
because the bad value really is in the store; the point is that the
verifier caught it, not that the store stayed clean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentopsworkbench.approval import always_approve, always_deny
from agentopsworkbench.executor import run_plan
from agentopsworkbench.policy import build_plan
from agentopsworkbench.store import SEED, CustomerStore


def store_diffs(before, after):
    diffs = []
    for cid in set(before) | set(after):
        if cid not in after:
            diffs.append(f"{cid} deleted")
        elif cid not in before:
            diffs.append(f"{cid} created")
        else:
            for field in set(before[cid]) | set(after[cid]):
                if before[cid].get(field) != after[cid].get(field):
                    diffs.append(f"{cid}.{field}")
    return diffs


def expected_diffs(expect_store):
    if expect_store.get("unchanged"):
        return set()
    return {k for k in expect_store if k != "unchanged"}


def check_trace(result, expect_trace):
    problems = []
    if "approver_calls" in expect_trace:
        got = result.approver_calls()
        want = expect_trace["approver_calls"]
        if got != want:
            problems.append(f"approver_calls {got} != {want}")
    for tool_name, want in expect_trace.get("tool_calls", {}).items():
        got = result.tool_calls(tool_name)
        if got != want:
            problems.append(f"tool_calls[{tool_name}] {got} != {want}")
    for tool_name, want in expect_trace.get("max_attempts", {}).items():
        got = max(
            (e.attempts for e in result.trace
             if e.kind == "tool" and e.tool == tool_name),
            default=0,
        )
        if got != want:
            problems.append(f"max_attempts[{tool_name}] {got} != {want}")
    if "kinds" in expect_trace:
        got = {e.kind for e in result.trace}
        missing = set(expect_trace["kinds"]) - got
        if missing:
            problems.append(f"trace missing kinds {sorted(missing)}")
    return problems


def run_scenario(scenario):
    store = CustomerStore()
    before = store.snapshot()
    approver = always_approve if scenario["approver"] == "approve" else always_deny
    if "task" in scenario:
        steps, allow_list, verify_spec = build_plan(
            scenario["task"], scenario["inputs"]
        )
    else:
        steps, allow_list, verify_spec = scenario["steps"], scenario["allow_list"], None
    result = run_plan(
        steps, allow_list, store, approver,
        verify_spec=verify_spec, faults=scenario.get("faults", {}),
    )
    problems = []
    if result.status != scenario["expected_status"]:
        problems.append(
            f"status {result.status} != {scenario['expected_status']}"
        )
    after = result.store_snapshot
    expect = scenario.get("expect_store", {})
    if expect.get("unchanged"):
        if after != before:
            problems.append("store changed but expected unchanged")
    else:
        for key, want in expect.items():
            cid, field_name = key.split(".", 1)
            got = after.get(cid, {}).get(field_name)
            if got != want:
                problems.append(f"store {key} {got!r} != {want!r}")
    unauthorized = [
        d for d in store_diffs(before, after)
        if d not in expected_diffs(expect)
    ]
    problems.extend(check_trace(result, scenario.get("expect_trace", {})))
    return result, problems, unauthorized


def main():
    path = Path(__file__).resolve().parents[1] / "data" / "golden_scenarios.jsonl"
    scenarios = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    total_unauthorized = 0
    passed = 0
    for scenario in scenarios:
        result, problems, unauthorized = run_scenario(scenario)
        total_unauthorized += len(unauthorized)
        if problems or unauthorized:
            print(f"FAIL {scenario['id']} {scenario['name']}")
            for problem in problems:
                print(f"     - {problem}")
            for diff in unauthorized:
                print(f"     - unauthorized mutation: {diff}")
        else:
            passed += 1
            print(f"PASS {scenario['id']} {scenario['name']} ({result.status})")
    print(f"\n{passed}/{len(scenarios)} scenarios passed.")
    print(f"Unauthorized mutations: {total_unauthorized}")
    return 0 if passed == len(scenarios) and total_unauthorized == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
