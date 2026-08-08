# REV-0058 R0 pre-flight result

Status: **RETAINED NEGATIVE EVIDENCE -- R0 IS NOT ACCEPTED**

Three independent static passes compared the R0 RED contract with ADR-020 R2,
ADR-021 R2, ADR-023 R1, WO-0151, and the current E1 public seams. No source,
test, ADR, or lifecycle file was changed by those passes.

## Result

**BLOCK** -- P0: 1, P1: 7, P2: 0.

The P0 was decisive: R0 accepted caller-selected request/effect/leg/root
selectors in `project_acquisition_venue`, while the current
`VenueRecoveryTransition` did not carry a sealed source-fact relation. A
current-book lookup can prove that an older root exists, not that it produced
the supplied transition. That is incompatible with ADR-021's required sealed
relation.

The P1 findings had one shared root: R0 named component outcomes without
threading the authenticated pre-state, post-state, exact execution/venue
relation, or specialized authority data needed to produce them. In particular,
it lacked a target-scoped bootstrap source, a state holder for registry and
lineage, an authority/venue outcome, a compatibility reference in
`ProtectionMandate`, a mixed-recovery protection bridge, exact effect-term
retention, a bounded status shape, and mechanical static-boundary rules.

## Required replacement direction

The replacement must use a selector-free, transition-derived venue fact proof;
a separate target-scoped bootstrap proof; one explicit composite acquisition
state/result; exact specialized authority permits; a protection-owned
mixed-recovery consumption API; and literal module/import/export restrictions.

`WO-0151-RED-CONTRACT.md`, `request.md`, and the R0 manifest are retained
unchanged so the rejected assumptions remain auditable. The next candidate is
R1 and must receive a fresh independent review.
