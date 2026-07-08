---
work_order: WO-0003
title: Adapter + Store layer ADR audit — findings
verified_by: Claude (implementer)
date: 2026-07-08
scope: read-only; adapter = app/{broker,marketdata}; store = app/{store,events}
store_test_baseline: "39 tests / 37 passed / 2 skipped / 0 failed — GREEN"
verdict: all governing clauses CONFIRMED; candidate-ADR list effectively empty
---

# WO-0003 — Adapter + Store layer ADR audit: findings

Read-only audit at commit `c6feff5` (source unchanged since `3989984`). No source/test/ADR edits.

## ADR verdicts

### ADR-001 — overfill/quarantine (store side) → **CONFIRMED**
- Store records broker-authoritative overfill (`apply_fill(allow_short=True)`, `position.py:98`) + `fill_overfill_quarantined` event (`store/core.py:345`), quarantine derived from the log (`quarantined_symbols`). (Detail in WO-0002.)

### ADR-002 — timeout / ambiguous submit (adapter side) → **CONFIRMED**
| Clause | Verdict | Evidence |
|---|---|---|
| Stable `client_order_id` = deterministic reconciliation key, not blind-redrive | CONFIRMED | `client_order_id=order.id` (internal uuid, minted once + persisted) on every submit — `app/broker/alpaca_paper.py:239,249`, `app/monitoring.py:1100,1581`; never regenerated |
| Duplicate client-order lookup recovers existing venue order without new submit | CONFIRMED | on 409/422 duplicate, recovers via `get_order_by_client_order_id(order.id)` instead of resubmitting — `alpaca_paper.py:258-275` |
| Ambiguous outcome classified, not resubmitted | CONFIRMED | `AmbiguousBrokerError` classification (ADR-002/§6); resolution is read-only targeted query |

### ADR-004 — event-log-as-truth (store) → **CONFIRMED (for migrated flows)**
| Clause | Verdict | Evidence |
|---|---|---|
| First durable write is an `ExecutionEvent`; append-only | CONFIRMED | events table append-only — **no `UPDATE`/`DELETE`** on it (`sqlite.py`); INSERT with `dedupe_key TEXT UNIQUE` (`sqlite.py:319`) |
| Idempotent dedup (INV-5) | CONFIRMED | deterministic keys `fill:{order_id}:{source_fill_id}` (`core.py:191`), `{status}:{order.id}`, `reconcile_resolve:...`; duplicate = no-op (`sqlite.py:473`) |
| Replay reproduces projection; dual-store parity | CONFIRMED | `project_symbol_position`/`project_read_models` (`events/projectors.py`,`replay.py:166`); `verify_dual_store_parity`/`verify_dual_store_readmodel_parity` (`replay.py:108,236`) |
| Legacy tables are read-models only | CONFIRMED w/ WO-0001 caveat | position/quarantine/trading-state demoted + parity-checked; **order-status column still legacy_truth (projector deferred)** — the one NOT-TERMINAL flow (WO-0001 / WO-0007) |

## Focus areas
| Area | Verdict | Evidence |
|---|---|---|
| alpaca-py imported ONLY in adapter | CONFIRMED | `import alpaca`/`from alpaca` appears solely in `app/broker/alpaca_paper.py` + `app/marketdata/alpaca_stream.py` (inv #5 / ADR-006) |
| Deterministic `client_order_id` | CONFIRMED | `= order.id`, stable per order (see ADR-002) |
| Event-log append-only truth | CONFIRMED | no UPDATE/DELETE on events; UNIQUE dedupe_key |
| Fill dedup | CONFIRMED | INV-5 keys above |
| Projection correctness | CONFIRMED | FILL-only position fold; read-model projector |
| Parity verifier status | CONFIRMED (KEEP) | dual-store position + read-model parity verifiers present |

## Candidate new ADRs
- **Effectively empty.** The one notable un-ADR'd choice — "use the internal order uuid (`order.id`) as the venue `client_order_id` idempotency key" — is a faithful realization of ADR-002 and needs no separate ADR (optionally a one-line note in ADR-002). No other undocumented significant decisions in this layer.

## Boundary & stale-doc notes
- Adapter/store boundary clean: only the two ports import alpaca (import-linter inv #5, green in WO-0001).
- **Stale:** `app/store/core.py:148-152` wave-3a `shadow_evented` comment (pre-flip); the `tests/test_spine_phase3_shadow_fills.py` docstring + 2 skips (superseded store hooks). (Flagged WO-0001/0002.)

## Baseline suite (this layer)
```yaml
evidence:
  phase: FULL_SUITE
  command: "pytest -q <store subset: fill_event_truth, fill_dedup, readmodel_parity, shadow_fills>"
  result: PASS
  decisive_output: "39 tests | 37 passed | 2 skipped | 0 failed — GREEN"
```

## fable_done
```yaml
fable_done:
  task: "WO-0003 — adapter + store layer ADR audit (read-only)"
  done_when_results:
    - "every ADR-001/002/004 clause has a file:line verdict: MET"
    - "6 focus areas checked: MET (all CONFIRMED)"
    - "candidate-ADR list: MET (effectively empty; stated explicitly)"
    - "boundary + stale-doc notes: MET"
    - "store test subset baseline: MET (37/39 GREEN)"
    - "no source/test/ADR edits: MET"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "alpaca isolation CONFIRMED (broker/marketdata only)"
    - "client_order_id=order.id stable key (alpaca_paper.py:239,271); append-only log; UNIQUE dedupe_key"
  status: VERIFIED   # adapter/store match ADR-001/002/004; only carried-over NOT-TERMINAL order-status caveat
```
