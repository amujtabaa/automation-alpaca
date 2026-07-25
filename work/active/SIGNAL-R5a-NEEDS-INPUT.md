# Signal Seat R5a — NEEDS-INPUT batch

WO-0137 cannot truthfully move to `REVIEW` under the ratified contract. The implementation is
preserved on `codex/signal-r5a-foundation`; the feature flag remains off, and no review packet,
ledger line, merge, or PR has been created.

## Decision 1 — authorize a cross-platform launcher-test correction or supply POSIX evidence

The staged launcher replaces the complete child environment with five values, including a Unix-only
`PATH`. On Windows, both bare-Uvicorn cases fail in stdlib `_overlapped` with WinError 10106 before
Uvicorn imports `app.main`. Seven launcher cases pass raw; a normal inherited-environment control
passes all nine and produces the required exact `Attribute "app" not found` pre-bind failure.

Choose one:

1. authorize a narrowly reviewed staged-test correction that starts from a sanitized inherited
   environment, applies the explicit Signal Seat values, and adds a timeout to `_run`; or
2. provide fresh unchanged-corpus evidence from the intended POSIX execution environment and
   explicitly accept that evidence for the local Windows gate.

This is beyond D-R5a-3, currently the only authorized staged-test edit.

## Decision 2 — resolve the importable zero-argument test factory

The staged `tests.signal_seat_helpers:build_flag_on_app` is a zero-argument Uvicorn factory that
mints a launch capability and wires permissive rails. A fresh `uvicorn.Config(..., factory=True)`
load succeeds. That conflicts with accepted ADR-009:

- A-1 forbids a zero-argument authorized factory that can reacquire the capability; and
- A-4 requires permissive fakes to be confined so production config/environment cannot select them.

Choose an approved design, for example:

1. change the staged helper/callers to require explicit non-default test authority and add a hostile
   import-string negative proof; or
2. structurally exclude tests from the deployed/importable runtime artifact and add a packaging
   proof that the helper cannot be selected.

Do not enable the seat or stage REV-0041 until this is resolved.

## Decision 3 — dispose the inherited gate-baseline conflicts

Two stipulated full-battery commands cannot pass within R5a's allowed paths:

- `ruff format --check .` reports 12 files: ten inherited/out-of-scope files plus the two immutable
  staged launcher/guard tests.
- direct `python tests/r2_conformance_oracle.py` cannot import `app`; the unchanged script exits 0
  when the repo root is supplied through `PYTHONPATH`.

Choose one:

1. authorize a bounded formatter baseline/ratchet and an exact R2 invocation substitution; or
2. land separate baseline cleanup/import-context work, then rebase and rerun WO-0137 raw.

## Resume gate

After all three decisions are recorded, rerun the exact raw launcher corpus and complete gate
battery. Only then set WO-0137 to `REVIEW` and stage `work/review/REV-0041/request.md`.
