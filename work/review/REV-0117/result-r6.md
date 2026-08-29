### [P1] Owner-mismatch control is preempted by the N+1 check

- Location: `tests/execution_core/test_persistence_unit_of_work.py:3480`
- Requirement: R6 requires failure-capable controls for removal of both the N+1 and exact owner-semantic checks; a stale, forged, wrong-head, regressing, or owner-mismatched checkpoint must remain refused.
- Evidence: `static-reasoning` — the retained context is built from the dormant fixture at checkpoint version N=1 (`test_persistence_runtime_checkpoint_pure.py:312-322`), while `mismatched_owner_projection` is built from the active fixture whose base proof is also issued at version 1 (`test_persistence_startup_hydration.py:450`; `test_persistence_runtime_checkpoint_pure.py:312-322`). `_require_retained_checkpoint_payload` rejects that projection at the earlier `version != expected + 1` predicate (`app/execution_core/persistence/unit_of_work.py:643-644`) before evaluating `_m2_checkpoint_semantics_match` (`:649-652`). Consequently, deleting or bypassing the owner-semantic check still leaves this negative test green; it does not prove that a genuine owner mismatch at the valid retained-N/projected-N+1 boundary fails closed.
- Impact: A regression that removes the owner-component comparison can pass the new R6 direct controls, leaving the core splice/owner-equality guard unproven at the exact successor-proof relationship that this correction admits.
- Resolution: Build the mismatched projection from an authentic successor proof with the same retained application/profile/head coordinates and version N+1, then change only an owner component; assert that this reaches and is refused by the semantic-comparison guard.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0

Unverified: SQLite, fresh-file, and held-test execution were not run as prohibited; the broader six-file pure slice was not rerun.
