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
  - **Manual flatten routing (ADR-003):** an emergency control that bypasses risk checks and logging is itself a hazard; the override exists but is explicit and audited.
  - **WO-0113 governance status:** the following capability, CREATED-exposure, accepted-submit,
    and attribution bullets describe behavior implemented on the branch but still pending operator
    ratification and REV-0033 independent review.
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
    single-flight ownership and cannot be locally canceled. Routine reads select accepted facts without decoding
    unrelated UNKNOWN history, project CAPI order lifecycle from event truth, and skip
    checkpoint-only repair transport so idle consumers converge. Startup/reconnect must successfully establish
    the reconcile-driver REDUCING gate even when composed state was already HALTED. A failed
    planned inferred-fill lookup/append cannot be called parity: the verified REDUCING gate stays
    in force and same-tick venue work stops. Repair makes no broker call.
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
