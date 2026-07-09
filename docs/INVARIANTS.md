# Invariants Registry — Alpaca Clean-Sheet CAPI Option 2.5

This is the **independent oracle** for review: what the system must always be
true, stated separately from any implementer's tests. `REVIEW_LOOP_REFINEMENT.md`
(the Phase-7 X-001..X-005 remediation retro) named the root cause of three
missed defects as reviewing *against the implementer's own tests* — a test can
assert the same bug it should catch (X-002 is the on-the-record example: the
ADR said self-heal was required, the code didn't do it, and the test asserted
the buggy `APPROVED` result as correct). This file exists so a reviewer — human,
Claude, or an external tool — can probe the system against a statement that
was **not** written by whoever wrote the fix, and so a future change can be
checked against a stable list instead of re-deriving "what should never happen"
from scratch.

**How to use this file:**
- Before trusting a green test suite, pick a handful of invariants below and
  write a **fresh probe** against them — not a re-run of the linked pinning
  test, which only proves the implementer's own scenario.
- When a new blocker/ADR-declared rule is added, add it here in the same
  session, not as a follow-up — an invariant that exists only in an ADR
  paragraph is exactly the drift class this file is meant to close (see X-003:
  the code and the ADR silently disagreed, and nothing forced them to be
  compared).
- Each entry: **statement** (the thing that must always hold), **why**
  (failure mode if violated), **pinned by** (the test(s) that would fail if it
  broke). "Pinned by" is provenance, not proof — the statement must stand on
  its own without reading the test.
- IDs are stable once assigned; do not renumber on edit. Superseded entries are
  marked superseded, not deleted (history matters more than tidiness here).

---

## Position and Fill (Rule 7, `docs/02_DATA_AND_PERSISTENCE.md`)

**INV-001 — Position quantity is derived from fills, never a stored mutable
number.** No code path writes to a position's quantity directly; folding the
fill table is the only way a position's `quantity`/`cost_basis` changes.
*Why:* any other write path silently breaks the append-only audit guarantee
the whole persistence model depends on.
*Pinned by:* `tests/test_position_folding.py`, `no_live_untracked_broker_order` /
`filled_quantity_bounded_and_whole` invariants in
`tests/test_lifecycle_state_machine.py`.

**INV-002 — A position quantity never goes negative.** A sell fill that would
overdraw a position is a data-integrity error (rejected), never a silent short.
*Why:* beta is long-only; a negative position has no defined meaning anywhere
downstream (protection floor, CAPI exposure).
*Pinned by:* `position_never_negative` invariant
(`tests/test_lifecycle_state_machine.py`).

**INV-003 — A fill's `source_fill_id`, when present, is unique — a duplicate
observation never appends a second fill row or mutates position.**
*Why:* polling-based reconciliation can observe the same broker fill twice
(overlapping poll, reconnect, replay); without this, position would silently
double-count.
*Pinned by:* `tests/test_duplicate_fill.py`, `tests/test_air_group_b.py` (B3),
`tests/test_monitoring.py::test_duplicate_fill_replay_is_ignored`.

**INV-004 — `Order.filled_quantity` and the fill table never disagree.**
`filled_quantity` always equals the sum of that order's recorded fills.
*Why:* `append_fill` and the later `transition_order(filled_quantity=...)`
call are two separate atomic operations (see `02_DATA_AND_PERSISTENCE.md`) —
a caller that reads the stale field between them (e.g. CAPI exposure) would
double-count or under-count.
*Pinned by:* `order_filled_matches_recorded_fills` invariant
(`tests/test_lifecycle_state_machine.py`).

---

## Candidate lifecycle

**INV-010 — A candidate is never left `APPROVED` with no order.** Every
`approve` either completes through to `ORDERED` or reverts to `PENDING`
(`revert_candidate_approval`) on any post-approval failure (risk block, dispatch
rejection).
*Why:* a stranded `APPROVED` candidate poisons re-approval (idempotency check)
and never surfaces as actionable to a human.
*Pinned by:* `no_candidate_stranded_approved` invariant
(`tests/test_lifecycle_state_machine.py`).

