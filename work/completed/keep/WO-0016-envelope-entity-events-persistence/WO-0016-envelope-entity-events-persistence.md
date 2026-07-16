---
type: Work Order
title: ExecutionEnvelope entity, state machine, events, dual-store persistence (ADR-010 §2-3, §6)
status: DRAFT
work_order_id: WO-0016
wave: W3
model_tier: strong
risk: high
disposition: []
owner: Ameen (human-gated: event-log truth changes; schema migration)
created: 2026-07-11
---

# Work Order: ExecutionEnvelope entity, state machine, events, dual-store persistence

## Goal

Introduce the `ExecutionEnvelope` entity per ADR-010 — immutable bounded fields (hard rails vs
soft bounds), status machine with amendment-by-supersession, the envelope ExecutionEvent family
with ADR-008 provenance, persisted and behavior-identical in both stores.

## Context packet

Read only these first:

- `AGENTS.md`
- `docs/adr/ADR-010-execution-envelope.md` (authoritative; §2 fields, §3 states, §6 events)
- `docs/adr/ADR-008-order-status-event-provenance.md`
- `app/models.py` — `SellIntent`, `SellIntentStatus`, ExecutionEvent kinds; follow the
  candidate/sell-intent XOR-linkage style for envelope↔intent linkage
- `app/transitions.py` — `SELL_INTENT_TRANSITIONS` / `SELL_INTENT_TIMESTAMP` patterns
- `app/store/core.py`, `app/store/memory.py`, `app/store/sqlite.py` — entity CRUD + event append
  patterns; the ENG-001 atomic-unit style
- `tests/` — nearest sell-intent store tests as the template

## Allowed paths

```yaml
allowed_paths:
  - app/models.py
  - app/transitions.py
  - app/store/core.py
  - app/store/memory.py
  - app/store/sqlite.py
  - tests/**
  - docs/INVARIANTS.md
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - app/marketdata/**
  - app/monitoring.py
  - app/approval/**
  - cockpit/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] `ExecutionEnvelope` model: all ADR-010 §2 fields; hard-rail vs soft-bound classification
      encoded (validators reject construction with floor ≤ 0, empty ranges, missing dispositions);
      immutable after creation (no bound-mutation API exists).
- [ ] Status machine in `transitions.py`: `PENDING/APPROVED/ACTIVE/FROZEN/COMPLETED/EXPIRED/
      EXHAUSTED/BREACHED/SUPERSEDED/CANCELLED` with only the ADR-010 §3 legal edges; illegal
      transitions raise, both stores.
- [ ] Remaining-qty decrement **only** via deduped fill events (submission/ack paths structurally
      cannot change it).
- [ ] Supersession: creating envelope B superseding A atomically marks A `SUPERSEDED` and links
      both (one atomic store op; no window with two ACTIVE envelopes for one intent).
- [ ] Envelope event family appended per ADR-010 §6 with ADR-008 provenance
      (operator-* on create/approve rows written here as data plumbing only — the approval *flow*
      is WO-0017's scope).
- [ ] SQLite schema addition is a migration (human-gated; pause for approval per CLAUDE.md).

## Required tests

- [ ] Unit: field validation (each hard rail rejects bad construction).
- [ ] Unit: full transition matrix legal/illegal, parametrized, both stores.
- [ ] Unit: qty decrements on fill event only; ack/submitted cannot decrement.
- [ ] Integration: supersession atomicity — concurrent supersede attempts yield exactly one
      ACTIVE successor, both stores (mirror the W2-CAND single-flight test shape).
- [ ] Integration: event provenance fields round-trip both stores.

## Required commands

```bash
ruff check . && ruff format --check . && mypy && lint-imports && pytest -q
```

## Notes

- Fable FULL; gated surface (event-log truth + migration) ⇒ Complex regardless of size; plan
  pauses for human approval; queues for independent review per ADR-010 status.
- Out of scope, log only: approval flow (WO-0017), policy (WO-0018), engine seam (WO-0019).
