# REV-0082 result — WO-0168c invalidation and gate-provenance review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d`
- Candidate code tree: `bd0274f086c8d156bad6b6e1fc5fb45c43980df8`
- Review range: `9984232fcc6fce9b9261798858262e529c3729e2..7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d`

This result faithfully records two independent fresh-context review returns:
one checkpoint-semantic pass and one source-grammar pass. Both were pure/static
only. No SQLite connection, DDL installation, database-bearing test, runtime
composition, credential, network, broker, or order path was used.

## Findings

### [P1] Invalidation ordering has no failure-capable control

- Location: `tests/execution_core/test_persistence_runtime_checkpoint_pure.py:2295`
- Requirement: R20 §2 / R17 proof-selected ordering; REV-0081 test-critic pass.
- Evidence: `static-reasoning`. The new control creates only one selected
  invalidation row, so it proves membership but cannot distinguish a reordered
  runtime contradiction tuple.
- Impact: a regression accepting a reordered tuple could remain green.
- Resolution: construct two distinct selected invalidations; prove matching
  ordinal order succeeds and a swapped runtime tuple fails.

### [P1] NEVER_DISPATCHED selected-claim refusal lacks a checkpoint-boundary control

- Location: `tests/execution_core/test_persistence_runtime_checkpoint_pure.py:2405`
- Requirement: a NEVER_DISPATCHED closure is cancellation-only and claim-free
  under the selected durable relation.
- Evidence: `static-reasoning`. The current control uses a no-claim selection,
  so it tests cancellation state but not the selected-claim branch.
- Impact: weakening the selected-claim refusal could permit a claimed
  NEVER_DISPATCHED checkpoint without failing the new control.
- Resolution: add a canceled current effect plus forged selected claim and
  NEVER_DISPATCHED proof; require the selected-claim refusal.

### [P1] The source audit misses SQLite acquisition routes outside direct `sqlite3.connect`

- Location: `tests/execution_core/test_persistence_write_capability.py:1055`,
  `:1285-1305`, `:1448-1466`
- Requirement: the human approval must dominate every SQLite connection and
  indirect routes must fail closed.
- Evidence: `static-reasoning`. The audit does not model nested static SQLite
  imports or non-`connect` acquisition constructors such as
  `sqlite3.Connection(path)`.
- Impact: a held fixture could open SQLite without the approval accessor.
- Resolution: recognize or refuse every SQLite-rooted acquisition expression,
  including nested static imports and constructors, with isolated mutants.

### [P1] Dynamic and namespace-recovered SQLite routes remain outside the grammar

- Location: `tests/execution_core/test_persistence_write_capability.py:1129`,
  `:1179-1207`, `:1397-1466`
- Requirement: direct runtime dominance must survive dynamic imports, namespace
  recovery, and function-local import paths.
- Evidence: `static-reasoning`. Dynamic target recognition is literal-only;
  function-local dynamic imports and module namespace recovery are not fully
  modeled.
- Impact: a dynamically or namespace-recovered connection can bypass the
  pre-open check.
- Resolution: fail closed on dynamic import and namespace recovery used to
  obtain a connection callable, including nonliteral and function-local paths.

### [P1] Approval provenance can be mutated through namespaces outside ordinary rebinding

- Location: `tests/execution_core/test_persistence_write_capability.py:110`,
  `:1171-1178`, `:1397-1425`
- Requirement: approval access must have a single un-rebound,
  human-controlled provenance boundary.
- Evidence: `static-reasoning`. Ordinary stores/imports are detected, but
  wildcard imports and mutable namespace/module routes are not fully refused.
- Impact: an apparent canonical accessor can be made to return a forged digest
  before the connection opens.
- Resolution: permit only exact bare accessor calls at approved positions and
  refuse wildcard, mutable namespace/module, and accessor attribute/subscript
  recovery, with focused mutants.

### [P2] Bound unrelated installer methods can still be false positives

- Location: `tests/execution_core/test_persistence_write_capability.py:1485`
- Requirement: the audit governs only canonical schema-installer provenance.
- Evidence: `static-reasoning`. A noncanonical bound `.install_schema` method
  that is merely retained is treated as an escape.
- Impact: unrelated non-SQLite fixtures can be blocked by a generic method
  name.
- Resolution: apply schema-module provenance to the attribute-escape branch
  and add a passing unrelated bound-method control.

### [P2] New grammar mutants do not cover every claimed bypass family

- Location: `tests/execution_core/test_persistence_write_capability.py:1785`
- Requirement: WO-0168c requires failure-capable bypass controls.
- Evidence: `static-reasoning`. Several nested/static/dynamic/namespace and
  timing forms have no route-specific mutant.
- Impact: recognition-branch regressions can remain green.
- Resolution: add one focused mutant per admitted recognition branch and
  assert its owning diagnostic; retain unrelated-source positive controls.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 5
P2: 2

Unverified: changed-DDL installation, all SQLite-bearing suites, repository and
load behavior, query plans, runtime composition, and a completed
post-remediation review are deliberately not run.
