# Spine v2 — Phase 4 Plan: Reconciliation Engine (§7)

Planning/characterization scaffold (agent-scoped, mirrors the wave-3c/3d/3e plan docs).
Record safety-critical conflicts before coding; flip exactly the *facts* §7 names to
`event_truth`; keep read-model columns co-written; stage each wave characterize → shadow
→ truth. Migrates `docs/MIGRATION_MATRIX.md` row **"Reconciliation"** (`partial legacy →
event_truth`) and drives the wave-3d/§8 `Reducing` hook.

> **Blocking decision gaps R1, R2, R3 gate waves 4f/4g (the FSM/startup waves). Waves
> 4a–4e + 4h are NOT gated on them and can proceed.**

## 1. Current vs target (file:line)

### What reconciliation already exists (partial-legacy)
- **Tick pipeline** — `app/monitoring.py:457` `run_monitoring_tick`: `_run_protection` →
  `_submit_pending_orders` (494) → `_redrive_stale_submitting` (689) →
  `_resolve_timeout_quarantine` (856) → `_reconcile_open_orders` (1282) →
  `_recover_unpersisted_submits` (1191).
- **Per-order open reconcile** — `_reconcile_open_orders` (`monitoring.py:1282`) polls each
  open order **one-at-a-time by `broker_order_id`** via `adapter.get_order_status`; `_apply_update`
  appends fills (dedup by `source_fill_id`), reconciles status from *recorded* fills
  (`_reconciled_status`), escalates broker>local divergence to `needs_review` (AIR-002). Keyed on
  an id we already hold — cannot discover a venue order we don't know, never queries positions.
- **Wave-3c targeted resolution** — `_resolve_timeout_quarantine` (`monitoring.py:856`): the one
  READ-ONLY targeted-query-before-REJECTED path (`get_order_by_client_order_id`). The seed Phase 4
  generalizes to the whole §7 cache-vs-venue table.
- **Stale-SUBMITTING redrive** — `_redrive_stale_submitting` (`monitoring.py:689`).
- **Durable submit-recovery ledger (D-017)** — `SubmitRecoveryRecord` (`models.py:613`) +
  `_recover_unpersisted_submits` (`monitoring.py:1191`): a narrower precursor to §7 external-order
  surfacing, keyed on a known `broker_order_id`.
- **Startup** — `main.py:78-137` lifespan: `initialize()` then unconditionally start
  `monitoring_loop`. **No startup reconcile, no gate — trading is enabled the instant the loop starts.**
- **TradingState** — `trading_state` is independent `event_truth` (`models.py:752`), but its ONLY
  writer `trading_state_change_event` (`core.py:365`) derives `to = TradingState.of(kill, pause)`
  (388) — structurally cannot emit `REDUCING` unless `buys_paused`. Nothing drives it from a
  reconcile/stream signal.
- **Reserved-but-unused** — `EventSource.RECONCILIATION`, `EventAuthority.SYNTHETIC`,
  `ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED`. No synthetic fills emitted anywhere.

### §7 requirement → gap
| §7 requirement | Current | Gap |
|---|---|---|
| Startup mass-status reconcile; fail → trading not enabled | none | new startup coroutine + gate |
| Mass order-status + position reports | adapter has submit/get-by-id/cancel/get-by-client-id only | new adapter methods |
| Targeted query before not-found→REJECTED (open poll) | only for TIMEOUT_QUARANTINE | generalize to §7 table |
| Deterministic synthetic fills for inferred facts | none; SYNTHETIC/RECONCILIATION unused | new synthetic-fill append + id scheme |
| Broker position parity (qty exact, avg-px 0.01%) | position derives from local fills only | new position-report comparison |
| External/unmanaged order surfacing | `list_external_orders` raises | new projector + facade + route |
| Stream reconnect → Reducing + reconcile | REST-poll only, no trade-update stream | R1 |
| Query throttling / 200-min budget | none | deterministic in-engine budget |
| §7 verified defaults | none in config.py | new settings |

## 2. Numbered conflicts / decision gaps (CLAUDE.md §1)

- **R1 — No trade-update stream exists; "reconnect → Reducing" has no real trigger. [BLOCKING 4g].**
  The spine is REST-poll (D-011); the only reconnect lifecycle is the *market-data* feed (a
  different stream). Options: (a) repurpose market-data DEGRADED/stale to drive Reducing; (b)
  simulate a trade-update reconnect in the **sim seam only**, defer real wiring; (c) treat every
  startup/poll-gap as the reconcile trigger. **Recommend (b)+(c)** — determinism inside the sim
  seam (§12); real trade-update stream deferred with real creds.
