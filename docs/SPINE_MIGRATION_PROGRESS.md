# Spine v2 Migration — Progress Ledger (resumable state of work)

**This file is the single source of truth for "where are we in the migration."**
It exists so that work can be *resumed* after a usage-budget refresh or a new
session without re-deriving context. Update it at every checkpoint commit.

Branch: `claude/confident-babbage-ti5cm8`.
Roadmap: `docs/REARCHITECTURE_ROADMAP.md` (phases 0→6).
Operating contract: root `CLAUDE.md`. Phase gate discipline: one phase, stop
for review at each boundary. External independent review is an outstanding gap
for every phase so far (proceeding was explicitly user-authorized).

---

## How to resume

1. Read root `CLAUDE.md` + the canonical read-order docs it `@`-imports.
2. Read this ledger's **Current position** below.
3. Run the suite to confirm a green baseline:
   ```
   TMPDIR="$PWD/.pytest-tmp" PYTHONPATH="$PWD" python -m pytest \
     --basetemp=.pytest-tmp -p no:cacheprovider -q -o addopts=""
   ```
   and the harness smoke checks:
   ```
   python harness/check_claude_imports.py
   python harness/check_stale_prompt_links.py
   ```
4. Pick up at the first unchecked box under **Current position**.

---

## Phase status summary

| Phase | Title | Status |
|---|---|---|
| 0 | Docs, inventory, migration seams | ✅ done (`7a25649`) — report: `docs/SPINE_PHASE0_INVENTORY.md`, `docs/SPINE_PHASE0_MIGRATION_PLAN.md` |
| 1 | Facade shell + characterization | ✅ done (`d146e0e`, `afe8543`) — report: `docs/SPINE_PHASE1_FACADE_REPORT.md` |
| 2 | Event schema + replay scaffolding | ✅ done (`7ba8dd0`…`60d38a0`) — report: `docs/SPINE_PHASE2_EVENT_LOG_REPORT.md` |
| 3 | Safety-critical event-first migration | ✅ safety flows done (waves 3a/3b/3c/3d/3e, all reviewed+remediated). Deferred to later phases: flatten facade migration (→ Phase 5/API-routes), reconciliation-driven Reducing (→ Phase 4), spawn/order projectors (→ Phase 4) |
| 4 | Reconciliation engine | ⬜ not started |
| 5 | Import-boundary enforcement | ⬜ not started |
| 6 | Legacy table demotion/removal | ⬜ not started |

---

## Phase 2 — Event schema + replay scaffolding — ✅ CLOSED

All substeps done; adversarial review (workflow `w32i9qgc8`, 4 lenses +
synthesis) returned **safe to finalize**; 5 low/nit findings applied (see
`docs/SPINE_PHASE2_EVENT_LOG_REPORT.md` §6). Commits: `7ba8dd0` (log + projector
+ replay), `b0434f3` (coverage→100%), `b46b83b` (matrix/report/ledger),
`60d38a0` (review remediation). Full suite green, `app/events/` 100%.

Locked design decisions (kept, for the record): `ExecutionEvent` is distinct
from the audit `Event`; Phase 2 is additive/shadow (no `event_truth` flip, no
production writer); the projector reuses `apply_fill` (formula single-sourced);
primary/spawn/TradingState projectors deferred to Phase 3 (recorded per the
CLAUDE.md conflict rule, not silently picked).

---

## Current position: Phase 3 — Safety-critical event-first migration

**The largest phase and the first that CHANGES behavior.** It resolves the
ADR-001/002/003 conflicts characterized in Phase 0 by making the event log
authoritative for migrated flows. Break into sub-waves; each wave:
characterize → implement → adversarial-verify → report → commit.

**Planned sub-wave order (lowest-risk first):**

- [x] **Wave 3a-shadow — broker-authoritative fill ingestion + dedup →
      `shadow_evented`** (Decision 1 / INV-5). `append_fill` now also appends a
      broker-authoritative `FILL` `ExecutionEvent` atomically with the fill row
      (both stores, via extracted unlocked/cursor helpers); the replay
      projection is proven == the fill-table position, dual-store parity holds,
      dupe/reject paths emit nothing. Additive — full suite green, no behavior
      change to position derivation. `tests/test_spine_phase3_shadow_fills.py`.
      Fill ingestion is `shadow_evented` in the matrix. **Adversarial review
      (workflow `wub26fmm1`, 4 lenses + synthesis, fault-injection verified):
      safe to finalize — 0 correctness defects; 3 test-hardening findings
      applied (fault-injection atomicity guard [mutation-tested live],
      multi-symbol/fold-to-flat parity, SELL-event price assertion), 1 future
      backfill note recorded above.** Commits `bf60d74` + `e7c423c`.
