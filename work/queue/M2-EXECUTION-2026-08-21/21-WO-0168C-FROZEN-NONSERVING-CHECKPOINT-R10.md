# WO-0168c frozen non-serving checkpoint contract — R10 terminal correction

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `c67b6c3`

R10 incorporates the exact R9 object at
`fb66ea803e2c34f920488e3d81f3f32a2e73111b:work/queue/M2-EXECUTION-2026-08-21/20-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R9.md`,
SHA-256 `fa3735b9c363eea69456844ee5a44f15ec9ecab0f10790e8d7087dd182a33d24`,
including its recursive graph.

R9 section 3's four exception behaviors remain unchanged. Its final mutant sentence is replaced
exactly by:

> No reorder-only mutant is required because the four predicates are non-overlapping. Required
> behavior-changing mutants separately: broaden receipt-validation translation beyond its three
> exact classes/phase; narrow or broaden each named SQLite classification; translate an injected
> or unknown non-SQL exception; replace rather than preserve a propagated exception object; swap
> each required outcome kind; and return a record/receipt on every failure. Each mutant is tied to
> its exact F01, F03, F07, or F09 assertion and must fail for behavior, not source ordering.

All other R9/R8/R7/R6/R5/R4 authority remains unchanged. REV-0077 must return exact R10 `ACCEPT`
with `P0=0/P1=0` before source/test paths are released. The changed-DDL human gate and every safety
and scope exclusion remain fully in force.
