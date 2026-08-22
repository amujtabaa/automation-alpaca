---
type: Work Order
title: M2-I5 startup, reconciliation, and cold market recovery
status: READY
work_order_id: WO-0169
wave: M2-I5
model_tier: strong
risk: critical
disposition: []
owner: unassigned local coding LLM; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0168 exact accepted head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: NOT_ACTIVE; requires accepted M2-I4 and separate activation.
---

# Work Order: M2-I5 startup and cold recovery

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Ready specification — not implementation authority

`[FABLE • FULL • spec-first/TDD • fake capabilities only, no broker network]`

## Context and goal

Implement fail-closed process ownership, startup integrity, unknown-effect reconciliation, and the
accepted ADR-023 cold market restart sequence. The exact build may enter `SERVING` only after every
direct proof and capability gate passes. Tests use injected/fake capabilities; no broker call or
credential is authorized.

## Functional requirements

- FR-1: Startup MUST acquire one process-lifetime owner lock before database or adapter work; a second process
  cannot write or dispatch, and uncertain takeover remains non-serving.
- FR-2: Startup MUST verify immutable datastore/application/profile identity, schema/version, checkpoint,
  direct-route totality, one-LIVE/controller uniqueness, current heads, claim/owner/closure
  consistency, and supervisor-fence coordinates.
- FR-3: Startup MUST enforce `BOOTSTRAPPING -> RECONCILING -> SERVING`; a successful open is never enough.
- FR-4: Startup MUST convert stranded/in-flight/unknown claims to deterministic reconciliation without blind
  retry; require complete targeted query/stream coverage before release.
- FR-5: Startup MAY classify ADR-023 warm-exact only with quiescence, atomic last-cursor publication, and
  proof of no later publication.
- FR-6: Otherwise startup MUST invalidate volatile market authority before adapter work, obtain a
  source-authoritative post-ack fence, require strict `F > cursor` or the exact initial no-cursor
  exception, exclude buffered `<=F`, deliver one baseline at `F`, then permit `>F` work.
- FR-7: Unsupported or incomplete source capability MUST remain reconciliation-only/non-serving.
- FR-8: Startup MUST use direct current proof; no full facts/receipts/retired-generation/owner/
  closure/tape scan may manufacture serving authority.

## Non-functional requirements

- Fake/injected adapter, query, stream, filesystem, and lock capabilities only.
- Deterministic virtual time and bounded startup/query counts.
- No configured database, credentials, outbound network, orders, or real broker/market source.
- Every refusal retains exact reason/evidence coordinates without secret or raw account material.

## API Contracts

One startup coordinator owns explicit phases and returns a typed serving or non-serving result.
Owner lock, effect reconciliation, and market recovery remain separate injected capabilities; none
may directly mutate reducer state or bypass M2-I4.

N/A — no HTTP or real external service API exists. The Python coordinator consumes injected lock,
repository, query, and stream capabilities and returns one typed phase/serving/refusal result.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Startup phase/result | Bootstrapping, reconciling, serving, or non-serving refusal | Monotonic allowed transitions; successful open is insufficient |
| Owner lease/lock evidence | Exact process-lifetime ownership coordinates | One owner; uncertainty/loss fails closed |
| Reconciliation item | Claimed/in-flight/unknown effect plus coverage state | Deterministic identity; no blind retry; complete coverage required |
| Market recovery state | Profile, stream generation/mode, cursor, fence, baseline | ADR-023 exact ordering and source-authoritative proof |

## Acceptance Criteria

### AC-1: Ownership and integrity gate all startup work (FR-1, FR-2, FR-3)

Given two-owner, stale-lock, lock-loss, identity/profile/fence, route/head, and claim/closure mutants
When startup attempts to progress phases
Then adapter work and `SERVING` remain impossible and the exact refusal is retained

### AC-2: Unknown effects reconcile without blind resend (FR-4)

Given stranded, in-flight, and outcome-unknown claims with complete or incomplete coverage
When reconciliation evaluates deterministic identity and coverage
Then only fully resolved occurrences may progress and no uncertain effect is blindly resubmitted

### AC-3: Market restart obeys exact ADR-023 order (FR-5, FR-6, FR-7)

Given warm-exact, no-cursor, equality-fence, buffered, unsupported-source, and crash variants
When the injected market recovery capability runs CR-01 through CR-19
Then only the exact accepted sequence reaches a fresh baseline and every mutant remains non-serving

### AC-4: Startup work is history-bounded (FR-8)

Given target/stress unrelated history growth
When normal startup loads direct current proof
Then query/work shape remains bounded and history-fold mutants fail

## Edge Cases

- EC-1: Owner lock loss after database open but before serving returns non-serving and disables
  mutation/dispatch eligibility.
- EC-2: Fence equal to retained cursor fails strict `F > cursor`; only the exact no-cursor initial
  exception can proceed.
- EC-3: Source cannot prove post-ack coverage or emits unsupported coordinates; baseline is not
  delivered and current market authority remains invalidated.

## Proposed allowed paths on activation

```yaml
allowed_paths:
  - app/execution_core/persistence/startup.py
  - app/execution_core/persistence/owner_lock.py
  - app/execution_core/persistence/market_recovery.py
  - tests/execution_core/test_persistence_startup.py
  - tests/execution_core/test_persistence_cold_recovery.py
  - work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/completed/keep/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/ledger.jsonl
```

Activation appends one exact review path and reconciles paths against the accepted I4 head.

## Out of scope and completion

- OS-1: Production adapter/runtime composition and broker/network/credentials/orders — fake injected
  capabilities only.
- OS-2: Configured DB and live/shadow — forbidden; temporary accepted M2 persistence only.
- OS-3: M2-I6 execution, M3, promotion, and `master` merge — later separately authorized work.

Completion requires RED, CR-01..19 and failure-capable mutants, focused/static/full-governance
evidence, independent P0=0/P1=0 acceptance, exact publication, and an M2-I6 handoff.
