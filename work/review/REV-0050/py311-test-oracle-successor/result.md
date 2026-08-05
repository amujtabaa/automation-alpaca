# WO-0148 Python 3.11 test-oracle successor review result

No findings.

## Reviewed target

- Base: `9f696dc4142f9876d0292afc029d6d561671e7b5`
- Candidate scope: the uncommitted delta in
  `tests/execution_core/test_authority.py`,
  `tests/execution_core/test_authority_stateful.py`,
  `tests/execution_core/test_protection.py`, and the matching WO-0148 record
- Candidate SHA-256 values: all four values matched `request.md`
- Scope: no production, runtime, workflow, database, broker, credential, or
  operational file changed; the WO amendment adds only the directly required
  test path and the failed-CI successor gate

## Acceptance evidence

- `reproduced-live`: the exact eight-node regression focus passed `8/8` under
  the mock-only local Python 3.12 environment. This included the new structural
  control and all seven cases that raised `RecursionError` in exact-head Python
  3.11 run #691.
- `reproduced-live`: the bounded affected suite passed `642/642` across
  `test_authority.py`, `test_authority_stateful.py`, and `test_protection.py`.
- `static-reasoning`: the comparison uses an explicit work stack and assigns
  deterministic traversal ordinals to exact dataclass and tuple containers.
  It records dataclass type and ordered field names, tuple length and order,
  exact leaf type and representation, and repeated-reference ordinals. The
  current immutable graphs exercised by the affected suite therefore cannot
  substitute a changed deep leaf, reordered or differently typed structure,
  or shared-versus-duplicated topology without changing the fingerprint.
- `reproduced-live`: a leaf-value-blind counterfactual made the deep changed
  leaf indistinguishable, while the candidate fingerprint distinguished it.
  An alias-blind expansion made shared and duplicated child topology
  indistinguishable, while the candidate fingerprint distinguished it. Both
  weaker substitutes were therefore rejected by failure-capable controls.
- `reproduced-live`: a cyclic frozen dataclass whose tuple child referenced the
  dataclass terminated, produced a reference token, matched an independently
  constructed equal cycle, and rejected a changed-value cycle. The 1,200-node
  chain control independently exercised depth beyond Python 3.11's recursive
  equality limit.
- `static-reasoning`: all shared apply-twice seams implicated by the seven
  failures now use the common helper for both output equivalence and input
  non-mutation. The remaining direct equalities are bounded one-off checks that
  were green in run #691 and in the affected suite; expanding this successor to
  replace them is not required by the reproduced failure class.
- `reproduced-live`: `git diff --check` passed and the final tracked-drift check
  showed only the four reviewed candidate files before this required result
  artifact.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: exact-head Python 3.11/3.12 CI, fresh R2, full-repository tests, and branch coverage remain mandatory post-review gates; no local Python 3.11 interpreter was available in this review environment.
