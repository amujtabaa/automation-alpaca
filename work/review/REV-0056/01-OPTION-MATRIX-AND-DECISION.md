# Option matrix and selected architecture

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

## Decision question

The current M1E contract can safely create one acquisition lifecycle for a scope, but no legal
post-genesis successor. The project needs a choice that supports ordinary repeat entry after a
fully closed, flat lifecycle without weakening fill-only economics, single-flight ownership, or
late-fact safety.

## Option matrix

| Option | Safety and lifecycle result | M2–M8 result | Complexity / maintainability | Decision |
|---|---|---|---|---|
| 1. Permanent never-before-used target scope | Avoids rollover now, but turns a temporary M1 containment into a lifetime one-entry rule. A later removal must reinterpret persistent identity, late facts, currentness, replay, and adapter correlation together. | M6 ordinary re-entry is impossible; M2 durable "used" proof becomes dead-end state; M3–M8 must later replace it. | Looks small now but creates deferred cross-layer rework. | **Reject as permanent architecture.** Retain only as an interim refusal until an approved successor path exists. |
| 2. Serial acquisition generations with one symbol controller and bounded emergency compatibility | A new B generation gets an independent normal protection mandate and clean first-fill classification. A retired A fact routes directly to A, updates aggregate economics once, invalidates B authority, and enters one restricted mixed-recovery hard-bail route under a pre-agreed compatible emergency profile. | M2 persists one controller and indexed lineage; M3 replays races; M4 correlates immutable generation ownership; M5–M8 retain one active controller and gain realistic repeat-entry coverage. | Adds a small identity, one controller record, direct summaries, and one compatibility value. No new process, service, policy engine, or second controller. | **Choose.** |
| 3. General multi-generation protection-policy arbitration | Requires simultaneous policies, net quantity/basis allocation, rule combination, multiple market evidence states, and broad crash/replay policy. | Expands M5/M6 substantially and makes M7 handoff/M8 soak a policy-composition program. | Speculative and hard to audit; no accepted beta need. | **Reject/defer behind a new ADR and product requirement.** |

## Selected architecture — minimal serial generation model

### Identity and ownership

- **ApplicationGenerationId** remains the deployment/cutover identity that fences process,
  persistence, client identities, and broker authority. It is **not** an acquisition lifecycle.
- **AcquisitionGenerationId** is a reducer-minted, opaque, monotone identity for one approved
  acquisition lifecycle in one exact PositionScope. It is bound once to the exact
  ApplicationGenerationId, scope, complete DualMandateBinding, predecessor controller head, and
  successor ordinal. It is neither caller-minted nor a substitute for a mandate ID.
- **MarketStreamGenerationId** remains ADR-023's market-evidence/cursor identity. It is
  orthogonal to AcquisitionGenerationId. Every successor uses a fresh normal protection state and
  a distinct approved market-stream generation only after the predecessor state is non-serving;
  that mandate/state replacement is the separately reviewed ADR-023 cutover and starts through
  ADR-023's safe baseline rules. It never transfers or reuses A's cursor/evidence.
- Every acquisition root, correction/bust lineage, effect, occurrence, venue owner, and
  acquisition-local capacity is immutably associated with exactly one AcquisitionGenerationId.
  A direct root/effect/owner-to-generation index routes later facts.

### One controller, one aggregate, one active authority

For each exact application-generation/broker/environment/account/symbol scope, a
SymbolAcquisitionController owns:

1. one aggregate canonical execution projection;
2. at most one LIVE acquisition generation;
3. one controller/currentness head used by create and final-claim revalidation; and
4. exactly one active normal PositionProtectionState, one protection/broker authority, and one
   symbol-wide recovery state.

The controller is a pure reducer value. It grants no actor, broker, credential, persistence, or
runtime authority. Retired generations never regain BUY authority and never create their own
protection controller. It contains no retired-generation collection. A separate direct
GenerationRegistry maps an exact generation/root/effect/owner key to immutable provenance, one
replaceable current economics head, and one bounded closure summary; live routes use a single
direct lookup, never controller traversal or history materialization.

### Narrow emergency compatibility, not policy arbitration

Each complete ProtectionMandate gains or references one immutable
EmergencyRecoveryCompatibility commitment. It contains only the values needed to safely protect an
aggregate same-symbol exposure after a historical generation fact: exact scope and session fence,
emergency guard, emergency rate/deadline, aggregate emergency quantity/risk cap, and a
compatibility identity. It does **not** contain normal trail, normal loss threshold, market cursor,
or an algorithm for merging policies.

A successor may use a different complete normal protection mandate only when its immutable
EmergencyRecoveryCompatibility is exactly equal to every serial predecessor retained by the
controller. The controller sets that scalar compatibility commitment at its first generation and
never changes it; equality at every successor is therefore inductive, not a history scan. If a
late retired fact restores exposure, the controller changes the
one active normal protection state into restricted MIXED_GENERATION_RECOVERY / HARD_BAIL using that
shared emergency commitment. No ordinary B trail/entry policy is combined with A's. If aggregate
exposure exceeds the approved emergency cap or any compatibility/provenance proof is missing,
economics still commit but broker authority is non-serving/reconciliation-only.

This is the least permissive way to honor both accepted requirements: B's first owned fill is
FLOOR_ONLY; a late A fact after a flat A lifecycle is never treated as ordinary B growth and
forces conservative emergency handling under authority compatible with A's original mandate.

### Successor admission and late-fact route

begin_acquisition_generation is the sole successor route. It atomically verifies an authentic
controller, exact predecessor head, terminal predecessor, exact flat aggregate execution, clear
reconciliation/basis/integrity state, no live/pending/unknown/unclosed old BUY or SELL ownership,
all relevant acceptance sets exactly CLOSED, no protection exit/flatten/cancel reservation, no
potentially executable old BUY, a distinct approved dual-mandate binding, and exact emergency
compatibility. It retires A, makes A's normal protection state non-serving, installs B with a
fresh normal protection state and distinct market-stream generation, and advances the controller
once; there are never two LIVE generations.

The composite reducer derives—not accepts from a caller—one sealed lineage relation:
LIVE_FIRST_ROOT, LIVE_FOLLOW_ON_ROOT, RETIRED_ROOT, or NON_ACQUISITION. It includes the
authenticated generation identity, root/effect ownership, prior controller head, canonical
execution commitment, and venue commitment.

- LIVE_FIRST_ROOT for B creates fresh B normal protection behavior and yields FLOOR_ONLY.
- RETIRED_ROOT for A applies the canonical fact and A's exact current economics first, never
  credits B capacity, advances the controller head, stales/preempts B authority, and enters or
  preserves one mixed-recovery hard-bail state.
- A missing mapping, fork, cross-scope identity, stale head, copied commitment, or caller-made
  relation halts in reconciliation/non-serving; it never guesses the current generation.

At most one broker-facing protective effect may become eligible in a transition, and only after
the existing symbol, budget, claim, and final-currentness gates. A prior claimed/in-flight or
unknown effect causes the existing wait/reconciliation behavior, not a duplicate action.

## Rejected shortcuts

- Clearing a scope slot or treating a retired scope as never used.
- Retaining the old FLAT protection state into B or resetting it without lineage proof.
- A per-generation protection controller, concurrent acquisition generations, or a generic
  policy-combination engine.
- Raw requested effects, caller-supplied generation/currentness/provenance, private venue access,
  or generic BUY admission.
- Audit/history scans, tombstone-chain walks, event sourcing, a new service/message bus, or a
  persistence/runtime implementation in this decision.
