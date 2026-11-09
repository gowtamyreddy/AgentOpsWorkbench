"""Read-back verification. No LLM judge: re-read the record and compare.

A verify spec is {"tool": "get_customer", "args": {...},
"expect": {"email": "..."}}. The check passes only when every expected
field matches what the store actually holds now.
"""
from __future__ import annotations

from .tools import call_tool


def run_verification(store, verify_spec):
    try:
        record = call_tool(store, verify_spec["tool"], verify_spec["args"])
    except Exception as exc:  # noqa: BLE001 - verification must not crash
        return False, f"verification read failed: {exc}"
    if record is None:
        return False, "verification read returned nothing"
    mismatches = [
        f"{field}: expected {expected!r}, found {record.get(field)!r}"
        for field, expected in verify_spec.get("expect", {}).items()
        if record.get(field) != expected
    ]
    if mismatches:
        return False, "; ".join(mismatches)
    return True, "read-back matches expected values"
