# WO-0168c frozen non-serving checkpoint contract — R12 exhaustive exception oracle

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

R12 incorporates the exact R11 object at
`248736ebf111118f4d958e07fc3dca40b37be342:work/queue/M2-EXECUTION-2026-08-21/22-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R11.md`,
SHA-256 `31003810536acb19a79de2511dcd6d6bd878d7815fe00558729b2892df354b09`,
including its recursive graph. R12 replaces R11's two sections after its authority paragraph.

## Ordered, disjoint exception oracle

The checkpoint write path applies these rules in order:

1. Only while constructing, validating, or registering the success receipt, an exception whose
   exact type is `TypeError`, `ValueError`, or `OverflowError` returns `INTEGRITY_FAILURE` with no
   record or receipt.
2. Otherwise, an exception that is an instance of the already-loaded driver's `sqlite3.Error`
   hierarchy is classified as follows:
   - an `sqlite3.IntegrityError` with exact extended code `1555`
     (`SQLITE_CONSTRAINT_PRIMARYKEY`) returns `CONFLICT`;
   - an `sqlite3.IntegrityError` with exact extended code `2067`
     (`SQLITE_CONSTRAINT_UNIQUE`) returns `CONFLICT`;
   - only at the `runtime_checkpoint_payload` INSERT seam, an `sqlite3.IntegrityError` whose exact
     message is `runtime checkpoint payload identity is already retained` returns `CONFLICT`;
   - every other `sqlite3.Error` returns `INTEGRITY_FAILURE`.
   Every SQLite-classified failure returns no record or receipt.
3. Every remaining exception propagates as the identical object. This includes the three receipt
   classes at every non-receipt seam, their subclasses at every seam, `sqlite3.Warning`, and any
   foreign exception carrying SQLite-shaped attributes or text.

Classification uses loaded-driver class identity and ordinary `isinstance` only for the enumerated
SQLite hierarchy. The trigger message comparison is exact and receives its one literal allowlist
only at the payload INSERT. It is not enabled at CAS, reread, selection, or receipt seams. No
substring, generic `Exception`, attribute duck typing, or message-only classification exists.

All checkpoint SQL exception catches call one private
`_classify_runtime_checkpoint_sqlite_failure(caught, *, payload_insert: bool)` helper. There is
exactly one definition; F01 passes `payload_insert=True`; every selection, CAS, and reread catch
passes `False`. No seam-local copy or alternate classifier exists. Receipt translation occurs only
inside one private `_issue_runtime_checkpoint_write_receipt` wrapper after successful exact reread
and does not call the SQL classifier. Static AST/reference tests pin this routing and kill a bypass,
duplicated predicate, wrong Boolean, or classifier call at receipt issuance.

## Exhaustive failure-capable controls

The fault suite has a separate named control and a separate narrowing mutant for each of:

- `IntegrityError` code `1555`, code `2067`, and the exact payload-trigger message;
- non-conflict `IntegrityError` and direct instances of `sqlite3.Error`, `InterfaceError`,
  `DatabaseError`, `DataError`, `OperationalError`, `InternalError`, `ProgrammingError`, and
  `NotSupportedError`, each expecting `INTEGRITY_FAILURE`;
- exact `TypeError`, `ValueError`, and `OverflowError` at receipt construction, each expecting
  `INTEGRITY_FAILURE`, and each same exact object injected separately at payload INSERT, each
  propagating by identity;
- a receipt-phase subclass of `ValueError`, propagating by identity;
- a direct `sqlite3.Warning`, propagating by identity; and
- a custom non-SQL exception carrying `sqlite_errorcode=1555` and exact trigger-message text,
  propagating by identity at payload INSERT.

Each control also asserts rollback and no record/receipt. Required mutants independently change
the expected disposition of exactly one listed control; enable the trigger message at one wrong
seam; translate the adjacent receipt subclass; classify either non-SQL impostor; replace a
propagated object; swap an outcome kind; or return a record/receipt on failure. Every required
mutant must be killed by its one named caller-visible assertion.

The exhaustive class controls invoke the shared classifier directly without SQLite activity.
Separate F01/F03/F07 proxy controls prove each SQL catch routes the identical injected exception
to that helper and preserves the required outcome/identity. Receipt controls invoke the sole
receipt wrapper directly and through F09. Together with the structural routing assertion, no
seam-local classification or translation predicate is admitted.

All other R11/R10/R9/R8/R7/R6/R5/R4 authority remains unchanged. REV-0077 must return exact R12
`ACCEPT` with `P0=0/P1=0` before source/test paths are released. The changed-DDL human gate and
every safety and scope exclusion remain fully in force.
