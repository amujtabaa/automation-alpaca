# WO-0148 production failure-capability evidence

`[FABLE - FULL - verification: DIRECT fail/restore mutation controls - task: pure position protection]`

## Boundary and restoration contract

All controls were executed against the WO-0148 production working copy based at `HEAD 486b250`.
No broker, credential, network, runtime, persistence, SQL, DDL, or database path was used.
Production mutations changed only the allowed `app/execution_core/protection.py` path. The two M1C
controls used temporary pytest-local monkeypatches inserted into the allowed
`tests/execution_core/test_protection.py` path; `authority.py` was never edited.

Baseline and final values:

- `protection.py` SHA-256
  `6e1dfe6ddf5a3b4d38f1076f631fff4b7c340958ae069f934f27507c513a05fc`;
  Git blob `ba4303f8d6cc110bf589c1d8061c3ab4d507e7b7`.
- `test_protection.py` SHA-256
  `e25fee0bcc6127f353c38e2ab025a2c676b18f0bfa94765dda66dd0a2e082188`;
  Git blob `ff72af868dca367a4784bef68782d42913c61468`.
- Unchanged `authority.py` SHA-256
  `2ff53c9d790615c3594d13e3c08710c15d31c5ebebf661faf8e8bb50f13b8a6e`.

Every listed mutant was applied with `apply_patch`, the exact focused command was run with
`-B -p no:cacheprovider`, the mutant was reversed with `apply_patch`, and the applicable final
hash above was rechecked. Expected outcome for every final control was pytest exit 1 at the named
acceptance assertion.

## Exact controls and decisive results

| ID | Temporary mutation | Exact command | Actual failure |
|---|---|---|---|
| M01 | Replace the first upward conversion numerator with `raw_units.numerator`, rounding a fractional candidate downward. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_fractional_average_rounds_formula_candidates_up_to_the_next_tick` | Exit 1: hard-bail trigger was `92`, expected `93`. |
| M02 | Change the inclusive hard trigger comparison from `<=` to `<`. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_two_distinct_bids_at_the_exact_trigger_activate_hard_bail` | Exit 1: policy stayed `FLOOR_ONLY`, expected `HARD_BAIL`. |
| M03 | Replace `if hard_triggered` with `if False`, allowing the trail path to outrank hard bail. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_hard_bail_outranks_trail_exit_on_the_same_evidence_branch` | Exit 1: policy became `EXIT_NORMAL`, expected `HARD_BAIL`. |
| M04 | Disable the exact occurrence-identity replay branch. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_changed_delivery_context_replay_is_exact_for_every_occurrence_form` | Exit 1: two sequence-less BID/TRADE cases returned `APPLIED`, expected `EXACT_REPLAY`. |
| M05 | Change the non-advancing source-sequence comparison from `<=` to `<`. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_nonadvancing_sequence_does_not_corroborate` | Exit 1: equal sequence changed state and corroborated. |
| M06 | Disable the trigger-change branch reset. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_trigger_ratchet_cannot_reuse_evidence_from_the_old_trigger` | Exit 1: the first observation under the new trigger produced `HARD_BAIL`. |
| M07 | Disable reducer projection-authenticity validation, allowing caller-shaped cursor/closure-like counts. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_reducer_rejects_forged_projection_cursor_execution_and_summary` | Exit 1 in all 10 cases: forged fields returned replay/stale outcomes rather than `REFUSED`. |
| M08 | Force `waiting_buy_resolution = False`, releasing OPEN/INVALIDATED BUY authority. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_buy_wait_is_orthogonal_and_parent_close_not_leg_terminal_releases tests/execution_core/test_protection.py::test_late_acceptance_invalidates_release_and_preserves_normal_policy` | Exit 1 in both cases: waiting was false while BUY authority remained unresolved/invalidated. |
| M09 | Disable preservation of prior `EXIT_NORMAL` through an economic/wait transition. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_buy_wait_is_orthogonal_and_parent_close_not_leg_terminal_releases` | Exit 1: terminal-only transition regressed to `FLOOR_ONLY`. |
| M10 | Ignore `blocking_effect_count` in flat readiness. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_flat_requires_zero_quantity_and_closed_buy_and_sell_parents` | Exit 1: zero quantity with a live SELL attempt became `FLAT`. |
| M11 | Treat `late_positive` as flat-ready. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_late_owned_buy_after_flat_restores_hard_bail_and_alert` | Exit 1: positive quantity after flat remained `FLAT`. |
| M12 | Treat any available average as valid formula authority, ignoring candidate/basis compatibility. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_formula_loss_discards_market_evidence_and_restores_a_fresh_branch` | Exit 1: rounding-unavailable economics retained `formula_available=True`. |
| M13 | Ignore `OVERFILL_QUARANTINE` when deriving formula authority. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_positive_broker_overfill_cannot_emit_after_trigger_shaped_evidence` | Exit 1 at the intended boundary: a SELL `ExecutionGoal(residual=5)` was emitted. |
| M14 | Disable the same-epoch halt latch. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_source_time_regression_and_halt_reopen_start_fresh_branches` | Exit 1: same-epoch evidence mutated the halted state. |
| M15 | Disable primary-price step eligibility across BID and TRADE. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_cross_kind_market_step_limit_uses_the_last_eligible_primary` | Exit 1 in both BID-to-TRADE and TRADE-to-BID cases: the oversized step changed state. |
| M16 | Test-local monkeypatch `authority._create_gate_reason` to return `None`. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_goal_translation_remains_subject_to_m1c_create_and_claim_gates` | Exit 1: kill-gated creation returned `APPLIED`, expected `REFUSED`. |
| M17 | Test-local monkeypatch `authority._claim_gate_reason` to return `None`. | `.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py::test_goal_translation_remains_subject_to_m1c_create_and_claim_gates` | Exit 1: kill-gated final claim returned `APPLIED`, expected `REFUSED`. |

