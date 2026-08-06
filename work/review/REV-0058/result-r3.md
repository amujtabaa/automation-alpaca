# REV-0058 R3 pre-flight result

Status: **RETAINED NEGATIVE EVIDENCE -- R3 IS NOT ACCEPTED**

Three fresh independent static reviewers verified the R2+R3 composite hashes
against the R3 manifest and compared the candidate with ADR-020 R2, ADR-021
R2, ADR-023 R1, WO-0151, and the active E1 seams. They changed no source,
test, ADR, work-order, PKL, ledger, or lifecycle record.

## Result

**BLOCK** -- P0: 0, P1: 2, P2: 0.

R3 closed the R2 genesis-coordinate, retired-reconciliation precedence,
protection pre/post relation, and specialized BUY mandate-field findings. Two
connected scope/fence requirements remain:

1. **P1 -- application-generation fence.** GENESIS_EMPTY did not bind and
   recheck the caller-supplied ApplicationGenerationId against the live
   authority/venue generation. PositionScope excludes that cutover identity, so
   a typed but different application generation could derive a valid-looking
   first controller coordinate.
2. **P1 -- unscoped authority pair.** R3 proposed scalar authority execution
   and venue commitments even though the authority and recovery book are
   account-level and retain direct bindings for multiple PositionScopes. The
   scalar could bind another symbol or make a controller stale solely because
   of unrelated-symbol activity.

## Required replacement direction

R4 must replace the scalar authority reads with one opaque, bounded,
exact-PositionScope authority context that binds the target execution/venue
pair and the current application-generation fence. The target venue commitment
must be explicitly scope-derived rather than a whole-account book commitment;
it may include the necessary bounded account-safety fence without scanning
history. Genesis, registration, rebase, and specialized permits must consume
that same exact context. R3 and this result remain unchanged as retained
negative evidence. A new exact R4 freeze and focused review are required
before activation.

