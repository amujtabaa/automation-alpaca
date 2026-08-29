# REV-0115 finding disposition

Date: 2026-08-29

Status: **ALL THREE FINDINGS ACCEPTED AND ROOT-REMEDIATED — exact-head re-review pending**

The independent result at SHA-256
`ff9400ab02c3ccb2fed1dfc07d41f76aeeeac6d8b6579a1ee6657e7b40a3293e` returned
`BLOCK` with P0=2/P1=1/P2=0. The implementation seat accepts every finding:

1. Manual SELL creation now consumes one sealed `CreateBrokerEffect` observation bound to the
   selected active scope and exact READY manual row. Raw, unbound `_manual_by_id` history cannot
   authorize an effect. The public route and UOW route share the same owner kernel.
2. A predecessor-valid correction or bust whose quarantined root has no acquisition route now
   persists canonical broker truth, advances the exact quarantined root/fact/controller rows, and
   returns `RECONCILIATION_REQUIRED` without inventing attribution or acquisition authority.
3. `unit_of_work.py` now carries the literal O1-O8 repository-call table and common write table.
   Failure-capable controls pin every row/family/call, reject missing/extra/reordered/dynamic/
   wildcard mutants, prove actual mutator call sites are static and exactly catalogued, and exercise
   rollback plus lease retirement before and after every catalogued boundary.

Remediation source candidate:

- Commit: `55c4698236858fd1f9a92fc8e50134b8161c1843`.
- Tree: `6b6c4dda85e56c9648fb545b806c12bce5d42b0b`.
- Remediation diff: `7c0e52b26cf0bc1b82bbfa04ffc4131e80161145..55c4698236858fd1f9a92fc8e50134b8161c1843`.
- `authority.py` blob: `174c1b40926e53e54314b276779f59bc4e908966`.
- `unit_of_work.py` blob: `105d5189a75d0d2044752a71ece1d893db146f65`.
- Pure UOW test blob: `3d03e30043bb1b9edffc0b82c3f2cc5a1208789b`.

Exact-candidate evidence: all 2,178 ordinary `tests/execution_core` tests passed at 100% with exit
zero; Ruff check and format check passed the three changed Python files; mypy passed all 96
application source files; `git diff --check` passed. The focused table, manual-proof, route-less
correct/bust, and 173-boundary fault controls also passed independently.

DDL and gate authority did not move: `SCHEMA_DDL` remains 190,705 UTF-8 bytes at SHA-256
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, schema blob
`164de10ad9fef6ce37324840aff59b5b68c07d2a`, and
`DDL_EXECUTION_AUTHORIZED_BY_AMEEN` remains exact boolean `False`.

One correction-only fresh-context re-review must independently disprove or accept these root
closures before WO-0168 may close. No SQLite/database/DDL/held-suite execution occurred in this
remediation or its review preparation.
