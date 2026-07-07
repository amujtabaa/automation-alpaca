# Start Here — Alpaca Clean-Sheet CAPI Option 2.5

This folder is the Claude Project knowledge base for a clean-sheet, paper-first
automated trading system. It is a **planning, architecture, and review**
workspace — not the implementation environment. Code is written later in Codex
or Claude Code against the repository, using these files as the spec.

## Read Order

1. `00_START_HERE.md` — this file (orientation + decisions log)
2. `01_ARCHITECTURE.md` — system design, boundaries, API contract, non-negotiables
3. `02_DATA_AND_PERSISTENCE.md` — storage model, state machine, lifecycle
4. `03_UI_WORKFLOW.md` — cockpit screens and user flow
5. `04_IMPLEMENTATION_PLAN.md` — phased build sequence and tooling
6. `05_REVIEW_CHECKLIST.md` — what to verify in agent output
7. `INVARIANTS.md` — the living invariant registry; the oracle for review,
   kept separate from any implementer's own tests (see D-025)
8. `AGENTS.md` / `CLAUDE.md` — short rule files for coding agents

## What This Project Is

A browser-operated, paper-first automated trading system using:

- Alpaca Paper (market data + paper trading)
- FastAPI backend as the durable engine
- Streamlit cockpit as a thin UI client
- a custom strategy engine
- a Capital Allocation & Preservation Intelligence (CAPI) layer
- local SQLite persistence so data survives restarts and accumulates across days

## What This Project Is Not

- not live trading
- not Webull-, IBKR-, TradersPost-, or TradingView-centric
- not command-line-first
- not a Dash/React project yet
- not a full OMS/EMS or high-frequency system
- not multi-user (single-user localhost in beta)

## How to Use This Project

Use this Claude Project to refine architecture, draft Codex/Claude Code prompts,
review implementation output, identify contradictions, and preserve context
across chats. Use Codex or Claude Code to create/modify repo files, run tests,
and implement code.

---

## Decisions Log

Records *why* the architecture is what it is, so the reasoning survives across
chats. Newest first.

### D-025 — Phase-7 sell-intent lifecycle remediation (X-001..X-005): atomic flatten, self-heal, needs_review eligibility, sell correlation
**Context.** Two rounds of independent review of the Phase-7 sell-side work —
D-021's readiness gate and D-024's own AIR Group C — had already passed. A
*third*, different-lineage review (external tooling, not this codebase's own
review loop) then found one CRITICAL and two HIGH defects the in-loop review
had missed, plus two lower-severity gaps. `docs/INVARIANTS.md`'s companion
retro (`REVIEW_LOOP_REFINEMENT.md`, kept outside the docs tree as project
history rather than architecture) names the root causes: the in-loop reviewer
had been checking the implementer's own tests as its oracle (X-002's tell —
the ADR required self-heal, the code didn't do it, and the test *asserted the
buggy behavior* as correct), review was scoped per-increment so a race
*between* two increments was invisible (X-001), and shared context between
implementer and reviewer meant a shared blind spot (X-003: this project's own
prior session had rewritten `base.py`'s docstrings to *delete* the
needs_review clause, so the code and the ADR came to silently disagree with
each other, not just with the truth). `docs/INVARIANTS.md` — an oracle
deliberately separate from any implementation's own tests — is the direct
structural fix for the first root cause; this entry records the four
technical fixes plus the process gap.

