---
type: Work Order
title: Faithful per-transition provenance for routine order-status ExecutionEvents
status: ACTIVE
work_order_id: WO-0009
wave: W2-remediation
model_tier: strong
risk: high
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: Faithful order-status event provenance

> Follow-up to WO-0007a (human decision: "you're free to faithful provenance"). WO-0007a shipped
> routine order-status ExecutionEvents with a deliberately conservative uniform `ENGINE`/`LOCAL`
> provenance. This WO replaces that with FAITHFUL per-transition `source`/`authority`, matching the
> provenance convention the rest of the event log already uses (`execution_event_for_fill`,
> `plan_resolve_timeout_quarantine`, `plan_reconcile_resolve_order` all label broker-observed facts
> `BROKER_REST`/`BROKER_AUTHORITATIVE`). This is NOT the read-flip (that stays WO-0007b, gated).

## fable_gate

- **goal:** every routine order-status ExecutionEvent carries provenance that reflects HOW the fact
  was learned, consistent with the existing evented paths — not a blanket `ENGINE`/`LOCAL`.
- **assumptions (VERIFIED by recon, workflow `wf` + main-context grep of every `transition_order` /
  `claim_order_for_submission` caller in app/):**
  - No caller drives a broker-observed status with non-broker provenance. SUBMITTED is only reached
    with a broker id (AIR-001, `plan_transition_order` core.py:1415-1426); PARTIALLY_FILLED/FILLED
    come from the reconcile poll (`monitoring.py:1545-1549` via `_reconciled_status`); REJECTED comes
    only from the reconcile poll or the evented TQ-not-found path — never an engine-local routine
    REJECTED. [VERIFIED]
  - CANCELED is engine-local ONLY when the order was never submitted (old status CREATED):
    `monitoring.py:240` ("cancel locally"), facade `_cancel_transition` never-submitted branch
    (`store_backed.py:858-860`), `plan_close_session` still-CREATED-BUY cancel, and
    `plan_flatten_position` supersede-cancel. CANCELED from any post-CREATED state is broker-confirmed.
    [VERIFIED]
  - The claim (`CREATED → SUBMITTING`, SUBMIT_PENDING) is a pre-broker engine decision. [VERIFIED]
  - All routine broker observations currently arrive via REST poll/ack, so `source=BROKER_REST` is
    faithful today; a future websocket ingestion path would pass `BROKER_STREAM`. [VERIFIED — no
    `transition_order`/`claim` caller is stream-driven today]
  - The helper already receives the PRE-transition order (old status) at every emission site, so
    provenance is derivable in-store from `(old_status, new_status)` with NO change to monitoring.py
    or the store method signatures. [VERIFIED]
- **approach:** add a pure `_routine_event_provenance(old_status, new_status) -> (EventSource,
  EventAuthority)` in core.py and use it inside `execution_event_for_routine_transition` for the
  `source`/`authority` of every branch, replacing the hardcoded `ENGINE`/`LOCAL`.
  - claim (`→ SUBMITTING`): `ENGINE`/`LOCAL`
  - `→ CANCELED` of an order with no `broker_order_id`: `ENGINE`/`LOCAL` (broker never saw it —
    covers never-submitted CREATED cancels AND the `SUBMITTING → CANCELED` submit-failure release;
    **corrected from the initial `old_status is CREATED` proxy after the adversarial-verify pass found
    the SUBMITTING-release over-claim — see fable_fix in the WO-0009 close**)
  - everything else in the routine map (`SUBMITTED`, `PARTIALLY_FILLED` incl. self-loop, `FILLED`,
    `REJECTED`, and a broker-confirmed `CANCELED` with a `broker_order_id`): `BROKER_REST`/`BROKER_AUTHORITATIVE`
  - alternative rejected: threading `source`/`authority` params from the monitoring/facade callers
    (Option A) — more future-proof for a websocket path but touches the highest-risk store method
    signatures + ~6 monitoring call sites for no correctness gain today; deferred to whenever a
    stream ingestion path is actually added.
- **out_of_scope:** the read-flip (WO-0007b); `CANCEL_PENDING`/release (no event, WO-0007a scope);
  monitoring.py / facade / adapter; `BROKER_STREAM` (no stream path exists yet).
- **done_when:**
  - behavior: routine SUBMITTED/PARTIALLY_FILLED/FILLED/REJECTED + broker-confirmed CANCELED events
    are `BROKER_REST`/`BROKER_AUTHORITATIVE`; claim + never-submitted CANCELED stay `ENGINE`/`LOCAL`.
    test: updated + new provenance tests in the WO-0007a test files, both stores. command: `pytest -q`.
  - behavior: dual-store parity still holds (provenance is part of the compared shape). test: extend
    the Stage-4 parity assertions to include (source, authority). command: `pytest -q`.
  - behavior: no read-path / position change (INV-9 intact — provenance never affects folding).
    command: `pytest -q` full suite green + `ruff check .` + `mypy app/`.
- **blast_radius:** `app/store/core.py` (helper only; pure planners still untouched) + the WO-0007a
  test files. No production call site changes. Events remain non-authoritative shadow (no projector).
- **rollback:** revert the single helper change; events revert to `ENGINE`/`LOCAL`. No data migration
  (append-only log; historical events keep their recorded provenance — informational, pre-WO-0009).

## Allowed paths
```yaml
allowed_paths:
  - "**"
write_allowed:
  - app/store/core.py
  - tests/**
  - work/active/WO-0009*/**
```

## Forbidden paths
```yaml
forbidden_paths:
  - app/monitoring.py
  - app/facade/**
  - app/api/**
  - app/events/**
  - cockpit/**
  - docs/adr/**
```

## Required tests
- [ ] Helper unit tests: provenance for each (old_status, new_status) branch (RED->GREEN).
- [ ] Store-level: SUBMITTED/FILLED/PARTIALLY_FILLED/REJECTED via transition_order are BROKER_*;
      claim is ENGINE/LOCAL; CANCELED-from-CREATED (close/flatten/local) is ENGINE/LOCAL;
      CANCELED-from-SUBMITTED is BROKER_*. Both stores.
- [ ] Stage-4 dual-store parity extended to assert (source, authority) in the compared shape.

## Acceptance criteria
- [ ] Faithful provenance on every routine event; `authority` correct in every case.
- [ ] Full suite green; RED->GREEN evidence; ruff + mypy clean.
- [ ] INV-9 intact; no read-flip; pure planners untouched.
- [ ] Fable DONE block with evidence.

## Completion disposition
- [ ] RESULT_SUMMARY_KEPT
