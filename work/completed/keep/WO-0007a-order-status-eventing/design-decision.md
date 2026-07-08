---
work_order: WO-0007a
title: Order-status ExecutionEvent emission — final design decision (from Understand-phase evidence)
date: 2026-07-08
status: DESIGN — adversarially reviewed (workflow wf_3f5aca5a-602); corrections incorporated below; ready for TDD implementation
---

# WO-0007a — design decision

Synthesized from a 5-agent parallel recon pass (transition semantics, test-coverage risk, exact
current code at every touch point, the dual-store parity mechanism, and an independent INV-9
safety re-audit). Full agent reports: see workflow run `wf_9f652d7f-348` journal. Then pressure-tested
by a 3-agent adversarial design-review pass (workflow `wf_3f5aca5a-602`) — see "Design-review findings
incorporated" below for what that pass found and how this doc was corrected as a result.

## Key facts established

1. **`ORDER_TRANSITIONS` graph is a DAG with exactly one cycle**: `CREATED ⇄ SUBMITTING` (claim
   forward via `plan_claim_order_for_submission`; `SUBMITTING → CREATED` release-on-transient-failure
   via the generic `transition_order`). Every other status, traced exhaustively (independently
   re-derived and confirmed by adversarial review — SCC/condensation argument, not assertion), is
   reachable **at most once per order** — `TIMEOUT_QUARANTINE`, `SUBMITTED`, `FILLED`, `CANCELED`,
   `REJECTED` are all true one-shot destinations (no path leads back to them or past them; `TIMEOUT_QUARANTINE`
   was omitted from this list in an earlier draft — flagged by review, added here for completeness,
   it does not change any conclusion since it was already excluded from the new routine mapping).
   The only **self-loops** are `PARTIALLY_FILLED→PARTIALLY_FILLED` and `CANCEL_PENDING→CANCEL_PENDING`
   (repeated partial fills / late fill-progress while pending cancel).
2. **`plan_transition_order`'s same-status branch is NOT a no-op when `filled_quantity` changes** — it
   writes an `order_fill_progress` audit event (not `order_transition`), monotonic `filled_quantity`
   guaranteed by an existing bound-check. Today neither branch touches `execution_events` — only the
   separate **evented** path (`plan_transition_order_evented`, used only by TIMEOUT_QUARANTINE
   quarantine/resolve and reconcile-not-found) does.
3. **No function derives `Order.filled_quantity` from folding FILL events** (unlike `Position`, which
   is a pure FILL-event fold). `filled_quantity` is a store-set field today. WO-0007a does not change
   this — it only adds order-status-lifecycle events; it does not attempt to make `filled_quantity`
   event-sourced (that's a WO-0007b/projector-era decision).
4. **INV-9 independently re-confirmed PASS**: every reader of `execution_events` was enumerated
   (15 call sites across `projectors.py`/`replay.py`/both stores); every position-deriving path
   filters strictly to `ExecutionEventType.FILL` (`projectors.py:129,377`, plus SQL-level
   `WHERE event_type='fill'` pre-filters in sqlite). New non-FILL event types cannot reach position.
   Residual code-review obligation (not a defect): any new fold code added must keep this filter.
5. **`_EXECUTION_EVENT_FOR_RESOLVED_STATUS`'s key format `f"{new_status.value}:{order.id}"` is safe to
   REUSE for the routine path's terminal-ish statuses** — CORRECTED by adversarial review: an earlier
   draft of this doc claimed `_RECONCILE_RESOLVE_EXEC` uses the *same* format too; it does not
   (`plan_reconcile_resolve_order` actually uses `f"reconcile_resolve:{order.id}:{new_status.value}"`,
   `core.py:1693`) — an unverified claim that happened to be harmless (different formats can't collide
   regardless) but should not have shipped as a "verified" fact. The real safety argument, precisely
   stated: for a given order, at most ONE of {routine `transition_order`, TQ-resolution, reconcile-
   resolution} ever succeeds in writing a given terminal status, because (a) each terminal status is
   graph-reachable at most once (item 1), AND (b) every current call site that could write toward that
   status re-checks the order's CURRENT status immediately beforehand (e.g. the routine ack-handling
   call sites in `monitoring.py` only fire when status is `SUBMITTING`, which a TQ-resolved order no
   longer is). Point (b) is a call-site discipline property, not a pure graph-structure guarantee — a
   future refactor that called generic `transition_order(order, SUBMITTED)` on a `TIMEOUT_QUARANTINE`
   order (legal per `ORDER_TRANSITIONS[TIMEOUT_QUARANTINE]`) would collide with `plan_resolve_timeout_quarantine`'s
   identical key. **Mitigation added to the design** (see "Decision: mapping + dedupe-key scheme"):
   the new routine-mapping helper explicitly asserts the order is NOT `TIMEOUT_QUARANTINE` before
   constructing a shared-format key, so this is enforced in code, not just argued in a doc.
