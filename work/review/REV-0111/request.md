---
type: Review Request
rev_id: REV-0111
work_order_id: WO-0168d
status: AWAITING_REVIEW
review_mode: fresh-context findings-only required-index proof correction
date: 2026-08-28
allowed_paths:
  - tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
  - work/review/REV-0111/**
  - work/ledger.jsonl
forbidden_paths:
  - app/execution_core/persistence/schema.py
  - app/execution_core/persistence/repository.py
---

# REV-0111 — required-index fresh-prepare proof correction

## Role and finite boundary

Use a fresh context. Review only the root correction for the required-index negative-control
failure recorded in `work/review/REV-0110/execution-result.md` on the published execution branch.
Create only `work/review/REV-0111/result.md`; do not edit any existing file, commit, or push.

This is a static findings-only review. `ACCEPT` requires zero open P0/P1. Do not connect to
SQLite, access/create a database, install DDL, collect or execute `tests_gated`, migrate, unlock,
implement later work, promote, or merge.

## Authority and exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168d-required-index-proof-r1`.
- Accepted flag-false predecessor: `f1f1ad2dd5287ea3295f72298ef520151dc6ed75`, tree
  `70e9fc519b4adc706f5cddcf50383b11180a6c6f`.
- Test-only candidate: `e139a1a1b19ff58c82b189676bc7394b9d4c045e`, tree
  `a76cb8bb1ce8adc9b707d7b2f76f45124075a37f`.
- Candidate parent is the exact predecessor above.
- Held test blob: `3482d9162dc793d71e62ca7e1dd401242b406b6f`; file SHA-256:
  `c472e8dfcd322b80782eece643ea7a3c8ac54655141e8f345f9d8cd4505524f5`.
- Frozen DDL: 180,858 UTF-8 bytes at SHA-256
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Frozen 13-query SQL-manifest SHA-256:
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.
- `schema.py` blob: `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- REV-0110 execution evidence commit:
  `d15a4bf461616e22eb93c77f008c0592b61bdd79`; result blob
  `b6cd18616917e5dfb00684b54b40051b5876ea6e`; result SHA-256
  `7ebc494d980bb7e443f21ec2fa154f482dc6bbf7de071a6a7b033e810823aa4f`. Read it with
  `git show d15a4bf461616e22eb93c77f008c0592b61bdd79:work/review/REV-0110/execution-result.md`.

Ameen authorized Codex to persist through bounded root diagnosis, test/proof remediation, review,
and fresh-file reruns without returning after each intermediate failure. DDL, repository-query,
schema-index, runtime, configured/in-memory database, migration, credential, broker/network,
order, promotion, and merge changes remain outside this correction.

Any packet-hosting commit may add only this request and one append-only ledger line before review.
Review the exact candidate above, not an inferred branch HEAD.

## Reproduced root cause

REV-0110 attempt 1 removed the first required manifest index inside a savepoint, then reused the
same `EXPLAIN QUERY PLAN` SQL text that had already been prepared earlier in the connection. It
reported the deleted index instead of raising, so the negative control failed.

A fresh file-only minimal reproduction established the mechanism:

```text
before     SEARCH probe USING COVERING INDEX ix_probe_key
same-text  NO_ERROR; stale plan still names ix_probe_key
fresh-text OperationalError: no such index: ix_probe_key
```

Python's SQLite connection caches prepared statements by exact SQL text. The candidate appends an
inert per-index comment only to the post-drop negative-control probe, forcing a fresh prepare. It
also strengthens attribution by requiring exact `no such index: <index>` text. The repository SQL
tuple is not modified.

## Review questions

1. Does the changed SQL text force a fresh preparation without changing query semantics?
2. Does matching `no such index: <index>` prove the intended dropped-index failure rather than an
   unrelated `OperationalError`?
3. Would removing the cache-busting comment reproduce the observed surviving mutant?
4. Is the correction confined to the owning held negative control, with no DDL/query/index/
   runtime/public-API or authority drift?

## Author evidence

- RED: exact REV-0110 held execution reached 100% and failed because the drop-index probe did not
  raise; attempt 2 was correctly not run.
- Root reproduction: same prepared SQL remained stale after the transactional drop; text differing
  only by an inert comment raised `no such index`.
- Candidate static checks: Ruff clean, formatting clean, `py_compile` clean, and
  `git diff --check` clean.
- DDL, query manifest, schema blob, and flag-false authority were re-derived unchanged.
- The held suite has not been collected or executed with the candidate.

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
