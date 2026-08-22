---
type: Work Order
title: M3-P1 deterministic broker simulator, normalized tape, and virtual clock
status: READY
work_order_id: WO-0171
wave: M3-P1
model_tier: strong
risk: high
disposition: []
owner: unassigned local coding LLM; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0170 exact accepted M2 closeout head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: BLOCKED_BY_M2; preparation only, no M3 implementation authority.
---

# Work Order: M3-P1 deterministic simulator foundation

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Prepared — blocked by accepted M2 closeout and separate M3 activation

`[FABLE • FULL • conditional M3 preparation • no real broker]`

## Context and goal

After M2 closes, build a deterministic scripted broker capability, normalized input tape, and
virtual clock that feed authenticated inputs through the accepted M2 boundary. The simulator is an
adapter/test capability and never directly mutates engine or repository state.

## Functional Requirements

- FR-1: One seed-free virtual clock MUST control all scenario time; no wall-clock reads.
- FR-2: A versioned normalized tape MUST record typed broker/market/control observations, exact
  coordinates, and expected capability outcomes without credentials or raw account material.
- FR-3: The scripted broker MUST return deterministic submit/query/cancel/stream outcomes, including
  landed/not-landed timeout ambiguity, partial/late fills, corrections/busts, pagination, disconnect,
  and unsupported capability.
- FR-4: Every simulator observation MUST enter through the same authenticated input/sequencer path
  used by the M2 kernel; no state, DB, checkpoint, claim, or effect row is edited directly.
- FR-5: The same tape/configuration/build MUST produce byte-identical normalized input and state/effect
  trace coordinates.
- FR-6: The minimum roadmap histories 1-8 MUST be representable; AR-02 through AR-09 fixtures are
  reserved for the M3-P2 comparator/corpus.

## Non-Functional Requirements

- NFR-1: The simulator MUST be deterministic, offline, seed-free, clock-injected, and fully typed.
- NFR-2: Repeated scenarios MUST produce byte-identical normalized tape and trace coordinates.
- NFR-3: Static boundaries MUST make repository/engine direct mutation and real broker/network
  imports unreachable.

## API Contracts

N/A — no HTTP or external provider API exists. The pure Python scenario API accepts a normalized
tape plus virtual clock and yields typed simulated observations through the accepted M2 input seam.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Virtual clock | Deterministic scenario time/advance | No wall clock, sleeping, timezone drift, or unseeded randomness |
| Normalized tape item | Typed broker/market/control observation | Versioned, exact coordinates, no credential/raw account material |
| Scripted broker outcome | Deterministic submit/query/cancel/stream response | Distinguishes landed/not-landed/unknown and capability refusal |
| Scenario | Ordered tape, clock actions, expected invariant checkpoints | Reproducible and M2-input-only |

## Acceptance Criteria

### AC-1: Scenario replay is deterministic (FR-1, FR-2, FR-5, NFR-1, NFR-2)

Given each minimum roadmap scenario and one exact build/configuration
When it is executed repeatedly through the virtual clock and normalized tape
Then timing, input bytes, outcomes, and trace coordinates are identical

### AC-2: Simulator cannot become an engine (FR-4, NFR-3)

Given direct-state/repository mutation and forbidden-import mutants
When static and decisive runtime boundaries execute
Then every mutant fails and all observations enter only through the accepted M2 sequencer seam

### AC-3: Required ambiguity histories remain distinct (FR-3, FR-6)

Given landed/not-landed timeout, fill-during-cancel, stale/crossed/phantom data, startup mismatch, and crash scripts
When the scripted broker emits their outcomes
Then each history remains semantically distinguishable and ready for M3-P2 comparison

## Edge Cases

- EC-1: Unknown tape version/event or non-monotonic virtual time is refused before observation.
- EC-2: Unsupported capability returns a typed refusal; it cannot silently substitute a success.
- EC-3: Any real network/SDK/credential/configured-DB reachability fails static and runtime guards.

## Activation path boundary

Activation after M2 must freeze exact new simulator/tape/clock and test paths from the accepted M2
head. Existing legacy `app/broker/sim.py` is evidence only and may not be transplanted or edited
without an explicit comparison and scope amendment.

## Out of scope and completion

- OS-1: Semantic comparator/corpus shrinker — owned by M3-P2.
- OS-2: Alpaca adapter, credentials, broker/network calls, orders, and M4 — later human-gated work.
- OS-3: Promotion and `master` merge — separate authority after independent acceptance.

Completion requires independent P0=0/P1=0 acceptance and a frozen M3-P2 handoff; it does not
activate M3-P2.
