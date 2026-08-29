# REV-0117 R2 author disposition

Date: 2026-08-29

Status: **P1 accepted; one test-only root-boundary correction**

The independent `result-r2.md` is preserved unchanged. Its `ACCEPT-WITH-CHANGES` verdict remains
authoritative until a fresh correction-only verification returns zero open P0/P1.

## P1 — accepted unresolved-generation mutation gap

The production correction changed both live and unresolved checkpoint generation comparisons to
the established one-based durable mapping, but the first remediation tested only the live path.
That left the unresolved comparison independently revertible without a failing test.

The correction adds one pure, non-SQLite test that constructs an authentic acquisition successor
with its retired predecessor and retained predecessor stream route. The exact one-based durable
predecessor row must encode. Replacing only its durable ordinal with the domain ordinal must raise
`selected unresolved generation is spliced`. No production code, DDL, held test, gate flag, or
execution authority changes.

## Finite correction verification

The same fresh reviewer may inspect only this accepted test gap and regressions introduced by its
test. Zero open P0/P1 is required before a new fresh-file execution packet. No SQLite access or
held-suite execution is authorized by this disposition.
