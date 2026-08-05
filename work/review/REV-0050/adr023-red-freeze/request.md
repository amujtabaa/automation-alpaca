# WO-0148 ADR-023 replacement RED exact-commit review

Review type: independent functional-conformance review of an immutable test-contract candidate

Target commit: `e886fead41dca94e86e666a993f4f976507ece8d`

Authority base: `f528b5dd59a415413e010bb6015364d0094512c4`

Accepted ADR-023 SHA-256:
`898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259`

## Seat and output

Re-derive the candidate from the exact committed tree; do not rely on author reasoning. Review only
and write findings to `result.md` in this folder. Do not edit `request.md`, tests, application code,
governance records, or other evidence.

Return `ACCEPT` only with P0=0 and P1=0. A finding must include exact file/line evidence, why it is
material, and what would resolve it. P2 observations do not block this RED freeze.

## Materiality boundary

P0/P1 is limited to a defect that can affect protection-state authenticity, restart/replay
correctness, bounded memory or work, deterministic reproducibility, execution-goal safety, exact
ADR-023 authority, or the ability of a required control to fail for its named regression. Do not
block on naming, style, preferred refactors, generalized AST variants outside the production
contract, or concerns already excluded by a stronger exact invariant.

## Exact candidate scope

The commit changes only:

- `tests/execution_core/test_protection.py`
- `tests/execution_core/test_protection_stateful.py`
- `tests/execution_core/test_import_boundary.py`
- `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`
- `work/review/REV-0050/replay-retention-successor/ADR-023-RED-PRE-FREEZE-EVIDENCE.md`
- `work/review/REV-0050/replay-retention-successor/ADR-023-RED-PREFLIGHT-DISPOSITION.md`

No application file changes. Production implementation remains barred during this review.

## Required review checks

1. Verify the target and base SHAs, exact six-file diff, ADR hash, active WO, and application-diff
   absence.
2. Reconcile the 504-test contract with ADR-023, including its five exact public transitions,
   derived occurrence identity, 19-part/480-byte cursor, generation/mode and epoch admission,
   cursor-before-context ordering, invalidation/baseline/halt/exhaustion, split reducers, bounded
   state/work, restart deferral, and goal suppression.
3. Confirm production-facing failures are honest structural RED outcomes rather than collection
   errors or unrelated fixture failures, and that semantic paths not reached are labeled as such.
4. Reproduce the focused controls for exact state-commitment sources and bindings, optional cursor
   authentication, repeated branch resets, exact deterministic state shape, bounded fixed leaves,
   invalidation projection authority, canonical digest use, and constructor closure.
5. Verify the replacement RED commit preserves the predecessor suite and introduces no acceptance
   claim for production, M2 recovery-fence provenance, runtime wiring, persistence, or broker work.

Safe text inspection, static analysis, collection, and focused pure tests are allowed. Do not use a
database, SQL/DDL, network, broker, Alpaca, credentials, runtime wiring, deletion, or cleanup.

## Reproducible evidence supplied

- replacement RED: 504 total, 410 intentional failures, 94 passes, 0 errors, 0 skips;
- predecessor execution-core corpus: 745/745 passes;
- focused pre-freeze controls: parent 5/5 and independent delta reviewer 6/6;
- Ruff, format, Python 3.11 AST, mypy (86 application files), diff, scope, install, version, ledger,
  PKL, disposition, application-absence, accepted-ADR hash, and nine auxiliary-worktree gates pass;
- current-worktree material delta verdict before freeze: ACCEPT, P0=0/P1=0/P2=0.

The review must state anything not independently verified. Exact-commit acceptance authorizes only
the next WO-0148 production-implementation gate under the active work order; it does not accept
production or close WO-0148.
