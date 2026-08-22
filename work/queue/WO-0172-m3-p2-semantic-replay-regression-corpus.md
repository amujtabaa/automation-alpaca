---
type: Work Order
title: M3-P2 semantic trace comparison and permanent regression corpus
status: READY
work_order_id: WO-0172
wave: M3-P2
model_tier: strong
risk: high
disposition: []
owner: unassigned local coding LLM; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0171 exact accepted head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: BLOCKED_BY_M2_AND_M3_P1; preparation only, no M3 implementation authority.
---

# Work Order: M3-P2 semantic replay and regression corpus

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Prepared — blocked by M2 and accepted M3-P1

`[FABLE • FULL • conditional M3 preparation • semantic comparison, not live truth]`

## Context and goal

Build a semantic trace comparator and permanent minimized corpus over accepted M2 persisted
interfaces and M3-P1 deterministic scenarios. Replay is test/forensic evidence; it never replaces
committed current state or becomes a second operational engine.

## Functional Requirements

- FR-1: The comparator MUST define a versioned semantic trace vocabulary for admitted input, reducer disposition,
  canonical fact/head, position/protection/currentness, effect/claim/owner/acceptance/closure,
  checkpoint, receipt, startup phase, and refusal reason.
- FR-2: The comparator MUST compare semantic values and exact authority coordinates while excluding explicitly
  nonsemantic transport noise; every exclusion is enumerated and mutation-pinned.
- FR-3: The same tape/configuration/build MUST produce the same state/effect trace, including after crash
  and restore.
- FR-4: Every roadmap history and AR-02 through AR-09 counterexample MUST fail under its stated
  mutant and passes under the accepted disposition while asserting capital invariants at every step.
- FR-5: The shrinker MUST minimize failing traces without deleting the decisive event/coordinate; persist the
  original seedless trace, minimized trace, expected verdict, and authority version.
- FR-6: A vocabulary ratchet MUST fail when a new semantic event/state appears without explicit
  classification.
- FR-7: Comparator/replay MUST read evidence only and MUST NOT write current M2 state or emit an
  external effect.

## Non-Functional Requirements

- NFR-1: Comparison and shrinking MUST be deterministic, seedless, typed, and reproducible.
- NFR-2: Corpus loading and comparison MUST be bounded by the selected trace, not repository history.
- NFR-3: Static/runtime boundaries MUST prevent writes, dispatch, broker/network, configured DB, and
  operational serving authority.

## API Contracts

N/A — no HTTP or external provider API exists. The pure Python comparator accepts two versioned
semantic traces and returns equivalent, different-at-coordinate, or incompatible-vocabulary.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Semantic trace item | One classified input/state/effect/authority coordinate | Versioned, ordered, explicit semantic/nonsemantic fields |
| Comparison result | Equivalent, first semantic difference, or incompatible | Deterministic and exact-coordinate reporting |
| Regression specimen | Original and minimized trace plus expected verdict | Decisive event retained; authority/build versions bound |
| Vocabulary registry | Complete semantic event/state classifications | Unknown member fails ratchet; no silent exclusion |

## Acceptance Criteria

### AC-1: Required histories compare deterministically (FR-1, FR-3, FR-4, NFR-1)

Given every roadmap and AR-02 through AR-09 history with crash/reopen variants
When accepted and mutant traces are compared repeatedly
Then accepted traces match and each stated mutant differs at the decisive semantic coordinate

### AC-2: Comparator cannot hide authority changes (FR-2, FR-6)

Given mutants that ignore economics, profile/source, claim/acceptance/closure, phase, refusal, ordering, or new vocabulary
When the real comparator and vocabulary ratchet execute
Then every mutant fails and no unknown semantic member is silently excluded

### AC-3: Minimized corpus remains decisive and non-operational (FR-5, FR-7, NFR-2, NFR-3)

Given a failing trace and attempts to delete its decisive event or write current state
When shrinking, corpus loading, and structural guards run
Then the minimized trace keeps the decisive coordinate and no write/dispatch path exists

## Edge Cases

- EC-1: Unknown/incompatible vocabulary or missing authority coordinates returns incompatible, not
  equivalent or best-effort comparison.
- EC-2: Multiple possible shrink results use one deterministic ordering and retain the original.
- EC-3: Non-deterministic input order, duplicate coordinate, or corpus hash mismatch is refused.

## Activation path boundary

Activation freezes exact comparator/corpus/test paths after M3-P1 acceptance. Existing legacy
replay and simulator artifacts are regression evidence only; no live operational truth or wholesale
copy is allowed.

## Out of scope and completion

- OS-1: Alpaca adapter, credentials, broker/network calls, orders, and M4 — later human-gated work.
- OS-2: Operational replay/current truth — M2 committed current state remains authoritative.
- OS-3: Promotion and `master` merge — separate future authority.

Completion requires the full permanent corpus, failure-capable mutants, independent P0=0/P1=0
acceptance, and a separately authorized M3 closeout/next-milestone decision.