- **R2 — Drive `trading_state → REDUCING` from reconcile without touching the booleans. [BLOCKING
  4f/4g].** The only FSM writer *derives* `to` from `TradingState.of(kill, pause)` — it cannot emit
  `REDUCING` unless `buys_paused`. Phase 4 needs a **second independent driver** (a reconcile-scoped
  `TRADING_STATE_CHANGED` with `to=REDUCING`, booleans unchanged) **plus a composition rule** so a
  later boolean-derived event doesn't clobber the reconcile-driven Reducing, and kill still dominates.
  `current_trading_state` folds latest-wins → two uncoordinated drivers race. **Recommend**: effective
  state = `max(boolean_derived, reconcile_driven)` with `Halted > Reducing > Active`, folded from BOTH
  event kinds. Changes the FSM driver model — rule before coding 4f/4g.
- **R3 — What is "trading not enabled" on reconcile failure? [RULED: `Reducing` — user-confirmed].**
  §7: fail → trading not enabled. §8: Reducing is "the default under pending reconciliation" (allows
  reducing sells + cancels). **Ruling (user):** pending reconcile → `Reducing`; reconcile **failure** →
  stay `Reducing` + loud operator alert; never auto-`Active` until parity; never auto-`Halted` (so a
  held position stays exitable at boot). R1 (sim-seam + defer real trade-update stream) and R2
  (`max(boolean, reconcile)` composition, `Halted > Reducing > Active`) are adopted as recorded
  spec-derived engineering decisions.
- **R4 — §7 rows vs the repo's OrderStatus set. [record, non-blocking].** Alpaca `accepted`→our
  `SUBMITTED`; no distinct `ACCEPTED`; cancel-requested is `CANCEL_PENDING` (has a broker id, polled),
  not §7 in-flight `PENDING_CANCEL`; no primary FSM (3c-C1/3d-D6). Map: `SUBMITTED`+broker-id + absent
  + targeted-query-confirms-absent + retries-exhausted → `REJECTED`; `PARTIALLY_FILLED` same → `CANCELED`
  (fills preserved); `CANCEL_PENDING` stays on the existing poll. §6 "keep BLOCKED not optimistic-CANCELED"
  has no in-flight-PENDING_CANCEL analogue here — record, don't invent a state.
- **R5 — `open_check_open_only` mode. [to-confirm].** If the venue returns open-only, "no resolution
  — log only." Alpaca `get_orders` supports `closed`/`all`; targeted `get_order_by_client_order_id`
  already resolves absent → treat an unconfirmable absence as **log-only, never REJECTED**. Confirm SDK
  filter semantics before coding (§16 "to-confirm").
- **R6 — 200/min token-bucket. [design].** None exists (§9). Add a **deterministic in-engine budget
  counter with injected clock** (§12), shared across mass-status + targeted + position REST; skip a
  cycle when exhausted; a skipped position query is **never** read as flat.
- **R7 — Overfill-quarantine clear / reconciliation cover order. [recommend DEFER].** An autonomous
  cover BUY is capital-affecting + short-flip-adjacent. **Phase 4 delivers surfacing + operator-review
  clear only; defer any autonomous reconciliation-placed order.**
- **R8 — Synthetic `trade_id` scheme. [design].** §3: deterministic synthetic id (pure fn) so restart
  replays dedup (INV-5). **Propose** `dedupe_key = f"recon:{broker_order_id or client_order_id}:{cumulative_filled_qty}"`
  mirroring the real-fill scheme so a real-then-synthetic collision on the same shares dedups;
  `source=RECONCILIATION`, `authority=SYNTHETIC`.

## 3. Wave-by-wave plan (lowest-risk-first; each independently testable + committable + reviewable)

- **Wave 4a — Broker adapter reconciliation reports (additive, inert).** Add `list_open_orders() ->
  list[BrokerOrderReport]` + `list_positions() -> list[BrokerPositionReport]` to `BrokerAdapter`
  (`get_order_by_client_order_id` already covers targeted query). Implement on Mock + Sim first with
  seed hooks (mirror `seed_venue_order`); real `AlpacaPaperAdapter` wraps `get_orders(status=...)` /
  `get_all_positions()` behind env-gated integration tests. Nothing calls them. Corpus green.
- **Wave 4b — Pure Reconciliation engine module (deterministic, no wiring).** New `app/reconciliation.py`
  (§2 module 5): pure fns, injected clock, no IO. (local orders, positions, broker order/position
  reports, now, budget) → `ReconciliationPlan` (order transitions, inferred synthetic fills [R8],
  external orders, position mismatches, unresolved/blocked). Implements the §7 table [R4], recent-order
  protection, position tolerance (qty exact, avg-px 0.01%). Pure unit + property tests (§12).
