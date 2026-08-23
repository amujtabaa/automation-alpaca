# REV-0075 R3 — design/security review result

Reviewer: fresh independent design/security seat

Exact candidate reviewed: `1c2debca303bd31d44474ae191ee20d9285cff1c`, tree
`692238c679041cdf76878ef40239699e13b9caaa`, against parent
`17bacd9d58f251037e989a5a7e20cc9ed9f7b841`.

## Findings

### P1 — `CurrentProofSlice` leaves carried optional rows unauthenticated

- Location: `app/execution_core/persistence/records.py:318-327`, `441-578`
- Mechanism: The slice carries root/fact/effect/claim/owner/acceptance/closure rows, but
  `_current_proof_slice_binding()` neither validates nor commits any of them. Only their request
  IDs are bound.
- Impact: Post-issuance replacement of any optional row leaves `_is_authentic()` true, creating an
  unauthenticated optional-row authority path contrary to the sealed direct-current contract.
- Root correction: Either remove optional rows from this proof type, or validate and commit every
  optional row’s identity, contents, and required relationships; add mutation controls for each
  branch.

### P1 — Issuer-provenance check lacks a failure-capable test

- Location: `tests/execution_core/test_persistence_checkpoint_codec.py:29-32`
- Mechanism: The forged slice has no fields, so it remains unauthentic even if the `_issuer`
  comparison is removed; the route text scan also does not exercise that runtime check.
- Impact: A regression that drops issuer verification can pass the focused suite, reopening the
  repository-provenance requirement.
- Root correction: Start with a valid repository-issued slice, mutate only `_issuer`, and assert
  both `_is_authentic()` and codec adaptation reject it.

### P2 — Review packet records the wrong parent tree

- Location: `work/review/REV-0075/request-r3.md:11-12`
- Mechanism: Parent commit `17bacd9…` resolves to tree
  `413f90d2c1ef380444367bb0afec9bd6fc6bf130`, not recorded `961228…`.
- Impact: The evidence packet is not fully hash-bound and could mislead a cross-context reviewer.
- Root correction: Correct the recorded parent-tree hash.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 2
- P2: 1

Unverified: SQLite/DDL, runtime composition, external I/O, broader suites, and mypy were
intentionally not run. Focused pure checks exited 0; no source/test/docs changes were made.