**(X-001, CRITICAL) `POST /positions/{symbol}/flatten` is now backed by one
atomic `StateStore.flatten_position` operation, not a route-level
check-then-later-create.** The prior route shape — call
`active_sell_intent_for(symbol)`, then *separately* call
`create_sell_intent(MANUAL_FLATTEN, ...)` as its own lock hold — left a window
where a concurrent protection tick's own `create_sell_intent(PROTECTION_FLOOR,
...)` call could win the single-flight dedup. The human's flatten click would
silently receive back a `protection_floor` intent instead of the
`manual_flatten` it asked for; under a kill switch that intent is held
unsubmitted (D-P2's protection-pauses-but-buys-block rule), so the click reads
as success while the position keeps bleeding. Fixed by a single new store
method, `flatten_position(symbol)`, that reads the live position, stands down
any non-live `PROTECTION_FLOOR` exit (a `CREATED` order is canceled; a
stranded no-order `APPROVED`/`PENDING` intent is expired), then
creates+approves+dispatches a fresh `MANUAL_FLATTEN` — all under **one
continuous lock hold**, mirroring D-017's `claim_order_for_submission`
pattern (pure planner + single lock, not a new primitive). The route is now a
thin caller: normalize the symbol, check for a position, run the
broker-facing `cancel_open_buys` pre-step (this stays outside the atomic op
deliberately — it needs a broker round-trip, and the store lock must never be
held across network IO; `flatten_position` re-reads the live position under
its own lock regardless, so a buy that fills concurrently with the cancel is
still sized correctly), then call `store.flatten_position` and translate its
result. See `docs/INVARIANTS.md` INV-034 through INV-038. Both stores
implement the same lock-acquisition semantics via different internal
structuring — `InMemoryStateStore` nests everything in one `_atomic()` (pure
Python snapshot/restore, safely nestable); `SqliteStateStore` runs several
small sequential `_tx()` transactions under the one continuous lock hold,
since real SQL transactions can't nest — the **lock**, not transaction
granularity, is what closes the CONCURRENCY race. Proven under real
concurrent scheduling (`asyncio.gather`, both interleaving orders) at both the
store layer (`tests/test_phase7_flatten_atomic.py`) and the HTTP layer
(`tests/test_phase7_routes.py::test_flatten_http_race_with_concurrent_protection_create`).

**Follow-up (mandatory adversarial re-review of this diff, per the
remediation plan's merge-blocker checklist): a real crash-durability gap, not
just a cosmetic one.** The first draft of this entry claimed "a crash
mid-sequence in the SQLite path leaves a safe, independently-recoverable
state at each step" — a fresh-context review of the diff (given only
`docs/INVARIANTS.md` and the source, no rationale or tests) disproved that
for one specific step: `SqliteStateStore.flatten_position` committed the
fresh intent's insert+approve in one transaction, then dispatched its order
in a SEPARATE transaction. A crash landing between those two commits (not a
concurrency race — no `await` occurs between them, so no other coroutine can
interleave; only a hard process kill) durably strands a `MANUAL_FLATTEN`
intent `APPROVED` with no order. `plan_flatten_position` (the shared planner
in `app/store/core.py`) treated ANY `MANUAL_FLATTEN` active intent as "the
existing exit" unconditionally, so a later flatten call for the same symbol
returned the dead, order-less intent as success (HTTP 200, `order=None`)
forever, and permanently poisoned single-flight dedup — a protection tick
could never open a real protective exit for the symbol either. Fixed in the
shared planner (not sqlite-specific): a `MANUAL_FLATTEN` active intent is
only "existing" when `status is ORDERED`; a `pending`/`approved` one falls
through to the same self-heal/supersede path a stranded `PROTECTION_FLOOR`
intent already had. `InMemoryStateStore` cannot reach this exact state via a
crash (its whole sequence is one `_atomic()` block with no durability
window), but the fix lives in the shared pure function, so both stores'
*contract* is now correct, not just sqlite's crash window. See
`docs/INVARIANTS.md` INV-038;
`tests/test_phase7_flatten_atomic.py::test_stranded_manual_flatten_with_no_order_self_heals`
constructs the stranded state directly (confirmed to fail without the fix on
`InMemoryStateStore` too, via this same public API — not only reachable
through sqlite's specific crash window).

**(X-002, HIGH) `create_order_for_sell_intent` self-heals `approved → expired`
on every dispatch rejection, closing a gap between the code and the ADR's
explicit "Self-heal (blocker)" clause.** Any rejection after approval —
oversell, an invalid quantity, an unpriceable LIMIT, a MARKET order carrying a
limit price — now atomically expires the intent in the same operation that
raises the error, instead of raising and leaving the intent stranded
`APPROVED`. A stranded `APPROVED` intent would have permanently poisoned
X-001/INV-031's single-flight dedup for that symbol. The regression test that
had asserted the *old* (wrong) `APPROVED` result as the expected outcome was
corrected to assert `EXPIRED` — see `docs/INVARIANTS.md` INV-033 and
`REVIEW_LOOP_REFINEMENT.md` for why that test itself was the miss, not just
the code.

**(X-003, HIGH) `active_sell_intent_for`'s "active" definition is needs_review-
aware again, matching the ADR's "Stranded-order eligibility (blocker)"
clause.** An `ordered` intent whose order is stuck in an OPEN `needs_review`
recovery (AIR-002, e.g. a transiently un-priceable fill) no longer counts as
active — a spurious escalation must never permanently disable protection for a
still-breaching symbol. `unresolved` recoveries still count as active (the
recovery loop is still working them transiently). This is now the **one**
canonical definition, in `app.store.core.sell_intent_is_active`, consulted
identically by both stores — see `docs/INVARIANTS.md` INV-032.

**(X-004, MEDIUM) Every event on a protective-sell's order now carries
`correlation_id = sell_intent_id`, not just the creation events.** The generic
event writer in both stores previously defaulted `correlation_id` from
`candidate_id` only (D-020) — always `None` for a sell order, since order
origin is `candidate_id` XOR `sell_intent_id` (never both). Claim,
blocked-claim, submission, stale, fill, and recovery events for a protective
sell all lost the correlation key, so `GET
/api/events?correlation_id=<sell_intent_id>` returned only the creation
events, never the execution trail (only the sell-intent planners in
`app/store/core.py` that already passed `correlation_id=intent.id` explicitly
were unaffected). Fixed centrally in the event-write path: resolve
`correlation_id` from the owning order's `sell_intent_id` whenever neither an
explicit `correlation_id` nor a `candidate_id` is available but `order_id` is.
See `docs/INVARIANTS.md` INV-041, verified end-to-end through the real
monitoring-loop functions (not just the planners) in
`tests/test_phase7_sell_correlation.py`.

**(X-005) This entry, plus `docs/INVARIANTS.md`.** The registry is the
structural answer to the review-loop retro's core lesson: an invariant that
lives only in an ADR paragraph (X-003) or only in the implementer's own test
assertions (X-002) is not actually pinned — it can drift silently. Future
reviews of this codebase should probe against `docs/INVARIANTS.md` directly,
write fresh tests against its statements rather than re-running the linked
pinning tests, and add an entry here in the same session a new blocker-level
rule is introduced, not as a follow-up.

**Explicitly not closed by this entry:** an independent, different-lineage
adversarial re-review of the X-001..X-003 diff is a merge-blocker for this
work per the remediation plan — an in-repo review (however fresh-framed) is
not a substitute for that external half of the gate, and this entry does not
claim to satisfy it.

**Enforcement points:** `app/store/core.py` (`plan_flatten_position`,
`FlattenPlan`; `plan_create_order_for_sell_intent`'s self-heal;
`sell_intent_is_active`'s `order_needs_review` param), `app/store/base.py`
(`StateStore.flatten_position` abstract method, `FlattenResult`),
`app/store/memory.py` + `sqlite.py` (`flatten_position`,
`_order_needs_review_unlocked`/`_locked`, the `_insert_event`/
`_append_event_unlocked` correlation resolution), `app/api/routes_trading.py`
(`flatten_position` route, now a thin caller). New tests:
`tests/test_phase7_flatten_atomic.py`, `tests/test_phase7_sell_correlation.py`;
extended: `tests/test_phase7_sell_intents.py`, `tests/test_store_core.py`,
`tests/test_phase7_routes.py`. `docs/INVARIANTS.md` added as a new canonical
file (see its own header for how to use it).

### D-024 — AIR remediation Group C: test-quality (harness rare-branch proof + version-proof warnings)
**Context.** The final AIR subset is about the *tests* themselves, not production
behaviour — a harness that passes its invariants can still be silently blind to the
rare recovery branches, and a warning-as-error guard can silently stop firing on a
newer Python. Both are "green but not actually protecting you" failure modes.

**(C1 · AIR-010) The lifecycle harness now *proves* it reaches the rare recovery
branches.** `tests/test_lifecycle_state_machine.py` gained `hypothesis.event()`
markers, a `target()` (peak open-recovery count, fed once per example at teardown)
to bias the random search toward recovery-rich interleavings, and cross-instance
`_COVERAGE` counters. Three self-contained rules construct the rare states directly
so they are reachable regardless of luck: `crash_after_claim` (a stale, id-less
`SUBMITTING` order — the B2/AIR-003 precondition), `force_submit_cancel_orphan`
(the F-002 orphan tracked only by an open recovery record), and
`divergent_fill_and_reconcile` (a B3/AIR-002 unrecordable fill escalated to
`needs_review`, position still deriving only from fills). The **hard** "a critical
recovery branch is unreachable" assertion lives in a **deterministic driver**
(`test_harness_rules_reach_recovery_branches`, parametrized over both stores), not
in the random run — asserting a random run hit a specific branch is inherently
seed-flaky (verified: it failed under some `--hypothesis-seed`s), so the guard
instead invokes each rare-branch rule directly and asserts its counter advanced.
The `event()`/`target()` calls are wrapped so they no-op outside a Hypothesis
context (the driver calls the rules directly). Also pinned: the `SimBrokerAdapter`
models `client_order_id` idempotency (a duplicate `submit_order` returns the same
broker id and preserves broker-side state) — the exact property B2's re-drive
relies on, so the harness exercising that path is not a lie
(`test_sim_submit_is_idempotent_by_client_order_id`).

**(C2 · AIR-011) Resource-leak enforcement is version-proof.** `pyproject.toml`
promoted an unclosed-`sqlite3.Connection` `ResourceWarning` to an error (F-008), but
on Python 3.13+ pytest delivers a GC-time (unraisable) `ResourceWarning` wrapped in
`PytestUnraisableExceptionWarning` — **not** a `ResourceWarning` subclass, so the
plain filter would let a leaked connection escape on newer Pythons. Added
`error::pytest.PytestUnraisableExceptionWarning` alongside the existing filter so
both the plain and wrapped forms fail the suite on every Python version.
`tests/test_warning_hygiene.py` pins both (the wrapped test fails without the new
filter — verified). This immediately earned its keep: it caught a real leaked event
loop in the C1 deterministic driver (its `teardown` had aborted before
`loop.close()` when `target()` raised outside a Hypothesis context), which was then
fixed. Full suite is green under the stricter filter — no unclosed
connections/cursors remain.

### D-022 — AIR remediation Group B: durable submission/fill recovery
**Context.** Group B is the temporal/recovery subset of the AIR findings
(AIR-001/002/003) — higher blast radius than Group A because it spans the broker
adapter, the monitoring loop, and the recovery ledger, and because the failures
are about *what happens across a crash or a broker disagreement*, not a single
call's inputs. Each defect was reproduced red-first and driven green, store-facing
behavior parametrized over both stores (`any_store`), all in
`tests/test_air_group_b.py` (+ the rewritten `test_store_core.py` /
`test_alpaca_paper_fills.py` unit pins).

**The unifying principle: a broker truth the local state can't reconcile is never
dropped and never guessed — it is either recovered idempotently or escalated to a
durable, operator-visible record.**

**(B1 · AIR-001) No `SUBMITTED` without a real broker id.** `SUBMITTED` means the
broker accepted the order and handed back the id we poll and cancel by; an order
that reached `SUBMITTED` with `broker_order_id=None` was untrackable. Fixed at
three layers: (1) the `BrokerAdapter.submit_order` **contract** now documents that
an implementation must return a non-empty `str` or raise; (2) the shared
`plan_transition_order` **rejects** a status change *into* `SUBMITTED` without a
non-empty effective broker id (`OrderTransitionError`) — so **both** stores
enforce the invariant, not just the caller; (3) `monitoring._submit_pending_orders`
**validates** the returned id and treats an empty one as a submit failure (release
the claim, re-drive next tick) rather than persisting an untrackable order. The
one store-core unit test that asserted the old `SUBMITTING → SUBMITTED, id=None`
apply was rewritten to pass a real id (its real purpose was the `submitted_at`
assertion).

**(B2 · AIR-003) Stale `SUBMITTING` is recovered by idempotent re-drive, not left
stranded.** A claim (D-017) writes `SUBMITTING` durably *before* the broker call,
so a crash between claim and persist leaves an order `SUBMITTING` with
`broker_order_id=None` — excluded from both the `CREATED` submit sweep and the
open-order reconcile poll, so nothing ever touched it again (it silently inflated
CAPI exposure forever). **The durable `SUBMITTING` row plus the stable
`client_order_id` (`order.id`) already *is* the outbox — no new table.** A new
monitoring step `_redrive_stale_submitting` (run every tick, so within one cadence
of a restart) re-drives each such order through `adapter.submit_order`, which is
inherently double-submit-safe: a fresh submit either creates the broker order or
recovers the already-accepted one by client id. A non-empty id back →
`SUBMITTING → SUBMITTED`; a transient `BrokerError` → left `SUBMITTING` to retry
(idempotent, not a blind double-submit); a `TerminalBrokerError` / empty id / "can't
confirm" → a durable `needs_review` recovery record (the loop does not guess).
Deduped: an order already carrying an open recovery record is neither re-driven nor
re-recorded. A new `TerminalBrokerError(BrokerError)` subclass makes the transient-
vs-terminal distinction explicit (plain `BrokerError` stays transient-by-default).
Stale `SUBMITTING` orders are already surfaced in the operator view — they are in
`NON_TERMINAL_ORDER_STATUSES`, which the operator-orders endpoint filters on.

**(B3 · AIR-002) A broker/local fill divergence is escalated durably.** Two halves:
- **Adapter (`alpaca_paper._resolve_fill_price`)** no longer synthesizes a `0.0`
  price when neither the broker average nor the limit is a trustworthy (finite,
  positive) number — it returns `None`, and `_get_fills` then **omits** the fill
  entirely rather than appending a corrupt `$0` execution. The broker's cumulative
  `filled_quantity` still carries the truth, so the omission surfaces as a
  divergence downstream instead of a bogus fill.
- **Monitoring (`_apply_update`)** now escalates when, after appending every
  recordable fill, the broker's cumulative `filled_quantity` still **exceeds** what
  we recorded (a fill the store rejected, or one the adapter withheld). It writes a
  durable `needs_review` reconciliation record (via the recovery ledger — `event_type=
  fill_reconciliation_needed`, payload carrying broker status / broker filled /
  recorded / rejected-fill summary), deduped per order, and **holds the order
  non-terminal** (`_divergence_safe_status`: `cancel_pending` stays winding down,
  else `partially_filled`/`submitted`) so a real untracked position is never buried
  under a terminal `CANCELED`/`FILLED`. **The invariant is preserved: positions still
  derive only from appended fills** — the reconciliation record is the truth-divergence
  signal, not a position mutation. The verified defect (broker `FILLED`=10 + an
  un-priceable fill → order stuck `SUBMITTED`/`filled=0` forever, no escalation) is
  closed on both stores.

**Ledger reuse, not a new entity.** B2 and B3 both write through the existing
`SubmitRecoveryRecord` ledger — its meaning is broadened from "submission orphan"
to "any broker truth the local order state can't reconcile, surfaced to the
operator." `create_submit_recovery` gained three optional, additive params
(`cleanup_status` to birth a record directly `needs_review`, validated against
`RECOVERY_STATUSES` via the A1 machinery; `event_type` and `extra_payload` for the
distinct fill-divergence audit event). No new table, no schema migration.

**Enforcement points:** `app/broker/adapter.py` (`TerminalBrokerError`,
`submit_order` contract), `app/broker/alpaca_paper.py` (`_resolve_fill_price` →
`Optional`, `_get_fills` omit), `app/store/core.py` (`plan_transition_order` B1
guard, `require_recovery_status`), `app/store/base.py` + `memory.py` + `sqlite.py`
(`create_submit_recovery` new params), `app/monitoring.py`
(`_redrive_stale_submitting`, `_escalate_stale_submitting`, `_apply_update`
divergence branch, `_escalate_fill_divergence`, `_divergence_safe_status`). Suite:
**1053 passed / 3 skipped, branch coverage ~95%** (floor 93%). Positions still
derive only from fills; no live-trading path; the atomic claim remains the sole
entry into `SUBMITTING`.

**Gate B independent re-review — one confirmed finding, fixed.** A fresh-context
adversarial workflow (6 lenses → skeptic-verify) over the B1–B3 + A1 diff confirmed
one **major** defect: the B2 transient-vs-terminal split was unreachable in
production because the only real adapter, `AlpacaPaperAdapter.submit_order`, raised
**plain `BrokerError` for every failure** — so a *permanently*-rejected re-drive
(403 restricted account, 422 insufficient buying power, delisted symbol, or a
duplicate whose existing order can't be looked up) was classified transient and
retried **every tick forever**, inflating CAPI exposure indefinitely and never
escalating. Fixed two ways: (1) `AlpacaPaperAdapter.submit_order` now maps
definitive 4xx rejections (400/401/403/404/422) and the duplicate-lookup-failed
case to **`TerminalBrokerError`** (429/5xx/network stay transient `BrokerError`);
(2) a **bounded backstop** — each transient re-drive deferral writes a durable
`stale_submitting_redrive_deferred` audit event, and after
`stale_submitting_max_redrive_attempts` (default 10, configurable) the order is
escalated to `needs_review` regardless of classification, so no *misclassified*
permanent failure can livelock. The two other findings were adversarially refuted
(a planner same-status-reaffirm edge unreachable by any caller; an "unguarded store
write aborts the tick" claim that matched documented tick-isolation and a
pre-existing unguarded read) — the escalation store-writes were nonetheless wrapped
best-effort for per-order isolation consistency with `_handle_unpersisted_submit`.

A follow-up fresh-context verification of the fix confirmed it closes the livelock
with no regression, and flagged one **minor, pre-existing** analogue: the *first*-
submit path (`_submit_pending_orders`) also ignored terminal classification — a
definitive rejection on a brand-new order released `SUBMITTING → CREATED` and
re-submitted every tick (a `CREATED ↔ SUBMITTING` livelock hammering the broker).
Closed the same way: a `TerminalBrokerError` on first submit now escalates to a
durable `needs_review` record instead of releasing to CREATED, completing the
"no submission livelock" invariant across **both** submission paths.

### D-023 — AIR remediation Group A: deterministic validation & contract fixes
**Context.** An independent adversarial review (the "AIR" findings, AIR-001…011)
flagged eleven defects across validation, recovery, and test quality. Group A is
the deterministic subset — five findings (AIR-004/005/006/007/008/009) that are
fully decidable without any temporal or broker-recovery reasoning. Each was
reproduced firsthand as a **red test first**, then fixed to green, exercised
through the `any_store` fixture so `InMemoryStateStore` and `SqliteStateStore`
are proven to accept/reject/persist/read-back/audit **identically**, and every
new rejection raises a **domain error**, never a raw `ValueError`/`TypeError`/
pydantic `ValidationError`/JSON `ValueError`. Regressions live in
`tests/test_air_remediation.py`.

**The unifying root cause behind three of the five: silent coercion.** Python's
str-enums and pydantic's lax mode both *accept* an input that looks close enough
and quietly convert it — a bare `"pending"` string matching a `CandidateStatus`
member, `"false"` becoming a truthy bool, `True` becoming `1`. Each conversion
erases the caller's real intent before any guard can see it. The fix is the same
shape everywhere: **validate the concrete value at the store/domain boundary,
require the real type, reject the coercion class with a domain error.**

**(A1 · AIR-004) Recovery status is a validated enum with an explicit transition
table.** `SubmitRecoveryRecord.cleanup_status` transitions had no state machine —
any string could be written, and an already-resolved record could silently
re-open. Added `RECOVERY_STATUSES` (the frozenset of the three valid values) and
`RECOVERY_TRANSITIONS` (`unresolved → {resolved, needs_review}`; both terminal
states → `∅`) in `app/models.py`. `app.store.core.recovery_status_event` now
raises `RecoveryTransitionError` on an unknown status or a disallowed transition;
`None`/same-status is a no-op returning `None` (no spurious audit row), matching
the candidate/order same-status rule.

**(A2 · AIR-005 + AIR-008) The coercion class, swept.** Three sub-fixes, then a
grep of every store entrypoint and route schema to confirm no fourth surface was
missed:
- **Strict booleans on all four control surfaces.** `set_kill_switch`,
  `set_buys_paused`, `set_watchlist_armed`, `add_watchlist_symbol` now call
  `app.store.core.require_bool` (raises `InvalidControlValueError` on a non-`bool`)
  in **both** stores; the route schemas `KillSwitchRequest.engaged` and
  `WatchlistCreate.armed` use `StrictBool`. The reproduced defect this closes:
  `{"engaged": "false"}` — a payload *meant to disengage the emergency stop* —
  used to be accepted, memory storing the truthy string `'false'` and SQLite
  coercing it to `True`, so the disengage request would have **engaged** the kill
  switch. Now it is a clean `422` at the route and an `InvalidControlValueError`
  at the store. (The buys-pause/resume routes carry no body — they toggle a fixed
  value server-side — so there is no schema field to stricten there; the store
  setter `require_bool` is still the backstop for any direct caller.)
- **Candidate numerics validated at the store boundary.** A new
  `app.policy.candidate_numeric_reason` (reusing the existing
  `whole_count_reason`/`limit_price_reason`/`finite_number_reason` family — not a
  re-implementation) is checked in **both** `create_candidate`s *before* the
  pydantic `Candidate` is constructed, rejecting `NaN`/`Inf`/`-Inf`, zero,
  negative, a fractional quantity, a `bool`, and a string with `InvalidOrderError`.
  A genuinely-absent value is `None` (allowed — an unsized/unpriced candidate),
  never a non-finite sentinel. This **converges a real parity break**: a `nan`
  price used to roundtrip as `nan` through memory but as `NULL` through SQLite
  (SQLite stores `NaN` as `NULL`), so the two stores disagreed on what was
  persisted; now neither persists it at all. This **supersedes D-021's narrower
  `suggested_value_type_reason`** (bool/string only), which is now removed as dead
  code — `candidate_numeric_reason` subsumes it (bool/string rejection still flows
  through `finite_number_reason`) and additionally closes the non-finite/
  non-positive gap D-021 had deliberately deferred to order-creation time. The
  order-creation guards remain as **defense-in-depth** and as the sole guard for
  the one value the candidate boundary allows — a `None` price on a LIMIT order.
- **Serialization guard so no API response can emit a non-JSON float.** A
  persisted `inf`/`nan` (a legacy row, or any path that bypassed the write guard)
  would crash readback on Py3.13 and emit invalid `Infinity` on 3.12. Added
  `ResponseSafeFloat`/`ResponseSafeRequiredFloat` in `app/models.py` — `Annotated`
  float types with a `PlainSerializer(when_used="json")` that maps a non-finite
  value to JSON `null` — applied to every persisted float field (candidate/order
  limit price, fill price, position + snapshot cost basis/average price, recovery
  limit price). Verified end-to-end: a raw `inf` row inserted straight into SQLite
  reads back and serializes as `null` through the real FastAPI response path.

**(A3 · AIR-006) The test-only `create_order` is off the public contract.**
`create_order` had no production caller (every real order goes through
`create_order_for_candidate`) yet sat on the public `StateStore` surface as a
latent hazard — it accepted `qty=-100` and bypassed every gate. Removed from
`app/store/base.py` and renamed to `create_order_for_test` in both stores, with a
TEST-ONLY docstring; it inherits the candidate's `session_id` so a test order can
still be claimed for submission like a real one. Not threaded through the policy
plan (deliberately — it is a fixture helper, not a code path).

**(A4 · AIR-007) One path into `SUBMITTING`.** Removed `CREATED → SUBMITTING`
from `app.transitions.ORDER_TRANSITIONS`. The atomic submission claim
(`claim_order_for_submission`, D-017) writes `SUBMITTING` directly (never through
the generic `transition_order`), so removing the table entry closes a bypass and
breaks nothing — `claim_order_for_submission` is now provably the *sole* entry
into `SUBMITTING`. The stale comment that had called the claim "the ONLY path to
the broker" was corrected (submission, not the broker, is what the claim gates).

**(A5 · AIR-009) Enum/string parity at the store boundary.** The chosen public
contract: **status arguments must be real enum instances.** `transition_candidate`,
`list_candidates(status=)`, and `transition_order` (via `plan_transition_order`)
now call `app.store.core.require_status_enum`, raising `InvalidStatusError` on a
string/bool/None. This closes a silent parity divergence: `InMemoryStateStore`
compared with `is`/set-membership (a bare `"pending"` string *is* a member of a
str-enum set, so it matched and mutated), while `SqliteStateStore` pre-coerced
via `CandidateStatus(x)`/`OrderStatus(x)` — the two stores accepted or rejected
the same bare string differently. All such coercions of a caller-supplied status
were removed; both stores now require the enum and reject identically. (Verified
no production caller passes a string — routes pass enum members.) The remaining
`OrderSide(...)`/`OrderType(...)` coercions are out of scope: they are internal
callers only, symmetric across both stores (no parity divergence), and validated
at pydantic construction anyway.

**Sweep result.** Every store entrypoint and route schema taking a bool/enum/
numeric field was checked. Beyond the surfaces above, the only bool input found
was `open_only: bool = Query(default=True)` on the order-list read filter — a
display filter that mutates no state, so a lax coerce there carries no safety
consequence; recorded as reviewed-and-benign rather than strictened.

**Enforcement points:** `app/models.py` (recovery enum + transition table,
`ResponseSafe*` serializers), `app/store/core.py` (`require_bool`,
`require_status_enum`, `recovery_status_event`), `app/store/base.py` (new domain
errors `RecoveryTransitionError`/`InvalidStatusError`/`InvalidControlValueError`,
`create_order` removed from the ABC), `app/store/memory.py` + `sqlite.py`
(guards wired into all four bool setters, candidate numerics, status transitions;
`create_order` → `create_order_for_test`), `app/policy.py`
(`candidate_numeric_reason`; dead `suggested_value_type_reason` removed),
`app/transitions.py` (`CREATED → SUBMITTING` removed), `app/api/schemas.py`
(`StrictBool` on the two control-flag bodies). Suite: **1026 passed / 3 skipped,
branch coverage 95.49%** (floor 93%). Pre-existing tests that had asserted the
*old, later* rejection boundary (non-finite/non-positive rejected at
order-creation) were adapted to assert the new earlier-and-stronger candidate
boundary — the guarantee (bad value → rejected, nothing persisted) is preserved
and tightened, not relaxed.

**Gate A: GREEN.** Groups B (temporal/recovery: AIR-001/002/003) and C (test
quality: AIR-010/011) are tracked separately; Group B's gate additionally
requires an independent adversarial re-review of its diff by a fresh context.

### D-021 — Phase-7 readiness gate: audited green, three follow-up fixes landed
**Context.** Per the wave runbook, once Waves 0–2 are merged the capstone
Phase-7 readiness gate (12 preconditions spanning D-017 through D-020) must be
independently audited before the Phase-7 sell-side ADR can be written. Each
precondition was verified against the *actual current code and tests*, not
against what a decision-log entry claims — reading the real source, running the
real tests, and in several cases reproducing a claimed behavior live — then
cross-checked by a second, independent skeptic agent per item.

**Result: 10 of 12 preconditions passed cleanly on first read; two came back
`PARTIAL`, both real and reachable, both closed by this entry's fixes.**

**(1) `whole_count_reason` was dead code.** `app/policy.py` defined it (finite +
whole + non-negative) but `fill_value_reason` and `filled_quantity_reason` each
re-implemented the same logic inline instead of delegating — directly
contradicting the module's own "one shared guard" framing and, more
concretely, `docs/05_REVIEW_CHECKLIST.md`'s Wave 0 line that claimed the F-003
guard was implemented "via one shared `finite_number_reason`/`whole_count_reason`
guard." Fixed by making both functions delegate to it. Every reason-code string
the original inline logic produced is preserved exactly — verified by direct
probing of all 22 input cases (bool/string/NaN/Inf/fractional/negative/zero/
valid, both quantity and price) before and after, byte-for-byte identical.
`filled_quantity_reason`'s delegation is a pure drop-in (its "negative" reason
already matched `whole_count_reason`'s suffix exactly); `fill_value_reason`'s
needed one explicit remap (`whole_count_reason`'s bare `"negative"` collapses
into the pre-existing `"non_positive_quantity"` fill's stricter positivity
check already used for zero, rather than surfacing as a new, never-before-seen
`"negative_quantity"` reason code).

**(2) A live, reachable silent-coercion gap the audit reproduced against both
stores.** `Candidate.suggested_quantity`/`suggested_limit_price` are plain
pydantic `int`/`float` fields with no strict mode. Pydantic's lax coercion
already rejects `NaN`/`Inf`/a fractional value assigned to the `int` quantity
field (a real, if unfriendly, `ValidationError` — not silent), and negative/zero
correctly still reject at order-creation time via the existing
`qty is None or qty <= 0` check — but a **`bool`** (`True` → `1`) or a
**numeric `str`** (`"5"` → `5`) coerces with *zero error*, and once inside the
pydantic model the original type is unrecoverable — `plan_create_order_for_
candidate`'s later check just sees a clean positive int and creates a real,
persisted `Order`. This is exactly the "boolean silently persisting" defect
class `finite_number_reason`'s own docstring names as a *reproduced* defect for
fills — reachable here too, and previously unguarded. Fixed narrowly: a new
`app.policy.suggested_value_type_reason` predicate (bool / non-numeric-type
only — deliberately **not** `NaN`/`Inf`/fractional/negative/zero, which are
either already handled by pydantic or deliberately still deferred to
order-creation, unchanged) is checked in both stores' `create_candidate`,
**before** the `Candidate(...)` call, while the raw value still carries its real
type. Verified live against both stores pre- and post-fix.

**(1b) Follow-up (PR review): the store-level guard alone didn't close the gap
for the HTTP dev-injection route.** A Codex review on the D-021 PR pointed out
that `POST /api/dev/candidates` parses the JSON body into `MockCandidateCreate`
— a plain (lax) pydantic schema — *before* the request ever reaches
`create_candidate`; pydantic's own lax `int`/`float` field coercion already
turns a JSON `true`/`"5"` into `1`/`5` at that layer, so by the time
`suggested_value_type_reason` runs, the original type is already gone.
Reproduced live over real HTTP (both cases returned `201`, silently). Fixed by
declaring both `MockCandidateCreate` numeric fields `strict=True` — pydantic
strict mode rejects a JSON `bool`/`str` outright as a clean `422` (confirmed:
`bool`→`int`, `bool`→`float`, `str`→`int`, `str`→`float` all now reject) while
still accepting every genuine numeric input, including a whole-number JSON
`int` supplied for the `float` price field (strict mode still widens `int` →
`float`, just not `bool`/`str`) — verified no existing test payload (all send
plain ints/floats) was affected. This is the same defect class as (1) and (2)
above, closed at the one remaining externally-reachable entry point; the
Strategy Engine's real candidate-creation path calls `create_candidate`
directly with Python values it computed itself, never through a JSON schema,
so `MockCandidateCreate` was the only externally-reachable gap.

**(3) The F-002 submit-recovery ledger's own bookkeeping events didn't
correlate.** D-020 always correlated the recovery *trigger* event
(`order_submit_unpersisted`, which carries `candidate_id`), but the ledger's own
three lifecycle events (`submit_recovery_recorded`, `submit_recovery_needs_
review`, `submit_recovery_resolved`) never did — `SubmitRecoveryRecord` itself
carries no `candidate_id` (a deliberate D-020 scope decision: "one nullable
`Event` field, not a new entity column"), so an operator reconstructing a
candidate's incident history via `?correlation_id=` would silently miss the
recovery outcome, despite the `Event` model's own docstring generically
claiming "blocked/recovery" events all correlate. Fixed **without** adding a
column: `create_submit_recovery` gained an optional `candidate_id` kwarg
(threaded from `order.candidate_id`, already in scope at the one call site in
`app/monitoring.py::_handle_unpersisted_submit`) used only for the creation
event; `update_submit_recovery` resolves `candidate_id` for its later terminal
events by looking up the local order via `record.local_order_id` at write time
— reliable because orders are never deleted (`docs/02`'s append-only/no-delete
rule). Verified end-to-end against both stores: the full
create→cancel-races-submit→recovery→needs_review chain now returns under one
`correlation_id` query.

**Enforcement points:** `app/policy.py` (`whole_count_reason` delegation,
`suggested_value_type_reason`), `app/store/memory.py` + `sqlite.py`
(`create_candidate`'s new boundary guard; `create_submit_recovery`/
`update_submit_recovery`'s `candidate_id` threading), `app/store/base.py`
(abstract signature), `app/monitoring.py` (the one `create_submit_recovery`
call site), `app/api/schemas.py` (`MockCandidateCreate`'s `strict=True`, the
(1b) follow-up). All fixes are behavior-preserving or additive-only — no
existing test needed to change, all 791 pre-fix tests still pass unchanged;
39 new tests pin the fixes (`tests/test_wave0_numeric_hardening.py`,
`tests/test_correlation_id.py`, `tests/test_candidate_flow_sequences.py`).
Suite: 830 passed / 3 skipped, coverage 95.42%.

**Gate status: GREEN.** All 12 Phase-7 readiness preconditions now hold,
independently audited and cross-checked. Per the runbook, only the Phase-7
sell-side ADR (its own sell-intent lifecycle and risk model, never sells bolted
onto the buy-candidate path) is unblocked by this — Phase 7 *implementation*
is explicitly out of scope for this entry and has not been started.

### D-020 — Operator-truth endpoint + audit correlation IDs (Wave 2)
**Context.** Two observability gaps. (A) The cockpit *interpreted* order
lifecycle itself — which statuses count as "open", each order's hold reason from
the latest `order_submission_blocked` event, the `order_stale` scan, and the
status→label mapping — so every UI would re-derive it and could drift from the
backend (Wave 0 had already fixed one specific `created`-filter bug; this
generalizes the fix). (B) An order's lifecycle spans `candidate_id`, `order_id`,
and `fill_id`, so no single key tied candidate-creation → approval → claim →
submit → fill → position for incident reconstruction.

**(A) `GET /api/operator/orders` — server-side lifecycle classification.**
Read-only. Returns every durable non-terminal order already classified: an
`operational_status` label (`app.policy.operational_status_for`:
`awaiting_submission` / `held_kill_switch` / `held_buys_paused` /
`held_session_closed` / `held` / `submitting` / `submitted` /
`partially_filled` / `cancel_pending`), the hold `reason` behind a `created`
order (its latest `order_submission_blocked` event), a `cancelable` flag (the
same rule the cancel route enforces — non-terminal and not already
`cancel_pending`), and a `stale` flag; plus every open broker-submit recovery
record classified `broker_submission_failed` (unresolved) / `recovery_required`
(needs_review). The classifier lives in `app/policy.py` beside the gate
predicates so "what operational state is this" is decided in one place too.
Terminal orders are excluded via the same `NON_TERMINAL_ORDER_STATUSES` the CAPI
exposure calc uses. The cockpit now consumes this and **stops owning** the
open-status filter, the block-reason lookup, the stale-event scan, and the
status labeling — it keeps only a presentation-only label map (formatting, not
lifecycle logic) and trusts the backend's `cancelable` flag rather than a status
string. The raw `/orders` read and `/orders/{id}/cancel` action are unchanged;
the next UI (Dash) gets the same classified truth for free.

**(B) `Event.correlation_id` — one key per candidate lifecycle.** A single
nullable, additive field on `Event` (SQLite gets an additive column with a
`_migrate` guard; pre-D-020 rows and non-candidate events like
`market_data_stale` stay NULL, no backfill). The correlation key **is the owning
candidate's id**: rather than thread a fresh id through ~40 event sites, the
event writer defaults `correlation_id` from the event's `candidate_id`
(`correlation_id or candidate_id`, identically in both stores — parity). Every
lifecycle event already carried `candidate_id` (candidate transitions, order
creation, claim, submission-blocked, unpersisted-submit, stale, transitions)
**except fills**, which now also carry it — so `GET
/api/events?correlation_id=<candidate_id>` reconstructs creation → approval →
order → claim → submit → fill → transitions in one query. Deliberately **not**
event-sourcing: one nullable field, no new entity columns. **Scope note:** the
submit-recovery *ledger's own* bookkeeping events (`submit_recovery_recorded` /
`_resolved` / `_needs_review`) link by `order_id`, not `correlation_id` — the
recovery record intentionally stores no `candidate_id` (keeping D-020 to one
nullable Event field); the recovery *trigger* (`order_submit_unpersisted`) does
correlate. A state-machine invariant (`correlation_id_matches_owning_candidate`)
holds the derive rule across every random interleaving in both stores.

### D-019 — One pre-trade policy module (`app/policy.py`), the single source for every gate (Wave 2)
**Context.** Both post-Phase-6 reviews named the same root cause — "each layer
invents its own check." Wave 0 planted *one* shared numeric predicate
(`finite_number_reason`); Wave 2 finishes the consolidation so that every
pre-trade policy decision — numeric validity, limit price, session resolution,
control state, CAPI risk limit + exposure, market-data field finiteness — is made
in exactly one place that routes, both stores, the strategy engine, and the
market-data path all import from.

**What changed.**
- **Promoted `app/store/validation.py` → `app/policy.py`.** The module was
  already ~80% of the policy surface, but it is used by routes / strategy /
  market-data, not just the store, so its home under `app/store/` was a
  misnomer. It is now a top-level module; its role is stated in its docstring as
  *the* single source.
- **Centralized the two remaining forks.** `order_session_resolution_reason`
  (the F-004 dispatch-time "unresolved session blocks order intent" rule, which
  had been inline in `plan_create_order_for_candidate`) and
  `market_data_field_reason` (the F-005 market-data finiteness guard). The
  feature engine's `_finite` now *delegates* to `market_data_field_reason`
  instead of forking its own `math.isfinite` — so the strategy/feature layer and
  the order/fill layer decide "is this a real number" identically.
- **Moved `app/store/transitions.py` → `app/transitions.py`.** The order
  state-machine table is domain config, not store implementation — and the move
  was also *required* to break an import cycle the promotion exposed
  (`app.policy` → `app.store.transitions` would trigger `app/store/__init__`'s
  eager `import memory → core → app.policy`, a partially-initialized-module
  error). At top level, `app.policy` → `app.transitions` → `app.models` has no
  cycle.

**Constraints honored (this is a refactor, not a rewrite).**
- **Behavior-preserving.** All 730 pre-existing tests pass with *only* import
  paths changed; no reason code changed meaning, no gate loosened or tightened
  on any input the type contracts admit. (`_finite`'s sole divergence is
  rejecting a *boolean* market-data field, which `Optional[float]` forbids and
  which the order/fill layer already rejected — an alignment, not a live gate
  change.)
- **No `RiskEngine`/policy ABC or async seam** (D-016c preserved): `app/policy.py`
  is pure functions only, so the approve-route pre-check and the authoritative
  store check keep calling the *same* function with the *same* inputs.
- **`order_intent_block_reason(None)` emergency-stop semantics preserved** and
  now pinned *distinct* from `order_session_resolution_reason(None)`: the former
  stays `None` (a missing current session = nothing to stop, for the monitoring
  loop); only the latter blocks `None` as `unresolved_session` (order-creation
  path). `tests/test_policy_consolidation.py` asserts this non-uniformity did not
  get flattened by centralizing.
- **`NON_TERMINAL_ORDER_STATUSES` stays derived** from `ORDER_TRANSITIONS`.

### D-018 — Controllable broker sim + stateful lifecycle harness (Wave 1)
**Context.** Every serious defect in this project's history was a
*temporal-sequence* bug found by luck of tracing the right interleaving
(session orphaning D-009, the kill-switch date-rollover bypass D-013a, the F-001
submit TOCTOU, the F-002 orphaned broker order). Example-based tests only cover
the sequences someone thought to write. Wave 1 adds two layers that attack the
whole class instead of instances, both fully IO-free (Rule 9) and run against
**both** stores.

**(a) `SimBrokerAdapter` (`app/broker/sim.py`) — a controllable test double.**
Extends `MockBrokerAdapter` (never replaces it; still no SDK, no network, never
wired into a production factory) with the controls needed to make otherwise
timing-dependent races *deterministic*: `set_on_submit(hook)` fires an async
hook mid-`submit_order` — after the broker id is minted and live but before the
call returns — so a test flips a control (kill switch, manual cancel, session
close) at the exact instant the real F-001/F-002 race would land;
`fail_submit_when`/`fail_cancel_when` raise at a chosen call index;
`script(id, updates)` queues a per-order status sequence (models
partial→partial→filled, a duplicate `source_fill_id`, a late fill after
`cancel_pending`), with the last update sticking once exhausted;
`disconnect_status_for(n)` makes the next N status polls raise then recovers;
`is_live(broker_id)` reports whether a broker order's current status is
non-terminal — the seam a recovery test uses to assert a stranded order was
actually cancelled.

**(b) A Hypothesis `RuleBasedStateMachine` over the real backend
(`tests/test_lifecycle_state_machine.py`).** Rules fire the real
store + monitoring-loop + sim operations
(create/approve+dispatch/`run_monitoring_tick`/submit-only-phase/script-fill/
cancel/kill/pause/close/arm-mid-submit-cancel-race) in Hypothesis-chosen orders,
catching only the exceptions a *legitimate* racing interleaving produces (closed
session, illegal transition because state moved, a control block) — anything else
propagates and fails. After **every** action it asserts the system's steady-state
safety contract as `@invariant`s: position never negative, `filled_quantity`
whole/bounded/equal to recorded fills, no candidate stranded `APPROVED`, every
order has a resolvable session, and **no live-at-broker order is untracked** (the
F-002 orphan guard — every `is_live` broker id must be referenced by a local
order or an open recovery record). Runs against memory and SQLite as two
`TestCase`s; the SQLite one closes its connection on teardown (ResourceWarning is
a suite-wide error, F-008). Async-in-Hypothesis (rules are synchronous) is solved
by giving each machine instance one persistent asyncio loop, so the store's
`asyncio.Lock` and SQLite connection stay valid across rules.

For the orphan guard to be a *live* invariant and not a vacuous one, the machine
has to actually construct the orphan: `arm_submit_cancel_race` installs a
one-shot `set_on_submit` hook that cancels the next order *inside* `submit_order`
(after its broker id is live, before the local `SUBMITTED` persist), and
`submit_pending_only` runs just the submit phase so the resulting orphan — broker
order live, local order terminal, recovery record open — is observable at an
invariant checkpoint before a full tick's recovery phase heals it. (An
independent review of the Wave 1 diff caught that without these two rules the
random machine could never reach the orphan state, so `no_live_untracked_broker_
order` always passed via its `tracked` clause and its `open_recovery` branch was
dead — the guard's whole point unexercised.) Mutation-validated twice: reverting
`revert_candidate_approval` fires `no_candidate_stranded_approved`, and neutering
`create_submit_recovery` (the F-002 ledger) now fires `no_live_untracked_broker_
order` — which it provably did **not** before these rules existed.

**(c) A deterministic chaos matrix (`tests/test_sim_chaos.py`).** Six pinned
reproductions of the exact sequences the random machine explores but can't
*guarantee* to hit each run, so they can never silently regress: duplicate fill
via reconcile (not double-counted), late fill after `cancel_pending` wins
(CHAOS-1), disconnect-then-recover (loop logs-and-continues, fill lands on
recovery), the F-001 mid-submit kill flip (claim already committed → still
submits), and the F-002 accept→local-cancel→recovery orphan in both the clean
(cancel-and-resolve) and the partial-fill (`needs_review`, kept visible, never
cancelled-and-dropped) variants — all driven through the real monitoring loop
via the sim's controls.

**Out of scope (kept minimal):** no fuzzing of market-data feature math here
(covered by Phase 5/Wave 0 finite-guard tests); the machine models the
order/candidate/session lifecycle, not the strategy engine's candidate
*generation*, which is deterministic given a snapshot and already unit-tested.

### D-017 — Atomic submission claim (`SUBMITTING`) + durable broker-submit recovery ledger
**Context.** An independent post-Phase-6 review found two blocker races
(F-001, F-002) with the *same* root cause: there was no durable
"submission-in-progress" state. `_submit_pending_orders` read the controls,
`await`ed `adapter.submit_order`, and only *then* marked the order — a window in
which a `set_kill_switch(True)` (F-001) or a `close_session` that cancels the
still-`CREATED` order (F-002) could slip in undetected. The kill switch could
lose the race (a stopped account still submitted); a session close could cancel
an order the broker had already accepted, leaving it live upstream but
locally `canceled` with no `broker_order_id`, orphaned (nothing polled a
terminal order).

**(a) A new intermediate `OrderStatus.SUBMITTING`, claimed atomically.**
`StateStore.claim_order_for_submission(order_id)` re-reads the order, re-reads
the current **and** the order's own originating session, re-checks every
control (kill-switch / buys-paused / session-closed / session-unknown / status
still `CREATED`), and — all under **one lock hold**, the same idiom as
`set_kill_switch`, no new primitive — transitions `CREATED → SUBMITTING` and
audits it. The monitoring loop calls this **first** and only submits claimed
(`SUBMITTING`) orders. Because the claim and every control mutation serialize
through the same lock, a flip lands either *before* the claim (order stays
`CREATED`, held) or *after* `SUBMITTING` (already committed to submission — the
human approved it and the backend atomically claimed it before the stop). The
transition table is **strict**: `CREATED → {SUBMITTING, CANCELED, REJECTED}`
(no direct `CREATED → SUBMITTED`) and `SUBMITTING → {SUBMITTED, CREATED,
CANCELED, REJECTED}` — so the claim is the *only* path to the broker, not just
the path the loop happens to use. `CREATED → SUBMITTED` is gone; test setup
that needs "an order as if submitted" uses the two-step helper
`tests/store_helpers.submit_created_order`. A transient `submit_order` raise
releases the claim (`SUBMITTING → CREATED`) so the next tick re-runs the *full*
gate (a flip during the retry window is then honored) — **unless the order's own
session closed during the submit await**, in which case the release goes
`SUBMITTING → CANCELED` instead: releasing to `CREATED` there would strand a
zombie `CREATED` order in a closed session forever (close is one-shot; nothing
else cleans it up), permanently inflating CAPI exposure — cancelling it is
exactly what close would have done to a `CREATED` order (D-013a). Session close
never cancels a `SUBMITTING` order — its cancel filter keys on `status is
CREATED`, so `SUBMITTING` is naturally excluded (pinned by a test). `SUBMITTING` is
non-terminal (it has outgoing transitions), so it counts toward CAPI exposure
automatically via the derived `NON_TERMINAL_ORDER_STATUSES`; it carries no
`broker_order_id`, so reconcile (which keys on `broker_order_id is not None`)
skips it.

**(b) A durable broker-submit recovery ledger, retried until resolved.** When
the broker accepts an order but the local `SUBMITTING → SUBMITTED` persist
fails, the handling now splits by *why*:
- **Order still `SUBMITTING`** (a transient persist hiccup) — it is genuinely
  open at the broker, so *retry* marking it `SUBMITTED`; do not cancel a
  legitimately-open order.
- **Order went `CANCELED`/`REJECTED` locally** (a manual cancel raced the
  submit) — the true F-002 orphan: live at the broker, terminal locally. A
  single best-effort cancel is not enough (if it fails the broker order is
  lost), so a **durable `SubmitRecoveryRecord`** is written (new table +
  `create/list/update_submit_recovery` store methods, mirrored in both stores).
  A recovery step folded into the monitoring tick polls/cancels the
  `broker_order_id` **every cadence until resolved**: zero fills and terminal
  → `resolved_canceled`; zero fills and still live → cancel and confirm; **any
  fills at all (partial *or* full)** → `needs_review`, because those executed
  shares are a real untracked position that a human must reconcile — it is
  never cancelled-and-dropped. A `needs_review` record stays in the operator's
  open view (`RECOVERY_OPEN_STATUSES`) until a human clears it; only the
  recovery loop's own `unresolved`-scoped query excludes it, so it is not
  re-cancelled. (The naive "cancel anything not already fully filled" version
  silently discarded a partial fill's shares — a hole the pre-merge review
  caught.)

**Explicitly out of scope (kept minimal per the remediation prompt):** a full
OMS-lite command/outbox layer beyond this claim + recovery record. **Known
limitation:** a hard process crash *between* the claim and the broker call can
leave an order stuck `SUBMITTING` with no `broker_order_id` (we can't know if
the broker received it); Wave 0 does not auto-recover that (auto-releasing to
`CREATED` risks a double-submit on a broker without an idempotency key, and the
claim window is a single `await`). Restart-recovery of orphaned `SUBMITTING`
orders is a noted follow-up, not a beta blocker.

**Enforcement points:** `app/store/core.py`'s pure `plan_claim_order_for_submission`
(the re-check + `CREATED → SUBMITTING` decision, storage-agnostic like the
other `plan_*`), both stores' `claim_order_for_submission` + recovery methods,
and `app/monitoring.py`'s rewritten `_submit_pending_orders` /
`_handle_unpersisted_submit` / new `_recover_unpersisted_submits`.

### D-016 — CAPI is a pure pre-trade risk *gate*, not a position-sizing engine; local-derived exposure; reject-not-resize
**Scope.** Phase 6 ships the **preservation** half of CAPI (max shares/notional
per order, max total exposure, a trading allowlist) as a hard pre-trade gate.
It does **not** ship the **allocation**/sizing half — `suggested_quantity` and
`suggested_limit_price` remain the Strategy Engine's fixed placeholder (D-014b,
`risk_decision="phase5_fixed_size_pending_capi"`); real capital-based sizing
(account-equity-aware position sizing) is still future work that would feed
the *same* gate below, not a separate mechanism.

**(a) Gate-and-reject, never resize.** A proposed order that breaches a limit
is blocked outright with an audit reason; it is never silently shrunk to fit.
Rationale: the human approved a specific size — resizing it without asking
would be a surprising, opaque behavior change to what was approved, and real
position-sizing logic belongs in a future phase designed for it, not bolted
onto a limit check.

**(b) Local-derived exposure only — no live broker/market-data call.**
Exposure is computed entirely from state the store already has: every
position's **cost basis** (not mark-to-market — beta already defers
unrealized P/L elsewhere, per the Position Monitor) plus every non-terminal
order's remaining (unfilled) quantity × its own `limit_price`. This keeps the
order path free of a new dependency on `MarketDataService` or a broker
round-trip; "buying power" in the brokerage-account sense is out of scope
(fake money in paper anyway). `StateStore.current_exposure()` reads this as
one atomic snapshot under a single lock acquisition, so a caller outside the
store's lock (the approve route's pre-check) never observes a torn read
across two separate lock cycles.

An order's "remaining" notional is priced off its **actual filled quantity,
derived from the fill table** — not `Order.filled_quantity` — for a subtle but
real reason a pre-merge review caught: `append_fill` and the later
`transition_order(..., filled_quantity=...)` call that catches the order's own
`filled_quantity` field up are two *separate* atomic operation groups (see
`docs/02_DATA_AND_PERSISTENCE.md`; `app/monitoring.py`'s `_apply_update` always
calls them in that order, as two independent lock-guarded calls). In the
window between them, a position's cost basis has already moved but
`Order.filled_quantity` hasn't — reading the stale field there would
double-count the just-filled shares. `existing_exposure()` avoids this by
summing each order's fills directly (available in the same lock hold that
already reads `positions`), so both halves of the exposure sum are always
grounded in the fill table, never a field that can lag it.

This approximation is **directional, not neutral**: cost basis over-counts a
position that has since dropped in value (the cap binds *sooner* than
mark-to-market would — conservative) and under-counts one that has risen (the
cap binds *later* — permissive). Because `premarket_momentum_v1` (D-014)
specifically targets momentum winners, the realistic failure mode is the
permissive direction — a position that ran up since entry reads as less
exposure than it actually represents. Acceptable for beta's gate-and-reject
cap; worth revisiting if CAPI is ever asked to bound something more precise
than "don't blow past a round-number ceiling."

**(c) No separate `RiskEngine` ABC — a pure predicate, like the sibling checks.**
The original plan sketched a pluggable `RiskEngine` ABC mirroring
`BrokerAdapter`/`MarketDataService`/`ApprovalGate`. Implementation surfaced a
better fit already established in this codebase:
`order_intent_block_reason` (Rule 8's kill-switch/pause-buys check) is a
*plain synchronous function* called from two places — the approve route
(pre-check, for UX) and `create_order_for_candidate`'s planner (authoritative,
for correctness) — and gets "any future Auto-Buy mode honors this for free"
pluggability for free just by living at the store boundary, no ABC required:
the store is already the seam a future Auto-Buy mode would sit behind, so a
second pluggable layer above it would be pluggability the codebase already
has, built twice. `risk_limit_reason` (`app/store/validation.py`) follows the
identical pattern. This is a premature-abstraction call, not a technical
constraint — `plan_create_order_for_candidate` (`app/store/core.py`, from the
store-hardening interlude) stays a pure, synchronous planner either way, since
its inputs (`exposure_before_order`, `risk_limits`) are plain values the store
already fetched before calling in; an async `RiskEngine.check(...)` call
could sit in the store method that surrounds the planner without breaking the
planner's purity. The reason to skip it is that nothing today needs a second
implementation behind that interface — one pure function with one caller
shape doesn't earn an ABC. If a future Auto-Buy phase needs live broker-backed
limits (real buying power, not cost-basis exposure), *that* is the point to
introduce an async seam — not now, per (b).

**Enforcement points:** `app/api/routes_candidates.py`'s `approve_candidate`
(pre-check, mirrors the existing kill-switch/pause-buys pre-check exactly,
including race recovery via `revert_candidate_approval` if a limit is breached
between the pre-check and the store handoff) and
`StateStore.create_order_for_candidate`'s optional `risk_limits: RiskLimits`
parameter (authoritative, under the store's lock). `RiskLimits`
(`app/store/base.py`) bundles the four independently-optional limits
(`max_shares_per_order`/`max_notional_per_order`/`max_total_exposure`/
`allowlist`) into one dataclass rather than four separate keywords threaded
through the abstract method, both stores, the planner, and the route (which
needs the same values twice — pre-check and authoritative call) — a future
limit type is one field added in one place. `RiskLimits()`, the default, is
fully unenforced at the *interface* level (keeping ~20 pre-existing test call
sites unchanged), but the approve route always builds one from real,
validated-positive values loaded from `Settings` — `app.config`'s
`_env_float` rejects a non-finite/non-positive `CAPI_MAX_*` value at startup
(the same footgun class as `MARKET_DATA_STALE_MINUTES`), so CAPI can't be
silently disabled by an env misconfiguration the way `None` can be by a test.
A breach raises `RiskLimitBlockedError` and writes a `risk_limit_blocked`
audit event with the reason code and the numbers involved.

**Why now.** Phase 6 is the first CAPI work; recording the scope boundary (a)
and the exposure-model boundary (b) here means a future Auto-Buy/real-sizing
phase inherits an explicit decision to revisit, not silence. (c) is recorded
because it's a deviation from the originally-sketched design, surfaced only
once the store's own architecture was examined closely — worth keeping
visible so a future reader doesn't wonder why CAPI has no engine class
alongside its three siblings.

### D-015 — Order submission sets `extended_hours` from the current session (resolves BACKEND-2)
**Decision.** `AlpacaPaperAdapter.submit_order` (`app/broker/alpaca_paper.py`)
now sets Alpaca's `extended_hours` flag based on `session_type_for(utcnow())`
**at submission time**: `True` when the current session is `PRE_MARKET` or
`AFTER_HOURS`, `False` otherwise (including when there is no session at all,
e.g. overnight). No `Order`/`Candidate` schema change — submission-time is a
more correct reading of Rule 12's "session-conditional" than candidate-
creation time anyway, since extended-hours eligibility is a property of when
the order actually reaches the exchange. A candidate whose human approval is
delayed past its original session's close naturally falls back to a plain
regular-hours DAY limit (which doesn't need the flag) rather than incorrectly
carrying a stale premarket intent forward.

**Why now, and why it matters.** `BACKEND-2` (Phase 4 cleanup) deferred this
with the stated prediction "lands in Phase 5 when the Strategy Engine produces
session-tagged candidates" — but when Phase 5 actually shipped, the
order-submission side was never revisited, so the flag stayed unset. This
went from a **theoretical** gap to a **real one** the moment Phase 5's
`premarket_momentum_v1` started proposing real candidates: that strategy
proposes **exclusively** during `PRE_MARKET`/`AFTER_HOURS` (see D-014), so
every one of its approved candidates would have submitted as a plain
regular-hours DAY limit order — silently ineligible to execute in the very
session it was proposed for, defeating the strategy's purpose without any
error, rejection, or other visible signal. Found during a post-Phase-5
self-review specifically because "review prior development, especially
critical areas" prompted re-reading `alpaca_paper.py` alongside the now-built
Strategy Engine, rather than reading either file in isolation — the gap only
becomes visible when you trace a real premarket candidate all the way through
to submission.

### D-014 — Strategy Engine: candidate generation is not kill-switch-gated; placeholder sizing; open-candidate dedup; sync/staleness are session-independent
**Four decisions for Phase 5 (the first candidate generator).**

**(a) / D-014a — Candidate generation is not gated by the kill switch or pause-buys.**
Rule 8 blocks *order intent* — it says nothing about candidate *visibility*.
The Strategy Engine keeps proposing candidates for human review even while
buys are paused or the kill switch is engaged; the existing enforcement
(D-013a) already blocks any resulting order from reaching the broker. A human
operator may still want to see what the strategy would propose during a
stop, and conflating the safety control with the informational proposal feed
would make the kill switch do double duty as a "hide the feed" toggle it was
never meant to be.

**(b) / D-014b — Sizing is a fixed placeholder, not real risk logic, until CAPI exists.**
`suggested_quantity` is a configurable fixed default; `suggested_limit_price`
is `last_price` plus a small buy-through buffer. `risk_decision` states
plainly this is placeholder sizing pending Phase 6 CAPI — the Strategy Engine
does not invent risk management it isn't built to own.

**(c) / D-014c — Dedup blocks on an *unresolved* candidate only.** The strategy loop
skips a symbol that already has a `PENDING`/`APPROVED` candidate this session
(don't spam a proposal nobody has acted on yet), but a symbol that reached
`ORDERED`, `REJECTED`, or `EXPIRED` is eligible for a fresh proposal — the
human already made a decision on the prior signal, and a stock that keeps
moving can legitimately generate a new, separately-approvable one.

**(d) / D-014d — Subscription sync and staleness surfacing never touch session state.**
The strategy loop originally fetched (and, on an idle day with nothing armed,
implicitly *created*) the current session as its very first step, every tick —
an unintended side effect: an idle watchlist would still mint an empty session
purely from the loop ticking. Fixed by reordering so `get_current_session` is
only called once armed symbols are known to exist (i.e., there is actually a
candidate to evaluate against). This has a second, deliberate consequence: a
just-disarmed symbol's subscription is always synced (unsubscribed) and a dead
feed is always surfaced (`market_data_stale`), regardless of whether a trading
session is open, closed, or hasn't started yet for the day — market-data
ingestion is a process-lifetime concern (`app/main.py`'s feed task already
runs independent of the strategy loop), not a trading-session concern, so
gating its bookkeeping on session state was never correct. Only *candidate
evaluation* — the part that needs a session to attach to and to check "is
trading stopped for today" — still skips when the session is closed.

**Why now.** Phase 5 is the first phase where anything other than the dev
route creates candidates, so these are the first real calls on "what makes a
candidate worth proposing" and "what should proposal even mean" — recorded
here so a future Auto-Buy engine (Phase 9) inherits the same posture rather
than each future producer re-deciding it independently. (d) surfaced during a
self-review pass after the phase shipped — recorded here rather than only in
a commit message so a future reader of `strategy_loop.py` finds the reasoning
in the same place as (a)-(c).

### D-013 — Order submission gates on the order's own session; localhost is a load-bearing security boundary
**Two decisions, both surfaced by independent red-team review of Phase 4.**

**(a) / D-013a — Submission gate is per-order-session, not current-session.** A `CREATED`
order must be gated for submission against the kill-switch / pause-buys / closed
state of **the session that created it**, not merely the current live session.
Previously `_submit_pending_orders` checked only `get_current_session()`, on the
stated assumption that "beta opens no new session automatically, so a held order
can't be released." That assumption was false: `get_current_session()`
auto-creates a fresh session on UTC date rollover, so a kill-switched order from
yesterday's session could submit under today's permissive defaults (a Rule 8
violation). The same gap lets a `CREATED` order submit after its session was
manually closed. Fix: submission checks the order's own session; an order whose
originating session is kill-switched, paused, or closed is held (and audited),
never submitted under a different session's controls. Already-submitted orders
continue to reconcile after close (D-011 unchanged).

**(b) / D-013b — Single-user localhost is a security assumption, not just a convenience.**
The mutating API is unauthenticated by design (`routes_system.py` states "no auth
in beta"). This is acceptable **only while the backend is genuinely bound to
localhost and single-user.** Any exposure beyond localhost — LAN, cloud,
shared host, unattended deployment — requires an operator token / API-key guard
or enforced localhost binding **first**, because an unauthenticated mutating API
reachable on a network lets another party approve, cancel, pause, close, and
thereby indirectly submit paper orders. Recorded here as an explicit, hard
deployment boundary so it's a conscious gate before any non-local run, not a
silent assumption that erodes as the project grows.
**Why both now.** (a) is a confirmed safety bug fixed in the Phase 4 cleanup;
(b) is not a code change for beta but must be recorded before the project
approaches real accounts, where the same unauthenticated surface stops being
benign.

### D-012 — Position snapshots are point-in-time-at-close; post-close fills are not retro-applied
**Decision.** `position_snapshots` (written at session close, D-007) capture
the derived position *as it stood at the moment of close*. If an order that was
open at close — specifically a `cancel_pending` order still being polled to a
terminal state (D-011) — receives a fill *after* the session is closed, that
fill updates the **live** position and the order/fill record, but is **not**
retro-applied to the closed session's frozen snapshot. Consequently
`GET /api/review?date=<closed day>` (snapshot) can legitimately differ from
`GET /api/positions` (live) for a symbol whose order completed after that day's
close. This is intended behavior for beta, not a reconciliation bug.
**Why.** A point-in-time snapshot is, by definition, what the world looked like
at a specific instant; re-applying later events would make it not-point-in-time.
The alternative — re-snapshotting a closed session whenever a post-close fill
lands against one of its orders — is a real feature with real complexity
(closed sessions would stop being immutable), and it buys little in beta where
the divergence is small, visible in the live position and the order/fill/audit
record, and only arises in the narrow cancel_pending-fills-after-close window.
Beta accepts the divergence and documents it here so a future reviewer reading
a past day's snapshot understands why it may not match the order's final filled
quantity. Reconciling closed-session snapshots is a candidate for a later phase
if it ever proves to matter operationally.

### D-011 — Phase 4 Alpaca Paper Adapter: REST polling, surface-and-cancel, cross-session monitoring
**Decision.** Three Phase 4 design choices:
1. **REST polling over websocket trade updates.** Order status is polled on a
   fixed cadence (15-second default, `ALPACA_POLL_CADENCE_SECONDS`) rather than
   via Alpaca's trade-update websocket. REST polling is simpler, easier to test
   with a mock adapter, and sufficient since a human approves each order in beta
   (no latency pressure). The websocket trade-updates approach is noted as the
   Phase 8 upgrade when Auto-Sell's fill-reaction speed demands it.
2. **Surface unfilled timeouts + manual cancel; no auto-cancel.** Orders open
   past a configurable threshold (60-minute default, `ALPACA_UNFILLED_TIMEOUT_MINUTES`)
   are flagged via an audit event and surfaced in the cockpit. A manual cancel
   button calls `POST /api/orders/{id}/cancel`, which cancels via the adapter
   and transitions the order to `canceled`. Auto-cancellation is deferred to
   Phase 8's automated exit logic; human-in-the-loop beta doesn't auto-cancel.
3. **Keep polling until terminal state regardless of session close.** The
   monitoring loop polls all orders in `submitted`/`partially_filled` status
   irrespective of their session's closed/active state. A submitted order
   represents a real open position that needs tracking even after session close;
   stopping mid-fill would leave positions stale. The position carries forward
   across sessions by design (D-007).

**Also settled in Phase 4:** `alpaca-py` is the SDK (official current package,
not the older `alpaca-trade-api`); nothing outside the adapter imports it.
`BrokerAdapter` is a pluggable interface (same ABC pattern as `ApprovalGate`)
so a future live adapter is a drop-in without touching callers. Order submission
is driven by the monitoring loop (not the approval endpoint) — the loop finds
`ORDERED` orders not yet submitted and dispatches them, keeping the Phase 3
handoff and Phase 4 execution cleanly separate. Unrealized P/L is deferred to
Phase 5 (needs current price from the market data service). Position flatten is
deferred to Phase 7 (Sell-Side Protection owns exit logic).

### D-010 — Store entrypoints validate inputs; the fill table never holds corrupt data
**Decision.** `append_fill`, `create_order`, and `transition_order` validate
their inputs at the store boundary (both implementations), rejecting
malformed values before any row is written or position is mutated:
- **Fills:** `quantity > 0` and `price > 0`; the referenced `order_id` must
  exist; the fill's symbol and side must match the order's; cumulative filled
  quantity for an order may not exceed the order's quantity. Duplicate
  detection and oversell rejection (D-006) are preserved.
- **Orders:** `create_order` requires the referenced `candidate_id` to exist
  and the order symbol to match the candidate's symbol. (It does **not** yet
  require the candidate to be `APPROVED` — that lifecycle rule belongs to
  Phase 3's Approval Gate; adding it to `create_order` now would pre-empt a
  decision the gate owns. Existence + symbol match are the uncontroversial
  half and go in now.)
- **Order transitions:** `filled_quantity` must satisfy
  `0 <= filled_quantity <= order.quantity` and must be monotonic
  non-decreasing (no broker-correction path exists in beta). D-008's audit
  behavior is preserved.
Rejections write a clear rejection audit event (consistent type across both
stores) and raise; they never append a fill/`fill_appended` event or mutate
position.
**Why.** A red-team pass found `append_fill` accepted negative/zero quantity
and price (a negative buy creates a negative position; a negative price
creates negative cost basis — both directly corrupt the derived-position
truth the whole architecture treats as sacred), accepted fills for
nonexistent/mismatched orders, and `create_order` accepted nonexistent
candidates. These are input-boundary holes, distinct from the lifecycle/
temporal correctness the prior rounds focused on — the happy paths and
intended invariants were enforced, but hostile inputs weren't rejected.
Validating at the store boundary (not only the model) keeps both
implementations consistent and produces predictable `StoreError`s. Done now,
before Phase 3 generates real candidates/orders/fills, because corrupt
foundational data is far cheaper to prevent than to reconcile later.

### D-009 — One session per calendar date; no auto-create after close
**Decision.** A calendar date has at most one session. `get_current_session`
must **not** conjure a new session when the only session for today is already
`closed` — closing a session ends the trading day; there is no active session
again until a genuinely new day (or, later, an explicit open). `GET
/api/session` returns the closed session's state in that window rather than
silently creating a fresh active one. `get_session_by_date` therefore has an
unambiguous answer for every date.
**Why.** A red-team trace found that after `POST /api/session/close`, any
later `get_current_session` call — which `GET /api/session` makes on every
Session Control render — created a *second* session for the same date. With
two same-date sessions, `get_session_by_date` (newest-first / `ORDER BY rowid
DESC LIMIT 1`) returned the fresh empty active one, so `GET
/api/review?date=today` showed an empty session and the snapshots captured at
close became invisible by date. This is a temporal-interaction bug (no single
malformed call; it lives in the close → view → review sequence) and directly
undermines the D-007 snapshot mechanism it was meant to make reliable. The
"no auto-create after close" rule matches the manual-close model: you closed
the day, so there is no active session until the next one starts. (Automatic
next-session opening tied to a session window remains deferred to whenever the
Phase 4/5 monitoring loop exists.)

### D-008 — Order-transition audit events must not fire on true no-ops
**Decision.** `transition_order` (and any future order-mutating method) must
not write a new audit event when the call is a genuine no-op (status
unchanged, no other field changed) — matching the rule `transition_candidate`
already follows correctly. When `filled_quantity` changes without a status
change (the normal repeated-partial-fill case during Phase 4 reconciliation),
that's still a meaningful event and must be recorded, with the before/after
quantity in the payload.
**Why.** The first build round's implementation wrote an `order_transition`
event on every call regardless of whether anything changed, identically in
both `InMemoryStateStore` and `SqliteStateStore` (confirmed by direct code
review, not just the build's own self-review — its adversarial-review pass
missed this). Phase 4's polling-based reconciliation calls
`transition_order(..., PARTIALLY_FILLED)` repeatedly as fills accumulate
against one order; left as-is, the audit log fills with generic
"partially_filled → partially_filled" rows that don't show the one thing
that's actually interesting — how much has filled so far — which undermines
the audit log's whole purpose.

### D-007 — Session close is an explicit, manually-triggered lifecycle event; positions get a snapshot table; fills get session_id
**Decision.** `POST /api/session/close` (new endpoint, manual in beta) atomically: (1)
transitions every `pending`/`approved` candidate to `expired`, (2) writes the
current derived positions into a new `position_snapshots` table keyed by
`session_id`, (3) marks the session `closed`. `GET /api/review?date=` returns
the live derived view for the active session and the stored snapshot for a
closed one. `Fill` gains a `session_id` field (the parameter already existed
on `append_fill` but was never persisted onto the row) so fills are
date-filterable directly, without a join through `Order`. Automatic
close — tied to the session window ending — is deferred to whenever a
monitoring loop exists to drive it (Phase 4/5); beta only provides the manual
trigger.
**Why.** `02_DATA_AND_PERSISTENCE.md` always described what closing a session
should *accomplish* ("expires open candidates, and snapshots the day for
review") but the original API contract in `01_ARCHITECTURE.md` never defined
an endpoint that does it, and nothing implemented the snapshot table the
persisted-entities list had already named. This surfaced concretely once real
code existed: the review endpoint built in the first round returns today's
live position and the entire all-time fill history for *any* requested date,
because there was nothing point-in-time to read instead. Building the
snapshot mechanism now, before Phase 3/4 generate real candidates and fills,
is cheaper than retrofitting point-in-time accuracy after real trading history
exists.

### D-006 — Candidate/order split, fill dedup, transactional writes, precise position formula
**Decision.** Four refinements to Phase 1.5, adapted from concerns raised
against an analogous (but multi-broker) Webull/IBKR sibling project, applied
only where they're genuinely broker-agnostic:
1. Candidate and Order are separate lifecycles. Candidate status stops at
   `ordered`; broker-execution states (`submitted`, `partially_filled`,
   `filled`, `canceled`, `rejected`) live on the Order, linked by
   `candidate_id`. Fill remains append-only with no status at all.
2. The fill table carries a nullable `source_fill_id` (Alpaca's own
   fill/execution identifier), unique when present, so a duplicate observed
   fill is detected and audit-logged rather than appended twice.
3. Multi-row mutating operations are atomic: a SQL transaction in
   `SqliteStateStore`, the existing `asyncio.Lock` in `InMemoryStateStore`.
4. The derived-position folding formula is now precisely specified
   (average-cost, long-only), with minimum test cases and an explicit rule
   that a sell driving quantity negative is a rejected data-integrity error,
   not a short position.

**Deliberately not adopted from the reference material:** a fourth
`OrderIntent` entity between Candidate and Order (it exists in the sibling
project to abstract "approved, not yet dispatched to *which* broker adapter"
across multiple brokers — this project has exactly one broker, so that seam
has nothing to mediate); a persisted `market_snapshots` table (this project
already decided snapshots are in-memory working data, not durable records —
see D-005); a second `idempotency_key` field alongside `source_fill_id`
(redundant with one broker — Alpaca's fill ID already serves that purpose);
and the sibling project's IBKR/Webull/TradingView-specific phase structure
(not applicable — see Rule 11 and "What This Project Is Not").

**Why.** The candidate/order conflation made the Phase 4 reconciliation
policy (timeouts, partial fills) awkward to express against a status field
that also meant "did a human approve this." Duplicate fills are a real risk
specifically because Phase 4's reconciliation is polling-based — overlapping
polls or a reconnect can surface the same fill twice. Atomicity closes a gap
where the lock prevented races between coroutines but didn't guarantee a
multi-row write was all-or-nothing if the process died mid-write. The
position formula needed to move from "folding the fills" (true but
unspecified) to an actual formula so Phase 1.5 has something testable.

### D-005 — Market data: real-time websocket ingestion, fixed-cadence strategy evaluation
**Decision.** With the paid Algo Trader Plus subscription, the backend holds
one real-time SIP websocket stream open to maintain a per-symbol snapshot
continuously. The Strategy Engine evaluates that snapshot on a fixed cadence
(not on every tick). The backend must detect a dropped connection and
reconnect automatically rather than let the snapshot go silently stale.
**Why.** Continuous ingestion and periodic decision-making are different
concerns. Re-deciding on every tick produces flickering candidates from noise
with no benefit, since beta requires human approval anyway and isn't racing
anyone on latency. Auto-reconnect follows the project's standing rule that
nothing fails silently — an unnoticed dropped feed is the market-data
equivalent of silent data loss. This supersedes the earlier "polling" language
in `02_DATA_AND_PERSISTENCE.md`.

### D-004 — Approval is a pluggable gate; Auto-Sell ≠ Sell-Side Protection; order types are session-conditional
**Decision.** Candidate approval is built behind an Approval Gate interface
that, in beta, has exactly one mode (human-in-the-loop). A future Auto-Sell
Engine (nearer-term) and Auto-Buy Engine (further out) attach to the same gate
as automatic modes, rather than requiring a rebuilt state machine. Auto-Sell is
architecturally distinct from the Sell-Side Protection Engine: protection is
always-on safety (hard floor, controlled exit); Auto-Sell is a strategy
decision about taking profit or exiting on momentum reversal, including
canceling/replacing/resizing orders to complete an exit. Protection takes
priority over Auto-Sell if they disagree. Order type policy is permanent and
session-conditional: limit-only in pre-market/after-hours, broker order types
(market, trailing stop, etc.) permitted during regular hours.
**Why.** The buy side starts discretionary in beta but is expected to become
automatic later; the sell side is expected to gain a second, nearer-term
automatic mode (profit-taking) on top of the safety-only protection engine that
already exists. Building the approval step as an interface now — rather than
as hardcoded UI-triggered logic — means beta ships unchanged while leaving a
clean attachment point for both future engines. Distinguishing Auto-Sell from
protection prevents conflating "exit because it's strategically time" with
"exit because something is structurally wrong," which is a common source of
bugs in retail trading systems. The order-type rule is stated as permanent,
not beta-only, because the underlying reason (thin premarket/after-hours
liquidity) doesn't go away when automation is added.

### D-003 — Persistence: SQLite via a repository interface, history kept across days
**Decision.** State persists in a local SQLite file accessed only through a
`StateStore` interface. History (watchlists, candidates, orders, fills,
positions, events) accumulates across days and is queryable by session/date.
**Why.** A page refresh never loses data (Streamlit is thin and re-reads the
backend), but a backend *restart* — reboot, sleep, crash, redeploy — would wipe
pure in-memory state. For a trading cockpit that erodes trust and discards the
audit trail. The user wants data to persist unless outdated or deleted, and to
review past sessions. SQLite is a single local file: no server, no extra
process, no credentials, which fits single-user localhost. The interface keeps
unit tests IO-free (in-memory implementation) and makes a later Postgres swap a
one-file change.
**Supersedes.** The earlier "in-memory state, no database" stance.

### D-002 — "Durable" means authoritative-and-persistent, not just in-RAM
**Decision.** The backend is the single source of truth, and that truth is
persisted (see D-003). Current position is *derived* by folding the append-only
fill history, never mutated directly.
**Why.** Aligns the word "durable" with actual behavior and reinforces the
safety rule that only fills change position quantity — the fill table *is* the
source of truth.

### D-001 — Option 2.5: FastAPI engine + Streamlit thin cockpit, Dash later
**Decision.** FastAPI backend is the durable engine; Streamlit is a disposable
thin client; Dash is a possible future migration against the same API.
**Why.** The user does not want command-line operation. Streamlit gives faster
beta iteration than Dash as long as it stays thin. A stable, UI-agnostic API
contract preserves the migration path.

## Review Finding Tags

Several external review passes (a Codex QA/red-team review, and the Phase 4
cleanup round in `docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_4_CLEANUP.md`) tagged
individual findings with short ids that are still cited inline in code
comments and test docstrings (e.g. `(F1)`, `(BACKEND-1)`) as the reason a
specific guard/behavior exists. The originating review documents for the
Codex-tagged findings were never checked into this repo, so those ids weren't
resolvable anywhere in-tree — this index exists so a reader hitting one of
them in a comment doesn't have to grep the whole codebase to reconstruct what
it means. `docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_4_CLEANUP.md`'s own items (D-013,
D-013a, BE-1) are its native tags, already defined there in full — **not**
duplicated below, and **not** the same tag as the similarly-named `BACKEND-1`.

- **CHAOS-1** — `cancel_pending`/`CANCEL_PENDING` is a non-terminal order
  status: a cancel requested at the broker but not yet confirmed keeps being
  polled, so a late fill arriving before the venue finalizes the cancel is
  still recorded, never missed. See `app/models.py`'s `OrderStatus` docstring.
- **CHAOS-2 / DATA-1** — a single paired finding: the original fill-sourcing
  code mixed two fill-identity schemes (per-execution broker activity ids vs.
  a synthetic cumulative-level id), which could record the same shares twice
  under different ids if the activities API returned inconsistent results
  across polls. Fixed by using one scheme only — a stable
  `"<broker_order_id>:<cumulative filled_qty>"` delta id (see
  `app/broker/alpaca_paper.py`'s `_get_fills`, `tests/test_alpaca_paper_fills.py`).
- **DATA-2** — `normalize_symbol` (`app/store/base.py`) bounds the ticker
  domain (a leading letter then up to nine more letters/digits/`.`/`-`) and
  rejects blank/out-of-domain input with a clean 422 rather than letting an
  overly long, unicode, whitespace, or SQL-looking string reach durable
  trading data.
- **BACKEND-1** — `NaN`/`Infinity` slip past a bare `<= 0` guard (`nan <= 0`
  and `inf <= 0` are both `False`) and would poison `cost_basis`/
  `average_price` and persisted order/fill rows; rejected at the store
  boundary (D-010) and the API schema. See `tests/test_non_finite_inputs.py`.
  Distinct from the cleanup doc's `BE-1`, which is about non-finite *config*
  timing values (poll cadence / timeout), not order/fill numeric fields.
- **BACKEND-2** — `submit_order` never set Alpaca's `extended_hours` flag
  based on the current session, so a premarket/after-hours limit order was
  silently ineligible to execute in the very session it was proposed for.
  Resolved by D-015.
- **F1** — fill dedup was originally a column-level `UNIQUE` on
  `source_fill_id` alone (global across all orders), so the same broker fill
  id appearing on two *different* orders could swallow the second order's
  fill. Fixed with a composite `(order_id, source_fill_id)` index — dedup is
  per-order. See `tests/test_fill_dedup_per_order.py`.
- **F2** — no new candidates may be created against a closed session (D-009).
- **F3** — the in-memory candidate-approve + order-creation handoff must be
  all-or-nothing, matching `SqliteStateStore`'s transactional guarantee — a
  mid-way exception must not leave an approved candidate with no order.
- **F4** — two real (but previously unmapped) Alpaca order statuses, `held`
  and `calculated`, are explicitly mapped to `SUBMITTED` so they don't hit the
  unknown-status warning path in normal operation.
