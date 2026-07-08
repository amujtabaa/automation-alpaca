---
work_order: WO-0002
title: Engine layer ADR audit — findings
verified_by: Claude (implementer)
date: 2026-07-08
scope: read-only; engine layer = app/{events,policy,transitions,reconciliation,position,monitoring,strategy,strategy_loop,protection,approval}
engine_test_baseline: "157 passed / 0 failed (spine phase3b/3c/3d/3e + phase4 reconcile subset) — GREEN"
---

# WO-0002 — Engine layer ADR audit: findings

Read-only audit at commit `3989984`. Verdicts per ADR clause + spine INV, with file:line evidence.
No source/test/ADR edits.

## ADR verdicts (per clause)

### ADR-001 — Broker-authoritative overfill & quarantine → **CONFIRMED**
| Clause | Verdict | Evidence |
|---|---|---|
| Broker-authoritative overfill recorded, not rejected | CONFIRMED | `app/position.py:37,98` `apply_fill(allow_short=True)` records the short; `app/store/core.py:345` appends `fill_overfill_quarantined` |
| Primary quarantined; autonomous spawn blocked | CONFIRMED | `app/models.py:303-304` `FILL_OVERFILL_QUARANTINED`/`ORDER_INTENT_BLOCKED_QUARANTINE`; claim gate holds BUY when `symbol in quarantined_symbols(...)` — `app/store/memory.py:1146`, `app/store/sqlite.py:1904` |
| Malformed local input still rejected; dup fills idempotent | CONFIRMED | `apply_fill` rejects `new_quantity<0 and not allow_short` (`position.py:98`); dedup INV-5 (see below) |
| Quarantine derived from event log (replayable) | CONFIRMED | `list_quarantined_symbols` folds the log — `memory.py:1557`, `sqlite.py:2521` |

### ADR-002 — Timeout / 504 / ambiguous submit → **CONFIRMED**
| Clause | Verdict | Evidence |
|---|---|---|
| Ambiguous → `TIMEOUT_QUARANTINE`, no blind resubmit | CONFIRMED | `app/models.py:199-208` ("must NOT blind-resubmit… structurally unreachable by any resubmit"); status `app/models.py:367` |
| Primary BLOCKED until targeted reconcile (INV-3) | CONFIRMED | `app/store/sqlite.py:2942` raises "TIMEOUT_QUARANTINE order is unresolved (INV-3)"; transitions `app/transitions.py:71-75` |
| `client_order_id` = reconciliation key, not redrive | CONFIRMED | targeted resolve `plan_resolve_timeout_quarantine` (`sqlite.py:2325`), `timeout_quarantined_order_ids` (`sqlite.py:2352`) |

### ADR-003 — Manual flatten under Halted/Reducing → **CONFIRMED**
| Clause | Verdict | Evidence |
|---|---|---|
| Flatten denied by default in `Halted` | CONFIRMED | `plan_flatten_position` → `FlattenBlockedError` raised at creation — `app/store/sqlite.py:1612`, `app/store/memory.py:915` |
| Allowed reduce-only in `Reducing`/`Active` | CONFIRMED | gate reads trading_state + override in `plan_flatten_position` (`app/store/core.py`) |
| Emergency override → scoped Reducing, audited, single-use | CONFIRMED | `authorize_emergency_reduce_override` (`sqlite.py:2910`, `memory.py:1855`); `EMERGENCY_REDUCE_OVERRIDE(_RESOLVED)` events (`models.py:376-377`); projector `active_emergency_reduce_overrides` |

## Focus areas

