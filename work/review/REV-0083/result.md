# REV-0083 result — WO-0168c control-completeness review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `546471c86647637a277237a53cf949b66a6a955a`
- Candidate code tree: `f0aedb729b83136a021ce324dc2744ec8ad1325c`
- Prior implementation review target: `7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d`

This result faithfully consolidates two independent fresh-context returns: a
checkpoint-semantic pass and a static pre-open grammar pass. Neither reviewer
opened SQLite, installed DDL, ran a SQLite-bearing test, created a database,
accessed credentials/network/broker/order paths, pushed, or modified files.

## Findings

### [P1] Missing-gate namespace acquisition can evade static classification

- Location: `tests/execution_core/test_persistence_write_capability.py:1196-1206`,
  `:1308-1369`, `:1462-1563`, `:2021-2134`
- Requirement: the held-DLL pre-open control must fail closed for SQLite
  acquisition and accept only the direct canonical grammar.
- Evidence: `static-reasoning`. SQLite-surface detection starts from recognized
  imports/calls. A dynamic or namespace-recovered acquisition that omits the
  canonical accessor can remain outside `_is_sqlite_acquisition_call`, so it
  receives neither a violation nor a dominance check. The candidate proves
  module-instance `__getattribute__`, `globals`, and `sys.modules` only in
  sources that already import the canonical accessor; it does not prove the
  corresponding missing-gate route fails.
- Impact: a future fixture can obtain SQLite through an unrecognized
  namespace/dynamic path before human approval while the audit corpus remains
  green.
- Resolution: recognize direct namespace/dynamic acquisition patterns
  independently of a canonical approval import, while retaining ordinary pure
  module/exception inspection. Add focused missing-gate mutants that assert
  their owning violation.

## Clean semantic pass

The checkpoint reviewer returned **ACCEPT** with `P0=0`, `P1=0`, `P2=0`.
It live-ran the two focused pure controls with cache/bytecode writes disabled.
It confirmed that selected invalidations reconstruct in `(evidence_ordinal,
evidence_id)` order and compare exactly to the current contradiction tuple; the
swapped control reaches that equality. It also confirmed that the claimed
NEVER_DISPATCHED control reaches the selected-claim refusal before lifecycle
validation. SQLite-bearing paths and the static grammar were deliberately out
of that reviewer's scope.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 1
P2: 0

Unverified: changed-DDL installation, all SQLite-bearing suites, broader
runtime composition, and a completed post-remediation independent review.
