# WO-0148 eleventh exact-commit functional-conformance review

Exact candidate reviewed: `8d441d6bbbf90c634e073337ea28b2a758070bc4`

Activation review base: `d75806b1a79d1769db25ae962c0977cd9388a886`

## P1 findings

### P1-1 — The accepted one-element tuple annotation branch has no direct failure-capable control

**Location:** `tests/execution_core/test_import_boundary.py:688`

**Governing requirement:** `work/review/REV-0050/RED-ELEVENTH-REQUEST.md:24-32`
requires every accepted annotation-expression branch to be necessary, feasible, and directly
exercised, and classifies a missing failure-capable control as P0/P1 evidence.
`work/review/REV-0050/RED-CONTRACT-CORRECTION-WORKFLOW.md:96-101` likewise requires every accepted
annotation branch to be exercised in the static positive sample.

**Reproducible evidence:** `_supported_annotation_expression` takes a distinct branch when a
`tuple[...]` subscript has a non-`ast.Tuple` slice and recursively accepts it, so the complete
source checker returns no violation for `def keep(value: tuple[int]) -> int: return 1`. The committed
positive sample at `tests/execution_core/test_import_boundary.py:2195-2208` covers
`tuple[_ExecutionSide, ...]` and `tuple[_ExecutionSide, _ExecutionSide]`, but not
`tuple[_ExecutionSide]`. A read-only in-memory negative control replaced only lines 688-689 with
`return False`; both
`test_effect_call_oracle_rejects_direct_runtime_output` and
`test_protection_canonical_private_imports_preserve_exact_public_surface` still completed, while
the original helper accepted `tuple[int]` and the altered helper refused it. The cited authority
and committed samples identify no production-required one-element fixed-tuple annotation.

**Severity:** P1 — the exact pre-production gate contains an accepted grammar branch whose removal
is not detected, contrary to the required direct-exercise control.

**Required resolution:** Either add a production-shaped static positive control that directly uses
`tuple[_ExecutionSide]` and records why the one-element fixed-tuple form is required, or remove that
accepted branch. Re-freeze the candidate and rerun the focused classification and affected static
negative controls before another exact-commit review.

## Evidence reconciliation

- `HEAD` is the requested exact candidate, and the activation review base is its ancestor. Before
  this result was written, tracked and staged diffs were empty; the pre-existing untracked evidence
  and request artifacts were preserved.
- Focused collection reproduced 292 tests: 273 protection, four stateful, and 15 import-boundary
  tests. Exact execution reproduced 233 expected failures and 59 passes. Of the failures, 230 are
  caused by deliberate production-module absence and three are the required module-inventory,
  AST/import, and package-export deltas.
- The executable exact-public-surface control, private imported-annotation replacement control,
  production-shaped static checker control, and named altered-source controls completed. A separate
  full public-entrypoint annotation feasibility sample returned no static violations.
- The predecessor execution-core corpus, excluding the three failure-first files, collected and
  passed 698/698 tests in 167.7 seconds. The only warning was the pre-existing inability to write
  `.pytest_cache`; execution was unaffected.
- Ruff check and format-check, Python 3.11 grammar parsing of both changed Python files, `git diff
  --check`, the activation-base scope check, all three accepted ADR digests, the eight-file
  current-source effect scan, and production absence in both the worktree and exact target passed.
- Local execution used Python 3.12.13. No SQL/DDL, database initialization, broker call, credential
  access, persistence/runtime change, merge, deletion, or cleanup occurred.

## Unverified items

- Actual Python 3.11 execution is unavailable locally and remains an unchanged exact-head CI
  obligation; only Python 3.11 grammar parsing was performed.
- `app/execution_core/protection.py` is deliberately absent. Production functional conformance and
  implementation mutation-restoration evidence cannot yet be executed.
- Network/CI state, broker behavior, credentials, SQL/DDL, database/persistence behavior, runtime
  wiring, and repository tests outside the 698-test predecessor corpus were not exercised, in
  accordance with this review boundary.

## Verdict

**BLOCK**

P0: **0**

P1: **1**

One unresolved P1 negative-control gap remains. WO-0148 production implementation remains
prohibited until the accepted annotation grammar is directly exercised or narrowed and a new
immutable candidate receives an independent zero-P0/P1 verdict. This verdict governs only
permission to begin WO-0148 production implementation; it neither accepts production nor closes
the work order.
