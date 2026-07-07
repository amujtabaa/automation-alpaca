# Spine v2 — Wave 4e Plan: Runtime reconcile → `event_truth` (§7 truth flip)

Planning/characterization scaffold (mirrors the wave-3c/3d/3e + Phase-4 plan docs). Wave 4e is
**the big Phase-4 truth flip**: it turns the wave-4d SHADOW mass-report reconcile into an ACTING
reconcile that changes state through the single-writer store, adding the §7 capabilities the legacy
per-order poll structurally cannot provide. Record safety-critical conflicts before coding; flip
exactly the *facts* §7 names; keep read-model columns co-written; stage as slices
characterize → additive → truth. Migrates `docs/MIGRATION_MATRIX.md` **"Reconciliation"** row from
`partial legacy (P4 wave 4d shadow)` → `event_truth` (runtime facts).

> **Safety framing.** Every new action in 4e is on a path where a mistake is an oversell / stranded
> long / short-flip. The load-bearing safeguard is **targeted-query-before-any-not-found→terminal**
> (§7 / R5) — a mass-report *absence* is NEVER a reject on its own. The pure engine already encodes
> this (absence → `needs_targeted_query`, never a resolution); 4e's impure caller owns the retry
> budget + the read-only targeted query, reusing the wave-3c machinery.

## 1. Current vs target (file:line)

### What the runtime reconcile does today (partial-legacy + 4d shadow)
- **Per-order poll (the fill workhorse)** — `_reconcile_open_orders` (`monitoring.py:1289`): for each
  local open order **that already holds a `broker_order_id`**, `adapter.get_order_status(id)` → `_apply_update`
  appends fills (dedup by `source_fill_id`), reconciles status from *recorded* fills (`_reconciled_status`),
  escalates broker>local divergence to a `needs_review` record (AIR-002). **Cannot discover a venue order
  we don't know; never queries positions; an order absent from the venue is simply left open** (it just
  stops getting fills). This stays — it is the fill-ingestion path.
- **Targeted-query resolution (wave 3c)** — `_resolve_timeout_quarantine` (`monitoring.py:863`): the one
  READ-ONLY targeted-query-before-REJECTED path, but scoped to `TIMEOUT_QUARANTINE` orders only. Reusable
  machinery: `get_order_by_client_order_id`, `_order_deferral_count(store, id, reason)`,
  `_record_timeout_query_deferral(..., needs_review=)`, the clean-terminal-vs-adopt-as-SUBMITTED rule
  (`_QUARANTINE_TERMINAL_RESOLUTIONS`), the separate not-found vs query-error counters.
- **Shadow mass-report reconcile (wave 4d)** — `_shadow_reconcile` (`monitoring.py:~1586`): computes
  `plan_reconciliation` from `list_open_orders`/`list_positions` each tick and emits a
  `reconcile_shadow_divergence` audit event; **off by default; flips no truth.** 4e turns this into action.
- **Pure engine (wave 4b)** — `plan_reconciliation` (`reconciliation.py`): already emits
  `resolutions` (cancel/reject only), `inferred_fills` (priced, dedup-safe), `needs_targeted_query`,
  `external_orders`, `position_mismatches`, `skipped_recent`. **The decision logic 4e applies already exists.**
- **Synthetic-fill append (wave 4c)** — `append_fill(..., source=RECONCILIATION, authority=SYNTHETIC)`:
  the write surface for an inferred fill; identity = the execution's own `source_fill_id` (dedups with the
  real poll, INV-5). Nothing emits synthetic fills yet — 4e wires it.
- **Config** — `config.py`: has poll cadence, unfilled timeout, `timeout_quarantine_max_query_attempts`,
  `reconciliation_shadow_enabled` (4d). **No §7 defaults, no query budget.**

### §7 requirement → gap 4e closes
| §7 requirement | Today | 4e |
|---|---|---|
| Not-found (open order absent) → targeted-query-before-REJECTED/CANCELED | only for `TIMEOUT_QUARANTINE` | generalize to `SUBMITTED`/`PARTIALLY_FILLED` open orders (R4 map) |
| External/unmanaged order surfacing | `list_external_orders` raises | durable record + audit (route/DTO deferred to 4h) |
| Broker position parity (qty exact, avg-px 0.01%) | none | `needs_review` record, never overwrite |
| Deterministic synthetic fills for inferred facts | append surface only (4c) | wire plan.inferred_fills → `append_fill(SYNTHETIC)` |
| Query throttle / 200-min budget | none | deterministic in-engine token bucket (injected clock) |
| position-query-failure → skip, never flat | n/a (no position query) | a raised `list_positions` skips parity that cycle |
| §7 verified defaults | none | `config.py` |

