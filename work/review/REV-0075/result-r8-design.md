# REV-0075 R8 design review result

Exact candidate reviewed: `09195eea5a14fa2c350c789adb72a5f07d3be760`, tree
`9a00865fe59d4b4904f3fa7b3ec817b9b1669c7f`.

## P1 — Decoder issued state before direct-current reauthentication

Location: `app/execution_core/persistence/checkpoint_codec.py:274`.

The decoder rebuilt `_M2ExecutionState` from wire fields and checked only its
recomputed commitment; it did not invoke the direct-current proof checks that
bind retained map commitments to current rows. A self-consistent but unbound
component could thus be treated as authenticated state. Require the typed
direct-current proof and route decoded fields through the owning hydration
seam before returning `_M2ExecutionState`, with a mismatched-proof control.

## P1 — Wire contract controls were incomplete

Location: `tests/execution_core/test_position.py:332`.

Expected enum values reused production encoders, and tests covered only
populated optional fields. Add literal local known answers, valid absent-option
forms, mutated-owner encoder controls, and missing/extra/reordered structure
controls that fail at local boundaries.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=2, P2=0.

Unverified: author-reported pure tests, Ruff, and mypy were not rerun by this
review. No SQLite, database, network, or runtime composition was invoked.