- [x] **Wave 3a-truth — flip fill ingestion to `event_truth`.** Position is now
      derived from the event log (`project_symbol_position` folds the symbol's
      `FILL` events) in BOTH stores; the fill table is a compatibility
      read-model. Backfill at `initialize()` emits a `FILL` event per
      pre-wave-3a fill row (idempotent, 1:1 in append order). Behavior-preserving
      (whole position/fill/monitoring/routes/Hypothesis corpus green =
      characterization, matrix rule 4); truth proven to have moved
      (`tests/test_spine_phase3_fill_event_truth.py`: a FILL event with no fill
      row moves position; backfill covers orphan fills). Matrix rules 2/3
      satisfied (backfill + dual-store parity). Fill ingestion + dedup are
      `event_truth`. **Note:** fill + event are written in one atomic block
      (event authoritative, fill table a read-model); `prior_filled`/dedup
      accounting still read the fill-table read-model (accurate, lower-risk —
      not a position-truth concern). **Adversarial review (`wojsqwhiq`) caught a
      BLOCKER + MEDIUMs, all fixed + regression-tested (`5fdc993`):**
      the initial count/offset backfill was INVERTED (pre-shadow fills are a
      prefix, not a suffix) — replaced with an additive, identity-matched
      backfill that appends each fill's event through the deduped writer (never
      deletes an event-only reconciliation fill); null-source fills now carry a
      deterministic `fill:{order_id}:@{fill.id}` key so they are matchable.
      Blocker reproduced firsthand (qty 200→400) + mutation-tested. Also flipped
      `current_exposure`/`close_session` symbol enumeration to the event log
      (both stores agree) and added `idx_exec_events_symbol_type`. The
      behavior-preservation lens found the core flip sound (0 defects).
      - **Still open for wave 3b — ADR-001 oversell tolerance:** the projector's
        `apply_fill` reject-by-raise (comment at `app/events/projectors.py`)
        must become quarantine-tolerant once broker-authoritative overfills can
        be recorded, else a recorded oversell aborts the whole replay.
