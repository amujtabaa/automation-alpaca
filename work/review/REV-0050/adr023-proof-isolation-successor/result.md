# Independent exact-delta review - ADR-023 proof-isolation successor

Review target: `3f54df45d7234e0d5f678522686730dc1f374a60..b7ae0d7db900557d54784ede2a27a7df65be0ae4`

No P0, P1, or P2 findings.

## Evidence

- The parent and candidate objects exist, the candidate has the stated parent, and the immutable
  delta contains only the three declared paths. `git diff --check` is clean.
- The first preceding P1 is closed at
  `tests/execution_core/test_import_boundary.py:2967-2991`. An exact candidate-object probe
  produced one derived-setter violation for both a complete exact-field fragment with an omitted
  lifecycle and the same fragment with a renamed lifecycle. The non-complete standalone field
  fragment and a complete fragment with no `MarketOccurrence` each produced zero derived-setter
  violations. The direct omitted/renamed controls at
  `tests/execution_core/test_import_boundary.py:5116-5130` are failure-capable and preserve the
  intended distinction.
- The second preceding P1 is closed at
  `tests/execution_core/test_protection.py:12080-12105`: the exit-provenance branch now varies the
  first corroborating bid while retaining an identical current occurrence, then asserts the exact
  changed-field set `{"commitment", "_exit_provenance"}`. The static oracle independently adds an
  omitted-provenance mutant at `tests/execution_core/test_protection.py:14561-14596`, which fails
  the exact fifteen-part commitment inventory.
- The coordinated-identity control at
  `tests/execution_core/test_protection.py:6331-6422` independently rebuilds both text-plus-seal and
  cached-bytes-plus-seal inconsistencies for both market identity types. It proves the canonical
  positive path and rejects both coordinated variants. Its end-to-end case first establishes
  `EXACT_REPLAY`, then requires the forged state to fail authentication and return an unchanged,
  goal-free `REFUSED` result.
- A pure corroborating simulation replaced the corrected identity predicate with the prior
  seal-only relationship. The baseline remained `EXACT_REPLAY`, the coordinated forged state was
  incorrectly authenticated, and the same occurrence returned state-changing `APPLIED`. This
  demonstrates that the new end-to-end control can fail for the named pre-correction defect rather
  than merely asserting construction details. The simulation used the excluded application only
  as corroboration; the candidate test logic and static contract remain review authority.
- The import allowance adds exactly
  `("app.execution_core.identity", "_market_identity_is_canonical")` at
  `tests/execution_core/test_import_boundary.py:185`. Exact candidate-object probes admitted the
  canonical private import/call with zero violations, rejected a renamed alias with one
  noncanonical-binding violation, and rejected both a wrong helper and the right name from the
  wrong owner with import and call-binding violations. Existing generic rebound and duplicate
  import rules continue to apply.
- The requested focused command reproduced 27/27 passing. Ruff lint and format checks passed for
  both changed Python files. At execution time, the reviewed test and work-order files exactly
  matched the candidate object; dirty application files and untracked artifacts were excluded from
  candidate evidence.
- The work-order successor record at
  `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:1423-1452` accurately
  distinguishes the two proof-isolation corrections, the coordinated-identity RED obligation, and
  the excluded in-progress application.

## Verdict

**ACCEPT**

- P0: 0
- P1: 0
- P2: 0

Unverified: the excluded application implementation, broader full-suite results, exact-head
Python 3.11/3.12 CI, and any later production-acceptance or WO-0148 closeout claim.