6. **Test-coverage risk is low**: of 14 test files referencing `execution_events`, none drives an
   order through the real routine pipeline AND asserts an unscoped exact count. One near-risk pattern
   flagged (`test_spine_phase3c_timeout_quarantine.py::test_resolve_to_submitted_requires_broker_id_then_clears`,
   an unscoped store-wide `SUBMITTED` count) is safe only because that test's one order never reaches
   SUBMITTED via the routine path — will be re-verified with a fresh full-suite run, not just trusted.

## Decision: scope (Fable Law 4 — stay inside the WO's literal required-behavior list)

WO-0007a's Required Behavior names exactly 5 transition families: **claim, ack, fill-driven,
normal cancel, definitive reject.** It does not name `CANCEL_PENDING` or the `SUBMITTING→CREATED`
release. Rather than unilaterally expanding scope (which is also where the only cycle and the least
common edge cases live), this WO implements exactly the 5 named families and explicitly documents
`CANCEL_PENDING` (entry + self-loop) and the release edge as **out of scope, residual gap for
WO-0007b or a follow-up** — the same "log it, don't silently fix or silently skip it" discipline
used throughout this session's audits.

**Scope correction from adversarial review (incorporated, not deferred):** two independent review
agents found that "normal cancel" is NOT fully covered by patching `transition_order` alone — two
real, mainstream (not edge-case) code paths write `order.status = CANCELED` directly, bypassing
`transition_order`/`claim_order_for_submission` entirely, with only an audit event, never an
`execution_events` write:
- `plan_close_session`'s cancellation of still-`CREATED` BUY orders on session close
  (`core.py:1758-1769`; applied `memory.py:1990-1994`, `sqlite.py:~3060-3071`).
- `plan_flatten_position`'s supersede-cancel branch (a stranded `CREATED` order canceled when a
  manual flatten creates its replacement exit) (`core.py:1051-1072`; applied `memory.py:953-961`,
  `sqlite.py:1640-1657`).

Unlike `CANCEL_PENDING` (a genuinely rare intermediate state few orders enter), session close and
manual flatten are common, safety-relevant flows — leaving them uncovered would mean a meaningful
fraction of real cancellations show `orders.status == CANCELED` with **zero** corroborating event,
directly undermining WO-0007a's own stated purpose (closing the reconstructability gap for
WO-0007b). This is therefore **brought into scope**, not logged as a residual gap: both apply blocks
(both stores) are extended to also construct+append the SAME `CANCELED` execution event
(`f"canceled:{order_id}"` — safe to share: `CANCELED` is terminal, so whichever of the three writers
— `transition_order`, `plan_close_session`, `plan_flatten_position` — reaches it first for a given
order, the other two structurally cannot also reach it, per item 1).

## Decision: mapping + dedupe-key scheme

New helper in `app/store/core.py` (NOT touching `plan_transition_order`'s signature/behavior — the
existing pure planner stays untouched to avoid re-risking its large existing test surface; the new
execution-event construction is an ADDITIONAL step the store takes after a successful APPLY):

```python
_EXECUTION_EVENT_FOR_ROUTINE_STATUS: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: ExecutionEventType.PARTIALLY_FILLED,
    OrderStatus.FILLED: ExecutionEventType.FILLED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
}
```

