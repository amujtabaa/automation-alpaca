# REV-0058 R1 request -- WO-0151 RED contract replacement pre-flight

Review only `WO-0151-RED-CONTRACT-R1.md` as an exact documentation candidate.
`result-r0.md` explains why R0 is retained negative evidence; do not reuse its
conclusion as acceptance evidence.

Re-derive R1 from accepted ADR-020 R2, ADR-021 R2, ADR-023 R1, the active
WO-0151 draft, and the present E1 public seams. Treat retained WO-0149 material
only as non-authoritative comparison evidence. Do not edit source, tests, ADRs,
or lifecycle records.

Check especially that R1:

1. derives a fact relation from a sealed venue transition without caller
   selectors and separately supports target-scoped bootstrap;
2. threads authenticated pre/post acquisition, execution, venue, protection,
   registry/lineage, and authority state without a second writer;
3. binds compatibility to the full protection mandate and provides a feasible
   controller-to-protection mixed-recovery seam;
4. defines exact specialized BUY creation/final-claim/preemption authority
   permits, immutable term retention, and generic BUY refusal; and
5. has an acyclic, literal static boundary that can be mechanically tested.

Return findings only in `result-r1.md`: severity, location, why it matters,
and the smallest root-level correction. End with `ACCEPT`,
`ACCEPT-WITH-CHANGES`, or `BLOCK`; state P0/P1/P2 counts and any unverified
item. No review finding should be speculative or merely stylistic.
