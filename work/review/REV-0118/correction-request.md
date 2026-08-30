# REV-0118 — finite correction re-review request

Verdict requested: **findings only; correction re-review; no open-ended redesign**

## Exact candidate

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Candidate commit: `0587c7069dfcea7b53e37a35b2cad89cf72bd69d`
- Candidate tree: `ec14552d7f73e8c223d7581a8b5d2f99449c744d`
- Final implementation/test source inside the candidate:
  `c7e394f52782a9b398ed89bfdc55b45bc09499b4`, tree
  `2d5c662f569ec3ee792216863fe46213551773a8`
- Original reviewed manifest candidate:
  `d801fb1730d9116334b5eee735577217abee7d9f`
- Original reviewer result SHA-256:
  `8e429feefaaf5cf4f910590640a9e2b9fd0a405237e2f51e4ae3ecda52cdb005`
- Corrected closeout manifest SHA-256:
  `f4a6d8dbf60306a986f62b03aa0b2c84c6d4a769135018a04d78b33da28f6f9d`
- Corrected closeout manifest blob:
  `5038e3328be92f5c5e8d56e2b3302eac898b419a`
- DDL: unchanged 190,705 UTF-8 bytes at SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- Canonical `schema.py`: blob `164de10ad9fef6ce37324840aff59b5b68c07d2a`, authorization
  flag exact boolean `False`

## Required read order

1. `work/review/REV-0118/result.md` — the three retained P1 findings.
2. `harness/m2/closeout.py` and its pure fault/restore tests.
3. `tests_gated/execution_core/test_persistence_fault_matrix.py`.
4. `tests_gated/execution_core/test_persistence_boundedness.py` and
   `tests/performance/m2_persistence_budget.py`.
5. `work/review/REV-0118/execution-result-r6.md`, `execution-result-r7.md`, and
   `execution-result-r8.md`.
6. `harness/m2/M2-CLOSEOUT-MANIFEST.md`.

## Three required closure decisions

1. **Catalog decisiveness.** Verify that durable-input claim, erased dispatch claim, acceptance
   omission, closure omission, and both fixed/published market-cursor regressions each reach a
   dedicated failure-capable test, and that the finite catalog maps to those exact tests.
2. **Real hydration boundedness.** Verify that the target/stress test stores a canonical
   checkpoint; measures actual load, decode, and compact restoration; counts read statements and
   elapsed growth against the frozen 12x startup budget; measures canonical hydration memory
   against 2 MiB; and checks every selection/load plan at both coordinates.
3. **Destination-family restore collision.** Verify that snapshot refuses pre-existing
   destination database, WAL, or SHM independently of source sidecars and that verification
   rejects unrecorded destination sidecars.

Also check only for concrete P0/P1 regressions introduced by these corrections, including the
frozen test-import direction. Do not reopen accepted WO-0165 through WO-0169 architecture, propose
taste refactors, or convert honest 24-hour-soak `NOT_RUN` / R16 `NOT_EVALUATED` residuals into
findings without a correction-caused counterexample.

## Supplied evidence

- 60 focused pure closeout controls passed.
- Final canonical ordinary suite: 2,310 passed, zero failed/skipped.
- R2 conformance oracle: 61 passed.
- R8 exact final held proof: seven passed at flag-only commit
  `b14cbb88061aab09f69ce219e9c1427a01873761`, tree
  `f4571503ad5a3b507b0ee33997d3335c317f68b4`.
- Ruff lint and 11-file format checks passed; mypy passed over 99 application files; all six
  import contracts were kept; install/version/ledger/PKL/scope and diff hygiene passed.

The review seat may run static checks and targeted ordinary pure tests but must not open SQLite,
run held suites, change files, or alter the authorization flag. Treat R8 as supplied execution
evidence and state anything not independently verified.

## Finite verdict

For each retained finding, provide severity, exact file/line, demonstrated failure, real-world
impact, smallest root correction, evidence level, and a disproof pass. Return:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires all three original P1s closed and zero concrete correction-introduced P0/P1.
State explicitly that no SQLite/database/held-suite execution occurred in the review seat.
