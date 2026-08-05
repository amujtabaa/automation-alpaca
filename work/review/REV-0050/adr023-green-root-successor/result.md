# WO-0148 position-local pre-exposure root-successor exact-delta review

No findings.

## Evidence reproduced

- Exact immutable boundary: parent `2982048b3247e0c9cee5c9988b77fc43cd208235`, candidate and `HEAD` `e9c2d58a8f16d2b3457dad5e4c5ed04ca24073ae`. The delta contains only the five paths named by the request, and `git diff --check` passes. Unrelated untracked artifacts were ignored and preserved.
- Static authority chain: `PositionState.root_count` is derived from that exact position's immutable root sequence; the position commitment binds the root-sequence commitment, and coherent `ExecutionSnapshot` construction requires position/root-head count and sequence identity. The venue proof binds the exact position and root-head commitments. `project_protection_venue` verifies that proof/checkpoint chain, derives `position.root_count`, and binds it into the private projection factory and `execution-core/protection-venue-projection/v3` seal. The exhaustive projection-leaf mutation control rejects a changed root count before reduction.
- Lifecycle distinction: pre-exposure now requires zero raw quantity, zero roots for the same position, and either no prior state or retained pre-exposure provenance. Foreign-symbol registry catch-up does not create a target-position root. A same-position root survives a bust to zero, and the sticky `HARD_BAIL` guard excludes only genuine pre-exposure. True `FLAT`, formula-loss/restoration, pending basis, reconciliation, positive/negative overfill, and the three multi-scope kill/catch-up histories retain their fail-closed behavior.
- Required concrete controls: 4/4 critical lifecycle tests passed. A separate 10/10 restriction, lifecycle, predecessor-continuity, projection-seal, and multi-scope set passed.
- Failure capability: an in-memory substitution of account-registry count for position-root count made `test_cross_scope_registry_catch_up_preserves_prefill_until_first_owned_fill` fail. Independently restoring the pre-correction `prior.raw_quantity > 0` sticky-policy guard in memory made `test_fill_bust_to_zero_then_correction_remains_hard_bail` fail. Both probes ran in isolated processes and did not edit source files.
- Complete bounded suite: `test_protection.py`, `test_protection_stateful.py`, and `test_import_boundary.py` passed 513/513 in 97.1 seconds; collection reconciled to 451 + 35 + 27.
- Static gates: Ruff lint passed; all three candidate Python files were already Ruff-formatted; mypy passed all 86 application files; Import Linter kept 6/6 contracts over 122 files and 621 dependencies; Python 3.11 grammar parsing passed all three changed Python files.
- Restoration/preservation: candidate SHA-256 values reverified exactly as `F6161F16CF7D900EA4851A06121301B14E5648BA45CC2519460DD90D292CAE9D`, `521B2BF0A9A2D2CC4B438482B0965E5A8D05576AEE300F11C113919663787DAE`, and `1488E98A2DD6424892FF143916B062102AA8932ABD0514B071E28D75F28C94FC`. No tracked implementation or test file changed during review.
- Scope: no public protection field/function, caller-shaped authority, variable history, I/O, runtime wiring, persistence, database/SQL, broker/Alpaca, network, credential, M2, merge, deletion, or cleanup surface was added or exercised.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: the broader 1,258-test execution-core claim was not independently rerun because the request called for a bounded exact-delta review and the complete 513-test affected suite plus the required counterfactuals resolved the material determination. R2/full-repository gates, exact-head Python 3.11/3.12 CI, and deferred runtime/persistence/broker surfaces remain outside this review and were not exercised.