## 2. Numbered conflicts / decision gaps (record before coding; CLAUDE.md §1)

- **E1 — Double-actor: per-order poll vs mass-report reconcile on the SAME order. [design, load-bearing].**
  Both could touch a known open order in one tick. Rule: the mass-report reconcile ACTS only on the cases
  the per-order poll *cannot* handle — (a) an open order **absent** from the mass report (→ targeted query),
  (b) **external** orders, (c) **position parity**. For an order **present** in the mass report, status +
  fills stay the per-order poll's job (the pure engine's `resolutions` are cancel/reject-only and its
  `inferred_fills` only fire when the report carries priced executions — Alpaca `get_orders` does **not**,
  so in practice mass-report `inferred_fills` are empty against the real adapter and the fill delta routes
  to `needs_targeted_query` → the per-order poll). Ordering: run the mass-report reconcile’s not-found
  resolution **after** the per-order poll + `_resolve_timeout_quarantine`, and **recent-order protection**
  (injected `now`, ≥ threshold) keeps it off orders the poll just touched. **Never resolve an order the
  per-order poll is mid-ingesting.**
- **E2 — `open_check_open_only` (R5). [load-bearing safeguard].** Alpaca `get_orders(status=OPEN)` returns
  **open-only**, so an order absent from `list_open_orders` may be *closed* (filled/canceled) OR *never
  landed* — indistinguishable from the mass report alone. Therefore **absence NEVER rejects**: it triggers
  the read-only `get_order_by_client_order_id` targeted query (which distinguishes working/filled/canceled/
  rejected/absent), bounded by `open_check_missing_retries`, exactly like wave 3c. This is the single most
  important 4e safeguard.
- **E3 — Not-found → terminal mapping (R4). [record].** Reusing the wave-3c resolution:
  `SUBMITTED`+absent+targeted-confirms-absent+retries-exhausted → `REJECTED`; `PARTIALLY_FILLED` same →
  `CANCELED` (fills preserved — adopt-as-SUBMITTED first if the targeted query still reports fills, so the
  poll ingests them; INV-9). `CANCEL_PENDING` is left to the existing poll (already being wound down). No
  new order state invented (no primary FSM — 3c-C1/3d-D6).
- **E4 — Where does the flip live? [design].** 4d's `_shadow_reconcile` stays as the plan computation;
  add `_apply_reconciliation` that ACTS on the plan. Gate: rename intent — a new `reconciliation_enabled`
  (default **True**, `RECONCILIATION_ENABLED` env) supersedes `reconciliation_shadow_enabled` for the
  ACTING path; the shadow-only flag is retired/folded. `run_monitoring_tick` calls the acting reconcile
  (with the throttle) instead of the shadow. Direct `run_monitoring_tick` callers (the corpus) — the
  acting reconcile must be **inert when there is nothing to reconcile** (empty mass reports on the mock =
  every local open order → `needs_targeted_query`!). **→ E5.**
- **E5 — Corpus inertness under an unseeded mock. [load-bearing test-safety].** The mock's default
  `list_open_orders`/`list_positions` return `[]`. With the acting reconcile ON by default, EVERY existing
  monitoring test with an open order would drive a targeted query + eventually REJECT it, and every test
  with a position would log a parity mismatch — a mass corpus break. Options: (a) default the acting
  reconcile **off**, opt-in per test (safest, but then it never runs in prod either — bad); (b) make the
  targeted-query path **require the order to be genuinely absent AND past recent-order protection AND
  past N retries** — but an unseeded mock still eventually rejects; (c) **the mock/sim default
  `list_open_orders` returns the adapter's known live orders** (mirror `_broker_ids`) so an order the
  test submitted is reported open by default, and only an explicitly-seeded absence triggers not-found.
  **Recommend (c)** — makes the mock's mass report *consistent with its own submit state* by default, so
  the acting reconcile is naturally inert for the corpus (no order is spuriously absent) and tests opt into
  divergence by seeding. This is an adapter-test-fidelity fix, not a production behavior change. Confirm no
  existing test asserts `list_open_orders()==[]` after a submit (the 4a tests seed explicitly). **Decision
  gate before coding 4e-2.**
- **E6 — Query throttle scope (R6). [design].** A deterministic per-minute token bucket (injected clock,
  §12) shared across mass-status + targeted + position REST. When exhausted: **skip the cycle** (never a
  partial/なし read). A skipped position query is **never** read as flat (E7). Budget default from §7-ish
  200/min; the per-order poll's existing calls are out of scope for this bucket in 4e (record).
