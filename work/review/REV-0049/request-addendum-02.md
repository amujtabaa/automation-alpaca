---
type: Review Request Addendum
rev_id: REV-0049
addendum: 02
title: "WO-0147 checkpoint continuity and authority-state validation"
status: AWAITING_REVIEW
prior_review_target: 41c7e956d1c49b450615a03374bd0ef7ee730357
reviewed_target: 4e935851edd26f9f38ea93a9544815f5b49ecf88
focused_base: 41c7e956d1c49b450615a03374bd0ef7ee730357
original_failed_target: 1d294e0ac29dcd169a4733df3aa9cbd337dc8787
date: 2026-08-02
---

## Independent assignment and communication rules

This is an authorized, local, offline review of deterministic Python state transitions in this
repository. It requires no external account, credential, network service, remote system, or
external-system assessment. The entire task is local software quality assurance. Use the
vocabulary **local invariant check**, **focused
counterexample**, **invalid-state acceptance**, **failure-capability check**, and **independent
critical review** in prompts and status messages.

Review exact target `4e935851edd26f9f38ea93a9544815f5b49ecf88`. Re-derive conclusions from the accepted ADRs,
normative WO-0147 contract, source, and fresh local evidence. Author claims and prior green results
are context only. Write findings only to
`work/review/REV-0049/result-addendum-02.md`; preserve every request, prior result, implementation,
test, work-order, and evidence artifact byte-for-byte.

Keep chat output minimal: status while working, then only the final verdict and result path. Put
detailed reasoning, commands, and evidence in the result artifact. If platform classification
interrupts the review, produce no result and report only
`INTERRUPTED — no engineering verdict produced`; do not retry from the interrupted context. A
platform interruption is not `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`.

## Frozen object and scope

```text
original blocked implementation: 1d294e0ac29dcd169a4733df3aa9cbd337dc8787
prior repaired target:           41c7e956d1c49b450615a03374bd0ef7ee730357
final re-gate-6 target:          4e935851edd26f9f38ea93a9544815f5b49ecf88
focused delta:                   41c7e956d1c49b450615a03374bd0ef7ee730357..4e935851edd26f9f38ea93a9544815f5b49ecf88
complete repair range:           1d294e0ac29dcd169a4733df3aa9cbd337dc8787..4e935851edd26f9f38ea93a9544815f5b49ecf88
```

Verify object identity, parentage, and changed paths. The focused delta may change only:

```text
app/execution_core/authority.py
app/execution_core/venue.py
tests/execution_core/test_authority.py
tests/execution_core/test_venue_provenance_hardening.py
work/active/WO-0147-reset-kernel-c-trading-authority-controls.md
work/review/REV-0049/request-addendum-01.md
```

The last path is preserved request history from the intervening request-only commit; it is not
implementation evidence. No accepted ADR, reset-queue record, legacy/runtime source, store,
database, adapter, API/UI, or CI workflow may change.

No broker activity, credentials, network access, SQL/DDL, database client or engine, migration or
schema tool, runtime wiring, push, PR, merge, deletion, or cleanup is needed or permitted. Use only
pure in-memory checks, static inspection, focused existing tests, and temporary source changes that
are exactly restored. Do not use application or test paths that initialize a database.

## Spec-first review order

Before reading the repair evidence in the later WO-0147 checkpoints, derive the applicable
properties from:

1. `AGENTS.md` safety core and review rules.
2. ADR-020 execution-state, reconciliation, mutation-authority, and final-claim clauses.
3. ADR-021 unified admission/create/final-claim and manual-control clauses.
4. ADR-022 reset-beta scope and authority exclusions relevant to M1C.
5. `work/queue/ARCH-RESET-2026-07/06-roadmap.md`, M1 item 3 only.
6. WO-0147 from `Activation and authority` through `Stop conditions`.

Pre-register concrete local counterexamples before reading the author checkpoint. No INV entry was
added or amended since the prior request, so the PROC-0001 new-invariant probe set remains empty;
fresh scenarios are nevertheless mandatory.

## Required issue closure

Independently classify and close or keep open each item below with exact `file:line` evidence and a
fresh counterexample outcome:

1. Original REV-0049 P0: caller-shaped completion metadata must not clear venue uncertainty or
   create final-claim authority in public or private M1 paths.
2. Original REV-0049 P1: a residual change after manual SELL creation must have a safe local retry
   lifecycle without identity reuse, duplicate claim, or budget debit on refusal.
3. Original REV-0049 P1: new query claims are admitted only in `RECONCILING` or `SERVING`, while
   exact replay/conflict remains permanently ordered ahead of mutable phase policy.
4. Later private-closure P0: direct private calls, reconstruction, and replay must not treat raw
   externally shaped closure values as certified coverage.
5. Re-gate-6 P0: audit reconstruction must reject coordinated omission of an unresolved claimed
   effect and every correlated effect, claim, identity, input, binding, and registry field. An
   internally consistent empty replacement must not turn a blocking venue view into a clear one.
6. Re-gate-6 malformed-state finding: every top-level `ExecutionAuthorityState` field must have its
   exact shallow type checked before replay lookup, policy, property access, or mutation. In
   particular, string-valued enum lookalikes and integer-false kill state must be rejected rather
   than accepted by Python equality/truthiness.

The new repair is intentionally small: one slow-path exact checkpoint comparison and one
constant-work state-shape validator. Determine whether that is sufficient without inventing a new
public capability, persisted loader, caller approval value, or retained-history scan. Loading a
distinct authenticated persisted snapshot remains deferred to M2.

## Minimum fresh evidence

Create and record at least these four independent, pure scenarios rather than merely rerunning the
new named tests:

- an unresolved claimed BUY reconstructed with all correlated tuples and registry fields omitted;
  show reconstruction refuses and the original authority view remains blocking;
- raw phase/fence strings and `kill_engaged=0` supplied to query and manual-control paths; show
  rejection occurs before budget, venue, input, query, or manual indexes change;
- an exact previously applied query replayed from a state whose phase field was changed to a raw
  string; show state validation occurs before the replay can return; and
- one prior-review closure scenario covering private completion input, query phase drift, or late
  manual residual replacement, with the final authority outcome recorded.

Run at least two reversible failure-capability checks and record baseline/final SHA-256 values:

- remove or neutralize the exact checkpoint comparison and show the coordinated-omission case
  fails; and
- move state validation after the exact replay return, or weaken exact Boolean validation, and
  show the matching focused case fails.

Restore the exact target before writing the result. A check that stays green after its intended
control is weakened is a new P1 test-strength finding.

## Minimum reproduction gates

With `BROKER_ADAPTER=mock` and cache writes disabled, reproduce:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_venue_provenance_hardening.py::test_audit_hydration_rejects_coordinated_checkpoint_omission tests/execution_core/test_authority.py::test_authority_reducer_rejects_malformed_top_level_state_before_replay tests/execution_core/test_authority.py::test_authority_reducer_validates_state_before_exact_replay tests/execution_core/test_authority.py::test_manual_flatten_rejects_integer_kill_state_before_mutation
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core --maxfail=1
.\.venv\Scripts\python.exe -m ruff check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m ruff format --check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app/execution_core
.\.venv\Scripts\lint-imports.exe
git diff --check 41c7e956d1c49b450615a03374bd0ef7ee730357..4e935851edd26f9f38ea93a9544815f5b49ecf88
```

The author reports 18/18 focused, 710/710 execution-core, 61/61 R2, and 5,298 collected repository
tests with raw combined branch coverage `93.02945093976616%`. These are author evidence, not
independent proof. Full repository coverage, R2, SQL/SQLite, and external CI are not required for
this pure review. Do not claim them as reproduced unless actually run.

## Result contract

For every required item, state `CLOSED` or `OPEN`, evidence level, exact source lines, and fresh
scenario outcome. Report every new P0/P1 separately with impact and the smallest adequate
resolution. State anything not verified. Do not implement fixes.

End with exactly one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`.

`ACCEPT` requires every required P0/P1 closed, no new unresolved P0/P1, exact target restoration,
and a failure-capable result. Acceptance clears only the independent review gate. WO-0147 still
requires disposition, Fable/ledger/PKL closeout, one final immutable push, and unchanged exact-head
Python 3.11/3.12 CI before WO-0148 may activate.
