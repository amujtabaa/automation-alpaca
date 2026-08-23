# WO-0168c frozen non-serving checkpoint contract — R13 terminal control accounting

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

R13 incorporates the exact R12 object at
`a8965e988203e9d31aae211ec5f8c7d23a284ad5:work/queue/M2-EXECUTION-2026-08-21/23-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R12.md`,
SHA-256 `c533042ed9af25109ccc64e742586d083a70c104549453bd02e3d35574bc4e72`,
including its recursive graph. R13 changes only R12's control accounting as follows.

## Exact behavioral controls

Pure direct classifier controls assert only exact `RepositoryOutcomeKind` with no record, or the
identical propagated exception object. They make no transaction, rollback, or repository-record
claim.

Integrated seam controls separately inject the exact trigger-message `IntegrityError` at:

- selection, expecting `INTEGRITY_FAILURE` and no record;
- payload INSERT, expecting `CONFLICT` and no record;
- CAS, expecting `INTEGRITY_FAILURE` and no record; and
- reread, expecting `INTEGRITY_FAILURE` and no record.

Each integrated control asserts one caller rollback, zero commit, no receipt, close/reopen, and
the exact retained predecessor state required by F01-F09. A separate wrong-Boolean mutant at each
seam must change the expected caller-visible outcome and fail its named control.

Receipt translation has the exact Cartesian matrix of three classes by three phases: exact
`TypeError`, `ValueError`, and `OverflowError`, each injected separately during receipt object
construction, receipt field validation, and receipt registry insertion. All nine controls expect
`INTEGRITY_FAILURE`, no record/receipt, and the integrated F09 rollback/reopen assertions. Nine
separate narrowing mutants move exactly one phase/class injection outside translation. A
receipt-phase `ValueError` subclass remains a tenth control and propagates by identical identity.

Every behavioral classification, translation, propagation, identity, outcome-kind, and
record-presence mutant is killed by one named pure or integrated caller-observable assertion.

## Structural controls

Static AST/token/reference tests separately kill: a duplicated classifier predicate; a SQL catch
that bypasses the shared classifier; a receipt catch outside the sole receipt wrapper; an alternate
classifier/wrapper definition; or a dynamic/duck-typed/message-substring route. These are
source-structure mutants and are not claimed to be killed by caller-visible behavior. The four
wrong-Boolean seam mutants remain behavioral and belong only to the integrated matrix above.

All other R12/R11/R10/R9/R8/R7/R6/R5/R4 authority remains unchanged. REV-0077 must return exact
R13 `ACCEPT` with `P0=0/P1=0` before source/test paths are released. The changed-DDL human gate
and every safety and scope exclusion remain fully in force.
