---
work_order: WO-0001
title: Verify Spine v2 migration is terminal — findings
verified_by: Claude (implementer)
date: 2026-07-08
verdict: NOT-TERMINAL (narrow, documented deferral)
suite_baseline: "1809 collected · 1804 passed · 5 skipped · 0 failed · 0 errors · 96.9s · GREEN"
---

# WO-0001 — Migration-terminal verification: findings

Read-only. All claims below are backed by pasted commands run against the working tree
at commit `05cb7b6` (post-install). Nothing in `app/`, `tests/`, or `docs/adr/` was modified.

## Method / commands run

```
rg -n "legacy_truth|shadow_evented|dual_write" --stats        # required marker sweep
rg -n "claim" app/ -i                                          # locate the atomic submit claim
read: app/store/core.py, app/store/memory.py, app/events/replay.py, app/config.py
python -m pytest -q  (+ --junit-xml)                           # baseline suite
```

Deviations:
- `[FABLE DEVIATION] lint-imports not runnable` — the `lint-imports` CLI is not installed in this
  sandbox (`exit 127`). The identical import contracts are asserted by `tests/test_import_boundaries.py`,
  which is GREEN in the baseline suite; that is the fallback evidence for the boundary rows.

## Marker sweep (decisive)

`rg -n "legacy_truth|shadow_evented|dual_write" --stats` → 29 matches / 14 files. In **code** (not docs),
only 3 non-live spots, and **zero `dual_write` anywhere**:

| Match | Kind | Meaning |
|---|---|---|
| `app/store/core.py:148-152` | stale comment | Describes the wave-3a *shadow* state ("fill table stays authoritative") — superseded by the wave-3a-truth flip. |
| `tests/test_spine_phase3_shadow_fills.py:3` | test docstring | Shadow-era characterization; its store hooks now **skip** (see below). |
| `tests/test_spine_v2_characterization.py:265` | test string | Characterization label `legacy_truth -> event_truth`. |

No live `legacy_truth`/`shadow_evented`/`dual_write` **flags** or **config** exist. `app/config.py` has
`reconciliation_enabled=True` and `protection_enabled=True` (operational flags) — **no shadow/dual/legacy
migration switch**.

## Per-flow verdict (all 16 matrix rows, code-verified)

| # | Flow | Matrix says | Code-verified | Evidence |
|---|---|---|---|---|
| 1 | Broker-authoritative fill ingestion | event_truth | ✅ event_truth | position folds the FILL event log; `test_spine_phase3_fill_event_truth.py` GREEN |
| 2 | Fill deduplication | event_truth | ✅ event_truth | composite dedupe_key on FILL events; `test_fill_dedup_per_order.py` GREEN |
| 3 | Overfill/negative-position | event_truth | ✅ event_truth | `test_spine_phase3b_overfill_quarantine.py` GREEN |
| 4 | Timeout/504 submit ambiguity | event_truth | ✅ event_truth | `TIMEOUT_QUARANTINE` first-write; `test_spine_phase3c_timeout_quarantine.py` GREEN |
| 5 | **Atomic submit claim** | **legacy_truth** | ✅ **legacy_truth (confirmed)** | `plan_claim_order_for_submission` sets `order.status=SUBMITTING` as the **order-row authority**; the `order_submission_claimed` event is an audit append, not the truth source. `replay.py:136-139` documents the order-status/spawn projector is **deferred** ("mirror of 3c-C5"). |
| 6 | Manual flatten | event_truth | ✅ event_truth | deny reads event_truth TradingState; `test_spine_phase3e_manual_flatten.py` GREEN |
| 7 | Emergency reduce override | event_truth | ✅ event_truth | override grant/consume events; `test_spine_phase3e_emergency_override.py` GREEN |
| 8 | Kill / TradingState | event_truth | ✅ event_truth | `TRADING_STATE_CHANGED` folded; `test_spine_phase3d_trading_state.py` GREEN |
| 9 | API routes | facade-backed | ✅ facade-backed | `test_import_boundaries.py` + `test_phase6e_command_facade.py` GREEN (lint-imports CLI unavailable — see deviation) |
| 10 | Streamlit cockpit | "likely thin / verify later" | ✅ thin, **enforced** | import contract inv #4 (cockpit imports no `app.*`) asserted by `test_import_boundaries.py` GREEN — matrix note is **stale** |
| 11 | Alpaca adapter | "concrete adapter" | ✅ SDK confined | inv #5 (alpaca SDK only in the two ports) asserted by `test_import_boundaries.py` GREEN; classifier/token-bucket/stream are feature follow-ups, not truth-migration |
| 12 | Reconciliation | event_truth | ✅ event_truth | `reconciliation_enabled=True`; `test_spine_phase4_reconcile_event_truth.py` (+6 reconcile suites) GREEN |
| 13 | Event log | "shadow (P2)" | ⚠️ **stale status** | Row describes the event log's P2 origin; flows above are event_truth. Doc residue, not live shadow. |
| 14 | In-memory/SQLite parity | replay verifier | ✅ present (KEEP) | `verify_dual_store_parity` / `verify_dual_store_readmodel_parity` in `replay.py`; `test_phase6b_readmodel_parity.py` GREEN |
| 15 | Import-linter | enforced | ✅ enforced | `test_import_boundaries.py` GREEN (CLI unavailable — deviation) |
| 16 | Auth for command endpoints | minimal actor-audit | ✅ as designed | `test_phase6c_actor_audit.py` GREEN; token gate is an accepted **post-beta** upgrade, not a migration gap |

