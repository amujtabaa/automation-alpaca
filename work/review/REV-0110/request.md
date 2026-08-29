---
type: Review Request
rev_id: REV-0110
work_order_id: WO-0168d
status: AWAITING_REVIEW
review_mode: fresh-context findings-only static Q3 plan-proof remediation review
date: 2026-08-28
allowed_paths:
  - app/execution_core/persistence/repository.py
  - tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
  - work/review/REV-0110/**
  - work/ledger.jsonl
forbidden_paths:
  - app/execution_core/persistence/schema.py
---

# REV-0110 — bounded intermediate query-plan proof remediation

## Review role and finite boundary

Use a fresh context. Review only the root correction for the substantive Q3 failure recorded in
`work/review/REV-0109/execution-result.md`, including regressions introduced by that correction.
Create only `work/review/REV-0110/result.md`; do not edit any existing file, commit, or push.

This is one bounded static review, not a reopened DDL-intent review. `ACCEPT` requires zero open
P0/P1. No SQLite connection, database creation or access, DDL installation, held-suite collection
or execution, migration, unlock, later work order, promotion, or merge is authorized.

## Human authority and exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168d-q3-plan-proof-r1`.
- Remediation base: `c27bb94e45022228d94812f9e1b5fd186787eb1b`, tree
  `4e9cf8535f00817e655514865f852b3d5ab98098`.
- Source/test candidate: `f1f1ad2dd5287ea3295f72298ef520151dc6ed75`, tree
  `70e9fc519b4adc706f5cddcf50383b11180a6c6f`.
- Candidate parent is the exact remediation base above.
- `repository.py` blob: `a147805eb486e76ba0069b7bafbac7cc44961a96`; file SHA-256:
  `6f1b6ea89e795030d8e9815c9fa26acaa4f74e87984258c169f3759ee1870a33`.
- Held runtime-checkpoint test blob: `f7e43c3d407443e88531c50579e50af0b17f5027`; file SHA-256:
  `13f36766ac2e77048365aeb033ed97e97e088b3dd8aa82dc65e701a3bff2ed77`.
- Frozen DDL: 180,858 UTF-8 bytes at SHA-256
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Unchanged `schema.py` blob: `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- Exact 13-query SQL-manifest SHA-256, using NUL-separated UTF-8 SQL strings:
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.

Ameen authorized the bounded root correction after Codex diagnosed the observed `SCAN SELECTED`
as a bounded materialized-CTE access that the proof checker incorrectly classified as an
unbounded base-table scan. The authority permits explicit per-query bounded-intermediate plan
metadata, strict base-table indexed/primary-key search requirements, and failure-capable static
controls. It does not permit DDL bytes, query SQL, schema indexes, runtime behavior, later work,
or another SQLite run to change.

Any later packet-hosting commit may add only this request and one append-only ledger line before
review. Review the exact source/test candidate above, not an inferred branch HEAD.

## Read order

1. `AGENTS.md`, especially safety and independent-review rules.
2. `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`.
3. `work/review/REV-0109/execution-result.md`.
4. This request.
5. Exact diff `c27bb94e45022228d94812f9e1b5fd186787eb1b..f1f1ad2dd5287ea3295f72298ef520151dc6ed75`.

## Root diagnosis to re-derive

The preserved failed-gate database contains 10,001 stress rows in each relevant base table.
SQLite 3.53.1 materialized Q3's `selected_scope` CTE, used the required covering index to populate
it, then reported `SCAN selected` while driving indexed/primary-key searches of the base tables.
Q2 bounds accepted scopes to at most 4,096 before Q3. Historical proof policy explicitly allowed
such bounded materialized CTE/subquery scans. The later exact-access checker accidentally rejected
every unmatched `SEARCH`/`SCAN`, thereby treating a bounded intermediate as a base-table defect.

The correction:

1. adds a per-query upper-bound multiset of named materialized CTE/subquery plan sources;
2. preserves exact required index/primary-key searches for every declared base source;
3. consumes at most one plan row per declared intermediate occurrence;
4. still rejects undeclared plan accesses, base scans, missing base searches, and automatic base
   indexes; and
5. parses exact plan access names so a bare `SCAN expected` cannot evade the base-scan control.

## Review questions

1. Can any bounded-intermediate declaration excuse a scan, missing search, or automatic index for
   a declared base source?
2. Are intermediate names and multiplicities explicit upper bounds, with every unmatched
   `SEARCH`/`SCAN` still rejected?
3. Does exact-name parsing avoid both alias-prefix collisions and the prior bare-scan blind spot?
4. Do the pure controls fail if intermediate allowance is absent/too small, or if a base scan is
   mislabeled as an intermediate?
5. Did the candidate change any query SQL, DDL byte, schema index, execution authority, runtime
   behavior, public API, or unrelated path?

## Author static evidence

- Expected RED: the new intermediate-multiplicity control initially failed with `TypeError`
  because the checker had no intermediate manifest parameter.
- Pure helper controls: PASS for unlisted-search rejection, exact intermediate multiplicity, and
  base-scan non-reclassification. They import source only and create no connection.
- Read-only diagnostic proof against the preserved failed-gate file: all 13 actual EXPLAIN plans
  produce zero violations with the candidate metadata; `PRAGMA query_only=1`; no creation, write,
  or DDL occurred. This is diagnosis evidence only, not a rerun of the held gate.
- Ordinary no-I/O boundary suites: 22 passed.
- Ruff check: clean; Ruff format check: clean; mypy: 95 source files clean; import-linter: six
  contracts kept; `py_compile` and `git diff --check`: clean.
- Frozen identities above were re-derived after the candidate commit.
- The held suite itself was not collected or executed after the failure.

## Response contract

For each finding, give priority, exact `file:line`, governing requirement, evidence level,
concrete impact, smallest complete resolution, and a disproof pass. End with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

State explicitly that no SQLite/database/DDL/held-suite execution occurred.
