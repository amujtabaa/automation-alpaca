---
type: Work Order
title: M2-I6 crash, restore, fault, and boundedness closeout
status: READY
work_order_id: WO-0170
wave: M2-I6
model_tier: strong
risk: critical
disposition: []
owner: unassigned local coding LLM; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0169 exact accepted head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: NOT_ACTIVE; requires accepted M2-I5 and separate activation.
---

# Work Order: M2-I6 fault and restore closeout

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Ready specification — not implementation authority

`[FABLE • FULL • verification-heavy closeout • no promotion gain]`

## Context and goal

Prove the complete M2 build under crash, restore, corruption, scale, and operator reconstruction.
This order may make only directly necessary M2 corrections found by its tests. It does not wire a
broker, promote the system, or claim M3 readiness without exact evidence.

## Functional requirements

- FR-1: The closeout harness MUST inject failure at every M2 write/commit/publication/claim/lock/cursor edge and verify
  old-complete or new-complete state after independent reopen.
- FR-2: The closeout harness MUST restore copied database/WAL evidence into an independent destination and reproduce exact
  integrity, current-proof, reconciliation, and non-serving classifications.
- FR-3: The closeout harness MUST kill mutants for duplicate/forked lineage, stale/missing routes, two-LIVE controllers,
  profile substitution, claim erasure, acceptance/closure gaps, cursor ordering, and history-fold
  startup.
- FR-4: The closeout harness MUST measure bounded direct hydration/startup and target/stress query plans using the frozen
  testing-model budgets; unexplained regression fails.
- FR-5: The closeout MUST run the required faulted soak for at least 24 hours on one exact build/profile and retain
  incident/operator reconstruction evidence. Interrupted or shortened soak remains `NOT_RUN`.
- FR-6: The closeout MAY evaluate the frozen R16 G0-G7 conjunction only if every named input is current and exact;
  otherwise retain `NOT_EVALUATED` with the missing coordinates.
- FR-7: The closeout MUST produce a self-contained M2 closeout/handoff manifest binding source, tests, schema,
  environment, evidence, limitations, and every `NOT_RUN` item.

## Non-functional requirements

- Fresh temporary or explicitly isolated restore destinations only; never the configured DB.
- No credentials, broker/network calls, orders, production runtime, or live/shadow mode.
- Failure seeds/traces and environment versions are retained and reproducible.
- No waiver converts environmental inability, Paper observation, or documentation into PASS.

## API Contracts

N/A — no HTTP or production runtime API is added. The harness accepts an exact M2 build/profile,
fresh temporary/restore destinations, a named fault schedule, and deterministic evidence sinks.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Fault case/result | Named edge, exact precondition, injected fault, reopened outcome | Reproducible; old/new complete classification only |
| Restore evidence | Source DB/WAL hashes, independent destination, integrity result | Source untouched; destination isolated; exact environment |
| Soak record | Build/profile, start/end, fault schedule, incidents, reconstruction | At least 24 uninterrupted hours or `NOT_RUN` |
| M2 closeout manifest | Source/test/schema/environment/evidence hashes and limitations | Self-contained, exact, no PASS laundering |

## Acceptance Criteria

### AC-1: Complete fault and restore proof (FR-1, FR-2)

Given every named fault edge plus independent restore/corruption variants
When the harness crashes, reopens, and verifies each destination
Then every result is old-complete, new-complete, or exact fail-closed refusal with no blind resend

### AC-2: Mutants and scale cannot bypass M2 authority (FR-3, FR-4)

Given directness, uniqueness, lineage, profile, claim, closure, cursor, and history-fold mutants at target/stress scale
When the decisive mutation and boundedness gates execute
Then every mutant fails and accepted query/work budgets remain within the frozen limits

### AC-3: Soak and R16 state remain evidence-faithful (FR-5, FR-6)

Given one exact build/profile and the current R16 inputs
When the soak and conjunction evaluation are attempted
Then a full 24-hour exact record passes or remains `NOT_RUN`, and R16 passes only with every exact current input

### AC-4: Closeout is independently reproducible (FR-7)

Given the final candidate and closeout manifest
When an independent reviewer rehashes and reruns its named gates
Then the evidence reproduces with P0=0/P1=0 or M2 remains unclosed

## Edge Cases

- EC-1: Interrupted/shortened soak, destination collision, source-file mutation, or missing WAL
  remains failed/`NOT_RUN`; no partial credit.
- EC-2: Environmental inability or unavailable target hardware is recorded exactly and never
  converted to a passing proxy result.
- EC-3: A production correction discovered by closeout stops at an exact scope amendment; the
  harness cannot silently edit an unlisted production path.

## Proposed allowed paths on activation

```yaml
allowed_paths:
  - tests/execution_core/test_persistence_fault_matrix.py
  - tests/execution_core/test_persistence_restore.py
  - tests/execution_core/test_persistence_boundedness.py
  - tests/performance/m2_persistence_budget.py
  - harness/m2/**
  - work/active/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/completed/keep/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/ledger.jsonl
```

Any production correction needs an exact scope amendment naming the M2 file and defect before edit.
Activation also appends one exact review path and reconciles all paths against the accepted I5 head.

## Out of scope and completion

- OS-1: Adapter/runtime composition and broker/network/credentials/orders — no operational activity.
- OS-2: Configured DB and promotion — only fresh isolated evidence destinations; no readiness gain
  beyond proven M2 closeout.
- OS-3: M3 implementation and `master` merge — separate future authority.

Completion requires exact independent acceptance, full lifecycle closeout, M2 manifest, honest
soak/R16 state, and a separately reviewed M3 entry handoff. It activates neither M3 order.
