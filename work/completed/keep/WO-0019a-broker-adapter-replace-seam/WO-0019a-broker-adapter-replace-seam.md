---
type: Work Order
title: Broker-adapter replace/edit seam (pre-requisite for WO-0019, ADR-010 §1)
status: CLOSED
work_order_id: WO-0019a
wave: W3
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT]
record_reconciliation: "WO-0120 (2026-07-20) verified fable-done.md status VERIFIED and the existing WO-0019a DISPOSED ledger row; a canonical CLOSED ledger row is appended."
owner: Ameen (human-gated: order submission / cancel-replace surface)
created: 2026-07-11
---

# Work Order: Broker-adapter replace/edit seam

## Why this exists

The WO-0019 tripwire fired: no `BrokerAdapter` method exposes venue-side replace/edit
(`adapter.py` has submit/status/cancel/get-by-client-id/list only), and WO-0019 forbids
`app/broker/**`. The pinned alpaca-py (0.43.5) DOES provide
`TradingClient.replace_order_by_id`. Without this seam, envelope repricing degrades to
cancel+resubmit pairs — two venue round-trips with a no-order/double-order race window in thin
books, exactly what the envelope executor exists to avoid.

## Goal

Add `replace_order` to the `BrokerAdapter` ABC and all three concrete adapters, with the same
ambiguity discipline as submit (ADR-002): a timeout/ambiguous replace outcome must be
quarantinable, never blind-retried.

## Context packet

- `docs/adr/ADR-002-*` (ambiguous-outcome discipline), ADR-010 §1
- `app/broker/adapter.py` — the ABC + report shapes
- `app/broker/alpaca_paper.py` — SDK call conventions, D-017 client_order_id discipline,
  `work/review/FINDING-alpaca-adapter-wrong-sdk-method.md` (this surface's review debt)
- `app/broker/mock.py`, `app/broker/sim.py` — deterministic test/sim behavior incl. chaos hooks

## Allowed paths

```yaml
allowed_paths:
  - app/broker/**
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**
  - app/monitoring.py
  - app/sellside/**
  - app/api/**
  - app/facade/**
  - cockpit/**
```

## Required behavior

- [ ] `BrokerAdapter.replace_order(broker_order_id, *, limit_price=None, quantity=None,
      client_order_id) -> str` (returns the NEW broker order id — Alpaca's replace creates a
      replacement order): abstract on the ABC, implemented in alpaca_paper (via
      `replace_order_by_id`), mock, and sim (sim: chaos-injectable like submit/cancel).
- [ ] Deterministic `client_order_id` threading on the replacement (the reconcile-by-client-id
      recovery must cover an ambiguous replace exactly like an ambiguous submit).
- [ ] Ambiguous outcome (timeout/transport/5xx) raises the SAME error taxonomy as submit_order so
      WO-0019's engine seam can TIMEOUT_QUARANTINE the working order — never blind-resubmit or
      blind-re-replace.
- [ ] Mocked-SDK unit tests assert the REAL SDK method name is invoked
      (`replace_order_by_id`) — the FINDING's X-002 regression pattern.
- [ ] No live/paper network calls in the standard suite (keyless skips as today).

## Required commands

```bash
ruff check . && ruff format --check . && mypy && lint-imports && pytest -q
```

## Notes

- Human-gated (cancel/replace surface): plan pauses for approval; queues for independent
  cross-model review alongside the FINDING remediation already noted for this file.
- WO-0019 remains blocked until this is dispositioned; its own gate (T3) then proceeds unchanged.
- Alternative the human may choose instead: descope W3 repricing to cancel+resubmit pairs via the
  existing surface (no broker change; worse thin-book semantics; WO-0019 proceeds today).
