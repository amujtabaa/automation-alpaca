# WO-0007a — Fable DONE block

`[DONE]` WO-0007a — Emit routine order-status ExecutionEvents + dual-store parity (no read-flip).

STATUS: VERIFIED

## What shipped

Every routine order-status transition now co-writes a deterministic order-status
`ExecutionEvent` into the `execution_events` log, in BOTH stores, atomically with the
existing `orders.status` write + audit row. `orders.status` stays authoritative — purely
additive, no read-flip, no projector (that is WO-0007b). Implementation commit `c9a8335`.

- New pure helper `app/store/core.py::execution_event_for_routine_transition` +
  `_EXECUTION_EVENT_FOR_ROUTINE_STATUS` map; the pure planners
  `plan_transition_order` / `plan_claim_order_for_submission` are untouched.
- Emission wired at 4 mirrored call sites per store: `claim_order_for_submission`
  (`SUBMIT_PENDING`), `transition_order` (`SUBMITTED` / first-entry `PARTIALLY_FILLED` /
  `FILLED` / `CANCELED` / `REJECTED` + the `PARTIALLY_FILLED` fill-progress self-loop),
  and the two direct-CANCELED bypass writers `plan_close_session` + `plan_flatten_position`
  (scope correction from the adversarial design review).

## Required behavior — all met

- [x] Each routine transition co-writes an order-status ExecutionEvent (deterministic
      `dedupe_key`), atomically, both stores. Mapping resolved incl. `SUBMITTING` -> `SUBMIT_PENDING`.
- [x] INV-9 preserved — order-status `FILLED`/`PARTIALLY_FILLED` are distinct from `FILL`;
      position projector folds only `FILL` (adversarial-verified HOLDS).
- [x] INV-5 / idempotency — unique `dedupe_key`; terminal statuses one-shot in the graph so
      the shared `{status}:{id}` format cannot collide across writers (adversarial-verified HOLDS).
- [x] No read-flip — `orders.status` remains authoritative; no existing read path changed.

## Required tests — all present (both stores via `any_store`)

- [x] Characterization: the pre-existing transition/quarantine suite pins current behavior and
      stayed green, proving emission is purely additive.
- [x] Emission: each routine transition appends exactly one expected event (both stores).
- [x] Dual-store parity: Stage 4 drives 4 end-to-end lifecycles independently on memory + sqlite
      and asserts identical (event_type, normalized dedupe_key) SEQUENCES, plus exact expected shapes.
- [x] Idempotent replay + INV-9 + the safety-relevant TIMEOUT_QUARANTINE-consumer regression
      (`tests/test_wo0007a_quarantine_consumer_unaffected.py`).

## Evidence (fresh, my own run — working tree, base d52c6d0)

```
command: python -m ruff check .
=> All checks passed!

command: python -m mypy app/
=> Success: no issues found in 54 source files

command: python -m pytest -q  (JUnit XML; this env suppresses the terminal summary line)
=> 1863 collected, 1858 passed, 5 skipped, 0 failed, 0 errors  (114.8s)
   (48 WO-0007a emission/parity cases + 6 quarantine-consumer regression cases)
```

Adversarial verify pass (workflow `wf_15570028-93a`, 5 independent skeptics, each tasked to
REFUTE one safety claim) — all **HOLDS, severity none**: INV-9 (position untouched),
dedupe/idempotency (no reachable key collision; the append primitives silently no-op on a
duplicate key, and none is reachable), dual-store parity (both stores delegate to the one pure
helper), scope/test-integrity (proven by mutation — breaking the dedupe-key format => 6 failures,
neutering the TQ guard => 3 failures; only comment-line diffs deleted; planners untouched), and the
provenance judgment (`ENGINE`/`LOCAL` is a safe under-claim; no consumer reads source/authority today).

## Scope / disposition

- Diff confined to `app/store/{core,memory,sqlite}.py` + 5 new `tests/test_wo0007a_*.py`. No
  human-gated surface auto-executed (additive writes into the pre-existing log via existing
  append primitives; no schema migration; `orders.status` unchanged as the authority).
- Residual, flagged (NOT fixed — out of `app/store/**` scope): `timeout_quarantined_order_ids`'s
  docstring rationale is now stale (routine path also emits those lifecycle types); output unchanged,
  recommend a one-line docstring fix in a WO-0007b-era touch of `app/events/`.
- Deferred to WO-0007b: the projector + read-flip, and faithful per-transition broker provenance.
- Disposition: RESULT_SUMMARY_KEPT (this folder + `design-decision.md` are the durable record).
