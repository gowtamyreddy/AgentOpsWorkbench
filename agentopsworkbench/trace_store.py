"""Run records: every interactive run saves its trace to runs/.

A record is one JSON file per run: where it ran, what was asked,
the plan, the grounding result, the status, the full trace, and the
store before and after. A failure can be replayed later instead of
being reconstructed from memory. Batch runners (golden, stress,
adversarial) print their results and do not save records.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path


def runs_dir(base=None):
    root = Path(base) if base else Path(__file__).resolve().parents[1]
    directory = root / "runs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def new_run_id():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(3)}"


def build_record(*, source, brain, request=None, task=None, inputs=None,
                 plan=None, grounding_problems=None, refusal_reason=None,
                 status=None, trace=None, store_before=None,
                 store_after=None):
    return {
        "source": source,
        "brain": brain,
        "request": request,
        "task": task,
        "inputs": inputs or {},
        "plan": plan or [],
        "grounding_problems": grounding_problems or [],
        "refusal_reason": refusal_reason,
        "status": status,
        "trace": [
            {"kind": e.kind, "tool": e.tool, "status": e.status,
             "detail": e.detail, "attempts": e.attempts}
            for e in (trace or [])
        ],
        "store_before": store_before or {},
        "store_after": store_after or {},
    }


def save_run(record, base=None):
    record.setdefault("run_id", new_run_id())
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    path = runs_dir(base) / f"run-{record['run_id']}.json"
    path.write_text(json.dumps(record, indent=2))
    return path


def list_runs(base=None):
    return sorted(runs_dir(base).glob("run-*.json"))


def summarize(record):
    task = record.get("task") or (record.get("request") or "")[:60]
    return {
        "run_id": record.get("run_id"),
        "timestamp": record.get("timestamp"),
        "source": record.get("source"),
        "brain": record.get("brain"),
        "task": task,
        "status": record.get("status"),
    }


def list_run_summaries(base=None):
    summaries = [summarize(json.loads(p.read_text()))
                 for p in list_runs(base)]
    return sorted(summaries, key=lambda s: s["timestamp"] or "",
                  reverse=True)


def load_run(run_id, base=None):
    directory = runs_dir(base)
    path = directory / f"run-{run_id}.json"
    if not path.exists():
        matches = sorted(directory.glob(f"run-{run_id}*.json"))
        if not matches:
            raise FileNotFoundError(f"no saved run {run_id}")
        path = matches[0]
    return json.loads(path.read_text())
