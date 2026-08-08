# WO-0149 R3 never-seen-scope bootstrap preflight

Status: **PREFLIGHT REQUEST — DRAFT ONLY**

Target: the proposed WO-0149 R3 amendment in this packet. This is a documentation-only static
review. It does not amend the active work order or authorize implementation.

## Background

REV-0053 established that exact empty-account genesis prevents a legal first M1E lifecycle after
unrelated account history. REV-0054 then showed that same-symbol rollover is not a WO-only
correction: a successor first fill and an old late fact require distinct M1D lineage semantics.
Those packets remain unchanged historical evidence.

R3 adopts only the safe subset: a sealed initial M1E bootstrap for a never-before-used exact
`PositionScope` after other scopes have account history. It explicitly refuses same-scope
rollover, including after exact flat/closure, pending a new ADR.

## Review question

Re-derive whether R3 preserves the accepted first-fill `FLOOR_ONLY` rule and late-old-fact
`HARD_BAIL` rule by proving the target scope has no prior canonical or venue lineage at all.
Verify its absence proof is bounded and direct-indexed, does not reopen generic BUY admission,
and leaves existing exact-empty genesis intact.

Review only the R3 draft against ADR-020 through ADR-023, the domain specification, active
WO-0149, and relevant public M1E interfaces. Deposit findings only in `result.md`. Do not edit
code, tests, the active work order, or this request. No application/test execution, database,
SQL/DDL, network, broker, or Git mutation is needed.
