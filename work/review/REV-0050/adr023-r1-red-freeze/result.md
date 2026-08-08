# ADR-023 amendment R1 replacement RED exact-commit review

Review target: `7e0b869c852b66a6744b447429f4bf0eca756b5b` over exact sole parent
`f8367944a156150bb362913ac52ae40f85d68526`

### [P1] The passive dataclass seal rejects the required derived identity field

- Location: `tests/execution_core/test_protection.py:2688`,
  `tests/execution_core/test_protection.py:2725`,
  `tests/execution_core/test_protection.py:2734`, and
  `tests/execution_core/test_protection.py:4856`
- Requirement: Ratified ADR-023 amendment R1 requires exactly
  `MarketOccurrence.occurrence_id: _MarketOccurrenceId = _field(init=False)`. The replacement RED
  contract must admit that honest production shape while continuing to reject broader field uses.
- Evidence (`reproduced-live`): `_assert_passive_dataclass_metadata` unconditionally requires every
  retained field's `init` metadata to be `True`, requires `__match_args__` to equal all field names,
  and builds its behavioral reference with every field constructor-initialized. The public-value
  shape test applies that helper to `MarketOccurrence`. A fresh in-memory standard dataclass with
  the required `occurrence_id = field(init=False)` shape had `occurrence_id.init == False` and
  `__match_args__ == ('source_id',)`, then failed this helper. This contradicts the separate exact
  runtime pins at `tests/execution_core/test_protection.py:5682` and
  `tests/execution_core/test_protection.py:16718`, which correctly require
  `occurrence_field.init is False`. The four named R1 failure-capability controls passed 4/4, but
  none exercises the required field shape through this generic public-value seal.
- Evidence (`reproduced-live`, bounded reconciliation): the target has the exact sole parent and
  exact nine-file path set, no `app/**` delta, a clean tracked worktree, `SCOPE CHECK PASSED`, and
  `git diff --check` passed. The approved proposal and amended ADR rehashed to
  `F0403B87770648DE233575CE29D853327FD0B48559CE032B4CEF529A6EFE34E9` and
  `9A61D4F952079B5F78DA7A8F1A17F70DC3099D20FB359596923C5938CC421EAF`; applying the sole
  approved retained-state replacement to the parent ADR reproduced the target ADR exactly. The
  retained JUnit files rehashed to their recorded values and contained 505 cases / 410 failures /
  95 passes / 0 errors / 0 skips and 745/745 predecessor passes. Fresh collection reproduced 505
  focused tests and 745 predecessor tests while excluding exactly `test_import_boundary.py`,
  `test_protection.py`, and `test_protection_stateful.py`. Ruff lint/format and Python 3.11 grammar
  parsing passed for both changed Python files.
- Impact: An implementation that uses the only ratified standard-library form for the derived
  occurrence identity will necessarily fail the complete public-value contract. The replacement
  RED freeze therefore remains internally contradictory and cannot serve as an implementable
  production gate.
- Resolution: Make the passive metadata helper accept an exact per-field `init` inventory, generate
  its reference dataclass with the same field metadata, and require `__match_args__` to contain only
  constructor fields. Pass the one-field exception only for
  `MarketOccurrence.occurrence_id`; add a direct negative control proving any other `init=False`
  field or omission of the required exception still fails.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: Full execution of the 505-test RED classification and 745-test predecessor corpus was
not repeated because their exact artifacts, metadata, fresh collections, selector, and sampled R1
controls were consistent. Actual Python 3.11 execution was not available locally; the two changed
files passed Python 3.11 grammar parsing under Python 3.12.13.
