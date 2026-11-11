"""Read-back verification. No LLM judge: re-read the record and compare.

A verify spec is {"tool": "get_customer", "args": {...},
"expect": {"email": "..."}}. The check passes only when every expected
field matches what the store actually holds now.

When a before snapshot is given, the check is full-record: every
field of the target record must equal its before value except the
expected fields, which must equal the expected values, and every
other record must be unchanged. A tool that writes the right value
and silently changes another field fails here, even though a
field-scoped read-back would pass it. Without a before snapshot,
the check falls back to the expected fields only.
"""
from __future__ import annotations

from .tools import call_tool


def _full_record_mismatches(store, verify_spec, before):
    mismatches = []
    customer_id = verify_spec["args"].get("customer_id")
    expect = verify_spec.get("expect", {})
    after_all = store.snapshot()
    target_before = before.get(customer_id, {})
    target_after = after_all.get(customer_id, {})
    for field in set(target_before) | set(target_after):
        if field in expect:
            continue
        if target_before.get(field) != target_after.get(field):
            mismatches.append(
                f"{field}: unexpected change from "
                f"{target_before.get(field)!r} to "
                f"{target_after.get(field)!r}"
            )
    for cid in set(before) | set(after_all):
        if cid == customer_id:
            continue
        for field in set(before.get(cid, {})) | set(after_all.get(cid, {})):
            if before.get(cid, {}).get(field) != after_all.get(cid, {}).get(field):
                mismatches.append(
                    f"record {cid}: unexpected change to {field}"
                )
    return mismatches


def run_verification(store, verify_spec, before=None):
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
    if before is not None:
        mismatches.extend(_full_record_mismatches(store, verify_spec, before))
    if mismatches:
        return False, "; ".join(mismatches)
    return True, "read-back matches expected values"
