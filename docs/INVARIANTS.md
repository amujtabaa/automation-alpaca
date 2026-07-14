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
- Probe each invariant over its **observable scope** (entity lifetime, session,
  restart boundary), varying every free parameter — a pinning test that held a
  parameter fixed proves the implementation's frame, not the invariant (the
  SOL-F-002 lesson: "monotone" held per-call but not per-lifetime). And probe
  **every ingress** the computation trusts, not just the newest one (SOL-F-003:
  history rows were never screened).
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

**INV-075 — Order status is projected by latest-lifecycle-event-wins over an
append-ordered, single-writer, transition-guarded log; adding ANY asynchronous or
out-of-order order-status ingest path MUST first preserve that ordering (route it
through the single-writer transition guard) OR add authority-aware conflict
resolution with conflict tests — before it ships.** `project_order_status` is a **pure
`sequence`-ordered latest-wins fold**: the `ORDER_TRANSITIONS` legality it assumes is
enforced upstream at the write path (`plan_transition_order`), not re-checked by the
fold, and it does **not** read `source`/`authority` (ADR-008 "Truth model (this flow)").
That is correct only while
every order-status writer is the single-writer engine appending in causal order —
true today (REST-poll / reconcile / engine only; the one websocket carries
market-data prices, not order status). A future `trade_updates` websocket, or a
reconciliation that asserts a conflicting fact, could deliver an earlier real-world
fact at a later `sequence`, which latest-wins would mis-project.
*Why:* an out-of-order broker fact overwritten by a stale engine echo would diverge
the order-status read-model. Position/P&L is firewalled from this (INV-001 / INV-9:
only fills move quantity), but the status-gated claim/cancel/flatten logic is not.
This is the tripwire that forces the design decision **at the point** the async path
is introduced, instead of silently relying on an ordering guarantee that path breaks.
*Pinned by:* `tests/test_wo0007b_stageb_projector.py` (authority-independent
latest-wins) + ADR-008 "Truth model (this flow)". *(Forward-looking guard, REV-0003:
no reachable violation today; it fires the day someone builds async status ingestion.)*

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
gap. *Resolved (REV-0002 F-001, WO-0015):* the earlier open follow-up — that
deferring to a `TIMEOUT_QUARANTINE`/`SUBMITTED`/`CANCEL_PENDING` order reported
"already exiting" identically to a real submitted exit — is fixed by the **distinct
outcome** option (never the blind-cancel supersede path ADR-002 forbids):
`FlattenResult.deferred` / `FlattenResponse.deferred` + `deferred_order_status`
now make the deferral explicit, and the cockpit renders a distinct "no manual
order submitted — already exiting … monitoring" message instead of "flatten
submitted". *Resolved (REV-0002 F-002, WO-0015):* operator identity (`actor`) is
no longer dropped — the command actor is threaded route→facade→store and recorded
on the `manual_flatten_deferred` event's payload (deferred path) and the created
manual-flatten's `sell_intent_created` event payload (create path); it defaults to
`"system"` for internal/test callers and for protection-tick `create_sell_intent`.
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

## Execution envelopes (ADR-010 / WO-0016)

**INV-076 — An envelope's remaining quantity is decremented ONLY by deduped
fill events.** `ExecutionEnvelope.remaining_quantity` starts at `qty_ceiling`
and moves only through `record_envelope_fill` (both stores), which appends the
FILL `ExecutionEvent` through the dedupe-aware writer and applies the decrement
ONLY when the append actually wrote a new event — a replayed `dedupe_key` is
counted exactly once. No other store operation touches the field; submitted/
ack-shaped facts structurally cannot (the sell-side analogue of invariants 8/9).
*Why:* the qty ceiling is the hard scope rail of the human's mandate (ADR-010
§2); if anything but a fill fact could move it, the envelope could under- or
over-report how much of the mandate is spent.
*Pinned by:* `tests/test_wo0016_envelope_fills.py`
(`test_duplicate_fill_is_counted_exactly_once`,
`test_transitions_and_raw_event_appends_cannot_move_remaining`).

