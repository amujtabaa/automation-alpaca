# Proposed WO-0149 R3 — bounded never-seen-scope bootstrap

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

## Decision to ratify

Extend pure M1E only enough to establish its first acquisition lifecycle for one exact
never-before-used `PositionScope` after other account scopes have canonical venue history.
This fixes the account-level-empty-book overconstraint without adding authority from history.

This amendment deliberately does **not** support a second M1E lifecycle for a previously used
target scope. A terminal/flat same-symbol acquisition still requires a new acquisition mandate
for any future entry, but creating that later lifecycle is deferred pending a new ADR that defines
protection/acquisition generation and late-lineage semantics. The amendment neither transfers nor
duplicates protection authority.

## Contract amendment

### 1. Sealed never-seen-scope bootstrap projection

`project_acquisition_venue(book, binding, *, execution=...)` gains a sealed bounded source kind,
`SCOPED_BOOTSTRAP`. It may be minted only from the exact current `VenueRecoveryBook` and exact
current `ExecutionSnapshot` for one requested `PositionScope` when all of the following hold:

- the target execution is exactly flat with zero target root heads and no target canonical
  economic lineage;
- account reconciliation is clear;
- the target scope has no prior venue effect, owner, request/claim, attempt, terminal closure,
  acceptance set, execution binding, dual-mandate binding, protection cursor, M1E live slot, or
  M1E retired-lineage record;
- the target scope has no active, pending, unknown, unresolved, cancellation-reserved,
  protection-exit, flatten, or conflicting single-flight ownership; and
- every predicate is obtained from bounded current scope indexes or direct keyed absence/count
  proofs. It must never materialize audit effects, owners, attempts, closures, or another
  lifetime collection.

The projection seals the exact book commitment, execution commitment, target-scope authority
proof, new complete dual-mandate binding, and `SCOPED_BOOTSTRAP` source kind. Account history for
other scopes is not authority and does not itself block the projection. Existing exact-empty-book
`GENESIS` behavior remains unchanged.

### 2. First-lifecycle-only initialization and registration

`initialize_acquisition` accepts `SCOPED_BOOTSTRAP` only as a first lifecycle: it has no
predecessor, no prior acquisition currentness, and no retained protection state. On the first
owned BUY fill it therefore uses the existing `initialize_position_protection` path and preserves
the accepted `FLOOR_ONLY` first-fill behavior.

`RegisterAcquisitionCurrentness` accepts this source only when the exact target scope has no live
or retired M1E record and its currentness predecessor is absent. It rechecks exact book/execution
commitments, account/symbol/session/configuration scope, the complete dual mandate binding, and
the never-seen target proof before it records the sole live M1E head.

The route refuses a copied/forged bootstrap, any predecessor, any historical target-scope fact,
an old binding, stale head, cross-scope substitution, nonflat execution, reconciliation concern,
or nonempty target authority predicate. It never creates a tombstone, rollover projection, or
same-scope successor route.

### 3. Preserved boundaries

Generic `CreateBrokerEffect` continues to refuse BUY `SUBMIT` and BUY `REPLACE`. A raw
`RequestedEffect`, caller-built currentness, copied commitment, neutral transition, private venue
accessor, or audit-history scan cannot establish bootstrap authority. Target-derived BUY
cancellation retains its existing M1C route.

The active M1E lifecycle remains terminal after `COMPLETED` or `ABORTED`. A later same-scope entry,
including one after exact flatness and exact parent closure, is explicitly out of scope for this
amendment and must refuse rather than reuse, reset, or replace the old lifecycle.

## Required RED and proof controls before implementation

- Historical AAPL account activity does not prevent the first ever MSFT-scope M1E bootstrap; the
  first owned MSFT BUY fill follows the unchanged `FLOOR_ONLY` initialization path.
- Any prior MSFT-scope root, effect, owner, request/claim, attempt, closure, acceptance set,
  execution binding, protection cursor, dual binding, M1E record, or retired lineage refuses,
  even if it is flat, terminal, and `CLOSED`.
- Any predecessor, copied/forged `SCOPED_BOOTSTRAP`, raw venue input, generic BUY,
  cross-symbol/account/session/configuration substitution, positive quantity, reconciliation
  concern, `OPEN`/`INVALIDATED`, pending/unknown ownership, or stale currentness refuses.
- Bounded-work controls trap every audit/history materializer and prove that bootstrap uses only
  the direct target-scope absence/count indexes.
- Existing exact-empty genesis, generic cancellation/reduction, first-fill protection integration,
  preemption cursor, and late owned fact after an active lifecycle remain covered without
  compatibility aliases.

## Re-gate sequence

1. Obtain a fresh independent static preflight with P0=0/P1=0 for this exact draft.
2. Obtain human ratification of the exact accepted amendment or an alternative design.
3. Freeze the amended active WO and hash, write and confirm RED controls, then make production
   changes only within the ratified allowed paths.
4. Run focused and required full gates, then request a new independent exact-candidate acceptance.
