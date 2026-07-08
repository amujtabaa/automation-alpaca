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
| 4 | Reconciliation engine | ✅ done (waves 4a–4h, `da2260c` incl. review remediation) — all §7 goals met; event_truth |
| 5 | Import-boundary enforcement | ✅ done — `.importlinter` (5 contracts) + CI `lint-imports` + `tests/test_import_boundaries.py`; ADR-006 |
| 6 | Legacy table demotion/removal | ⬜ not started (inherits the Contract-5 ratchet punch-list) |

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
- [x] **Wave 4d — shadow the runtime reconcile** (characterize → shadow; additive/inert, no truth flip).
  `_shadow_reconcile` runs LAST in `run_monitoring_tick` (after the legacy per-order poll + recovery, so a
  surfaced divergence is one the per-order poll structurally CAN'T capture), computes the mass-report
  `plan_reconciliation`, and emits a single `reconcile_shadow_divergence` audit event on divergence
  (external/unmanaged venue order, broker-vs-local position drift), **deduped by a content fingerprint**
  (`_shadow_fingerprint`; `skipped_recent` excluded) so a persistent divergence logs once, not per tick.
  **Never flips truth** (no transition/fill/position mutation — the returned plan is observability/test
  only); **failure-isolated** (a raised mass report is caught → cycle skipped, never read as flat; the
  legacy reconcile is untouched); **off by default** (`reconciliation_shadow_enabled` /
  `RECONCILIATION_SHADOW_ENABLED`) so the whole existing corpus + any real deployment stay unperturbed
  until wave 4e adds the 200/min throttle (R6). Matrix "Reconciliation" row → `partial legacy (P4 wave 4d
  shadow)`. 19 tests (`tests/test_spine_phase4_reconcile_shadow.py`): off-by-default makes zero report
  calls + no event; shadow-on doesn't change the legacy fill→position/status outcome; external-order +
  position-mismatch surfaced without overwriting position truth; dedup + re-log-on-change; both report
  failures skip-not-crash; pure `_shadow_fingerprint` over all 5 categories + full payload schema.
  **Review protocol ran** (per the goal, cheap models for a low-risk additive/inert wave): two Haiku
  agents — correctness/safety returned "NO CORRECTNESS DEFECTS FOUND, no nits" (verified never-flips-truth,
  failure-isolated, inert-when-off, dedup, run-last ordering); alignment returned "ALIGNED" (§7 read-only
  shadow discipline, audit-log-not-ExecutionEvent choice correct, matrix/plan/ledger accurate + not
  overclaiming event_truth, throttle-deferred-to-4e defensible). No remediation. Suite 1640 passed,
  coverage 95.12%, ruff clean, harness green.
- [ ] **4e** runtime truth flip (+§7 config defaults, query throttle, position-query-failure→skip).
  **Plan: `docs/SPINE_WAVE4E_PLAN.md`** (conflicts E1–E9; slices 4e-1…4e-5). THE big Phase-4 truth flip:
  turns the 4d shadow into an ACTING mass-report reconcile. Load-bearing safeguard **E2/R5**:
  a mass-report *absence* NEVER rejects — it triggers the read-only targeted query (reusing wave-3c
  machinery) before any not-found→REJECTED/CANCELED. Critical pre-coding gate **E5**: the mock/sim
  `list_open_orders` must default to the adapter's known-live orders, else the acting reconcile (on by
  default) would drive every existing open-order test to a spurious not-found→reject. Heavier Opus
  adversarial review at slice 4e-5 (oversell/short-flip focus).
  - [x] **Slice 4e-1 — §7 config defaults + query budget** (additive/inert). `config.py`:
    `reconciliation_enabled` (default True) + `reconcile_recent_threshold_ms` (5000) +
    `reconcile_avg_price_tolerance` (0.0001) + `reconcile_open_check_missing_retries` (3, min 1) +
    `reconcile_query_budget_per_min` (200, min 1) + `reconcile_startup_delay_secs` (10.0, for 4f), all
    env-overridable (misconfigured retries/budget < 1 fail-fast, matching the timeout-quarantine pattern).
    New pure `ReconcileQueryBudget` (`reconciliation.py`): a deterministic per-minute token bucket with an
    INJECTED clock (§12/§9) — starts full, refills only on forward time, `try_consume(now,n)` skips-not-flat
    when empty; token-conservation property-tested. Nothing consumes it yet (wired in 4e-4).
    `tests/test_spine_phase4_reconcile_budget.py` (11 tests). Suite 1651 passed, cov 95.20%, ruff clean.
    **Reviewed clean** (cheap Haiku, per the goal's token-efficiency rule): refill math sound, the
    monotonic-clock guard can't over-credit/rewind, denied consumes take zero tokens, config fail-fast on
    retries/budget < 1 is the safe choice (0 retries = oversell path; 0 budget = silent disable). No defects.
  - [x] **Slice 4e-2 — acting reconcile: external/unmanaged order surfacing.** `_run_reconciliation`
    (gated by `reconciliation_enabled`, default True) SUPERSEDES the 4d shadow: computes the plan each tick
    and takes its first, **non-mutating** action — surfacing external venue orders (no local match) as
    durable, deduped-by-`broker_order_id` `reconcile_external_order` audit records (§7 "never absorbed").
    Retired the 4d shadow (flag `reconciliation_shadow_enabled`, `_shadow_reconcile`/`_emit_shadow_divergence`/
    `_shadow_fingerprint`, `RECONCILE_SHADOW_DIVERGENCE`). **Naturally inert** against the corpus: external
    orders come from the broker report, so an empty report (the default mock) yields none — the reconcile
    runs on every tick but surfaces nothing. Failure-isolated (a raised mass report skips the cycle, never
    read as flat; the legacy poll is untouched). Never flips truth (audit record only — no order transition/
    fill/position change). **Scope refinement:** position parity → 4e-4 (needs the position-report fidelity;
    an empty mock report would false-positive on every local position); E5 open-order fidelity → 4e-3 (where
    a not-found absence bites). `tests/test_spine_phase4_reconcile_acting.py` (16, replacing the shadow tests):
    empty-reports-surface-nothing, disabled-makes-no-calls, external-surfaced-without-absorbing, dedup-by-id +
    new-order-relogs, doesn't-change-legacy-fill-outcome, both report failures skip-not-crash, returns-plan.
  - [x] **Slice 4e-3a — adapter open-order fidelity (E5)** (`237fc6a`). The mock/sim `list_open_orders` now
    DERIVES the venue's open orders from the adapter's own known-live submits when unseeded (sentinel
    `_open_order_reports=None`) instead of `[]`, so a locally-open managed order the adapter accepted is
    reported open — never spuriously *absent* (which would drive a false not-found→reject). Explicit seed
    still overrides; fresh adapter derives `[]`. Inert to 4e-2. 1655 passed.
  - [x] **Slice 4e-3b — not-found → targeted-query-before-terminal (the oversell-critical flip).** The acting
    reconcile resolves open orders ABSENT from the mass report — but absence is NEVER a reject on its own:
    each gets a READ-ONLY targeted `get_order_by_client_order_id` query first, and only a venue-CONFIRMED
    absence sustained past `reconcile_open_check_missing_retries` (3) resolves it — `SUBMITTED→REJECTED` /
    `PARTIALLY_FILLED→CANCELED` (fills preserved), event-authoritative via the new `reconcile_resolve_order`
    store method + `plan_reconcile_resolve_order` (BROKER_AUTHORITATIVE; FILLED refused — INV-9). Venue-has-it
    → left to the per-order poll (no bare terminal flip that could drop a fill). Query FAILURE → never read as
    absent (§7); retried, `needs_review` on a SEPARATE counter so a run of failures can't erode the not-found
    bound. CANCEL_PENDING excluded (R4). Reuses the wave-3c deferral machinery (`_order_deferral_count` gained
    an `event_type` param). `tests/test_spine_phase4_reconcile_notfound.py` (18, dual-store): no-premature-
    reject, partial→canceled-fills-preserved, venue-has-it-never-resolved, query-failure-never-rejects+
    needs_review, query-errors-don't-erode-not-found-bound, event-authoritative, cancel_pending-untouched,
    managed-order-not-touched (E5), FILLED-refused. **Ran by default without perturbing the corpus** (E5
    fidelity + recent-order protection). 1673 passed, cov 95.08%, ruff clean.
  - [x] **Slice 4e-4 — synthetic fills (INV-5/R8) + query throttle (E6/E7).** `_apply_inferred_fills`
    appends each `plan.inferred_fills` as a `source=RECONCILIATION`/`authority=SYNTHETIC` fill; the engine
    only infers from a PRICED execution covering the delta (never a $0 fill), and `source_fill_id` = the
    execution's own venue id so a synthetic + the later real observation of the same execution dedup (INV-5)
    — naturally inert (a derived mock report carries no fills). The `ReconcileQueryBudget` is now WIRED
    (E6): `monitoring_loop` owns ONE persistent budget (refills across ticks), threaded via
    `run_monitoring_tick(reconcile_budget=)` → `_run_reconciliation(budget=)`; the 2 mass-report calls are
    consumed up front and the cycle SKIPS if uncovered (never a partial read / never flat — E7), targeted
    queries consume one each and defer the rest when exhausted. Direct callers pass no budget (unthrottled).
    **Position parity (E9) DEFERRED** to a post-4e follow-up (audit-only surfacing, never a truth flip, so
    it doesn't gate `event_truth`; venue avg-price fidelity is a separate rabbit hole).
    `tests/test_spine_phase4_reconcile_synthetic_throttle.py` (12).
  - [x] **Slice 4e-5 — `event_truth` matrix flip + heavier adversarial review + remediation.** Flipped the
    matrix "Reconciliation" row to `event_truth` (the not-found REJECTED/CANCELED lifecycle events +
    synthetic FILL events are the durable truth; order-status column a co-written read-model, order-status
    projector deferred — mirror of 3c-C5; position replays from the log; dual-store parity).
    `tests/test_spine_phase4_reconcile_event_truth.py` (4). **Two independent Opus adversarial reviewers**
    (oversell/safety + inertness/event_truth-honesty): BOTH returned **no BLOCKER/HIGH** — "could NOT break
    the oversell-critical path with any in-contract interleaving" and "the flip is HONEST, the design is
    sound." 5 LOW/MEDIUM hardening findings (none truth bugs / none 4e regressions), all remediated:
    **F1** engine now refuses to infer a priced fill with a null/empty `source_fill_id` (the one input that
    defeats INV-5 dedup → routes to the targeted poll); **F2** the not-found reject bound is now CONSECUTIVE
    (reset by a venue-present observation via a `cleared_present` streak marker), not a lifetime sum;
    **F3** external-order surfacing now excludes any venue row matching a known local order in ANY state
    (not just open) — robust to adapter/venue mirror lag; **F4** `_resolve_reconcile_not_found` wraps each
    order so one failure never stops the loop (honors the docstring); **F5** documented that `plan.resolutions`
    (matched-terminal) is deliberately left to the per-order poll (double-actor safety). +3 remediation tests
    (F1/F2/F3). **Wave 4e CLOSED** — the runtime open-order reconcile is `event_truth`, reviewed clean.
- [x] **Wave 4f — startup reconcile gate + R2 FSM composition** (`21b7607` + startup wiring).
  - **4f-1 (FSM composition, R2):** the §8 TradingState FSM gained a SECOND, independent driver so the
    reconcile engine can drive `trading_state → Reducing` WITHOUT touching the kill/pause booleans (the
    wave-3d hook). `compose_trading_state(Halted > Reducing > Active)` folds the control driver
    (`control_trading_state`) + reconcile driver (`reconcile_trading_state`); `current_trading_state` now
    returns the composition. New `set_reconcile_trading_state(to, reason)` store method emits a
    `driver="reconcile"` `TRADING_STATE_CHANGED` event; the control event gained a `driver="control"` stamp
    (legacy events fold as control). Behavior-preserving (no reconcile events → composition == control;
    wave-3d suite green). Kill dominates a reconcile Reducing; a kill *release* can't lift a Reducing
    pending reconciliation still needs. Reconcile driver refuses `Halted` (R3). `tests/test_spine_phase4f_
    fsm_composition.py` (11, dual-store).
  - **4f-2 (startup gate, §7 / R3):** `run_startup_reconcile` (called in `main.py` lifespan before the loop)
    enters reduce-only (`Reducing`), runs one mass-reconcile pass, and lifts to `Active` on confirmed parity;
    divergence or a reconcile FAILURE stays `Reducing` (R3 — never auto-Halt; a held position stays exitable
    at boot). The monitoring loop re-checks each tick (`drive_reconcile_state=True` → parity ⇒ Active,
    divergence/failure ⇒ Reducing) via `_has_unresolved_divergence` (needs_targeted_query / external / position
    drift — the deferred position-parity computation finally gates something). **Only the loop/startup drive
    the FSM**; a direct `run_monitoring_tick` (the whole corpus) leaves `trading_state` untouched
    (`drive_reconcile_state=False` default). `tests/test_spine_phase4f_startup_gate.py` (12, dual-store):
    clean-parity→Active, divergence→stays-Reducing, failure→Reducing-never-Halted, kill-dominates,
    divergence-then-resolution-lifts, direct-tick-never-drives.
- [x] **Wave 4g — stream reconnect → Reducing + reconcile (R1 sim-seam).** `on_stream_reconnect` reuses the
  4f gate (`_reconcile_and_gate`): a trade-update stream reconnect (no replay → possible drift) enters
  reduce-only (`Reducing`), triggers a mass reconcile, and lifts to `Active` on parity (or holds `Reducing`
  on divergence/failure — R3; kill still dominates). **R1:** no real trade-update stream exists (REST-poll,
  D-011), so this is the SIM SEAM a real stream's reconnect callback will call — invoked from sim/tests;
  real-stream wiring deferred with real creds. `tests/test_spine_phase4g_reconnect.py` (5). Suite 1732 passed.

- [x] **Wave 4h — position-parity surfacing + reconciliation read route/DTO + Phase-4 consolidation.**
  Two additions, both `drive_state`-gated / read-only (no truth flip; the row was already `event_truth`
  at 4e):
  - **Position parity (§7 / E9, deferred from 4e).** `_surface_position_mismatches` emits a durable,
    deduped (`(symbol, kind)`) `reconcile_position_mismatch` needs-review record for a broker-vs-local
    drift (qty exact, avg-px within `reconcile_avg_price_tolerance`). **Position truth is NEVER
    overwritten (Rule 7)** — the record is audit-only; the drift also holds trading reduce-only via
    `_has_unresolved_divergence` → the reconcile FSM driver. Gated behind `drive_state` (loop/startup/
    reconnect) so the direct-tick corpus stays inert (a mock that doesn't mirror positions can't
    false-fire). `EventType.RECONCILE_POSITION_MISMATCH`. `tests/test_spine_phase4h_position_mismatch.py`
    (5, dual-store).
  - **Operator read surface (ADR-005).** `GET /api/reconciliation` → `ReconciliationStatusResponse`
    {`external_orders`, `position_mismatches`}, facade-backed: `StoreBackedQueryFacade.list_external_orders`
    (migrated from `NotYetImplementedError`) + new `list_position_mismatches` map the durable audit
    records to typed view DTOs. **The view DTOs live in `app/facade/dtos.py`, not `app.api.schemas`**, so
    the dependency direction stays api→facade — keeping the Phase-5 import-linter contract clean (the
    route/`ReconciliationStatusResponse` import them, the facade never imports up into the API layer). The
    Phase-1 pinning test consciously re-pinned (`list_external_orders` dropped from the still-unmigrated
    parametrize list). `tests/test_spine_phase4h_reconcile_read.py` (8: facade dual-store + HTTP wiring).
  - Suite **1754 passed** (memory+SQLite), ruff clean.

- [x] **Phase-4 adversarial review + remediation.** Tiered independent review of the 4f/4g/4h diff:
  a cheap read-surface pass (facade/DTO/route/boundary/payload-key contract — **clean, no defects**) +
  a safety-critical pass on the reconcile FSM/gating. The safety pass **cleared** kill-dominance, R3
  (reconcile never drives Halted), never-flat (failed report → Reducing; budget-skip → state unchanged,
  never lifted to Active), Rule-7 (position never overwritten), direct-tick inertness, and the subtle
  divergence-stickiness question (`_has_unresolved_divergence` reads the LIVE plan, not the dedup set, so
  a dedup-suppressed record can't lift a still-diverging state). One actionable **MED** found + fixed:
  - **RF-1 (log hygiene / perf).** The reconcile driver's no-op re-assert (`_apply_reconcile_state_*`)
    appended a `trading_state_reconcile` audit row + rewrote the column on EVERY steady-parity tick
    (the loop drives `drive_reconcile_state=True` each cadence), growing the legacy audit log unbounded
    (~17k rows/day @ 5s) and quadratically slowing the per-tick log folds. Fixed: guard the audit append
    + column rewrite on an actual state change (`exec_event is None` → return), mirroring the existing
    ExecutionEvent gate; the ExecutionEvent log + FSM were already correct (unchanged). Now a redundant
    set is a true store no-op — dual-store symmetric, so parity holds. Regression pinned in
    `test_spine_phase4f_fsm_composition.py::test_redundant_reconcile_set_is_a_noop` (now asserts BOTH the
    exec-event AND the audit-row count stay flat across repeated redundant sets).
  - **Accepted as-is (planning-seat notes, do NOT gate):** (a) position-mismatch dedup by `(symbol,kind)`
    is a once-ever flag — a cleared-then-recurred drift with a new magnitude isn't re-surfaced; safety
    is unaffected (the FSM reads the live plan), audit fidelity only, and a clear/resolution path is a
    Phase-4-deferred item. (b) A budget-exhausted reconcile leaves the driver at its last-known state
    (possibly Active) rather than affirmatively Reducing — matches §7 "a skipped report is never treated
    as flat" (takes no action); a liveness gap, not an oversell, and improbable at paper/beta scale.
  - Suite green after the fix; ruff clean.

**Phase 4 — CLOSED.** All §7 reconciliation goals are met: startup mass-status reconcile + gate (4f),
targeted single-order query before any not-found→terminal (4e-3), external/unmanaged order surfacing +
route (4e-2/4h), broker position parity surfacing (4h), deterministic synthetic fills (4e-4), stream
reconnect→`Reducing`+reconcile (4g). Remaining follow-ups do NOT belong to Phase 4's scope: the
order-status/spawn projector (spine §4, mirror of 3c-C5) and real trade-update-stream wiring (replaces
the 4g sim-seam, needs real creds). **Next: the Phase-4 adversarial review** (concentrate on the 4e
truth-flip + 4f/4g FSM-composition/startup-gate safety-critical paths), then **STANDBY before Phase 5**
per the standing request.

---

## Current position: Phase 5 — Import-boundary enforcement (import-linter) — ✅ CLOSED

**Goal (roadmap Phase 5 / CLAUDE.md §5):** turn the layered architecture from documented into
mechanically enforced — "a PR that crosses a protected boundary fails CI".

- [x] **Recon (grimp import-graph audit).** The architecture is already clean: `alpaca` is imported
  by exactly the two concrete ports (`app.broker.alpaca_paper`, `app.marketdata.alpaca_stream`); the
  cockpit imports zero `app.*`; `app.models` is a leaf; `app.facade`/`app.store`/`app.broker` have no
  upward imports; no engine module imports a concrete adapter. The only api→backend edges are the ~12
  known unmigrated route→store/broker/monitoring imports (the Phase-6 target).
- [x] **`.importlinter` — 5 forbidden contracts (ADR-006).** Four Tier-1 hard invariants hold with
  ZERO exceptions (alpaca-SDK-confined-to-adapter, cockpit-thin-client, engine-venue-agnostic,
  models-is-a-leaf), all `allow_indirect_imports = True` (direct-edge boundaries; the composition root
  legitimately creates transitive paths). A fifth Tier-2 contract encodes the ADR-005 "routes reach the
  backend only via the facade" TARGET as a **ratchet**: `ignore_imports` is the exhaustive Phase-6
  punch-list of the remaining direct route→backend edges, and `unmatched_ignore_imports_alerting =
  error` makes a migrated route's stale ignore fail the build until deleted — the boundary can only
  tighten. `app.api.deps` (DI/composition root) + `app.api.schemas` (DTOs) are excluded from the source.
- [x] **Non-vacuity proven.** Verified both that removing a Contract-5 ignore immediately BREAKS the
  build and that an unmatched/stale ignore ERRORS — the config genuinely bites and the ratchet fires.
- [x] **Enforcement wiring.** `import-linter>=2.0` added to `requirements.txt`; a dedicated
  `lint-imports` CI step (before the suite, for a clear failure signal); and
  `tests/test_import_boundaries.py` runs all contracts IN the suite (via `configuration.configure()` +
  `use_cases.lint_imports`) PLUS two INI-independent grimp proofs (alpaca confinement, thin UI) so
  those safety boundaries survive a config mis-edit. `pytest.importorskip` keeps a dev without the tool
  from being blocked; CI always has it.
- [x] **Docs.** ADR-006 written; MIGRATION_MATRIX Import-linter row → `enforced`; INVARIANTS INV-070…074
  added; this ledger. No `app/` source changed (coverage unaffected).
- [x] Gate: `lint-imports` green (5 kept / 0 broken); full suite green; ruff clean.

**Phase 5 — CLOSED.** The boundary is now enforced two ways (CI step + suite test). Phase 6 (legacy
table demotion + route→facade migration) inherits a mechanical, self-tightening checklist: empty the
Contract-5 `ignore_imports` block one migrated route at a time, and the ratchet forbids the edge from
returning. **Next: the Phase-5 adversarial review**, then **STANDBY before Phase 6** per the standing
request.

---

**Resume hint (historical, Phase 4):** **Phase 3's safety-critical flows are all migrated + reviewed** (waves
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
