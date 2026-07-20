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

**INV-002 — Local or synthetic logic never creates a negative/overfilled
position; broker-authoritative excess is recorded and quarantined.** A
LOCAL/SYNTHETIC fill that exceeds the order or would overdraw the long position
is rejected before fill, event, envelope, or position mutation. An equivalent
BROKER_AUTHORITATIVE fact is unwelcome reality: persist its raw `FILL`, append a
durable `QUARANTINED` fact atomically, block autonomous spawn, and require manual
review—even when the resulting position remains positive.
*Why:* beta is long-only, but hiding venue truth is more dangerous than projecting
the contained exception; record-first envelope ingress must survive a crash before
the compatibility fill row is bridged.
*Pinned by:* `tests/test_wo0113_store_parity.py` (dual-store order/envelope,
dedupe-poison, and SQLite-reopen cases), `tests/test_monitoring.py::
test_broker_authoritative_overfill_is_recorded_and_quarantined`, and
`position_never_negative` for non-broker state-machine input.

**INV-003 — A fill's `source_fill_id`, when present, binds immutable economics.**
An exact order/symbol/side/quantity/price replay is a duplicate no-op. Reusing the
identity with changed economics is a durable `fill_duplicate_conflict` requiring
manual review; it never appends a second fill/FILL or mutates position.
*Why:* polling-based reconciliation can observe the same broker fill twice
(overlapping poll, reconnect, replay); without this, position would silently
double-count.
*Pinned by:* `tests/test_duplicate_fill.py`, `tests/test_air_group_b.py` (B3),
`tests/test_monitoring.py::test_duplicate_fill_replay_is_ignored`.

**INV-004 — Raw fill truth is authoritative; the bounded Order progress scalar
never exceeds its immutable quantity.** Normally `Order.filled_quantity` equals
the order's recorded-fill sum. If broker-authoritative fills exceed the order,
the raw fill/FILL and position retain the full quantity while the Order read model
is `min(raw_sum, order.quantity)` and the symbol is quarantined. Adapter delta
calculation always receives the raw recorded sum, never the capped scalar.
*Why:* clipping broker truth would re-report/double-count fills; allowing the
compatibility scalar past the order ceiling would violate lifecycle consumers.
*Pinned by:* `tests/test_wo0113_store_parity.py`,
`tests/test_monitoring.py::test_broker_authoritative_overfill_is_recorded_and_quarantined`,
and `order_filled_matches_recorded_fills` for the non-quarantined state machine.

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
code path. *WO-0113 operator-ratified branch behavior — pending REV-0033
independent review:* a BUY claim also recomputes the current risk-limit
exposure under that same lock/transaction, including exact accepted-submit
UNKNOWN/recovery ownership that appeared after order mint. Before either side
can enter `SUBMITTING`, a side-independent ownership rail also refuses a
projected-`CREATED` order that already carries a concrete broker id or its own
accepted-submit UNKNOWN fact; the same local id is never blindly submitted a
second time. (D-017, AIR-007 / D-023 A4.)
*Why:* this is what closes the F-001 kill-switch race and the F-002
session-close orphan — a second path into `SUBMITTING` would silently
reopen both.
*Pinned by:* `tests/test_wave0_submission_claim.py`,
`tests/test_air_remediation.py::TestAir007OnlyClaimEntersSubmitting`, and
`tests/test_wo0113_capi_uncertainty.py::test_final_buy_claim_rechecks_uncertainty_created_after_order_mint`,
plus `tests/test_wo0113_acceptance_identity.py::test_created_order_with_own_venue_identity_cannot_be_resubmitted`.

**INV-022 — A live-at-broker order is never untracked.** Ordinarily, every broker
order the adapter still considers live has one durable local owner: a local
order row or an open (`unresolved`/`needs_review`) `SubmitRecoveryRecord`.
*WO-0113 operator-ratified branch behavior — pending REV-0033 independent
review:* if neither ordinary owner can be written after acceptance, one
exact canonical `UNKNOWN_RECONCILE_REQUIRED` execution fact temporarily owns
the accepted broker identity until repair adopts it or creates that recovery;
the ordinary acceptance audit may or may not already have succeeded.
*Why:* an orphaned live order is real capital exposure the backend has lost
visibility into (F-002).
*Pinned by:* `no_live_untracked_broker_order` invariant
(`tests/test_lifecycle_state_machine.py`), `tests/test_sim_chaos.py`, and the
exact provenance/identity pins in `tests/test_wo0113_submit_acceptance_fallback.py`.