- [x] **Wave 3b — overfill / negative-position quarantine** (ADR-001).
      - [x] **Part 1 — projector oversell-tolerance + quarantine detection**
        (`563ed4d`). `apply_fill(..., allow_short=True)` records a crossing
        sell as a negative position instead of raising (the default still raises
        — the long-only backstop for *local* input is preserved); the
        projector uses it (a recorded broker FILL is a fact to project, not an
        error). `quarantined_symbols(events)` flags any symbol whose event-log
        position is negative. **Additive/inert on the live path** — nothing
        records an oversell yet (`append_fill` still rejects local negatives), so
        the whole position/fill corpus stays green.
        `tests/test_spine_phase3b_overfill_quarantine.py`.
      - [x] **Part 2 — record path + block** (`fa6e72a`). `append_fill`
        now RECORDS a *broker-authoritative* overfill (a SELL crossing long-only
        through flat) — `plan_append_fill` step 5+6 appends the fill row + a
        `fill_overfill_quarantined` audit event + the broker-authoritative `FILL`
        `ExecutionEvent`, all atomically — instead of reject-and-drop. Intrinsic
        malformed-input rejects (`fill_value_reason`: non-positive qty/price,
        cumulative-over-order, symbol/side mismatch) are UNCHANGED and still
        reject. Both stores gained `list_quarantined_symbols()` (derived from the
        event log via `quarantined_symbols`); `create_order_for_candidate` passes
        `quarantined=` to the planner, which blocks autonomous BUY intent for a
        quarantined symbol (`order_intent_blocked_quarantine` audit event,
        `OrderIntentBlockedError`). Position now derives the recorded short
        (`get_position` returns negative). Characterization + parity tests
        migrated (reject→record): `test_spine_v2_characterization`,
        `test_sqlite_store`, `test_input_validation`, `test_position_folding`,
        `test_store_core`; the "reject→no shadow event" property re-pinned via a
        still-rejected `InvalidFillError` path in `test_spine_phase3_shadow_fills`.
        Replay reproduces the quarantine per-store and across memory+SQLite
        (ADR-001 required test). Full suite green (1441 passed), coverage 95.65%.
        Fill overfill / negative-position handling is `event_truth`. Commits
        `fa6e72a` + ledger `1d768b7`.
      - [x] **Part 2 fix — adversarial-review remediation** (`44f4592`).
        Review workflow `w0mjp9fx2` (4 lenses + synthesis, mutation-verified)
        returned **FIX_REQUIRED** with two coupled defects, both fixed +
        regression-tested:
        - **HIGH — quarantine was memoryless.** `quarantined_symbols` keyed off
          the *current* projected sign (`quantity < 0`), so a covering BUY fill
          (a pre-existing order, a reconciliation cover) that lifted the short
          back to ≥0 silently un-quarantined the symbol and resumed autonomous
          trading with no review — an ADR-001 violation ("must not continue
          autonomous trading from such a state"). Fixed: **latch to the fold
          history** — a symbol is quarantined once its FILL fold ever crosses
          negative, durable/replay-stable, cleared only by a future audited
          reconciliation (Phase 4). Also **gated the submission-claim path**
          (`plan_claim_order_for_submission` + both stores) so a *pre-existing*
          CREATED autonomous BUY for a quarantined symbol is HELD
          (`symbol_quarantined`), not just newly-created intent; protective/
          flatten SELLs stay exempt (exits allowed).
        - **MEDIUM — `apply_fill` cost-basis corruption on short recovery.** The
          BUY branch accumulated `cost_basis` additively over a zeroed short base,
          so a symbol that crossed through flat and returned long derived a wrong
          `average_price`/`cost_basis` (inflated CAPI exposure). Fixed: covering a
          short re-establishes basis from the covering fill alone; behavior-
          preserving for every normal (non-short) fold.
        - **LOW — overfill idempotency untested.** Added a replayed-overfill
          idempotency test (INV-5 on the record path) + short-recovery cost-basis
          + durable-latch + claim-hold tests. Full suite green (1455 passed),
          coverage 95.70%. **Re-review (`w587o6zou`, 3 lenses + synthesis,
          3 mutations each caught): `FIX_COMPLETE` — D1 + D2 both fully closed,
          0 confirmed findings, no new BLOCKER/HIGH.** Commit `44f4592` + ledger
          `7731f6d`. ✅ Wave 3b is independently reviewed clean.
- [~] **Wave 3c — timeout/504 `TIMEOUT_QUARANTINE`** (ADR-002). Replace blind
      redrive (characterized in `tests/test_spine_v2_characterization.py`
      Flow 2) with quarantine + targeted reconcile-by-`client_order_id`. **Design
      + recorded conflicts (C1–C6): `docs/SPINE_WAVE3C_PLAN.md`** (mapped by a Plan
      agent over the submit/recovery/adapter path; Phase-3/Phase-4 boundary set —
      wave 3c does a single-order read-only targeted query, defers the mass
      reconcile engine to Phase 4).
      - [x] **Part 1 — inert scaffolding** (`4bf6362`).
        `OrderStatus.TIMEOUT_QUARANTINE` (+ `SUBMITTING→TQ`, `TQ→{SUBMITTED,
        REJECTED,CANCELED}` transitions) + audit `EventType`s
        (`order_timeout_quarantined`/`_resolved`/`_deferred`); `AmbiguousBrokerError`
        (a `BrokerError` subclass); read-only `get_order_by_client_order_id` on the
        interface + alpaca/mock/sim (+ `seed_venue_order`/`fail_next_client_query`
        + `BrokerOrderUpdate.broker_order_id`); shared `plan_transition_order_evented`
        + `plan_quarantine_timed_out_order`/`plan_resolve_timeout_quarantine` in
        core.py; store `quarantine_timed_out_order`/`resolve_timeout_quarantine`/
        `list_timeout_quarantined_orders` (both stores, co-write ExecutionEvent +
        audit + row flip atomically); `timeout_quarantined_order_ids` projector
        (latest-lifecycle-event-wins, event-truth). Additive/inert — nothing routes
        to it; full corpus green (1455) + 27 new tests
        (`tests/test_spine_phase3c_timeout_quarantine.py`); coverage 95.42%.
      - [x] **Part 2 — wiring** (`e148876`). Monitoring routes
        `AmbiguousBrokerError` → `quarantine_timed_out_order` at BOTH submit choke
        points (`_submit_pending_orders` guard placed BEFORE the generic release;
        `_redrive_stale_submitting`); new `_resolve_timeout_quarantine` tick step
        (after redrive, before reconcile) does the read-only targeted query →
        SUBMITTED (working/filled, reconcile ingests fills via SUBMITTED — INV-9) /
        CANCELED / REJECTED (bounded confirmed-absent) / manual-review (persistent
        inconclusive, `needs_review` deferral). Adapter `submit_order` classifies
        504/5xx/timeout → `AmbiguousBrokerError`, 429 stays transient (C2). Config
        `timeout_quarantine_max_query_attempts` (default 3). Operator surfacing:
        `operational_status_for` → `timeout_quarantine`; the manual-cancel route
        **refuses** a quarantined order (409 — a local cancel of a possibly-live
        order is an oversell path). Flow-2 characterization migrated
        (`TestCharacterizeStaleSubmittingRetry`: ambiguous→quarantine+targeted
        resolve; a plain transient still redrives). Matrix row → `event_truth`.
        Commit `e148876`.
      - [x] **Part 2 fix — adversarial-review remediation** (`b493dcb`).
        Review `w698efqy1` (4 lenses + synthesis, mutation-verified) returned
        **SAFE_TO_FINALIZE** — the core no-double-submit/oversell property was
        proven structurally sound + live (3 mutations each broke a shipped test).
        0 BLOCKER/HIGH. 5 follow-ups fixed (none merge-blocking): **M1** the
        not-found REJECT bound and query-error bound shared one counter (a run of
        query errors could erode the venue-lag tolerance) → separate reason-scoped
        counters (`_order_deferral_count`); **M2** resolving to a venue-terminal
        CANCELED/REJECTED with `filled_quantity>0` dropped broker fills (stranded
        an untracked long) → route through SUBMITTED unless a CLEAN terminal
        (filled==0), so reconcile ingests the fills (§7); **M3** the adapter
        5xx/504/timeout→`AmbiguousBrokerError` classification was unpinned → split
        the test (429 plain vs 5xx/504/network ambiguous); **L1** persistent query
        error appended a deferral every tick → bounded at max_attempts; **L2**
        re-added the dropped `list_submit_recoveries()==[]` assertion. Full suite
        1505 passed; coverage 95.33%; M2 mutation-verified. **Re-review: not run
        (all fixes ≤ MEDIUM, individually mutation-/reason-verified).**
- [~] **Wave 3d — kill/TradingState FSM** (§8): `Active`/`Reducing`/`Halted`
      replacing the binary flags (Flow 5). **Design + conflicts (D1–D6):
      `docs/SPINE_WAVE3D_PLAN.md`.** Behavior-PRESERVING `event_truth` refactor
      (the shape of 3a-truth): the 3-state FSM only *names* behavior the two
      booleans already encode.
      - [x] **Slice 1 — enum + `SessionRecord.trading_state` field + SQLite
        migration** (`d42d16c`). `TradingState` + `TradingState.of(kill, pause)`;
        column + `_migrate` guard + mapper/insert; Flow-5 `not hasattr` assertion
        migrated to assert the field. Additive/inert.
      - [x] **Slices 2–4 + 6 — event-truth core** (`701c8df`). `current_trading_state`
        projector (latest-`TRADING_STATE_CHANGED`-wins, session-scoped);
        `trading_state_change_event` (durable FSM truth, payload carries the full
        `(kill, pause)` tuple, `None` on redundant re-engage); both stores'
        `set_kill_switch`/`set_buys_paused` rewired through a shared
        `_apply_control_change` co-writing derived `trading_state` + booleans +
        legacy audit event + the `TRADING_STATE_CHANGED` ExecutionEvent atomically;
        `current_trading_state()` query; init backfill (pre-wave-3d session →
        consistent, idempotent). 19 tests; suite 1506+ green; the trading_state
        FACT is event_truth + dual-store consistent + independent-release preserved.
      - [x] **Slice 5 — enforcement reads the FSM** (`e4851d7`). The 3
        Rule-8 predicates (`order_intent_block_reason`/`session_submission_block_reason`/
        `kill_switch_block_reason`) now decide off `session.trading_state`
        (HALTED→`kill_switch`, REDUCING→`buys_paused`; reason strings kept for label
        continuity); `_claim_hold_reason` inherits the FSM read transitively (it calls
        the same predicates). `monitoring._run_protection_tick` kill-pauses-protection
        and the `/protection` status DTO's `paused_by_kill_switch` both read
        `trading_state is HALTED`. Behavior-identical since booleans == derived FSM.
        (Slice 5 originally added a `SessionRecord` validator forcing
        `trading_state == of(kill, pause)`; **removed in review remediation** — see
        below.)
      - [x] **Slice 7 — Flow-5 full migration** (`e4851d7`). Characterization
        Flow-5 migrated: `set_kill_switch → HALTED` (blocks a PROTECTION_FLOOR exit
        end-to-end via monitoring tick, ADR-003) + `set_buys_paused → REDUCING`, both
        proven against `current_trading_state()` (event log). `TestEnforcementReadsFsm`
        pins the FSM→reason mapping; `TestReducingIsReduceOnly` (INV-7 / §8 / ADR-003)
        proves REDUCING permits a reduce-only PROTECTION_FLOOR claim while denying a
        BUY, and HALTED denies both. Migration matrix row flipped to `event_truth`.
        Also cleaned pre-existing ruff debt from earlier 3d slices (F821 forward-refs
        to `TradingState` in `projectors.py`/`base.py`; F401 unused import in `core.py`).
      - [x] **Adversarial review + remediation** (`12a8c4a`). Review workflow
        `wdv4jbze4` (4 lenses + synthesis, mutation-tested): **SAFE_TO_FINALIZE**, 0
        blockers/highs, 5 non-blocking findings — all remediated. (MEDIUM + footgun-LOW)
        **removed the slice-5 `_derive_trading_state` validator**: forcing
        `trading_state == of(kill, pause)` made every enforcement test tautological
        AND was a Phase-4 footgun (§8 Reducing is driven by stream-degradation/reconcile
        *without* the booleans; the validator would heal that away = kill-switch bypass).
        `trading_state` is now an honest INDEPENDENT field co-written only by the setters;
        added `TestEnforcementFollowsFsmFieldNotBooleans` + divergent claim/monitoring/DTO
        tests (record whose FSM contradicts its booleans) — mutation-verified green→red→green
        against reverting each site to boolean-reading. (LOW) SQLite backfill column-heal
        was dead code (validator masked it) → un-deadened + guard compares the RAW row +
        test asserts via direct SQL. (LOW) downgraded the false "booleans reconstructable
        from the log" claim (core.py/projectors.py/matrix): only the derived TradingState
        is event-reconstructable; the booleans stay co-written `sessions` columns. (LOW)
        fixed `test_projector_latest_wins` false guardian (distinct first/last).
        1539 passed, coverage 95.29%, ruff clean, harness green. **Wave 3d CLOSED.**
      `MANUAL_FLATTEN`-under-Halted denial + emergency-reduce is wave 3e (D3);
      stream→Reducing trigger is Phase 4 (D4).
- [x] **Wave 3e — manual flatten + emergency reduce** (ADR-003, Flow 1) — CLOSED.
      **Plan: `docs/SPINE_WAVE3E_PLAN.md`** (conflicts E1–E8). **E1 RULED: Option B**
      (adopt ADR-003) — user-confirmed. The kill switch is now a true all-stop.
      - [x] **Slice 1 — inert override scaffolding** (`be5c110`). `EMERGENCY_REDUCE_OVERRIDE`/
        `_RESOLVED` event types; `active_emergency_reduce_overrides` projector (latest-wins
        per `{session, symbol}`); `emergency_reduce_override_event` core planner; store
        `grant_`/`resolve_emergency_reduce_override` + `list_emergency_reduce_overrides`
        (both stores, dual-store parity). Nothing read it yet — corpus stayed green.
      - [x] **Slices 3–4 — deny under Halted + emergency override** (`b15af3d`). Ordinary
        flatten denied in `Halted` w/o override (`plan_flatten_position` →
        `FLATTEN_DENIED_HALTED` → `FlattenBlockedError` → 409); allowed in Active/Reducing.
        Gated at **creation** (sole `MANUAL_FLATTEN` producer), so the claim gate is
        untouched. `authorize_emergency_reduce_override` (atomic: Halted + open position +
        INV-3 no-`TIMEOUT_QUARANTINE`-for-symbol) grants a scoped single-use override;
        `POST /positions/{symbol}/emergency-reduce` authorizes → cancels buys → flattens
        (sees grant, creates exit, **consumes** override same lock hold). Global
        `TradingState` stays `Halted` (E3: scoped grant, not a global flip). Migrated
        characterization Flow-1 + route pinning tests + D-P2 arch note (annotated).
        `tests/test_spine_phase3e_manual_flatten.py` maps ADR-003's required tests.
        Matrix rows → `event_truth`. Halted-deny mutation-verified. 1577 passed, cov 95.30%.
      - [ ] **Slice 2 — facade migration of flatten (ADR-005 / E6): DEFERRED** to the
        "API routes" matrix row (orthogonal ADR-005 hygiene; the ADR-003 *behavior* is done).
      - [x] **Adversarial review + remediation** (`3255d3f`). Review workflow `w7evfd8vh`
        (4 lenses + synthesis, firsthand repro + mutation): verdict FIX_REQUIRED — 1 MEDIUM
        + 5 lower, all remediated. **MEDIUM (override leak):** the grant was consumed ONLY on
        the create branch, so an authorize whose flatten dedup'd to EXISTING/FLAT leaked an
        active override that later bypassed the Halted-deny (reduce-only, no oversell). Fixed:
        consume on EVERY authorized outcome (moved before the outcome branches, both stores) +
        `authorize` refuses if an override is already active (no grant-stacking); consuming
        before create also makes a crash lose the override rather than leak it (fixes the
        sqlite crash-window LOW). **LOW accepted+pinned:** a CREATED-in-Active flatten submits
        under a later Halt (Halted-deny is at issuance; a local CREATED order is an already-
        commanded exit, outranking autonomous protection — D-P2); fixed the inaccurate
        docstring + added a characterization test. **LOW documented:** the INV-3
        authorize→flatten window is unreachable under Halted (no new submits) → Phase-4
        reconciliation. **Test gaps:** added override-consumed-on-existing (no leak),
        double-authorize-refused, INV-3 symbol-specificity; rewrote the tautological authority
        test to exercise the production builder. Leak fix mutation-verified. 1585 passed,
        cov 95.29%, ruff clean (changed files), harness green. **Wave 3e CLOSED.**

## Current position: Phase 4 — Reconciliation engine (§7)

**Plan: `docs/SPINE_PHASE4_PLAN.md`** (waves 4a–4h; conflicts R1–R8). **Blocking decision
gaps R1/R2/R3 gate the FSM/startup waves 4f/4g** (R1 no real trade-update stream; R2
independent reconcile-driven `Reducing` + a `max(boolean, reconcile)` FSM composition rule;
R3 kill-switch meaning on reconcile failure). Waves 4a–4e + 4h are NOT gated.
- [x] **Wave 4a — broker adapter reconciliation reports** (`159ddbf`, additive/inert).
  `BrokerOrderReport`/`BrokerPositionReport` + `list_open_orders()`/`list_positions()` on the
  `BrokerAdapter` ABC; Mock (+ seed/fail controls + counters), Sim (inherited), real
  AlpacaPaperAdapter (env-gated, wraps `get_orders(status=OPEN)`/`get_all_positions()`). §7
  safeguard pinned: a FAILED report RAISES, never read as "no open orders"/"flat". 1596 passed.
- [x] **Wave 4b — pure `app/reconciliation.py` engine** (`02dde31`, deterministic, unwired).
  `plan_reconciliation` → `ReconciliationPlan` (resolutions / inferred_fills / needs_targeted_query /
  external_orders / position_mismatches / skipped_recent). §7 safeguards property-tested (300 ex):
  absence → targeted-query request never a bare reject; position divergence surfaced never overwritten;
  no fabricated $0 fill; only cancel/reject resolved by status-flip (FILLED flows through a fill);
  deterministic synthetic `recon:{id}:{cum}` ids [R8] colliding with the real-fill scheme (INV-5).
- **R3 RULED (user): reconcile-failure → `Reducing`** (never auto-Halted; a held position stays
  exitable). R1 (sim-seam + defer stream) + R2 (`max(boolean, reconcile)` composition) adopted as
  recorded spec-derived decisions. **All Phase-4 decision gaps resolved.**
- [x] **Wave 4c — synthetic-fill append + inferred-fill identity fix** (`7e27863`, additive).
  Found + fixed a wave-4b double-count design flaw: the `recon:`-prefixed synthetic id would NOT
  collide with the real `{broker_order_id}:{cumulative}` id, so a synthetic fill + the later real
  observation of the same execution would double-count — `InferredFill` now carries the report
  execution's OWN `source_fill_id` (same identity a real poll carries) so they dedup (INV-5/R8).
  `append_fill`/`plan_append_fill`/`execution_event_for_fill` gain `source`/`authority` overrides so a
  reconciliation-inferred fill is marked `RECONCILIATION`/`SYNTHETIC` (provenance only; defaults preserve
  behavior). No-double-count property tested both stores (synthetic↔real, both orders). External-order
  projector moved to wave 4h (where the route consumes it).
- [x] **Phase-4-foundation review (waves 4a/4b/4c)** — per the goal directive, ran the review protocol
  with **cheap models (two Haiku `Explore` agents)** since the foundation is additive/inert (low risk).
  **Correctness/safety agent:** "No correctness defects found" — verified all 7 §7 safeguards in code
  (absence→needs_targeted_query never reject; divergence→PositionMismatch never overwrite; no fabricated
  $0 fill; only CANCELED/REJECTED bare-flip; broker_order_id→client_order_id match; recent-order via
  injected `now`; pure/deterministic), the synthetic-fill identity (INV-5/R8 no-double-count), and the
  provenance-override defaults (behavior-preserving). **Alignment agent:** "✅ ALIGNED" with §7, §2
  module-5 (pure functions), §12 (determinism), §5 INV-1/5/9, and R8 — confirmed the R8 synthetic-fill
  identity fix is correct ("better than proposed"). Only **1 LOW advisory** (Alpaca error-message
  type-specificity in the adapter) — deferred to wave 4e monitoring/config. No remediation needed;
  foundation is clean. 1620 passed.
- [ ] **4d** shadow the runtime reconcile (compute the plan each tick, emit shadow events, don't flip
  truth). **4e** runtime truth flip (+§7 config defaults, query throttle, position-query-failure→skip).
  **4f** startup mass reconcile + "not-enabled-until-reconcile" gate → `Reducing` (R2 max-composition
  FSM + R3). **4g** reconnect→Reducing (R1/R2). **4h** external-order route/DTO + docs + **the Phase-4
  adversarial review** (concentrates on the 4e/4f truth-flips).

**Resume hint:** **Phase 3's safety-critical flows are all migrated + reviewed** (waves
3a/3b/3c/3d/3e). Next is **Phase 4 — Reconciliation engine** (`docs/REARCHITECTURE_ROADMAP.md`
Phase 4): startup mass-status reconcile, targeted single-order query before any
not-found→REJECTED, external/unmanaged order surfacing, broker position parity, deterministic
synthetic fills, and stream-reconnect → `Reducing` + reconcile (the wave-3d/§8 hook Phase 4
drives WITHOUT touching the booleans). Several wave-3 items were deliberately deferred here:
the flatten facade migration (ADR-005/E6 → Phase 5 or the API-routes row), spawn/order
projectors (3c-C5), and continuous quarantine re-verification (3e INV-3 window). Phase 3
flips a flow to `event_truth` only when the 6 conditions in `docs/MIGRATION_MATRIX.md`
"Migration rule" hold. Read root `CLAUDE.md` §7 (Nautilus-verified reconciliation defaults in
`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §7`) before starting Phase 4; characterize the
current partial-legacy reconciliation (`app/monitoring.py` redrive/resolve + the wave-3c
`_resolve_timeout_quarantine`) first.

---

## Commit trail (most recent first)

- `afe8543` — Phase 1: fix adversarial-review test-quality findings + report
- `d146e0e` — Phase 1: facade seam for GET /positions + pause/resume-buys
- `7a25649` — Phase 0: inventory, facade skeleton, characterization tests, harness
- `3d65448` — Backfill Spine v2 docs; fix stale legacy-prompt path references
- `f770b65` — Repo prep for Spine v2: replace CLAUDE.md, archive legacy prompts
