# WO-0148 eleventh RED review disposition

Status: **P1 ACCEPTED AND REMEDIATED IN A NARROWER SUCCESSOR**

The independent `RED-ELEVENTH-RESULT.md` verdict remains authoritative for exact commit
`8d441d6bbbf90c634e073337ea28b2a758070bc4`: `BLOCK`, P0=0/P1=1. This disposition preserves that
result unchanged and records the author seat's root correction for a later candidate. It does not
accept the eleventh candidate or authorize production.

## Accepted finding

The annotation-expression grammar accepted a distinct one-element fixed tuple form, `tuple[T]`.
No governing requirement or production-shaped construction required that form, and the static
positive samples did not exercise it. An in-memory branch-removal control left the owning tests
green, proving the allowance was unnecessary and unpinned.

## Root correction

The successor removes the one-element tuple allowance rather than adding unused surface. The
accepted tuple forms are now fixed multi-element tuples and the exact homogeneous form
`tuple[T, ...]`. Direct altered-source controls cover both `tuple[_ExecutionSide]` and the
runtime-equivalent trailing-comma spelling `tuple[_ExecutionSide,]`; each failed before its owning
grammar correction and passes afterward by requiring an `unsupported annotation expression`
finding. The existing positive sample continues to exercise both accepted tuple forms, and the
malformed extra-element ellipsis form remains refused.

## Fresh affected evidence

- Exact one-element tuple refusal and private-annotation replacement controls: **2/2 passed**.
- Complete focus: **292 collected / 233 expected RED failures / 59 passes**.
- Ruff check and format-check pass for the changed Python file.
- Production `app/execution_core/protection.py` remains absent.

- Predecessor preservation: **698/698 passed** in a fresh 172.26-second run. The sole warning was
  the pre-existing inability to write `.pytest_cache`; collection and execution were unaffected.
- Ruff check/format-check, Python 3.11 grammar parsing, `git diff --check`, the eight-file
  current-source effect scan, and production absence pass.
- Final post-eleventh current-worktree pre-flight: **ACCEPT, P0=0/P1=0/P2=0**. Its live expression
  matrix passes 6 accepted and 8 refused forms, and separate in-memory restorations prove each
  one-item tuple control can fail.

Activation-base scope and new-record terminology checks pass. Accepted-ADR digest, worktree, and
exact-commit gates must be reconciled again before the successor is frozen.

## Gate

Freeze a new immutable candidate and obtain fresh independent exact-commit `ACCEPT` with zero
unresolved P0/P1 before any production edit.
