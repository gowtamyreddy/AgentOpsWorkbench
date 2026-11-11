"""Executor: runs a plan under the guardrails, keeping a full trace.

Rules, in order, for every step:
1. Unknown tool, or tool outside the allow-list: refused, run stops.
   Nothing is executed for that step.
2. Tool needs approval: the approver is asked. Denial is terminal and
   is never retried. Approval is logged.
3. Tool runs with a bounded retry budget, transient errors only.
   Exhausting the budget fails the run. No infinite loops.
4. After all steps, the verifier re-reads the record and compares it
   to the expected values, against a snapshot taken before the run.
   Every field must match its before value except the expected
   changes, and every other record must be unchanged. A mismatch
   fails the run loudly.

Run statuses: succeeded, refused, denied, failed, verification_failed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .registry import get_tool
from .tools import TransientError, ToolError, call_tool
from .verify import run_verification


@dataclass
class TraceEntry:
    kind: str  # policy, approval, tool, verify
    tool: str
    status: str
    detail: str = ""
    attempts: int = 0


@dataclass
class RunResult:
    status: str
    trace: list = field(default_factory=list)
    store_snapshot: dict = field(default_factory=dict)

    def approver_calls(self):
        return sum(1 for e in self.trace if e.kind == "approval")

    def tool_calls(self, tool_name=None):
        return sum(
            1
            for e in self.trace
            if e.kind == "tool"
            and (tool_name is None or e.tool == tool_name)
        )


def run_plan(plan, allow_list, store, approver, verify_spec=None,
             faults=None, max_retries=3):
    trace = []
    faults = {k: dict(v) for k, v in (faults or {}).items()}
    before = store.snapshot()

    for step in plan:
        tool_name = step["tool"]
        args = step.get("args", {})

        try:
            tool = get_tool(tool_name)
        except KeyError:
            trace.append(TraceEntry("policy", tool_name, "refused",
                                    "unknown tool"))
            return RunResult("refused", trace, store.snapshot())

        if tool_name not in allow_list:
            trace.append(TraceEntry("policy", tool_name, "refused",
                                    "tool not in task allow-list"))
            return RunResult("refused", trace, store.snapshot())

        if tool.needs_approval():
            approved = approver(tool_name, args)
            trace.append(TraceEntry(
                "approval", tool_name,
                "approved" if approved else "denied",
                f"approval for {tool_name}",
            ))
            if not approved:
                return RunResult("denied", trace, store.snapshot())

        attempts = 0
        while True:
            attempts += 1
            try:
                result = call_tool(store, tool_name, args, faults=faults)
                trace.append(TraceEntry("tool", tool_name, "ok",
                                        str(result)[:200], attempts))
                break
            except TransientError as exc:
                if attempts >= max_retries:
                    trace.append(TraceEntry("tool", tool_name, "failed",
                                            f"retry budget exhausted: {exc}",
                                            attempts))
                    return RunResult("failed", trace, store.snapshot())
                continue
            except (ToolError, KeyError) as exc:
                trace.append(TraceEntry("tool", tool_name, "failed",
                                        f"non-retryable: {exc}", attempts))
                return RunResult("failed", trace, store.snapshot())

    if verify_spec is not None:
        ok, detail = run_verification(store, verify_spec, before=before)
        trace.append(TraceEntry("verify", verify_spec["tool"],
                                "ok" if ok else "failed", detail))
        if not ok:
            return RunResult("verification_failed", trace, store.snapshot())

    return RunResult("succeeded", trace, store.snapshot())