**INV-011 — Approve and reject are idempotent; a terminal candidate
(`rejected`/`expired`) cannot be approved without an explicit transition back
to `pending`** (which beta does not provide).
*Pinned by:* `tests/test_candidate_flow_sequences.py`.

---

## Order lifecycle (`docs/02_DATA_AND_PERSISTENCE.md`)

**INV-020 — `submitted` is never reached without a real, non-empty broker
order id.** Enforced at three layers: the `BrokerAdapter.submit_order`
contract, `plan_transition_order`'s guard (both stores), and
`_submit_pending_orders`'s validation of the returned id.
*Why:* an untrackable `SUBMITTED` order can't be polled, canceled, or
reconciled — it is functionally lost. (AIR-001 / D-022 B1.)
*Pinned by:* `tests/test_air_group_b.py::TestAir001NoSubmittedWithoutBrokerId`.

**INV-021 — `claim_order_for_submission` is the sole entry into `SUBMITTING`.**
`CREATED → SUBMITTING` does not exist anywhere else in
`ORDER_TRANSITIONS`; the claim's one atomic lock-held re-check (kill switch,
buys-paused, session-closed, still-`CREATED`) is never bypassable by a second
code path. (D-017, AIR-007 / D-023 A4.)
*Why:* this is what closes the F-001 kill-switch race and the F-002
session-close orphan — a second path into `SUBMITTING` would silently
reopen both.
*Pinned by:* `tests/test_wave0_submission_claim.py`,
`tests/test_air_remediation.py::TestAir007OnlyClaimEntersSubmitting`.

**INV-022 — A live-at-broker order is never untracked.** Every broker order
the adapter still considers live is referenced by either a local order row or
an open (`unresolved`/`needs_review`) `SubmitRecoveryRecord`.
*Why:* an orphaned live order is real capital exposure the backend has lost
visibility into (F-002).
*Pinned by:* `no_live_untracked_broker_order` invariant
(`tests/test_lifecycle_state_machine.py`), `tests/test_sim_chaos.py`.

**INV-023 — A stale `SUBMITTING` order (crash between claim and broker
persist) is recovered by idempotent re-drive, never left stranded, and never
silently retried forever.** A `TerminalBrokerError` or
`stale_submitting_max_redrive_attempts` exceeded escalates to a durable
`needs_review` record; only a transient failure re-drives. (D-022 B2 + its
Gate-B follow-up.)
*Pinned by:* `tests/test_air_group_b.py::TestAir003StaleSubmittingRecovery`.

**INV-024 — A broker/local fill divergence is escalated durably, never
silently dropped and never guessed at with a synthesized price.** The order
is held non-terminal until a human resolves the `needs_review` record.
(D-022 B3.)
*Pinned by:* `tests/test_air_group_b.py::TestAir002FillDivergence`.

**INV-025 — A same-status transition call is a no-op: no new audit row, no
side effect.** Applies identically to candidate, order, and sell-intent
transitions.
*Pinned by:* `tests/test_store_core.py::TestPlanTransitionOrder`.

---

## Sell-intent lifecycle (Phase 7, `docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_7.md`)

**INV-030 — Exactly one order origin: `candidate_id` XOR `sell_intent_id`,
never both, never neither.** Enforced by a model validator on `Order`.
*Pinned by:* `tests/test_phase7_sell_intents.py`, model-level validator tests.

**INV-031 — At most one *active* sell-intent per symbol, and the
check-and-insert is atomic under a single store-lock hold.** "Active" is
defined by INV-032 below — this invariant is about **mutual exclusion**, not
the definition itself.
*Why:* two concurrent callers (a human flatten click, a protection tick) must
never both succeed in creating a live intent for the same symbol — the second
must see and reuse the first's.
*Pinned by:* `tests/test_phase7_sell_intents.py::test_create_sell_intent_single_flight_dedup`,
the three concurrent race tests in `tests/test_phase7_flatten_atomic.py`.

