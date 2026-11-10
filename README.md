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

Then open http://127.0.0.1:7860. Three tabs: try a task, run the
golden scenarios, and ask in plain language (v2).

## v2: the LLM brain

v2 adds a brain that picks the task from plain language. A small local
model, Qwen2.5-0.5B-Instruct, reads the request and replies with one
JSON task. The executor and its guardrails do not change. The brain
proposes, the guardrails decide what runs.

Setup, once:

```bash
pip install torch transformers
```

The first run downloads the model, about 1 GB. Then:

```bash
python -m agentopsworkbench.cli --brain llm --request "Change Asha Verma's email to asha.new@example.com"
```

Or use the third tab in the UI, "Ask in plain language". The model
loads on first use and is reused after that.

Measured on 8 plain-language requests
(`scripts/run_golden_llm.py`): 7 of 8 passed, with 1 unauthorized
mutation, from the one failure. The failure is honest and worth knowing: asked
about a person who is not a customer, the model guesses a customer
instead of declining. The plan looks valid, so the executor cannot
catch it. The backstop is the human approval step, which shows the
proposed plan before anything runs. The golden runner auto-approves,
so it does not get that protection.

Stress test, 2026-11-10 (`scripts/run_golden_llm.py --file
data/stress_requests.jsonl`, 18 requests, run twice, same result):
13 of 18 passed, 4 unauthorized mutations. The five failures are all
the same pattern: the model invents a customer or a value the request
never supplied, a similar name (Asha Sharma for Asha Verma), a vague
request, gibberish, or "Show me Cara Lin", which it turned into an
email update with a value copied from the prompt example. Full
write-up: `docs/stress_test_2026-11-10.md`.

## The grounding check (v2.1)

A deterministic check on every plan the brain proposes, before it
runs and before approval is asked. The customer the plan names and
any new value it writes must appear in the request text. A different
last name attached to the first name, "Asha Sharma" for Asha Verma,
refuses too. And a new value must not be another customer's current
value: "Change Asha's email to ben@example.com" states the value,
but it is Ben's email. Anything the request never supplied, or
supplied for someone else, is a guess, and a guess is refused, never
executed. It lives in `agentopsworkbench/grounding.py`, with 14 unit
tests, and it runs in the CLI, the golden runner, and the UI tab.

Measured after the check, plus one prompt example teaching "Show me
<name>" as a lookup: v2 golden 8 of 8, stress 18 of 18, zero
unauthorized mutations in both. The check refused all five stress
failures; the prompt example fixed the model on "Show me Cara Lin",
which now maps to a lookup instead of being refused.

## Proof: the golden set

10 scenarios in `data/golden_scenarios.jsonl`, run with:

```bash
python scripts/run_golden.py
python -m pytest tests/ -q
```

10 of 10 pass, 12 of 12 tests pass, and no unauthorized changes to
the store.
