# WO-0148 pre-fill lifecycle exact-delta review

## Immutable boundary

- Parent: `d3e11f31f16b55f1209f7e2b3f00a1b4056ca157`
- Candidate: `2848b8540645dbd6c58e62dffa867e666b0c32f9`
- Exact candidate paths:
  - `app/execution_core/protection.py`
  - `tests/execution_core/test_protection.py`
  - `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`
  - `work/review/REV-0050/adr023-green-successor/GREEN-SUCCESSOR-EVIDENCE.md`

Review only this immutable delta as the successor to the P1 in
`work/review/REV-0050/adr023-green-candidate/result.md`. Ignore and preserve all untracked
historical artifacts.

## Required determination

Reproduce the original genuine pre-fill venue-chain counterexample and determine whether the first
canonical positive exact-basis fill now arms `FLOOR_ONLY` without an alert. Verify the correction
does not weaken these separate cases:

- zero quantity after any canonical execution history is not pre-exposure;
- formula loss after positive exposure remains sticky `HARD_BAIL`;
- true `FLAT` followed by late positive remains `HARD_BAIL` with its deterministic alert;
- zero-quantity protection state can still follow multi-scope kill/catch-up transitions;
- pending basis, reconciliation, overfill, and nonpositive exposure remain restricted.

Re-derive that `_execution_fact_count` comes only from the authenticated venue execution
checkpoint, is included in the opaque projection factory and v2 projection commitment, and cannot
be changed without failing projection authentication. Verify pre-exposure provenance is committed,
is never treated as a real exit, persists only while raw quantity and canonical execution-fact count
are both zero, and is replaced on first positive economics. Confirm no public field/function,
caller-authored flag, variable history, I/O, runtime, or deferred authority was added.

Determine whether both new controls are failure-capable and isolate the intended distinction. The
author-side claims are 8/8 critical focus and 511/511 direct/stateful/import, plus Ruff, format,
mypy, Import Linter, and diff checks. Reproduce proportionately; do not rerun unrelated broad review
unless a material uncertainty requires it.

No database or SQL, broker or Alpaca, network, credentials, runtime wiring, persistence cutover,
M2, master merge, deletion, or cleanup activity is permitted. Write findings only to `result.md` in
this directory. Do not edit request, evidence, application, tests, WO, ADRs, PKL, or ledger.

Each finding must include P0/P1/P2, file:line, reproduced impact, and smallest root correction. End
with `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`, explicit counts, evidence reproduced, and anything
unverified. Acceptance requires P0=0/P1=0.
