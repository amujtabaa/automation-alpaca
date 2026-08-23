# WO-0168c frozen non-serving checkpoint contract — R11 SQLite exception closure

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

R11 incorporates the exact R10 object at
`b6d728dba1fdcc9e6efa14b9dc22e2a9160a3710:work/queue/M2-EXECUTION-2026-08-21/21-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R10.md`,
SHA-256 `be5a44df2f54ad9650193f491fdac135b8ac42c2925e972ed1989d9b1394be51`,
including its recursive graph, except for the SQLite-classification clarification below.

## Closed SQLite exception partition

At each repository write/finalization seam, classify an exception only when it is an instance of
the loaded driver's `sqlite3.Error` hierarchy. Caller-visible behavior is total and disjoint:

1. `sqlite3.IntegrityError` whose SQLite primary/extended code is `SQLITE_CONSTRAINT_PRIMARYKEY`
   (`1555`) or `SQLITE_CONSTRAINT_UNIQUE` (`2067`), or whose exact message is one of the frozen
   named trigger-conflict messages, returns `CONFLICT` with no record or receipt.
2. Every other `sqlite3.Error`, including non-conflict `IntegrityError`, `OperationalError`,
   `DatabaseError`, and its other concrete siblings, returns `INTEGRITY_FAILURE` with no record or
   receipt.
3. An exception outside `sqlite3.Error` is not classified or translated. It propagates as the
   identical exception object.
4. The separately frozen receipt-validation rule remains phase-bound: only its three exact
   validation exception classes raised while constructing the success receipt translate to
   `INTEGRITY_FAILURE`; adjacent classes and the same classes injected at other seams propagate as
   the identical object.

The implementation must not classify by message substring, generic `Exception`, or a foreign
object carrying SQLite-shaped attributes.

## Failure-capable controls and mutants

F01/F03/F07/F09 must include exact controls for: a named primary/unique conflict; a named trigger
conflict; a non-conflict `IntegrityError`; an `OperationalError`; at least one otherwise-unlisted
loaded-driver sibling such as `DataError`; an injected non-SQL exception; and all three exact
receipt-validation classes plus an adjacent class and an exact-class injection outside the receipt
phase. Each control asserts exact outcome or identical propagated-object identity, rollback, and
no record/receipt.

Required mutants are only behavior-changing mutations against that closed oracle: map either
named conflict class to `INTEGRITY_FAILURE`; map non-conflict `IntegrityError`, `OperationalError`,
or the sibling control to `CONFLICT` or propagation; translate an injected non-SQL exception;
replace a propagated object; broaden receipt translation to the adjacent class or another phase;
swap each required outcome kind; or return a record/receipt on failure. Every mutant must be killed
by its named control for caller-visible behavior.

All other R10/R9/R8/R7/R6/R5/R4 authority remains unchanged. REV-0077 must return exact R11
`ACCEPT` with `P0=0/P1=0` before source/test paths are released. The changed-DDL human gate and
every safety and scope exclusion remain fully in force.
