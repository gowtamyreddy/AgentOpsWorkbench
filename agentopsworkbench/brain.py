"""Brains: decide which tools to call for a plain-language request.

A brain proposes a plan. It never executes anything. The executor runs
the plan under the same guardrails as v1: allow-list, approval, bounded
retries, verification. A bad plan is refused, not executed.

- RuleBrain: the v1 deterministic dispatcher. Baseline and fallback.
  It takes a task name plus inputs, no language understanding.
- LLMBrain: a small local instruction model (Qwen2.5-0.5B-Instruct)
  prompted to output one JSON task. Free, local, no API key. The model
  is downloaded from Hugging Face on first use (about 1 GB).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .policy import TASKS
from .store import SEED

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

# Inputs each task needs, in order. The brain must supply all of them.
REQUIRED_INPUTS = {
    "update_customer_email": ["customer_id", "new_email"],
    "update_customer_address": ["customer_id", "new_address"],
    "lookup_customer": ["customer_id"],
}


@dataclass
class PlanProposal:
    """What a brain proposed, and whether it survived validation."""

    task: str | None = None
    inputs: dict = field(default_factory=dict)
    raw: str = ""
    ok: bool = False
    error: str = ""


def validate_proposal(task, inputs):
    """Check a proposed task and inputs. Returns a PlanProposal."""
    if task is None:
        return PlanProposal(raw="", ok=False,
                            error="brain declined: no matching task")
    if task not in TASKS:
        return PlanProposal(task=task, ok=False,
                            error=f"unknown task {task}")
    missing = [k for k in REQUIRED_INPUTS[task]
               if k not in inputs or not str(inputs[k]).strip()]
    if missing:
        return PlanProposal(task=task, inputs=inputs, ok=False,
                            error=f"missing inputs: {', '.join(missing)}")
    if inputs["customer_id"] not in SEED:
        return PlanProposal(task=task, inputs=inputs, ok=False,
                            error=f"unknown customer {inputs['customer_id']}")
    return PlanProposal(task=task, inputs=inputs, ok=True)


def _extract_json(text):
    """Pull the first JSON object out of model output.

    Handles a fenced code block and trailing chatter. Returns the parsed
    object, or raises ValueError.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object in model output")
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start:i + 1])
    raise ValueError("unbalanced JSON in model output")


def parse_plan_output(text):
    """Turn raw model output into a validated PlanProposal."""
    try:
        obj = _extract_json(text)
    except (ValueError, json.JSONDecodeError) as exc:
        return PlanProposal(raw=text, ok=False,
                            error=f"unparseable plan: {exc}")
    if not isinstance(obj, dict):
        return PlanProposal(raw=text, ok=False,
                            error="plan is not a JSON object")
    task = obj.get("task")
    inputs = {k: v for k, v in obj.items() if k != "task"}
    proposal = validate_proposal(task, inputs)
    proposal.raw = text
    return proposal


def build_messages(request):
    """Chat messages for the planner prompt."""
    customers = "\n".join(
        f"- {cid}: {rec['name']}, {rec['email']}"
        for cid, rec in SEED.items()
    )
    system = (
        "You are the planner for a customer-record agent. "
        "You pick exactly one task and its inputs. "
        "Reply with JSON only, no other text.\n\n"
        "Tasks:\n"
        "- update_customer_email: inputs customer_id, new_email\n"
        "- update_customer_address: inputs customer_id, new_address\n"
        "- lookup_customer: inputs customer_id\n\n"
        f"Customers:\n{customers}\n\n"
        "Rules:\n"
        "- There is no delete task. If the request asks to delete, "
        'reply {"task": null}.\n'
        "- If the person is not one of the customers above, "
        'reply {"task": null}.\n'
        "- Never invent a value the request does not state. If the "
        "request gives no new email or address, pick lookup_customer "
        "for a question, or reply {\"task\": null} for an update.\n"
        "- Do not guess. If you are not sure which customer the "
        'request means, reply {"task": null}.\n'
        "- Use the customer_id, never a name, in the inputs.\n"
        "- One task per request. If the request asks for two changes, "
        "pick the first one.\n\n"
        "Examples:\n"
        "Request: Change Asha Verma's email to asha.new@example.com\n"
        '{"task": "update_customer_email", "customer_id": "C1001", '
        '"new_email": "asha.new@example.com"}\n\n'
        "Request: Look up Ben Ortiz\n"
        '{"task": "lookup_customer", "customer_id": "C1002"}\n\n'
        "Request: What is Asha Verma's email?\n"
        '{"task": "lookup_customer", "customer_id": "C1001"}\n\n'
        "Request: Show me Cara Lin\n"
        '{"task": "lookup_customer", "customer_id": "C1003"}\n\n'
        "Request: Update the email for Zoe to zoe@example.com\n"
        '{"task": null}'
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": request},
    ]


class RuleBrain:
    """The v1 deterministic dispatcher, as a brain.

    No language understanding: the caller names the task and inputs.
    """

    def plan_task(self, task, inputs):
        proposal = validate_proposal(task, inputs)
        proposal.raw = json.dumps({"task": task, **inputs})
        return proposal


class LLMBrain:
    """A small local model plans the task from plain language.

    The model loads once, on the first plan() call, and is reused.
    Greedy decoding, so the same request always gives the same plan.
    """

    def __init__(self, model_id=MODEL_ID):
        self.model_id = model_id
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id, torch_dtype="auto",
        )
        self._model.eval()
        self._torch = torch

    def plan(self, request, max_new_tokens=150):
        self._load()
        messages = build_messages(request)
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        inputs = self._tokenizer(prompt, return_tensors="pt")
        with self._torch.no_grad():
            out = self._model.generate(
                **inputs, max_new_tokens=max_new_tokens, do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        text = self._tokenizer.decode(
            out[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )
        return parse_plan_output(text)
