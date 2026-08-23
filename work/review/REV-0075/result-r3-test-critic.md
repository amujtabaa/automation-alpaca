# REV-0075 R3 — test-critic review result

Reviewer: fresh independent test-critic seat

Exact candidate reviewed: `1c2debca303bd31d44474ae191ee20d9285cff1c`, tree
`692238c679041cdf76878ef40239699e13b9caaa`, against parent
`17bacd9d58f251037e989a5a7e20cc9ed9f7b841`.

## Findings

### P1 — Canonical child-tuple rule lacks a failure-capable control

- Location: `tests/execution_core/test_position.py:314`
- Mechanism: The test covers both prefix absence cases, but never reorders or duplicates a valid
  multi-child witness tuple. Removing `label <= previous_label` in
  `app/execution_core/fills.py:412` leaves these tests green.
- Impact: The frozen strict-order/no-duplicate canonical-witness rule can regress undetected.
- Root correction: Add a multi-child witness test that reverses, and separately duplicates, root
  child entries while preserving the XOR commitment; `_matches()` must refuse both.

### P1 — Codec issuer check is not exercised at its admission boundary

- Location: `tests/execution_core/test_persistence_checkpoint_codec.py:29`
- Mechanism: The test only calls `CurrentProofSlice._is_authentic()` on an uninitialized object. It
  never passes a semantically valid but issuer-tampered sealed slice into
  `_m2_protection_authority_proof_from_current_proof()` (`checkpoint_codec.py:52`). Removing that
  bridge check still leaves the static route scan green.
- Impact: A regression allowing a non-repository-issued but otherwise coherent slice through the
  checkpoint bridge would not be detected.
- Root correction: Mint a valid test slice, replace only `_issuer`, then assert the codec bridge
  rejects it before issuing a protection proof.

### P2 — Review request mispins the remediation-parent tree

- Location: `work/review/REV-0075/request-r3.md:11`
- Mechanism: Commit `17bacd…` resolves to tree `413f90d2c1ef380444367bb0afec9bd6fc6bf130`, not the
  declared `961228…`.
- Impact: The parent-tree identity cannot be independently reproduced from the request, although
  the commit range and candidate tree are unambiguous.
- Root correction: Correct the recorded parent-tree pin.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 2
- P2: 1

Unverified: The isolated candidate worktree was removed cleanly after the combined focused pytest
process failed to return a final result; no focused suite can be claimed green. Ruff, mypy, broader
suites, SQLite/DDL, and runtime composition were not run.
