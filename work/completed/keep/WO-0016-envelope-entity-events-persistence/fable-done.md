# WO-0016 — fable_done

`[FABLE • FULL • verification: DIRECT • task: WO-0016]` — closed 2026-07-11, commit `5ca48f2` on `feat/execution-envelope-wo-0016`.

## done_when → evidence

| done_when | met | evidence |
|---|---|---|
| Hard-rail validators reject bad construction | ✅ | `tests/test_wo0016_envelope_model.py` — 34 passed (floor≤0/NaN/Inf, inverted trail range, participation ∉(0,1], empty aggressiveness/phases, missing dispositions, side≠SELL, reduce_only=False, self-supersession, extra fields all raise ValidationError) |
| Full transition matrix legal/illegal, both stores | ✅ | `tests/test_wo0016_envelope_transitions.py` — 209 passed; 100-pair (source,target) matrix parametrized over `any_store`; table cross-checked against a hand-written copy of the ADR-010 §3 edges; terminals empty; illegal edges raise `EnvelopeTransitionError` and mutate nothing |
| Remaining qty decrements on deduped FILL only | ✅ | `tests/test_wo0016_envelope_fills.py` — replayed dedupe_key counted exactly once (70 not 40); SUBMITTED/ACCEPTED appends + freeze/resume cycles leave remaining untouched; overfill floors at 0 + BREACHED; frozen fill never unfreezes (completes on resume); late fill on terminal recorded + flagged |
| Concurrent supersede → exactly one ACTIVE successor, both stores | ✅ | `tests/test_wo0016_envelope_supersede.py::test_concurrent_supersedes_yield_exactly_one_active_successor` — 5 concurrent, 1 winner, 4 `EnvelopeTransitionError`, exactly one ACTIVE after. **Mutation-checked:** disabling the ACTIVE guard makes the test FAIL (AssertionError at line 122), re-enabled → green |
| Event provenance round-trips both stores | ✅ | `tests/test_wo0016_envelope_events.py` — lifecycle ENGINE/LOCAL + actor payload; fills BROKER_REST/BROKER_AUTHORITATIVE; created-event payload reconstructs full mandate; SQLite close/reopen keeps envelope+events+dedupe; pre-W3 legacy DB gains `envelope_id` by `_migrate`, old rows read back NULL |
| Full gate green | ✅ | `ruff check .` All checks passed · `ruff format --check .` 188 files already formatted · `mypy app/` Success 54 files · `lint-imports` 5 kept 0 broken · `pytest -q` exit 0 (full suite incl. 132 new tests) |

## Scope check

Touched: `app/models.py`, `app/transitions.py`, `app/store/core.py`, `app/store/memory.py`, `app/store/sqlite.py`, `tests/test_wo0016_*.py` (5 new files), `docs/INVARIANTS.md` (INV-076..079), `docs/adr/ADR-010-execution-envelope.md` (two recorded amendments) — all inside allowed paths (+ADR, whose amendments were human-delegated at T1). Forbidden paths untouched.

## Decisions recorded (delegated at T1, "smart choice")

1. **ADR-010 §3 amendment** — pre-activation escape edges `PENDING/APPROVED → {CANCELLED, EXPIRED}`; pre-activation supersession stays illegal.
2. **ADR-010 §6 amendment** — `envelope_activated`/`envelope_completed`/`envelope_cancelled` added (machine not replayable from the log without them); `ExecutionEvent.envelope_id` additive nullable column, no `EXECUTION_EVENT_SCHEMA_VERSION` bump.
3. Overfill of the hard qty ceiling from ACTIVE → recorded faithfully + `BREACHED`; a freeze is never exited by a fill (auto-complete happens on resume, atomically).

## Deviations

- `[FABLE DEVIATION]` fill/supersede/events tests were authored after the pure planners existed (the store surface landed as one unit); mitigations: first run caught a real bug (missing `whole_count_reason` import in core.py — genuine red→green), and the single-flight test was mutation-checked (see table). Transition/model tests were strict test-first (watched RED on ImportError, then GREEN).
- Envelope API is concrete-only on both stores (no abstract declarations): `app/store/base.py` is outside WO-0016 allowed paths. Deferred to WO-0019, which needs the interface seam anyway. `EnvelopeTransitionError` lives in `app/store/core.py` for the same reason.

## Status: VERIFIED
