# WO-0168c frozen non-serving checkpoint contract — R18 exact dormant storage grammar

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO DDL OR DATABASE AUTHORITY**

Date: 2026-08-23

R18 incorporates R17 and replaces only its sections 1-3 dormant wire/provenance details. Two fresh
R17 reviewers agreed that all six R16 findings were resolved and found only an unspecified dormant
payload grammar plus aliasing of wire-integrity and source-projection commitments. This amendment
closes those two findings. All other R17 and recursively incorporated authority remains exact.

## 1. Exact selected-order ordinal replacement

R17's repository-proof order remains authoritative. In the retained R1 venue EffectCurrent and
OwnerAttempt rows, `I(source_ordinal)` is replaced by `I(checkpoint_ordinal)`: the zero-based index
of that row in its exact proof-selected family after the frozen SQL/vector canonical ordering.
It does not claim reducer insertion order. The value is dense `0..n-1`; wrong, missing, duplicate,
or reordered values fail literal known answers. No venue source order or rank map is read.

## 2. Dormant storage-projection primitives

The following scalar notation is exact: `A(x)` is the existing durable M1 atom array; `I(x)` is an
exact JSON integer (never Boolean); `T(x)` is exact JSON text; `H(x)` is lowercase 64-character
SHA-256 text; and `N` is JSON null. Every collection is exactly `[tag,count,rows]`, has count equal
to row-array length, is capped at 65,535, and retains the corresponding selection-proof family
order without another sort.

The five wrappers and child rows are:

```text
DormantGenerationRows =
 ["m2.acquisition.DormantGenerations/v1",count,[
  ["m2.acquisition.DormantGeneration/v1",A(acquisition_generation_id),
   I(scope_id),T(status),I(successor_ordinal),A(predecessor_generation_id)|N,
   H(mandate_commitment_sha256),H(emergency_compatibility_sha256)]...]]

DormantGenerationCurrentRows =
 ["m2.acquisition.DormantGenerationCurrents/v1",count,[
  ["m2.acquisition.DormantGenerationCurrent/v1",A(acquisition_generation_id),
   I(scope_id),I(current_economics_head_ordinal),I(unresolved_effect_count),
   I(active_protection_count)]...]]

DormantMarketStreamRows =
 ["m2.acquisition.DormantMarketStreams/v1",count,[
  ["m2.acquisition.DormantMarketStream/v1",A(stream_generation_id),I(scope_id),
   A(application_generation_id),A(acquisition_generation_id),
   H(generation_mandate_commitment_sha256),T(source_profile_id),A(session_id),
   T(sequence_mode)]...]]

DormantMarketCursorRows =
 ["m2.acquisition.DormantMarketCursors/v1",count,[
  ["m2.acquisition.DormantMarketCursor/v1",A(stream_generation_id),I(scope_id),
   A(application_generation_id),A(acquisition_generation_id),
   H(generation_mandate_commitment_sha256),T(source_profile_id),A(session_id),
   T(sequence_mode),I(fixed_cursor_ordinal),I(published_head_ordinal)]...]]

DormantLineageRows =
 ["m2.acquisition.DormantLineageRoutes/v1",count,[
  ["m2.acquisition.DormantLineageRoute/v1",E(GenerationRouteKind),Identity,
   A(acquisition_generation_id),SourceBinding,H(source_record_binding),
   H(route_commitment)]...]]
```

All rows are raw repository storage projections; none is an owner-derived R1 `Generation` or
`MarketStreamRoute`. Generation and current rows pair one-for-one by `(scope_id,generation_id)`.
Streams and present cursors pair by stream ID and must name one included generation. A missing
cursor is represented only by the exact selection-proof cursor absence; no null cursor row exists.

`source_record_binding` is the existing domain-separated
`_runtime_checkpoint_selected_record_binding` of the exact selected source record. Lineage rows
are ordered by `REQUEST,EFFECT,OWNER,ROOT,FACT`, then canonical durable `Identity`. Their exact
identity/source forms are:

```text
REQUEST: Identity=A(request_occurrence_id);
         SourceBinding=["m2.acquisition.LineageEffectSource/v1",A(effect_external)]
EFFECT:  Identity=A(effect_external);
         SourceBinding=["m2.acquisition.LineageEffectSource/v1",A(effect_external)]
OWNER:   Identity=A(VenueLegKey(position-scope venue coordinates, owner_id));
         SourceBinding=["m2.acquisition.LineageOwnerSource/v1",I(scope_id),A(owner_id)]
ROOT:    Identity=A(RootFillKey(position-scope venue coordinates, root_fill_id));
         SourceBinding=["m2.acquisition.LineageRootSource/v1",I(root_fill_key_id)]
FACT:    Identity=A(ExecutionFactKey(position-scope venue coordinates, source_event_id));
         SourceBinding=["m2.acquisition.LineageFactSource/v1",I(fact_id)]
```

REQUEST/EFFECT source the exact selected `VenueEffectRecord`; OWNER sources the exact selected
`VenueIdentityOwnerRecord`; ROOT sources the exact paired selected `AcquisitionRootRouteRecord` and
`RootFillRecord` (its `source_record_binding` is
`K("execution-core/m2-acquisition/dormant-root-source/v1",route-binding,root-binding)`); FACT
sources the exact selected `ExecutionFactRecord`. `route_commitment` is
`K("execution-core/m2-acquisition/dormant-lineage-route/v1", canonical row without final member)`.
Every identity, generation, and source coordinate must agree with those records.

## 3. Exact dormant rows and distinct provenance commitments

The R17 acquisition row keeps its exact 17 members, substituting the five wrappers above. Its
integrity members are:

```text
bounded_registry_commitment =
 K("execution-core/m2-acquisition/dormant-registry/v2",
   canonical four generation/current/stream/cursor wrappers)
bounded_lineage_commitment =
 K("execution-core/m2-acquisition/dormant-lineage/v2",canonical lineage wrapper)
dormant_commitment =
 K("execution-core/m2-acquisition/dormant/v2",canonical row without final member)
```

The acquisition source-owner slot instead contains the distinct:

```text
K("execution-core/m2-acquisition/dormant-source-projection/v1",
  FIELD_BYTES(selection_proof_binding),FIELD_INT(scope_id),
  FIELD_BYTES(selected-controller-record-binding),
  SEQ_DOMAIN("execution-core/m2-acquisition/dormant-selected-records/v1",
             FIELD_BYTES(each exact generation/current/stream/cursor/lineage source-record
                         binding in the same partitioned order)))
```

The dormant protection wire remains R17's seven-member row and its final wire-integrity digest
remains `K("execution-core/m2-protection/dormant/v1", row without final member)`. Its source-owner
slot instead contains:

```text
K("execution-core/m2-protection/dormant-source-projection/v1",
  FIELD_BYTES(selection_proof_binding),FIELD_INT(scope_id),
  FIELD_BYTES(selected-protection-authority-record-binding))
```

Thus neither wire self-hash is authority or provenance. Controls independently alias each valid
wire self-hash into its source-owner slot, swap the two distinct source-projection commitments,
omit one, and cross-scope substitute one; all fail. Literal empty and representative nonempty
known answers pin every wrapper tag, count, row tag, member, order, optional, self-integrity
preimage, and source-projection preimage.

## 4. Boundaries

R18 changes no SQL, DDL byte, public export, transaction rule, runtime composition, serving type,
or serving authority. Fresh REV-0077 review must return exact R18 `ACCEPT` with `P0=0/P1=0` before
source implementation resumes. No SQLite, schema install, configured database, or in-memory
database is authorized by this amendment.