**INV-077 — At most ONE envelope per sell intent is ACTIVE, with no observable
two-ACTIVE window.** Activation checks the intent's other envelopes under the
same lock/transaction that writes the status (in-memory: under-lock scan;
SQLite: explicit check + the `idx_envelopes_one_active` partial unique index as
a structural backstop). Amendment-by-supersession swaps ACTIVE inside one
atomic unit, and concurrent supersedes of the same envelope yield exactly one
ACTIVE successor.
*Why:* two live mandates for one intent means two executors repricing the same
position — double exposure the human approved once.
*Amended (WO-0027 / REV-0023 F6):* the invariant binds in SUBSTANCE, not just
status: supersession refuses while a venue-live working order exists, sweeps
staged CREATED orders in its atomic unit, and conserves the mandate
(successor ceiling ≤ predecessor's current remaining, read under the same
lock). One human approval can never become two live venue orders or a wider
live mandate via amendment.
*Pinned by:* `tests/test_wo0016_envelope_supersede.py`
(`test_concurrent_supersedes_yield_exactly_one_active_successor`,
`test_second_activation_for_same_intent_is_blocked`).

**INV-078 — Envelope bounds never mutate in place; amendment is by
supersession only.** The model validates bounds at construction; neither store
exposes a bound-update operation (the SQLite `UPDATE` lists only status/
counters/linkage/timestamps — bounds are structurally absent), and the
supersede operation links predecessor and successor both ways.
*Why:* the bounds ARE the human approval (ADR-010 §1); mutable bounds would
let post-approval drift silently widen a mandate.
*Pinned by:* `tests/test_wo0016_envelope_model.py` (construction rails) +
`tests/test_wo0016_envelope_supersede.py`
(`test_supersede_swaps_active_atomically_and_links_both`).

**INV-079 — BREACHED and EXHAUSTED are terminal-pending-human, and a freeze is
never exited by a fill.** Neither status has an outgoing edge
(`ENVELOPE_TRANSITIONS`); a breached/exhausted mandate resumes only as a NEW
envelope through the approval gate. A fill landing on a FROZEN envelope is
recorded and decremented (facts are never hidden) but the envelope stays
FROZEN; completion at remaining==0 happens on RESUME, atomically with it.
*Why:* quarantine posture (ADR-001/ADR-010 §3): an envelope stopped for a
human, or by the kill switch, must never silently resume through a data event.
*Pinned by:* `tests/test_wo0016_envelope_transitions.py` (matrix: terminal
rows empty) + `tests/test_wo0016_envelope_fills.py`
(`test_fill_while_frozen_decrements_but_never_unfreezes`,
`test_overfill_of_the_hard_ceiling_breaches`).

**INV-080 — Envelope activation is one atomic unit, and the kill switch both
blocks and preempts it.** `approve_envelope_activation` (both stores) runs
dedup → HALTED check → create → approve → activate → events under ONE lock/
transaction hold with no await between the control check and the durable
writes: a kill landing first blocks the op with ZERO artifacts; landing after
leaves an ACTIVE envelope that the kill hook freezes in the SAME atomic unit
as the control change. Any `→ ACTIVE` transition (first activation OR resume)
is refused while HALTED; releasing the kill NEVER auto-resumes a frozen
envelope — resume is an explicit human action.
*Why:* invariant 10 (kill blocks new order intent) — an ACTIVE envelope IS
standing, pre-approved order intent; any window or auto-resume would let
autonomous submissions restart without the human who stopped them.
*Pinned by:* `tests/test_wo0017_envelope_approval.py`
(`test_halted_blocks_approval_with_zero_artifacts`,
`test_kill_race_never_ends_with_an_active_envelope_under_halted`) +
`tests/test_wo0017_precedence.py` (`test_kill_freezes_every_active_envelope_atomically`,
`test_release_never_auto_resumes`, `test_resume_and_activation_are_refused_while_halted`).

