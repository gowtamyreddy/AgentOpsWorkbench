"""Command line: run one task against the fake customer store.

Examples:
  python -m agentopsworkbench.cli update_customer_email --customer C1001 --email asha.new@example.com
  python -m agentopsworkbench.cli lookup_customer --customer C1002
  python -m agentopsworkbench.cli update_customer_email --customer C1001 --email x@y.z --yes
"""
from __future__ import annotations

import argparse
import json

from .approval import always_approve, console_approver
from .executor import run_plan
from .policy import TASKS, build_plan
from .store import CustomerStore


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agentops")
    parser.add_argument("task", choices=sorted(TASKS))
    parser.add_argument("--customer", required=True)
    parser.add_argument("--email")
    parser.add_argument("--address")
    parser.add_argument("--yes", action="store_true",
                        help="auto-approve (demo and scripts only)")
    args = parser.parse_args(argv)

    inputs = {"customer_id": args.customer}
    if args.email:
        inputs["new_email"] = args.email
    if args.address:
        inputs["new_address"] = args.address

    store = CustomerStore()
    steps, allow_list, verify_spec = build_plan(args.task, inputs)
    approver = always_approve if args.yes else console_approver
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify_spec)

    print(f"\nRun status: {result.status}")
    for entry in result.trace:
        print(f"  [{entry.kind}] {entry.tool}: {entry.status} - {entry.detail}")
    print(json.dumps(result.store_snapshot.get(args.customer), indent=2))
    return 0 if result.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
