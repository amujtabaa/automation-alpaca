---
type: Work Order
title: Complete the event-truth flip on the order-status write path + backfill (REV-0001 P0s)
status: CLOSED
work_order_id: WO-0013
wave: W1
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT, ADR_CREATED]
owner: Ameen (human-gated: event-log-truth, order-submission)
created: 2026-07-09
---

# Work Order: Complete the event-truth flip on the order-status write path + backfill

## Goal

Make the order-status **write path** (the double-submit claim gate) and the init
**backfill** derive from the event log instead of trusting the legacy `orders.status`
column, closing the two P0 gaps the REV-0001 independent review confirmed, and amend
ADR-008 to cover the two lifecycle edges the flip relies on.

## Context packet

Read only these first:

- `AGENTS.md`
- `work/review/REV-0001/request.md` and `work/review/REV-0001/result.md` (F-001..F-004)
- `docs/adr/ADR-004-event-log-truth-migration.md` (event-truth rule: business logic must not treat legacy tables as authoritative)
- `docs/adr/ADR-008-order-status-event-provenance.md` (Proposed; the provenance table to amend)
- `app/events/projectors.py::project_order_status` (the latest-lifecycle-event-wins fold)
- `app/store/memory.py` — `claim_order_for_submission` (~1188), `_project_order_unlocked`, `_backfill_order_status_events_unlocked` (~166)
- `app/store/sqlite.py` — `claim_order_for_submission` (~1950), `_project_order_locked`, `_backfill_order_status_events_locked` (~429)
- `app/store/core.py` — `plan_claim_order_for_submission` and the other status-dependent planners
- `tests/test_wo0007b_stage*.py`, `tests/test_wo0007a_transition_order_eventing.py`

## Allowed paths

