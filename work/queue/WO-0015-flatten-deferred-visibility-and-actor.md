---
type: Work Order
title: Make a deferred manual-flatten operator-visible + thread the command actor (REV-0002 F-001/F-002)
status: DRAFT
work_order_id: WO-0015
wave: W1
model_tier: strong
risk: medium
disposition: []
owner: Ameen (human-gated: manual-flatten)
created: 2026-07-09
---

# Work Order: Make a deferred manual-flatten operator-visible + thread the command actor

## Goal

When a manual flatten is safely deferred to an in-flight protection order
(`CANCEL_PENDING`/`TIMEOUT_QUARANTINE`/`SUBMITTED`), tell the operator plainly that **no
manual order was submitted** (instead of reporting "flatten submitted"), and record
**who** issued the command in the `manual_flatten_deferred` audit event — without
changing the safe no-blind-cancel decision itself.

## Context packet

Read only these first:

- `AGENTS.md`
- `work/review/REV-0002/result.md` (F-001, F-002)
- `app/store/core.py` — `plan_flatten_position` deferral branch (~1027-1065); the `manual_flatten_deferred` `EventSpec`
- `app/facade/store_backed.py` — `create_exit` (~789-826); note it discards `result.outcome`
- `app/api/routes_trading.py` — the flatten route (~90-110); it already resolves `actor`
- `cockpit/app.py` — the flatten call site (~381-383) that reports "flatten submitted"
- `app/models.py` — `FlattenResponse`, `FlattenResult`, `FLATTEN_*` outcomes
- `docs/INVARIANTS.md` — INV-034 / INV-036 (~212, the recorded actor-provenance gap)
- `tests/test_phase7_flatten_atomic.py` (deferral test covers only `SUBMITTED`)

## Allowed paths

```yaml
allowed_paths:
  - app/store/core.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/api/routes_trading.py
  - cockpit/app.py
  - app/models.py
  - docs/INVARIANTS.md
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - app/marketdata/**
  - app/events/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] **F-001 — deferral is an explicit, operator-visible state.** A deferred flatten no
      longer returns the same success payload as a submitted exit. The response carries
      the deferred order status + a "no manual order submitted; monitoring the existing
      protection exit" signal (see Notes — **human decision D-2** for the exact shape),
      and the cockpit renders it distinctly from "flatten submitted". The safe
      no-second-order behavior is preserved exactly.
- [ ] **F-002 — thread the command actor.** `create_exit(actor=...)` passes the actor
      through `flatten_position` so the `manual_flatten_deferred` event payload records
      it (and, for parity, the created `MANUAL_FLATTEN` intent path where the same actor
      boundary applies). Update the INV-034 note that currently records this as an open gap.

## Required tests

- [ ] Deferral distinctness (memory + sqlite + facade) for `SUBMITTED`, `CANCEL_PENDING`,
      and `TIMEOUT_QUARANTINE`: the response/outcome is distinguishable from a submitted flatten.
- [ ] Actor retained (dual-store + facade): the real `X-Actor` appears in the audit event
      for BOTH the created-flatten and deferred-flatten paths.
- [ ] Cockpit renders the deferred state distinctly (unit-level assertion on the message/branch).
- [ ] RED→GREEN; the existing `SUBMITTED`-only deferral test is extended, not weakened.

## Required commands

```bash
python -m pytest -q tests/test_phase7_flatten_atomic.py tests/test_lifecycle_state_machine.py
python -m pytest -q
ruff check app/ && ruff format --check app/
mypy app/
```

## Acceptance criteria

- [ ] Operator can tell a deferred flatten from a submitted one, in API and cockpit.
- [ ] Actor recorded on created + deferred flatten audit events.
- [ ] No change to the flatten decision, position/order/fill state, or the no-blind-cancel rule.
- [ ] RED→GREEN; no test weakened; scope within allowed paths.
- [ ] Fable DONE block with fresh evidence; INVARIANTS note updated.

## Model-tier rationale

**strong** — manual-flatten is human-gated and the change spans store → facade → api →
cockpit; getting the response contract + the "no state change" guarantee right needs care.

## Notes

- **Human decision D-2 — deferred response shape:**
  - **(A) Explicit field (recommended).** Add an `outcome`/`deferred` discriminator to
    `FlattenResponse` (carrying the deferred order status + next-action hint). Cleanest,
    self-describing to API clients and the cockpit; small additive contract change.
  - **(B) Message-only.** Leave the response shape and derive a distinct cockpit message
    from existing fields. Smaller, but API clients still can't distinguish the two outcomes.
- **Human-gated surface:** manual-flatten. No auto-apply; GATE the approach (esp. the
  response-contract change) before coding.
- Additive-provenance discipline: the `manual_flatten_deferred` event and actor threading
  must not alter any order/fill/position state (INV-9 / single-writer).

## Completion disposition

_(complete after merge)_

## Distillation checklist

_(complete after merge)_

## Deletion decision

_(complete after merge)_
