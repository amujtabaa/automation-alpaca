---
type: Review Result
rev_id: REV-0110
work_order_id: WO-0168d
status: COMPLETE
review_mode: fresh-context findings-only static Q3 plan-proof remediation review
reviewed_base: c27bb94e45022228d94812f9e1b5fd186787eb1b
reviewed_candidate: f1f1ad2dd5287ea3295f72298ef520151dc6ed75
---

# REV-0110 — independent static review result

No findings. The bounded-intermediate remediation satisfies the stated static
plan-proof contract without changing frozen query SQL, DDL, schema indexes,
execution authority, runtime behavior, public API, or an unrelated path.

## Identity and scope evidence

- Verified the candidate is a commit whose sole parent is the exact remediation
  base. The base and candidate trees are respectively
  `4e9cf8535f00817e655514865f852b3d5ab98098` and
  `70e9fc519b4adc706f5cddcf50383b11180a6c6f`.
- Verified the candidate blobs and working-tree SHA-256 values: `repository.py`
  is `a147805eb486e76ba0069b7bafbac7cc44961a96` /
  `6f1b6ea89e795030d8e9815c9fa26acaa4f74e87984258c169f3759ee1870a33`, and
  the held test is `f7e43c3d407443e88531c50579e50af0b17f5027` /
  `13f36766ac2e77048365aeb033ed97e97e088b3dd8aa82dc65e701a3bff2ed77`.
- The exact diff changes only the two permitted source/test files (51 additions
  in `repository.py`; 80 additions and 14 deletions in the held test). `git diff
  --check` is clean. The candidate `schema.py` blob remains
  `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`; its diff is empty, the frozen DDL
  digest remains `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`,
  and `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact boolean `False`.
- A no-connection source import confirmed 13 frozen selection SQL members, 13
  base-access metadata members, 13 intermediate-metadata members, aligned tuple
  lengths, and the required NUL-separated manifest SHA-256
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.

## Re-derived plan-proof contract

`select_runtime_checkpoint` obtains Q2 before Q3--Q13 and rejects Q2 at the
4,097-row refusal sentinel (`repository.py:4743-4749`); later result families
also retain their 65,536-row refusal checks (`repository.py:4802-4812`,
`4889-4899`). The correction therefore records only named, bounded
materialized CTE/subquery access rows, per individual frozen query; it does not
alter the queries or make a base-table scan acceptable.

Every declared base source is still handled first. The checker identifies exact
`SEARCH`/`SCAN` access names, emits violations for a base scan and any automatic
base index, requires an eligible search (and the named forced index where
declared), and consumes the matching base row before considering intermediates
(`tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py:51-104`).
The new intermediate metadata is an explicit per-query multiset
(`repository.py:4324-4349`, `4443-4465`): it can consume no more than one
remaining matching plan row per declaration, and all remaining `SEARCH`/`SCAN`
details are rejected as unexpected (`test_persistence_runtime_checkpoint_sqlite.py:106-119`).

## Disproof pass

- **Undeclared or undersized intermediate allowance:** static control at
  `test_persistence_runtime_checkpoint_sqlite.py:138-165` supplies two `SCAN
  selected` rows. One fewer allowance leaves `SCAN SELECTED` available and the
  checker returns it as an unexpected access.
- **Base scan mislabeled as an intermediate:** `plan_access_name` recognizes a
  bare `SCAN expected` (`:51-58`), so the base pass emits both the unbounded-scan
  and missing-search failures before the intermediate pass can consume that row;
  the static control asserts both failures (`:168-178`).
- **Missing base search or automatic base index:** the base pass is independent
  of intermediate metadata and emits the missing-search failure (`:90-103`) and
  automatic-index failure (`:85-88`) before any intermediate matching. A
  declaration cannot clear either recorded violation.
- **Alias-prefix collision and bare-scan blind spot:** the old prefix-only
  matching is replaced by tokenized exact-name equality for both `SEARCH` and
  `SCAN` (`:51-73`); names that merely share a prefix are not equal, while a
  two-token bare scan is no longer skipped.
- **Regression/scope counterexample:** the exact diff adds plan metadata and
  checker/control wiring only. The SQL manifest, frozen schema blob, authority
  flag, and every non-permitted path are unchanged.

No SQLite/database connection, database access or creation, DDL installation,
held-suite collection or execution, migration, implementation/request/ledger
edit, commit, or push occurred during this review.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: Dynamic `EXPLAIN QUERY PLAN` evidence and all held-suite/SQLite execution were intentionally not run under this static-only review authority; the author-reported runtime results were not treated as reproduced evidence.
