# Draft downstream reconciliation — non-authoritative

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

This file supplies copy-ready future amendments only. It does not modify the named authoritative
records and does not activate a work order.

## Target architecture / domain specification amendment

Add a successor section after ratified ADR-020 R2 and ADR-021 R2:

> A PositionScope may contain serial AcquisitionGenerationIds but never concurrent live
> generations. Every operator-approved acquisition lifecycle uses a new complete dual-mandate
> binding and reducer-minted generation identity. A successor is admitted only from exact flat,
> exact CLOSED, clear reconciliation/integrity, no potentially executable predecessor BUY, exact
> predecessor controller head, exact immutable controller-lifetime EmergencyRecoveryCompatibility,
> and a distinct approved
> MarketStreamGenerationId. The predecessor protection state is non-serving before the fresh
> successor state begins its ADR-023 baseline. One SymbolAcquisitionController owns one aggregate
> position and one active protection/broker authority. A current generation first owned root is
> FLOOR_ONLY; an exact retired-generation
> root is economics-first, generation-local, and enters constrained mixed-generation HARD_BAIL
> while staling current BUY authority. No caller-shaped provenance, history scan, policy merge, or
> ownership transfer is permitted.

## Persistence and cutover amendment

Add an M2 requirement:

> In the existing atomic unit of work, persist immutable AcquisitionGenerationId ownership for
> every acquisition root/effect/owner, one direct retired/current economics head per generation,
> and one bounded SymbolAcquisitionController record. Unique constraints must prohibit two LIVE
> generations per scope and any ambiguous root/effect/owner mapping. Restart validates direct
> index totality/currentness and is non-serving on any inconsistency. No checkpoint stores or
> scans an unbounded retired-generation collection.

## Roadmap amendment

Replace the permanent never-before-used target-scope containment with:

> Before ordinary repeated BUY acquisition, complete the ratified serial-generation M1 split:
> direct generation lineage; one-controller successor/mixed-recovery behavior; then generated and
> stateful conformance. M2 persists the same direct authority atomically, M3 replays A/B/C and
> crash/race histories, M4 preserves broker fact correlation, M5 preserves fresh ADR-023 evidence,
> M6 proves attended repeat lifecycle, M7 exposes controller status, and M8 soaks bounded routing.
> Concurrent policy arbitration remains deferred.

## PKL/project posture amendment

Append, rather than overwrite:

> WO-0149 implementation is paused pending human ratification of the exact ADR-020 R2 /
> ADR-021 R2 serial acquisition-generation decision. REV-0053 and REV-0054 remain negative
> evidence; REV-0055 is an unaccepted narrow bootstrap draft. No later reset work order is active.
> Ratification is required before re-gating/splitting M1E work; M2 and later milestones remain
> inactive.

## Work-order re-gate amendment

After ratification only:

> Supersede the one-lifetime same-scope assumption in WO-0149. Do not implement a successor as a
> cleanup/reuse exception. Replace it with M1E-1, M1E-2, and M1E-3 work orders defined in
> REV-0056. Each work order must bind to the ratified ADR hashes, identify its exact public
> contracts/allowed paths, run its own RED and independent acceptance gates, and preserve all
> broker/database/runtime exclusions until separately authorized.

## Ledger / provenance entry

Append, rather than rewrite history:

> ARCH-RESET serial acquisition-generation decision candidate prepared in REV-0056. It proposes
> ADR-020 R2 and ADR-021 R2 to resolve REV-0054 P1.1/P1.2. Candidate is documentation-only,
> unratified, and does not authorize implementation. Exact candidate and review hashes must be
> recorded only after independent preflight and human ratification.
