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
| 3 | Safety-critical event-first migration | 🚧 in progress — waves 3a-shadow / 3a-truth / 3b / 3c done (all reviewed); waves 3d/3e remain |
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
      - [ ] **Slice 5 — enforcement reads the FSM.** Thread `trading_state` into the
        3 policy predicates + `_claim_hold_reason` `PROTECTION_FLOOR` branch +
        `monitoring` kill-pauses-protection (keep reason strings; behavior-identical
        since booleans == derived FSM). Then flip the matrix row to `event_truth`.
      - [ ] **Slice 7 — Flow-5 full migration** (assert `set_kill_switch → HALTED` /
        `pause → REDUCING` + the `Reducing`-allows-`PROTECTION_FLOOR` counterpart)
        + INV-7 reduce-only-under-Reducing test + docs + **adversarial review**.
      `MANUAL_FLATTEN`-under-Halted denial + emergency-reduce is wave 3e (D3);
      stream→Reducing trigger is Phase 4 (D4).
- [ ] **Wave 3e — manual flatten + emergency reduce** (ADR-003, Flow 1). Depends
      on the TradingState FSM (3d).

**Resume hint:** Waves 3a + 3b are done and green. Start **Wave 3c
(timeout/504 `TIMEOUT_QUARANTINE`, ADR-002)**. Re-read `docs/adr/ADR-002`,
`tests/test_spine_v2_characterization.py` Flow 2 (the pinned blind-redrive
current behavior), and the submission/claim path
(`app/store/core.py:plan_claim_order_for_submission`, the broker-submit recovery
ledger D-017, `app/monitoring.py` submit flow). Phase 3 flips a flow to
`event_truth` only when the 6 conditions in `docs/MIGRATION_MATRIX.md`
"Migration rule" hold.

---

## Commit trail (most recent first)

- `afe8543` — Phase 1: fix adversarial-review test-quality findings + report
- `d146e0e` — Phase 1: facade seam for GET /positions + pause/resume-buys
- `7a25649` — Phase 0: inventory, facade skeleton, characterization tests, harness
- `3d65448` — Backfill Spine v2 docs; fix stale legacy-prompt path references
- `f770b65` — Repo prep for Spine v2: replace CLAUDE.md, archive legacy prompts
