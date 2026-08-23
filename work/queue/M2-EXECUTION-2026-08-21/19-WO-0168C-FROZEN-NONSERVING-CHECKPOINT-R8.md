# WO-0168c frozen non-serving checkpoint contract — R8 scope closure

Status: **SUPERSEDED BY R9 — EVIDENCE ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `08bf179`

## 1. Closed authority

R8 incorporates the exact R7 object at
`855b3f26abc8d1cb3a6f83eb2dd718754d18e0df:work/queue/M2-EXECUTION-2026-08-21/18-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R7.md`,
SHA-256 `086b49103ad3480401ea0450a9d8d309a206bd2dec99d0302e75113332ab1c89`,
including its recursively closed R6/R5/R4 graph. R8 replaces only R7's copied-provenance claim,
sections 3 and 5, and the broad exception-propagation sentence in section 6. All wire, envelope
formula, API, outcome, selection, SQL, DDL, vector, binding, setup-capability, F00-F11, safety, and
human-gate clauses remain exact except as stated below.

## 2. Provenance is a value discriminator

Projection accepts exact `str` value `PROJECTED`; load accepts exact `str` value `LOADED`; the
actual `_provenance` field is bound through FIELD_TEXT and must agree with registry metadata.
Equal strings are intentionally the same canonical value. No test claims copied-string identity
is authority. Tests alter type or value, while separate exact-envelope registry tests cover copied
or forged envelope objects.

## 3. Runtime capability is a hard successor hold, not WO-0168c scope

Current source has no production runtime-capability issuer and WO-0168c adds none. It adds no
runtime lease activation/retirement helper, no `unit_of_work.py`, and no runtime issuer test
allowlist. Therefore no production runtime path can legitimately call checkpoint store during
WO-0168c. All WO-0168c successful store/fault tests use the exact setup capability from
`tests/execution_core/persistence_setup_support.py`, one fresh `tmp_path` file connection, and an
explicit caller transaction.

The reproduced connection/seal-only stale-token defect is a hard WO-0168b activation hold. Before
WO-0168b source authority is released, its documentation preflight must freeze in one recursively
closed contract:

1. exact unit-of-work input/result/receipt/eligibility types, members, signatures, and terminal
   outcomes, including refused, conflict, replay, commit ambiguity, and double-fault precedence;
2. exact transaction-generation capability object, registry identity, copy/reduction refusal,
   activation/retirement lifecycle, and every normal/exceptional exit;
3. exact BEGIN IMMEDIATE, verification, reducer, write, retire, COMMIT/ROLLBACK ordering;
4. exact source and test `path:function` allowlists plus failure-capable AST/reference mutants; and
5. exact behavior tests proving T1 tokens fail in T2 on the same connection.

That preflight requires a fresh P0=0/P1=0 review before implementation. Until it passes, the
existing `_RuntimeWriteCapability` is explicitly insufficient and unissuable; no M2 runtime
composition or production checkpoint write is authorized. This records the root defect without
inventing WO-0168b result types inside WO-0168c.

WO-0168c W00 is limited to its reachable boundary:

- missing/arbitrary/object-new-with-missing-or-fake-fields/subclass-attempt/wrong-seal/
  cross-connection values fail
  before SQL and cannot impersonate runtime authority;
- an authentic setup token outside an explicit transaction returns `INTEGRITY_FAILURE` with zero
  SQL; and
- only an authentic setup token on its exact connection inside the explicit fresh-fixture
  transaction reaches schema/selection/write SQL.

Static tests retain the existing setup-issuer allowlist and assert no production runtime issuer or
activation/retirement symbol exists before WO-0168b. No test pretends to exercise a legitimate
runtime token.

## 4. Exact fault exception precedence

Only the exact test-only `_InjectedCheckpointFault` and `_InjectedCommitFault` variants named in
R7 F00-F11 propagate unchanged. F09a is an explicit higher-priority translation rule:
`TypeError`, `ValueError`, or `OverflowError` raised while constructing/validating the receipt is
caught and returns `INTEGRITY_FAILURE` with no record. SQLite exceptions follow the exact F01/F03/
F07 classifications. Every other unexpected non-SQL exception propagates unchanged and is not
silently broadened into an outcome. Tests pin this precedence with one exception-swap mutant per
named class.

F10 remains solely the setup-capability caller COMMIT-ambiguity harness. It has no lease assertion
and returns no invented unit-of-work result. Future production commit ambiguity is part of the
mandatory WO-0168b preflight above.

## 5. Stop

REV-0077 must return exact R8 `ACCEPT` with `P0=0/P1=0` before source/test paths are released.
Changed DDL still cannot be installed and no SQLite-bearing test may run before Ameen's exact
candidate approval. No serving authority, second engine, configured/in-memory database,
migration, runtime composition, credentials, network/broker/orders, promotion, or merge is
authorized.
