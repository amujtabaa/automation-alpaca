# Proposed ADR-021 R2 — position protection, serial acquisition generations, and liquidity execution

Status: **PROPOSED COMPLETE REPLACEMENT — DRAFT ONLY — NOT RATIFIED**

Body predecessor: ADR-021 R1, SHA-256
ca822fe682bc2ccca32b5a7915ea4f07bd4ad2319e62d48312edd12c3f8f44f0.

Controlling overlay preserved: accepted ADR-023 R1, SHA-256
9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf.

If ratified, this document replaces ADR-021 R1 in full while preserving ADR-023 as the later,
controlling decision for market occurrence authority, stream generation, evidence policy, cursor,
and recovery semantics. It adds only the generation-aware distinction needed to preserve both a
successor's first-fill FLOOR_ONLY behavior and a retired root's late-fact HARD_BAIL behavior.

## Context

The reset beta has one canonical aggregate position and one symbol-wide execution authority.
A protection mandate must be complete, operator-approved, immutable, and bound to acquisition
authority. Its first owned acquisition fill arms a protective floor. A late owned BUY fact after a
flat lifecycle must apply economics and return the symbol to conservative protection rather than
leave exposure unprotected.

The previous text did not distinguish two different reasons why positive exposure can appear after
a true flat state: a new approved acquisition generation's first root, and a late fact belonging to
a retired acquisition generation. Treating both as ordinary late positivity self-preempts the new
entry; treating both as new entry loses the late-fact safety proof. The distinction must be derived
from immutable ownership, never inferred from a caller or current symbol.

## Decision

### 1. Retained protection and execution baseline

Only canonical execution facts change raw position. Submitted is not filled. Acknowledgements and
order status do not change quantity. One aggregate canonical position exists per exact scope.
Human/manual controls, kill switch, trade modes, request budgets, symbol_may_execute, exact
acceptance-set closure before release, final-claim revalidation, and independent venue ownership
remain mandatory.

The protection supervisor remains deterministic and I/O-free. It emits requests only through the
one composite authority path and never directly invokes a broker. Normal protection uses the
approved market evidence policy, guards, floor/trail rules, tick rounding, deadline, and capacity
rules. HARD_BAIL remains conservative and sticky until a valid flat condition under its owning
controller; unknown, reconciliation, stale, or incompatible conditions never grant entry.

### 2. Identity and serial-controller invariant

The following identities are distinct and non-substitutable:

- ApplicationGenerationId fences deployment/cutover, runtime, persistence, client identity, and
  broker authority.
- AcquisitionGenerationId identifies exactly one approved serial acquisition lifecycle.
- MarketStreamGenerationId identifies only ADR-023 market evidence/cursor authority.

There is exactly one SymbolAcquisitionController and exactly one active normal
PositionProtectionState for each exact scope. The controller permits at most one LIVE acquisition
generation. Retired generations are RETIRED_UNSERVING: they retain only direct historical
provenance and current economics heads, never a second protection controller or broker authority.

### 3. Complete mandates and emergency recovery compatibility

Every AcquisitionMandate remains operator-approved and binds one complete ProtectionMandate.
Every ProtectionMandate additionally contains or references an immutable
EmergencyRecoveryCompatibility commitment:

- exact scope and session fence;
- compatibility identity and configuration commitment;
- emergency execution guard;
- emergency rate/budget/deadline constraints; and
- one approved aggregate emergency quantity/risk ceiling.

It contains no normal-entry algorithm, normal loss threshold, normal trail, market cursor, or
quantity/basis allocation rule. It is the minimum shared authority for a single conservative
aggregate response if an exact retired-generation fact later conflicts with a successor.

A successor acquisition may have a different complete normal ProtectionMandate only if its
EmergencyRecoveryCompatibility equals the controller's immutable scalar compatibility commitment
exactly. The controller sets that commitment at its first generation and never replaces it, so
successor equality inductively proves compatibility with every retired predecessor without a
history scan. Every successor normal mandate uses a distinct approved MarketStreamGenerationId and a
fresh PositionProtectionState only after the predecessor protection state is non-serving. This
mandate/state replacement is the separately reviewed ADR-023 cutover and begins through ADR-023's
safe baseline behavior. Acquisition generations never reset, reuse, or transfer market
cursor/evidence authority.

An incompatible commitment, absent proof, cap exceedance, mismatched scope/session, or invalid
market evidence does not erase economics. It refuses entry and makes the controller
reconciliation-only/non-serving; it never combines policies or invents a replacement guard.

### 4. Successor admission

begin_acquisition_generation is the exclusive same-symbol successor transition. It accepts only
an authentic terminal predecessor and exact controller currentness. In one atomic pure transition
it requires:

1. exact flat aggregate canonical execution;
2. clear basis, integrity, reconciliation, account, and symbol gates;
3. every predecessor-relevant parent acceptance set exactly CLOSED;
4. no OPEN, INVALIDATED, pending, unknown, unmatched, potentially executable, cancellation-
   reserved, protection-exit, flatten, or conflicting single-flight ownership;
5. a distinct complete approved DualMandateBinding, a distinct approved MarketStreamGenerationId
   for the fresh normal protection state, and a reducer-minted successor AcquisitionGenerationId;
6. exact predecessor binding, generation, closure summary, execution/venue commitments, and
   controller head; and
7. equal EmergencyRecoveryCompatibility.

It atomically retires the predecessor, makes the predecessor normal protection state non-serving,
installs the successor as the one LIVE generation with fresh normal protection authority and fresh
ADR-023 baseline state, preserves immutable old ownership/indexes, and advances controller
currentness. It never transfers A's normal protection state or cursor into B, never clears old
historical evidence, and never allows two LIVE generations.

