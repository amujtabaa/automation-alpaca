# WO-0148 ADR-023 immutable application acceptance review

### [P1] Pre-fill initialization prevents the first fill from arming `FLOOR_ONLY`

- Location: `app/execution_core/protection.py:1278` (public admission path at `app/execution_core/protection.py:2401`)
- Requirement: ADR-021 requires the protection mandate to exist before a BUY effect and requires that BUY's first fill to activate `FLOOR_ONLY`; WO-0148 clause 3 likewise requires a positive exact-basis first fill to arm `FLOOR_ONLY` after economics.
- Evidence: `reproduced-live`. I initialized protection from a genuine mandate-bound `RequestedEffect` venue transition while canonical quantity was zero, advanced the same state through claim, unknown transport, leg discovery, `NEEDS_REVIEW`, and then a canonical first BUY fill of 4 @ 100. The public reducers reported:

  ```text
  initialized HARD_BAIL 0 False
  first_fill APPLIED HARD_BAIL 4 True None
  ```

  The initial zero state takes the `raw_quantity <= 0` / formula-loss path. When the first valid fill arrives, the prior formula-loss provenance at line 1278 forces `HARD_BAIL` even though the resulting quantity and basis are positive and formula authority is valid. The 509-test focused suite is green because `test_first_owned_fill_arms_only_its_exact_mandate_after_economics` initializes only from the already-filled projection; it does not exercise the public pre-fill lifecycle.
- Minimal counterexample: `VenueRecoveryBook.empty` + flat execution -> mandate-bound BUY `RequestedEffect` -> `project_protection_venue` -> `initialize_position_protection` -> ordinary claim/unknown/discovery/review transitions -> first canonical BUY fill -> `reduce_position_protection`. No caller-authored closure, readiness, formula, or execution-eligibility flag is involved.
- Impact: A later authorized integrator can naturally initialize the public protection state when the approved mandate becomes bound, before the first partial fill. That position then never enters ordinary floor/trail policy: favorable evidence cannot activate trailing because activation is restricted to `FLOOR_ONLY`, and the state remains restricted until a hard-bail branch gains real exit provenance or the position becomes flat. This is a material capital-policy deviation and produces no critical alert.
- Resolution: Make pre-exposure initialization structurally inadmissible (for example, reject authentic zero-quantity initialization and retain only the mandate until the first economic projection), or introduce separately approved reducer-owned pre-fill state authority. Add a real venue-chain test that initializes before the BUY fill and proves the first positive exact-basis fill becomes `FLOOR_ONLY`; retain separate fail-closed cases for pending basis, reconciliation, and overfill.

## Evidence reproduced

- Exact target: `HEAD=629ffaa3f9a93ce2cc44ba38197f2ed8428cc11d`; merge base with `4c420e1e9323bf881683ddc197758535b5638519` is the declared parent; the five changed paths exactly match the request; tracked state was clean.
- `git diff --check 4c420e1e9323bf881683ddc197758535b5638519..629ffaa3f9a93ce2cc44ba38197f2ed8428cc11d`: passed.
- `python -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py tests/execution_core/test_protection_stateful.py tests/execution_core/test_import_boundary.py`: passed; collection was exactly 447 + 35 + 27 = 509 tests.
- `ruff check .`: passed.
- `ruff format --check app/execution_core/__init__.py app/execution_core/identity.py app/execution_core/protection.py`: passed, 3 files already formatted.
- `mypy app --no-incremental`: passed, 86 source files.
- `lint-imports`: passed, 122 files / 621 dependencies / 6 contracts kept / 0 broken.
- Independent real-transition pre-fill/first-fill probe: reproduced the P1 output above.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: the 1,254-test full execution-core corpus was not rerun because the focused gate and counterexample resolved the material uncertainty; actual Python 3.11/3.12 exact-head CI, M2/runtime recovery fencing, persistence, broker, network, credentials, and later closeout remain outside this review and were not exercised.
