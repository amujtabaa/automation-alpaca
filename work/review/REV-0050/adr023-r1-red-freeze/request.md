# WO-0148 ADR-023 amendment R1 replacement RED exact-commit review

Review type: independent functional-conformance review of an immutable test-contract delta

Target commit: `7e0b869c852b66a6744b447429f4bf0eca756b5b`

Exact parent/base: `f8367944a156150bb362913ac52ae40f85d68526`

Approved amendment proposal SHA-256:
`F0403B87770648DE233575CE29D853327FD0B48559CE032B4CEF529A6EFE34E9`

Resulting amended ADR-023 SHA-256:
`9A61D4F952079B5F78DA7A8F1A17F70DC3099D20FB359596923C5938CC421EAF`

## Seat and output

Re-derive the exact delta from the committed tree. Review only. Write findings to `result.md` in
this folder and edit no other file. Do not edit `request.md`, tests, application code, governance
records, or retained evidence.

Return `ACCEPT` only with P0=0 and P1=0. Each finding must identify exact file/line evidence, why it
is material, and the smallest resolution. State anything not independently verified.

## Materiality boundary

P0/P1 is limited to a defect that can affect exact ADR/amendment authority, protection-state
authenticity, restart/replay correctness, bounded memory or work, deterministic reproducibility,
execution-goal safety, or the ability of a required regression control to fail for its named
defect. Naming, style, preferred refactors, generalized AST forms outside the production contract,
and concerns already excluded by a stronger exact invariant are non-blocking.

This is one bounded exact-delta gate, not a general re-review of the already accepted ADR-023 RED
contract or predecessor implementation.

## Exact candidate scope

The target changes only:

- `docs/adr/ADR-023-bounded-market-occurrence-authority.md`
- `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`
- `pkl/architecture/architecture-map.md`
- `pkl/log.md`
- `pkl/project/goals.md`
- `tests/execution_core/test_import_boundary.py`
- `tests/execution_core/test_protection.py`
- `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`
- `work/review/REV-0050/adr023-green-feasibility/ADR-023-R1-RED-FREEZE-EVIDENCE.md`

No `app/**` file changes. Production implementation remains barred during this review.

## Required checks

1. Verify target, sole parent, exact nine-file path set, clean committed diff, active-WO scope, and
   application-diff absence.
2. Rehash the approved proposal and amended ADR. Confirm the ADR has only the approved retained-
   state text replacement and that ratification/WO/PKL records reconcile it without overstating
   acceptance.
3. Re-derive both RED corrections:
   - retained `_market_last_primary` is exact `ReportedPrice | None` solely for the next maximum-
     step comparison; absent cursor part 13 stays absent and a present value uses the existing
     canonical reported-price commitment; the cursor remains 19 parts/480 bytes and bounded;
   - only canonical private `dataclasses.field` binding and exactly `_field(init=False)` on
     `MarketOccurrence.occurrence_id` are admitted; broader aliases, rebinding, arguments,
     annotations, classes, fields, and call sites remain rejected.
4. Reproduce the four focused failure-capability controls named in the evidence. Inspect their
   direct mutants and confirm each can fail for its stated defect.
5. Verify the retained JUnit hashes and metadata: corrected RED 505 total / 410 intentional
   structural failures / 95 passes / 0 errors / 0 skips; predecessor 745/745 passes. Confirm the
   predecessor selector excludes exactly the three ADR-023 contract files. A full rerun is required
   only if the artifacts, hashes, collection, or sampled behavior are inconsistent.
6. Re-run proportionate static checks for the exact delta: Ruff lint/format for changed Python,
   Python 3.11 grammar parse, `git diff --check`, and scope/application-absence checks.

## Execution boundary

Text inspection, static analysis, collection, and focused pure tests are allowed. Do not use SQL or
DDL, a database engine, persistent application data, broker or Alpaca services, network access,
credentials, runtime wiring, M2 implementation, master merge, deletion, or cleanup.

Exact-commit acceptance authorizes only the next WO-0148 production-implementation gate under the
active work order. It does not accept production behavior or close WO-0148.