## Residue inventory + classification

| Residue | Location | Class |
|---|---|---|
| Dual-store parity verifier (position + read-models) | `app/events/replay.py` | **KEEP** — permanent regression tooling (matrix 14/17) |
| Fill table as compatibility read-model (backfilled at init) | `app/store/*`, `app/models.py` | **KEEP** — event-reconstructable, parity-checked |
| `orders.status` / `sessions.trading_state` co-written read-model columns | `app/store/*`, `replay.py` | **KEEP** (status column tied to the item below) |
| **Order-status/spawn projector not implemented → "Atomic submit claim" stays legacy_truth** | `replay.py:136-139`; claim path | **RETIRE-CANDIDATE** — needs its own WO (event-source the order-status state machine) |
| Stale `shadow_evented` comment (pre-flip wording) | `app/store/core.py:148-152` | **RETIRE-CANDIDATE** — comment refresh (source edit is out of scope here) |
| Shadow-fills test: stale docstring + 2 skips (store hooks removed) | `tests/test_spine_phase3_shadow_fills.py` | **RETIRE-CANDIDATE** — fold into event-truth parity suite / update (test edit out of scope here) |
| Stale matrix statuses (row 13 "shadow (P2)", row 10 "verify later", row 11 framing) | `docs/MIGRATION_MATRIX.md` | **RETIRE-CANDIDATE** — doc refresh; boundaries are actually enforced |
| Migration-era docs (`SPINE_*`, phase plans, `IMPLEMENTATION_PROMPT_*`) | `docs/` | **KEEP** as historical (per migration-history.md; never delete w/o human ok) |
| Live migration/shadow feature flags | — | **ALREADY-DEAD** — none exist |

The 5 baseline skips include the 2 shadow-fills skips:
`InMemoryStateStore has no _insert_execution_event` / `SqliteStateStore has no _append_execution_event_unlocked`
— i.e. the shadow-era private store API was removed; the shadow test's introspection no longer matches the
event-truth store. Direct evidence the shadow scaffolding was superseded.

## Verdict: NOT-TERMINAL (narrow, documented deferral)

The Spine v2 migration is **substantially complete**: every safety-critical truth-routing flow
(fills, dedup, overfill, timeout, manual flatten, emergency reduce, kill/TradingState, reconciliation)
is **event_truth with dual-store parity**, all API routes are facade-backed, and the four Tier-1 import
invariants are enforced. **No live `shadow_evented`/`dual_write` scaffolding drives truth.**

It is **not strictly terminal**: one truth-routing flow — **"Atomic submit claim" (the order-status /
primary-spawn state machine)** — remains **`legacy_truth`** by an explicit, documented deferral
(`replay.py:136-139`, "order-status/spawn projector deferred, mirror of 3c-C5"). Order status
(incl. the `CREATED → SUBMITTING` claim) is table-authoritative; only its safety-critical derived
quantity (position) is projected + parity-checked.

Per WO-0001 Notes ("If NOT-TERMINAL, stop after reporting; remediation is a new planned order, not scope
creep here"), remediation — **event-sourcing the order-status/spawn state machine** — should be raised as
its own work order. No source/test/ADR edits were made here.

## Baseline suite (required evidence)

```yaml
evidence:
  phase: FULL_SUITE
  command: "python -m pytest -q  (counts via --junit-xml)"
  result: PASS
  decisive_output: "1809 collected | 1804 passed | 5 skipped | 0 failed | 0 errors | 96.9s | GREEN"
```

## fable_done

```yaml
fable_done:
  task: "WO-0001 — verify Spine v2 migration is terminal (read-only)"
  done_when_results:
    - "every matrix flow code-verified: MET — 16/16 rows table above, per-row evidence"
    - "residue inventory complete + classified: MET — KEEP/RETIRE-CANDIDATE/ALREADY-DEAD table"
    - "TERMINAL/NOT-TERMINAL verdict with evidence: MET — NOT-TERMINAL (narrow), per-flow + suite evidence"
    - "migration-history.md updated (claim->fact / NOT-TERMINAL recorded): MET — last_verified 2026-07-08 + verified finding"
    - "no source/test/ADR modified: MET — git status shows only work/active/WO-0001*/ + pkl/process/migration-history.md"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "rg marker sweep: 0 dual_write; only stale comment + test strings in code"
    - "claim path: order.status=SUBMITTING is order-row authority (memory.py/core.py); order-status projector deferred (replay.py:136-139)"
    - "baseline suite: 1804 passed / 5 skipped / 0 failed"
  deviations:
    - "lint-imports CLI unavailable in sandbox; boundary rows verified via tests/test_import_boundaries.py (GREEN)"
  status: VERIFIED   # verification task complete; finding = NOT-TERMINAL (narrow, documented deferral)
```