```yaml
allowed_paths:
  - app/store/memory.py
  - app/store/sqlite.py
  - app/store/core.py
  - app/events/projectors.py
  - docs/adr/ADR-008-order-status-event-provenance.md
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - app/marketdata/**
  - app/api/**
  - cockpit/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] **F-001 (P0) — claim gate reads the projection, not the column.**
      `claim_order_for_submission` derives order status from the event-log projection
      **under the same lock/transaction** before the claim decision, in BOTH stores.
      A stale/divergent `orders.status` column (e.g. `CREATED` while the log says
      `SUBMITTED`) must NOT let the order be claimed, and must NOT append a second
      `SUBMIT_PENDING`.
- [ ] **Audit sibling write paths.** Enumerate every status-dependent planner/transition
      that reads the raw column (cancel, flatten planners, `transition_order`, etc.).
      Fix any that gate on the column, or document in the DONE block why each remaining
      one is safe (e.g. `transition_order` already refuses `TIMEOUT_QUARANTINE`).
- [ ] **F-002 (P0) — backfill keys on event ABSENCE, not `projected==CREATED`.**
      The init backfill emits a synthetic reconstruction event only when the order has
      **no lifecycle events at all**, in BOTH stores. An order with a real released
      cycle (`SUBMIT_PENDING → SUBMIT_RELEASED`, which legitimately projects `CREATED`)
      must never receive a synthetic event even if its column is stale. Correct the
      docstring to match what the code checks.
- [ ] **F-003 (P1) — amend ADR-008.** Add `SUBMIT_RELEASED` (`SUBMITTING → CREATED`)
      and `CANCEL_PENDING` to the provenance table (both `ENGINE`/`LOCAL`), with the
      note on why that stays consistent with ADR-001 (BROKER_AUTHORITATIVE wins).
      ADR stays `Proposed` — human acceptance + the follow-up review clear it.

## Required tests

- [ ] Regression (memory): a stale `CREATED` column cannot claim a log-`SUBMITTED` order; no second `SUBMIT_PENDING` appended.
- [ ] Regression (sqlite): same, dual-store parity.
- [ ] Regression (memory): a `SUBMIT_PENDING → SUBMIT_RELEASED` order with a stale terminal column gets NO synthetic backfill event.
- [ ] Regression (sqlite): same, dual-store parity.
- [ ] All must be RED against current code, GREEN after the fix.

## Required commands

```bash
python -m pytest -q tests/ -k "wo0007 or claim or backfill or flatten"
python -m pytest -q          # full suite, expect prior baseline + new tests, 0 failed
ruff check app/ && ruff format --check app/
mypy app/
python -m pytest -c /dev/null lint-imports 2>/dev/null || lint-imports
```

## Acceptance criteria

- [ ] All required behavior implemented; both P0 failure modes proven fixed in both stores.
- [ ] Tests prove behavior (RED→GREEN), no existing test weakened.
- [ ] Scope limited to allowed paths; no forbidden paths touched.
- [ ] Fable DONE block includes fresh pasted evidence (the RED→GREEN transcript + full-suite green).
- [ ] ADR-008 amended; PKL migration-history change-log updated.

## Model-tier rationale

**strong** — event-log-truth + the order-submission double-send gate are the most
safety-critical surface in the repo; a subtle projection/lock error here is a real
correctness hazard.

## Notes

- **Human-gated surfaces:** event-log truth, order submission/reconciliation. Every code
  change here is gated — no auto-apply; GATE the approach before coding.
- **F-004 disposition (not code):** the REV-0001 request's `commit_range`
  (`97123d6~1..64715fe`) bleeds in WO-0012 commits `e3fb487`/`4537aa2`. Record this in
  the packet disposition; tighten the range narrative. No code impact.
- **Re-review loop:** because this re-touches event-log truth, the fix itself queues for
  a fresh independent review (a new REV packet) before REV-0001's gate can truly clear.
  This WO does not itself clear the gate — it makes the flip correct enough to re-submit.

## Fable DONE (2026-07-09, commit `a7b012d` + disposition-commit hardening)

**F-001 (P0) — claim gate reads the projection.** `claim_order_for_submission`
projects order status under the lock before the gate, both stores. Dual-store RED→GREEN
(`tests/test_wo0013_event_truth_writepath.py`): a column drifted to CREATED can no longer
re-claim a log-SUBMITTED order.

**Sibling-audit conclusion (acceptance criterion "fix OR document why safe").** The recon
found the raw-column read is systemic — `claim`, `transition_order`, `flatten_position`,
`quarantine/resolve/reconcile`, `close_session`, `_active_sell_intent`, `_current_exposure`
all gate on the co-written `orders.status` column. **Decision: document-safe, not rewrite**,
justified by the **co-write invariant**, which was verified writer-by-writer (and
independently re-verified by REV re-review VER-13a/VER-X): every `orders.status` write
co-appends its lifecycle `ExecutionEvent` in the SAME atomic/tx block —
- claim → `SUBMIT_PENDING`; `transition_order` → the routine exec_event; the evented
  plan → its `execution_event`; flatten supersede-cancel → `CANCELED`; close-session
  cancel → `CANCELED`; an order is created only at `CREATED` (matches the projector's
  empty-log default, no event needed); and `TIMEOUT_QUARANTINE` is refused on the routine
  path and set only via the evented co-writing path (`execution_event_for_routine_transition`
  asserts, `core.py`).
- No `orders.status` writer exists outside the two stores (single-writer engine).
- Therefore column == projection in every reachable state; the siblings reading the column
  are correct, and the claim-gate flip to the projection is strictly safer (robust to
  hypothetical drift, never worse). A **defense-in-depth assert** now pins the invariant in
  code at the claim site (raw past-CREATED that projects CREATED fails loud, never
  blind-resubmits) — see `tests/test_wo0013_event_truth_writepath.py`.
- Deferred (documented, not blocking): a full projection-flip of every write path is a
  possible future WO if the team wants zero raw-column reads anywhere.

**F-002 (P0) — backfill keys on event absence.** `_backfill_order_status_events_*` now
fires only when an order has zero status-lifecycle events (new
`projectors.ORDER_STATUS_EVENT_TYPES`, FILL excluded). Released-cycle order no longer
clobbered; pre-eventing FILLED order still reconstructed; idempotent; dual-store parity.

**F-003 (P1) — ADR-008 amended** for `SUBMIT_RELEASED`/`CANCEL_PENDING` provenance (stays
`Proposed`).

**Evidence:** full suite green (0 failed), `ruff check` clean, `mypy app/` Success,
`import-linter` 5/0. Adversarial re-verify `wf_eb46fdce-662` (VER-13a/13b/X) all PASS.

## Completion disposition
- [x] RESULT_SUMMARY_KEPT — this DONE block + `work/review/REV-0001/disposition.md`.
- [x] ADR_CREATED — ADR-008 amended (F-003).

## Distillation checklist
- [x] Durable facts captured (co-write invariant + sibling-audit rationale, above).
- [x] Architecture decision captured in ADR-008.
- [x] Ledger updated (`work/ledger.jsonl`).
- [ ] Gate NOT cleared: re-review queued as `work/review/REV-0003/` (event-truth re-touch).

## Deletion decision
Keep — the sibling-audit rationale + co-write-invariant proof have durable value and are
referenced by REV-0001's disposition and the REV-0003 re-review.
