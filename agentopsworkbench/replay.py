"""Replay a saved run against a fresh store and compare outcomes.

Used by the CLI (--replay) and the UI Runs tab. Recorded approval
decisions are honored, so a run that was denied replays denied.
For LLM runs the model is greedy and deterministic, so a replay
should match.
"""
from __future__ import annotations

from .brain import LLMBrain
from .executor import run_plan
from .grounding import grounding_problems
from .policy import build_plan
from .store import CustomerStore


def replay_record(record, llm_brain=None):
    store = CustomerStore()
    decisions = [e["status"] == "approved"
                 for e in record["trace"] if e["kind"] == "approval"]

    def approver(tool_name, args):
        return decisions.pop(0) if decisions else True

    proposal_raw = None
    if record.get("request"):
        brain = llm_brain or LLMBrain()
        proposal = brain.plan(record["request"])
        proposal_raw = proposal.raw
        if not proposal.ok:
            status, after = "refused", store.snapshot()
        else:
            grounded = grounding_problems(proposal, record["request"], store)
            if grounded:
                status, after = "refused", store.snapshot()
            else:
                steps, allow_list, verify_spec = build_plan(
                    proposal.task, proposal.inputs
                )
                result = run_plan(steps, allow_list, store, approver,
                                  verify_spec=verify_spec)
                status, after = result.status, result.store_snapshot
    else:
        try:
            steps, allow_list, verify_spec = build_plan(
                record["task"], record["inputs"]
            )
        except ValueError:
            status, after = "refused", store.snapshot()
        else:
            result = run_plan(steps, allow_list, store, approver,
                              verify_spec=verify_spec)
            status, after = result.status, result.store_snapshot
    return {
        "original_status": record["status"],
        "status": status,
        "match": status == record["status"] and after == record["store_after"],
        "store_after": after,
        "proposal_raw": proposal_raw,
    }
