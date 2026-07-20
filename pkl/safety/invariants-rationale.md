---
type: Project Rule
title: Safety Invariants — Rationale
status: active
authority: high
owner: Ameen
last_verified: 2026-07-19
tags: [safety, invariants, trading]
source_refs: [docs/SPINE_EXECUTION_ARCHITECTURE_v2.md, docs/adr/ADR-001-overfill-quarantine.md, docs/adr/ADR-002-timeout-quarantine.md, docs/adr/ADR-003-manual-flatten-halted-reducing.md, docs/adr/ADR-008-order-status-event-provenance.md, docs/adr/ADR-010-execution-envelope.md]
supersedes: []
superseded_by: null
---

# Safety Invariants — Rationale

## Summary

The 11 invariants and safety rails live **verbatim in `CLAUDE.md`** so they are always in agent context — deliberately not one indirection away. This page holds the *why*, so the shim stays short.

## Rules / facts

- The normative text is `CLAUDE.md` "Safety core". This page never overrides it; on any divergence, `CLAUDE.md` wins and this page gets fixed.
- Why each cluster exists:
  - **Paper-only / live-disabled (inv 1–2):** the beta's blast radius must be zero real dollars. Live paths aren't "unused"; they're absent-by-config so an agent cannot accidentally enable them.
  - **Backend as truth, thin UI (inv 3–7):** a browser client that owns state or talks to the broker is an unauditable second writer. All mutation flows through one reviewable engine.
  - **Submitted ≠ filled; only fills move positions (inv 8–9):** the classic execution bug is counting intent as reality. Structural inability of `SUBMITTED`/`ACCEPTED` to change quantity makes the bug unrepresentable.
  - **Kill switch gates intent (inv 10):** halting must cut new risk at the front door, not race the pipeline.
  - **Quarantine over rejection (rails; ADR-001/002):** broker reality (overfills, ambiguous timeouts) must be recorded even when unwelcome — hiding it corrupts positions. Deterministic `client_order_id` makes reconciliation possible; blind resubmit makes duplicates possible.
  - **Broker-overfill truth (ADR-001):** broker order/envelope excess retains raw fill/position
    truth, caps only the compatibility Order progress scalar, and atomically latches explicit
    `QUARANTINED` truth even while net position remains positive. Exact identity replay is a no-op
    only when its economics match; conflicting reuse is audited, dropped, and held for manual review.
  - **Manual flatten routing (ADR-003):** an emergency control that bypasses risk checks and logging is itself a hazard; the override exists but is explicit and audited.
  - **WO-0113 governance status:** the operator ratified YES the following capability,
    CREATED-exposure, accepted-submit, protection-deferral, and attribution behavior on 2026-07-19;
    REV-0033 independent review remains required.
  - **Capability-bound emergency override:** an active override grant is durable scope, not ambient
    permission. Only the explicit emergency command passes the internal capability to flatten;
    ordinary flatten/exit callers remain blocked while halted and cannot consume the grant. A
    fail-closed retry revalidates halted/position/quarantine preconditions and reuses, rather than
    stacks, the active grant; the first authorized exit resolves it. Grant, intent, order, and
    resolution stay bound to the same lock-held session; explicit foreign session scope is refused.
    The scoped reducing authorization does not lift the global composed HALTED state.
  - **CREATED is not proof of venue absence:** event-projected `CREATED` means no active local
    submission claim. A local cancel additionally requires no broker id, no unresolved or
    needs-review recovery, and no accepted-submit fallback for that order. The deliberate exclusion of CREATED from the may-execute
    set is compensated at both ends: exit admission/dispatch stands down safely local CREATED BUYs,
    and submission claim rechecks opposing exposure before any venue call. Cached
    `filled_quantity` is not part of that local-only proof. A concrete broker id on projected
    CREATED remains venue exposure at every SELL choke point.
  - **Accepted-submit ownership survives partial persistence:** an audit seed normally preserves
    the exact `(local order, broker order)` identity. Whenever recovery ownership cannot be
    written, an `UNKNOWN_RECONCILE_REQUIRED` execution fact is the last durable owner whether or
    not that audit already succeeded, and remains venue exposure until repair. Exact UNKNOWN or
    open-recovery accepted BUY exposure contributes remaining CAPI once per exact broker identity;
    distinct acceptances are additive, known fills allocate once, and malformed numeric scope
    cannot shrink immutable referenced-order exposure. A CREATED order with its own broker id or
    fallback fact cannot be claimed again; an accepted direct SELL also remains same-side
    single-flight ownership and cannot be locally canceled. Every durable boundary canonicalizes
    broker-id transport whitespace. Order, recovery, and canonical-fallback representations for
    the same local/id pair coalesce; one local order may own multiple distinct concrete recovery
    legs. Mutable order/recovery assignments keep each concrete broker id exclusive to one local;
    conflicting append-only fallback truth is retained as evidence, cannot be rebound, blocks
    progress, and fails SQLite restart closed. Every leg is polled and resolved independently.
    Venue acknowledgements/targeted lookups must echo the requested client id, status polls must
    echo the requested broker id, and id-less mass-reconcile fallback additionally requires exact
    symbol/side. Cancellation cannot abandon a possibly accepted send: shielded ownership
    finalization completes before cancellation propagates. The fallback itself blocks stale redrive before
    repair. Blank post-call broker identity is quarantined as ambiguity rather than released as a
    preflight rejection. Routine reads select accepted facts without decoding
    unrelated UNKNOWN history, project CAPI order lifecycle from event truth, and skip
    checkpoint-only repair transport so idle consumers converge. Startup/reconnect must successfully establish
    the reconcile-driver REDUCING gate even when composed state was already HALTED. A failed
    planned inferred-fill lookup/append cannot be called parity: the verified REDUCING gate stays
    in force and same-tick venue work stops. Repair makes no broker call.
  - **Durable exact venue scope:** the final gapless submit/reprice claim writes one authenticated
    `VENUE_ORDER_SCOPE` before the broker call. It captures the exact client/owner identity,
    symbol/side/quantity, rendered type/price, TIF/class, asset and quantity mode,
    extended-hours decision, and replacement predecessor. Restart replays this scope instead of
    re-deriving session-sensitive intent. Direct, targeted, recovery, and mass consumers validate
    the same wire contract; managed mass rows cannot hide fractional cumulative fill, advanced
    order material, or contradictory replacement lineage. The injected decision clock selects
    new session scope, and broker overfill remains ADR-001 truth rather than a correlation reject.
  - **Append-only envelope attribution repair:** a canonical FILL is immutable and remains the sole
    position-quantity fact. If its envelope bridge was missed, a globally deduped
    `ENVELOPE_FILL_ATTRIBUTED` marker may apply that exact pre-existing fill to one uniquely bounded
    envelope. The marker validates fill/order/owner identity and the entire contiguous
    remaining-quantity chain, never folds position again, and conflicts rather than guessing when
    existing truth is malformed or foreign. Cadence validates direct-attributed facts too; its
    durable tail checkpoint advances only after a clean batch and never on error.
  - **Fail-fast market data:** garbage quotes driving sizing is a silent capital risk; halting is the safe failure mode.
- Human-gated surfaces (order submission, cancel/replace, kill switch, flatten, mode config, migrations, event-log truth, deletions of tests/docs/ADRs) exist because LLM auto-approval hooks optimize for flow, and flow is the wrong objective on these surfaces.

## Rationale

Safety rules survive by being cheap to obey and expensive to miss. Keeping them always-on in the shim, with rationale here, optimizes both.

## Applies to

- Everything.

## Related pages

- `CLAUDE.md` (normative text)
- `pkl/architecture/architecture-map.md`

## Change log

- 2026-07-07: Created.
- 2026-07-19: WO-0113 distilled session-bound emergency reduction, recovery/broker-identity-aware
  CREATED exposure, durable accepted-submit fallback ownership, non-maskable reconciliation
  gating, and contiguous/checkpointed append-only envelope attribution repair. Final WO
  implementation SHA pending close-out.