| Transition | ExecutionEventType | dedupe_key | Why safe |
|---|---|---|---|
| `CREATED→SUBMITTING` (claim) | `SUBMIT_PENDING` (existing, currently-dead vocabulary — perfect semantic fit) | `f"submit_pending:{order_id}:{n}"`, `n` = count of prior `SUBMIT_PENDING` execution events for this order_id | Only transition that can repeat (the one cycle); `n` disambiguates each repeat |
| `→SUBMITTED` (any source) | `SUBMITTED` (existing, shared w/ TQ/reconcile-resolution) | `f"submitted:{order_id}"` — **same format as existing evented callers** | At-most-once per order; mutually exclusive with the evented callers producing the same status |
| `→PARTIALLY_FILLED` (first entry, status-changed) | `PARTIALLY_FILLED` (existing, dead vocabulary) | `f"partially_filled:{order_id}"` | First entry is at-most-once (self-loop handled separately below) |
| `→FILLED` (any source) | `FILLED` (existing, dead vocabulary) | `f"filled:{order_id}"` | Terminal, at-most-once |
| `→CANCELED` (direct, not via CANCEL_PENDING) — via `transition_order`, `plan_close_session`, or `plan_flatten_position`'s supersede branch | `CANCELED` (existing, shared w/ TQ/reconcile) | `f"canceled:{order_id}"` | Terminal, at-most-once across ALL THREE writers (confirmed by adversarial review — see scope correction above) |
| `→REJECTED` (direct, not via TQ) | `REJECTED` (existing, shared w/ TQ/reconcile) | `f"rejected:{order_id}"` | Terminal, at-most-once, shared-key-safe |
| `PARTIALLY_FILLED→PARTIALLY_FILLED` (fill progress, same status) | `PARTIALLY_FILLED` (reused) | `f"order_fill_progress:{order_id}:{filled_quantity}"` | `filled_quantity` is monotonically increasing (bound-checked) — guaranteed distinct per repeat |

**Out of scope, documented (not implemented in WO-0007a):** `CANCEL_PENDING` entry/self-loop;
`SUBMITTING→CREATED` release. An order that transits through `CANCEL_PENDING` still gets its final
terminal event (via the `→CANCELED`/`→FILLED`/`→REJECTED` rules above, which key only on the
resulting status, not the prior one) — only the *intermediate* `CANCEL_PENDING` state itself goes
unrecorded in the execution-event log for now.

## Decision: where the code changes (surgical, not touching the pure planners)

- `app/store/core.py`: add `_EXECUTION_EVENT_FOR_ROUTINE_STATUS` + a new pure helper
  `execution_event_for_routine_transition(order, new_status, filled_quantity, occurrence=None) -> Optional[ExecutionEvent]`
  that returns `None` when the status isn't in the map and it's not the fill-progress case (so the
  store can call it unconditionally and just skip appending if `None`). **Defense-in-depth (from
  review Finding D):** this helper asserts `order.status is not OrderStatus.TIMEOUT_QUARANTINE`
  before constructing a `submitted:`/`canceled:`/`rejected:` shared-format key — cannot happen today
  (item 5), but enforces the invariant in code rather than leaving it as doc-only reasoning that a
  future refactor could silently violate.
- `app/store/memory.py` / `app/store/sqlite.py`: in `transition_order` and `claim_order_for_submission`,
  after a successful APPLY/CLAIMED outcome, call the new helper and — if it returns an event — append
  it via the EXISTING `_append_execution_event_unlocked`/`_insert_execution_event` primitives, inside
  the SAME atomic block as the order-row + audit-event write (mirroring `_apply_order_evented_plan_locked`'s
  pattern exactly, per Map-C item 9).
- **Additional touch points (scope correction above):** the `plan_close_session` apply block
  (`memory.py:1990-1994`, `sqlite.py:~3060-3071`) and the `plan_flatten_position` supersede-cancel
  apply block (`memory.py:953-961`, `sqlite.py:1640-1657`) — both extended identically: call the same
  helper with `new_status=CANCELED`, append the resulting event in the same atomic block as their
  existing order-row + audit-event write.
- `app/models.py`: no new enum members needed — `SUBMIT_PENDING`, `PARTIALLY_FILLED`, `FILLED` were
  declared-but-dead; this WO is their first live emission. `SUBMITTED`/`CANCELED`/`REJECTED` already live.