### 5. Sealed lineage classification

The composite M1E-to-M1D reducer derives an opaque AcquisitionLineageRelation from the exact
current controller, direct root/effect/owner index, authenticated venue transition, and canonical
execution update. It is not a public or caller-buildable value. Its exhaustive kinds are:

- LIVE_FIRST_ROOT: first accepted root of the current live generation;
- LIVE_FOLLOW_ON_ROOT: later accepted root of that same live generation;
- RETIRED_ROOT: an exact valid fact whose immutable owner is a retired generation; and
- NON_ACQUISITION: a fact outside acquisition ownership.

The relation seals source root/effect/owner, AcquisitionGenerationId, prior controller head,
execution commitment, venue commitment, and applicable emergency compatibility. Any mismatch,
missing owner, stale/forked generation, copied commitment, cross-scope substitution, or raw venue
input is reconciliation-required/non-serving. No private-state shortcut may synthesize the
relation.

### 6. Generation-aware protection behavior

For LIVE_FIRST_ROOT, fresh successor normal protection starts from that root and produces
FLOOR_ONLY under B's complete normal mandate. It must not inherit A's true-FLAT marker, old trail,
old capacity, old market cursor, old ordinary policy, or old acquisition authority.

For RETIRED_ROOT, the reducer applies the exact canonical fact and retired generation current
economics first. It never credits current B capacity or treats the fact as B's normal growth. A
non-no-op retired economic change advances controller currentness, atomically stales/preempts
current BUY authority, and enters or preserves one controller-level
MIXED_GENERATION_RECOVERY/HARD_BAIL state under the equal shared EmergencyRecoveryCompatibility.
The normal B policy is no longer used to make an ordinary entry or trail decision in that state.

The controller may make no more than one protective broker effect eligible for that transition,
and only if the existing symbol gate, emergency guard, rate/budget, and final-currentness checks
all pass. If an exit, cancel, claim, or unknown ownership already exists, the controller enters
the bounded wait/reconciliation state instead of issuing another effect. Retired A never regains
BUY authority. A retired late fact that leaves quantity flat still advances its own canonical
lineage; it does not fabricate B capacity or relax a prior safety fence.

### 7. Recovery, replay, and restart

A controller-level mixed recovery is only an emergency aggregate classification; it is not
cross-generation policy arbitration. There is one aggregate quantity, one current controller
head, and one active broker authority. The controller uses direct lineage indexes and bounded
summaries only. If aggregate exposure is beyond the approved emergency ceiling, raw economics
remain exact, but new entry and protective dispatch eligibility remain unavailable pending
reconciliation/operator disposition.

M2 persistence must make fact route, retired-current-head update, aggregate economics,
controller currentness, current BUY staleness/preemption, protection classification, and any
eligible effect one atomic unit. After a crash, restart/replay observes either the old controller
state or the complete new state. It must never recreate B as live without A provenance, two normal
protection controllers, an unbound root, or a claim valid against an earlier controller head.

### 8. Explicit exclusions

This decision does not authorize concurrent acquisition generations, independent per-generation
protection controllers, generic BUY creation, policy merging, quantity/basis allocation,
protection-authority transfer while positive, market cursor reuse, caller-made authority,
history scans, persistence implementation, runtime wiring, broker activity, or changes to
ADR-023's stream/cursor rules.

## Consequences

A later entry can use a new complete acquisition and normal protection mandate without making its
first fill self-preempt. A late valid old fact remains conservatively actionable because every
serial mandate agrees on one narrowly defined emergency authority. The cost is a small explicit
compatibility commitment and direct lineage/controller state, rather than a general multi-policy
system.

M1 must prove the relation and controller semantics in pure reducers. M2 must persist them in the
existing atomic unit of work. M3 must replay them. M4 must correlate adapter facts by immutable
owner/generation, and M5–M8 must exercise repeat entry and cross-generation recovery without
inventing policy combinations.

## Rejected alternatives

- Exact same normal ProtectionMandate for every successor, because it unnecessarily prevents a
  newly approved normal mandate and still relies on old state semantics.
- Retaining A's protection state into B, because B's first positive root becomes late-positive.
- Resetting/erasing A state, because later A facts lose their required provenance.
- General multi-policy arbitration or parallel controllers, because they add unneeded broker
  authority and cannot be safely inferred from beta requirements.
- Treating any post-flat positive quantity as B first fill, because it can falsely normalize a
  late A fact.

## Migration and deferred decisions

This is a forward contract only. No existing state is migrated and no code is authorized by it.
M2 must make the exact durable representation, constraints, and crash semantics separately
reviewable. M3 must prove deterministic pure replay before M4 maps broker evidence. M5/M6 must
define attended Paper scenarios only after their applicable gates.

Deferred: successor with incompatible emergency compatibility, positive-exposure mandate handoff,
concurrent tranches/pyramiding, automatic mixed-policy allocation, cross-account recovery,
market-evidence transfer, native broker handoff, and any second protection controller.

## Required evidence before implementation reliance

- RED controls prove B first fill FLOOR_ONLY, retired A fill/correct/bust HARD_BAIL, generation-
  local capacity, direct A routing after A -> B -> C, stale created/claimed B work, and at most one
  eligible protective effect.
- Negative controls refuse OPEN/INVALIDATED/unknown/reconciliation/nonflat/duplicate/forked/
  cross-scope/stale/incompatible conditions and all caller-shaped inputs.
- Stateful/replay controls prove one aggregate economic delta per fact, no double effect, direct
  bounded lookup, crash old-or-new atomicity, and no market-stream reset/reuse.
- Exact candidate independent review has P0=0 and P1=0, then a human ratifies the frozen hashes.
