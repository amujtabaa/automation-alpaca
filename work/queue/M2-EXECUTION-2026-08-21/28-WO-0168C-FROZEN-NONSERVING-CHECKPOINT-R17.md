# WO-0168c frozen non-serving checkpoint contract — R17 database-anchored dormant closure

Status: **PREFLIGHT REMEDIATION CANDIDATE — DOCUMENTATION ONLY; NO DDL OR DATABASE AUTHORITY**

Date: 2026-08-23

R17 incorporates accepted R13, R14's direct effectless-manual route, R15's authority domains and
lineage integer grammar, and the unchanged portions of R16. It supersedes R16 after two fresh
reviewers independently returned `ACCEPT-WITH-CHANGES` (`P0=0`, `P1=3`). This amendment replaces
R15/R16 source-rank projection, the R16 dormant acquisition/protection form, and their controls.
No other recursively incorporated clause changes.

## 1. Repository order is checkpoint order; reducer insertion order is not claimed

The checkpoint is inert and does not claim that bounded database rows reproduce history-shaped
`VenueRecoveryBook` insertion order. Projection therefore does not read `_effect_order`,
`_owner_order`, a derived rank map, or any whole-order commitment. The two proposed R15/R16 rank
maps are deleted from the contract and must not be implemented.

The repository-authentic selection proof is the sole selected-row membership and order witness.
Every collection uses its already frozen SQL/vector canonical order, including effects by
`(created_ordinal,effect_id)` and owners by the exact Q4b/Q5 vector keys. Projection performs only
direct current-owner lookups for those proof-selected keys, deeply validates equality to each
selected record, and emits rows in proof order. It neither compares selected cardinality with
unrelated source history nor consults an unselected order member. Swapping, omitting, duplicating,
or substituting proof rows fails the selection-proof binding before projection.

WO-0169 may not hydrate this inert order directly into serving reducer state. Its owner-locked
conversion must define and review the cutover from canonical checkpoint order to any new serving
order and prove behavior independently. Existing source insertion order and its history-shaped
commitment are deliberately outside WO-0168c's restart claim.

## 2. Closed acquisition union

An active scope retains the existing 17-member acquisition form and requires one exact authentic
`AcquisitionControllerState`. Its selected controller, LIVE generation/current row, stream/cursor,
and all selected unresolved generations, streams, and lineage rows must agree exactly with the
owner and with the repository proof. No selected acquisition row may be omitted merely because it
is retired.

A scope whose selected controller has `live_acquisition_generation_id=None` has no acquisition
serving owner. It uses this exact database-derived form:

```text
["m2.acquisition.Dormant/v2",A(application_generation_id),PositionScope,
 I(scope_id),I(aggregate_quantity),T(integrity_state),I(currentness_head_ordinal),
 I(controller_version_ordinal),H(emergency_compatibility_sha256),
 UnresolvedGenerationRows,UnresolvedGenerationCurrentRows,
 UnresolvedMarketStreamRows,UnresolvedMarketCursorRows,LineageRows,
 H(bounded_registry_commitment),H(bounded_lineage_commitment),
 H(dormant_commitment)]
```

The five collections are the complete proof-selected rows for that scope, partitioned from the
already authenticated selection without another query. Their row grammars and canonical order are
the retained R1/R5 generation/current, stream/cursor, and lineage forms. Each current row must pair
with exactly one generation; each stream/cursor and lineage source must resolve to one selected
generation and the exact selected effect/owner/root/fact source row. Empty is valid; a null-LIVE
scope with selected retired unresolved state is valid and nonempty.

`bounded_registry_commitment` is
`K("execution-core/m2-acquisition/dormant-registry/v2", canonical generation/current/stream/cursor collections)`.
`bounded_lineage_commitment` is
`K("execution-core/m2-acquisition/dormant-lineage/v2", canonical lineage collection)`.
`dormant_commitment` is
`K("execution-core/m2-acquisition/dormant/v2", canonical row without final member)`.
The exact 32-byte dormant commitment occupies the acquisition slot of the retained R6
`scope_owner_commitments` row. This slot is explicitly a source-projection commitment, not a
serving-owner commitment: it is derived from repository-authentic selected records and is bound
again by `selection_proof_binding`. No absent-owner sentinel or synthetic acquisition owner exists.

## 3. Closed protection union and scope cross-binding

An active protection-authority row retains the existing exact authentic
`PositionProtectionState` form and proof relation. A row whose six active stream/acquisition/
mandate/source/session/sequence members are all null has no protection serving owner and uses:

```text
["m2.protection.Dormant/v1",I(scope_id),T(authority_class),
 I(expected_controller_head_ordinal),H(state_commitment_sha256),
 I(version_ordinal),H(dormant_commitment)]
```

Its commitment is
`K("execution-core/m2-protection/dormant/v1", canonical row without final member)` and occupies the
protection slot of the R6 source-owner row. It authenticates retained database state only; it does
not claim to reconstruct a `PositionProtectionState`. Partial-null active coordinates fail.

Every scope still requires an exact authentic `ExecutionSnapshot`. Projection re-encodes it and
requires exact agreement with all selected execution roots, heads, current facts, quantities,
scope coordinates, and absence evidence. The selected controller aggregate quantity must equal
`execution.position.raw_quantity`; the controller/application/profile/scope coordinates and
protection scope must agree; and protection `expected_controller_head_ordinal` must equal the
controller currentness head. Controller `integrity_state` remains an exact database lifecycle
classification committed in the acquisition row; it is not falsely equated to the narrower
`PositionIntegrity` flag grammar.

For active protection, `raw_quantity == execution.position.raw_quantity`,
`execution_commitment == execution.commitment`, protection scope is exact, and the selected
authority's state commitment, version, expected head, active stream, acquisition, mandate, source,
session, and sequence coordinates must all match the authentic protection owner and selected rows.
For dormant protection, the database-derived commitment replaces those unavailable owner
relations. Same-scope stale execution, active protection, controller, or authority substitutions
fail independently.

## 4. Per-family superset and dormant controls

Noise invariance is separate and failure-capable for:

1. unselected closed effect authorizations;
2. an unrelated historical claim present consistently in both claim indexes; and
3. an unrelated historical descriptor-by-effect row.

Each holds the selected proof and payload bytes fixed while changing only that source superset and
kills a family-local whole-map-cardinality mutant. Exact selected-scope current maps retain their
R16 completeness rule.

Dormant controls independently cover empty and nonempty unresolved registries, missing/current
pair mismatch, stream/cursor mismatch, every lineage-source mismatch, wrong registry/lineage/self
commitment, wrong acquisition or protection source-owner slot, partial-null protection authority,
controller/execution quantity mismatch, head mismatch, and same-scope stale owner substitution.
Active controls retain the exact owner/selection relations. Static controls fail any source-order
or rank-map dependency and any projector loop over unselected persistent history.

## 5. Boundaries

R17 changes no SQL, DDL byte, public export, transaction rule, runtime composition, or serving
authority. It narrows implementation by deleting the venue rank-map change and permits no new
source path. Fresh REV-0077 review must return exact R17 `ACCEPT` with `P0=0/P1=0` before source
implementation resumes. No SQLite, schema install, configured database, or in-memory database is
authorized by this amendment.
