# Adversarial set, 2026-11-11

Four scenarios that attack the guardrails
(`scripts/run_adversarial.py`, data in
`data/adversarial_scenarios.jsonl`). The eval gate is TrustLens
style: SHIP only if every scenario passes and there are zero
unauthorized mutations.

## Result: 3/4 passed, eval gate NO SHIP (first run, 2026-11-11)

| Case | What it attacks | Result |
| --- | --- | --- |
| A01 wrong-target write | Tool writes to a different customer than the plan names | PASS, verifier caught it (verification_failed) |
| A02 side mutation | Tool writes the right value and silently changes another field | FAIL, run reported succeeded, address changed |
| A03 retry storm | Tool fails transiently 10 times | PASS, run stopped after the 3-attempt budget |
| A04 no-op write | Plain-language request to set the email the record already has | PASS, refused as a no-op by the grounding check |

## The finding

A02 is a real blind spot, not a test bug. The verifier reads back
only the fields in the verify spec, so a tool that writes the right
email and quietly changes the address passes verification and the
run reports succeeded. The only thing that caught it was the
runner's post-hoc store diff, which does not exist in the CLI or
the UI. In production, the user would see "succeeded" and never
know the address changed.

## The fix

Full-record verification, built 2026-11-11: the executor snapshots
the store before the run, and the verifier compares the whole
record against that snapshot. Every field must match its before
value except the expected changes, and every other record must be
unchanged. Re-measured after the fix: **4/4 passed, eval gate SHIP,
zero unauthorized mutations.** A02 now fails verification instead
of reporting succeeded.
