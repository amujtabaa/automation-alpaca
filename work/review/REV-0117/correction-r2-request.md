# REV-0117 WO-0169 failed-execution correction review R2

Date: 2026-08-29

Status: **OPEN — STATIC CORRECTION REVIEW ONLY**

## Exact review identity

- Branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Failure-evidence predecessor: `f8b14ae46d12319d1d4e33f9a5d8d643b0e8bb21`.
- Root-correction candidate: `dee3533099bba6ffeaa3372d33b04c1513cd75b7`.
- Candidate tree: `50861bbcc4d6e1b68490f619132fb16338a30e8e`.
- Review range: `f8b14ae46d12319d1d4e33f9a5d8d643b0e8bb21..dee3533099bba6ffeaa3372d33b04c1513cd75b7`.
- Changed paths in that range:
  - `app/execution_core/persistence/checkpoint_codec.py`
  - `tests/execution_core/test_persistence_startup_hydration.py`

Read `execution-result-attempt-1.md` first. The failed SQLite attempt and its database are immutable
evidence; do not execute or inspect the database through SQLite.

## Correction claim to challenge

The acquisition domain intentionally numbers its genesis generation at zero. The accepted durable
schema intentionally numbers the corresponding first retained row at one, so a NULL predecessor
identifies the first durable row. M2-I4 already applies `domain ordinal + 1` at the repository
boundary. Checkpoint hydration incorrectly compared the durable row ordinal directly to the domain
ordinal, and its shared proof fixture used domain/non-durable vocabulary in durable records.

The candidate makes only the boundary correction:

1. live and unresolved checkpoint generations require durable ordinal = domain ordinal + 1;
2. the shared active proof uses durable ordinal 1 for domain genesis 0;
3. durable controller/protection/effect classes use `CONSISTENT` / `NORMAL`, not the domain-style
   fixture labels `ACTIVE` / `DORMANT`;
4. positive and failure-capable off-by-one assertions pin the translation.

`SCHEMA_DDL`, its expected digest, the held test, and the human authorization flag are unchanged.

## Required finite review lenses

1. Re-derive the zero-based-domain to one-based-durable mapping from production acquisition,
   schema, unit-of-work, and checkpoint code. Reject a fixture-only disguise.
2. Verify both live and unresolved generation comparisons use the same correct mapping.
3. Verify the durable class corrections match the accepted schema and M2-I4 authority checks.
4. Verify the new tests fail if the plus-one mapping is removed or if the shared fixture regresses
   to the prior invalid durable coordinates.
5. Check for a simpler root correction, hidden DDL drift, held-test drift, authorization-flag
   change, scope creep, or a new P0/P1 defect.

This is one correction-only static review. Do not reopen the accepted whole-work-order review and
do not require unrelated hardening. Return `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` with exact
P0/P1/P2 counts. Write the independent result to `result-r2.md`; do not edit this request or any
source/test file.

## Author evidence to reproduce or inspect, not inherit

- Changed hydration file: 22 passed.
- Full ordinary non-SQLite boundary: 2,261 tests collected; full run reached 100%, exit code 0.
- Ruff check: pass on both changed Python paths.
- Ruff format check: both changed Python paths already formatted.
- mypy: success on 99 application source files.
- Correction-range `git diff --check`: pass.
- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob unchanged: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- Held-test blob unchanged: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` remains exact boolean `False`.

No SQLite connection, fresh database, held-suite execution, migration, DDL change, configured DB,
credential, broker/network activity, order, later work order, promotion, or merge is authorized for
this review.
