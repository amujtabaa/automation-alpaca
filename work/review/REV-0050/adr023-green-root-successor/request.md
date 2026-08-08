# WO-0148 position-local pre-exposure root-successor exact-delta review

## Immutable boundary

- Parent: `2982048b3247e0c9cee5c9988b77fc43cd208235`
- Candidate: `e9c2d58a8f16d2b3457dad5e4c5ed04ca24073ae`
- Exact candidate paths:
  - `app/execution_core/protection.py`
  - `tests/execution_core/test_protection.py`
  - `tests/execution_core/test_protection_stateful.py`
  - `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`
  - `work/review/REV-0050/adr023-green-root-successor/GREEN-ROOT-SUCCESSOR-EVIDENCE.md`

Review only this immutable delta. Ignore and preserve unrelated untracked historical artifacts.
The prior `adr023-green-successor/result.md` is an audit input, not a controlling conclusion.

## Required determination

Re-derive the exposure boundary from ADR-021 and the authenticated execution/venue model:

1. Account-wide registry history from another symbol must not be treated as exposure for this
   position. A genuine foreign-symbol fill and registry catch-up must leave a zero-root target
   position pre-exposure; that target's own first exact-basis fill must arm `FLOOR_ONLY`.
2. This position's own immutable root history must survive zero quantity. Fill -> bust to zero ->
   valid positive correction must remain `HARD_BAIL`, with no false late-flat alert and no goal.
3. True `FLAT` -> late positive remains `HARD_BAIL` with its required alert. Positive formula
   loss/restoration, overfill, reconciliation, and pending basis remain fail-closed.
4. The private projection count must come only from the proof-bound position root sequence, be
   included in the opaque factory and v3 commitment, and fail authentication if changed.
5. Pre-exposure remains committed, is not a real exit, and is the sole exception to sticky
   `HARD_BAIL` on a first position root. No public surface, caller flag, unbounded history, I/O,
   runtime, persistence, database, broker, network, or deferred authority may be added.

Confirm both new concrete controls and the reconciled stateful rule are failure-capable. In
particular, substitute account-registry count for position-root count in memory or by a fully
restored temporary edit and confirm the cross-scope control fails; independently check that the
pre-correction policy guard makes the fill/bust/restore control fail. Restore and hash-verify any
temporary edit before concluding.

Author-side claims are 4/4 critical lifecycle, 10/10 hostile lifecycle/seal, 513/513 complete
protection/stateful/import, 1,258/1,258 execution core, Ruff, format, mypy, Import Linter, Python
3.11 grammar, and diff/scope. Reproduce proportionately. Do not broaden review absent a material
contradiction.

No database or SQL/DDL, broker or Alpaca, network, credentials, runtime wiring, persistence,
M2, master merge, deletion, or cleanup is permitted. Write findings only to `result.md` in this
directory; do not edit any other file.

Each finding must include severity, file:line, reproduced impact, and smallest root correction.
End with `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`, explicit P0/P1/P2 counts, reproduced evidence,
and anything unverified. Acceptance requires P0=0 and P1=0.