**INV-032 — The ONE canonical definition of "active" sell-intent:** a
`pending`/`approved` intent, OR an `ordered` intent whose order is
non-terminal **and does not have an OPEN `needs_review` recovery record**
(`unresolved` still counts as active — only `needs_review` frees the symbol).
This definition lives in exactly one place
(`app.store.core.sell_intent_is_active`, called from both stores'
`active_sell_intent_for`) — no second reimplementation is permitted anywhere
(routes, protection engine, cockpit).
*Why (X-003):* the code had silently dropped the ADR's needs_review clause,
so a spuriously escalated protective order permanently disabled protection for
a still-breaching symbol — exactly the "protection permanently disabled by
noise" failure the ADR's "Stranded-order eligibility" clause exists to
prevent.
*Pinned by:* `tests/test_store_core.py::TestSellIntentIsActive`,
`tests/test_phase7_sell_intents.py::test_needs_review_order_does_not_block_re_protection`,
`tests/test_phase7_sell_intents.py::test_unresolved_recovery_still_counts_as_active`.

**INV-033 — No sell-intent is ever left stranded `APPROVED` with no order.**
On ANY `create_order_for_sell_intent` rejection (oversell, invalid quantity,
unpriceable LIMIT, MARKET-with-limit-price), the intent atomically self-heals
`approved → expired` in the same operation that raises the rejection — never
raise-without-expiring.
*Why (X-002):* an intent stuck `APPROVED` with no order poisons INV-031's
single-flight dedup forever — no fresh protective (or manual) intent could
ever be created for that symbol again.
*Pinned by:* `tests/test_phase7_sell_intents.py::test_no_sell_intent_stranded_approved_after_any_rejection`,
`tests/test_store_core.py::TestPlanCreateOrderForSellIntentSelfHeal`.

**INV-034 — A human-commanded `POST /positions/{symbol}/flatten` returns (or
creates) a `MANUAL_FLATTEN` intent, with exactly ONE deliberate exception: it
may DEFER to an already in-flight/live `PROTECTION_FLOOR` exit (INV-036). It
never silently hands back any OTHER reason, and never a not-yet-live protection
intent.** The route never has to inspect a returned intent's reason to know
whether it "worked": either it got a fresh `MANUAL_FLATTEN`, or the position is
already exiting via a live protective order that flatten deliberately left alone.
*Why (X-001):* checking `active_sell_intent_for` and later calling
`create_sell_intent(MANUAL_FLATTEN)` as two *separate* lock holds left a
window where a concurrent protection tick's own `create_sell_intent` call
could win the dedup — the human's flatten click would silently receive back a
`protection_floor` intent instead, which a kill switch then holds unsubmitted
while the click reads as success. Closed by making `StateStore.flatten_position`
one atomic store operation: read live position, stand down any non-live
`PROTECTION_FLOOR` exit, then create+approve+dispatch a fresh
`MANUAL_FLATTEN` — all under one continuous lock hold (mirrors D-017's
`claim_order_for_submission` pattern). The route is now a thin caller with no
supersede logic of its own.
*INV-036 carve-out (reconciled 2026-07-09):* the "always MANUAL_FLATTEN" phrasing
above was in direct tension with INV-036, which deliberately LEAVES a genuinely
in-flight/live protective order alone (never double-exits, never blind-cancels a
possibly-live order — ADR-002). Both cannot be literally true, and INV-036 is the
safety-correct one, so INV-034 is stated WITH the carve-out. When flatten defers,
it now emits a `manual_flatten_deferred` audit event (correlated to the deferred
intent, carrying the order's status) so the human's action is recorded even though
no fresh intent is created — closing the "click reads as success with no trail"
gap. **Open follow-up:** deferring to a `TIMEOUT_QUARANTINE`/`SUBMITTING` order
reports "already exiting" when the exit is not *confirmed* live (only in flight);
tightening that is a design decision (block vs. distinct outcome vs. re-drive), not
a predicate flip — routing those to the local-cancel supersede path would be the
blind-cancel hazard ADR-002 forbids. Operator identity (`actor`) is also still
dropped on all flatten paths — a separate provenance follow-up.
*Pinned by:* `tests/test_phase7_flatten_atomic.py` (esp. the concurrent race tests,
`test_live_protection_floor_order_is_left_alone`, and
`test_live_protection_floor_deferral_records_provenance`),
`tests/test_phase7_routes.py::test_flatten_http_race_with_concurrent_protection_create`,
and the `flatten` rule in `tests/test_lifecycle_state_machine.py`.

**INV-038 — A `MANUAL_FLATTEN` intent returned as "existing" must have a REAL
order** — not just the right `reason` (INV-034), but `status is ORDERED` with
a linked order. A `MANUAL_FLATTEN` intent found `pending`/`approved` with no
order is stranded and must be self-healed (expired, then a fresh one
created), never trusted as-is.
*Why:* an adversarial re-review of the X-001 diff found that
`SqliteStateStore.flatten_position` commits the intent's insert+approve and
the order's dispatch as two SEPARATE SQL transactions (the lock, not
transaction granularity, closes the concurrency race — see INV-050 — but a
hard crash between those two commits is a real durability gap). A
`MANUAL_FLATTEN` intent only sits at `pending`/`approved` transiently,
mid-dispatch; before this fix, `plan_flatten_position` treated ANY
`MANUAL_FLATTEN` active intent as "the existing exit" unconditionally,
so a later flatten call for the same symbol returned the dead, order-less
intent as success (`order=None`, HTTP 200) forever, and permanently
poisoned single-flight dedup for the symbol — a protection tick could never
create a real protective order either. `InMemoryStateStore` cannot reach
this exact state via a crash (its whole sequence is one `_atomic()` block),
but `plan_flatten_position` is a shared pure function, so the fix (only
treat `MANUAL_FLATTEN` as "existing" when `status is ORDERED`; otherwise fall
through to the same supersede/self-heal logic a stranded `PROTECTION_FLOOR`
intent already gets) closes the gap for both stores' contract, not just
sqlite's crash window.
*Pinned by:* `tests/test_phase7_flatten_atomic.py::test_stranded_manual_flatten_with_no_order_self_heals`
(both stores — confirmed to fail without the fix on memory.py too, not only
sqlite.py, since the test constructs the stranded state directly rather than
via an interrupted transaction).

