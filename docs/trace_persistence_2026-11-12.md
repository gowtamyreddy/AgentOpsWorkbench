# Trace persistence and replay (2026-11-12)

Every run from the CLI or the UI now saves one JSON record to
`runs/run-<id>.json`: source, brain, request or task, inputs, plan,
grounding problems, refusal reason, status, full trace, and the
store before and after. Refused runs are recorded too, with the
reason, so a refusal can be debugged later. Batch runners (golden,
stress, adversarial) print their results and do not save records.

Replay (`python -m agentopsworkbench.cli --replay <run-id>`) re-runs
the same plan or request against a fresh store and reports MATCH or
DIFF against the saved status and store. Recorded approval
decisions are honored, so a denied run replays denied. For LLM
runs the model is greedy and deterministic, so a replay should
match.

Files: `agentopsworkbench/trace_store.py` (save/load/list),
`agentopsworkbench/cli.py` (recording + replay), `app.py` (recording
in both tabs, run id shown in the trace). `runs/` is gitignored.

Verified 2026-11-12: tests 48/48 (6 new: save/load round-trip,
list, missing run, replay of a succeeded run, replay of a denied
run, replay of a refused record). Live check: a rule run saved and
replayed MATCH; a collision refusal saved its record. v1 golden
10/10, adversarial 4/4, gate SHIP, zero unauthorized mutations.

Runs tab (2026-11-12): a fourth UI tab lists the saved runs
(newest first), shows the full record for one, and replays it from
the browser, reusing the tab-3 model instance when it is loaded.
Verified live: UI answers HTTP 200, all four tabs and all six
buttons present in the served config; the tab's list, show, and
replay functions run against the real runs/ directory, and an LLM
refusal replays refused/MATCH. Tests 51/51 (3 new: summaries
newest-first, replay_record on a succeeded run, replay_record on a
denied run).