## Survivor-driven test-strength corrections

The initial M01 selection,
`test_nonunit_tick_rounds_each_trail_candidate_once_and_forgets_missing_inputs`, passed under the
downward-rounding mutant because every pre-tick candidate in that example was already integral.
`test_fractional_average_rounds_formula_candidates_up_to_the_next_tick` now uses an exact
`100.5` average and pins upward results `93` and `109`; M01 then fails at `92`.

The initial M02 selection,
`test_hard_bail_outranks_trail_exit_on_the_same_evidence_branch`, passed under a `<=` to `<`
mutant because its observations were strictly below the trigger.
`test_two_distinct_bids_at_the_exact_trigger_activate_hard_bail` now pins the inclusive boundary;
M02 then remains `FLOOR_ONLY` and fails.

The earlier positive-overfill test killed M13 at policy classification before reaching goal
creation. The dedicated `test_positive_broker_overfill_cannot_emit_after_trigger_shaped_evidence`
now runs the quarantined history through trigger-shaped evidence and proves the mutant emits the
forbidden SELL goal.

These are test-strength corrections only. Production behavior did not change for M01, M02, or M13.
The two permanent tests pass on the restored production source.

## M1C predecessor boundary

Current `authority.py` exactly matches the accepted WO-0147/REV-0049 digest, and fresh composition
tests cover create-time kill/fence plus final-claim kill/fence without venue, claim, or budget
mutation. Existing REV-0049 mutation evidence directly covered exact Boolean validation, not
removal of the actual create/final-claim gate functions. M16 and M17 close that proof gap without
editing the WO-0148-forbidden predecessor source: pytest temporarily replaced each live private
classifier at runtime from the allowed protection test, observed the intended composition test
fail, automatically restored the runtime binding, then restored the test file exactly.

No prohibited predecessor edit or inherited mutation claim is used.