**INV-035 — A stranded `PROTECTION_FLOOR` intent with no order at all (crash
between approve and order-create) is superseded by a flatten exactly like one
with a `CREATED`-but-unsent order** — a human flatten must never be a no-op
just because the thing it's superseding never got as far as having an order.
*Pinned by:* `tests/test_phase7_routes.py::test_flatten_supersedes_stranded_protection_intent_without_order`,
`tests/test_phase7_flatten_atomic.py::test_supersedes_stranded_intent_with_no_order`.

**INV-036 — A genuinely LIVE protective order (already submitted to the
broker) is left alone by a flatten request, not double-exited.** The human is
told the position is already exiting.
*Pinned by:* `tests/test_phase7_routes.py::test_flatten_leaves_live_protection_order_alone`,
`tests/test_phase7_flatten_atomic.py::test_live_protection_floor_order_is_left_alone`.

**INV-037 — `flatten_position` never cancels a live BUY order itself** —
that is a route-level pre-step (`cancel_open_buys`) that runs *before* the
atomic store call, because canceling a live order needs a broker round-trip
and the store's lock must never hold across network IO. `flatten_position`
re-reads the live position under its own lock regardless, so a buy that fills
concurrently with the cancel is still correctly sized.
*Pinned by:* `tests/test_phase7_routes.py::test_flatten_cancels_open_buys`.

---

## Correlation / audit (D-020, X-004)

**INV-040 — Every event that names a candidate carries that candidate's id as
`correlation_id`.** The default rule: `correlation_id = correlation_id or
candidate_id`, applied identically in both stores.
*Pinned by:* `correlation_id_matches_owning_candidate` invariant
(`tests/test_lifecycle_state_machine.py`).

