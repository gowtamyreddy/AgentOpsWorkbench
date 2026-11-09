"""Approval gates. An approver is a callable (tool_name, args) -> bool."""
from __future__ import annotations


def console_approver(tool_name, args):
    """Ask a human on the command line. The v1 interactive gate."""
    print(f"\nApproval requested: {tool_name} {args}")
    answer = input("Approve? [y/N] ").strip().lower()
    return answer in ("y", "yes")


def always_approve(tool_name, args):
    return True


def always_deny(tool_name, args):
    return False
