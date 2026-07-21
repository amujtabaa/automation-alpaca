---
type: Work Order
title: Envelope approval surface + flatten/kill-switch precedence (ADR-010 §1, §4)
status: CLOSED
work_order_id: WO-0017
wave: W3
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT]
record_reconciliation: "WO-0120 (2026-07-20) verified fable-done.md status VERIFIED and the existing WO-0017 DISPOSED ledger row; a canonical CLOSED ledger row is appended."
owner: Ameen (human-gated: order submission delegation, kill switch, manual flatten)
created: 2026-07-11
---

# Work Order: Envelope approval surface + flatten/kill-switch precedence

## Goal

Route envelope creation/approval through the `ApprovalGate` pattern as one store-atomic unit (ENG-001
style), and enforce ADR-010 §4 precedence: kill switch freezes all envelopes; manual flatten
atomically cancels/freezes a symbol's envelopes *before* proceeding.

## Context packet

Read only these first:

- `AGENTS.md`
- `docs/adr/ADR-010-execution-envelope.md` (§1, §4)
- `docs/adr/ADR-003-manual-flatten-halted-reducing.md`
- `app/approval/gate.py`, `app/approval/human.py` — the gate ABC + idempotency conventions
- `app/store/core.py` — the ENG-001 atomic exit-open unit (dedup→HALTED check→create→approve→
  dispatch→audit with no await between check and durable writes) as the required shape
- `app/store/core.py` — `plan_flatten_position`; `app/facade/store_backed.py` — `create_exit`
- WO-0016 output (envelope entity + transitions)
- `tests/test_phase7_flatten_atomic.py`, the REV-0020 regression shapes

## Allowed paths

```yaml
allowed_paths:
  - app/approval/**
  - app/store/core.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/api/routes_trading.py
  - app/models.py
  - tests/**
  - docs/INVARIANTS.md
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - app/marketdata/**
  - app/monitoring.py
  - cockpit/**            # operator UI rendering lands in WO-0020
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] Envelope create→approve→ACTIVE is one store-atomic unit with the HALTED/kill check atomic
      with durable writes (no await window); a kill mid-flow leaves zero envelope artifacts,
      both stores.
- [ ] Approval is idempotent per the candidate-gate conventions (re-approve of ACTIVE is a no-op;
      approve of terminal states is illegal).
- [ ] Approval event carries operator-* provenance; autonomous-side events remain system-actor.
- [ ] Kill switch engaged ⇒ every ACTIVE envelope → FROZEN before any further envelope action can
      be planned or written; resume requires explicit human action.
- [ ] `plan_flatten_position` (or its atomic successor) cancels/freezes all envelopes for the
      symbol **first**, in the same atomic unit, then proceeds — envelopes can never race or block
      flatten. The safe deferral semantics of ADR-003/WO-0015 are unchanged.
- [ ] TTL/expiry disposition and stale-data disposition are mandatory at approval time (reject
      approval without them).

## Required tests

- [ ] Integration: kill lands between check and would-be write ⇒ zero artifacts, both stores
      (mirror REV-0020 last-await kill shape).
- [ ] Integration: flatten with an ACTIVE envelope ⇒ envelope frozen/cancelled in the same atomic
      unit, flatten proceeds; assert event ordering in the log.
- [ ] Integration: concurrent approve ⇒ single-flight (one ACTIVE, one event), both stores.
- [ ] Unit: approval rejected when dispositions missing; idempotency matrix.

## Required commands

```bash
ruff check . && ruff format --check . && mypy && lint-imports && pytest -q
```

## Notes

- Fable FULL; touches kill switch + flatten ⇒ Complex; plan pauses for human approval; queues for
  independent cross-model review (gated surfaces) before beta reliance.
- Depends on WO-0016. Do not begin until WO-0016 is dispositioned.
