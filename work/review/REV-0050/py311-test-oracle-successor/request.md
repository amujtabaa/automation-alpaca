# WO-0148 Python 3.11 test-oracle successor review

Review the exact uncommitted delta from closeout candidate
`9f696dc4142f9876d0292afc029d6d561671e7b5`. Produce findings only in
`result.md`; do not edit source, tests, the work order, or any other evidence.

## Trigger

Push-triggered exact-head GitHub Actions run `30989580232` (#691) passed Python
3.12 job `92252257437` and failed Python 3.11 job `92252257396`. The 3.11 job
reported seven `RecursionError` failures after 5,828 passes. Every traceback
ended in generated dataclass equality invoked by shared test helpers' recursive
whole-object `assert second == first`; no production reducer raised.

## Candidate

The successor adds one test-only explicit-stack, alias-aware structural
fingerprint in `test_authority.py`, reuses it across shared authority,
authority-stateful, and protection apply-twice helpers, and adds a deep control
for equal graphs, a changed deep leaf, and shared-versus-duplicated topology.
It changes no production, workflow, recursion limit, database, broker, runtime,
or operational behavior.

Exact SHA-256 values:

- `tests/execution_core/test_authority.py`:
  `E70A53BF73BBB899E52329EEA73372D056D4FE69B646CCFF83594B5CFFD7DFE3`
- `tests/execution_core/test_authority_stateful.py`:
  `5FB612D684D8CC6295FC2C04D8CBBDE0D77684BE0EDD3C711A46AFB6CEB6223B`
- `tests/execution_core/test_protection.py`:
  `5C27620BF071EBA4B9E864E07D32959FF9A9E3462A77B13CBCE131AAD1B0D2D2`
- WO-0148 record:
  `FD51F8D1323945AFCEC425B8812C1476F5330ECFD1794A5AE78DFDE32C698389`

## Required review

Re-derive whether the fingerprint is complete for the immutable graphs under
test, terminates for deep/aliased/cyclic dataclass-and-tuple graphs, and cannot
silently accept divergent reducer output or mutated input. Check that reuse is
complete at the shared failure-class seams and that path re-gating is minimal.
Run the exact eight-node regression focus and the affected suite as useful.
Perform bounded counterfactuals that prove the deep-leaf and alias controls can
fail without leaving tracked edits. Reject recursion-limit changes, shallow
commitment/count substitutes, production fixes for test rendering, and scope
expansion.

Return P0/P1/P2 findings with file:line, impact, resolution, and final
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. Zero unresolved P0/P1 is required.
