# AgentOps Workbench

An agent that can use tools, with clear limits on what it is allowed
to do.

v1 picks tools by rules, not by an LLM. Each task lists the tools it
may use, and anything else gets refused before it runs. Every step is
logged. Retries stop after 3 tries. Writes pause for a human to
approve. After a write, the record is read back and checked. No LLM
judge, no paid APIs, standard library only.

## The five guardrails

1. Limited tools. Each task declares the tools it may use. Anything
   else is refused before it is called.
2. Controlled execution. Every action and result goes into a trace log.
3. Bounded retries. 3 attempts per step, transient errors only. A
   denied approval ends the run and is never retried.
4. Human approval. Write and consequential tools pause for a human.
   Read-only tools never ask.
5. Verification. After a change, the record is read back and compared
   to what was expected. A mismatch fails the run loudly.

## Run it

```bash
python -m agentopsworkbench.cli update_customer_email --customer C1001 --email asha.new@example.com
python -m agentopsworkbench.cli lookup_customer --customer C1002
```

Add `--yes` to auto-approve (demo and scripts only).

## Try it in the browser

```bash
pip install gradio
python app.py
```

Then open http://127.0.0.1:7860. Two tabs: try a task, and run the
golden scenarios.

## Proof: the golden set

10 scenarios in `data/golden_scenarios.jsonl`, run with:

```bash
python scripts/run_golden.py
python -m pytest tests/ -q
```

10 of 10 pass, 12 of 12 tests pass, and no unauthorized changes to
the store.