- `orders.status` remains authoritative — no read path changes. This is purely additive.
- **Explicit test requirement (from review Task 3):** a dedicated test that drives an order through
  claim → release (`SUBMITTING→CREATED`) → re-claim at least twice, asserting the resulting
  `SUBMIT_PENDING` execution events are gapless, uniquely keyed (`n=0,1,2,...`), and both appear in
  `get_execution_events()` — not just implied by "mirrors the existing pattern."
- **Documented, not code-changed:** the in-tick ordering between `_reconcile_open_orders` and
  `_resolve_reconcile_not_found` (both can target `SUBMITTED`/`PARTIALLY_FILLED`→terminal in the same
  monitoring tick) is safe because `_reconcile_open_orders` always runs first and the not-found
  resolver re-fetches + re-checks status before acting — confirmed by review, no change needed, noted
  here so a future reader doesn't have to re-derive it. Historical orders already mid-lifecycle before
  this WO's deploy will have an incomplete event trail for legs completed pre-deploy (consistent with
  "first live emission" framing) — informational, not a defect.

## Design-review findings incorporated (workflow `wf_3f5aca5a-602`, 3 agents, all completed clean)

| Finding | Severity | Disposition |
|---|---|---|
| `plan_close_session` + `plan_flatten_position` bypass `transition_order`, write CANCELED with no execution event | Real gap, found independently by 2 of 3 agents | **Brought into scope** — see scope correction + updated touch-points above |
| Item 1's "one-shot" list omitted `TIMEOUT_QUARANTINE` | Doc-completeness only, no correctness impact | Fixed in item 1 |
| Item 5 claimed `_RECONCILE_RESOLVE_EXEC` shares `_EXECUTION_EVENT_FOR_RESOLVED_STATUS`'s key format | Factual error, harmless in effect (unverified claim) | Corrected in item 5; real safety argument restated precisely |
| "Mutually exclusive by graph shape" was imprecise (relies on call-site discipline too) | Justification-precision, no correctness impact today | Restated in item 5; defense-in-depth guard added to the helper |
| Occurrence-count concurrent-claim safety | Confirmed safe (lock/atomicity traced against actual code) | No design change; added as an explicit test requirement |
| In-tick `_reconcile_open_orders` vs `_resolve_reconcile_not_found` ordering | Confirmed safe (execution order + fresh-status re-check) | Documented above, no code change |
| No backfill story for pre-deploy order legs | Informational | Documented above, no code change |
| mypy self-check in original verification plan | Moot — WO-0008 (already merged) grandfathers `app/store/*` in the mypy ratchet | No change needed |

Cycle/self-loop/one-shot graph claims (item 1) were independently re-derived from scratch by a
blind agent and matched exactly (net of the `TIMEOUT_QUARANTINE` completeness fix above). Per-row
dedupe-key collision analysis: 6 of 7 original rows CONFIRMED-SAFE outright; the 7th (`→CANCELED`)
had the coverage gap above, now closed by scope extension rather than a key-scheme change.

## Verification plan before claiming done

1. ~~Adversarial design-review pass~~ — DONE, findings incorporated above.
2. TDD implementation (RED before GREEN) per transition family, both stores, full suite green after each.
3. New dual-store parity test for the emitted order-status stream (extends `verify_dual_store_parity`-
   style testing, not the projector itself — no projector exists yet, per WO-0007a scope).
4. Adversarial verify pass on the resulting diff: INV-9, dedupe/idempotency, dual-store parity,
   scope (allowed/forbidden paths), test-integrity (nothing weakened).
5. My own fresh `git diff` review + `ruff check .` + `mypy app/` + full `pytest -q` before any DONE claim.

## Implementation & verification outcome (post-build)

**Fresh evidence (my own run, working tree on `chore/ai-os-install`, base `d52c6d0`):**
`ruff check .` → all checks passed. `python -m mypy app/` → Success, no issues in 54 files. Full
`pytest` (JUnit XML, this env suppresses the terminal summary line) → **1857 collected, 1852 passed,
5 skipped, 0 failed, 0 errors**, 120.8s. Diff confined to `app/store/{core,memory,sqlite}.py` +
new `tests/test_wo0007a_*.py`; the pure planners `plan_transition_order`/`plan_claim_order_for_submission`
are untouched.

