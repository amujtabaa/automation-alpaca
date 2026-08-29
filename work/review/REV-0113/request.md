---
type: Review Request
rev_id: REV-0113
work_order_id: WO-0168
status: AWAITING_REVIEW
review_mode: fresh-context executable-contract feasibility and contradiction review
date: 2026-08-28
allowed_paths:
  - work/review/REV-0113/**
---

# REV-0113 — WO-0168 executable-contract preflight

## Boundary

Use a fresh context and produce findings only. Review the exact active work-order contract, not an
implementation. Create only `work/review/REV-0113/result.md`; do not edit source, tests, the work
order, request, ledger, or Git history. Do not connect to SQLite, create/access a database, install
DDL, run `tests_gated`, migrate, compose runtime, load credentials, call a broker/network, place an
order, promote, or merge. `ACCEPT` requires zero open P0/P1.

## Exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- Accepted predecessor: `25aca36956d68db014df3769678699597e9be56a`, tree
  `aa79bee93b51b81d4b004a154f86cc7ca547d17f`.
- Contract candidate: `9485256811e633578c0059afe15b160c4555d8b6`, tree
  `f31bed27f8041550f78c81f6dc502e8b28bf523f`.
- Candidate parent is the exact predecessor above.
- Active work-order SHA-256:
  `bcc99128c68cb4784b83b9c13b597f77745cce30acf71aab59e53777d48f04a9`.
- Frozen unchanged DDL: 180,858 UTF-8 bytes; SHA-256
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Human flag remains exact `False`; the accepted flag-true execution branch is quarantined.

## Read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/active/WO-0168-m2-i4-atomic-unit-of-work-effects.md` in full.
3. Companion contract 06 sections 2.3-3 and R12.2-R12.5.
4. Companion R7 sections 3-5 for exact runtime lease identity and L00-L08.
5. `app/execution_core/persistence/operations.py` operation/projection types.
6. `repository.py` capability, durable input, direct proof, and checkpoint methods.
7. `checkpoint_codec.py` `_project_runtime_checkpoint` and envelope behavior.
8. The eight public reducer entry points and their result types in owner modules.

## Contract decisions to challenge

1. The UOW receives full authentic in-memory owner objects but trusts none directly. Inside the
   transaction it selects current direct proof and passes all owners through the accepted runtime
   checkpoint projector. Is this a complete freshness/authenticity check for a running process,
   while leaving cold reconstruction to WO-0169, or does a specific reachable owner member escape
   the projection and permit stale state?
2. The UOW calls only the existing eight public reducer pipelines and derives repository rows from
   their exact predecessor/result objects. Does any row require semantic inference not exposed by
   the owning result? Name the concrete missing evidence and operation; do not require speculative
   `_M2*` types merely by naming convention.
3. Owner-level `REFUSED`, `STALE`, or semantic `EXACT_REPLAY` is a committed durable decision with
   receipt/outcome but no authority/checkpoint write. Technical refusal, primary replay, and
   primary identity conflict roll back/short-circuit. Is this partition consistent with the
   durable-input lifecycle, mandatory receipt rule, and R7 L03?
4. Technical IDs/ordinals use fixed, explicit next-value SQL under one `BEGIN IMMEDIATE` writer.
   Does any accepted trigger/table make that unsafe or nondeterministic, or require a new DDL
   sequence surface?
5. Commit ambiguity retires the lease, makes one commit attempt, performs no rollback/retry or
   eligibility publication, and returns reconciliation-only after closing where supported. Is any
   claimed observable state stronger than the evidence permits?
6. Are the public API, exact transaction order, unchanged-DDL boundary, TDD fault matrix, allowed
   paths, and bounded review protocol implementable without a second engine, generic callback,
   caller-authored write plan, or needless architecture?

## Required disproof pass

For every provisional finding, identify the exact accepted clause, reachable counterexample, and
smallest owning-boundary correction. Attempt to refute the finding against current code before
retaining it. Preference or a hypothetical future API is not a P1.

End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

State explicitly that no SQLite/database/DDL/held-suite execution occurred.
