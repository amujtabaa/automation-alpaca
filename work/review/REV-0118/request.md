---
type: Review
review_id: REV-0118
work_order_id: WO-0170
review_mode: fresh-context whole-candidate closeout review
status: REVIEW
authoritative_diff: 0e9c5aadf003aae7dc66cf6df497b1a1d1d6d130..d801fb1730d9116334b5eee735577217abee7d9f
---

# REV-0118 — WO-0170 crash, restore, fault, and boundedness closeout review

Return findings only. Do not edit, commit, push, or implement fixes. Re-derive the candidate from
the exact diff, work order, code, tests, manifests, and execution records. Earlier failed attempts
and focused reviewer notes are findings-input, not authority.

This is one bounded whole-candidate review. If a concrete P0/P1 survives a disproof pass, one root
correction and one correction-only re-review are the maximum. Do not expand a passing closeout into
new architecture or reopen accepted predecessor design without a concrete regression in this diff.

## Exact identity

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Accepted WO-0169 predecessor: `0e9c5aadf003aae7dc66cf6df497b1a1d1d6d130`, tree
  `b5f1042247804ad9fde4347c8729d5bde29a172d`
- Candidate: `d801fb1730d9116334b5eee735577217abee7d9f`
- Candidate tree: `8133fe09e6e5f934238f05d23215165f61167a56`
- Review exactly:
  `0e9c5aadf003aae7dc66cf6df497b1a1d1d6d130..d801fb1730d9116334b5eee735577217abee7d9f`
- Diff size: 23 files, 1,907 insertions, 10 deletions
- Final implementation/test source: `3b3b1462bc8a52e6dd4308121e87545bd11f6a70`, tree
  `800b0f7a56eda308d445810dc998107597f7c539`
- Closeout manifest blob: `2f2bdfb55670998f418576a762fdcea174687056`; SHA-256
  `7408a679a8750bd423daa93a020fdd1009409fc4505499fa765521784c0782c9`
- Closeout catalog blob: `7a71534c88ae50d37596cb56210f0d0df26fb0ec`
- Soak driver blob: `f0ae7351f68a5192b0ff442d8df78240dab0ef08`
- Cross-layer fault test blob: `1dee32ebb81a80ba458fcf818ace3e6bcd819851`
- Flag-false schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- DDL: 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- `EXPECTED_EXECUTION_DDL_SHA256` equals that digest and
  `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact boolean `False`.

## Read order

1. `AGENTS.md`, the safety core in `CLAUDE.md`, and
   `work/active/WO-0170-m2-i6-crash-restore-fault-closeout.md`.
2. `harness/m2/M2-CLOSEOUT-MANIFEST.md` and `harness/m2/closeout.py`.
3. The three new pure files under `tests/execution_core/`, the SQLite-boundary amendment, and
   `tests/performance/m2_persistence_budget.py`.
4. The three new files under `tests_gated/execution_core/`, especially the clean-control
   old/new-complete oracle, DB/WAL restore, and target/stress proof.
5. `harness/m2/soak.py` and its pure ordering/status test.
6. `work/review/REV-0118/execution-packet-r4.md`, `execution-result-r4.md`,
   `execution-packet-r5.md`, and `execution-result-r5.md`.
7. Directly relevant accepted M2 source/tests only as needed to verify each catalog mapping.

## Threat model and acceptance criteria

In scope: a harness that omits a real write/commit/publication/claim/lock/cursor edge; a test that
cannot fail or mistakes partial state for old/new complete; a restore that is not independent or
byte-consistent; a mutant mapped to a non-decisive test; history-shaped startup/query/memory work;
a short/failed soak laundered as PASS; a stale or false manifest identity; a hidden SQLite boundary;
or any canonical DDL/flag drift.

Out of scope without a diff-caused counterexample: redesign of accepted WO-0165 through WO-0169,
production lock/adapter composition, broker behavior, configured databases, promotion policy,
the future 24-hour execution, the unavailable external R16 input set, M3 implementation, and
taste-only refactoring.

Acceptance requires source/contract proof or a concrete failure-capable counterexample for every
P0/P1. The candidate must:

1. keep a finite, mutation-pinned mapping of every stated fault/mutant/boundedness obligation to a
   real decisive test;
2. prove pre-COMMIT old-complete and post-COMMIT clean new-complete against an independent complete
   durable-state oracle, then retain new-complete through retry and replay;
3. copy and verify an independent DB/WAL restore without source mutation or destination reuse;
4. prove direct indexed work and frozen target/stress budgets without hiding unbounded history;
5. keep SQLite tests outside ordinary discovery and behind the exact application-owned installer
   gate while canonical DDL/flag bytes remain unchanged;
6. make the one-cycle smoke failure-capable and classify it `NOT_RUN`, never as the 24-hour soak;
7. state every missing operational/R16/promotion coordinate honestly; and
8. provide a self-contained, hash-correct reproduction manifest.

## Supplied fresh evidence

- 55 focused pure/static WO-0170 controls passed.
- 2,305 ordinary `tests/execution_core` tests passed with zero failures/skips.
- The 61-case R2 conformance oracle passed.
- R4 passed all 259 exact fresh-file cases. The only subsequent code change was the soak-driver
  parent-directory fix plus its pure regression test; production, DDL, and gated-test hashes did
  not change.
- R5 passed all 180 scheduled cases in 7.29 seconds and emitted `NOT_RUN`, one passed cycle, and
  7.75 seconds elapsed against 86,400 required.
- Ruff lint, changed-file Ruff format, mypy over 99 app files, six import contracts, work-order
  scope, install/version/ledger/PKL/disposition, and `git diff --check` passed.
- The 24-hour soak is `NOT_RUN`; R16 G0-G7 is `NOT_EVALUATED` because its current exact input
  manifest/freshness coordinates are absent.

## Permitted reviewer evidence

Static source/contract tracing, hash/blob/ancestry verification, targeted ordinary pure tests,
mutation or fixture analysis, and concrete in-model counterexamples are permitted. Do not edit the
checkout, create/open a SQLite database, run `tests_gated/**`, change the authorization flag, or
re-run the held matrix. Treat the recorded exact execution as supplied evidence and report any
part you cannot independently verify under `Unverified`.

## Mandatory review lenses

1. Catalog completeness and whether every mapped test is decisive.
2. Exact old/new-complete, retry, and replay attribution.
3. Restore copy consistency, independence, collision, and drift refusal.
4. Boundedness measurement validity and query-plan failure capability.
5. Soak loop/status/evidence integrity, including the fixed parent-order regression.
6. Manifest hashes, branch/source separation, canonical false flag, and DDL immutability.
7. Scope, safety, test discovery, and needless-complexity check.

## Output and finite stop

For each retained finding: severity, `file:line`, violated clause or demonstrated failing case,
real-world impact, smallest root correction, and evidence level (`reproduced-live` or
`reasoned-only`). Perform a disproof pass against your own finding before retaining it. Do not
create a finding for preference, a hypothetical outside the work-order model, or already-honest
`NOT_RUN`/`NOT_EVALUATED` residuals.

End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1. State that no SQLite/database/held-suite execution occurred in
the review seat.