**INV-023 — A stale `SUBMITTING` order (crash between claim and broker
persist) is recovered by idempotent re-drive, never left stranded, and never
silently retried forever.** A `TerminalBrokerError` or
`stale_submitting_max_redrive_attempts` exceeded escalates to a durable
`needs_review` record; every no-progress pass consumes that same durable cap,
including an unpriceable MARKET order, while only a transient failure re-drives.
(D-022 B2 + its Gate-B follow-up.)
*Pinned by:* `tests/test_air_group_b.py::TestAir003StaleSubmittingRecovery` and
`tests/test_wo0113_lifecycle_closure.py::test_unpriceable_stale_submitting_uses_durable_attempt_cap`.

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
canceling a live order needs a broker round-trip, and the store's lock must
never hold across network IO. *Amended 2026-07-17 (WO-0107 Option B; the
original prose described the superseded unconditional route-level pre-step):*
the store now DETECTS still-open BUYs under its own deciding lock and returns
``FLATTEN_BUYS_OPEN`` (minting nothing); the **facade** performs the
`cancel_open_buys` broker call off-lock and retries, bounded, failing closed
to a 409 if buys keep reappearing. The invariant itself is unchanged — the
store still never makes the broker call — but the cancel is now
signal-driven, not an unconditional pre-step, so a genuinely-flat symbol's
unrelated resting BUY is never touched. `flatten_position` re-reads the live
position under its own lock regardless, so a buy that fills concurrently with
the cancel is still correctly sized.
*Pinned by:* `tests/test_phase7_routes.py::test_flatten_cancels_open_buys`,
`tests/test_wo0036_r2_flatten_buys_open.py` (signal, retry convergence,
flat-symbol-buy-untouched, fail-closed bound).

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
*Pinned by:* structural — see the flatten `FLATTEN_BUYS_OPEN` signal-then-
off-lock-cancel-then-retry flow (INV-037, as amended 2026-07-17 for WO-0107
Option B) and `_submit_pending_orders`'s claim-then-call ordering (INV-021).

---

## Control surfaces / kill switch (Rule 8)

**INV-060 — The kill switch blocks all new order intent; a Halted exit requires
the explicit audited emergency-reduce capability.** Ordinary manual flatten,
direct `MANUAL_FLATTEN` intent creation, autonomous protection, legacy SELL
dispatch, and every new order-intent path remain blocked in `Halted`.
*WO-0113 operator-ratified branch behavior — pending REV-0033 independent
review:* the emergency command alone may carry one active,
symbol/session-scoped capability through the same reduce-only mint path; an
ambient grant never authorizes an
ordinary call. This scoped reducing authorization does not lift or transition
the global composed state out of `Halted`. The authorized intent, order, and
resolution remain bound to the same lock-held session as the grant: an explicit
foreign `session_id` is rejected, and a clock rollover cannot rebind the
outcome. This does not revoke an already-authorized `MANUAL_FLATTEN`
order that was minted while Active: its later submission claim may finish under
Halted (accepted D-P2 claim semantics), while a `PROTECTION_FLOOR` claim may
bypass buys-paused/closed-session but never Halted.
*Why:* the exit carve-out remains available without turning a durable grant
into an invisible global bypass.
*Pinned by:* `tests/test_wo0113_emergency_override.py`
(`test_ordinary_flatten_cannot_consume_emergency_grant`) and
`tests/test_wo0113_sell_boundary.py`
(`test_direct_manual_intent_creation_is_denied_while_halted`,
`test_direct_manual_dispatch_rechecks_halted_and_self_heals`).

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