- **E7 — position-query-failure → skip-never-flat. [safeguard].** A raised `list_positions` (or an
  exhausted budget) skips the parity check that cycle — it is NEVER read as "flat" (that would mask a real
  long). Already the 4d shadow's failure-isolation stance; 4e keeps it and adds the throttle-skip.
- **E8 — External-order surfacing durability. [scope].** 4e records external orders durably (audit event
  keyed by `broker_order_id`, deduped like the shadow fingerprint / once-per-id) so 4h's route/DTO can read
  them; the `list_external_orders` projector + facade + route is **4h**. 4e does NOT place any autonomous
  cover/cancel for an external order (R7 — defer).
- **E9 — Parity mismatch action. [scope].** A `position_mismatch` → a durable `needs_review` audit record
  (once per `{symbol, kind}` until it clears), **never** a position overwrite (Rule 7 / INV-1). No
  autonomous correction (R7).

## 3. Slice plan (lowest-risk-first; each committable + reviewable)

- **Slice 4e-1 — §7 config defaults + deterministic query-budget token bucket (additive, inert).**
  Add `config.py`: `reconciliation_enabled` (default True), `reconcile_recent_threshold_ms`,
  `reconcile_avg_price_tolerance`, `reconcile_open_check_missing_retries`, `reconcile_query_budget_per_min`,
  (record `reconciliation_startup_delay_secs` for 4f). New pure `ReconcileQueryBudget` (injected clock,
  per-minute bucket) with unit + property tests. Nothing wired. Corpus green.
- **Slice 4e-2 — Adapter mass-report fidelity (E5) + acting reconcile skeleton behind the flag.** Make
  mock/sim `list_open_orders` default to the adapter's known-live orders (so the corpus is inert), add the
  4a-style tests. Add `_apply_reconciliation` that computes the plan and, for now, ONLY surfaces external
  orders + parity mismatches as durable `needs_review` audit records (deduped) — the LEAST-risk actions
  first (no order-state change yet). Wire it into the tick under `reconciliation_enabled`. Migrate the
  wave-4d shadow tests (shadow-divergence event → the acting records). Matrix stays partial-legacy.
- **Slice 4e-3 — Not-found → targeted-query-before-terminal (the oversell-critical flip).** Generalize the
  wave-3c targeted-query resolution to non-quarantined open orders absent from the mass report (E2/E3),
  reusing `get_order_by_client_order_id` + the deferral counters + `open_check_missing_retries`. Adopt-as-
  SUBMITTED when the targeted query still reports fills (INV-9); REJECTED/CANCELED only on confirmed-absent
  + retries-exhausted. Property-test the no-premature-reject invariant over interleavings.
- **Slice 4e-4 — Synthetic fills wiring (INV-5/R8) + query throttle wiring (E6/E7).** Wire
  `plan.inferred_fills` → `append_fill(SYNTHETIC)` (guard: only when a priced execution covers the delta —
  never a $0 fill; the real adapter path stays needs_targeted_query). Wire the token bucket around the mass
  + targeted + position REST; exhaustion/failure → skip-never-flat. Migrate the pinning tests.
- **Slice 4e-5 — Matrix flip + gate + adversarial review.** Flip the "Reconciliation" row to `event_truth`
  once the 6 migration-rule conditions hold. Full gate (suite/coverage/parity/harness/ruff) + the **heavier
  Phase-4 adversarial review** (Opus workflow, concentrated on E2/E3 oversell + E1 double-actor + E5
  corpus-inertness), remediate, commit, push.

## 4. §7 safeguards → test checklist
Targeted-query-before-not-found→REJECTED (E2) · recent-order protection (injected clock, E1) ·
position-query-failure/throttle-exhaustion → skip-never-flat (E7) · query throttle determinism (E6) ·
synthetic-id determinism (real+synthetic dedup, INV-5) · position parity (qty exact, avg-px 0.01%,
mismatch → needs_review never overwrite, E9) · external order never silently absorbed (E8) · corpus inert
under the fidelity fix (E5) · double-actor non-interference (E1) · memory+SQLite parity + replay ·
property/soak over interleavings asserting INV-1…INV-9; hostile reproducers (oversell-via-reconcile,
fill-after-reject, position-drift) with persisted seeds.

## 5. Deferred (out of 4e)
Startup mass reconcile + not-enabled-until-reconcile gate + `trading_state → REDUCING` (**4f**, R2/R3) ·
reconnect → Reducing (**4g**, R1) · external-order route/DTO + `list_external_orders` projector/facade
(**4h**) · autonomous cover/cancel for external orders + parity correction (**R7**) · real trade-update
stream (deferred, R1) · flatten/kill facade migration (Phase 5) · legacy read-model demotion (Phase 6).
