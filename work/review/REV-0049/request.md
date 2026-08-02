---
type: Review Request
rev_id: REV-0049
title: "Reset M1C pure trading authority and manual controls"
status: AWAITING_REVIEW
targets: [WO-0147, RESET-M1C, ADR-020, ADR-021, ADR-022]
human_gated_surfaces: [effect admission, final dispatch claim, kill switch, manual flatten, emergency reduction, request budget, venue recovery truth]
commit_range: d0a51d96a74662592dbbbe91b7bb76eaddb7ea80..1d294e0ac29dcd169a4733df3aa9cbd337dc8787
implementation_head: 1d294e0ac29dcd169a4733df3aa9cbd337dc8787
created: 2026-08-01
---

## Your Role

You are the independent review seat. You did not author this implementation or its in-process
review prompts. Follow `AGENTS.md`, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`,
`pkl/process/review-hardening.md`, and the accepted reset authority identified below. Produce
findings only. Do not edit a reviewed file or this request; write only `result.md` in this folder.

Before reading implementation source, its tests, or the work order's implementation checkpoints,
pre-register in `result.md` the properties and counterexamples you will attack from the accepted
ADRs and the normative work-order contract. Then inspect the implementation. Use three hostile
perspectives: production saboteur, context-free maintainer, and safety/data-integrity reviewer.
Converge them into one deduplicated findings table.

All prior RED reviews, implementation reviews, mutation passes, scope reviews, and recorded green
results were in-process filters. They do not satisfy this independent gate and must not be treated
as proof.

## Frozen Object Under Review

Review exactly:

```text
base:   d0a51d96a74662592dbbbe91b7bb76eaddb7ea80
target: 1d294e0ac29dcd169a4733df3aa9cbd337dc8787
diff:   git diff d0a51d96a74662592dbbbe91b7bb76eaddb7ea80..1d294e0ac29dcd169a4733df3aa9cbd337dc8787
```

The target introduces a pure, deterministic authority reducer over the already accepted execution
and venue kernels. It classifies effect creation, final effect claims, metered query claims, kill,
manual flatten, request capacity, and one-shot emergency reduction. It is intentionally unwired:
it does not persist, dispatch, call a broker, authenticate credentials, read a clock, or expose a
runtime/API/UI control.

Review the entire claimed authority boundary, not only changed lines. A bypass in an unchanged
private venue seam or a constructible public state still counts if it defeats a claimed property.
Historical Spine v2 implementation remains read-only evidence, not target design authority.

No credential discovery/use, Alpaca or other broker activity, network access, SQL/DDL, database
engine/client/fixture, ORM/schema/migration tool, runtime wiring, PR, merge, push, deletion, or
cleanup is permitted or needed. Pure in-memory Python tests and static inspection are permitted.
Do not use any prohibited R1 DDL result as evidence.

## Spec-First Reading Order

Before implementation inspection:

1. `AGENTS.md`, especially Safety core and Architecture reset lane.
2. `docs/adr/ADR-020-current-state-execution-kernel.md`, especially the execution-state,
   reconciliation, mutation-authority, and final-claim clauses around lines 91-107, 158-210, and
   the mandatory state-machine/mutation requirements around line 262.
3. `docs/adr/ADR-021-position-protection-liquidity-execution.md`, especially the unified
   admission/create/final-claim classifier and manual-control clauses around lines 197-215 and
   266-268.
4. `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md`, only the reset-beta scope and
   authority exclusions relevant to this slice.
5. `work/queue/ARCH-RESET-2026-07/06-roadmap.md`, M1 item 3 only.
6. `work/active/WO-0147-reset-kernel-c-trading-authority-controls.md` from `Activation and
   authority` through `Stop conditions` only.

Pre-register attack properties now. Only afterward read changed source/tests and the later
RED/re-gate/evidence checkpoints in WO-0147.

## Exact Changed-Path Inventory

The frozen implementation object contains only:

```text
app/execution_core/__init__.py
app/execution_core/authority.py
app/execution_core/identity.py
app/execution_core/venue.py
tests/execution_core/test_authority.py
tests/execution_core/test_authority_stateful.py
tests/execution_core/test_import_boundary.py
tests/execution_core/test_venue_binding_recovery.py
tests/execution_core/test_venue_checkpoint_hardening.py
tests/execution_core/test_venue_ownership.py
tests/execution_core/test_venue_provenance_hardening.py
tests/execution_core/test_venue_recovery.py
tests/execution_core/test_venue_stateful.py
work/active/WO-0147-reset-kernel-c-trading-authority-controls.md
```

Any accepted ADR, reset-queue, legacy/runtime application, database/store, adapter, API/UI, or CI
workflow change in the exact range is a blocking scope defect.

## INV-* Delta Since REV-0048

- **ADDED:** none.
- **AMENDED:** none.
- **Preserved/implemented, not redefined:** `INV-1` through `INV-9`.

This slice directly exercises primarily `INV-2`, `INV-3`, `INV-4`, `INV-7`, `INV-8`, and `INV-9`.
`INV-1`, `INV-5`, and `INV-6` remain inherited boundaries rather than newly claimed folds.
Because no catalogued invariant statement changed, PROC-0001's new-ID probe set is empty. Fresh
authority counterexamples are still mandatory; rerunning a pinning test alone is not a fresh probe.

## T1 Applicability to Verify

| Gate | Applicability claim to attack |
|---|---|
| T1.1 | Applies: authority phase/mode/fence/query/manual enums and reused side/effect/acceptance/disposition enums must be explicitly total; an unclassified member must break the build. |
| T1.2 | Applies: every new safety pin needs a named live mutant, decisive failure, and exact restoration. |
| T1.3 | Applies: `_cancel_target_reservation_by_leg`, `_authority_contribution_by_effect`, `_authority_summary_by_scope`, and `_account_unclaimed_requested_effect_ids` must each have a real producer/updater, hydration rebuilder, invariant validator, and executable safety consumer. |
| T1.4 | N/A only because this slice has no clock, refill, timing, or wall-clock gate. Do not extend this N/A to any flaky claim. |
| T1.5 | Applies: require a property-by-choke-point matrix over genesis/import, create, final claim, query claim, kill, begin/advance flatten, cancel/recovery/hydration, close/readiness, and replay/conflict. |
| T1.6 | N/A only because persistence and memory/SQLite parity belong to M2; independently verify that no persistence path leaked into this slice. |
| T1.7 | Applies: budget, safety reserve, effect/query claims, cancel reservation, and emergency grant must cover success, refusal, conflict, exact replay, retention, release, debit, and one-shot consumption. Durable restart is N/A here. |
| T1.8 | N/A only because this pure slice performs no broker call or durable audit/recovery write; independently verify that claim data is not itself dispatch. |

## Negative-Space Review Questions

Enumerate every public, private-but-callable, or constructible path by which:

1. a caller could mint `ACTIVE`, `REDUCING`, `PAPER_MUTATION_ELIGIBLE`, request capacity, a grant,
   kill clearance, a manual-flatten phase, or a positive authority predecessor;
2. actor/reason/evidence metadata, a boolean, subclass, duck type, dataclass replacement, raw venue
   input, or package-root import could authenticate or bypass authority;
3. reused permanent effect, request-occurrence, client-order, claim, query, flatten, or authority
   input identity could become a transient refusal after policy drift instead of a stable conflict;
4. create and final claim could disagree after late phase/mode/fence/kill/session/binding/residual,
   account-epoch, venue-uncertainty, target, budget, reservation, or grant drift;
5. a sibling or cross-symbol effect could be hidden by a target exemption, per-symbol cache, stale
   account registry, copied history, or caller-supplied summary;
6. an acknowledgement, outcome-unknown status, terminal leg, `OPEN`/`INVALIDATED` parent, reordered
   checkpoint, semantic alias, or forged cancel owner could release ambiguity or flatten readiness;
7. kill could fail to latch, partially stand down account work, strand a cancel reservation, alter
   claimed work, or prevent the cancel/query/reconcile actions required to resolve uncertainty;
8. manual flatten could mutate partially in the presence of safely-local, known cancellable, claimed,
   or unknown BUY work; emit more than one final SELL; silently clamp/`abs` residual; or consume
   budget/grant on refusal;
9. a reserved query or emergency grant could be unmetered, double-debited, reused, cross-scoped,
   consumed on refusal, or applied to an ineligible action; or
10. a cached projection, enum addition, replay index, or hot-path audit materialization could bypass
    the intended bounded single authority classifier.

For each path, identify the choke point and either demonstrate an exploit/counterexample or provide
a specific file-and-line-keyed unreachability proof. Narrative confidence is not closure.

## Required Fresh Probes

Run at least three novel pure in-memory scenarios not merely calls to existing named tests. Record
the exact setup/outcome and property attacked in `result.md`. Include:

- one public-construction or provenance forgery;
- one effect created under valid authority followed by late mutable-state drift at final claim;
- one cross-symbol/account-epoch, multi-leg manual-flatten, or cancel-reservation/parent-closure
  counterexample.

Also perform at least one independent failure-capability probe without editing the frozen object:
use a test-local runtime monkeypatch, a one-off public-API counterexample, or independently verify a
recorded mutation-to-failing-test mapping. The probe must attack a real final-claim,
cancel-reservation, cached-projection, or kill/manual-control pin and must be able to fail.

## Mechanical and Reproduction Gates

At minimum, independently reproduce from the frozen target with `BROKER_ADAPTER=mock` and cache
writes disabled:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_authority.py tests/execution_core/test_authority_stateful.py tests/execution_core/test_venue_binding_recovery.py tests/execution_core/test_venue_checkpoint_hardening.py tests/execution_core/test_venue_ownership.py tests/execution_core/test_venue_provenance_hardening.py tests/execution_core/test_venue_recovery.py tests/execution_core/test_venue_stateful.py --maxfail=1
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core --maxfail=1
.\.venv\Scripts\python.exe -m ruff check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m ruff format --check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app/execution_core
.\.venv\Scripts\lint-imports.exe
git diff --check d0a51d96a74662592dbbbe91b7bb76eaddb7ea80..1d294e0ac29dcd169a4733df3aa9cbd337dc8787
```

