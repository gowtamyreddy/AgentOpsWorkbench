# AgentOps Workbench

A tool-using agent with clear boundaries, so its actions are
predictable, traceable, and safe.

v1 is a deterministic dispatcher (rules pick the tools, not an LLM),
a tool registry with side-effect classes, task allow-lists, an
executor with a trace log and bounded retries, a human approval gate,
and read-back verification. No LLM judge, no paid APIs, standard
library only.

## The five guardrails

1. Limited tools: each task declares exactly which tools it may use.
   Anything else is refused before it is called.
2. Controlled execution: every action and result is written to a trace
   log, with run state (pending, running, awaiting approval, done,
   failed).
3. Bounded retries: 3 attempts per step, transient errors only. An
   approval denial is terminal and is never retried.
4. Human approval: write and consequential tools pause for a human.
   Read-only tools never ask.
5. Verification: after a mutation, the record is read back and compared
   to the expected values. A mismatch fails the run loudly.

## Run it

```bash
python -m agentopsworkbench.cli update_customer_email --customer C1001 --email asha.new@example.com
python -m agentopsworkbench.cli lookup_customer --customer C1002
```

Add `--yes` to auto-approve (demo and scripts only).

## Proof: the golden set

10 scenarios in `data/golden_scenarios.jsonl`, run with:

```bash
python scripts/run_golden.py
python -m pytest tests/ -q
```

Headline metric: zero unauthorized mutations across the suite.
