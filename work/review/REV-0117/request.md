---
type: Review
review_id: REV-0117
work_order_id: WO-0169
review_mode: fresh-context static pre-execution integration review
status: REVIEW
authoritative_diff: c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51..f6f64207faa3ffa57224a5755536638d981fdfcb
---

# REV-0117 — WO-0169 cold startup and reconciliation review

Return findings only. Do not edit, commit, push, or implement fixes. Re-derive the candidate from
the exact diff, accepted work order, source, and tests. Prior summaries and earlier reviewer notes
are findings-input, never authority.

This is round one of one bounded WO-0169 review packet. It is intentionally static before the
separate human gate permits the one held fresh-file SQLite proof. If a concrete P0/P1 is confirmed,
one root-remediation round and one exact-head correction review are the maximum. A second-round
failure remains an explicit blocker or requires claim re-diagnosis; it does not open a review
treadmill.

## Exact identity

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Accepted WO-0168 predecessor: `c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51`.
- Static candidate: `f6f64207faa3ffa57224a5755536638d981fdfcb`.
- Candidate tree: `ca677a9fe854e5c3cd34646eabf9ce340894f7d7`.
- Review exactly:
  `c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51..f6f64207faa3ffa57224a5755536638d981fdfcb`.
- Diff size: 33 files, 11,723 insertions, 202 deletions.
- `startup.py` blob: `043ad103d9a91b7b68b99709594cd1de56ab2a13`.
- `checkpoint_codec.py` blob: `d84a912c6e73135d398a9792d5cdd12900623d28`.
- Pure cold-recovery test blob: `a68ce0a4ea3bd3d3da14febe200c14807c391538`.
- Active-owner hydration test blob: `f75cff5840e3143b0cee11b7f6eefd7898ccb729`.
- Held SQLite proof blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Flag-false schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- DDL: 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `EXPECTED_EXECUTION_DDL_SHA256` equals that digest and
  `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact boolean `False`.

## Read order

1. `AGENTS.md`, the safety core in `CLAUDE.md`, and
   `work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md`.
2. `work/review/REV-0116/result-r3.md` and `disposition-r3.md` for the accepted contract only.
3. `app/execution_core/persistence/startup.py`, `owner_lock.py`, `market_recovery.py`,
   `unit_of_work.py`, and the private checkpoint hydration/projection seams.
4. The changed owner modules and the pure tests in the exact diff.
5. `tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py` statically only.

## Threat model and acceptance criteria

In scope: a cold process may serve with the wrong owner lease, a forged/stale checkpoint, omitted
current authority, an unresolved claimed effect, a retried ambiguous commit, incomplete source
fencing, or a non-failing proof test. Also in scope are regressions introduced by the final root
corrections: known claimed outcomes must not be queried again, while all uncertain claimed states
must remain blocking.

Out of scope: warm restart, a production lock implementation, broker/source adapters, configured
databases, migrations, M2-I6/M3 design, taste-only refactors, and hypothetical concerns outside the
accepted injected-capability model. Record such matters as nonblocking proposals rather than
expanding this review.

Acceptance requires source/contract proof or a concrete failure-capable counterexample for every
P0/P1. The candidate must:

1. acquire and retain the owner lease before datastore or source access;
2. hydrate only proof-bound compact non-serving owners from inert checkpoint bytes;
3. atomically publish the compact cold-invalidated successor before reconciliation;
4. query every and only current uncertain claimed effect through M2-I4 operations;
5. refuse on classified cutover/query/commit/current-proof uncertainty without publishing caller
   state or retrying an ambiguous commit;
6. apply the final idempotent invalidation barrier and prove post-subscription fence/baseline
   currentness before serving; and
7. provide a held fresh-file test that would fail if the C0-to-C1 transaction, persisted broker
   outcome, or exact-replay behavior were wrong.

Permitted evidence: static source/contract tracing, targeted ordinary pure tests, mutation or
fixture analysis, and concrete in-model counterexamples. Do not open SQLite, create a database,
install DDL, run `tests_gated/**`, or change the checkout.

## Fresh supplied evidence

- 596 relevant pure/import-boundary tests passed across cold recovery, UOW, checkpoint codec,
  active-owner hydration, runtime-checkpoint pure behavior, import boundaries, and venue hardening.
- Ruff check and format check passed all five changed Python files, including the held proof.
- mypy passed all 99 application source files.
- Work-order scope and `git diff --check` passed.
- The held SQLite proof was parsed/linted but deliberately not executed.
- No DDL byte changed; no SQLite connection/database, configured path, migration, runtime
  composition, credentials, broker/network activity, orders, promotion, master merge, history
  rewrite, or M3 implementation occurred.

## New-invariant probe declaration

No repository-wide `INV-*` entry is added or amended by WO-0169. Fresh work-order probes include:

- CR-08/CR-12: one real claimed C0 is projected and compact-hydrated; the held proof requires a
  persisted `ACKNOWLEDGED` C1 and a zero-query exact replay on the second cold start.
- CR-15: pure failure-injection covers rollback, commit ambiguity, final invalidation, and direct
  reread classification.
- CR-17/CR-18: known terminal outcomes are not queried again; `DISPATCH_CLAIMED`,
  `OUTCOME_UNKNOWN`, and `NEEDS_REVIEW` remain non-serving.

## Mandatory review lenses

1. Lock/order/lifetime and every refusal path.
2. Checkpoint authenticity, compact-owner completeness, and omitted-history boundaries.
3. Reconciliation union, route binding, lifecycle totality, and operation attribution.
4. UOW atomicity, rollback, commit ambiguity, reread, and idempotent replay.
5. Source subscribe/fence/baseline/currentness ordering.
6. Test-critic disproof, especially whether the held SQLite proof can fail independently of its
   fixture and whether a green result would prove the claimed transaction chain.
7. Scope, safety, and needless-complexity check against the accepted contract.

## Output and finite stop

For each retained P0/P1/P2: severity, `file:line`, violated clause or demonstrated failing case,
real-world impact, smallest root correction, and evidence level (`reproduced-live` or
`reasoned-only`). Perform a disproof pass against your own finding before retaining it. Do not
create a finding for preference, an alternate architecture, or an out-of-model threat.

End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1. State that no SQLite/database/held-suite execution occurred.
