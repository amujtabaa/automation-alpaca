# WO-0148 ADR-023 final coverage-pin review

Review target: the sole uncommitted delta in
`tests/execution_core/test_protection.py` relative to
`6696743337f9eae8dad0567be6d49333d9d100cc`:
`test_projection_rejects_non_exact_proof_envelope_at_runtime`.

## Findings

### [P1] Commitment "exactness" test does not reject a bytes subclass

- Location: `tests/execution_core/test_protection.py:6745-6750`
- Requirement: WO-0148 requires an exact reducer-constructed opaque venue
  transition and a narrow, fail-closed venue projection
  (`work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:82-91`).
  The implementation intentionally enforces an exact commitment type at
  `app/execution_core/protection.py:2317-2319`.
- Evidence (`reproduced-live`): the reviewed test passed with
  `.\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_protection.py::test_projection_rejects_non_exact_proof_envelope_at_runtime`.
  Its commitment counterfeit is a `str`, so it fails both the current
  `type(value) is bytes` guard and a weaker `isinstance(value, bytes)` guard.
  A read-only live probe built a `NonExactBytes(bytes)` value with the genuine
  commitment payload, cloned it into the otherwise genuine transition, and
  confirmed that the current runtime rejects it with
  `proof commitment is not exact`. If the exact-type guard regressed to
  `isinstance`, that counterfeit would pass the commitment comparison and this
  new test would remain green.
- Impact: the test is behavior-relevant and exercises both named runtime error
  paths, but it cannot pin the "exact" part of the bytes-envelope boundary.
  A subclass-admission regression can therefore receive false coverage.
- Resolution: retain the existing `str` malformed-type control if desired, and
  add a separate `class NonExactBytes(bytes): pass` counterfeit carrying the
  authentic bytes. Assert the same exact `ValueError` from the public
  `project_protection_venue` boundary.

## Scope and checks

- Exact base confirmed: `HEAD` is
  `6696743337f9eae8dad0567be6d49333d9d100cc`.
- The target delta adds only this 21-line test and is within the active
  WO-0148 allowed path. No application or earlier WO-0148 changes were
  reviewed.
- `git diff --check -- tests/execution_core/test_protection.py` passed.
- No counterfactual edits were made; the bytes-subclass disproof was executed
  in-memory with bytecode writing disabled.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: none

## Addendum — corrected exact-commitment coverage pin

This addendum reviews only the follow-up correction to the P1 above. The
original finding is preserved as historical review evidence.

The test now counterfeits the authentic commitment with a local
`NonExactBytes(bytes)` subclass. This is the required exact-type
counterexample: it would satisfy a weaker `isinstance(value, bytes)` check
while preserving the genuine commitment payload.

- Evidence (`reproduced-live`):
  `.\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_protection.py::test_projection_rejects_non_exact_proof_envelope_at_runtime`
  passed.
- Evidence (`reproduced-live`, in-memory counterfactual): a throwaway Python
  process replaced only `type(proof_commitment) is not bytes` in
  `project_protection_venue` with `not isinstance(proof_commitment, bytes)`.
  The amended test then failed with `DID NOT RAISE`, printing
  `weak-commitment-isinstance-guard-killed-by-amended-test`. The original
  function was restored in that process; no tracked source was edited.
- Scope: the correction remains a single test-only delta in the WO-0148
  allowed path. No application or earlier WO-0148 work was re-reviewed.

No unresolved finding remains in the corrected coverage pin.

Final verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: none

## Final addendum — projection and state envelope exactness

This bounded pass reviews only the renamed
`test_runtime_rejects_non_exact_protection_envelopes` additions after the
accepted proof-commitment pin.

The two added controls are behavior-relevant and coherent with that pin:

- A genuine `ProtectionVenueProjection` with `_seal` replaced by an
  authentic-payload `NonExactBytes(bytes)` is passed through the public
  projection reducer. It must fail closed as `REFUSED`, preserve the input
  state, and emit neither goal nor alert.
- A genuine `PositionProtectionState` with `commitment` replaced the same way
  is passed through that reducer. It must likewise fail closed, retaining the
  supplied forged state and emitting neither goal nor alert.

Both controls distinguish exact type validation from `isinstance` validation,
not merely malformed non-bytes input.

- Evidence (`reproduced-live`):
  `.\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_protection.py::test_runtime_rejects_non_exact_protection_envelopes`
  passed.
- Evidence (`reproduced-live`, in-memory counterfactual): separately weakening
  `_projection_is_authentic` from `type(projection._seal) is not bytes` to
  `not isinstance(projection._seal, bytes)` caused the focused test to fail,
  printing `weak-projection-seal-isinstance-guard-killed-by-amended-test`.
  Separately weakening `_state_is_authentic` from
  `type(state.commitment) is not bytes` to
  `not isinstance(state.commitment, bytes)` also caused it to fail, printing
  `weak-state-commitment-isinstance-guard-killed-by-amended-test`. Both
  temporary replacements existed only in a throwaway process and were
  restored before exit; tracked source was not changed.

No unresolved finding remains in this final tests-only coverage delta.

Final verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: none
