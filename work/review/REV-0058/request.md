# REV-0058 request — WO-0151 RED contract pre-flight

Review only `WO-0151-RED-CONTRACT.md` as an exact documentation candidate.
Re-derive its semantics from accepted ADR-020 R2, ADR-021 R2, ADR-023 R1, the
active WO-0151 draft, and current public execution-core seams. Treat retained
WO-0149 material only as non-authoritative comparison evidence.

Assess whether the frozen public interface is sufficient and bounded for:

1. target-scoped bootstrap despite unrelated-symbol account history;
2. one-controller serial A→B→C admission and direct registry/lineage routing;
3. composite canonical-fact handling, fresh normal protection, and retired
   fact mixed recovery;
4. refusal of generic BUY creation plus controller-head revalidation at effect
   creation and final claim; and
5. no private access, history materialization, second writer, or hidden
   runtime/persistence scope.

Return findings only in `result.md`: severity, location, why it matters, and
the smallest correction. End with `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`;
state P0/P1/P2 counts and any unverified item. Do not edit production, tests,
ADRs, or lifecycle records.
