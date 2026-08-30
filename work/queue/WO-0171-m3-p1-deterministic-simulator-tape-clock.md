---
type: Work Order
title: M3-P1 deterministic broker simulator, normalized tape, and virtual clock
status: PREPARED-CANDIDATE
work_order_id: WO-0171
wave: M3-P1
model_tier: strong
risk: high
disposition: []
owner: unassigned M3 implementation seat; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0170 closeout 6edd8fbae0cd0eb7868826cfd0450860c63df70e / tree 8c918f3a1cf46333ed0eef79d3ef51d0503de88a
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: M2_WO_CHAIN_CLOSED; PREPARATION_CANDIDATE_PENDING_REV-0119; separate human M3 activation required; no M3 implementation authority.
---

# Work Order: M3-P1 deterministic simulator foundation

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Prepared candidate — blocked by terminal REV-0119 acceptance and separate M3 activation

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

### Frozen M3 entry checkpoint

Activation MUST start from the exact accepted M2 closeout above and reverify all of these identities:

- final M2 implementation/test source `c7e394f52782a9b398ed89bfdc55b45bc09499b4`, tree
  `2d5c662f569ec3ee792216863fe46213551773a8`;
- REV-0118 accepted candidate `2051afe2bbc21918fac6b69875e0a536fe722e49`, tree
  `2d3fef0011412ec432fd26f43f526be6946ad00c`;
- canonical DDL SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, 190,705
  UTF-8 bytes, schema blob `164de10ad9fef6ce37324840aff59b5b68c07d2a`, and exact authorization
  flag `False`; and
- closeout manifest SHA-256
  `a72f5e92820415c48bf404063fe6a4d1dbe6397c02f5439424a43b7cc823eb66`, blob
  `e708e782f980d4eecd79ba148a11e5a3a884e304`.

The accepted M2 application boundary is the frozen public surface at that checkpoint:

- `persistence.operations`: the eight-member `M2Operation` union, its typed coordinates and
  semantic keys, and the public operation/key encoders and decoders;
- `persistence.unit_of_work`: `PostCommitEffectEligibility`, `UnitOfWorkContext`,
  `UnitOfWorkDisposition`, `UnitOfWorkResult`, and `execute_unit_of_work`;
- `persistence.startup`: `StartupDisposition`, `StartupPhase`, `StartupRefusalCode`,
  `StartupRequest`, `StartupResult`, and `start_startup`; and
- `persistence.checkpoint_codec`: `InertRuntimeCheckpointComponent`,
  `RuntimeCheckpointEnvelope`, `RuntimeCheckpointScopeCandidate`, and
  `encode_runtime_checkpoint`.

Their exact source blobs are respectively `21845a500363edf96f2c9fc06939830067469659`,
`1d0879ba4dfddefa59e3c815abbaf62e685131a6`,
`ee168dee89f51253af1930544b3c96b78b8f93ff`, and
`3ed34cddfd3d56f3835628072661b527df2367c9`. M3 may feed typed observations through those
accepted seams; simulator/comparator code may not call repository, records, schema, checkpoint
storage, or current-state mutators directly. A needed seam change is a separately reviewed
contract amendment, not an implementation convenience.

### Required scenario representation

| Roadmap history | M3-P1 representation obligation |
| --- | --- |
| 1. Partial fill, cancel request, late fill, terminal cancel | Ordered submit/fill/cancel/fill/terminal observations with exact occurrence identity |
| 2. Submit timeout where the order landed | Timeout outcome followed by deterministic query/stream discovery of the same occurrence |
| 3. Submit timeout where the order never landed | Timeout outcome followed by exhaustive deterministic absence evidence |
| 4. Cancel timeout with fill during ambiguity | Cancel ambiguity and an independently ordered broker-authoritative fill |
| 5. Trail trigger, normal exit, hard-bail escalation | Virtual-clock market observations and broker outcomes sufficient to distinguish each policy step |
| 6. Crash at every durable/network boundary and recover | Deterministic crash/restart markers and replayable observations; M2 remains owner of persistence fault injection |
| 7. Stale/crossed/phantom data near each trigger | Explicit source, sequence, event/receipt time, bid/ask, and validity metadata |
| 8. Position mismatch and external order on startup | Deterministic startup query/stream evidence for mismatch and unowned-order discovery |

P1 must also be able to express the inputs for AR-02 through AR-09: multiple and late
acceptances; generation-fence delay; fill/correct/bust reorder and duplicate; terminal-leg replay;
duplicate quote occurrence; formula-changing fills and trigger observations; BUY-resolution wait;
and a late BUY fill after `FLAT`. M3-P2—not P1—owns their semantic verdicts, mutants, minimization,
and permanent corpus.

Activation must freeze exact new simulator/tape/clock and test paths from this accepted checkpoint.
Existing legacy `app/broker/sim.py` is evidence only and may not be transplanted or edited without
an explicit comparison and scope amendment. A fresh branch and review identity are assigned only
after separate M3-P1 activation.

## Out of scope and completion

- OS-1: Semantic comparator/corpus shrinker — owned by M3-P2.
- OS-2: Alpaca adapter, credentials, broker/network calls, orders, and M4 — later human-gated work.
- OS-3: Promotion and `master` merge — separate authority after independent acceptance.

Completion requires independent P0=0/P1=0 acceptance and a frozen M3-P2 handoff; it does not
activate M3-P2.
