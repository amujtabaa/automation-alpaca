---
type: Work Order
title: M2-I4 atomic unit of work and effect claims
status: READY
work_order_id: WO-0168
wave: M2-I4
model_tier: strong
risk: critical
disposition: []
owner: unassigned local coding LLM; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0167 exact accepted head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: NOT_ACTIVE; requires accepted M2-I3 and separate activation.
---

# Work Order: M2-I4 atomic transition and effect claims

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Ready specification — not implementation authority

`[FABLE • FULL • spec-first/TDD • no external I/O]`

## Context and goal

Compose one admitted typed input, existing pure reducer, repository writes, immutable effect claim,
outbox eligibility, checkpoint/outcome, and mandatory decision receipt in one old-or-new SQLite
transaction. External broker publication remains absent.

## Functional requirements

- FR-1: The unit of work MUST authenticate exact application/profile/source/scope/session and direct current proof
  inside the transaction before invoking the owning pure reducer.
- FR-2: The unit of work MUST persist every changed fact/head, aggregate, route, controller/currentness, protection/
  market edge, effect/claim/owner/closure, checkpoint/outcome, and receipt atomically.
- FR-3: `REFUSED`, replay, conflict, and no-op MUST preserve the owning reducer's exact semantics and
  cannot become partial authority writes.
- FR-4: The transaction MUST commit an immutable concrete claim before an effect can become post-commit eligible.
  No pre-commit dispatcher visibility and no claim erasure.
- FR-5: A mandatory decision receipt MUST be transactionally correlated but never economic,
  currentness, claim, closure, or recovery authority. Receipt failure rolls back everything.
- FR-6: Commit/publication ambiguity MUST fail closed and record reconciliation need; it MUST NOT
  blind-resubmits or reports a hybrid success.
- FR-7: Only the sequenced unit of work MAY mutate capital-relevant persistence. Direct
  repository writes outside it remain test/setup-only and structurally unavailable to runtime.

## Non-functional requirements

- Deterministic injected clock/sequence; no broker/network/configured DB.
- Crash injection at every composite write, before/after commit, and publication handoff edge.
- Every crash yields old-complete or new-complete durable state.
- No second in-memory engine, hidden transaction, auto-commit, or retry loop.

## API Contracts

One typed `UnitOfWork.execute(input, authenticated_context)`-style boundary returns an explicit
committed/refused/replayed/conflict/reconciliation-only outcome and post-commit effect eligibility.
Naming is frozen on activation; semantics may not be split across public mutators.

N/A — no HTTP or external API exists. The single Python boundary accepts one typed input plus an
authenticated context and returns one typed transaction outcome with post-commit eligibility.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Authenticated input/context | Exact typed input and current proof coordinates | Must match current application/profile/source/scope/session |
| Transaction outcome | Committed, refused, replayed, conflict, or reconciliation-only | One explicit terminal result; no hybrid success |
| Effect eligibility | Post-commit pointer to immutable claim/effect | Invisible before commit; never external I/O |
| Decision receipt | Correlated explanation | Mandatory but never current/economic/claim/closure authority |

## Acceptance Criteria

### AC-1: Composite state changes atomically (FR-1, FR-2, FR-3)

Given each admitted/refused/replay/conflict input and every named write/commit fault edge
When the unit of work executes and the database is independently reopened
Then durable state is old-complete or new-complete with the owning reducer's exact disposition

### AC-2: Claim precedes eligibility without blind retry (FR-4, FR-6)

Given a new effect, timeout ambiguity, or corrupted local effect state/timestamp
When claim and post-commit eligibility are evaluated
Then the immutable claim survives, pre-commit eligibility is absent, and blind resend is impossible

### AC-3: Receipt and write ownership cannot become authority (FR-5, FR-7)

Given receipt failure, direct repository-write pressure, and a receipt-as-truth mutant
When the decisive transaction and static boundaries run
Then receipt failure rolls back, runtime mutation remains unit-of-work-only, and every authority mutant fails

## Edge Cases

- EC-1: Duplicate/reordered fact, stale head, profile mismatch, or claim conflict produces the exact
  owner-defined outcome without partial writes.
- EC-2: Successful commit followed by publication/wakeup loss remains committed but
  reconciliation-only; it is never replayed as a fresh dispatch.
- EC-3: Mandatory receipt serialization/write failure rolls back facts, checkpoint, claim, effect,
  and eligibility together.

## Proposed allowed paths on activation

```yaml
allowed_paths:
  - app/execution_core/persistence/unit_of_work.py
  - app/execution_core/persistence/outbox.py
  - tests/execution_core/test_persistence_unit_of_work.py
  - tests/execution_core/test_persistence_crash_atomicity.py
  - work/active/WO-0168-m2-i4-atomic-unit-of-work-effects.md
  - work/completed/keep/WO-0168-m2-i4-atomic-unit-of-work-effects.md
  - work/ledger.jsonl
```

Activation appends one exact review path and reconciles paths against the accepted I3 head.

## Out of scope and completion

- OS-1: Dispatcher/broker call and market subscription — external I/O remains absent.
- OS-2: Startup serving, owner lock, configured DB, and migration — deferred or forbidden.
- OS-3: M2-I5+, M3, promotion, and `master` merge — later separately activated work.

Completion requires RED, complete fault matrix/mutations, focused/static/full-governance evidence,
independent P0=0/P1=0 acceptance, exact publication, and an M2-I5 handoff.