**INV-081 — Manual flatten preempts envelopes; the ADR-003 deferral leaves the
live exit's envelope managing it.** When a flatten takes over the exit path
(create, or already-flat), every non-terminal envelope for the symbol is
CANCELLED through legal edges inside the SAME lock/transaction, sequenced
BEFORE the flatten's own writes — an envelope never races, blocks, or
outlives the human's direct backstop (ADR-010 §4, D-2). When the flatten
DEFERS to an in-flight PROTECTION_FLOOR exit (ADR-003/WO-0015 semantics,
unchanged), that exit's envelope is deliberately left alone: it is the live
order's manager, and cancelling it would strand the very exit the flatten
defers to.
*Why:* the backstop must dominate its dependents without destroying the
mechanism executing the exit the human already has in flight.
*Amended (WO-0024 / REV-0023 F3):* preemption extends to the preempted
envelopes' STAGED orders — every CREATED (never venue-submitted) order staged
by a preempted envelope is locally CANCELLED in the SAME atomic unit,
sequenced after the envelope's own cancellation events. The kill switch does
the same for the envelopes it freezes (a staged order IS pending order
intent, INV-060). Belt two: ``redrive_staged_envelope_action`` re-validates
against CURRENT state and time before any venue call — non-ACTIVE envelope,
staged-action age past the redrive ceiling, or any ``validate_action`` rail
(now including TTL and session phase, making ADR-010 §1's "bounds checked
twice" true for every §2 rail) refuses with zero venue calls and locally
cancels the staged order. Refusals are staleness, not defects: the envelope
is never frozen by this path (INV-082 stays a defect-only signal).
*Pinned by:* `tests/test_wo0017_precedence.py`
(`test_flatten_cancels_the_symbols_envelopes_before_proceeding`,
`test_flatten_on_a_flat_position_still_cancels_stale_envelopes`,
`test_flatten_cancels_frozen_and_preactivation_envelopes_too`,
`test_deferral_to_a_live_protection_exit_leaves_its_envelope_alone`) +
`tests/test_phase7_flatten_atomic.py` (kept green, unmodified) +
`tests/test_wo0021_envelope_chaos.py`
(`test_flatten_mid_reprice_staged_order_never_reaches_the_venue` — the
flipped WO-0021 finding pin) + `tests/test_wo0019_engine_seam.py`
(`test_kill_between_staging_and_venue_call_blocks_at_the_claim`,
`test_redrive_of_a_frozen_envelopes_staged_order_cancels_locally`,
`test_redrive_past_staleness_ceiling_cancels_locally`,
`test_write_time_ttl_rail_bites_at_the_seam`,
`test_write_time_session_phase_rail_bites_at_the_seam`) +
`tests/test_rev0023_phase_a_pins.py` (the three flipped `PIN_F3_*` tests).

**INV-082 — Plan/write validator disagreement is a DEFECT signal: freeze +
ENVELOPE_PLAN_DIVERGENCE, zero venue calls.** ``stage_envelope_action`` (both
stores) re-runs the SAME ``app.sellside.policy.validate_action`` the policy
ran at plan time, inside one lock/transaction with the HALTED check and the
durable writes. Any rail violation the plan claimed was valid — or a
structural mismatch (REPRICE with no live working order; SUBMIT over one) —
freezes the envelope and appends ``ENVELOPE_PLAN_DIVERGENCE`` with the rail,
detail, and snapshot fingerprint; no order is minted and the executor makes
no venue call (ADR-010 §5, D-3).
*Why:* if plan-time and write-time validation can disagree silently, the
"bounds checked twice" guarantee is theater — the divergence event is the
tripwire that turns a validator drift into an operator-visible incident.
*Amended (WO-0025 / REV-0023 F4):* the false-positive class is gone — plan
time and write time now evaluate the SAME live working-order predicate
(ADR-010 §5 amendment), so a healthy second leg (filled tranche, stop
continuation, disposition-cancel re-entry) never trips the tripwire; a
divergence event again MEANS a defect (or a benign plan/write race on a
freshly-changed fact — the §5 classification refinement itself is WO-0029).
*Amended again (WO-0029A, accepted):* write-time rejections are now
CLASSIFIED — state-dependent rails (qty_ceiling, structural) refuse as
benign ``refused_stale`` events without freezing; only deterministic-rail
disagreement (floor/ttl/phase/cooldown/budget) and reduce_only fire the
divergence tripwire. A divergence event now ALWAYS merits investigation.
*Pinned by:* `tests/test_wo0019_engine_seam.py`
(`test_write_time_rejection_freezes_with_divergence_event`,
`test_divergence_makes_zero_venue_calls`,
`test_structural_disagreement_is_also_divergence`).

**INV-083 — Envelope budget accounting is atomic with the order it pays for,
and a quarantined leg pauses the envelope.** The ENVELOPE_ACTION event (the
policy's history-derived budget/cooldown accounting substrate) commits in the
SAME transaction as the staged order row — a crash between them is
structurally impossible, and recovery re-drives the SAME staged order without
a new accounting event (no double-spend). While ANY of an envelope's orders
is in TIMEOUT_QUARANTINE, staging refuses (`EnvelopeActionPausedError`) —
the ADR-002 rule that an ambiguous outcome is never blind-re-driven extends
to the whole envelope. The venue leg enters SUBMITTING only through the
existing submission claim (INV-021 unbroken).
*Why:* budget accounting that can desynchronize from its order lets a crash
mint free replaces; acting on an envelope with an unknown-fate order is the
blind-resubmit failure mode ADR-002 exists to prevent.
*Pinned by:* `tests/test_wo0019_engine_seam.py`
(`test_sqlite_staging_is_all_or_nothing`,
`test_ambiguous_replace_quarantines_and_pauses_the_envelope`,
`test_transient_failure_releases_and_redrive_spends_no_new_budget`,
`test_kill_between_staging_and_venue_call_blocks_at_the_claim`).

**INV-084 — Reduce-only is enforced against the live fill-derived position at
every pre-venue seam.** ``stage_envelope_action`` (both stores) reads the
symbol's fill-derived position projection under the SAME lock/transaction as
the staging writes and refuses any SELL whose quantity exceeds it
(``ENVELOPE_PLAN_DIVERGENCE`` rail ``reduce_only``, envelope FROZEN, zero
venue calls); ``redrive_staged_envelope_action`` re-checks the same bound
before its venue call and locally cancels on violation. The envelope's own
``remaining_quantity`` counter is NOT the enforcement point for this rail —
both counters gate independently, so a fill/flatten racing the stage (or a
stale envelope counter, REV-0023 F5) cannot produce a venue SELL the account
cannot cover. Position source is the deduped fill log (single-writer truth),
never the broker snapshot.
*Why:* ADR-010 §2 declares reduce-only a HARD rail; before WO-0026 the only
implementation was a validator locking the boolean flag — 180 shares were
SOLD against a zero-share book in the REV-0023 Phase A repro, with harm
surfacing only post-venue as an overfill quarantine, exactly what H1 forbids.
*Pinned by:* `tests/test_rev0023_phase_a_pins.py`
(`test_PIN_F1_sell_against_zero_position_never_reaches_venue` — the flipped
P0 finding pin) + `tests/test_wo0019_engine_seam.py`
(`test_position_shrink_between_plan_and_write_hits_reduce_only`,
`test_redrive_recheck_catches_position_shrink`).

**INV-085 — A ceiling-violated mandate never terminates in the success
state.** A broker-authoritative overfill of ``qty_ceiling`` chains the
envelope to ``BREACHED`` in every state that can receive a fill — including
FROZEN (edge added by the accepted WO-0029A amendment). Remaining floors at
0 (never negative), the overfill facts stay in the FILL event payload, and a
resume of a breached envelope is structurally refused; an EXACT fill-to-zero
while FROZEN remains benign (resume auto-completes, INV-079 unchanged).
*Why:* before this, an overfill while FROZEN was clamped + flagged and the
envelope resumed into COMPLETED — the audit trail filed a violated mandate
as a success (REV-0023 SPEC-05).
*Pinned by:* `tests/test_rev0023_phase_a_pins.py`
(`test_frozen_overfill_chains_breached_never_completed`,
`test_frozen_exact_fill_still_completes_on_resume`) +
`tests/test_wo0016_envelope_transitions.py` (ADR-mirror table).

**INV-086 — The working stop is monotone over the ENVELOPE LIFETIME, and only
validated data ever drives it.** Three mechanisms, all in the pure policy:
(1) historical ratchet candidates are computed with the urgency of their OWN
epoch (``urgency_at``), so a session-phase boundary that widens time-to-close
can never loosen an already-ratcheted stop; (2) the still-filling 30s bucket
is excluded from the ratchet (``last_bar_open``) — the stop ratchets only on
immutable completed bars, so an intra-bucket rewrite cannot lower it; (3) the
ENTIRE active tape is screened by ``_snapshot_invalid_reasons`` before any
feature computation — a stale/crossed/non-finite historical print never
drives bars, ATR, VWAP, regime, sizing, or the stop (H6, whole-tape scope).
Additionally the zero-allowance protective probe is REPORTED (participation
ClampNote) and a venue-REJECTED probe doubles the next probe's floor, capped
by remaining (adjudicated by the operator 2026-07-12); and a
``refused_stale`` event never consumes the tranche entitlement (WORKING
actions only).
*Why:* SOL-0001 crosswise findings SOL-F-002/003/004 + DRIFT-SVD-2 — the
stop loosened exactly at session opens and during intra-bar selloffs, a
single poisoned historical print could re-anchor every feature, the 1-share
probe was silent, and a benign refusal burned the one tranche.
*Pinned by:* `tests/test_sol0001_incumbent_pins.py` (all six tests; each
mechanism mutation-checked — including the pin itself, whose first version
was vacuously green below the floor and was caught by the R4 discovery
sweep).

**INV-087 — At most one ACTIVE execution envelope per SYMBOL.** The
single-ACTIVE mandate is scoped per ``symbol``, not per ``sell_intent_id``:
activation (``approve_envelope_activation``), resume (``transition_envelope``
→ ACTIVE), and supersession all refuse if any OTHER envelope for the same
symbol is already ACTIVE — enforced under the store lock/transaction in both
stores (the SQLite twin is the partial unique index
``idx_envelopes_one_active ON execution_envelopes(symbol) WHERE
status='active'``).
*Why:* REV-0023 Phase-A2 P0. Scoping the guard per intent left a hole: a
second sell_intent for the same symbol (e.g. across a session boundary that
EXPIREd the first intent while its envelope stayed ACTIVE, since the envelope
path never advances its backing intent past APPROVED) could activate a SECOND
envelope for the same symbol/position. Two ACTIVE mandates could then each
stage a full-size SELL against one position — a broker-authoritative
oversell / double-book the single-mandate design exists to prevent. The
orphaned first envelope keeps working its exit; a redundant second mandate is
simply refused.
*Pinned by:*
`tests/test_rev0023_phase_a2_pins.py::test_PIN_P0_no_two_active_envelopes_per_symbol_across_session_boundary`
(both stores; the session-boundary reproduction now refuses the second
activation) and `tests/test_wo0032_per_symbol_mandate.py` (direct guard +
supersession still permitted).

---

## Superseded / historical

None yet. When an invariant is later found to be wrong or is deliberately
loosened, mark it **superseded by INV-0xx** here rather than deleting it —
the history of "we used to require X, then decided Y" is itself useful context
for the next reviewer.
