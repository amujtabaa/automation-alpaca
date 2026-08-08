# Proposed WO-0149 R1 — bounded successor bootstrap

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

## Decision to ratify

Extend the existing pure-M1E contract only enough to permit a sealed acquisition lifecycle to
start after canonical account history exists, without reopening generic exposure-increasing BUY
creation or creating a history-derived authority path.

No new ADR is proposed for the exact-flat case: ADR-020/ADR-021 already require a new mandate for
new entry and symbol-scoped ownership. If a later decision permits rollover while positive
exposure remains, or transfers active protection authority between mandates, stop for a new ADR.

## Contract amendment

1. `project_acquisition_venue(book, binding, *, execution=...)` gains one additional sealed,
   bounded source kind: `SCOPED_BOOTSTRAP`. It is not a caller-provided projection or an alternate
   constructor. It may be minted only from the exact current `VenueRecoveryBook` and exact current
   `ExecutionSnapshot` for the requested account/symbol when all of the following are true:

   - the requested position is exactly flat;
   - account reconciliation is clear;
   - the target symbol has no live, pending, unknown, or unresolved BUY/SELL ownership;
   - the target symbol has no unmatched cancellation/closure condition; and
   - each fact is derived with existing bounded current indexes/direct per-effect lookups, never
     from `effects`, `owners`, attempts, closure history, or another lifetime materialization.

   The opaque projection seals the exact book, execution, target scope, dual-mandate binding, and
   bounded target-symbol authority proof. Existing `GENESIS` behavior remains unchanged.

2. `initialize_acquisition` gains one optional opaque predecessor-currentness argument. `None`
   retains first-scope genesis/bootstrap behavior. A supplied predecessor is accepted only when it
   is exact/authentic, has the same account/symbol/session/configuration authority, represents a
   terminal old acquisition lifecycle, and is paired with an exact current `SCOPED_BOOTSTRAP` for a
   distinct new dual-mandate binding. The new composite head is successor-linked to the old head.
   No caller may mark a currentness terminal or synthesize this relationship.

3. `RegisterAcquisitionCurrentness` recognizes that exact successor only. For a new symbol it
   registers the scoped-bootstrap head only when no record exists. For a same-symbol rollover it
   atomically retires the old M1E slot only when its parent acceptance set is exactly `CLOSED`,
   target-symbol authority is clear, the predecessor head matches, the old lifecycle is terminal,
   and the new binding has a distinct acquisition mandate identity. It preserves venue/audit
   history and refuses stale heads, `OPEN`/`INVALIDATED`, nonflat execution, reconciliation,
   pending/unknown legs, old binding replay, and cross-symbol substitution.

4. `CreateAcquisitionEffect` remains the sole path for an exposure-increasing BUY. Generic
   `CreateBrokerEffect` still refuses BUY `SUBMIT`/`REPLACE`; inherited target-derived BUY
   cancellation remains available under its existing M1C rules.

## Required RED and proof controls before implementation

- A prior M1E lifecycle reaches terminal state and exact parent closure; a distinct next mandate
  for that same flat symbol can use only the sealed successor route.
- Existing AAPL history does not prevent a valid, flat MSFT scoped bootstrap, while an AAPL
  binding/old head cannot be substituted for MSFT.
- Positive quantity, `OPEN`, `INVALIDATED`, pending/unknown legs, account reconciliation, stale
  predecessor, reused binding, raw venue input, generic BUY, and a copied/forged bootstrap all
  fail at construction, registration, creation, or final claim as applicable.
- Bounded-work controls trap audit/history materialization on the bootstrap path.
- The regular first-genesis path, generic cancellation/reduction behavior, preemption cursor, and
  first-fill protection integration remain covered without compatibility aliases.

## Re-gate sequence

1. Human ratifies this exact amendment or supplies an alternative bounded design.
2. Freeze the amended WO and its hash, then obtain a fresh focused independent preflight with
   P0=0/P1=0.
3. Write and confirm RED controls before production changes.
4. Implement the minimal root-level path, run focused and full required gates, then request a new
   independent exact-candidate acceptance.