**Adversarial verify pass (workflow `wf_15570028-93a`, 5 independent skeptics, each tasked to REFUTE
one safety claim):** INV-9 (position untouched), dedupe/idempotency (no reachable key collision — the
append primitives silently no-op on a duplicate dedupe_key, so a collision *would* be a silent drop;
none is reachable), dual-store parity (both stores delegate to the one pure helper; the sqlite
occurrence COUNT runs after the audit-event insert but that writes the `events` table, not
`execution_events`, so `n` is identical), scope/test-integrity, and the provenance judgment call — see
verdicts recorded in the ledger/close notes.

### Finding incorporated post-build (adversarial-verify): TIMEOUT_QUARANTINE consumer

The INV-9 skeptic surfaced that the WO-0007a event types `SUBMITTED`/`CANCELED`/`REJECTED`/`FILLED`
are members of `projectors.py::_ORDER_LIFECYCLE_EVENT_TYPES`, which `timeout_quarantined_order_ids`
folds (latest-wins, per `order_id`) to derive the currently-quarantined set — consumed by
`list_timeout_quarantined_orders` **and the INV-3 emergency-reduce gate** (`memory.py:1936` /
`sqlite.py:2996`, which refuses an emergency reduce while an ambiguous quarantined order is unresolved).
So WO-0007a's new routine emissions feed a **safety-relevant, reconciliation-adjacent** derivation.

Correctness is **preserved** (output of `timeout_quarantined_order_ids` unchanged), by a structural
argument: from `TIMEOUT_QUARANTINE` the only legal transitions are `{SUBMITTED, REJECTED, CANCELED}`
(`app/transitions.py:73-83`), and those three are exactly the helper's `_SHARED_FORMAT_KEY_STATUSES`,
which the defense-in-depth guard refuses to event for a TQ order; `FILLED` (the one lifecycle type the
guard does not cover) is **illegal from TQ**, hence unreachable via the routine path. The two
CREATED-order cancel writers (session close, flatten supersede) select only `CREATED` orders, never a
TQ one. Therefore no routine emission can flip a quarantined order out of the set, and per-`order_id`
latest-wins means other orders' new lifecycle events never leak across. Pinned by a new regression test
`tests/test_wo0007a_quarantine_consumer_unaffected.py` (both stores).

**Residual doc-staleness (flagged, NOT fixed here — out of `app/store/**` scope):** the docstring of
`app/events/projectors.py::timeout_quarantined_order_ids` still states "Only the wave-3c evented
transitions emit these order-lifecycle events." WO-0007a makes that clause false (the routine path now
emits them too); the function's *output* is unchanged, but the stated *rationale* is stale. Recommend a
one-line docstring fix in a WO-0007b-era or a tiny follow-up touching `app/events/` — surfaced to the
human rather than silently expanding this WO's scope.

### Provenance (source/authority) decision — the one substantive judgment call

The design doc above was silent on `source`/`authority`. The implementation stamps every routine
order-status event `EventSource.ENGINE` / `EventAuthority.LOCAL`. This is a **deliberate conservative
choice**, documented in code at the helper: correct for the genuinely engine-local transitions (claim,
and the two CREATED-order cancels); a **safe under-claim** for the broker-observed statuses
(`SUBMITTED`/`PARTIALLY_FILLED`/`FILLED`/`REJECTED`), which the codebase convention
(`execution_event_for_fill`, `plan_resolve_timeout_quarantine`, `plan_reconcile_resolve_order`) would
label `BROKER_REST`/`BROKER_AUTHORITATIVE`. Under-claiming is the safe direction —
`BROKER_AUTHORITATIVE` is the conflict-WINNING authority (ADR-001), so it can never let an
engine-echoed status wrongly override a real broker reconciliation; over-claiming could. No consumer
reads source/authority off these events today (no projector; `orders.status` stays authoritative), so
the under-claim is functionally inert now. **Faithful per-transition broker provenance is deferred to
WO-0007b** (it needs a source/authority argument threaded from the monitoring callers — outside this
WO's `app/store/**` scope — and is only meaningful once WO-0007b's projector consumes it). Flagged to
the human as the one design judgment that borders event-log-truth semantics.
