# WO-0149 R2 scoped-bootstrap preflight

Status: **PREFLIGHT REQUEST — DRAFT ONLY**

Target: the proposed WO-0149 R2 bounded bootstrap amendment in this packet. This is a
documentation-only feasibility review. It neither changes the active work order nor authorizes
production or test implementation.

## Question

The prior WO-0149 contract has no public bounded way to start a later M1E acquisition after
account venue history exists. REV-0053 established that gap and preserved its initial proposal
and review unchanged. The R2 proposal deliberately separates two cases:

1. A first M1E acquisition for a flat symbol after other account history exists; and
2. A same-symbol successor after the old acquisition is terminal and the symbol is exactly flat.

For the second case, R2 permits only a distinct acquisition mandate that retains the exact same
complete protection mandate and protection state. A different protection mandate is explicitly
out of scope and requires a new ADR.

## Review boundary

Re-derive conformance from ADR-020 through ADR-023, the accepted domain specification, the
active WO-0149, current public M1E interfaces, and the R2 draft. Verify that its direct-index
tombstone and shared-protection restrictions preserve late old FILL/CORRECT/BUST handling without
generic BUY admission, a history scan, private-state access, duplicate protection authority, or
cross-symbol substitution.

Produce findings only in `result.md`. Do not edit implementation files, the active work order,
or this request. No application execution, test run, database, SQL/DDL, broker, network, or Git
mutation is needed for this static preflight.
