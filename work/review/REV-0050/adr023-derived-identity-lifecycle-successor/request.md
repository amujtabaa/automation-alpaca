# ADR-023 R1 derived-identity lifecycle successor review

## Immutable review boundary

- Parent: `0dd1d0d7fcee56fa71b058a0bcc895886ce39790`
- Candidate: `1d015ff41102a46a7a23e078220a3df763062c59`
- Exact candidate paths:
  - `tests/execution_core/test_import_boundary.py`
  - `tests/execution_core/test_protection.py`
  - `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`

Review only the immutable parent-to-candidate delta. The local working tree contains uncommitted
application implementation and preserved unrelated artifacts; neither is candidate evidence.

## Required independent determination

Re-derive whether the successor closes the sole P1 in the preceding exact-delta review without
broadening the passive-lifecycle or import-boundary rules. In particular, verify that only the exact
ordered `MarketOccurrence.__post_init__` preimage binding and derived identity setter are admitted;
wrong inputs, ordering, receiver, target, constructor, digest, duplication, rebinding, unrelated
assignment, and trailing work must remain refused. Confirm that unrelated synthetic complete-
grammar modules and the standalone `_field(init=False)` fixture are not incorrectly required to
provide a lifecycle setter.

Review the three aligned contract corrections for source fidelity: current exact derived identity
versus lower non-current coordinate disposition, the cross-kind step example's first admissible
primary relative to the recovery baseline, and the exit-provenance fixture's use of a genuine
immutable occurrence difference. Determine whether any change weakens a production obligation or
merely removes a contradictory/ineffective test assumption.

Author-side claims to reproduce rather than trust are: 34/34 focused checks, 446/446 complete pure
protection tests, 62/62 stateful plus import-boundary tests, Ruff lint/format, and clean diff. Use
only pure file/static/test execution; do not run database, SQL, broker, network, credential, runtime
wiring, M2, merge, deletion, or cleanup activity.

Write findings only to `result.md`. Each finding must include severity, file and line, concrete
production or proof impact, and the smallest root correction. End with `ACCEPT`,
`ACCEPT-WITH-CHANGES`, or `BLOCK`, explicit P0/P1/P2 counts, and anything not verified. Do not edit
`request.md`, application code, tests, ADRs, PKL, ledger, or the work order.
