# WO-0168c frozen non-serving checkpoint contract — R7 final clarification

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `7cd8098`

## 1. Authority and narrow precedence

R7 incorporates the exact R6 object at
`2c6c680742aec2ed04465d1818887d591836e797:work/queue/M2-EXECUTION-2026-08-21/17-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R6.md`,
SHA-256 `3dd93f8376516003bcb169195f2457395435741aa7a2f628ab644d128736ce0e`,
including its recursively closed graph. R7 replaces only the clauses below.

In the authority top, R2's symbolic `ManualFlattenRows` is exactly contract-07's `ManualRows`
wrapper: literal tag `m2.authority.ManualFlattens/v1`, key `flatten_id`, strict key order,
duplicate refusal, exact empty form `["m2.authority.ManualFlattens/v1",0,[]]`, and the imported
ManualFlatten row. No separate manual wrapper exists.

## 2. Provenance binds the actual field

R6's projected/loaded formulas replace their literal provenance argument with
`FIELD_TEXT(value._provenance)`. Before binding, projected requires exact
`value._provenance == "PROJECTED"`; loaded requires exact
`value._provenance == "LOADED"`. Any other exact string, non-string, copied value, or
`object.__setattr__` mutation fails. Registry provenance must equal that same validated field.

## 3. Exact runtime capability identity and issuer confinement

R6's active entry is extended to:

```text
active_runtime_lease[id(connection)] =
    (connection, generation, lease_identity, exact_capability_object)
```

Activation constructs the capability, then atomically registers that exact object under the
private lock. Validation additionally requires `entry.capability is capability`. Retirement
requires and removes only that exact object. `_RuntimeWriteCapability.__copy__`, `__deepcopy__`,
and `__reduce__` raise `TypeError`; `copy.copy`, `copy.deepcopy`, pickle/reduction, object-new plus
field copying, and a second exact-type object carrying copied references all fail. W00c includes a
separate mutant for each registry-identity and copy/reduction control.

The source-confinement matrix is exact:

- definitions of `_activate_runtime_write_lease` and `_retire_runtime_write_lease` occur only in
  `repository.py`;
- calls/references outside their definitions occur only in `unit_of_work.py` and their exact named
  tests;
- AST plus token/reference tests reject direct imports, imported aliases, repository module
  attributes from any other module, assignment/rebinding, matching `getattr` string literals,
  constructor/object-new issuance, and unlisted test callers;
- mutants add one forbidden route of each kind and must fail; and
- the test also proves activation follows the exact BEGIN/verification site and retirement is
  adjacent to every transaction exit in `unit_of_work.py`.

No claim is made to defeat hostile runtime reflection; this is the repository's structural
authority boundary.

## 4. Exact transaction-gate behavior

This section overrides R5's generic no-transaction outcome:

- selection and composed load with `connection.in_transaction is not True` return
  `INTEGRITY_FAILURE` with no record and zero SQL;
- store with a missing/arbitrary/forged/subclassed/wrong-seal/cross-connection runtime capability,
  or an exact runtime capability outside its active transaction, raises exact `TypeError` for
  wrong type and exact `ValueError` for invalid state before outcome translation and with zero SQL;
- store with an authentic setup capability but no active explicit transaction returns
  `INTEGRITY_FAILURE`, no record, and zero SQL after capability validation; and
- store with an authentic active runtime or setup capability proceeds to schema verification and
  the exact R5 selection/write path.

W00a pins each case and swaps every exception/outcome in separate mutants. W00b retains setup
issuer/import restrictions. No broad `Exception` assertion is accepted.

## 5. Future WO-0168b lease exit matrix

WO-0168b-W00c is exactly:

| ID | Exit | Required lease/transaction calls |
| --- | --- | --- |
| L00 | verification fails before activation | zero activation, zero retirement; rollback per UOW contract |
| L01 | activation refuses because one exact lease is active | registry unchanged; zero new capability and zero retirement of existing lease |
| L02 | post-activation verification/body raises | retire once, rollback once, zero commit; original error remains exact unless UOW defines a typed refusal |
| L03 | body returns non-committing/refused result | retire once, rollback once, zero commit |
| L04 | body succeeds | retire once immediately before one commit, zero rollback |
| L05 | commit raises/returns ambiguously | retire once before one commit attempt; zero rollback and zero retry; typed reconciliation-only result |
| L06 | rollback raises | retire once before one rollback attempt; zero commit; rollback error propagates/fails closed and registry is empty |
| L07 | normal T1 commit then T2 on same connection | new generation/identity; every T1 token rejected |
| L08 | normal T1 rollback then T2 on same connection | new generation/identity; every T1 token rejected |

