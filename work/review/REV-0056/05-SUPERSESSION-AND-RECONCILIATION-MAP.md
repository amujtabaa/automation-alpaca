# Supersession, clause, and reconciliation map

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

## Replacement and overlay rule

The proposed ADR-020 R2 and ADR-021 R2 are versioned complete replacement candidates. They do
not alter accepted ADR files in this packet. Ratification must name their exact frozen hashes,
predecessor hashes, and this narrow supersession map. ADR-023 R1 remains controlling wherever
market occurrence authority, market stream generation, evidence policy, cursor, or recovery
baseline is concerned.

## Clause map

| Current authority | Current requirement | R2 treatment | Reason |
|---|---|---|---|
| ADR-020 R1 §§ decision / core / transaction | One pure core, one logical writer, fact-only quantity, bounded checkpoint and write transaction | Carried forward in ADR-020 R2 §§1 and 5–6 | Serial lineage must extend the existing kernel, not create another writer/store. |
| ADR-020 R1 §§ correction and terminal owner rules | Corrections/busts remain valid and terminal closure keeps indexed head | Carried forward and made generation-total in ADR-020 R2 §§1 and 3 | Late A economics need a direct current head after A is retired. |
| ADR-020 R1 no prior clause | No explicit same-symbol post-terminal acquisition lineage route | Added in ADR-020 R2 §§2–5 | Resolves REV-0054 P1.2 without history scan or caller authority. |
| ADR-020 R1 § no-history live transition | Live transitions never scan audit history | Carried forward in ADR-020 R2 §§3–5 | Direct root/effect/owner-to-generation indexes are mandatory. |
| ADR-021 R1 §§ acquisition and first fill | Complete dual mandate and first acquisition fill begins FLOOR_ONLY | Carried forward, generation-qualified in ADR-021 R2 §§3–6 | B first root must remain normal first fill, not inherit A's FLAT marker. |
| ADR-021 R1 § late fact after flat | Late owned fact after flat applies economics and returns HARD_BAIL | Carried forward, provenance-qualified in ADR-021 R2 §§5–7 | Retired A is distinguished from B first root and becomes one mixed emergency path. |
| ADR-021 R1 §§ symbol gate / closure / final claim | One symbol authority, exact CLOSED, final claim revalidation | Carried forward in ADR-021 R2 §§1, 4, 6–7 | Successor admission and preemption use existing gates, extended by controller head. |
| ADR-021 R1 no prior clause | No compatible distinct-normal-mandate successor definition | Added in ADR-021 R2 §3 | Defines the smallest shared emergency authority while refusing policy composition. |
| ADR-022 R1 | Human ratification, M1 split, beta boundaries | Unchanged | It already requires ADR-level authorization and work-order separation. |
| ADR-023 R1 | Market stream/evidence/cursor are immutable under their mandate and separate reviewed cutover is required | Unchanged, explicitly preserved | AcquisitionGenerationId is not MarketStreamGenerationId; each successor uses a distinct stream in a fresh state only after its predecessor is non-serving, with no cursor reset/reuse. |

## Exact terminology disambiguation

| Identity | Authority it identifies | Never used as |
|---|---|---|
| ApplicationGenerationId | Deployment/cutover, persistence, process/client/broker fence | Acquisition campaign or market cursor |
| AcquisitionGenerationId | One serial, operator-approved acquisition lifecycle and immutable owned fact/effect lineage | Caller-provided token, application generation, or market stream |
| MarketStreamGenerationId | ADR-023 market evidence/cursor authority | Acquisition lifecycle, successor ordinal, or market-state reset shortcut |
| EmergencyRecoveryCompatibility | Immutable controller-lifetime equality commitment for one restricted aggregate emergency response | General policy engine, normal strategy, or broker credential |

## Proposed non-authoritative document reconciliation

No authoritative document is changed by this packet. After exact human ratification, the minimum
atomic documentation change set is:

1. Add accepted ADR-020 R2 and ADR-021 R2 with their exact candidate hashes to the ratification
   and authorization/provenance record; record ADR-023 as retained unchanged.
2. Append successor amendments—not rewrites—to the frozen target architecture, domain
   specification, persistence/cutover, roadmap, and ADR-set records. Each must name this packet,
   the predecessor hash, and the approved R2 hash.
3. Update the architecture map and project goals/current posture to say WO-0149 is paused pending
   re-gated, ADR-authorized serial-generation work; append the PKL log and ledger, never rewrite
   historical closeout/evidence text.
4. Supersede/re-gate the active WO-0149 only after the ADR ratification is recorded. Split new
   work orders rather than stretching the old implementation contract.
5. Refresh docs/04_IMPLEMENTATION_PLAN.md only as a historical navigation/status backlink, never
   as target authority.

The future reconciliation must not declare M1 complete, approve master landing, activate M2, or
erase REV-0053 through REV-0055. All failed proposals remain retained negative evidence.
