# WO-0168c frozen non-serving checkpoint contract — R16 authenticated ranks and dormant scopes

Status: **PREFLIGHT REMEDIATION CANDIDATE — DOCUMENTATION ONLY; NO DDL OR DATABASE AUTHORITY**

Date: 2026-08-23

R16 incorporates accepted R13 and all unmodified R15 corrections. It supersedes R15 after both R15
reviewers returned `ACCEPT-WITH-CHANGES` (`P0=0`, `P1=2`). This file replaces only R15 sections 1,
4's map-cardinality sentence, 5's live-generation shape, and the corresponding controls.

## 1. Direct rank lookup is authenticated by the existing source order

Venue retains the two R15 derived direct rank maps. For each selected effect or owner, projection
must perform all of these constant-depth checks:

1. direct current-row lookup by canonical key;
2. direct rank lookup by the identical key;
3. exact non-negative integer rank within the retained order length; and
4. `book._effect_order.get(rank) == effect_id` or
   `book._owner_order.get(rank) == leg_key`, respectively.

The rank-map size must equal both its current-map size and its source-order length. Projection never
iterates an unselected order member. Missing, substituted, swapped, duplicate, out-of-range, or
wrong-key ranks fail. Full-audit validation separately folds the complete order and rank map for
offline corruption diagnosis; that fold is not called by projection.

The exact field names
`_checkpoint_effect_source_ordinal_by_id` and
`_checkpoint_owner_source_ordinal_by_leg` are added to
`_protection_book_commitment`'s derived-field exclusion set. They must not affect the existing
venue/protection commitment, any reducer decision, or any serving proof. Empty and representative
nonempty pre-R16 commitment known answers must remain byte-identical; removing either exclusion or
consulting either map from a serving path must fail a named control.

## 2. Authority maps have per-family completeness rules

Projection deeply validates every reached row, but it does not compare a selected subset with an
append-only/history map's whole size.

- Exact current selected-scope maps: `_manual_flatten_by_scope`,
  `_acquisition_currentness_by_scope`, `_acquisition_descriptor_by_scope`, and
  `_acquisition_active_by_scope`. Because repository selection contains every application scope,
  every present key in these maps must be one selected scope and every selected-scope lookup must
  have the exact closed absent/present combination.
- Directly reachable current rows: `_manual_by_id` is reached from the exact current scope index;
  its retained row must match, but older unreachable IDs are omitted.
- Permitted authenticated supersets: `_effect_authority_by_id`, `_claim_by_effect`,
  `_claim_by_occurrence`, and `_acquisition_descriptor_by_effect`. Only rows reached by a selected
  effect or a selected current slot are checkpointed; unrelated closed-effect history is omitted.
- Omitted replay/history indexes remain `_input_by_id`, `_query_by_id`,
  `_consumed_grant_ids`, and derived reverse indexes already excluded by R13.

Pure noise-invariance controls pair one selected live effect with arbitrary unselected closed
ownerless authorizations and require identical payload bytes. A whole-map-cardinality mutant must
fail that control.

## 3. Selected scopes without a live acquisition generation

A repository-selected `SymbolControllerRecord.live_acquisition_generation_id is None` is valid and
must not be silently rejected. Such a scope has no `AcquisitionControllerState` owner and uses the
exact inert database-derived row:

```text
["m2.acquisition.Dormant/v1",A(application_generation_id),PositionScope,
 I(aggregate_quantity),T(integrity_state),I(currentness_head_ordinal),
 I(controller_version_ordinal),H(emergency_compatibility_sha256),
 H(dormant_commitment)]
```

`dormant_commitment` is
`K("execution-core/m2-acquisition/dormant/v1", canonical row without final member)`.
The selected controller must have no selected LIVE generation/current row for that scope. Its
selected protection-authority row must have its active stream generation, acquisition generation,
generation-mandate commitment, source profile, session, and sequence-mode members wholly null,
while its expected controller head, state commitment, and version remain exact. The provided
scope-owner value contains `acquisition=None` plus exact execution and
protection owners; aggregate quantity and selected scope coordinates must agree with the execution
owner. Any partial active coordinates, supplied acquisition owner, selected LIVE row, or cross-scope
splice fails.

An active selected controller still requires an exact authentic `AcquisitionControllerState` and
the existing 17-member active acquisition row. The inert decoder accepts exactly the active or
dormant tag and never constructs an acquisition owner. The outer scope remains a single row; this
is a closed acquisition-component union, not an optional missing component. WO-0169 alone decides
whether a dormant candidate can become restart-eligible.

## 4. Revised controls and retained boundaries

Pure controls add swapped/substituted rank values, rank-map/order/current-map cardinality mutants,
unchanged serving commitments, unselected historical authority noise, and the complete dormant
scope matrix. Static controls forbid any whole-order loop in the projector and pin the two exact
commitment exclusions. Existing R15 manual, authority-domain, lineage-integer, selected-subset, and
over-cap noise controls remain.

R16 changes no SQL query, DDL byte, public export, runtime composition, transaction rule, or serving
authority. The existing nullable controller storage/selection contract is retained. Fresh REV-0077
review must return exact R16 `ACCEPT` with `P0=0/P1=0` before source implementation proceeds.
