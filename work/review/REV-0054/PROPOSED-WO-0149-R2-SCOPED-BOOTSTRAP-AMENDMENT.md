# Proposed WO-0149 R2 — bounded scoped bootstrap and same-protection successor

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

## Decision to ratify

Extend the pure-M1E contract only enough to permit a sealed acquisition lifecycle after canonical
account history exists. The amendment preserves generic exposure-increasing BUY refusal and adds
no history-derived or caller-shaped authority.

It distinguishes two bounded cases:

1. A first M1E lifecycle for a target symbol that is exactly flat, even when other symbols have
   account venue history.
2. A later lifecycle for the same target symbol only after the old lifecycle has terminally
   resolved, the symbol is exactly flat, and the successor retains the exact same complete
   `ProtectionMandate` identity and commitment.

The successor's `AcquisitionMandate` identity must be distinct. A same-symbol successor with a
different protection mandate, protection formula, guard, evidence policy, session, configuration,
or protection identity is refused. Deciding how distinct protection authorities share one symbol
position is outside this amendment and requires a new ADR.

This is consistent with the domain requirement that a later unrelated acquisition use a new
mandate: the acquisition mandate is new, while one retained protection authority continues to
govern the exact position scope. It does not transfer, merge, or duplicate protection authority.

## Contract amendment

### 1. Sealed scoped bootstrap projection

`project_acquisition_venue(book, binding, *, execution=...)` gains one additional sealed bounded
source kind, `SCOPED_BOOTSTRAP`. It may be minted only from the exact current
`VenueRecoveryBook` and exact current `ExecutionSnapshot` for the requested account/symbol when:

- the requested canonical position is exactly flat;
- account reconciliation is clear;
- the target symbol has no active, pending, unknown, unresolved, or unmatched-close BUY/SELL
  ownership;
- every target parent acceptance set is exactly `CLOSED`, never `OPEN` or `INVALIDATED`; and
- each predicate comes from existing bounded current indexes or direct per-effect lookups, never
  `effects`, owners, attempts, closure history, or another lifetime materialization.

The opaque projection seals the exact book, execution, target scope, binding, source kind, and
the bounded target-symbol proof. Existing exact-empty `GENESIS` behavior remains unchanged.

### 2. Directly indexed lifecycle slot and tombstone

M1E retains one direct per-scope lifecycle slot with explicit `LIVE` or `RETIRED` status; a prior
M1E scope is never treated as if it had no history. On eligible same-symbol succession, authority
atomically installs the successor live record and retains an immutable predecessor tombstone.
The tombstone is directly indexed by its exact old binding, owned effect/root identities, and
terminal currentness head. It is not discovered by a scan.

The tombstone seals:

- the complete old `AcquisitionMandate`, exact shared `ProtectionMandate`, and old
  `DualMandateBinding`;
- terminal acquisition/currentness head, terminal lifecycle, owned quantity/notional, exact
  closed-parent proof, and old creation/claim identities;
- exact execution and venue commitments at retirement; and
- the distinct successor acquisition binding and its successor head.

An old binding, head, or retired tombstone can establish a successor only through the sealed
successor route. A late old fact may instead resolve its exact old effect/root identity through
the direct tombstone index, but may never establish acquisition authority. Reusing a retired
binding, omitting the predecessor, substituting a cross-symbol predecessor, or treating a retired
scope as new is refused.

### 3. Same-protection successor registration

`initialize_acquisition` and `RegisterAcquisitionCurrentness` gain only the opaque successor
proof necessary for R2. It may establish a same-symbol successor only when all of the following
hold atomically:

- the scoped-bootstrap projection is exact and authentic;
- the old lifecycle is terminal, its parent acceptance set is exactly `CLOSED`, and all old
  target-symbol ownership/reconciliation predicates are clear;
- the predecessor tombstone/head, scope, session, configuration, execution high-water, and venue
  commitment match exactly;
- the new `AcquisitionMandate` identity is distinct; and
- the new and old `ProtectionMandate` objects have the same exact identity and full immutable
  commitment.

The successor retains the exact predecessor `PositionProtectionState`; the scope retains at most
one shared protection state and does not initialize or mint a second protection authority. Its
live acquisition fields start clean: no issued BUY, no creation head, no preemption latch, no
exit-effect identity, and no successor acquisition economics. Old acquisition authority remains
terminal and cannot create or claim an effect.

For a target symbol with no M1E history, registration accepts `SCOPED_BOOTSTRAP` only without a
predecessor. For a previously retired target scope, registration requires the exact predecessor
tombstone and one-shot successor proof. Generic `CreateBrokerEffect` continues to refuse BUY
`SUBMIT` and BUY `REPLACE`; target-derived BUY cancellation retains its existing M1C route.

### 4. Late old-lineage handling under the one shared protection authority

Every old canonical FILL/CORRECT/BUST after succession is located only by its exact immutable
old effect/root binding through the tombstone's direct index. The reducer applies canonical
economics first, advances the old tombstone's acquisition economics only, and never credits old
economics to successor acquisition capacity.

The one retained `PositionProtectionState` advances exactly once from the aggregate current
execution projection under its unchanged protection mandate. If old lineage restores positive
quantity, it returns to sticky `HARD_BAIL` as required by ADR-021. In the same transition,
authority invalidates or preempts successor BUY authority and stands down safely local successor
BUY work through the existing bounded route; unknown work remains in the existing resolution
state. No second protection state, duplicate exit authority, new protection mandate, or reopened
old acquisition lifecycle is created.

### 5. Explicit exclusions

This amendment does not authorize a successor with different protection authority, simultaneous
protection policies for one position scope, protection-policy transfer/merging, raw venue input,
private-state access, generic BUY admission, audit/history materialization, runtime wiring,
persistence, broker activity, or an ADR change.

## Required RED and proof controls before implementation

- A valid first M1E acquisition for flat MSFT can bootstrap after historical AAPL venue activity,
  while AAPL state cannot substitute for MSFT.
- A terminal, exactly closed AAPL acquisition can start a distinct AAPL acquisition mandate only
  through the sealed successor proof and only with the exact same full protection mandate.
- A changed protection identity, formula, guard, evidence policy, session, configuration,
  predecessor, head, old binding, successor binding, scope, or a reused retired binding refuses.
- Late old FILL, CORRECT, and BUST before and after a successor BUY attempt/fill update old
  tombstone economics only, never replenish successor capacity, maintain one protection state,
  and apply the required shared-mandate `HARD_BAIL`/preemption result.
- Positive quantity, `OPEN`, `INVALIDATED`, pending/unknown legs, account reconciliation,
  copied/forged bootstrap, raw venue input, generic BUY, and stale successor currentness refuse.
- Bounded-work controls trap audit/history materialization and prove direct indexed lookup for
  bootstrap, retirement, and late-old-lineage routing.
- Existing genesis, target-derived cancellation/reduction, preemption cursor, and first-fill
  protection integration remain covered without compatibility aliases.

## Re-gate sequence

1. Obtain a fresh independent static preflight with P0=0/P1=0 for this exact draft.
2. Human ratifies the exact accepted amendment or supplies an alternative bounded design.
3. Freeze the amended active WO and hash, then write and confirm RED controls before production
   changes.
4. Implement the minimal root-level path, run focused and required full gates, then request a new
   independent exact-candidate acceptance.
