# Independent exact-delta review - ADR-023 derived-identity lifecycle successor

Review target: `0dd1d0d7fcee56fa71b058a0bcc895886ce39790..1d015ff41102a46a7a23e078220a3df763062c59`

The parent and candidate objects exist, the candidate has the stated parent, the immutable delta
contains only the three declared paths, and `git diff --check` is clean. The candidate lifecycle
recognizer admits the exact ordered preimage/setter tail and its composed passive-prefix check
rejects the fourteen declared wrong-shape, reordering, rebinding, duplication, unrelated-work, and
trailing-work variants. The replay/stale corrections follow ADR-023's exact-current-before-lower-
coordinate ordering, and the cross-kind example now establishes an eligible primary relative to
the fixture's retained 100-unit baseline before testing the rejected one-unit cross-kind step.

## [P1] A complete module can omit the derived-identity lifecycle without a setter violation

- **Location:** `tests/execution_core/test_import_boundary.py:2969-2978` and
  `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:1405-1408`
- **Requirement:** ADR-023 requires `MarketOccurrence` itself to derive its non-init identity, and
  this successor must remove synthetic-fixture false positives without broadening the complete
  import/effect boundary or admitting a missing/malformed lifecycle.
- **Evidence (`reproduced-live`, immutable candidate object):** Loading
  `_protection_write_effect_violations` directly from the candidate and checking a synthetic module
  with exact `MarketOccurrence.occurrence_id = _field(init=False)`, no `__post_init__`, and
  `require_complete=True` produced `derived_setter_violations=0`. Static inspection explains the
  result: line 2976 requires exactly one setter only after a method already named
  `MarketOccurrence.__post_init__` is present. Omitting or renaming that method disables the setter
  cardinality rule. This is broader than needed to let the unrelated complete-grammar module pass
  (it has no `MarketOccurrence`) and the standalone field fixture pass (it does not request a
  complete grammar).
- **Impact:** Other functional identity tests are likely to reject the current production class if
  its lifecycle disappears, so this is not evidence of an accepted production bypass. It is a
  concrete hole in the claimed complete static boundary and leaves no failure-capable control for
  lifecycle omission/renaming. The work-order statement that malformed lifecycle setters still
  fail is therefore incomplete as a proof claim.
- **Resolution:** Require one exact setter when an exact derived occurrence field/class is present
  in `require_complete` mode, or when the exact lifecycle is present in a focused fragment. Keep no
  setter requirement for a complete synthetic module with no occurrence class and for the
  non-complete standalone field fixture. Add direct omission and renamed-lifecycle mutants beside
  the existing positive and wrong-setter controls.

## [P1] The exit-provenance case changes the current cursor and cannot prove independent binding

- **Location:** `tests/execution_core/test_protection.py:4353-4360`,
  `tests/execution_core/test_protection.py:11899-11911`, and
  `tests/execution_core/test_protection.py:11992-12011`; the corresponding claim is at
  `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:1413-1414`.
- **Requirement:** ADR-023 requires the main commitment to bind each cursor and provenance field
  separately; the test explicitly claims to bind each retained authority independently. A control
  for `_exit_provenance` must be able to fail when that field is omitted while all other committed
  inputs remain equal.
- **Evidence (`static-reasoning`):** The `exit_provenance` branch now changes the second
  occurrence's `source_time` and `evaluation_time`. Source time is part of occurrence identity, and
  source time, evaluation time, and occurrence identity are all independently retained cursor
  inputs. The final commitment must therefore differ even if `_exit_provenance` is not committed.
  The branch cannot distinguish the named defect.
- **Evidence (`reproduced-live`, dirty-application corroboration only):** With the candidate tests
  and the excluded working-tree application, the revised fixture changed `commitment`,
  `_market_source_time`, `_market_evaluation_time`, `_market_occurrence_identity`,
  `_hard_bid_identity`, `_hard_bid_source_time`, and `_exit_provenance`. A focused alternative using
  the already-supported `first_bid=93` versus `first_bid=92` while keeping the second occurrence
  identical changed only `commitment` and `_exit_provenance`. The application result is
  corroboration, not immutable candidate authority.
- **Impact:** The suite is green, but the named runtime sensitivity case would remain green after
  an exit-provenance commitment omission because another committed cursor input guarantees the
  observed digest difference. The successor replaces a discarded-label assumption with a real
  difference, but not with a failure-capable independent proof.
- **Resolution:** For the `exit_provenance` parameter, vary only the first corroborating immutable
  occurrence (the existing `first_bid` fixture parameter is sufficient) and keep the final/current
  occurrence identical. Assert `_exit_provenance` differs and every other retained state field is
  equal before asserting the commitment differs. Retain or add a focused mutation control that
  removes the exit-provenance commitment part and proves this case fails.

## Reproduced evidence

- `tests/execution_core/test_protection.py`: 446 collected, 446 passed.
- `tests/execution_core/test_protection_stateful.py` plus
  `tests/execution_core/test_import_boundary.py`: 62 collected, 62 passed.
- A 32-case focus covering the complete synthetic effect grammar, derived field/setter controls,
  lifecycle-tail mutants, replay/stale corrections, cross-kind step case, and commitment
  sensitivity passed.
- Ruff lint and format checks passed for both changed Python files; the working-tree copies of all
  three reviewed paths exactly match the candidate object.

The test executions above used the explicitly excluded uncommitted application implementation and
are corroboration only. Findings are derived from the immutable test/work-order delta and focused
candidate-object static checks.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 2
- P2: 0

Unverified: the author's exact 34-test selector was not available as a retained command, although
both larger suites containing the changed controls reproduced green. Exact-head Python 3.11/3.12
CI and the uncommitted application implementation are outside this immutable review boundary.
