---
type: Work Order
title: Monitoring-tick wiring + operator visibility for envelopes (ADR-010 §1; LASE 04)
status: DRAFT
work_order_id: WO-0020
wave: W3
model_tier: mid
risk: medium
disposition: []
owner: Ameen
created: 2026-07-11
---

# Work Order: Monitoring-tick wiring + operator visibility for envelopes

## Goal

Run the envelope policy inside `run_monitoring_tick()` immediately after `_run_protection(...)`
(protection always first), route planned actions to the WO-0019 engine seam, and give the cockpit
read-only envelope visibility (status, bounds, remaining budget/qty, last action, breach/divergence
flags) plus the approval affordance — the UI observing state and issuing intents only.

## Context packet

Read only these first:

- `AGENTS.md`
- `docs/adr/ADR-010-execution-envelope.md`
- LASE `04_INTEGRATION.md` (placement intent only; store methods there are superseded by WO-0016)
- `app/monitoring.py` — `run_monitoring_tick`, `_run_protection` ordering; never-crash-the-tick
  conventions
- `app/api/routes_trading.py`, `cockpit/api_client.py`, `cockpit/app.py` — thin-client seams
- WO-0016..0019 outputs

## Allowed paths

```yaml
allowed_paths:
  - app/monitoring.py
  - app/api/routes_trading.py
  - app/facade/store_backed.py
  - cockpit/**
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - app/store/core.py      # seam is WO-0019's; consume it
  - app/store/memory.py
  - app/store/sqlite.py
  - app/sellside/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] Envelope pass runs after `_run_protection` in the same tick; a policy exception is caught,
      event-logged, freezes only that envelope, and never crashes the tick (match existing
      protection error-isolation conventions).
- [ ] Tick uses one snapshot fetch per symbol shared with protection where the current code allows;
      no duplicate market-data calls introduced.
- [ ] Cockpit renders envelopes distinctly: ACTIVE (bounds + remaining budget/qty + last action),
      FROZEN/BREACHED/EXHAUSTED prominently (quarantine-grade visibility, consistent with the
      WO-0015 deferred-flatten visibility standard); approval flow surfaces the mandatory
      disposition choices; UI issues intents via the typed API client only.
- [ ] UI holds no envelope state; refresh derives everything from the API.

## Required tests

- [ ] Integration: full loop with a stub broker — approve envelope, ticks reprice within bounds,
      fill completes envelope; both stores.
- [ ] Integration: policy raises ⇒ tick completes, other symbols processed, envelope frozen +
      event present.
- [ ] Integration: API surface — envelope list/status/approve routes; approve without dispositions
      is rejected end-to-end.
- [ ] Snapshot/unit: cockpit rendering states (whatever the existing cockpit test convention is;
      follow it, don't invent one).

## Required commands

```bash
ruff check . && ruff format --check . && mypy && lint-imports && pytest -q
```

## Notes

- Fable FULL (multi-file, interface-adjacent) though mostly consuming prior WOs' surfaces.
- Depends on WO-0016..0019 all dispositioned.
- Out of scope, log only: any store/broker change the wiring reveals as missing — NEEDS-INPUT
  back to the planning seat instead.
