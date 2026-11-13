# Bigger model: Qwen2.5-1.5B-Instruct (2026-11-13)

Question: does a bigger brain plan better, or just invent more?
The 1.5B model ran the same two sets the 0.5B runs, with the same
grounding checks on. The 0.5B numbers below are a same-code
baseline re-run in the sandbox on 2026-11-13; the 1.5B numbers are
from a MacBook Air the same day. The machines differ, so the speed
gap is indicative, not a controlled benchmark.

## Results

| Set | 0.5B (sandbox) | 1.5B (Mac) |
| --- | --- | --- |
| Golden (8) | 8/8, plans valid 7/8, 0 mutations, avg 14.8s | 8/8, plans valid 6/8, 0 mutations, avg 75.7s |
| Stress (18) | 18/18, plans valid 12/18, 0 mutations, avg 11.5s | 17/18, plans valid 10/18, 0 mutations, avg 129.3s |

## The one miss

S05, "What is Ben's address?" The 1.5B planned an address update
with new_address "123 Main St", a value the request never states.
The grounding check refused it (the value is not in the request),
so there was no mutation, but the case expected a lookup, so it
failed. The prompt had an email-question example ("What is Asha
Verma's email?" is a lookup) and a "Show me" example, but no
address-question example. The model saw "address" and reached for
the update task.

This is a prompt gap, not a size problem: the 0.5B answers S05
correctly. One example was added to the prompt ("What is Cara
Lin's address?" is a lookup), using a different person than the
test case so it teaches the pattern instead of memorizing the
answer. Re-measured on the 0.5B after the fix: golden 8/8, stress
18/18, zero unauthorized mutations, tests 51/51.

Note on the re-run: the first 1.5B re-run on the Mac (2026-11-13,
13:57) still failed S05 identically, 17/18, because the fix had
not been pushed yet and the Mac was still running the old prompt.
That run also came in faster (avg 46.4 s per request, total
834.6 s, vs 129.3 s and 2,327.8 s the first time), for no recorded
reason; the machines and load differed. The fix was pushed after
that run; the 1.5B re-run with the fix is still to confirm.

## Verdict

The bigger model is not better here: same golden, one worse on
stress, 5 to 11 times slower per request. The 0.5B stays the
default brain. The model is selectable (`--model` in the CLI and
the golden runner, a dropdown in the UI tab), and run records store
which model produced them, so a replay uses the same model.

## Note on the run

The 1.5B download in the sandbox was declined, so the experiment
ran on a MacBook Air instead: `git pull`, then
`scripts/run_golden_llm.py --model Qwen/Qwen2.5-1.5B-Instruct`
and the same with `--file data/stress_requests.jsonl`. First run
downloads about 3 GB. The 1.5B stress set took 2,327.8 s, about
39 minutes.
