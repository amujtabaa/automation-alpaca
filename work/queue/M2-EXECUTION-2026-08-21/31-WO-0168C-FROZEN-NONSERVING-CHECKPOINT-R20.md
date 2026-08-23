# WO-0168c frozen non-serving checkpoint contract — R20 implementability closure

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO DDL OR DATABASE AUTHORITY**

Date: 2026-08-23

R20 incorporates R19 and resolves three implementation-time contradictions missed by the R19
review. All other R19 and recursively incorporated authority remains exact.

## 1. Distinct venue source-projection commitment

The venue row's final member remains the wire-integrity commitment
`K("execution-core/m2-venue/state/v1", canonical venue row without final member)`.
The projected-envelope `venue_owner_commitment` instead contains the distinct
`K("execution-core/m2-venue/source-owner/v1", canonical venue row without final member)`.
The authority `VenueRef` contains the wire-integrity commitment, not the source-owner commitment.
The outer owner preimage separately binds the repository selection proof, so no payload digest,
history-shaped `_protection_commitment`, serving proof, or circular envelope value participates.
Aliasing either commitment, swapping their consumers, or changing one selected source member fails.

## 2. Authority collection ordering

R17 proof-family order applies to database-selected venue/acquisition families. Authority
collections retain R2 canonical semantic-key order because their rows are projections of current
owner maps, not repository vectors. Effect authorizations are ordered by canonical effect ID;
manuals by flatten ID; descriptors by effect ID; and slots by PositionScope canonical durable-atom
bytes. Claims remain nested beneath their effect authorization. Input order and whole-map order are
never consulted.

## 3. Terminal manual references are bounded owner semantics

`_ManualFlatten.cancel_effect_ids` and `sell_effect_id` are payload-owned authenticated semantics.
They are emitted from the exact current manual reached through `_manual_flatten_by_scope` then
`_manual_by_id`. The cancel tuple is capped at 65,535, requires exact `EffectId` members, and is
canonical effect-ID ordered with no duplicates; sell is exact or null.

If a referenced effect is in the repository-selected effect family, its owner authorization and
selected record must agree exactly. A terminal cancel effect omitted by the frozen OPEN/INVALIDATED
selection remains valid owner-only manual history and does not require a selected
`VenueEffectRecord`. It cannot create a current venue effect row or serving authority. A mutant that
requires every terminal manual reference to be repository-selected must fail the retained READY
control; a mutant that accepts a forged/unreachable manual, duplicate ID, wrong scope, or malformed
identity must also fail.

The same rule applies only to terminal IDs nested in a reached current manual. Current effect
authorizations, current claims, descriptor-by-effect rows, and active slots still require their
existing selected/direct proof relations. No SQL predicate, query, DDL byte, or row cap changes.

## 4. Execution

Implementation must remove `_validate_full`, `_effect_order`, `_owner_order`, source-rank, and
whole-history dependencies from projection. Venue uses proof-selected direct keys and dense
checkpoint ordinals; authority uses the canonical owner-key ordering above. The checkpoint and
source-owner domains for venue and authority are distinct and exact.

R20 changes no SQL, DDL byte, public export, transaction rule, runtime composition, serving type,
or serving authority. Fresh REV-0077 exact-head review must return `ACCEPT` with `P0=0/P1=0` before
implementation resumes. No SQLite or database execution is authorized.
