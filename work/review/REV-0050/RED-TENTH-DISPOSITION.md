# WO-0148 tenth RED review disposition

Status: **TENTH CANDIDATE NOT ACCEPTED — CONTRACT CORRECTED IN A SUCCESSOR**

Exact tenth candidate `5c5bee9543b78fc2fa8f612c61d75d4fdbf52bae` remains preserved. Its external
review attempt ended before findings were produced because of a platform-level interruption. No
`RED-TENTH-RESULT.md` exists, no verdict was issued, and the interruption supplies no acceptance
evidence.

Production `app/execution_core/protection.py` remained absent throughout this correction.

## Reconciled P1 issues

Subsequent author reconstruction and read-only pre-flight review identified five contract issues.
No P0 was found.

1. The exact public-surface rule and the blanket refusal of renamed imports were contradictory.
   Required dependencies such as `dataclass` and `Enum` could neither remain private nor appear as
   additional public module names.
2. An ordinary future-annotations directive retained a public `annotations` runtime binding, so it
   also violated the exact public surface.
3. Canonical private imports required matching private annotation names and replacement-type
   resolution. The prior public `VenueRecoveryTransition`, `ReportedPrice`, `Decimal`, and
   `Fraction` spellings were inconsistent with the repaired import contract.
4. An explicitly quoted private annotation produced an additional quoting layer in deferred
   runtime metadata and was not tied to the inspected imported name.
5. The accepted union and container annotation forms initially lacked direct checker-positive
   controls.

## Root correction

- Public imported names must use exactly `Name as _Name`; imported names that are already private
  remain unaliased. The future directive uses `annotations as _annotations`.
- Module imports, wildcard imports, arbitrary aliases, redundant private aliases, duplicate
  bindings, and post-import rebinding remain refused.
- Imported annotations use the retained private names. The public venue entrypoint expects
  `_VenueRecoveryTransition`, and optional replacement resolution recognizes `_ReportedPrice`,
  `_Decimal`, and `_Fraction`.
- Annotation expressions are limited to loaded names, PEP 604 unions, `None`, and exact
  `frozenset[...]`, `tuple[...]`, or `type[...]` forms. Ellipsis is accepted only in the exact
  homogeneous tuple form; explicit annotation strings are refused.
- A test-only executable sample proves the required imports remain private while non-private
  runtime names equal exact `__all__`. Direct altered-source controls cover every retained refusal,
  annotation form, and malformed tuple case.

## Fresh successor evidence

- Complete focus: **292 collected / 233 expected RED failures / 59 passes**. The 233 failures are
  unchanged production-absence and required inventory/import/export deltas; all correction and
  meta-controls pass.
- Predecessor preservation: **698/698 passed** in 157.08 seconds. The sole warning was the
  pre-existing inability to write `.pytest_cache`; collection and execution were unaffected.
- Ruff check and format-check pass for both changed Python files.
- Both changed Python files parse with the Python 3.11 grammar; actual Python 3.11 execution is not
  available locally and remains an unchanged exact-head CI obligation.
- `git diff --check`, accepted ADR digests, the eight-file current-source effect scan, and
  production absence pass.
- Critical current-worktree pre-flight verdict: **ACCEPT, P0=0, P1=0**. This is not immutable
  exact-commit acceptance.

## Gate

The tenth candidate remains unaccepted. Freeze the corrected successor, create a new neutral
functional-conformance request, and require fresh independent exact-commit `ACCEPT` with zero
unresolved P0/P1 before any production edit.
