# REV-0075 R3 disposition

Author: Codex implementation/orchestrator seat  
Date: 2026-08-23

The two independent R3 findings records are preserved unchanged in
`result-r3-design.md` and `result-r3-test-critic.md`.

## Disposition

- Accepted P1: `CurrentProofSlice` must authenticate every optional direct row that it carries.
  Commit `fd56983c31ce3f103bc981b67adc14a67eea5f04` adds an explicit closed record-binding table,
  validates all selected root/fact/effect/claim/owner/acceptance/closure relationships, and adds
  row-by-row mutation assertions to the existing repository test. It uses neither reflection nor
  a generic persistence codec.
- Accepted P1: the canonical radix child tuple needs duplicate and ordering negative controls.
  The same commit adds a multi-child reordered witness and an XOR-preserving duplicate-label
  witness; both must be refused.
- Accepted P1: issuer provenance needs an admission-boundary control. The same commit mutates only
  a valid slice issuer and proves the checkpoint-codec bridge refuses it.
- Accepted P2: `request-r3.md` is preserved as the historical packet, not rewritten. Its source
  candidate parent `17bacd9d58f251037e989a5a7e20cc9ed9f7b841` has actual tree
  `413f90d2c1ef380444367bb0afec9bd6fc6bf130`; `request-r4.md` carries corrected immutable pins
  for the next review.

## Evidence before R4

Pure evidence at the R3 remediation worktree passed: `test_position.py` (21),
`test_protection.py` (complete suite), `test_persistence_checkpoint_codec.py` (3),
`test_import_boundary.py` (32), and `test_persistence_operations.py` (49), plus Ruff, format,
Mypy (95 app files), and whitespace checks. `test_persistence_repository.py` collected 33 tests;
it was not executed because SQLite-bearing tests remain held for the distinct DDL/test human gate.
The only pytest warning was the pre-existing `.pytest_cache` permission warning.

R4 remains required. This disposition does not close WO-0168a, authorize changed DDL installation,
SQLite execution, runtime composition, external I/O, promotion, or a merge to `master`.

