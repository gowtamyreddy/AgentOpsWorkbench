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
from agentopsworkbench.policy import TASKS, build_plan
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
    approver = always_approve if approve else always_deny
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify_spec)
    record = result.store_snapshot.get(customer_id)
    return result.status, format_trace(result), json.dumps(record, indent=2)


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
    if not proposal.ok:
        return "refused", plan_text, "", ""
    steps, allow_list, verify_spec = build_plan(
        proposal.task, proposal.inputs
    )
    store = CustomerStore()
    approver = always_approve if approve else always_deny
    result = run_plan(steps, allow_list, store, approver,
                      verify_spec=verify_spec)
    record = result.store_snapshot.get(proposal.inputs["customer_id"])
    return (result.status, plan_text, format_trace(result),
            json.dumps(record, indent=2))


with gr.Blocks(title="AgentOps Workbench") as demo:
    gr.Markdown("# AgentOps Workbench: test UI")
    gr.Markdown(
        "Same guardrailed executor as the CLI. Fake customer store, "
        "in-memory: every run starts from the seed data again, "
        "so nothing persists."
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


if __name__ == "__main__":
    demo.launch()
