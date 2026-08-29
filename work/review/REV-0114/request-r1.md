# REV-0114 correction-only static review — held test remediation

Date: 2026-08-29

Status: **AWAITING REVIEW — execution gate closed**

## Boundary

Use a fresh context. Review only the three test-contract/fixture corrections made after the first
REV-0114 fresh-file run. Return findings only as `result-r1.md`; do not edit implementation,
tests, the request, or prior reviewer artifacts. Do not import/invoke `sqlite3`, connect to a
database, install DDL, collect or execute `tests_gated`, migrate, unlock, implement later work,
promote, or merge.

## Exact identities — verify, do not trust

- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- Accepted changed-DDL source candidate:
  `b7bf7d2d4f5356a3977fd68cc1dc6cfcdf0dbaae`, tree
  `3c1eab6ad18c6865e9cbf4e5b33dd343bd3b036c`.
- First execution unlock: `99f14907d0b4cfdb7ebeff20492c9c101ca9aeb9`, tree
  `2828f325cb83867ab58428a41becc308a420f13b`; quarantined.
- Test-only correction candidate:
  `9a79f5821d5c74bf4b8650868e91e36ca18d4f95`, tree
  `bb0c8c0ce07cc5eeb7c4daf8b50927423f6e5476`.
- Correction diff: `26f19230891710224e908cc59ac9b7b26dcbc213..9a79f5821d5c74bf4b8650868e91e36ca18d4f95`.
- DDL remains 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob remains `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- Corrected schema-suite test blob: `911e5b3b17307f4920264fd84a1eded82d456cdd`;
  SHA-256 `ef6486a755c288f2c5c7eec8b4f1b1ade2b076a2b3ad5b5df8d4892098fabe25`.
- Corrected WO-0168 test blob: `940b1326a9ed2528a612b097ae69bcdb84f99b27`;
  SHA-256 `5e02cfaf732a940f43955ce2c9a8e22e5c203eaa5aa66672a948c273ecaa9151`.
- Attempt-one evidence SHA-256:
  `193c365718fb9ea145f8b6d6fe2265c564aa1b83c21e1fe5bb147ef4a956e07e`.

## Failure and correction map

The exact five-suite run collected 381 tests, reached 100%, and returned 6 failures / 375 passes.
Attempt 2 was not run.

1. Cross-root route refusal now requires the precise owning guard message instead of obsolete
   generic `FOREIGN KEY` text. Confirm this strengthens attribution and still fails if the guard is
   removed or routes the wrong root.
2. The serial late-owner expected final controller head/version changes from `(6, 7)` to `(5, 6)`.
   Confirm the setup starts at `(2, 3)`, exactly three late owners each advance once, and their exact
   matching invalidations do not advance again.
3. The shared dormant-position fixture changes first `fact_id`/default ordinal from 900 to 1.
   Confirm the database is empty of execution facts at that point, identity 1 is unused, and the
   four affected controls now reach their intended positive/negative/dormant protection assertions
   without changing the tested semantics.

Static evidence: both files compile, Ruff check/format pass, work-order scope and governance checks
pass, DDL identity and flag are unchanged. Held tests were not rerun on the correction candidate.

## Finite stop and response

This is one correction-only static review. Block only for a concrete stale expectation, fixture
collision, weakened assertion, scope violation, or DDL/flag drift. Do not reopen accepted schema
design. End with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

State explicitly that no SQLite/database/DDL/held-suite execution occurred.