**INV-076 — An envelope's remaining quantity is charged ONLY by an exactly-once
canonical fill fact.** `ExecutionEnvelope.remaining_quantity` starts at
`qty_ceiling` and moves only through `record_envelope_fill` (both stores). The
normal path appends a deduped FILL and decrements only when that event is new.
If the same canonical FILL was already appended without envelope ownership, an
append-only `ENVELOPE_FILL_ATTRIBUTED` marker may apply it once to one uniquely
bounded envelope. The marker is globally deduped from the fill key, preserves
the immutable FILL, and is ignored by position projection; a marker alone can
never move shares. A supplied child id must name a real Order with exactly one
matching `ENVELOPE_ACTION`. Before every NEW application, repair, or replay,
all canonical envelope FILLs and markers must form one sequence-ordered,
contiguous `remaining_before -> remaining_after` chain from `qty_ceiling`
exactly to the stored remaining quantity. Cadence validates direct-attributed
as well as uniquely parented orphan FILLs and propagates any identity/chain
conflict before venue action. Its durable high-water checkpoint advances only
after the selected execution-log tail validates completely; an error leaves it
unchanged so restart retries the same facts. No submitted- or ack-shaped fact
can move the field (the sell-side analogue of invariants 8/9).
*WO-0113 operator-ratified amendment — pending REV-0033 independent review.*
*Why:* the qty ceiling is the hard scope rail of the human's mandate (ADR-010
§2); if anything but a fill fact could move it, the envelope could under- or
over-report how much of the mandate is spent.
*Pinned by:* `tests/test_wo0016_envelope_fills.py`
(`test_duplicate_fill_is_counted_exactly_once`,
`test_transitions_and_raw_event_appends_cannot_move_remaining`) and
`tests/test_wo0113_attribution_repair.py`
(`test_unattributed_fill_is_applied_once_by_append_only_marker`,
`test_record_first_keeps_one_fill_and_marker_alone_cannot_move_position`, plus
the identity/lineage conflict matrix,
`test_new_repair_rejects_an_existing_unreflected_marker`,
`test_cadence_validates_direct_attributed_fill_chain`, and
`test_attribution_repair_uses_durable_tail_checkpoint`).

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
*Amended 2026-07-17 (WO-0107 Option B + WO-0036 R2 Part B, operator-ratified;
re-verified against final code):* two fail-closed PRE-outcomes now precede
"takes over", neither weakening it. (1) A held symbol with a still-open BUY
returns ``FLATTEN_BUYS_OPEN`` before any preemption — the caller cancels the
buys off-lock and retries into the normal take-over/defer flow (no
MANUAL_FLATTEN SELL is ever minted beside a DETECTED open BUY — the
``OPEN_BUY_STATUSES`` set ``CREATED``/``SUBMITTED``/``PARTIALLY_FILLED`` read
under the deciding lock; venue-uncertain ``SUBMITTING``/``TIMEOUT_QUARANTINE``
BUYs stay outside the signal, as they were outside the pre-Option-B cancel
set — and, per the 2026-07-18 REV-0029 correction, so did ``CANCEL_PENDING``
and the ``APPROVED`` BUY *candidate* handoff, both invisible to the order-only
scan. WO-0108 closed the projected-order and candidate-handoff portions of
P0-1/P0-2: P0-1 widens the flatten detection set to
``FLATTEN_BLOCKING_BUY_STATUSES`` (adds ``SUBMITTING`` / ``CANCEL_PENDING`` /
``TIMEOUT_QUARANTINE``; the facade cancels only the cancellable subset and
fails closed on the rest), and P0-2 adds the cross-side same-symbol claim rail
+ same-symbol BUY-candidate stand-down + dispatch refusal, so a BUY and an exit
SELL cannot both pass those projected-order seams).
*Amended 2026-07-18 (WO-0109 Cluster A / REV-0029 round 2):* the remaining
terminal-local/venue-live schedule is closed. A stale ``CREATED`` snapshot can
no longer cancel a BUY after the submission claim advances it: the local
cancel is a store-atomic compare-and-swap with ``expected_from=CREATED`` and an
advanced row stays non-terminal or follows the broker-cancel path. Flatten and
the final exit-SELL claim now consume the same BUY execution-exposure
projection, combining their existing order-status boundary with open
``unresolved`` and ``needs_review`` BUY recoveries. Thus a local-terminal BUY
which may still execute at the paper venue remains blocking in both stores.
Mutation-verified pins: ``tests/test_wo0109_round3_remediation.py``. (2) A symbol whose
obligation is retained only by an open ``needs_review`` recovery child
REFUSES the flatten at the preemption residual check (``FlattenBlockedError``)
— unreconciled possible venue SELL exposure quarantines the manual path too
(INV-090). Whenever the flatten DOES take over, this invariant applies
verbatim. *Additional pins:*
`tests/test_wo0036_r2_flatten_buys_open.py`,
`tests/test_wo0036_r2_close_and_recovery_ownership.py`
(`test_needs_review_retention_is_fail_closed_but_not_monopolizing`).
*WO-0113 operator-ratified amendment — pending REV-0033 independent review:*
exit
preemption now closes the full proposal-to-order epoch. Candidate admission
refuses during a same-symbol exit, final dispatch expires rather than parks a
candidate that loses the race, and a successful exit stands down every
PENDING/APPROVED candidate plus every safely local event-projected `CREATED`
BUY. There is no `filled_quantity == 0` exception. A broker id or open recovery
makes a projected-CREATED order ineligible for local cancel and remains
venue-execution exposure; an accepted-submit uncertainty fact has the same
local-cancel effect until ownership/reconciliation, including for direct SELL.
Pins: `tests/test_wo0113_primary_remediation.py`
(`test_exit_preempt_cancels_nonzero_filled_created_buy`,
`test_envelope_stage_defers_without_canceling_recovery_owned_created_buy`,
`test_candidate_creation_is_refused_during_exit_preemption`, and
`test_exit_blocked_candidate_dispatch_expires_instead_of_reviving`).

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