**INV-041 — Every event that names an order whose origin is a sell-intent
(no `candidate_id`) carries that sell-intent's id as `correlation_id`.**
Resolved by looking up the owning order's `sell_intent_id` whenever neither an
explicit `correlation_id` nor a `candidate_id` is available but `order_id` is
— centrally, in the generic event-write path (`_append_event_unlocked` /
`_insert_event`), not per call site.
*Why (X-004):* the buy-side default alone left every claim/blocked-claim/
submitted/transition/fill/recovery event downstream of a protective sell's
*creation* with `correlation_id=None` — `GET
/api/events?correlation_id=<sell_intent_id>` returned only the creation
events, never the execution trail, for every sell EXCEPT the sell-intent
planners in `app/store/core.py` that already passed `correlation_id=intent.id`
explicitly.
*Pinned by:* `tests/test_phase7_sell_correlation.py` (both tests, both stores
— drives the full protective-exit lifecycle through the real monitoring-loop
functions, not just the planners).

---

## Concurrency and atomicity (`docs/02_DATA_AND_PERSISTENCE.md`, "Mutating
Operations Are Atomic")

**INV-050 — Every multi-row mutation is atomic, not just sequential.**
`SqliteStateStore` wraps writes in a single SQL transaction; `InMemoryStateStore`
relies on the same `asyncio.Lock` plus its nestable `_atomic()`
snapshot/restore context manager to guarantee the same all-or-nothing
behavior. The listed operation groups (candidate transition + audit,
candidate approval + order creation + audit, order transition + audit, fill
append + dup-check + audit, control-flag change + audit, sell-intent
transition + audit, `flatten_position`'s supersede + create + approve +
dispatch) never leave a partial write visible.
*Why:* a crash mid-write must never leave the audit trail inconsistent with
the state it's supposed to describe.
*Pinned by:* `tests/test_sqlite_store.py`, `tests/test_phase7_flatten_atomic.py`.

**INV-051 — The store's `asyncio.Lock` is never acquired reentrantly.**
Composition within an already-held lock goes through explicit `*_unlocked`
(memory) / `*_locked` (sqlite, explicit cursor) helper variants — never by a
public lock-acquiring method calling another public lock-acquiring method.
*Why:* `asyncio.Lock` is not reentrant; a nested `async with self._lock:`
deadlocks the whole process, not just the caller.
*Pinned by:* no dedicated test (a real deadlock hangs the suite, which is its
own signal) — reviewed structurally at every `flatten_position` /
`create_order_for_sell_intent` refactor.

**INV-052 — No network/broker call happens while the store lock is held.**
Broker calls (submit, cancel, poll) always happen either before acquiring the
lock or after releasing it; the lock only ever guards local state reads/writes.
*Why:* holding the lock across an `await` to a real (or even mock/sim) network
boundary would serialize all store access behind broker latency and could
deadlock the monitoring loop against a concurrent request.
*Pinned by:* structural — see `flatten_position`'s route-level
`cancel_open_buys` pre-step (INV-037) and `_submit_pending_orders`'s
claim-then-call ordering (INV-021).

---

## Control surfaces / kill switch (Rule 8)

**INV-060 — The kill switch blocks all new order intent, with exactly one
narrow, enumerated exception (D-P2):** a SELL order whose owning sell-intent's
`reason` is `manual_flatten` bypasses all controls; one whose reason is
`protection_floor` bypasses buys-paused/closed-session but **not** the kill
switch. No other bypass exists anywhere in the claim gate.
*Why:* the exit carve-out exists so a human can always de-risk even during an
emergency stop, but must never be widened into "buys still work" or "any sell
always bypasses everything."
*Pinned by:* `tests/test_phase7_routes.py::test_flatten_works_under_kill_switch`,
`tests/test_store_core.py::TestPlanClaimSellGate`.

