# REV-0075 R7 design review result

Exact candidate reviewed: `a6c687a399d3e4c547eefa7b10ce090af83b9789`, tree
`31da5be0bc5028bd761dc902e27d095aa436f577`.

## P1 — Fixed-position control still admitted field swaps

Location: `tests/execution_core/test_protection.py:9964`.

All selected states had equal `market_occurrence_epoch` and
`market_committed_epoch` values, while `market_halted` and `market_exhausted`
were always false. Swapping those encoder positions could therefore leave the
claimed fixed-order control green. The smallest complete correction is to add
ordinary reducer states with distinguishable values and assert one unique
per-position vector across the real-state corpus.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=1, P2=0.

Unverified: no candidate test command was run by this design review. No
SQLite, database, network, or runtime composition activity occurred.