**INV-085 — A ceiling-violated LIVE mandate never terminates in the success
state.** A broker-authoritative overfill of ``qty_ceiling`` chains the
envelope to ``BREACHED`` when it is still working the mandate — i.e. from
``ACTIVE`` or ``FROZEN`` (the FROZEN edge added by the accepted WO-0029A
amendment). Remaining floors at 0 (never negative), the overfill facts stay in
the FILL event payload, and a resume of a breached envelope is structurally
refused; an EXACT fill-to-zero while FROZEN remains benign (resume
auto-completes, INV-079 unchanged).

**Scope (narrowed by REV-0023 Phase-A2 spec-0, decision 3a):** the
BREACHED-chain applies to the two NON-TERMINAL states only (``ACTIVE`` /
``FROZEN``). A fill arriving after the envelope has ALREADY reached a terminal
state (``COMPLETED`` / ``EXPIRED`` / ``EXHAUSTED`` / ``SUPERSEDED`` /
``CANCELLED``) is recorded as a ``late_fill`` with the terminal status left
unchanged — a done mandate is not retroactively un-terminated into BREACHED by
a straggler execution. The independent backstop for a real position short in
that case is the POSITION-level ADR-001 quarantine on ``append_fill``
(``fill_overfill_quarantined`` + the projection-derived quarantine latch), which
is unaffected by the envelope's terminal status. So a *violated live mandate* is
never filed as a success, and a *late fill on a finished mandate* is faithfully
recorded without a spurious status flip.
*Why:* before the FROZEN edge, an overfill while FROZEN was clamped + flagged
and the envelope resumed into COMPLETED — the audit trail filed a violated
mandate as a success (REV-0023 SPEC-05). The Phase-A2 narrowing corrects the
earlier prose "every state that can receive a fill," which over-claimed a
terminal-state chain the transition table never implemented (COMPLETED etc. have
no outgoing edge to BREACHED).
*Pinned by:* `tests/test_rev0023_phase_a_pins.py`
(`test_frozen_overfill_chains_breached_never_completed`,
`test_frozen_exact_fill_still_completes_on_resume`) +
`tests/test_wo0016_envelope_transitions.py` (ADR-mirror table) +
`tests/test_wo0034_eventlog_fidelity.py`
(`test_late_fill_on_terminal_envelope_is_recorded_not_breached`).

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

**INV-088 — An unprintable price never drives features, sizing, or pricing.**
Beyond the per-row validity screens (INV-086 clause 3), every print in the
active window is screened by STEP DEVIATION against its immediate raw
predecessor: a move greater than ``MAX_STEP_DEVIATION`` (25% per ~10-30s step
— an order of magnitude outside LULD trading bands; planning calibration,
Ameen-directed completion 2026-07-15) is excluded from bars/ATR/VWAP/regime/
stop math, and if the LATEST print is deviation-suspect the tick fails quiet
(``StaleDataSignal(price_deviation)``) — actions are priced off the latest
print, so a phantom is never sized or submitted against. PRECEDENCE: a
deviation-suspect latest print AT/BELOW the floor falls through to the hard
floor rail instead (BreachSignal, never silence) — fail-safe outranks
fail-quiet below the floor, so a genuine crash gap gets immediate protection
and a phantom yields at worst a spurious frozen-for-human breach, never an
order and never a quiet tick. Raw-predecessor comparison makes the screen
self-healing: an isolated fat-finger costs at most two rows, a genuine gap
(halt reopen) at most one.
*Why:* REV-0023 Phase-A2 pure-math-0 — one finite absurd print (500,000x)
passed every screen, pinned ``ref_high`` via the running max, and held a
perpetual phantom-level ``stop_triggered`` SUBMIT.
*Pinned by:* `tests/test_puremath0_deviation_band.py` (defect pins + self-heal
+ inside-band guards; band and latest-gate mutation-checked separately).

