"""CAMPAIGN-0002 (R2 consolidation campaign) -- Claude investigator's spec-derived
conformance oracle for WO-0036 R2 (the SellIntent<->Envelope lifecycle link).

DERIVATION DISCIPLINE (CONSOLIDATION-CHARTER.md §3): every property below is derived
from the spec sources -- ADR-010 (`docs/adr/ADR-010-execution-envelope.md`),
`docs/INVARIANTS.md` (INV-030..038 sell-intent lifecycle, INV-076..089 execution
envelopes), `work/active/WO-0036-intent-envelope-lifecycle-link.md` (the "Option A+"
design + its Done-when checklist), `work/review/AUDIT-0001-quarantine-treadmill.md`,
and `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` §5 (INV-1..9) -- NOT from reading either
R2 attempt's diff. It is run, unmodified, against both attempts in scratch worktrees;
see the campaign report `work/review/CAMPAIGN-0002-claude/report.md` §B for the
resulting truth table. Per the charter: "the oracle is the definition of done for
behavior -- it may not be edited to pass" (§B1); a needed change here is a spec
change and goes to the human.

CORE R2 PROPERTY (charter §3, stated formally): for every symbol, at every point in
an envelope-backed exit's life, the backing SellIntent is "active" (dedup-blocking,
per INV-032/`active_sell_intent_for`) IFF there exists a non-terminal exit obligation
for that symbol -- a live (ACTIVE/FROZEN) envelope, OR a child order that may still
rest at the venue. No boundary (session close, rollover, reprice, quarantine,
supersession, flatten, kill/resume) may open a window where the symbol has zero
owner but live exposure, or two owners.

IMPLEMENTATION-INDEPENDENCE NOTE: the two attempts under comparison represent this
fact differently -- one (evented terminal propagation) is expected to keep the
SellIntent row's own `status` field non-terminal for as long as the obligation
exists, ultimately writing an explicit terminal transition when it is discharged;
the other (delegation projection) is expected to derive activeness from envelope
lineage at read time, which does not require the SellIntent row's `status` column
itself to stay non-terminal. This oracle therefore asserts the OBSERVABLE contract
(`active_sell_intent_for`, `create_sell_intent`'s single-flight dedup, and the
ACTIVE-envelope-per-symbol count) rather than pinning the internal representation
choice -- except where the spec is explicit that a *specific* status value is part
of the contract (e.g. WO-0036's "NOT SUPERSEDED -- the successor keeps the intent").

SCOPE LIMIT (recorded, not silently dropped -- see charter's VERIFIED/UNVERIFIED/
BLOCKED/NEEDS-INPUT discipline): the charter's §3 class-closure list also names
"stale SUBMITTING", "claim/venue crash", and "monitoring-side newest-wins
convergence" as treadmill siblings to probe. Those three require driving the real
monitoring tick (`app.monitoring._run_envelopes` / `_redrive_stale_submitting` /
the reconciliation loop) rather than the StateStore contract alone, and the
tick-driving code differs enough between the two attempts (Sol's attempt also
rewrites `app/monitoring.py` and `app/reconciliation.py`; Claude's does not) that a
single implementation-independent store-level harness cannot exercise them
faithfully. They are left as explicit NEEDS-INPUT stubs below rather than shipped
as shallow/misleading tests; §C/§E of the campaign report exercise them directly
against each attempt's own tick code instead. "below-floor/phantom-print" and
"deviation-suspect prints" (INV-088) are pre-existing, closed pre-R2 (AUDIT-0001
root R4/pure-math-0) and orthogonal to the intent<->envelope link itself -- included
here only as a regression guard, not a new R2 property. True multi-day "date
rollover" (as opposed to an ordinary same-day session close) is ALSO deferred:
`get_current_session()` exposes no injectable clock in the StateStore ABC, and an
earlier version of this suite that called `close_session()` twice in a row without
a real calendar-day change simply hit `SessionAlreadyClosedError` on the
already-closed session rather than exercising a second boundary -- a fixture
artifact, not a property result, removed rather than shipped misleading. The
single-close-boundary property (`test_no_orphan_at_session_close`) is exercised
directly and rigorously below; a genuine multi-day repro needs either an
injectable session clock or driving the real calendar through the sqlite file's
date columns, better done in §C/§E against each attempt's own fixtures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.core import STAGE_STAGED
from tests.store_helpers import submit_created_order

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)  # Wed 10:00 ET, REGULAR


# --------------------------------------------------------------------------- #
# Shared builders. Pattern shared with base-commit (22617f4) test infrastructure
# (tests/test_wo0019_engine_seam.py, tests/test_wo0032_per_symbol_mandate.py,
# tests/test_rev0023_phase_a2_pins.py) -- this is pre-existing, implementation-
# -independent scaffolding common to both attempts' ancestry, not derived from
# either attempt's diff.
# --------------------------------------------------------------------------- #


def make_draft(
    intent_id: str, symbol: str = "AAPL", *, session_id: str | None = None, **overrides
) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol=symbol,
        session_id=session_id,
        qty_ceiling=100,
        floor_price=9.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=T_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def planned_submit(
    kind: ActionKind = ActionKind.SUBMIT, *, limit_price: float, quantity: int
) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=limit_price,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=limit_price - 0.50,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


async def seed_position(store, symbol: str = "AAPL", quantity: int = 100) -> None:
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, quantity, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, quantity, 10.0, session_id=session.id
    )


async def open_mandate(
    store, symbol: str = "AAPL", quantity: int = 100, **draft_overrides
):
    """The full realistic R2 chain this oracle probes: a real position, a real
    SellIntent (not a synthetic id), SESSION-STAMPED (matching
    `tests/test_rev0023_phase_a2_pins.py::
    test_PIN_P0_no_two_active_envelopes_per_symbol_across_session_boundary`'s own
    construction -- W3-STATE.md records that `create_sell_intent` does NOT
    auto-stamp `session_id`, so an oracle that omits it would never actually
    reach `close_session`'s per-session expiry sweep and would silently produce
    false passes), and a human-approved+activated envelope SESSION-STAMPED TO
    MATCH IT (confirmed empirically: Sol's `envelope_owner_scope_reason`,
    app/store/core.py, requires `envelope.session_id == intent.session_id` as
    part of its owner-binding validation -- an envelope draft that omits it,
    same as the intent gap above, would misrepresent a correct implementation
    as broken). Returns (SellIntent, ExecutionEnvelope)."""

    await seed_position(store, symbol, quantity)
    session = await store.get_current_session()
    intent = await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=quantity,
        session_id=session.id,
    )
    draft_overrides.setdefault("session_id", session.id)
    envelope = await store.approve_envelope_activation(
        make_draft(intent.id, symbol=symbol, qty_ceiling=quantity, **draft_overrides),
        actor="operator-a",
    )
    return intent, envelope


async def submit_child(
    store, envelope, *, limit_price: float, quantity: int, now=T_NOW
):
    """Stage + submit a REAL live child order for `envelope` -- lands at
    OrderStatus.SUBMITTED, genuinely resting at the (simulated) venue, not a
    bookkeeping fiction. Returns the Order."""

    result = await store.stage_envelope_action(
        envelope.id,
        planned_submit(limit_price=limit_price, quantity=quantity),
        snapshot_fingerprint=f"fp-{envelope.id}-submit",
        now=now,
    )
    assert result.outcome == STAGE_STAGED, (
        "oracle fixture precondition failed: staging the initial SUBMIT did not "
        f"succeed (outcome={result.outcome!r}) -- not a property failure, a "
        "fixture-setup problem worth flagging in the campaign report if it recurs"
    )
    assert result.order is not None
    return await submit_created_order(store, result.order.id)


# =============================================================================
# CORE R2 PROPERTY -- see module docstring. Each test below is one boundary the
# charter names explicitly: session close, rollover, terminal-with-no-live-child,
# terminal-with-resting-child, supersession, flatten, kill/resume, masked
# predecessor.
# =============================================================================


async def test_no_orphan_at_session_close(any_store):
    """The headline R2 defect (AUDIT-0001 root R2 / WO-0036): base `close_session`
    blindly expires every PENDING/APPROVED sell intent with zero envelope
    awareness, orphaning a still-ACTIVE envelope (proven live behavior, pinned as
    accepted pre-fix fact by `tests/test_rev0023_phase_a2_pins.py::
    test_PIN_P0_no_two_active_envelopes_per_symbol_across_session_boundary`'s own
    comment: "expires si1, leaves the envelope ACTIVE (orphan)"). R2 must close
    this window: an envelope-backed intent survives session close as long as its
    envelope is non-terminal.
    """

    await any_store.initialize()
    intent, envelope = await open_mandate(any_store)

    await any_store.close_session()

    still_owned = await any_store.get_sell_intent(intent.id)
    assert still_owned is not None
    assert still_owned.status.value != "expired", (
        f"intent {intent.id} was silently EXPIRED at session close while its "
        f"envelope {envelope.id} is still {envelope.status.value} -- the R2 "
        "orphan (AUDIT-0001 root R2) is NOT closed"
    )
    assert (await any_store.get_envelope(envelope.id)).status is S.ACTIVE, (
        "session close must not itself freeze/terminate a running envelope "
        "(ADR-010 §4: envelopes keep running through an ordinary close; only "
        "Halted freezes them)"
    )
    assert await any_store.active_sell_intent_for("AAPL") is not None, (
        "symbol AAPL shows no owner immediately after close, while its "
        "envelope is still ACTIVE -- zero-owner-with-live-exposure window"
    )


async def test_activation_links_validates_and_normalizes_the_backing_intent(any_store):
    """WO-0036 Option A+, stated directly: `approve_envelope_activation` must
    LOAD the backing SellIntent, validate it exists and its symbol matches, and
    normalize PENDING -> APPROVED ("the envelope approval IS the human
    approval"). WO-0036 P1 #8 (independently confirmed real at tip): base
    `approve_envelope_activation` never loads the referenced SellIntent at
    all, so (a) the intent is left PENDING forever regardless of the
    envelope's fate, and (b) a mismatched/typo `sell_intent_id` or a
    symbol-mismatched intent would mint an ACTIVE mandate with no real owner.
    Both halves are tested directly here rather than only inferred from
    downstream symptoms.
    """

    await any_store.initialize()
    await seed_position(any_store, "AAPL", 100)
    session = await any_store.get_current_session()
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    assert intent.status.value == "pending"

    await any_store.approve_envelope_activation(
        make_draft(intent.id, symbol="AAPL", qty_ceiling=100, session_id=session.id),
        actor="operator-a",
    )

    normalized = await any_store.get_sell_intent(intent.id)
    assert normalized.status.value == "approved", (
        f"intent {intent.id} is still {normalized.status.value!r} after its "
        "envelope activated -- approve_envelope_activation must normalize "
        "PENDING -> APPROVED (WO-0036 Option A+: 'the envelope approval IS "
        "the human approval')"
    )

    # A mismatched/typo sell_intent_id (or a real intent for a DIFFERENT
    # symbol) must be REJECTED, not silently minted into an ACTIVE mandate
    # with no real owner (WO-0036 P1 #8).
    other_symbol_intent = await any_store.create_sell_intent(
        symbol="MSFT",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=10,
        session_id=session.id,
    )
    with pytest.raises(Exception):
        await any_store.approve_envelope_activation(
            make_draft(
                other_symbol_intent.id,
                symbol="AAPL",
                qty_ceiling=100,
                session_id=session.id,
            ),
            actor="operator-a",
        )
    with pytest.raises(Exception):
        await any_store.approve_envelope_activation(
            make_draft(
                "no-such-intent-id",
                symbol="AAPL",
                qty_ceiling=100,
                session_id=session.id,
            ),
            actor="operator-a",
        )


async def test_intent_released_when_envelope_completes_with_no_live_child(any_store):
    """The property's OTHER direction: once the exit obligation is genuinely
    discharged (full fill, no live child resting), the symbol MUST be released
    -- an implementation that closes the orphan bug by never releasing the
    intent (e.g. always keeping it non-terminal) is just as wrong as the
    original bug, and would permanently disable re-protection for the symbol
    (the exact class of failure INV-032/X-003 exists to prevent).
    """

    await any_store.initialize()
    intent, envelope = await open_mandate(any_store, quantity=50)

    completed = await any_store.record_envelope_fill(
        envelope.id, quantity=50, dedupe_key="fill:o1:x1", price=9.80, order_id="o1"
    )
    assert completed.status is S.COMPLETED
    assert completed.remaining_quantity == 0

    assert await any_store.active_sell_intent_for("AAPL") is None, (
        f"intent {intent.id} still shown as the AAPL owner after its envelope "
        "fully COMPLETED with no live child -- the symbol is stuck, blocking "
        "any future protective or manual exit for it"
    )
    # A fresh intent for the symbol must be genuinely obtainable now.
    fresh = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=1
    )
    assert fresh.id != intent.id, "symbol is still stuck on the old, discharged intent"


async def test_intent_stays_owned_while_child_rests_after_expiry_rest_at_floor(
    any_store,
):
    """Core property's SECOND disjunct: a terminal ENVELOPE does not always mean
    a discharged obligation. WO-0036 names REST_AT_FLOOR among the "releasing
    terminal" states that can leave a resting child. ADR-010 §2: REST_AT_FLOOR
    is a mandatory approval-time TTL disposition meaning the working order is
    explicitly LEFT resting, not cancelled, on expiry. A mechanism that treats
    "envelope left ACTIVE/FROZEN" as the ONLY live signal -- ignoring a still-
    resting order under a now-EXPIRED envelope -- would wrongly free the symbol
    while real venue exposure remains.
    """

    await any_store.initialize()
    intent, envelope = await open_mandate(
        any_store, expiry_disposition=EnvelopeExpiryDisposition.REST_AT_FLOOR
    )
    child = await submit_child(any_store, envelope, limit_price=9.60, quantity=100)
    assert (await any_store.get_order(child.id)).status is OrderStatus.SUBMITTED

    expired = await any_store.transition_envelope(
        envelope.id,
        S.EXPIRED,
        actor="system",
        reason="ttl_lapsed",
        now=T_NOW + timedelta(hours=3),
    )
    assert expired.status is S.EXPIRED

    # REST_AT_FLOOR means nobody touches the child on this transition.
    assert (await any_store.get_order(child.id)).status is OrderStatus.SUBMITTED, (
        "the child order changed status merely from the envelope's own EXPIRED "
        "transition -- REST_AT_FLOOR means it is left resting, untouched"
    )
    assert await any_store.active_sell_intent_for("AAPL") is not None, (
        f"symbol AAPL shows no owner even though order {child.id} is still "
        "SUBMITTED (resting) at the venue under a REST_AT_FLOOR expiry -- a "
        "masked release: real exposure with zero recorded owner"
    )

    # Once that order finally resolves (fill or cancel), the symbol releases.
    await any_store.transition_order(child.id, OrderStatus.CANCELED)
    assert await any_store.active_sell_intent_for("AAPL") is None, (
        "symbol AAPL still shows an owner after its last resting child "
        "resolved to CANCELED and its envelope is EXPIRED -- stuck symbol"
    )


async def test_supersession_does_not_release_the_intent(any_store):
    """WO-0036's Option A+ design is explicit: a FINAL terminal state release
    list is "COMPLETED/EXPIRED/EXHAUSTED/BREACHED/CANCELLED, NOT SUPERSEDED --
    the successor keeps the intent". A mechanism that treats ANY envelope
    leaving ACTIVE (including superseded-by-amendment) as a release signal
    would wrongly free the symbol mid-amendment, racing a concurrent creator
    into a second, conflicting intent for the same still-managed exit.
    """

    await any_store.initialize()
    intent, env1 = await open_mandate(any_store, quantity=100)

    successor = make_draft(
        intent.id, symbol="AAPL", qty_ceiling=90, session_id=env1.session_id
    )
    env2 = await any_store.supersede_envelope(
        env1.id, successor, actor="operator-a", reason="amendment"
    )
    assert (await any_store.get_envelope(env2.id)).status is S.ACTIVE
    assert (await any_store.get_envelope(env1.id)).status is S.SUPERSEDED

    assert await any_store.active_sell_intent_for("AAPL") is not None, (
        "symbol AAPL shows no owner immediately after a same-intent "
        "supersession -- SUPERSEDED must not be treated as a release signal"
    )
    active_envs = [
        e for e in await any_store.list_envelopes(symbol="AAPL") if e.status is S.ACTIVE
    ]
    assert len(active_envs) == 1 and active_envs[0].id == env2.id


async def test_kill_freeze_release_resume_never_opens_a_window(any_store):
    """FROZEN is explicitly in the charter's LIVE set (`LIVE = {ACTIVE, FROZEN}`
    in both attempts' summaries). Engaging the kill switch, releasing it
    (INV-080: release never auto-resumes a frozen envelope), and an explicit
    human resume must never pass through a window where the symbol shows zero
    owner -- kill-switch engagement must not be usable as an accidental
    side-channel to free a symbol still under an unresolved mandate.
    """

    await any_store.initialize()
    intent, envelope = await open_mandate(any_store)

    await any_store.set_kill_switch(True, actor="operator-a")
    assert (await any_store.get_envelope(envelope.id)).status is S.FROZEN
    assert await any_store.active_sell_intent_for("AAPL") is not None, (
        "symbol AAPL shows no owner while its envelope is FROZEN (still LIVE)"
    )

    await any_store.set_kill_switch(False, actor="operator-a")
    assert (await any_store.get_envelope(envelope.id)).status is S.FROZEN, (
        "INV-080: releasing the kill switch must never auto-resume a frozen envelope"
    )
    assert await any_store.active_sell_intent_for("AAPL") is not None

    resumed = await any_store.transition_envelope(
        envelope.id, S.ACTIVE, actor="operator-a"
    )
    assert resumed.status is S.ACTIVE
    assert await any_store.active_sell_intent_for("AAPL") is not None


async def test_flatten_defers_to_live_envelope_child_never_double_books(any_store):
    """WO-0036 #4: base `flatten_position` only recognizes an already-live exit
    via the intent's OWN `order_id`, which is structurally always None for an
    envelope-backed intent (envelope children are minted by the envelope
    executor, never linked back onto `SellIntent.order_id`). So base flatten
    cannot see the live envelope child and blindly mints an independent fresh
    `manual_flatten` SELL order -- two live SELLs against one position. R2 must
    make flatten recognize the envelope's live child as an already-discharged
    (or already-being-discharged) exit obligation for the symbol.
    """

    await any_store.initialize()
    intent, envelope = await open_mandate(any_store, quantity=100)
    child = await submit_child(any_store, envelope, limit_price=9.60, quantity=100)

    result = await any_store.flatten_position("AAPL", actor="operator-a")

    assert result.outcome != "created", (
        f"flatten minted an independent fresh manual_flatten order while "
        f"envelope {envelope.id}'s own child order {child.id} was still "
        f"{(await any_store.get_order(child.id)).status.value} at the venue "
        "-- double exposure against one position (WO-0036 #4)"
    )


async def test_masked_predecessor_keeps_intent_owned(any_store):
    """WO-0036 finding #6: a reprice REPLACEMENT that is itself rejected at the
    venue (without cancelling the predecessor) leaves the OLD order as the true
    live child. The newest order ROW looks terminal (REJECTED), but real
    exposure still rests at the venue under the predecessor. The core
    property's second disjunct must be evaluated against the actual live
    order, not merely "the newest one for this envelope" -- a mechanism that
    naively looks at only the newest child would wrongly free the symbol.
    """

    await any_store.initialize()
    intent, envelope = await open_mandate(any_store, quantity=100)
    predecessor = await submit_child(
        any_store, envelope, limit_price=9.60, quantity=100
    )

    reprice = await any_store.stage_envelope_action(
        envelope.id,
        planned_submit(kind=ActionKind.REPRICE, limit_price=9.65, quantity=100),
        snapshot_fingerprint="fp-reprice-1",
        now=T_NOW + timedelta(seconds=5),
    )
    if reprice.outcome != STAGE_STAGED or reprice.order is None:
        pytest.skip(
            "oracle fixture could not stage a REPRICE to construct the masked-"
            f"predecessor scenario (outcome={reprice.outcome!r}) against this "
            "store -- flag in the campaign report rather than asserting a "
            "property the fixture never actually exercised"
        )
    replacement = reprice.order
    await any_store.claim_order_for_submission(replacement.id)
    await any_store.transition_order(replacement.id, OrderStatus.REJECTED)

    assert (
        await any_store.get_order(predecessor.id)
    ).status is OrderStatus.SUBMITTED, (
        "oracle fixture assumption broken: the predecessor was touched by the "
        "rejected replacement's own transition -- not a property failure"
    )
    assert await any_store.active_sell_intent_for("AAPL") is not None, (
        f"symbol AAPL shows no owner even though predecessor order "
        f"{predecessor.id} is still SUBMITTED (live) at the venue -- a masked "
        "predecessor (WO-0036 #6) silently reopened dedup while real exposure "
        "remains"
    )


# =============================================================================
# SAFETY-RAIL REGRESSION GUARDS (charter §3 "safety-rail obligations") -- these
# confirm R2's intent-linkage changes did not regress pre-existing invariants
# that were already correct pre-R2. Not new R2 properties; a failure here means
# an attempt broke something unrelated while fixing R2.
# =============================================================================


async def test_inv087_still_at_most_one_active_envelope_per_symbol(any_store):
    """INV-087 regression guard (pre-R2 invariant; WO-0032). Two different real
    intents for the same symbol must still never both back an ACTIVE envelope.
    """

    await any_store.initialize()
    await seed_position(any_store, "AAPL", 100)
    session = await any_store.get_current_session()
    intent_a = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=50,
        session_id=session.id,
    )
    await any_store.approve_envelope_activation(
        make_draft(intent_a.id, symbol="AAPL", qty_ceiling=50, session_id=session.id),
        actor="operator-a",
    )
    active = [
        e for e in await any_store.list_envelopes(symbol="AAPL") if e.status is S.ACTIVE
    ]
    assert len(active) == 1


async def test_envelope_bounds_still_immutable_after_r2(any_store):
    """INV-078 regression guard: no store exposes a bound-update path; amendment
    is supersession-only. R2's intent-linkage change must not have added one
    (e.g. a "relink to a different intent" shortcut on the same row).
    """

    await any_store.initialize()
    intent, envelope = await open_mandate(any_store, quantity=100)
    before = await any_store.get_envelope(envelope.id)
    assert not hasattr(any_store, "update_envelope_bounds"), (
        "a bound-mutation method appeared on the store -- ADR-010 §3 requires "
        "amendment-by-supersession only"
    )
    after = await any_store.get_envelope(envelope.id)
    assert after.qty_ceiling == before.qty_ceiling
    assert after.sell_intent_id == intent.id, (
        "an envelope's owning intent must never be re-pointed in place"
    )


async def test_only_deduped_fills_still_move_remaining_quantity(any_store):
    """INV-076 regression guard: R2's new terminal-transition/projection logic
    must not have introduced a second writer of `remaining_quantity`."""

    await any_store.initialize()
    _, envelope = await open_mandate(any_store, quantity=100)
    before = (await any_store.get_envelope(envelope.id)).remaining_quantity
    await any_store.transition_envelope(envelope.id, S.FROZEN, actor="operator-a")
    await any_store.transition_envelope(envelope.id, S.ACTIVE, actor="operator-a")
    after = (await any_store.get_envelope(envelope.id)).remaining_quantity
    assert after == before, (
        "a non-fill transition moved remaining_quantity (INV-076 violation)"
    )


# =============================================================================
# DEFERRED CLASS-CLOSURE ITEMS -- charter §3 names these; they need real
# monitoring-tick orchestration (differs materially between the two attempts,
# see module docstring) rather than the StateStore contract alone. Recorded as
# NEEDS-INPUT, not silently dropped; exercised directly in the campaign
# report's §C/§E against each attempt's own tick code instead.
# =============================================================================


@pytest.mark.skip(
    reason="NEEDS-INPUT: requires driving app.monitoring._redrive_stale_submitting "
    "against a real stale SUBMITTING envelope order under R2's new intent-linkage "
    "state; store-level harness cannot exercise the tick. See campaign report §C/§E."
)
async def test_stale_submitting_redrive_respects_r2_intent_linkage(any_store):
    raise NotImplementedError


@pytest.mark.skip(
    reason="NEEDS-INPUT: requires simulating a crash between claim_order_for_submission "
    "and the broker ack for an envelope child, then driving the real recovery/redrive "
    "path -- tick-level, not store-contract-level. See campaign report §C/§E."
)
async def test_claim_venue_crash_recovery_respects_r2_intent_linkage(any_store):
    raise NotImplementedError


@pytest.mark.skip(
    reason="NEEDS-INPUT: 'monitoring-side newest-wins convergence' is one of the four "
    "items Claude's REV-0028 packet ratified/disclosed (charter §6) -- requires reading "
    "monitoring.py's fold logic for both attempts directly, not a store-level property. "
    "See campaign report §E (adversarial cross-verification)."
)
async def test_monitoring_newest_wins_convergence_respects_r2_intent_linkage(any_store):
    raise NotImplementedError
