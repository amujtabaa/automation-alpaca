# Spine v2 Phase 0 — Repository Inventory

**Scope:** documentation/setup/inventory/harness/characterization only, per
`prompts/CLAUDE_CODE_PHASE_0_HANDOFF.md`. No production trading behavior was
changed to produce this document — every finding below was verified by
reading the current source and, where noted, by a new test that exercises
the real code path (not by inference from docstrings or prior docs).

Companion document: `docs/SPINE_PHASE0_MIGRATION_PLAN.md` (recommended Phase
1 scope, risks, open questions).

---

## 1. Route inventory — every FastAPI route and its direct dependencies

All 26 routes call `app.store` directly today. There is no facade boundary
(ADR-005's target) anywhere in the current call graph.

| File | Method | Path | Direct `store.*` calls | Also calls directly |
|---|---|---|---|---|
| `routes_candidates.py` | GET | `/candidates` | `get_current_session`, `list_candidates` | — |
| | GET | `/candidates/{id}` | `get_candidate` | — |
| | POST | `/candidates/{id}/approve` | `get_candidate`, `create_order_for_candidate`, `current_exposure`, `revert_candidate_approval` | `app.policy.order_intent_block_reason`, `app.policy.risk_limit_reason` |
| | POST | `/candidates/{id}/reject` | `get_candidate` (transition) | — |
| `routes_controls.py` | POST | `/kill-switch` | `set_kill_switch` | — |
| | POST | `/pause-buys` | `set_buys_paused` | — |
| | POST | `/resume-buys` | `set_buys_paused` | — |
| `routes_dev.py` | POST | `/candidates` (dev-only) | `get_current_session`, `create_candidate` | — |
| `routes_marketdata.py` | GET | `/snapshots` | — (uses `MarketDataService` directly, no store) | `app.features.pct_move` |
| `routes_review.py` | GET | `/review` | `get_session_by_date`, `list_candidates`, `list_orders`, `list_events`, `list_fills`, `list_sell_intents`, `list_position_snapshots`, `list_positions` | — |
| `routes_system.py` | GET | `/health` | — | — |
| | GET | `/session` | `get_current_session` | `app.features.session_type_for` |
| | POST | `/session/close` | `close_session` | — |
| `routes_trading.py` | GET | `/positions` | `list_positions` | — |
| | GET | `/positions/{symbol}` | `get_position` | — |
| | POST | `/positions/{symbol}/flatten` | `get_position`, `flatten_position` | `app.monitoring.cancel_open_buys` (which itself calls the broker adapter) |
| | GET | `/protection` | `get_current_session`, `list_events`, `list_positions`, `active_sell_intent_for` | `app.protection.floor_breach_reason`, `app.protection.floor_price` |
| | GET | `/sell-intents` | `list_sell_intents` | — |
| | GET | `/orders` | `list_orders` | — |
| | GET | `/order-recoveries` | `list_submit_recoveries` | — |
| | GET | `/operator/orders` | `list_orders`, `list_events`, `list_submit_recoveries` | `app.policy` classification helpers |
| | GET | `/orders/{id}` | `get_order` | — |
| | POST | `/orders/{id}/cancel` | `get_order`, `transition_order` | `adapter.cancel_order` (direct `BrokerAdapter` call) |
| | GET | `/events` | `list_events` | — |
| `routes_watchlist.py` | GET | `/watchlist` | `list_watchlist` | — |
| | POST | `/watchlist` | `get_watchlist_symbol`, `add_watchlist_symbol` | — |
| | DELETE | `/watchlist/{symbol}` | `set_watchlist_armed`/`remove_watchlist_symbol` | — |

**Direct broker-adapter calls from a route:** exactly one —
`routes_trading.py:414`'s `adapter.cancel_order(...)` inside
`POST /orders/{id}/cancel`.

**Direct monitoring-helper calls from a route:** exactly one —
`routes_trading.py:147`'s `cancel_open_buys(store, adapter, key)` inside
`POST /positions/{symbol}/flatten`.

**Direct policy-module calls from routes:** `routes_candidates.py`
(`order_intent_block_reason`, `risk_limit_reason` — pre-checks mirroring the
store's own authoritative gate) and `routes_trading.py`
(`floor_breach_reason`, `floor_price` for the read-only `/protection` view;
classification helpers for `/operator/orders`). These are pure functions
(no state mutation), a materially smaller boundary concern than the
store/broker/monitoring calls above, but still a route depending on domain
logic ADR-005 assigns to the facade layer.

**app/api/deps.py** is the current DI seam: `get_store`, `get_settings`,
`get_approval_gate`, `get_broker_adapter`, `get_market_data_service` all read
directly off `request.app.state.*` (populated once at startup in
`app/main.py`). This is the natural point a Phase 1 facade provider would
replace — the wiring pattern already exists, only the *type* returned needs
to change.

## 2. Points of EXISTING compliance with the target boundary model

Not everything is a gap. Three of ADR-005's target boundaries are **already
satisfied** by the current architecture, verified by direct inspection:

- **Streamlit imports only the typed API client.** `grep`ing
  `cockpit/*.py` for `^from app\.|^import app\.` returns nothing. `cockpit/
  app.py` imports only `cockpit.api_client`, an HTTP client — no Python
  import of any backend module. Rule 3/4 already hold.
- **`alpaca-py` is (almost) adapter-only.** It is imported in exactly two
  production modules: `app/broker/alpaca_paper.py` (the concrete broker
  adapter — expected) and `app/marketdata/alpaca_stream.py` (the concrete
  market-data stream). `app/models.py`'s `OrderType` docstring already
  documents this as a known, deliberate "second, equally lazy-imported call
  site... but no third" — ADR-005's literal wording ("the concrete Alpaca
  adapter is the only package") doesn't account for a *second* venue-specific
  adapter (market data vs. trading); Phase 5 (import-linter enforcement)
  will need to either broaden the allowed set to "the adapter layer" or
  treat this as two adapters, not one. Not a new problem — flagging so
  Phase 5 doesn't trip on it.
- **`submit_order` already runs off the event loop.** Spine v2 §9 requires
  this because the SDK's REST retry is a blocking `time.sleep`.
  `app/broker/alpaca_paper.py`'s `submit_order` already wraps every SDK call
  in `asyncio.to_thread` (verified at lines 246, 263, 322, 357). No gap here.
- **Single-writer-ish serialization already exists.** Both stores guard all
  mutating operations with one `asyncio.Lock` per store instance, and the
  process is single-worker FastAPI — in *effect* satisfying "exactly one
  logical writer" even though the code isn't organized into a distinct
  `Execution Engine` module (see §4 below, this is not the same as the
  target's clean module separation).

## 3. ADR conflicts — current behavior vs. accepted target, verified by test

Per `CLAUDE.md`'s Conflict rule ("do not silently pick one... stop and
record the decision gap before coding"), each of the following is a real,
verified divergence between current code and an accepted ADR. **None were
changed to produce this document** — each is now pinned by a new
characterization test in `tests/test_spine_v2_characterization.py` so a
future migration has to consciously break the pinning assertion, not
silently drift past it.

### 3.1 Manual flatten vs. ADR-003 — HIGH conflict

**Current:** `app/store/core.py`'s claim-gate docstring states outright:
"`MANUAL_FLATTEN` -> never held: a human-commanded flatten always exits,
even kill-switched/buys-paused/closed/unknown-session (D-P2)." Verified live:
`TestCharacterizeManualFlatten.test_manual_flatten_dispatches_and_submits_
under_kill_switch` engages the kill switch, then shows `flatten_position`
still dispatches and fully submits a `MANUAL_FLATTEN` SELL.

**Target (ADR-003):** manual flatten is denied by default when
`TradingState` is `Halted`; an operator must use an explicit, audited
emergency-reduce override that scopes into `Reducing`. ADR-003's own
Context section names the current behavior directly: "a global bypass
conflicts with the v2 rule that the kill switch blocks new order intent."

**Severity:** highest of the five — this is the exact behavior ADR-003 was
written to change, and it is exercised in production today (D-P2 was a
deliberate, reviewed design decision at the time, not an oversight — but it
is superseded by this accepted ADR).

### 3.2 Stale-`SUBMITTING` blind redrive vs. ADR-002 — MEDIUM-HIGH conflict

**Current:** `app/broker/alpaca_paper.py`'s `submit_order` raises a plain
`BrokerError` (transient classification) uniformly for network errors, 429,
AND 5xx/504 — it does not distinguish "the request almost certainly never
reached the venue" from "the outcome is genuinely unknown." A transient
`BrokerError` leaves the order `SUBMITTING` for an ordinary redrive next
tick, resubmitting with the SAME `client_order_id` and relying on Alpaca's
own duplicate-detection to recover an already-accepted order rather than
double-submitting. Verified live: `TestCharacterizeStaleSubmittingRetry.
test_transient_submit_failure_leaves_submitting_for_blind_redrive`.

**Target (ADR-002):** an ambiguous submit outcome (timeout/504/transport
failure) moves to a distinct `TIMEOUT_QUARANTINE` status and blocks a
replacement spawn until a TARGETED reconciliation query (not a resubmit)
confirms venue reality. ADR-002's Context section names this precisely:
"blind redrive is too permissive for ambiguous broker outcomes."

**Nuance:** the current mechanism is not naive — it has a bounded-attempts
backstop (`stale_submitting_max_redrive_attempts`) that escalates to
`needs_review` rather than looping forever, and the redrive genuinely is
safe against a double-submit (Alpaca rejects duplicate `client_order_id`).
The gap is architectural (no distinct quarantine state, no pre-resubmit
targeted query), not "orders get double-submitted."

### 3.3 Broker-reported overfill/negative-position vs. ADR-001 — MEDIUM conflict

**Current:** `append_fill` rejects (raises `NegativePositionError`, appends
nothing) any fill that would drive position negative — with no distinction
between a malformed local/synthetic input and a genuine broker-authoritative
fact. `app.monitoring`'s real fill-ingestion loop catches this exact
exception via its `_FILL_ERRORS` tuple, logs a warning, and (if the broker's
cumulative reported quantity now exceeds what was recorded) escalates via
the pre-existing, narrower fill-divergence `needs_review` mechanism (D-022
B3/AIR-002) — but the fill fact itself never enters the fill/position
ledger. Verified live:
`TestCharacterizeBrokerOverfillHandling.test_fill_that_would_go_negative_
is_rejected_and_position_unaffected`.

**Target (ADR-001):** the broker-authoritative fact must be RECORDED (even
though it violates the local no-oversell expectation), with the affected
primary explicitly `QUARANTINED` and blocked from further autonomous
spawned orders.

**Nuance:** this is the mildest of the three HIGH/MEDIUM conflicts — the
existing `needs_review` escalation already gives an operator *some*
visibility into the divergence (it is not silently dropped from the audit
log), it just doesn't record the broker's fill fact in the position ledger
itself, and there's no order-level quarantine gate blocking further trading
on the symbol specifically because of this.

### 3.4 Kill switch model vs. ADR-003/Spine v2 §8 — MEDIUM conflict (same root as 3.1)

**Current:** `SessionRecord.kill_switch: bool` / `.buys_paused: bool` are two
independent booleans; there is no `TradingState` enum. A `PROTECTION_FLOOR`
sell (unlike `MANUAL_FLATTEN`) IS blocked by the kill switch today, but it's
a binary block/no-block — no `Reducing`-style "reduce-only orders still
flow" grade. Verified live:
`TestCharacterizeKillSwitchModel.test_kill_switch_is_a_binary_flag_and_
blocks_protection_floor_claim`.

**Target:** three-state `TradingState` (`Active`/`Reducing`/`Halted`).
`Reducing` is the default under stream degradation or pending
reconciliation and explicitly permits reduce-only orders + cancels while
denying exposure-increasing ones.

### 3.5 Fill/position derivation — NOT a conflict, a replay baseline (ADR-004)

**Current:** average-cost folding (proportional cost-basis reduction on a
sell) and `source_fill_id`-keyed duplicate-fill dedup. Verified live:
`TestCharacterizeFillPositionDerivation.test_average_cost_folding_and_
duplicate_fill_dedup_baseline`.

ADR-004 does not change this folding semantic — it only migrates *where* it
is durably sourced from (a legacy fill table today; an `ExecutionEvent` log
once migrated). This test is the baseline a future replay/parity verifier
must reproduce exactly, not a behavior gap to resolve.

## 4. Architectural gaps beyond the five named flows

- **No single "Execution Engine" module.** Decision logic is currently
  spread across `app/store/core.py` (pure planners), `app/store/memory.py`
  / `sqlite.py` (apply the plans under the lock), and `app/monitoring.py`
  (the polling/submission/reconciliation loop). The target's §2 module
  table assigns "primary/spawn state machines... sole writer of order
  state" to one Execution Engine module, distinct from the State Store. The
  current split is *functionally* single-writer (one lock) but not
  *structurally* separated the way Phase 3+ will need.
- **No `primary`/`spawn` model.** The current `Order`/`SellIntent` models
  are the closest analogues, but neither the naming nor the "primary
  supervises 1 disposable spawn" structure (Spine v2 §4, INV-2) exists.
  `docs/MIGRATION_MATRIX.md` already tracks this ("Atomic submit claim:
  legacy_truth -> event_truth... Salvage prior claim semantics inside
  single-writer engine").
- **No event log.** `Event` rows exist as an append-only audit trail, but
  they are not the durable source of truth for order/fill/position state
  (the dedicated tables are) — ADR-004's entire premise.
- **No import-linter / boundary enforcement.** Confirmed: no
  `import-linter` config exists in `pyproject.toml`; nothing currently
  prevents a route from importing the store/broker/monitoring directly
  (which every route already does — see §1). Enforcement is explicitly
  Phase 5 (`docs/REARCHITECTURE_ROADMAP.md`).

## 5. Files changed in this Phase 0 pass

All additive; nothing existing was modified.

- `app/facade/__init__.py`, `protocols.py`, `commands.py`, `queries.py`,
  `errors.py` — inert `Protocol` skeletons (ADR-005/§10 shape only; zero
  runtime behavior, confirmed nothing outside `app/facade/` imports them).
- `harness/check_claude_imports.py` — supplied as-is; confirms every
  `CLAUDE.md` `@` import resolves.
- `harness/check_stale_prompt_links.py` — new; confirms no active file
  references an archived `docs/IMPLEMENTATION_PROMPT_*.md` at its
  pre-archive path.
- `tests/test_harness_smoke.py` — wires both harness checks into the normal
  pytest run as permanent regression guards (mutation-tested: a deliberately
  reintroduced stale reference was confirmed to make the check fail before
  being removed again).
- `tests/test_spine_v2_characterization.py` — 5 test classes (10 tests
  across both stores) pinning the current behavior of the five flows in §3
  above.
- `prompts/*.md` — applied from `spine_v2_prompts_backfill_patch.zip`
  (`CLAUDE_CODE_PHASE_0_HANDOFF.md`, `CLAUDE_CODE_PHASE_1_FACADE_SEAM.md`,
  `CODEX_PHASE_0_HANDOFF.md`, `INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`,
  `README.md`) — the previously-missing file this Phase 0 task's read order
  named (`prompts/CLAUDE_CODE_PHASE_0_HANDOFF.md`) now exists.

Stale implementation prompts (`docs/IMPLEMENTATION_PROMPT_*.md`) were
already archived to `docs/archive/legacy_implementation_prompts/` and all
stale path references fixed in an earlier session on this branch — this
pass only *confirmed* that (via `harness/check_stale_prompt_links.py`,
which passes clean) rather than redoing it.

## 6. Tests run

```text
python harness/check_claude_imports.py         -> All CLAUDE.md @ imports resolve.
python harness/check_stale_prompt_links.py     -> No stale references found.
pytest --collect-only -q                       -> 1337 tests collected, 0 errors
pytest -q --cov=app --cov-branch               -> 1334 passed, 3 skipped
                                                   coverage 94.89% (floor 93%)
```

No failures, no environment blockers. The 3 skips are the same
pre-existing, intentionally-gated integration tests (require real Alpaca
paper credentials) as every prior run on this branch.

**Coverage note (honest, not hidden):** total coverage dropped from 95.58%
to 94.89% versus the pre-Phase-0 baseline on this branch. Verified cause:
the new `app/facade/*` package is 0% covered (34 statements, all
unexercised) — expected and deliberate, since it is an intentionally inert,
unwired skeleton with no concrete implementation or tests yet. Still well
above the 93% floor. Phase 1 is expected to add real coverage once a
concrete facade implementation and tests exist.

## 7. Behavior-change risk assessment

**Risk from this Phase 0 pass: none.** Every change is additive
(new files) or a pure repo-state assertion (harness scripts, smoke tests).
Verification:

- `git diff` against the pre-Phase-0 commit touches zero existing `app/*.py`
  files other than adding the new `app/facade/` package (new files only).
- The full pre-existing suite (1322 tests before this pass) still passes
  unchanged; the only additions are 15 new tests (10 characterization + 2
  harness smoke + the facade package's zero net effect on anything else).
- `app/facade/` is confirmed unimported by anything outside itself (`grep
  -rln "from app.facade\|import app.facade" --include=*.py .` returns only
  files under `app/facade/` itself).

**Risk carried FORWARD into Phase 1+ (not created by this pass, but now
explicitly documented so it isn't silently inherited):** the four ADR
conflicts in §3 are live in production behavior today. Migrating each one
(especially 3.1, manual flatten under Halted) is a real behavior change
with real operational consequences (an operator who currently expects
"flatten always works" will need to learn the emergency-override flow) —
Phase 3 scope per the roadmap, not something to rush.