**INV-089 — An envelope fill fact always carries a valid price.**
``record_envelope_fill``/``plan_envelope_fill`` take a REQUIRED ``price``
(``float``, no ``None``), value-guarded by the shared D-019
``fill_value_reason`` exactly like ``plan_append_fill`` — a non-finite or
non-positive price rejects with ``InvalidFillError`` and writes nothing.
*Why:* REV-0023 Phase-A2 completeness-1 — a ``price=None`` FILL event appended
durably and then PERMANENTLY poisoned ``project_symbol_position`` for the
symbol (``ProjectionError`` on every later ``get_position``/``close_session``).
Both production fill sources (``BrokerFill``, ``InferredFill``) carry
``price: float``, so the requirement is honest end-to-end (AIR-002 already
forbids fabricating a $0 price).
*Pinned by:* `tests/test_wo0033_phase_a2_fixes.py::test_completeness1_*`
(both stores; TypeError on omission, InvalidFillError on 0/negative/NaN/Inf,
projection stays healthy).

---

**INV-090 — A SellIntent's envelope-owner lifecycle is decided ONLY by the
shared obligation projection.** `project_envelope_obligation`
(`app/store/core.py`) is the single composition point for the three retention
predicates every consumer keys on — no store method, monitoring path, or
facade derives a neighboring definition of "live delegation":
(1) **strict** (`delegating ∨ unresolved-children ∨ malformed-ambiguity`)
gates owner promotion (`PENDING→APPROVED`), restore
(`EXPIRED→APPROVED`, `envelope_delegation_restored`), and the duplicate-
conflict sweep; (2) **widened** (strict ∨ open `needs_review` recovery
children) gates release (`envelope_delegation_released` fires only when it is
false) and every sell-side choke — single-flight activation, legacy dispatch,
flatten preemption residual, supersede/stage/claim (direct release attempts
are refused for ANY projection-linked owner via ``projection.linked``,
stricter than the widened predicate — the projection is the sole release
authority); (3)
**across-close** (widened minus bare pre-activation `APPROVED` delegation)
gates session-close sparing, with the non-sparing pre-activation envelope
swept `APPROVED→EXPIRED` in the same atomic close. Consequences: an owner
retained only by an open `needs_review` child is HELD, never resurrected, and
its symbol's sell side quarantines fail-closed pending human reconciliation;
a bare authorization never outlives its session; a working or venue-uncertain
mandate always does.
*Why:* WO-0036 R2 (both attempts) existed because path-local owner-release
definitions orphaned working mandates (release-while-child-rests) or stranded
symbols (spared-forever authorizations); the consolidation (operator
ratifications D1–D9, 2026-07-17) fixed the class by construction — one pure
predicate source, three explicitly-named keyings, dual-store parity.
*Pinned by:* `tests/test_wo0036_r2_lifecycle_link.py` (owner binding, ingress
parity, release/retention),
`tests/test_wo0036_r2_close_and_recovery_ownership.py` (close sparing + sweep
+ stream parity + needs-review quarantine + spared counter),
`tests/test_wo0036_r2_hostile_closure.py` (hostile/legacy shapes),
`tests/r2_conformance_oracle.py` + `tests/test_r2_conformance_oracle_claude.py`
(both spec oracles green; the Claude oracle carries 6 recorded NEEDS-INPUT
skips for tick-level properties not exercisable at store level — campaign
report §C/§E), both stores throughout.
*Correction 2026-07-18, closed by WO-0108 (REV-0029 P0-3 + P1-1 —
amended-and-closed):* two claims above were narrower than written; both are now
closed. (1) CLOSED (WO-0108 step 3, Policy A): "Every sell-side choke" now holds
for the WIDENED predicate — the envelope stage AND final claim rails consume
`needs_review_child_order_ids`, and the direct-SELL exposure scans widened to
`RECOVERY_OPEN_STATUSES`, so no submission lane reaches `SUBMITTING` beside a
`needs_review` exposure (the two P0-3 lanes are pinned closed on both stores).
(1a) ROUND-3 CORRECTION (WO-0109 Cluster B): recovery scope itself is now an
ingress invariant. When the referenced local Order exists,
`create_submit_recovery` compares immutable symbol/side under the same store
lock or transaction and rejects a contradiction without writing anything. A
missing local Order remains legal because the recovery ledger models that lost-
row case. Persisted legacy SELL mismatches still project fail-closed across
both scopes. The stage and final-claim rails are independently mutation-pinned
with a distinct prior sibling and a fresh owner in
`tests/test_wo0109_round3_remediation.py`, both stores.
(2) ROUND-3 CORRECTION (WO-0109 Cluster C): WO-0108 correctly made
`_validated_envelope_lineage` discover cancellation targets through the
OWNER-SCOPED identity universe (parent envelope / owner correlation /
referenced-order owner), but its assertion that monitoring could never appear
clean-empty was too broad: a malformed action selected by the store's symbol
scope alone still disappeared. Cancel authority remains owner-scoped — symbol
equality never authorizes a broker call. A read-only dual-store view now exposes
only the ambiguity identifiers from the shared symbol projection; cancellation
compares that diagnostic with its owner projection and emits the R6 fail-closed
warning for symbol-only corruption without targeting an unvalidated child.
Correlation and referenced-order-owner discovery are mutation-pinned with
mutually exclusive fixtures in `tests/test_wo0036_r2_hostile_closure.py`. The
release/retention/close semantics of this invariant remain unchanged.
(3) EVIDENCE CORRECTION (WO-0109 Cluster D): full-stream parity now preserves
causal `ts_event` and deterministic payload timestamps (including
`expires_at`), normalizing only generated identities and root audit
`created_at` / execution `ts_init` ingest clocks. The cross-store scripts freeze
their store clock sources. T1.3 now AST-verifies the real projection producer,
the four distinct memory/SQLite stage/final consumers, and both executable
`MAY_EXECUTE_ORDER_STATUSES` arguments; imports/comments cannot substitute for
a rail. Comparator fields and every producer/consumer entry are independently
mutation-pinned in `tests/test_wo0036_r2_close_and_recovery_ownership.py` and
`tests/test_review_hardening_gates.py`.
(4) PERFORMANCE CLOSURE (WO-0109 Cluster E): SQLite's action-row loader now
evaluates the same parent/owner/symbol selector through independent indexed
identity arms, deduplicates by event id, applies exclusion after composition,
and restores event-sequence order. In particular, combined owner+symbol scope
remains `parent OR (owner AND symbol)`; it was not broadened to a union.
Referenced-order expansion is bounded by SQLite's variable limit. Both stores'
status-event migration builds one lifecycle-order-id set rather than rescanning
the log for every Order. A dual-store selector matrix, exclusive immutable-key
fixtures, a reduced-variable-limit SQLite pin, and a deterministic dual-store
backfill work counter mutation-pin those mechanics; the retention semantics
above remain unchanged.

