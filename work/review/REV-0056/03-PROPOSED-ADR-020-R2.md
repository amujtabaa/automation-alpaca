# Proposed ADR-020 R2 — current-state execution kernel with acquisition-generation lineage

Status: **PROPOSED COMPLETE REPLACEMENT — DRAFT ONLY — NOT RATIFIED**

Predecessor body: ADR-020 R1, SHA-256
35c6782ff7c09ec125b2acad859b4080302660531004db47b8c544b4cf2a5838.

If ratified, this document replaces ADR-020 R1 as the complete current-state execution-kernel
decision. It preserves every retained R1 safety boundary stated below and narrows only the
previously unspecified ownership/currentness route for serial acquisition generations. It does not
implement persistence or authorize a schema change.

## Context

The reset beta has one account, a small symbol set, a single writer, and a pure reference kernel.
Raw position changes only through first-occurrence canonical execution facts: FILL and valid,
broker-authoritative predecessor-linked TRADE_CORRECT or TRADE_BUST revisions. Current state must
remain bounded and deterministic; audit history remains evidence, never a live transition input.

A completed acquisition does not make broker facts about its owned roots impossible. The prior
decision defines persistent fact/owner lineage but did not define a direct current authority route
when a later, distinct same-symbol acquisition begins. Clearing old state loses provenance;
retaining a completed protection state makes a later legitimate first fill indistinguishable from a
late old fill. That omission must be addressed at the kernel boundary, not by a work-order
shortcut.

## Decision

### 1. Retained kernel and fact-truth rules

There is one pure deterministic execution core and one logical writer. The core accepts an
authenticated current state and one bounded command/fact, returns a replacement state and zero or
more requested effects, and performs no I/O, wall-clock lookup, database access, runtime dispatch,
or audit-history fold.

Only a first-occurrence canonical FILL and a valid, broker-authoritative, exact-root,
immediate-predecessor TRADE_CORRECT or TRADE_BUST may change raw quantity or economics. A
correction/bust never overwrites an older fact, never guesses a missing/branched/out-of-order
predecessor, and never becomes free-standing position authority. Invalid, ambiguous, or
cross-environment/account/order/symbol/side input is reconciliation-required and non-serving.

The execution checkpoint remains bound to its execution sequence and chain commitment. A
non-tail correction/bust commits its exact signed root delta and reconciliation consequence without
a live full-history fold. Reconciliation, integrity, overfill, and unknown-outcome fences remain
fail closed. No live transition performs work proportional to audit-history length.

### 2. Three distinct generations

ApplicationGenerationId is the deployment/cutover and broker-authority fence. It is not an
acquisition campaign. MarketStreamGenerationId remains the independent market-evidence and cursor
identity governed by ADR-023. AcquisitionGenerationId is a third, opaque reducer-minted identity
for one operator-approved acquisition lifecycle in one exact PositionScope.

A serial successor's normal protection state is a new ADR-023 state with a distinct approved
MarketStreamGenerationId after its predecessor state is non-serving. Acquisition generation never
resets, reuses, or stands in for market-stream identity.

An AcquisitionGenerationId is immutable and binds exactly one application generation, scope,
successor ordinal, complete DualMandateBinding, predecessor controller head, and approved
EmergencyRecoveryCompatibility commitment. It cannot be provided by a caller, copied from another
scope, reused with another binding, inferred from the current symbol, or substituted for either
other generation identity.

### 3. Immutable ownership and direct lineage indexes

Every acquisition-owned request occurrence, effect, venue owner, canonical root, and revision
lineage records its exact AcquisitionGenerationId at creation/first canonical binding. An exact
root/effect/owner binding resolves to one and only one acquisition generation. Later
TRADE_CORRECT and TRADE_BUST facts follow the root's immutable generation; they never attach to a
currently live successor merely because it has the same symbol.

For every acquisition generation, the kernel retains immutable provenance and a directly indexed
replaceable current economics head. A retired generation has status RETIRED_UNSERVING: it may
receive an exact valid fact update, but it can never create, reprice, claim, or regain BUY
authority. A terminal fact does not erase its direct index. There is no mutable tombstone as the
sole authority, predecessor-chain walk, or scan of effects, owners, closures, or audit history.

The direct index is total for every accepted acquisition root and is unique across application
generation, broker, environment, account, scope, effect/owner, and root identity. A missing,
ambiguous, mismatched, or forked lookup is non-serving/reconciliation-only. It is never repaired
by current-symbol inference.

### 4. One controller and sequenced currentness

Each exact application-generation/broker/environment/account/symbol scope has one bounded
SymbolAcquisitionController record. It holds one aggregate canonical execution projection, one
controller currentness head, at most one LIVE acquisition generation, one scalar immutable
emergency-compatibility commitment established at controller genesis, and the one active
protection/broker authority defined by ADR-021 R2.
It contains no retired-generation collection. A separate direct GenerationRegistry holds one
record per generation with immutable provenance, one current economics head, and one bounded
closure summary; an exact root/effect/owner lookup reaches that record without controller
traversal or history materialization.

