# WO-0151 R13-R1 clean records-only activation disposition

Status: **PENDING INDEPENDENT RECORDS-ONLY ACCEPTANCE**

## Accepted semantic authority

The user ratified the unchanged R13 contract SHA-256
`240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90`,
clean R13-R1 semantic manifest SHA-256
`c05cddbc4d6d7d7cede2b893d6a3b287791eb25adc3015f7181fda5629fc9222`,
and independent R13-R1 result SHA-256
`71b7ff74f62bdc64f7f25cff5f8b047a30d82ebad961c0e2cdeb48f16638d1a5`
after `ACCEPT` at P0=0/P1=0/P2=0.

This disposition changes no R13 semantics. It exists only to publish the
clean semantic packet and reconcile the exact source/test activation boundary.

## Retained format-blocked evidence

The original R13 semantic manifest SHA-256
`923b23945627e87372e0f9d6e28255247cb3cbaaa4637b9a2cdb272425a5ec95`
and original R13 activation manifest SHA-256
`cb1b58234630e695be61a9c3418accef51281df55842c1d119d83d9e1e2c7e9d`
each retain one historical Markdown hard-break. They and their original
activation packet remain byte-stable, untracked historical evidence. They
must not be normalized, staged, rewritten, or used to satisfy this clean
activation gate.

## Two-commit activation sequence

The first commit is documentation-only. It may contain only:

- the seven current WO/PKL/ledger/ratification records named by the clean
  activation manifest;
- the clean-stageable original R13 semantic disposition, contract, request,
  and independent result;
- the clean R13-R1 format disposition, semantic manifest, request, and result;
- this clean activation disposition, its manifest and request, and the
  reviewer-owned clean activation result after independent acceptance.

The first commit contains no `app/`, `tests/`, `.github/`, ADR-body, runtime,
database, or operational change. It records the semantic ratification and the
still-inactive activation boundary.

The second commit may change only the seven current records to substitute the
exact first publication SHA and to activate the frozen R13 source/test scope:

- `app/execution_core/venue.py`;
- `app/execution_core/authority.py`;
- `app/execution_core/acquisition.py`;
- `tests/execution_core/test_acquisition.py`;
- `tests/execution_core/test_import_boundary.py`;
- directly necessary R13 evidence/current records; and
- the named authority, venue, and protection regression suites as execution
  evidence, with edits only if a genuine in-scope root defect requires them.

No R13 source/test implementation begins until the first commit has published
successfully and the second commit has reconciled its exact SHA. WO-0152 stays
ACTIVE/PAUSED and its frozen B-first-fill detector remains unchanged and
unstaged until R13 implementation independently accepts.

## Preserved exclusions

This activation adds no public API, runtime wiring, persistent database or
SQL/DDL work, credentials, broker/Alpaca/network activity, M2, master merge,
pull request, deletion, cleanup, force-push, rebase, coverage-threshold
reduction, exclusion, pragma, or CI-workflow change. Paired exact-head Python
3.11/3.12 success at the unchanged 93% threshold remains mandatory.