**INV-091 — Durable submit progress cannot disappear or be blindly repeated.**
*WO-0113 operator-ratified branch behavior — pending REV-0033 independent
review.*
Once `order_submit_unpersisted` commits, it is the ordinary restart-safe seed
for an accepted broker id whose `SUBMITTED`/recovery writes did not converge.
Whenever recovery ownership cannot be written, the engine appends an
`ENGINE`/`LOCAL` `UNKNOWN_RECONCILE_REQUIRED` execution fact containing the
exact local/broker identity whether or not the ordinary audit succeeded; every
opposite-side boundary treats that fact as venue exposure until the same repair
adopts it or creates a recovery. Before another tick performs venue work, and
before reconciliation may lift
`Reducing`, repair converges either seed without a broker call. A malformed seed
fails closed, and an acceptance already represented by the order or recovery is
idempotent. Same-side CAPI exposure counts each exact accepted BUY broker
identity until it is broker-authoritatively resolved; an exact order, open
recovery, and fallback for the same broker id coalesce as one accepted leg
rather than releasing it. Recovery ownership is one row per exact canonical
local/broker pair. Every durable assignment canonicalizes transport whitespace
before identity comparison. Order, recovery, and canonical-fallback
representations for that same pair coalesce as one accepted leg. One local order
may own multiple distinct concrete broker acceptances. Concrete broker-id
assignments in mutable order/recovery state are exclusive to one local order.
Because canonical fallback events are append-only evidence, a conflicting
fallback under another local order is retained rather than rewritten or silently
dropped; it cannot be adopted or rebound, blocks repair/venue progress, and makes
SQLite restart fail closed until the cross-owner evidence is dispositioned.
Every leg is polled, canceled, and resolved independently. Canonical fills are allocated
once across their aggregate, never once per identity. Malformed/legacy numeric
owner scope cannot shrink the immutable referenced-order remainder: the
conservative larger quantity/price wins, and an unbounded scope fails a
configured risk gate closed. Overlap with the same non-terminal order/recovery
is counted once. Routine claim/CAPI reads use a rollback/restart-safe
accepted-fact cache, so unrelated historical UNKNOWN facts are not materialized
at every choke. Global CAPI projects each order's lifecycle status from immutable
events, not its driftable raw status column. Bounded accepted-submit and
fill-attribution repair consumers skip checkpoint-only transport pages, so idle
cadence converges without the two cursors appending for each other. The fallback
itself blocks stale-claim reclaim before ownership repair. A broker call that
returns an empty or whitespace-only id is post-call ambiguity and must enter
quarantine rather than release the claim as a preflight rejection. A priceable stale redrive
must first commit `STALE_SUBMITTING_REDRIVE_STARTED`; without that fact there is
no venue call. An ambiguous send must commit either TIMEOUT_QUARANTINE or an
open `needs_review` owner for the exact local/client identity, including across
SQLite restart. Startup/reconnect must successfully write and verify the
reconcile driver as `Reducing` before repair; a pre-existing composed `Halted`
state cannot mask failure of that driver write. Only later repair/reconcile
faults may be contained behind the verified gate. Every planned inferred-fill
lookup and append is part of parity establishment: if either fails, driven
reconciliation must keep/verify `Reducing`, refuse an `Active` classification,
and stop the same tick before any venue action.
Every submit/replace acknowledgement and targeted client-order lookup must echo
the deterministic client-order id requested by the engine; missing or mismatched
correlation is ambiguity, never an adoptable broker identity. A per-order status
response must echo the exact requested broker id before its status or fills can
mutate local truth. Mass reconciliation treats an existing local broker id as
authoritative; only an id-less local order may fall back to a client-id match,
and then only when immutable symbol and side also agree. Cancellation after a
venue call may have crossed the send boundary, so accepted identity/quarantine
finalization is shielded to durable completion before the original cancellation
propagates.
*Pinned by:* `tests/test_wo0113_lifecycle_closure.py`
(`test_unpersisted_submit_audit_repairs_failed_recovery_next_tick`,
`test_sqlite_restart_repairs_unpersisted_submit_audit`,
`test_repair_skips_submit_already_persisted_then_terminal`,
`test_reconcile_gate_repairs_acceptance_before_it_can_lift_active`, and
`test_startup_repair_failure_stays_reducing`), plus
`test_first_submit_quarantine_fault_gets_durable_owner`,
`test_stale_redrive_quarantine_fault_gets_durable_owner`,
`test_ambiguous_owner_survives_sqlite_restart`, and
`test_startup_aborts_when_reduce_only_gate_cannot_commit`, plus
`tests/test_wo0113_submit_acceptance_fallback.py` and the gate-establishment
fault pins in `tests/test_wo0113_monitoring_failclosed.py`, including
`test_failed_inferred_fill_cannot_be_classified_as_parity`, plus the exact
CAPI/dedup pins in `tests/test_wo0113_capi_uncertainty.py`. Broker-identity
multiplicity, one-time fill allocation, conservative numeric scope,
self-reclaim, normalization, and bounded-history cases are pinned in
`tests/test_wo0113_acceptance_identity.py`; store-boundary canonicalization,
cross-representation conflict handling, and timeout-resolution ownership are pinned in
`tests/test_wo0113_store_parity.py`; bounded repair selection is pinned in
`tests/test_wo0113_repair_scaling.py`.

