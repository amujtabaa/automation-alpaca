# REV-0117 R6 finite retained-checkpoint correction review — WO-0169

Date: 2026-08-29

Status: **FRESH EXACT-HEAD REVIEW REQUIRED**

## Exact binding

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Instrumented-diagnosis base: `4791e780938084637c1c11f5a1896f97d3d9651d`.
- Exact correction candidate: `ecee243d5627d06a55f7de1b89c59b9982e253fd`.
- Candidate tree: `1f35f8204ebab2356885aea17ef19d2748e220b3`.
- Effective review range:
  `4791e780938084637c1c11f5a1896f97d3d9651d..ecee243d5627d06a55f7de1b89c59b9982e253fd`.
- `app/execution_core/persistence/unit_of_work.py` SHA-256:
  `12bb7ad3d25f1de23829010bf50bb5cb0ce26896f4696b200dd2744b8079295c`.
- `tests/execution_core/test_persistence_unit_of_work.py` SHA-256:
  `57c8c573e64dafbf997ea70acfcbec69bb30cec6eb0dcf60b599be66c8ee6f16`.
- Active work-order SHA-256:
  `30ed4dacfde4e9d50545a40fc0b19aeee7a714c4166757e1d6c93a15e755a929`.

This request file is a later documentation-only commit and is outside the reviewed candidate tree.

## Root defect and bounded correction

The authorized instrumented diagnosis reproduced the erased inner refusal on a copy of the R3
pytest-owned database. `_prepare_transaction` loaded the exact retained checkpoint at version N,
then correctly projected the same owners through the repository-selected successor proof at N+1.
The old guard compared those whole payload bytes for equality. That comparison necessarily failed
because checkpoint version is part of the canonical payload even though all six owner components
were byte-identical.

The correction keeps the exact loaded-envelope and projected-envelope authenticity boundaries but
separates predecessor identity from owner equality:

1. the retained `LOADED` envelope must match the expected application, currentness ordinal,
   checkpoint version, and payload digest exactly;
2. the authentic `PROJECTED` envelope must be the exact next checkpoint version and cannot regress
   currentness; and
3. the existing `_m2_checkpoint_semantics_match` comparator must match every retained venue,
   authority, position-scope, acquisition, execution, and protection owner component while
   deliberately ignoring successor metadata.

The former fake byte carrier test is replaced with codec-issued projected and loaded envelopes.
The controls prove the valid retained-N / projected-N+1 relationship; reject absent or non-loaded
retained records, loaded projections, predecessor-at-N projections, every expected-head mismatch,
and a genuine different owner set; and drive the complete `_prepare_transaction` repository path
with an authentic retained predecessor and successor proof.

## Evidence available to reproduce

- The three direct authentic controls pass.
- The six source-confirmed pure modules pass: `552 passed in 28.46s`.
- Exact final ordinary suite: `2266 passed in 721.27s (0:12:01)`.
- Ruff check and format-check pass on both changed Python files.
- Mypy passes all 99 application source files.
- Install, version consistency, ledger, PKL, disposition, work-order scope, and whitespace checks
  pass.

Protected identities are unchanged:

- `SCHEMA_DDL`: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- Held-test blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

## Finite review request

Review only this correction and verify:

1. the guard admits the intended retained-N / projected-N+1 relationship without accepting a
   stale, forged, wrong-head, regressing, or owner-mismatched checkpoint;
2. the application-level correction is placed at the owning boundary and does not weaken exact
   current proof, transaction atomicity, fail-closed startup, or checkpoint no-op refusal;
3. the authentic tests are failure-capable for the old whole-payload comparison and for removal of
   the N+1 or owner-semantic checks; and
4. the correction remains in scope and changes no DDL, schema API, held test, human flag, public
   UOW surface, or accepted startup architecture.

Do not reopen unrelated accepted WO-0169 design or earlier closed findings. Run only the three
direct controls or the six-file pure slice if useful. Do not import or execute SQLite, create a
database, run the held test, or edit implementation files. Return findings only with exact P0/P1/P2
counts and `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. The reviewer-owned result path is
`work/review/REV-0117/result-r6.md`.