| Area | Verdict | Evidence |
|---|---|---|
| Kill-switch gating of order intent | CONFIRMED | `order_intent_block_reason` (`policy.py:59`), `kill_switch_block_reason`/`session_submission_block_reason` gate the claim path (`store/core.py:1194,1264-1266`) |
| Overfill quarantine path | CONFIRMED | ADR-001 above |
| Timeout quarantine path | CONFIRMED | ADR-002 above |
| Manual-flatten routing through session control | CONFIRMED | gated at creation via `plan_flatten_position`; ADR-003 above |
| Single-writer enforcement | CONFIRMED | `policy.py`/`transitions.py`/`position.py` are **pure planners** — zero persistence (only `transitions.py:50` *comment* references the store write); mutation is store-only |
| INV-9 (acks ≠ position) | CONFIRMED | `app/events/projectors.py` folds **only FILL** events into position ("non-FILL … events are skipped", :124); SUBMITTED/ACCEPTED cannot reach the projector |
| Clock injection | **CONFIRMED (intent) / DRIFT (wording)** | Pure planners take injected `now: datetime` (`store/core.py:1731`); the impure boundary captures one centralized seam `utcnow()` (`models.py:63`) — `sqlite.py:922,1520,1849`, `monitoring.py:1396,1731`. Deterministic, but not literally "no bare datetime.now()" (the seam wraps `datetime.now`, `models.py:66`). |

INV-1/2/3/5/6/7/8 are exercised green by the phase3/phase4 suites (baseline below); INV-4 (overfill) and INV-9 verified directly above.

## Candidate new ADRs (undocumented significant decisions)

1. **Clock-seam determinism pattern** — "pure planners receive injected `now`; the impure boundary uses one centralized `utcnow()` seam." This is the *actual* determinism mechanism but isn't ADR'd, and it diverges from the literal CLAUDE.md/testing-model wording. Proposed decision: document the seam pattern (and either bless it or move to full clock injection at the boundary).
2. **Two-driver `TradingState` composition** — `compose_trading_state` (Halted > Reducing > Active; kill dominates) composing the control driver + the reconcile/startup driver. Significant safety-FSM decision, referenced in wave plans but no dedicated ADR.

(Timeout-resolution conservatism vs Nautilus is already documented in `SPINE_EXECUTION_ARCHITECTURE_v2.md §6` — spec-level, no ADR needed.)

## Boundary & stale-doc notes

- Engine planners import no `alpaca` and no store internals — consistent with the import-linter Tier-1 contracts (verified green in WO-0001 via `tests/test_import_boundaries.py`).
- **Stale doc:** `app/store/core.py:148-152` — the wave-3a `shadow_evented` comment describes pre-flip behavior (flagged in WO-0001).
- **Stale doc:** `pkl/architecture/architecture-map.md:18` calls the migration matrix "now-terminal", but WO-0001 found it NOT-TERMINAL (narrow: order-status/spawn deferred). Recommend WO-0006 reconcile.

## Baseline suite (this layer)

```yaml
evidence:
  phase: FULL_SUITE
  command: "pytest -q <engine subset: phase3b/3c/3d/3e + phase4 reconcile>"
  result: PASS
  decisive_output: "157 tests | 157 passed | 0 failed | 0 errors — GREEN"
```

## fable_done

```yaml
fable_done:
  task: "WO-0002 — engine layer ADR audit (read-only)"
  done_when_results:
    - "every ADR-001/002/003 clause + relevant INVs has a file:line verdict: MET"
    - "5 focus areas checked: MET"
    - "candidate-ADR list: MET (2 candidates + 1 already-spec'd)"
    - "boundary + clock notes; stale-doc notes: MET"
    - "engine test subset baseline: MET (157 green)"
    - "no source/test/ADR edits: MET (git status shows only work/active/WO-0002*/)"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "ADR-001/002/003 all CONFIRMED with file:line"
    - "single-writer CONFIRMED (planners pure); INV-9 CONFIRMED (FILL-only projector)"
    - "clock: CONFIRMED intent, DRIFT wording (utcnow seam + injected now)"
  status: VERIFIED   # audit complete; engine layer matches its ADRs, with 1 wording-drift + 2 candidate ADRs
```
