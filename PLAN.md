# AgentOps Workbench: Plan (Day 22)

Status 2026-11-09: v1 built and measured the same day. Deterministic
dispatcher, registry, allow-list, executor with trace log, bounded
retries (3), approval gate, read-back verifier, fake customer store,
CLI. Tests 12/12, golden set 10/10, zero unauthorized mutations.
Remaining arc: adversarial expansion, hardening, README polish, repo
push (she creates the repo), retrospective.

## Goal

Build a tool-using agent with clear boundaries, so its actions are
predictable, traceable, and safe. Announced as Day 21/60 on 2026-11-08,
with a 20-day build arc (Days 22-41).

This is her own spec, first shared 2026-10-19 as one of her three target
projects. Note: an earlier v1 proposal (2026-10-21) framed this as an
observability and cost console for agent runs. That proposal is
superseded by the Day 21 post. The guardrailed executor is v1 now.
Tracing survives inside it as the controlled-execution guardrail, and
the cost console becomes a later layer, not v1.

## Standing rules that shape this build

- Free and local only. No paid LLM API, no premium tools.
- No LLM judge anywhere. Verification is read-back checks, not model
  judgment (same rule as TrustLens).
- Demos must be live and self-verifiable, never canned or seed-data based.
- Role split: Boone builds the heavy parts. Meganaa owns design
  decisions, the golden scenarios, the README narrative, and the
  interview story. She must be able to whiteboard every design decision.
- Plain human professional language in public copy. No em-dashes.

## The one decision to confirm before scaffolding

v1 uses a deterministic dispatcher: the agent selects tools by explicit
rules (task intent plus allow-list), not by an LLM choosing freely.
Why: the guardrails are then testable. An LLM brain that picks tools
unpredictably cannot be golden-tested, and the whole point of this
build is proof. The LLM decision-maker becomes a pluggable adapter in
v2, behind the same guardrails. If she wants the LLM brain in v1
instead, the golden set changes completely, so this needs her word.

## v1 scope

- CLI first. No dashboard in v1.
- Fake customer store (in-memory dict, SQLite later) so nothing real
  is ever at risk. The demo task is the one from the post: update a
  customer record.
- Python, standard library only for the core. pytest for tests.

## Architecture (six parts)

1. Tool registry. Every tool declares name, description, argument
   schema, and side-effect class: read-only, mutating, or
   consequential. Consequential tools always need approval.
2. Task allow-list. Each task declares exactly which tools it may use.
   Anything else is refused before it is called. This is least
   privilege, and it is the headline guardrail.
3. Executor with state. A run moves through pending, running, awaiting
   approval, done, or failed. Every action and every tool result is
   written to a trace log, in the Forkwise spirit: find the first bad
   step, not the final error.
4. Bounded retries. A per-step retry budget (3 attempts, then stop).
   Retries apply only to transient tool errors. An approval denial is
   terminal and is never retried. A verification failure is never
   retried blindly.
5. Approval gate. Before any consequential tool runs, execution pauses
   and asks a human. Approve or deny, both logged. Denial ends the run
   cleanly with no mutation.
6. Verifier. After a mutating action, read the record back and compare
   it to the expected values. Mismatch means the run failed, loudly,
   never a silent success.

## Golden set (10 scenarios, the proof)

Headline metric: zero unauthorized mutations across the suite.
Secondary metric: scenario pass rate.

1. Normal update with approval: succeeds, verified by read-back.
2. Task asks for a tool outside the allow-list: refused, never called.
3. Agent asked to delete a record (consequential, not allowed):
   refused.
4. Tool fails twice transiently, succeeds on third: completes inside
   the retry budget.
5. Tool fails persistently: stops after the budget, marked failed, no
   infinite loop.
6. Human denies approval: no mutation, run ends cleanly.
7. Read-only tool: no approval asked (only consequential tools pause).
8. Verification catches a wrong write (simulated bad tool result):
   flagged failed, no silent success.
9. Retry after an approval denial: never happens, denial is terminal.
10. Every run leaves a complete trace: every action and result logged.

## 20-day arc (Days 22-41)

- Days 22-23: Scaffold, registry, allow-list. First proof: an
  unauthorized tool is refused.
- Days 24-25: Executor, state machine, trace log.
- Days 26-27: Bounded retries.
- Days 28-29: Approval gate.
- Days 30-31: Verifier (read-back checks).
- Days 32-33: End-to-end demo, the customer record update, happy path.
- Days 34-36: Adversarial golden set plus eval gate (ship or no-ship,
  TrustLens style).
- Days 37-39: Hardening, README, repo push (she creates the repo, as
  with the other projects).
- Days 40-41: Retrospective post: what the guardrails caught.

## Day 22 post angle

Not a build log. The plan itself is the post: the five guardrails,
the threat model (what goes wrong when an agent has every tool), and
the headline metric for the arc, zero unauthorized mutations. Results
start landing from Day 23.

## Files (planned)

- agentopsworkbench/registry.py (tool declarations, side-effect classes)
- agentopsworkbench/policy.py (task allow-lists)
- agentopsworkbench/executor.py (state machine, trace log, retries)
- agentopsworkbench/approval.py (human gate)
- agentopsworkbench/verify.py (read-back checks)
- agentopsworkbench/store.py (fake customer records)
- agentopsworkbench/cli.py (run a task from the command line)
- tests/ (one test file per guardrail, plus the golden set runner)
- data/golden_scenarios.jsonl
- README.md, PLAN.md (this file)
