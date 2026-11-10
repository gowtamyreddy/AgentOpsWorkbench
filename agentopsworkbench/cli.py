"""Command line: run one task against the fake customer store.

Rule brain (v1, default): name the task and its inputs.
  python -m agentopsworkbench.cli update_customer_email --customer C1001 --email asha.new@example.com
  python -m agentopsworkbench.cli lookup_customer --customer C1002
  python -m agentopsworkbench.cli update_customer_email --customer C1001 --email x@y.z --yes

LLM brain (v2): describe the request in plain language. A small local
model picks the task; the same guardrails run the plan.
  python -m agentopsworkbench.cli --brain llm --request "Change Asha Verma's email to asha.new@example.com"
  python -m agentopsworkbench.cli --brain llm --request "Look up Ben Ortiz" --yes
"""
from __future__ import annotations

import argparse
import json

from .approval import always_approve, console_approver
from .brain import LLMBrain, RuleBrain
from .executor import run_plan
from .policy import TASKS, build_plan
from .store import CustomerStore


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
    args = parser.parse_args(argv)

    store = CustomerStore()
    if args.brain == "llm":
        if not args.request:
            parser.error("--brain llm needs --request")
        brain = LLMBrain()
        proposal = brain.plan(args.request)
        print(f"Brain proposed: {proposal.raw[:300]}")
        if not proposal.ok:
            print(f"Refused: {proposal.error}")
            return 1
        steps, allow_list, verify_spec = build_plan(
            proposal.task, proposal.inputs
        )
        customer_id = proposal.inputs["customer_id"]
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
            return 1
        steps, allow_list, verify_spec = build_plan(args.task, inputs)
        customer_id = args.customer

    approver = always_approve if args.yes else console_approver
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify_spec)

    print(f"\nRun status: {result.status}")
    for entry in result.trace:
        print(f"  [{entry.kind}] {entry.tool}: {entry.status} - {entry.detail}")
    print(json.dumps(result.store_snapshot.get(customer_id), indent=2))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
