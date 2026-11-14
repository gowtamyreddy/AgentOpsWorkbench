# Persistent store, 2026-11-14

## What changed

The customer store is now persisted to `store.json` in the project
root. An approved update sticks between runs, in the CLI and in the
UI. Before this, every run started from the three seed customers
again, so no change ever survived a run.

## The one rule

The executor saves the store only after a run whose verification
passed. A refused, denied, failed, or verification-failed run
never writes the file. Only verified state persists.

This matters because the adversarial set already proved a tool
can write the wrong value while reporting success. If the store
saved on every write, that wrong value would land in the file
before verification ever ran. Saving behind verification keeps
the guardrail as the gate, not an afterthought.

## What did not change

Golden runs, stress runs, the adversarial set, and replays still
use an in-memory store (`CustomerStore()` with no path), so they
stay isolated and deterministic. The persistent store is used
only by the interactive paths: the CLI and the UI.

## How it works

- `agentopsworkbench/store.py`: `CustomerStore(path=...)` loads
  the JSON file when it exists, seeds and saves it on first use.
  `save()` writes the file (a no-op for in-memory stores),
  `reset()` restores the seed data, `load_store(path=None)` loads
  the project-root `store.json` by default.
- `agentopsworkbench/executor.py`: `run_plan` calls `store.save()`
  after a run whose verification passed, and returns before that
  call on every other outcome.
- `agentopsworkbench/cli.py`: uses the persistent store by
  default. `--fresh` resets it to the seed data first, `--store`
  points at another file.
- `app.py`: one shared persistent store for the whole session.
  The first and third tabs show the current customers, and the
  first tab has a Reset button.
- `store.json` is in `.gitignore`, like `runs/`. It is runtime
  state, not source.

## Verification (2026-11-14, sandbox)

- Tests: 59/59 (8 new persistence tests). The key ones: a denied
  run leaves the file untouched, a verification-failed run
  (write-wrong fault) leaves the file untouched, and an in-memory
  store never writes a file.
- v1 golden: 10/10, zero unauthorized mutations.
- Adversarial set: 4/4, eval gate SHIP, zero mutations.
- v2 golden (0.5B): 8/8, zero mutations.
- CLI smoke test: an email update in one process was still there
  in a second process, and `--fresh` restored the seed data.
- UI: answers HTTP 200, all four tabs present, the Current
  customers box and the Reset button present, header text updated.