Every post-activation exit asserts exact registry absence before COMMIT/ROLLBACK, exact call counts,
and T1-token refusal. Mutants skip/double/reorder retirement, retire the existing lease on L01,
retain on an exceptional path, retry ambiguity, or reuse generation/identity.

## 6. WO-0168c fault outcomes — exact and reachable

`_InjectedCheckpointFault` and `_InjectedCommitFault` are exact test-only exception classes. A
faulting connection/proxy or monkeypatched private issuer raises them at the named seam; production
source contains no fault hook. Non-SQL exceptions propagate unchanged after the caller performs
the required rollback. SQLite errors are classified by the existing closed repository policy.

| ID | Injection | Exact caller-visible store/commit result |
| --- | --- | --- |
| F00 | harness raises `_InjectedCheckpointFault` immediately before calling store | same exception; no repository call or receipt |
| F01a | payload INSERT raises PRIMARY KEY/UNIQUE `sqlite3.IntegrityError` | `CONFLICT`, no record |
| F01b | payload INSERT raises other `sqlite3.IntegrityError` | `INTEGRITY_FAILURE`, no record |
| F01c | payload INSERT raises `sqlite3.OperationalError` | `INTEGRITY_FAILURE`, no record |
| F01d | payload INSERT proxy raises `_InjectedCheckpointFault` | same exception, no receipt |
| F02 | proxy raises `_InjectedCheckpointFault` after INSERT and before CAS | same exception, no receipt |
| F03a | CAS execute raises `sqlite3.OperationalError` | `INTEGRITY_FAILURE`, no record |
| F03b | CAS proxy raises `_InjectedCheckpointFault` | same exception, no receipt |
| F04 | test-only CAS parameter/source mutant produces zero affected rows | `CONFLICT`, no record |
| F05 | full reselection is stale before INSERT | `CONFLICT`, no record; CAS not attempted |
| F06 | proxy raises `_InjectedCheckpointFault` after CAS and before reread | same exception, no receipt |
| F07a | reread raises `sqlite3.OperationalError` | `INTEGRITY_FAILURE`, no record |
| F07b | reread returns zero/two/mismatched rows | `INTEGRITY_FAILURE`, no record |
| F08 | proxy raises `_InjectedCheckpointFault` after reread and before receipt | same exception, no receipt |
| F09a | receipt validation raises `TypeError`, `ValueError`, or `OverflowError` | `INTEGRITY_FAILURE`, no record |
| F09b | receipt issuer raises `_InjectedCheckpointFault` | same exception, no receipt |
| F10 | setup-capability store returned `APPLIED` with authentic receipt, then caller COMMIT raises `_InjectedCommitFault` | same commit exception; no second commit/rollback; reopen classifies exact old-complete or new-complete |
| F11 | setup-capability store and caller COMMIT succeed | `APPLIED` with authentic receipt; exact new-complete reopen |

For F00, the harness begins first, catches its own exception, calls rollback once, and proves zero
store invocation. F00 is a caller-transaction control, not a repository outcome. F01-F09 each
require one caller rollback, zero commit, close/reopen, exact predecessor head, no candidate
payload/head coordinates, and unchanged reverse-edge counts. F10 is only the WO-0168c
setup-capability commit-ambiguity proof; it makes no runtime-lease claim. The future runtime
commit-ambiguity and reconciliation-only result are exclusively L05. F11 requires one commit,
zero rollback, exact payload/head/reverse edge, and retained receipt.

Tests pin exact outcome kind, record/receipt presence, exact propagated exception identity, all
transaction calls, SQL trace, and reopened state. Mutants swap kinds, swallow/replace exceptions,
return a receipt on failure, skip/double transaction calls, continue after F01, issue before
reread, or weaken reopen assertions.

## 7. Final stop

R6's recursively closed authority, wire, APIs, selection, SQL, DDL, binding, vector, capability,
and test clauses remain exact except these replacements. No source/test path is released until
fresh REV-0077 returns `ACCEPT` with `P0=0/P1=0`. The exact changed-DDL human gate remains fully in
force. No SQLite, serving authority, second engine, configured/in-memory database, migration,
runtime composition, credentials, network/broker/orders, promotion, or merge is authorized.
