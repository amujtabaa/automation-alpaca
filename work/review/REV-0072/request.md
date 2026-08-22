---
type: Review Request
rev_id: REV-0072
title: WO-0167 M2-I3 narrow typed SQLite repository slice
status: AWAITING_REVIEW
targets: [WO-0167]
human_gated_surfaces: []
---

# REV-0072 — independent M2-I3 repository-slice review

- Branch `codex/m2-i3-sqlite-repository-hydration-r1`
- Base `0a7b5ae324c34be488da24478f95e2658a1bb894` (tree `9e76edce…`)
- Candidate binding: review the diff range `0a7b5ae324c34be488da24478f95e2658a1bb894..adc8c592dc6700d2063cd5a29e99f24fc4a44846` (implementation and tests). Any later commit touching only `work/review/REV-0072/**` is documentation-only; the authoritative tip at review time is the branch HEAD.
- Diff range: `0a7b5ae..HEAD`; changed paths exactly:
  app/execution_core/persistence/{repository.py,records.py},
  tests/execution_core/{test_persistence_repository.py,test_persistence_directness.py},
  work/active/WO-0167-*.md, work/ledger.jsonl

## Scope honesty (read first)

This candidate is an **increment**: it implements 9 of the accepted schema families
(application_generation, acquisition_scope, acquisition_generation(+current), kernel_checkpoint,
execution_fact_head, dispatch_claim, acceptance_set) plus the shared outcome/verify-guard core.
Families NOT yet implemented and explicitly OUT of this increment's coverage claims:
root_fill/execution_fact rows, venue_effect, venue_identity_owner, acquisition_root_route,
acceptance_evidence writes, closure_chain, market_stream_authority/market_cursor,
protection_authority. Reviewer should treat completeness as P1 material if increments are
unacceptable for this order; acceptance here would cover only the implemented surface.

## Public API inventory (`repository.__all__`, export-pinned by test)

Records re-exported: ApplicationGenerationRecord, ScopeRecord, AcquisitionGenerationRecord,
AcquisitionGenerationCurrentRecord, KernelCheckpointRecord, ExecutionFactHeadRecord,
DispatchClaimRecord, AcceptanceSetRecord, RepositoryOutcome, RepositoryOutcomeKind.
Operations: store_application_generation/load_application_generation, store_scope/load_scope,
store_acquisition_generation, store_acquisition_generation_current/
load_acquisition_generation_current, record_kernel_checkpoint/load_kernel_checkpoint,
record_execution_fact_head/load_execution_fact_head, record_dispatch_claim/load_dispatch_claim,
store_acceptance_set/load_acceptance_set. records.py exports the record/outcome names only.

## Evidence

- RED: commit f43b72d tests fail ModuleNotFoundError on repository module (intended).
- GREEN (CPython 3.12.13 via repo .venv): focused pair 10 passed;
  full tests/execution_core 1700 passed / 0 failed (~9:56);
  schema baseline 82-test suite green pre-work;
  ruff check/format clean; mypy app clean (93 files).
- Mutation kills: removing both verify-guard calls fails tampered-catalog test;
  removing guard only from loads leaves write-path unproven (noted weakness).
- Directness: fixed domain-query count ==1 for key load, EXPLAIN shows index seek
  (no SCAN), unrelated-history stress (200 unrelated market rows) does not change count/result.
- Caller-owned transactions: rollback discards; no COMMIT emitted (trace-checked).
- Inert import + exact-export pins included.

## Prohibited activity statement

No DDL/schema bytes changed; only fresh tmp_path file databases; no in-memory/configured DB;
no credentials/network/broker/orders/runtime/M2-I4 work; nothing merged; reviewer owns result.md.

## Self-review remediation and declared coverage gaps

Self-review found and fixed before handoff: non-SQLite exceptions were
laundered into typed outcomes (now propagated); FOREIGN-KEY refusals are now
distinguished from identity conflicts (typed INTEGRITY_FAILURE vs CONFLICT);
stale candidate hash above replaced by range binding; acquisition-generation
store/duplicate-conflict round trip added.

Declared gaps requiring reviewer judgment (not silently covered):

1. Untested exported operations pending upstream family seeds:
   record_execution_fact_head / load_execution_fact_head,
   record_dispatch_claim / load_dispatch_claim,
   store_acceptance_set / load_acceptance_set.
2. acquisition_generation_current store returns CONFLICT on first insert in
   integrated flow while an equivalent raw insert succeeds and a subsequent
   raw duplicate reports 'already retained' — an apparent trigger/state
   interaction needing design clarification before repository semantics are
   frozen. Test intentionally withdrawn rather than weakened.
3. No advance/update primitives yet for mutable-current rows
   (kernel_checkpoint, current proof rows); insert-only in this increment.

These are P1-level findings against THIS candidate; treat completeness as
described, not as full WO-0167 coverage.

## Requested lenses

Contract vs WO-0167 FRs; integrity/attribution quality; directness/boundedness; completeness
judgment on the declared increment boundary; test-critic mutation adequacy.
Findings-only verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
