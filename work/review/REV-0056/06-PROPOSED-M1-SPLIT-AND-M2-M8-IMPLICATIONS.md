# Proposed pure-M1 work split and downstream implications

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

## Required re-gate before implementation

WO-0149 must remain paused. It was frozen around a one-lifetime scope model and cannot be safely
extended by an in-place exception. If the candidate is ratified, replace its future implementation
scope with three independently reviewable pure-M1 work orders. Each starts with a new Fable gate,
RED controls, an exact allowed-path list, and a fresh independent acceptance; none is activated by
this packet.

## Three-part pure-M1 split

| Slice | Single semantic center | Minimal deliverable | Required failure-capable proof |
|---|---|---|---|
| M1E-1: generation identity, ownership, and lineage | Immutable AcquisitionGenerationId and direct A/B/C fact routing | Reducer-minted generation ID; generation registry/current economics head; root/effect/owner index; sealed relation projection | A -> B -> C with late A fill/correct/bust routes directly to A; fork/reuse/cross-scope/caller-shaped relation refuses; no audit/history materialization. |
| M1E-2: aggregate controller, successor admission, and mixed recovery | One SymbolAcquisitionController and compatible serial rollover | Exact flat/CLOSED/clear successor gate; one LIVE rule; controller-head create/claim revalidation; fresh B normal protection state and distinct ADR-023 stream after A is non-serving; retired fact preemption and one emergency recovery path | B first fill is FLOOR_ONLY; late A after B create/claim is HARD_BAIL/preemption; one aggregate delta, at most one eligible broker action; incompatible/noisy/nonflat/unknown cases refuse. |
| M1E-3: generated/stateful conformance and evidence | Deterministic lifecycle/replay proof around the new root semantics | Generated A/B/C traces, reorder/duplicate/fork/restart/claim-race controls, mutation controls, boundedness probes, re-gated integration contract | Removing route equality, head advance, one-LIVE uniqueness, generation-local capacity, or compatibility equality makes a named control fail. |

M1E-1 is deliberately free of policy behavior. M1E-2 is the sole cross-side integration slice.
M1E-3 closes confidence rather than adding production capability. This preserves the one semantic
center per work order rule and avoids repeating the earlier implementation/review treadmill.

## M2 implications — contract only, no DDL or implementation

M2 will need a separately approved persistence design that atomically represents:

- a direct acquisition-generation table/record with immutable identity, binding, predecessor,
  status, and current economics head;
- root/effect/owner-to-generation uniqueness and direct lookup;
- one symbol-controller checkpoint/row with current live generation, controller head, aggregate
  commitment, compatibility commitment, and bounded closure summaries;
- the active normal protection/recovery state and any stale/preemption outcome;
- execution fact/revision, venue/closure, effect/claim, and decision receipt updates in the same
  transaction.

Required M2 crash cases are old-or-new successor admission, retired fact during successor
create/claim, duplicate and non-tail revision, and restart with an inconsistent/missing direct
mapping. M2 must reject rather than reconstruct authority from general history.

## M3–M8 obligations

| Milestone | Required future obligation | Explicit non-goal here |
|---|---|---|
| M3 simulator/replay | Deterministic traces for A -> B -> C, late old fact before/after B first fill, crash at every atomic boundary, and final-claim race; invariant check at every step. | No broker adapter or policy allocation. |
| M4 Alpaca Paper adapter | Bind broker-visible client/owner/fact correlation to immutable acquisition generation; a missing mapping is reconciliation-only. | No live/Paper activity or adapter implementation. |
| M5 protection beta | Prove fresh successor market baseline under ADR-023 and controller-level mixed recovery; surface incompatible emergency authority as non-serving. | No market-stream transfer or normal-policy composition. |
| M6 BUY acquisition | Attended Paper evidence for an approved G1 -> flat/CLOSED -> G2 lifecycle and late-old-fact containment. | No automatic repeated entry or authority beyond the approved mandate. |
| M7 RTH handoff/cockpit | Handoff and operator surfaces expose one current controller plus generation/recovery status and cannot reattach old facts to current B. | No second controller or UI-owned execution state. |
| M8 soak/promotion | Measure direct lookup integrity, stale-claim rejection, recovery demotions, bounded-state probes, and repeat-entry safety. | No broad multi-generation portfolio policy. |

## Deferred decisions

The following remain outside the selected architecture and require a new ADR if later wanted:
concurrent tranches/pyramiding, successor with different emergency compatibility, positive-exposure
mandate handoff, automatic multi-policy aggregation, cost-basis allocation by campaign,
cross-account coordination, market-evidence/cursor transfer, live capital, and a second process or
store.
