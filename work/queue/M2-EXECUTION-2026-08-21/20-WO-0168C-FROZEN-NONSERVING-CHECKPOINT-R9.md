# WO-0168c frozen non-serving checkpoint contract — R9 final closure

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `6bd6985`

## 1. Exact authority

R9 incorporates the exact R8 object at
`dadaa41bc09ba3668ff12882ac813ac508eee78d:work/queue/M2-EXECUTION-2026-08-21/19-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R8.md`,
SHA-256 `ad18edb1f2ce3b01a56802bcdb34d3425dda6b331c5de0ce5c3d5b250ac0fec6`,
including its recursive graph. R9 makes only the replacements below.

## 2. R7 section 4 is fully replaced

R7 section 4 has no retained authority. The complete WO-0168c transaction gate is exactly:

- selection and composed load with `connection.in_transaction is not True` return
  `INTEGRITY_FAILURE`, no record, and execute zero SQL;
- store with a missing, arbitrary, object-new-with-missing-or-fake-fields, subclass-attempt,
  wrong-seal, or cross-connection value raises exact `TypeError` for wrong type or exact
  `ValueError` for invalid state before outcome translation and executes zero SQL;
- store with an authentic setup capability but `connection.in_transaction is not True` returns
  `INTEGRITY_FAILURE`, no record, and executes zero SQL; and
- store with an authentic setup capability on its exact writer connection inside the explicit
  transaction proceeds to schema verification and the exact retained selection/write path.

There is no authentic-runtime success/out-of-transaction case or runtime W00 test in WO-0168c.
Runtime issuance and every authentic-runtime behavior remain solely the hard WO-0168b preflight
hold in R8 section 3.

## 3. One ordered exception oracle

Exception handling precedence is exact and non-overlapping:

1. receipt construction/validation exact `TypeError`, `ValueError`, or `OverflowError` returns
   `INTEGRITY_FAILURE`, no record;
2. loaded-driver SQLite exceptions use the exact retained F01/F03/F07 classifications;
3. exact `_InjectedCheckpointFault` and `_InjectedCommitFault` propagate as the identical object;
4. every other unexpected non-SQL exception propagates unchanged using ordinary `isinstance`
   catch semantics only where a named base class is explicitly caught; no catch-all translates it.

Mutants reorder any two rules, broaden receipt translation, translate an injected/unknown error,
or replace a propagated exception object.

## 4. Fresh-file connection model

Each SQLite-bearing checkpoint test, after the human DDL gate, uses one fresh `tmp_path` file
database and never `:memory:` or a configured/existing path. The write phase uses one
setup-authorized writer connection. After required commit/rollback, that writer is closed. The
durability phase opens one distinct, non-authorized read-only-for-test-classification connection to
the same fresh file, verifies schema pragmas, performs only the named reopen reads, and closes it.
No capability is transferred between connections and the reopen connection performs no write.

## 5. Stop

All other R8/R7/R6/R5/R4 exact clauses remain unchanged. REV-0077 must return R9 `ACCEPT` with
`P0=0/P1=0` before source/test paths are released. Changed DDL execution and every SQLite-bearing
test remain behind Ameen's exact human gate. No serving authority, runtime composition,
configured/in-memory database, migration, credentials, network/broker/orders, promotion, or merge
is authorized.
