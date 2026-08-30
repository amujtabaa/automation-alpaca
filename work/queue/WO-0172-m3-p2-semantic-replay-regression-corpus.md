---
type: Work Order
title: M3-P2 semantic trace comparison and permanent regression corpus
status: READY-BLOCKED
work_order_id: WO-0172
wave: M3-P2
model_tier: strong
risk: high
disposition: []
owner: unassigned M3 implementation seat; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0171 exact accepted head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: M2_TERMINAL_ACCEPTED_AT_8499845F668C0E0B71100E2420D000B0657606A6_BY_REV-0119; BLOCKED_BY_ACCEPTED_M3_P1_AND_SEPARATE_M3_P2_ACTIVATION; no M3 implementation authority.
---

# Work Order: M3-P2 semantic replay and regression corpus

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Prepared and REV-0119 accepted — blocked by accepted M3-P1 and separate M3-P2 activation

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

### Frozen inherited baseline

M3-P2 inherits, without widening, the exact M2 closeout at
`6edd8fbae0cd0eb7868826cfd0450860c63df70e`, tree
`8c918f3a1cf46333ed0eef79d3ef51d0503de88a`, and the exact accepted M3-P1 head that must be
substituted into `predecessor` during later activation. The frozen M2 public seam, DDL, flag,
manifest, and prohibition on direct repository/current-state mutation are those recorded in
WO-0171's M3 entry checkpoint. Semantic trace collection may observe typed results at that seam;
it may not become a second reducer, writer, recovery authority, or serving source.

### Required counterexample map

| Counterexample | Required semantic distinction and mutant target |
| --- | --- |
| AR-02 latent second acceptance | A terminal leg is not occurrence closure; late acceptance after `CLOSED` yields retained proof plus permanent `INVALIDATED` |
| AR-03 legacy restart/stale rollback | Application generation, account/profile, occurrence, and post-disable coverage remain exact fence coordinates |
| AR-04 correction/bust | Predecessor-linked immutable economics and ordered effective-root fold differ from naive overwrite/subtraction |
| AR-05 terminal-leg compaction | Immutable non-branching closure head prevents stale reactivation while active checkpoint size remains bounded |
| AR-06 duplicate quote | Repeated occurrence counts once; only a distinct strictly advancing observation corroborates the trigger |
| AR-07 formula displacement | Immutable formula/fill inputs remain distinguishable from a tighten-only armed trigger |
| AR-08 BUY-resolution wait | Waiting preserves `EXIT_NORMAL` versus `HARD_BAIL`; `OPEN`/`INVALIDATED` never release authority |
| AR-09 late BUY after `FLAT` | The late fill applies once and exits `FLAT` into protected `HARD_BAIL`/critical state |

Each roadmap history 1-8 and each row above requires one accepted trace and at least one
failure-capable mutant whose first semantic difference is asserted at an exact coordinate. Corpus
minimization must retain that coordinate. No row is satisfied by a fixture name, prose-only claim,
or a comparator that excludes the disputed field as transport noise.

Activation freezes exact comparator/corpus/test paths after M3-P1 acceptance and replaces the
placeholder predecessor with that exact accepted commit/tree. Existing legacy replay and simulator
artifacts are regression evidence only; no live operational truth or wholesale copy is allowed.

REV-0119 accepted the exact preparation candidate
`8499845f668c0e0b71100e2420d000b0657606a6`, tree
`79382c952ceacf5e777c13a7a44f4e3ccddb32f7`, with P0=0/P1=0/P2=0 and nothing unverified. This
lifecycle status update records that acceptance; it does not activate the order or satisfy its
future WO-0171 predecessor gate.

## Out of scope and completion

- OS-1: Alpaca adapter, credentials, broker/network calls, orders, and M4 — later human-gated work.
- OS-2: Operational replay/current truth — M2 committed current state remains authoritative.
- OS-3: Promotion and `master` merge — separate future authority.

Completion requires the full permanent corpus, failure-capable mutants, independent P0=0/P1=0
acceptance, and a separately authorized M3 closeout/next-milestone decision.