- **Wave 4c — Store write surface: synthetic fills + external-order projector (inert scaffolding).**
  Store method to append a reconciliation-inferred synthetic FILL `ExecutionEvent`
  (`source=RECONCILIATION`, `authority=SYNTHETIC`, deterministic `dedupe_key`) via the atomic co-write
  planner pattern (mirror `plan_append_fill` / `plan_transition_order_evented`). Pure `external_orders(events)`
  projector + store query. Dual-store parity + replay-verifier extension.
- **Wave 4d — Shadow the runtime reconcile (characterize → shadow). ✅ DONE.** `_shadow_reconcile`
  runs LAST in `run_monitoring_tick` (after the legacy poll + recovery, so a surfaced divergence is one
  the per-order poll structurally can't capture), computes the `ReconciliationPlan` from the mass reports,
  and emits a single `reconcile_shadow_divergence` audit event — deduped by a content fingerprint
  (`_shadow_fingerprint`, `skipped_recent` excluded) so a persistent divergence logs once, not per tick.
  **Never flips truth** (no transition/fill/position mutation), **failure-isolated** (a raised mass report
  is caught → the cycle is skipped, never read as flat; the legacy reconcile is untouched), and **off by
  default** (`reconciliation_shadow_enabled`, `RECONCILIATION_SHADOW_ENABLED` env) so the whole existing
  corpus + any real deployment stay unperturbed until 4e adds the throttle. Pinned in
  `tests/test_spine_phase4_reconcile_shadow.py` (19 tests: inert-when-off, shadow-on-doesn't-change-legacy-
  outcome, external-order + position-mismatch surfacing without overwrite, dedup + re-log-on-change,
  both report failures skip-not-crash, pure fingerprint over all 5 categories, full payload schema).
- **Wave 4e — Runtime open-order + position reconcile → event_truth (truth flip).** Apply the plan:
  flip order status via evented transitions, append synthetic fills, surface external orders, record
  parity mismatches. Generalize targeted-query-before-not-found→REJECTED (respect
  `open_check_missing_retries`). Query throttling (R6) + position-query-failure→skip-never-flat. Add §7
  defaults to `config.py`. Migrate the wave-4d pinning tests. Matrix row → `event_truth` (runtime facts).
- **Wave 4f — Startup mass-status reconcile + "not enabled until reconcile" gate (truth) [R2, R3].**
  New startup coroutine in `main.py` lifespan: after `initialize()`, run the mass-status reconcile
  (with `reconciliation_startup_delay_secs`) **before** enabling trading; drive `trading_state → REDUCING`
  while pending (R2), lift to `ACTIVE` on parity, hold `REDUCING`+alert on failure (R3). Gate lives in
  `monitoring_loop`/startup only — `run_monitoring_tick` direct callers (the whole corpus) stay ungated.
- **Wave 4g — Stream/degradation-reconnect → Reducing + reconcile (truth) [R1, R2].** Wire the
  reconnect/degradation signal → `Reducing` + trigger a mass reconcile until parity, per R1.
- **Wave 4h — External/unmanaged order surfacing + consolidation.** Implement facade
  `list_external_orders` + read route + typed DTO over the 4c projector. Docs sweep + independent
  adversarial review (§11), oversell/short-flip focus.

## 4. §7 safeguards → test checklist
Targeted-query-before-not-found→REJECTED · recent-order protection (injected clock) ·
position-query-failure→skip-never-flat · query throttling/200-min budget · synthetic-id determinism
(INV-5, real+synthetic on same shares dedup) · position parity (qty exact, avg-px 0.01%, mismatch→needs_review
never silent overwrite) · external order never silently absorbed · startup gate (fail→not-enabled per R3;
success→Active; direct tick callers unaffected) · reconnect→Reducing (R1/R2) · memory+SQLite parity + replay ·
property/soak (§12) over interleavings asserting INV-1…INV-9; hostile cases (oversell-via-reconcile,
fill-after-reject, position-drift) as named reproducers with persisted seeds.

## 5. Deferred (out of Phase 4 scope)
Real Alpaca trade-update stream + creds (sim-seam determinism per §12; live-shadow is separate — R1) ·
autonomous reconciliation cover order (R7) · real primary/spawn FSM projector (3c-C1/3d-D6) · flatten/kill
facade migration (ADR-005 → Phase 5) · legacy read-model demotion (Phase 6).