Every generation transition, canonical fact route, protection classification, acquisition
preemption, and final claim revalidates the exact controller currentness head. The writer advances
that head atomically whenever it commits a non-no-op generation-relevant fact or successor
admission. A create or final claim carrying an older head fails closed; no stale successor BUY may
be dispatched after a retired-lineage change.

The controller does not create a second writer, service, process, event stream, or aggregate. Its
aggregate is the one canonical position for the scope; it does not allocate quantity or basis
between generations.

### 5. Atomic transaction, restart, and replay requirements

In M2, one SQLite unit of work must atomically write the accepted execution fact or revision,
execution-chain head, aggregate checkpoint, exact acquisition-generation current head,
root/effect/owner-to-generation binding, bounded controller record, relevant venue/closure state,
effects, claims, and decision receipt. The old complete state or new complete state is durable;
there is never a durable state with two LIVE generations, an accepted root without a generation
binding, or a successor admission without its predecessor/compatibility proof.

The serving checkpoint keeps only the controller's direct keys/current heads, bounded summaries,
and active or unresolved venue work. Retired GenerationRegistry rows remain direct indexed
authority outside the checkpoint; the checkpoint never materializes their collection.
Startup/replay verifies controller uniqueness, index totality, live/retired status, exact
currentness, and root-head linkage through direct indexed lookups. A missing or inconsistent
mapping prevents serving. A separately measured non-serving audit may inspect full immutable
history but may not authorize a live effect.

### 6. Retained venue, closure, and claim boundaries

Occurrence acceptance-set state remains OPEN, CLOSED, or INVALIDATED as the sole canonical
persisted authority. OPEN and INVALIDATED remain potentially unsafe for successor admission;
terminality of a single leg, local cancellation, position flatness, or an in-memory projection does
not establish release. Every concrete acceptance retains its own immutable ownership. Terminal
owner closure remains an indexed, non-branching ordinal chain, and later valid facts advance that
owner's direct current head.

The immutable claim-before-I/O rule, one outbound arbiter, budget consumption, final-currentness
revalidation, broker coverage, cutover, one-process ownership, and live-endpoint refusal remain
unchanged. This ADR creates no broker permission and no runtime behavior.

### 7. Explicit refusals

This decision refuses generic exposure-increasing BUY creation, caller-made currentness or lineage
relations, raw requested effects, private venue access, history-derived authority, transfer or
rewriting of old ownership, resetting a scope to unused, two concurrent acquisition generations,
per-generation broker controllers, broad policy arbitration, and a non-SQLite second writer or
store.

## Consequences

The beta gains a durable, replayable way to distinguish an ordinary current-generation first fill
from a valid late retired-generation fact. Durable provenance grows with retained canonical facts
and generations, which is unavoidable while corrections remain valid; live transition work stays
bounded. M2 must add an approved direct lineage/controller persistence design, M3 must test
reorder/crash/replay, and M4 must correlate broker facts to immutable generation ownership.

The decision does not promise concurrent tranches, quantity/basis allocation across policies,
market-stream reuse, or automatic recovery under incompatible mandates. Those are separately
deferred.

## Rejected alternatives

- A permanent never-before-used scope rule, because it blocks ordinary repeat acquisition and
  forces later M2–M8 rework.
- Clearing/reusing a slot, because it destroys old root provenance.
- A single immutable tombstone, because a valid late fact requires an indexed mutable economics
  head.
- Full event sourcing or a history scan in the live path, because it violates bounded transition
  and restart rules.
- Multiple controllers or a general policy engine, because neither is required for serial beta
  acquisition and both multiply broker authority.

## Migration and deferred decisions

This proposed replacement has no runtime or data migration. On ratification it is a forward
architecture contract only. M2 must produce a separately reviewed schema/constraint design and
M3 must prove deterministic replay before any persistent implementation. Existing historical
application artifacts remain read-only evidence; no compatibility shim or automatic conversion is
authorized.

Deferred: multiple simultaneously live acquisition generations, protection-policy composition,
different emergency recovery compatibility, cross-account aggregation, market-evidence transfer,
native broker handoff mechanics, and non-SQLite persistence.

## Required evidence before implementation reliance

- Static clause comparison confirms all retained R1 boundaries and the ADR-023 overlay survive.
- RED controls prove direct A/B/C root routing, index totality, stale-claim rejection, no history
  materialization, and one-LIVE uniqueness.
- Generated/stateful controls cover duplicate, correction, bust, cross-scope, fork, restart, and
  atomic old-or-new transition cases.
- A fresh independent exact-candidate review finds P0=0 and P1=0.
- A human ratifies exact candidate hashes and separately authorizes any successor work order.
