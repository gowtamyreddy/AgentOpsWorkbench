"""Tool implementations plus the fault-injection hooks used by tests.

Faults simulate the real world for the golden set, and are labelled as
simulated wherever they appear:
- {"fail_times": n}: the tool raises TransientError n times, then works.
- {"write_wrong": value}: an update tool writes the wrong value while
  reporting success, so the verifier has something real to catch.
- {"write_target": customer_id}: an update tool writes to a different
  customer than the plan names, so the verifier must catch a
  wrong-target write.
- {"write_extra": {field: value}}: an update tool writes the right
  value and silently changes another field, so the verifier's
  field-scoped read-back has something to miss.
"""
from __future__ import annotations


class TransientError(Exception):
    """A retryable tool failure (network blip, lock, timeout)."""


class ToolError(Exception):
    """A non-retryable tool failure (bad id, bad args)."""


def _consume_fault(faults, tool_name):
    """Return and decrement the fault entry for a tool, if any."""
    if not faults:
        return {}
    entry = faults.get(tool_name)
    if not entry:
        return {}
    entry = dict(entry)
    if entry.get("fail_times", 0) > 0:
        entry["fail_times"] -= 1
        faults[tool_name] = entry
        raise TransientError(f"{tool_name} failed transiently")
    return entry


def get_customer(store, args, faults=None):
    _consume_fault(faults, "get_customer")
    record = store.get(args["customer_id"])
    if record is None:
        raise ToolError(f"unknown customer {args['customer_id']}")
    return record


def search_customers(store, args, faults=None):
    _consume_fault(faults, "search_customers")
    return store.search(args["query"])


def update_customer_email(store, args, faults=None):
    entry = _consume_fault(faults, "update_customer_email")
    value = entry.get("write_wrong", args["new_email"])
    target = entry.get("write_target", args["customer_id"])
    extra = entry.get("write_extra", {})
    return store.update(target, email=value, **extra)


def update_customer_address(store, args, faults=None):
    entry = _consume_fault(faults, "update_customer_address")
    value = entry.get("write_wrong", args["new_address"])
    target = entry.get("write_target", args["customer_id"])
    extra = entry.get("write_extra", {})
    return store.update(target, address=value, **extra)


def delete_customer(store, args, faults=None):
    _consume_fault(faults, "delete_customer")
    store.delete(args["customer_id"])
    return {"deleted": args["customer_id"]}


TOOL_FUNCS = {
    "get_customer": get_customer,
    "search_customers": search_customers,
    "update_customer_email": update_customer_email,
    "update_customer_address": update_customer_address,
    "delete_customer": delete_customer,
}


def call_tool(store, tool_name, args, faults=None):
    func = TOOL_FUNCS.get(tool_name)
    if func is None:
        raise ToolError(f"unknown tool {tool_name}")
    return func(store, args, faults=faults)
