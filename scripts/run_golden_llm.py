"""v2 golden set runner: plain-language requests through the LLM brain.

The model loads once and is reused for all cases. Each case measures
two things: did the brain produce a valid plan, and did the run end in
the expected status with the expected store? A bad plan must be
refused, never executed. Exit code 0 only if every case passes and
there are zero unauthorized mutations.

Usage:
  python scripts/run_golden_llm.py [--file data/stress_requests.jsonl]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentopsworkbench.approval import always_approve
from agentopsworkbench.brain import LLMBrain
from agentopsworkbench.executor import run_plan
from agentopsworkbench.grounding import grounding_problems
from agentopsworkbench.policy import build_plan
from agentopsworkbench.store import CustomerStore
from run_golden import expected_diffs, store_diffs


def run_case(brain, case):
    store = CustomerStore()
    before = store.snapshot()
    proposal = brain.plan(case["request"])
    grounded = grounding_problems(proposal, case["request"], store)
    if not proposal.ok:
        status = "refused"
        result = None
        detail = proposal.error
    elif grounded:
        status = "refused"
        result = None
        detail = "; ".join(grounded)
    else:
        steps, allow_list, verify_spec = build_plan(
            proposal.task, proposal.inputs
        )
        result = run_plan(steps, allow_list, store, always_approve,
                          verify_spec=verify_spec)
        status = result.status
        detail = ""
    problems = []
    if status != case["expected_status"]:
        problems.append(f"status {status} != {case['expected_status']}")
    after = store.snapshot()
    expect = case.get("expect_store", {})
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
    return status, proposal, detail, problems, unauthorized


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/golden_requests.jsonl")
    parser.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / args.file
    cases = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    print(f"Model: {args.model}")
    brain = LLMBrain(args.model)
    passed = 0
    plans_valid = 0
    total_unauthorized = 0
    by_category = {}
    total_seconds = 0.0
    for case in cases:
        started = time.monotonic()
        status, proposal, detail, problems, unauthorized = run_case(brain, case)
        seconds = time.monotonic() - started
        total_seconds += seconds
        cat = case.get("category", "uncategorized")
        got, want = by_category.get(cat, (0, 0))
        by_category[cat] = (got, want + 1)
        if proposal.ok:
            plans_valid += 1
        total_unauthorized += len(unauthorized)
        if problems or unauthorized:
            print(f"FAIL {case['id']} {case['request']} ({seconds:.1f}s)")
            print(f"     plan: {proposal.task or '-'} ok={proposal.ok} "
                  f"raw={proposal.raw[:120]!r}")
            for problem in problems:
                print(f"     - {problem}")
            for diff in unauthorized:
                print(f"     - unauthorized mutation: {diff}")
        else:
            passed += 1
            got, want = by_category[cat]
            by_category[cat] = (got + 1, want)
            print(f"PASS {case['id']} ({status}) plan={proposal.task} "
                  f"({seconds:.1f}s)")
    print(f"\n{passed}/{len(cases)} requests passed.")
    print(f"Plans valid: {plans_valid}/{len(cases)}")
    print(f"Unauthorized mutations: {total_unauthorized}")
    print(f"Total time: {total_seconds:.1f}s "
          f"(avg {total_seconds / max(len(cases), 1):.1f}s per request)")
    for cat in sorted(by_category):
        got, want = by_category[cat]
        print(f"  {cat}: {got}/{want}")
    return 0 if passed == len(cases) and total_unauthorized == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
