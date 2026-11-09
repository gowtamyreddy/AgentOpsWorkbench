"""Tool registry. Every tool declares its side-effect class up front.

Side-effect classes:
- read: no mutation, never needs approval.
- write: reversible mutation, needs approval.
- consequential: destructive or irreversible, always needs approval.
"""
from __future__ import annotations

from dataclasses import dataclass

READ = "read"
WRITE = "write"
CONSEQUENTIAL = "consequential"

APPROVAL_REQUIRED = frozenset({WRITE, CONSEQUENTIAL})


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    side_effect: str
    args: tuple = ()

    def needs_approval(self):
        return self.side_effect in APPROVAL_REQUIRED


REGISTRY = {
    "get_customer": Tool(
        "get_customer", "Read one customer record by id.", READ, ("customer_id",)
    ),
    "search_customers": Tool(
        "search_customers", "Search customers by name or email.", READ, ("query",)
    ),
    "update_customer_email": Tool(
        "update_customer_email",
        "Change a customer email address.",
        WRITE,
        ("customer_id", "new_email"),
    ),
    "update_customer_address": Tool(
        "update_customer_address",
        "Change a customer mailing address.",
        WRITE,
        ("customer_id", "new_address"),
    ),
    "delete_customer": Tool(
        "delete_customer",
        "Permanently delete a customer record.",
        CONSEQUENTIAL,
        ("customer_id",),
    ),
}


def get_tool(name):
    return REGISTRY[name]
