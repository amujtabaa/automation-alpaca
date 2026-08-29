---
type: Review Request
rev_id: REV-0112
work_order_id: WO-0168d
status: AWAITING_REVIEW
review_mode: fresh-context findings-only plan-mutant assertion correction
date: 2026-08-28
allowed_paths:
  - tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
  - work/review/REV-0112/**
  - work/ledger.jsonl
forbidden_paths:
  - app/execution_core/persistence/schema.py
  - app/execution_core/persistence/repository.py
---

# REV-0112 — unaliased plan-mutant semantic assertion correction

## Boundary

Use a fresh context. Review only the correction for the bare `SCAN venue_effect` failure recorded
by the first REV-0111 held execution. Create only `work/review/REV-0112/result.md`; do not edit any
existing file, commit, or push. This is a static findings-only review. Do not connect to SQLite,
access/create a database, install DDL, collect/execute `tests_gated`, migrate, unlock, implement
later work, promote, or merge. `ACCEPT` requires zero open P0/P1.

## Exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168d-plan-mutant-proof-r1`.
- Independently accepted flag-false predecessor:
  `e139a1a1b19ff58c82b189676bc7394b9d4c045e`, tree
  `a76cb8bb1ce8adc9b707d7b2f76f45124075a37f`.
- Test-only candidate: `20c47ba1eb936c73013e9e87ca4e432ed47a8e80`, tree
  `967c832f7b06945ee3f6dbc5290e7654aa2fbdda`.
- Candidate parent is the exact accepted predecessor above.
- Held test blob: `ca6869ec029773afd8e20e8e043714faf6e70ab4`; file SHA-256:
  `9bfc38aa94db25d7be4c7aa2a648334e578fd61a42879f21daedde3a2885fd98`.
- Failure evidence commit: `be445f3`; result blob
  `1c23b172aac249c4272a9536997e4d64ec75ed16`; result SHA-256
  `6c2a4d86985acd6e3bac554fc2d5cc08a3a2a39217ed83f02341b23f69675e44`.
- Frozen DDL: 180,858 UTF-8 bytes at
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Frozen 13-query SQL-manifest SHA-256:
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.
- `schema.py` blob: `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`; human flag: exact `False`.

Ameen authorized persistent bounded root remediation/review/reruns without returning after each
in-scope failure. DDL, query, schema-index, runtime, configured/in-memory database, migration,
credential, broker/network, order, promotion, and merge changes remain excluded.

Any packet-hosting commit may add only this request and one append-only ledger line before review.
Review the exact candidate, not an inferred branch HEAD.

## Root correction

SQLite validly emitted the two-token plan row `SCAN venue_effect`. The owning validator, already
covered by a pure bare-scan control, correctly returns both an `unbounded scan` violation and a
`missing SEARCH` violation for that row. A separate raw assertion duplicated parsing and required
`SCAN VENUE_EFFECT ` with a trailing space, so it failed before checking the validator.

The candidate deletes that duplicate string parser. The integration mutant now requires the
owning validator to report both semantic failures. A generic nonempty violation is no longer
sufficient. The source SQL, plan validator, manifests, DDL, indexes, and runtime are unchanged.

## Review questions

1. Do the two assertions prove the `NOT INDEXED` mutant is detected specifically as an unbounded
   base scan and absence of the required indexed search?
2. Would retaining `INDEXED BY` or weakening the validator cause this control to fail?
3. Does using the owning validator eliminate the trailing-space blind spot without relaxing plan
   requirements or duplicating another parser?
4. Is the one-file diff fully inside authority with no product/query/DDL/index/flag drift?

## Evidence

- RED: fresh held run reached 100%, emitted `('SCAN venue_effect',)`, and failed only the stale raw
  trailing-space assertion. The accepted required-index fresh-prepare correction passed.
- Pure no-connection probe for that exact plan row returns `unbounded scan`, `missing SEARCH`, and
  unexpected-access evidence; the candidate asserts the first two owning semantics.
- Ruff, format, `py_compile`, and `git diff --check` pass.
- DDL/query/schema/flag identities remain frozen and the flag is `False`.
- No held run occurred with this candidate.

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
