"""Command line: run one task against the fake customer store.

Rule brain (v1, default): name the task and its inputs.
  python -m agentopsworkbench.cli update_customer_email --customer C1001 --email asha.new@example.com
  python -m agentopsworkbench.cli lookup_customer --customer C1002
  python -m agentopsworkbench.cli update_customer_email --customer C1001 --email x@y.z --yes

LLM brain (v2): describe the request in plain language. A small local
model picks the task; the same guardrails run the plan.
  python -m agentopsworkbench.cli --brain llm --request "Change Asha Verma's email to asha.new@example.com"
  python -m agentopsworkbench.cli --brain llm --request "Look up Ben Ortiz" --yes

Every run saves its trace to runs/run-<id>.json. Replay one with:
  python -m agentopsworkbench.cli --replay <run-id>
"""
from __future__ import annotations

import argparse
import json

from .approval import always_approve, console_approver
from .brain import LLMBrain, RuleBrain
from .executor import run_plan
from .grounding import grounding_problems
from .policy import TASKS, build_plan
from .replay import replay_record
from .store import CustomerStore
from .trace_store import build_record, load_run, save_run


def replay(run_id, base=None):
    """Re-run a saved run against a fresh store and compare outcomes."""
    try:
        record = load_run(run_id, base=base)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    result = replay_record(record)
    if result["proposal_raw"]:
        print(f"Brain proposed: {result['proposal_raw'][:300]}")
    print(f"Original: {result['original_status']} (run {record.get('run_id')})")
    print(f"Replay:   {result['status']}")
    print("MATCH" if result["match"]
          else "DIFF: replay outcome differs from the saved run")
    return 0 if result["match"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agentops")
    parser.add_argument("task", nargs="?", choices=sorted(TASKS))
    parser.add_argument("--customer")
    parser.add_argument("--email")
    parser.add_argument("--address")
    parser.add_argument("--yes", action="store_true",
                        help="auto-approve (demo and scripts only)")
    parser.add_argument("--brain", choices=["rule", "llm"], default="rule")
    parser.add_argument("--request",
                        help="plain-language request (LLM brain only)")
    parser.add_argument("--replay", help="re-run a saved run by id")
    args = parser.parse_args(argv)

    if args.replay:
        return replay(args.replay)

    store = CustomerStore()
    before = store.snapshot()

    def save_refused(**fields):
        path = save_run(build_record(
            source="cli", brain=args.brain, store_before=before,
            store_after=before, status="refused", **fields))
        print(f"Run saved: {path}")
        return 1

    if args.brain == "llm":
        if not args.request:
            parser.error("--brain llm needs --request")
        brain = LLMBrain()
        proposal = brain.plan(args.request)
        print(f"Brain proposed: {proposal.raw[:300]}")
        if not proposal.ok:
            print(f"Refused: {proposal.error}")
            return save_refused(request=args.request,
                                refusal_reason=proposal.error)
        grounded = grounding_problems(proposal, args.request, store)
        if grounded:
            print(f"Refused (not grounded): {'; '.join(grounded)}")
            return save_refused(request=args.request,
                                grounding_problems=grounded,
                                refusal_reason="; ".join(grounded))
        steps, allow_list, verify_spec = build_plan(
            proposal.task, proposal.inputs
        )
        customer_id = proposal.inputs["customer_id"]
        task_name, inputs = proposal.task, proposal.inputs
    else:
        if not args.task or not args.customer:
            parser.error("rule brain needs a task and --customer")
        inputs = {"customer_id": args.customer}
        if args.email:
            inputs["new_email"] = args.email
        if args.address:
            inputs["new_address"] = args.address
        proposal = RuleBrain().plan_task(args.task, inputs)
        if not proposal.ok:
            print(f"Refused: {proposal.error}")
            return save_refused(task=args.task, inputs=inputs,
                                refusal_reason=proposal.error)
        steps, allow_list, verify_spec = build_plan(args.task, inputs)
        customer_id = args.customer
        task_name = args.task

    approver = always_approve if args.yes else console_approver
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify_spec)
    path = save_run(build_record(
        source="cli", brain=args.brain, request=args.request,
        task=task_name, inputs=inputs, plan=steps,
        status=result.status, trace=result.trace,
        store_before=before, store_after=result.store_snapshot))

    print(f"\nRun status: {result.status}")
    for entry in result.trace:
        print(f"  [{entry.kind}] {entry.tool}: {entry.status} - {entry.detail}")
    print(json.dumps(result.store_snapshot.get(customer_id), indent=2))
    print(f"Run saved: {path}")
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