**INV-092 — Local `CREATED → CANCELED` is one common proof, not a raw-status
shortcut.** Under the deciding lock/transaction, event projection must still
say `CREATED`, `broker_order_id` must be absent, no open `unresolved` or
`needs_review` recovery may reference the order, and no accepted-submit fallback
may own it. If eligible, row + audit +
routine ExecutionEvent + owner reconciliation commit atomically at the injected
logical time. Every direct cancel, exit stand-down, envelope cleanup,
monitoring cancel, and session-close caller delegates this proof; a raced claim
or recovery leaves the order non-terminal.
*WO-0113 operator-ratified amendment — pending REV-0033 independent review.*
*Pinned by:* `tests/test_wo0113_safe_local_cancel.py`
(`test_direct_created_cancel_is_blocked_by_open_recovery`,
`test_direct_created_cancel_uses_event_projection_not_raw_status`,
`test_facade_created_cancel_loses_safely_to_submission_claim`,
`test_terminal_cleanup_spares_recovery_owned_created_child`,
`test_session_close_uses_projection_spares_recovery_and_counts_exactly`, and
`test_local_created_cancel_rolls_back_row_audit_and_execution`), plus
`tests/test_wo0113_acceptance_identity.py::test_accepted_direct_sell_cannot_be_canceled_as_local_created`.

