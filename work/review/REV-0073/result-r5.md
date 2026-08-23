---
type: review-result
review_id: REV-0073
round: R5
work_order: WO-0167
review_seat: authoritative-fresh-independent-r5
review_date: 2026-08-22
base_commit: 0a7b5ae324c34be488da24478f95e2658a1bb894
r3_production_commit: 4ed0b4e0378a91940ca392dc40902959dc41ecff
blocked_predecessor: 0c601ebeebc44865c0b92c41e7be531cc9d3f981
candidate_commit: 3c028b9ae5fd3e1b6bf84b7d73c2f3039ac14043
candidate_tree: d078be4b8b0157216aef51c80b13cf211626b0d1
documentation_head: aaab13b0663fcd5b4b1de8800efbb96af1ed4e43
verdict: ACCEPT
p0_count: 0
p1_count: 0
p2_count: 0
---

# REV-0073 R5 — WO-0167 authoritative independent review result

## Findings

No P0, P1, or P2 findings.

## Candidate identity and scope

The reviewed candidate is exact commit
`3c028b9ae5fd3e1b6bf84b7d73c2f3039ac14043`, tree
`d078be4b8b0157216aef51c80b13cf211626b0d1`, over accepted WO-0166 base
`0a7b5ae324c34be488da24478f95e2658a1bb894`. Accepted-base ancestry and
candidate-to-documentation-head ancestry were reproduced. Later head
`aaab13b0663fcd5b4b1de8800efbb96af1ed4e43`, tree
`34b4bc2358f3053a7a591186a399e99c81afb414`, changes only the WO, ledger,
REV-0073 disposition, and R5 request.

The R5 candidate delta from immutable R4 result commit
`0c601ebeebc44865c0b92c41e7be531cc9d3f981` changes only
`tests/execution_core/test_persistence_repository.py` and
`tests/execution_core/test_persistence_directness.py`. Production repository blob
`2a668f28b547272ed9c6afd00ffa60a0c5938984` is identical to R3 production commit
`4ed0b4e0378a91940ca392dc40902959dc41ecff`. Schema blob
`5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd` is identical to the accepted base;
the independently recomputed DDL SHA-256 is
`2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859`.

The full accepted-base repository/records/focused-test semantic surface and all immutable prior
REV-0073 findings were inspected. No new production behavior, DDL, migration, runtime composition,
human-gated surface, or safety-invariant change is present.

## Fresh focused evidence

- **Unmodified focused gate — `reproduced-live`:** CPython 3.12.13 collected exactly 190 cases
  (33 repository and 157 directness) and completed at 100% with exit code 0. Pytest cache was
  disabled. Every database fixture used a fresh file-backed `tmp_path` SQLite database with
  foreign keys and recursive triggers enabled. The first sandbox-default temporary-directory
  attempts failed before fixture setup and are superseded by the successful explicit fresh
  `--basetemp` run.
- **Public-operation transaction matrix — `reproduced-live`:** all 56 exported repository
  operations are pinned one-for-one by `_operation_cases`. Each operation ran after the complete
  seed was written inside a caller-owned transaction, retained `in_transaction=True`, and passed
  exact pre/post rollback row-count equality across every non-internal application table.
- **Static transaction boundary — `reproduced-live`:** the focused source gate passed with no
  repository `commit`, `rollback`, `cursor`, `executemany`, or `executescript` acquisition and no
  constant-foldable `BEGIN`, `COMMIT`, `END`, `ROLLBACK`, `SAVEPOINT`, or `RELEASE` SQL.
- **Scope and forbidden dependencies — `reproduced-live`:** the reviewed production files contain
  no SQLite connection acquisition, in-memory database path, configured database discovery,
  environment access, broker/Alpaca call, or repository-owned transaction control.

## Exact R5 mutant reproduction

Each external mutant was applied to a separate disposable archive of exact candidate
`3c028b9ae5fd3e1b6bf84b7d73c2f3039ac14043`; no source or test in the review worktree was edited.
Each complete mutant run collected the same 190 focused cases and used fresh file-backed SQLite.

1. **Cursor hidden read — `reproduced-live`:** inserted the exact
   `hasattr(connection, "cursor")` branch followed by
   `connection.cursor().execute("SELECT count(*) FROM execution_fact").fetchone()` immediately
   after the proof schema guard. The complete gate failed with 7 failures and 183 passes. The
   owning exact-ledger assertion observed 16 proof calls against 15 allowed calls, with the hidden
   read recorded first. The source capability gate also rejected cursor acquisition.
2. **Cursor encoded `COMMIT` plus replacement `BEGIN` — `reproduced-live`:** inside an active caller
   transaction, acquired `connection.cursor()`, executed comment-prefixed dynamically assembled
   `COMMIT`, then dynamically assembled `BEGIN`. The complete gate failed with 4 failures and 186
   passes. The public-operation transaction control failed independently at the cursor wrapper
   with exact evidence `repository attempted transaction SQL COMMIT`; replacement `BEGIN` was not
   reached through the guarded path. Exact proof accounting also observed 17 calls against 15 when
   exercised without the tripwire.