Attempt to disprove, rather than accepting recorded PASS lines:

- the public package cannot import raw effect-request/claim, supervisor, grant-mint, or positive
  predecessor capabilities;
- permanent identity conflicts precede mutable gates and are bounded indexed lookups;
- all create/final-claim paths share action-aware classification and refuse without partial budget,
  grant, venue, or manual-state mutation;
- account-wide kill, cancellation, manual flatten, query, and emergency reduction retain their
  exact asymmetric permissions;
- all four cached safety projections are canonical, rebuilt, validated, and consumed rather than
  copied caller authority; and
- the exact changed path set remains within WO-0147.

The work order records R2, full repository coverage, mutation, and scope evidence. Those records are
implementation-seat claims, not independent proof. You need not run SQL/SQLite/full-repository
coverage to review this pure boundary. External exact-head Python 3.11/3.12 CI remains a separate
post-review closeout gate; do not report it as verified here.

## Evidence and Severity Contract

- Cite exact `file:line` evidence for every finding.
- Label each finding P0/P1/P2 according to `AGENTS.md`.
- P0 includes a safety-invariant violation, bypass on a human-gated surface, prohibited scope
  mutation, or completion claim you cannot reproduce.
- P1 includes an untested behavior change, bypassable/incomplete fix, false-green test, boundary
  violation, or scope creep.
- Preserve independent uncertainty: state every item you could not verify.
- End with exactly one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`.
- `ACCEPT` requires no unresolved P0/P1. P2 observations may remain only if they do not weaken a
  declared safety or completion claim.

## How to Respond

Create `work/review/REV-0049/result.md` and no other file. Preserve this request and every reviewed
file byte-for-byte. Findings only; do not implement fixes.