**INV-093 — A failed candidate dispatch cannot silently strand a consumed
approval.** Every ordinary exception and `asyncio.CancelledError` after approval
triggers the same guarded, cancellation-shielded APPROVED-with-no-order
reversion to PENDING; known domain failures remain mapped and unexpected
defects/cancellation propagate unchanged. If ordinary cleanup itself fails, the
original dispatch defect remains the surfaced error and the durable APPROVED
state remains visible for repair rather than being masked by cleanup telemetry.
*Pinned by:* `tests/test_wo0113_lifecycle_closure.py`
(`test_unexpected_candidate_dispatch_exception_reverts_approval` and
`test_approval_cleanup_failure_preserves_original_dispatch_error`, plus
`test_candidate_dispatch_cancellation_reverts_approval`).

**INV-094 — Order mint/dispatch boundaries are symmetric across same-symbol
opposite-side exposure.** BUY candidate admission and final dispatch refuse
while an exit may execute. Legacy SELL dispatch, envelope stage/final claim,
protection, flatten, and emergency reduce refuse while a BUY may execute by
projected order, concrete broker identity, open recovery truth, or an
unrepresented accepted-submit uncertainty fact. A successful direct SELL mint atomically
expires the symbol's PENDING/APPROVED BUY candidates and safely cancels eligible
projected-CREATED BUYs. Independently of direction, final claim refuses the
order's own broker identity or accepted-submit fact before any venue call. Thus
decomposing the normal facade flow cannot bypass either the cross-side rail or
the one-local-id/one-submission ownership rail. An accepted direct SELL also
remains in same-side single-flight at later intent-mint and final-claim choke
points even if a local terminal fact masks its order row.
*WO-0113 operator-ratified amendment — pending REV-0033 independent review.*
*Pinned by:* `tests/test_wo0113_sell_boundary.py`,
`tests/test_wo0113_submit_acceptance_fallback.py`,
`tests/test_wo0113_acceptance_identity.py`,
`tests/test_wo0113_primary_remediation.py`, and the existing final-claim pins in
`tests/test_wo0109_round3_remediation.py`.

**INV-095 — Every managed venue response is correlated to one durable exact
request scope.** Before a venue submit/replace, the engine appends one
`ENGINE`/`LOCAL` `VENUE_ORDER_SCOPE` for the current gapless submission claim.
It records client id, immutable owner identity/quantity, rendered type/price,
asset/quantity mode, TIF/class, extended-hours eligibility, and replacement
predecessor. Restart replays that scope; it never re-derives session-sensitive
wire intent. Every loader authenticates it against the immutable Order or durable
recovery owner before an adapter call. Direct ACK/status/targeted and mass-report
paths compare the same scope, including exact replacement lineage; a managed
mass `filled_quantity` must be finite, integral, and nonnegative (broker overfill
above ordered quantity remains valid truth). Unknown lifecycle states, scope
poison, foreign identity, and contradictory advanced-order fields fail closed.
The injected decision clock—not ambient wall time—chooses a new envelope scope.
*Why:* otherwise a restart, session boundary, poisoned event, or partial mass row
can authenticate a different venue order and apply its status/fills locally.
*Pinned by:* `tests/test_wo0113_monitoring_failclosed.py` (scope poison),
`tests/test_alpaca_paper_submit.py`, `tests/test_alpaca_paper_order_status.py`,
`tests/test_wo0019a_broker_replace.py`,
`tests/test_spine_phase4_reconciliation_engine.py`, and
`tests/test_wo0019_engine_seam.py::test_submit_scope_uses_the_injected_decision_clock`.

---

## Superseded / historical

None yet. When an invariant is later found to be wrong or is deliberately
loosened, mark it **superseded by INV-0xx** here rather than deleting it —
the history of "we used to require X, then decided Y" is itself useful context
for the next reviewer.
