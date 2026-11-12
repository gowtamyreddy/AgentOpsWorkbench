"""Gradio UI for testing AgentOps Workbench v1.

This is a thin front end over the same executor, store, and guardrails
as the CLI. Nothing here re-implements the agent.

The store is fake and in-memory: every run starts from the seed
customers again, so no change ever persists.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import gradio as gr

from agentopsworkbench.approval import always_approve, always_deny
from agentopsworkbench.brain import LLMBrain
from agentopsworkbench.executor import run_plan
from agentopsworkbench.grounding import grounding_problems
from agentopsworkbench.policy import TASKS, build_plan
from agentopsworkbench.replay import replay_record
from agentopsworkbench.trace_store import (
    build_record, list_run_summaries, load_run, save_run,
)
from agentopsworkbench.store import SEED, CustomerStore

ROOT = Path(__file__).resolve().parent

CUSTOMERS = [(f"{cid} - {rec['name']}", cid) for cid, rec in SEED.items()]


def format_trace(result):
    lines = []
    for entry in result.trace:
        line = f"[{entry.kind}] {entry.tool}: {entry.status}"
        if entry.detail:
            line += f" - {entry.detail}"
        if entry.attempts:
            line += f" (attempts: {entry.attempts})"
        lines.append(line)
    return "\n".join(lines)


def run_task(task, customer_id, new_email, new_address, approve):
    inputs = {"customer_id": customer_id}
    if task == "update_customer_email":
        if not new_email.strip():
            return "needs input", "Enter a new email first.", ""
        inputs["new_email"] = new_email.strip()
    if task == "update_customer_address":
        if not new_address.strip():
            return "needs input", "Enter a new address first.", ""
        inputs["new_address"] = new_address.strip()
    try:
        steps, allow_list, verify_spec = build_plan(task, inputs)
    except ValueError as exc:
        return "error", str(exc), ""
    store = CustomerStore()
    before = store.snapshot()
    approver = always_approve if approve else always_deny
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify_spec)
    path = save_run(build_record(
        source="ui", brain="rule", task=task, inputs=inputs, plan=steps,
        status=result.status, trace=result.trace,
        store_before=before, store_after=result.store_snapshot))
    record = result.store_snapshot.get(customer_id)
    return (result.status, format_trace(result) + f"\nrun saved: {path}",
            json.dumps(record, indent=2))


def run_golden():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_golden.py")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    out = proc.stdout + proc.stderr
    out += f"\nExit code: {proc.returncode} (0 means all green)"
    return out


_llm_brain = None


def run_request(request, approve):
    """Plain-language request through the LLM brain (v2)."""
    global _llm_brain
    if not request.strip():
        return "needs input", "", "", ""
    if _llm_brain is None:
        _llm_brain = LLMBrain()
    proposal = _llm_brain.plan(request)
    plan_text = json.dumps(
        {"task": proposal.task, **proposal.inputs}, indent=2
    ) if proposal.ok else f"no plan: {proposal.error}"
    store = CustomerStore()
    before = store.snapshot()
    if not proposal.ok:
        path = save_run(build_record(
            source="ui", brain="llm", request=request,
            refusal_reason=proposal.error, status="refused",
            store_before=before, store_after=before))
        return "refused", plan_text + f"\nrun saved: {path}", "", ""
    grounded = grounding_problems(proposal, request, store)
    if grounded:
        path = save_run(build_record(
            source="ui", brain="llm", request=request,
            grounding_problems=grounded,
            refusal_reason="; ".join(grounded), status="refused",
            store_before=before, store_after=before))
        return ("refused",
                plan_text + "\n\nNot grounded: " + "; ".join(grounded)
                + f"\nrun saved: {path}",
                "", "")
    steps, allow_list, verify_spec = build_plan(
        proposal.task, proposal.inputs
    )
    approver = always_approve if approve else always_deny
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify_spec)
    path = save_run(build_record(
        source="ui", brain="llm", request=request,
        task=proposal.task, inputs=proposal.inputs, plan=steps,
        status=result.status, trace=result.trace,
        store_before=before, store_after=result.store_snapshot))
    record = result.store_snapshot.get(proposal.inputs["customer_id"])
    return (result.status, plan_text,
            format_trace(result) + f"\nrun saved: {path}",
            json.dumps(record, indent=2))


def run_choices():
    return [(f"{s['timestamp']} | {s['status']} | {s['task']}",
             s["run_id"]) for s in list_run_summaries()]


def refresh_runs():
    return gr.update(choices=run_choices())


def show_run(run_id):
    if not run_id:
        return "Pick a run first."
    return json.dumps(load_run(run_id), indent=2)


def replay_run_ui(run_id):
    global _llm_brain
    if not run_id:
        return "Pick a run first."
    record = load_run(run_id)
    if record.get("request") and _llm_brain is None:
        _llm_brain = LLMBrain()
    result = replay_record(record, llm_brain=_llm_brain)
    lines = [
        f"Original: {result['original_status']}",
        f"Replay:   {result['status']}",
        "MATCH" if result["match"]
        else "DIFF: replay outcome differs from the saved run",
    ]
    return "\n".join(lines)


with gr.Blocks(title="AgentOps Workbench") as demo:
    gr.Markdown("# AgentOps Workbench: test UI")
    gr.Markdown(
        "Same guardrailed executor as the CLI. Fake customer store, "
        "in-memory: every run starts from the seed data again, "
        "so the store never keeps a change. Run records are saved "
        "to runs/ and listed in the Runs tab."
    )

    with gr.Tab("Try a task"):
        task = gr.Dropdown(
            choices=sorted(TASKS), value="update_customer_email",
            label="Task",
        )
        customer = gr.Dropdown(
            choices=CUSTOMERS, value="C1001", label="Customer",
        )
        new_email = gr.Textbox(
            label="New email", value="asha.new@example.com",
        )
        new_address = gr.Textbox(
            label="New address", value="99 Birch Ln, Sunnyvale, CA",
        )
        approve = gr.Checkbox(
            label="Human approval: approve this update",
            value=True,
        )
        run_btn = gr.Button("Run task", variant="primary")
        status = gr.Textbox(label="Run status")
        trace = gr.Textbox(label="Trace log", lines=10)
        record = gr.Textbox(label="Customer record after the run", lines=8)
        run_btn.click(
            run_task,
            inputs=[task, customer, new_email, new_address, approve],
            outputs=[status, trace, record],
        )
        gr.Markdown(
            "Try it twice: once with approval on, once with it off. "
            "Approved, the record changes and the read-back check passes. "
            "Denied, the run ends cleanly and the record stays as it was."
        )

    with gr.Tab("Golden scenarios"):
        gr.Markdown(
            "Runs the real `scripts/run_golden.py`: 10 scenarios, "
            "zero unauthorized mutations is the bar."
        )
        golden_btn = gr.Button("Run all 10 scenarios", variant="primary")
        golden_out = gr.Textbox(label="Results", lines=14)
        golden_btn.click(run_golden, outputs=golden_out)

    with gr.Tab("Ask in plain language (v2)"):
        gr.Markdown(
            "A small local model (Qwen2.5-0.5B-Instruct) picks the task. "
            "The same guardrails run the plan. First run downloads the "
            "model (about 1 GB) and takes a while; later runs reuse it."
        )
        request = gr.Textbox(
            label="Request",
            value="Change Asha Verma's email to asha.new@example.com",
        )
        approve_llm = gr.Checkbox(
            label="Human approval: approve this update",
            value=True,
        )
        ask_btn = gr.Button("Run request", variant="primary")
        status_llm = gr.Textbox(label="Run status")
        plan_llm = gr.Textbox(label="Plan the model proposed", lines=5)
        trace_llm = gr.Textbox(label="Trace log", lines=10)
        record_llm = gr.Textbox(label="Customer record after the run",
                                lines=8)
        ask_btn.click(
            run_request,
            inputs=[request, approve_llm],
            outputs=[status_llm, plan_llm, trace_llm, record_llm],
        )

    with gr.Tab("Runs"):
        gr.Markdown(
            "Every run from the command line or the UI saves its trace "
            "to runs/run-<id>.json. Pick one to see the full record, "
            "or replay it against a fresh store."
        )
        run_picker = gr.Dropdown(choices=run_choices(),
                                 label="Saved runs")
        refresh_btn = gr.Button("Refresh list")
        show_btn = gr.Button("Show record")
        replay_btn = gr.Button("Replay run", variant="primary")
        run_detail = gr.Textbox(label="Record", lines=20)
        replay_out = gr.Textbox(label="Replay result", lines=5)
        refresh_btn.click(refresh_runs, outputs=run_picker)
        show_btn.click(show_run, inputs=run_picker,
                       outputs=run_detail)
        replay_btn.click(replay_run_ui, inputs=run_picker,
                         outputs=replay_out)


if __name__ == "__main__":
    demo.launch()