**INV-061 — Control-surface setters (`set_kill_switch`, `set_buys_paused`,
`set_watchlist_armed`, `add_watchlist_symbol`'s `armed` field) accept only a
real `bool` — a coercible string (`"false"`) or truthy int is rejected with a
domain error, never silently coerced.**
*Why (AIR-005):* a coercion bug here means a payload *meant to disengage* the
kill switch could instead engage it (silently inverted intent).
*Pinned by:* `tests/test_air_remediation.py::TestAir005StrictBooleansStore`,
`tests/test_air_remediation.py::TestAir005StrictBooleansRoute`.

---

## Architecture boundaries (Phase 5, `.importlinter`, ADR-005 / ADR-006)

Mechanically enforced by import-linter (CI `lint-imports` step +
`tests/test_import_boundaries.py`). These are the "a PR that crosses a protected
boundary fails CI" rules of CLAUDE.md §5, made executable.

**INV-070 — Only the two concrete venue ports import the Alpaca SDK.**
`app.broker.alpaca_paper` and `app.marketdata.alpaca_stream` are the only
modules that may `import alpaca`; no UI, API, facade, engine, or store module
ever does (invariant #5 — "the UI never calls Alpaca, only the adapter does",
generalized).
*Why:* a stray SDK import anywhere else is a venue-coupling / live-trading leak
path that bypasses the adapter's paper-only, quarantine, and rate-limit
guarantees.
*Pinned by:* `tests/test_import_boundaries.py::test_alpaca_sdk_is_confined_to_the_two_concrete_ports`
(direct proof) + `::test_only_sanctioned_modules_transitively_reach_the_alpaca_sdk`
(TRANSITIVE proof — the two ports + two factories + `app.main` are the only reachers;
ADR-006 Finding 1), both INI-independent, + the `alpaca-sdk-confined-to-adapter`
contract in `.importlinter`.

**INV-071 — The Streamlit cockpit imports no backend (`app.*`) code.** The UI is
a thin client: it reaches the backend only over HTTP through
`cockpit.api_client` and owns no strategy/risk/order/fill/position logic
(invariant #4).
*Why:* any `cockpit → app` import lets business logic or state leak into the
disposable UI, breaking the "backend owns all truth" boundary and the future
Dash-swap path.
*Pinned by:* `tests/test_import_boundaries.py::test_cockpit_imports_no_backend_code`
+ the `cockpit-is-a-thin-client` contract.

**INV-072 — The execution engine is venue-agnostic.** Engine modules
(`monitoring`, `reconciliation`, `policy`, `position`, `protection`, `strategy`,
`strategy_loop`, `features`, `transitions`, `events`, `approval`) import the
abstract ports (`app.broker.adapter`, `app.marketdata.service`) but never a
concrete adapter (`alpaca_paper`/`mock`/`sim`/`alpaca_stream`) or the SDK.
*Why:* the single-writer engine must stay IO-free/testable and swappable per
venue; a concrete-adapter import couples decision logic to one venue.
*Pinned by:* `tests/test_import_boundaries.py::test_engine_never_reaches_a_concrete_venue_implementation`
(INI-independent grimp proof — no engine module reaches a concrete adapter by any
chain) + the `engine-is-venue-agnostic` contract (`::test_all_import_contracts_hold`).

**INV-073 — The shared model kernel is a leaf.** `app.models` imports no other
`app` layer, so the type kernel every layer depends on can never take a
dependency back on a higher layer.
*Why:* a back-edge from `models` to any layer creates an import cycle and
defeats the layering the other contracts rely on.
*Pinned by:* `tests/test_import_boundaries.py::test_models_kernel_imports_no_app_layer`
(INI-independent grimp proof) + the `models-is-a-leaf` contract
(`test_all_import_contracts_hold`).

**INV-074 — API route handlers reach the store/engine/broker only through the
typed facade (ADR-005 target; ratchet-enforced).** New route→backend imports are
forbidden; the current unmigrated edges are an explicit `ignore_imports`
punch-list that Phase 6 empties one route at a time. `unmatched_ignore_imports_alerting
= error` means a migrated route's stale ignore fails the build until removed —
the boundary can only tighten.
*Why:* direct route→store/broker/monitoring access bypasses the facade's
quarantine/timeout/TradingState/event-log seams (ADR-005). The ratchet stops the
partial migration from regressing.
*Pinned by:* the `api-routes-reach-backend-only-via-facade` contract
(`test_all_import_contracts_hold`).

---

## Superseded / historical

None yet. When an invariant is later found to be wrong or is deliberately
loosened, mark it **superseded by INV-0xx** here rather than deleting it —
the history of "we used to require X, then decided Y" is itself useful context
for the next reviewer.