3. **Raw escaped commit plus replacement `BEGIN` — `reproduced-live`:** deliberately escaped the
   test wrapper to the accepted raw SQLite connection, executed the encoded comment-prefixed
   `COMMIT`, and restored `in_transaction=True` with encoded `BEGIN`. The complete gate failed with
   2 failures and 188 passes. The independent post-rollback all-table snapshot caught persisted
   seed state despite the replacement transaction; the first reported mismatch was
   `acceptance_evidence = 1` after rollback versus the pre-transaction count `0`. The static
   constant-folding gate also rejected the transaction SQL.

The three required mechanisms therefore do not survive the complete focused gate.

## Capability-path disproof

An independent fresh-file-backed probe injected one additional SQL preparation after the exact
five-call schema-guard prefix through every requested accepted capability path. All paths entered
the same ordered recorder ledger:

| Path | Recorded proof calls | Allowed proof calls | First recorded addition |
| --- | ---: | ---: | --- |
| connection `execute` | 12 | 11 | hidden `execution_fact` read |
| cursor `execute` | 12 | 11 | hidden `execution_fact` read |
| connection `executemany` | 12 | 11 | zero-row domain update with executemany marker |
| connection `executescript` | 12 | 11 | hidden `execution_fact` read with script marker |
| cursor chaining | 13 | 11 | chained `SELECT 1`, followed by hidden read |
| `cursor.connection.execute` | 12 | 11 | hidden `execution_fact` read |
| `getattr(connection, "execute")` | 12 | 11 | hidden `execution_fact` read |
| `hasattr` capability branch | 12 | 11 | hidden `execution_fact` read |

Wrapped cursor results retain the wrapper on chaining, and `cursor.connection` returns the wrapped
recording connection. No accepted SQLite preparation path tested here escaped ordered accounting.

## R3 and prior-finding reconciliation

- **Wrong acceptance-evidence bind — `reproduced-live`:** replacing
  `(acceptance.acceptance_set_id,)` with `(effect.effect_id,)` made the complete focused gate fail
  with 7 failures and 183 passes; the deliberately disjoint effect/set/evidence identities caused
  proof hydration to return `INTEGRITY_FAILURE` instead of `FOUND`.
- **Parenthesized hidden domain read — `reproduced-live`:** the exact
  `SELECT count(*) FROM (execution_fact)` failure-capability case ran in the clean 190-case gate and
  was rejected. The stronger external cursor hidden-read mutant was also rejected by exact ordered
  call count as described above.
- **Comment-prefixed dynamic `COMMIT` — `reproduced-live`:** the cursor-based external mutant above
  preserves the exact R3 comment/dynamic assembly mechanism and adds replacement `BEGIN`; it was
  rejected at `COMMIT` by the runtime tripwire and by the complete gate.
- **Removed active-stream all-or-none rule — `reproduced-live`:** deleting the six-coordinate
  all-null/all-non-null rule made the complete focused gate fail with 1 failure and 189 passes. The
  independent `active_stream_generation_id=None` contradiction returned `FOUND` under the mutant
  and failed its expected `INTEGRITY_FAILURE` assertion; the all-null positive case remained green.

The original REV-0073 codec/direct-key/totality P0 and two production P1 findings, R1's
indexed-range/history-fold P0 and two P1 findings, R2's five failure-capability classes and two
production-semantic P1 findings, R3's four exact mutants, and R4's cursor capability finding were
reconciled against the unchanged production surface and the fresh R5 controls. No earlier
production defect was reproduced in the exact candidate, and every mandatory retained mutant was
killed.

## Disproof pass

The clean candidate passed the complete focused gate. The exact R4 cursor branch was then restored
as an external mutant and could no longer hide: both the ordered proof ledger and source capability
gate failed. The adjacent cursor transaction mechanism failed before commit at the runtime
tripwire. To disprove reliance on that tripwire or final `in_transaction` state alone, the required
raw escape committed seed writes and opened a replacement transaction; the all-table post-rollback
snapshot still failed on durable retained rows. Connection/cursor execution, batch/script,
chaining, `cursor.connection`, dynamic attribute access, and capability-branch counterexamples all
entered the recorder.

No provisional P0/P1 survived this proof rule. No speculative reflection-only concern is counted.

## Unverified items and boundaries

- The author's 563-case integration selection, 61-case R2 oracle, and 1,880-case full
  `tests/execution_core` run were not rerun. The requested bounded 190-case focused gate was run;
  the approximately ten-minute full suite was intentionally not widened into this review.
- Ruff, mypy, Import Linter, the complete governance suite, Python 3.11, external CI, and external
  review state were not rerun.
- No configured/existing or in-memory database, network service, broker, credentials, order,
  migration, DDL/schema change, runtime composition, M2-I4 work, push, PR, promotion, or merge was
  used or performed.

## Final counts and disposition

- **P0: 0**
- **P1: 0**
- **P2: 0**
- **Verdict: ACCEPT**

WO-0167 clears this independent R5 review gate. This acceptance does not activate M2-I4 and does
not authorize promotion, PR, or merge.
