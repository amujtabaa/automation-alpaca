# WO-0168c frozen non-serving checkpoint contract — R2

> **SUPERSEDED — NOT IMPLEMENTATION AUTHORITY.** REV-0077 R2 found eleven P1 and one P2 defect.
> The authoritative successor is `11-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R3.md` plus its exact
> `12-WO-0168C-R3-SQL-MANIFEST.md`. This file remains review evidence only.

Status: **PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `156639473ee6d0773c765ab1f04d1f1de58dc633`

## 1. Precedence and deliberate simplifications

This file is the sole R2 authority. It retains contract 09 sections 1, 3, 4, 6, and 10 only where
this file does not replace them. Contract 07 and contracts 08/09 are otherwise superseded evidence.

R2 makes four root corrections:

1. every decoded value is inert; no decoder or repository method creates a serving owner/proof;
2. selection, canonical projection, payload insert, and exact predecessor CAS are one acyclic path;
3. complete sets come from fixed bounded repository queries, while owner-only semantics are
   authenticated at projection and anchored by payload bytes; and
4. no persistent-map witness is serialized in WO-0168c. All R1 witness limits and witness tests are
   deleted. WO-0169 owns omitted-history replay/nonmembership and serving conversion.

There is no compatibility format: no R13 checkpoint has been installed. All retained tags remain
`/v1` and receive one implementation.

## 2. Canonical grammar is byte-complete

Canonical JSON and scalar forms are contract 09 section 2 with these exact corrections.

Key-frame octets are `N=0x00`, `B=0x01`, non-negative `I=0x02`, negative `Z=0x03`, `T=0x04`,
`X/H=0x05`, `A=0x06`, `E=0x07`, tagged array=`0x08`, composite=`0x09`. Boolean is never an
integer. Non-negative integers use `0x02`; `0x03` admits only `-2^63..-1`.

A scalar frame is `octet || uint64-be(len(canonical_json_utf8(value))) || bytes`. A composite of
at least two components is `0x09 || uint32-be(count) ||` each complete component frame preceded by
`uint64-be(len(frame))`. A tagged-array key includes its literal tag. An enum is exactly
`[literal_owner_tag,literal_member_value]`; every row below names its owner tag and aliases fail.

Limits measure the canonical UTF-8 bytes of the complete value, including tag, count, nested rows,
and delimiters. Validate leaves, then rows, then wrappers, then components, then payload; reject as
soon as a level exceeds its limit. `X` is measured after hex decoding and before encoding; `T` and
`A` use UTF-8 byte length. Existing limits remain: 4,096 scopes, 65,535 rows per family, 2,097,152
bytes per row, 67,108,864 per wrapper/component, and 268,435,456 per payload. No witness-node or
witness-child limit remains because no witness row exists.

Ordered semantic tuples—including bootstrap summary ID tuples—preserve source order. Keyed sets
use the frames above. No other collection ordering exists.

## 3. Exact inert carriers

`persistence/checkpoint_codec.py` adds three public constructor-hidden values and four private
carriers. All are frozen, slotted, exact-type, non-subclassable, and issuer-bound:

```python
class InertRuntimeCheckpointComponent:
    tag: str
    canonical_bytes: bytes
    commitment_sha256: str
    _binding: bytes
    _issuer: object

class RuntimeCheckpointScopeCandidate:
    scope_id: int
    position_scope: InertRuntimeCheckpointComponent
    acquisition: InertRuntimeCheckpointComponent
    execution: InertRuntimeCheckpointComponent
    protection: InertRuntimeCheckpointComponent
    _binding: bytes
    _issuer: object

class RuntimeCheckpointEnvelope:
    application_generation_id: ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    currentness_head_ordinal: int
    checkpoint_version_ordinal: int
    venue: InertRuntimeCheckpointComponent
    authority: InertRuntimeCheckpointComponent
    scopes: tuple[RuntimeCheckpointScopeCandidate, ...]
    canonical_payload_bytes: bytes
    payload_sha256: str
    _provenance: str                 # exactly PROJECTED or LOADED
    _selection_binding: bytes
    _binding: bytes
    _issuer: object

class _InertM2ExecutionComponent: _canonical_bytes: bytes
class _InertM2ProtectionComponent: _canonical_bytes: bytes
class _InertVenueTransitionProof: _canonical_bytes: bytes
class _InertBootstrapTarget: _canonical_bytes: bytes
```

Each authenticity check requires exact class, its distinct private sentinel, a re-derived 32-byte
binding over every semantic field, and failure on attribute/type/value/overflow error. Exact type
without binding is never sufficient. The projected envelope binds the authentic selection proof
plus every source-owner commitment and payload byte. The loaded envelope binds a private fresh
load proof plus the exact payload bytes. A loaded envelope may be re-encoded for inspection but
cannot be passed to the store path.

The component decoders parse one complete JSON value, validate the closed grammar, re-encode and
byte-compare, then retain canonical bytes. They never call
`_m2_execution_state_from_direct_proof`, `_M2ProtectionCheckpoint(...)`,
`_m2_position_protection_from_checkpoint`, `_m2_issue_protection_authority_proof`, or any owner
constructor.

Execution is the exact current 21-member `m2.position.execution-state/v1` array in
`checkpoint_codec.py`: tag, `PositionScope`, raw quantity, literal
`["m2.position.BasisAuthority",value]`, optional exact basis, optional price metadata,
optional tail fold, literal integrity-floor/integrity pairs, reconciliation Boolean/count/head,
root count, six map/order commitments, and state commitment. Protection is the exact current
32-member `m2.protection.checkpoint/v1` array: tag followed by all 31 fields in the current encoder
from policy through exit provenance. Projection calls the current encoders only after authentic
source-owner checks; load uses separate bytes-only parsers.

## 4. Complete venue/bootstrap wire

The venue top row and child rows are contract 09 section 4, except for these binding corrections.
Every enum shorthand uses its literal owner tag from contract 07 section 2.3. Effect and owner
source ordinals obey section 6 below.

`BootstrapCandidate` is exactly active or consumed; staged values and map-seal bytes are refused.
Active is the exact 25-member row:

```text
["m2.venue.BootstrapTargetActive/v1",A(application_generation_id),PositionScope,
 ["m1.venue.BootstrapSourceKind",value],H(source_execution),H(target_genesis),
 H(target_execution),VenueExecutionBinding,I(account_registry_count),H(account_registry),
 I(reconciliation_count),H(reconciliation_head),A(bootstrap_input),H(bootstrap_input_commitment),
 H(bootstrap_target_execution),I(bootstrap_registry_count),H(bootstrap_registry),
 I(bootstrap_reconciliation_count),H(bootstrap_reconciliation_head),
 H(bootstrap_neutral_proof_commitment),InertVenueTransitionProof,A(checkpoint_input),
 H(checkpoint_command_commitment),H(neutral_proof_commitment),InertVenueTransitionProof]
```

Consumed is exactly
`["m2.venue.BootstrapTargetConsumed/v1",Active,A(effect),A(request),A(request_input),
H(effect_scope_commitment)]`.

`InertVenueTransitionProof` is the exact current 25-member source projection, including the two
book commitments omitted by superseded contract 07:

```text
["m2.venue.ProtectionTransitionProof/v1",PositionScope,
 ProtectionTransitionCursor,ProtectionTransitionCursor,VenueScope,VenueScope,
 H(predecessor_book),H(book),H(predecessor_execution),H(execution),
 VenueExecutionCheckpoint,VenueExecutionCheckpoint,SymbolAuthoritySummary,
 SymbolAuthoritySummary,VenueExecutionBinding|N,VenueExecutionBinding|N,
 B(predecessor_binding_matches),B(binding_matches),B(predecessor_reconciliation_clear),
 B(reconciliation_clear),H(command),["m1.venue.VenueRecoveryDisposition",value],Z(delta),
 ["m1.venue.ProtectionTransitionSourceKind",value],H(source_binding)]
```

The cursor is exactly `["m2.venue.ProtectionTransitionCursor/v1",I(ordinal),H(head),
A(mandate)|N,H(execution)|N,VenueExecutionCheckpoint|N]`; the last pair is wholly present/null.
The summary is exactly tag plus four counts, three count-bearing ordered tuples of effect/leg
atoms, waiting-parent count, and unknown-buy count (10 members). Tuple order is source order;
duplicates fail.

At projection each source proof must be exact `_ProtectionTransitionProof`, have authentic
lineage, match its retained source commitment, and field-equal the inert projection. Current
summary fields must equal the summary re-derived from the selected current candidate. Predecessor
summary/book fields remain authenticated source provenance only. Load never allocates the source
proof, cursor, summary, bootstrap record, or venue book.

## 5. Complete authority and acquisition wire

The authority top row is the 14-member form:

```text
["m2.authority.Checkpoint/v1",["m1.authority.EnginePhase",value],
 ["m1.authority.TradingMode",value],["m1.authority.SupervisorFence",value],B(kill),
 A(session)|N,["m2.authority.RequestBudget/v1",I(remaining),I(reserve)],VenueRef,
 EmergencyGrant|N,CurrentEffectRows,ManualFlattenRows,AcquisitionDescriptorRows,
 AcquisitionSlotRows,H(checkpoint_commitment)]
```

Current effects, claims, manual rows, emergency grant, currentness, and permits retain their exact
contract-07 section-4.2 arrays with literal enum owners. `AcquisitionDescriptorRows =
C("m2.authority.AcquisitionDescriptors/v1",rows)` is effect-ID keyed; each row is
`["m2.authority.AcquisitionDescriptor/v1",A(effect_id),AcquisitionEffectPermit]`.

Each slot is `["m2.authority.AcquisitionSlot/v1",PositionScope,AcquisitionCurrentness,SlotValue]`.
`SlotValue` is exactly one of:

```text
["m2.authority.AcquisitionSlotEmpty/v1"]
["m2.authority.AcquisitionSlotActive/v1",A(effect),H(descriptor_commitment)]
["m2.authority.AcquisitionSlotInactive/v1",A(predecessor_effect),
 H(predecessor_descriptor_commitment),A(successor_generation)]
```

Active/inactive references resolve to exactly one descriptor row with matching permit/scope and
re-derived source commitments. Descriptor rows are exactly those referenced by a retained slot or
selected unresolved predecessor effect; missing, extra, mixed, or commitment-only descriptors
fail. This preserves the bounded domain of `_acquisition_descriptor_by_effect`.

Acquisition is exactly contract 09 section 6. Its bounded registry/lineage/state commitments are
payload-integrity domains only and never equal history-shaped serving commitments.

## 6. Source-order authority

At projection, effect order is the authentic `VenueRecoveryBook._effect_order` restricted to the
selected effect identity set; owner order is authentic `_owner_order` restricted to selected owner
identity set. Each selected set must equal its wire identity set. Assign dense unique `0..n-1`
ordinals by those source positions; wire rows remain identity-key sorted and carry the ordinals.

Effect source order must also have strictly increasing selected `VenueEffectRecord.created_ordinal`.
Every owner must equal one selected `VenueIdentityOwnerRecord` on scope/profile/owner/observation/
effect/root/generation/late-admission fields. The repository corroborates identity and effect
creation order; it does not replace owner-only order. Missing, extra, duplicate, tied, regressing,
or multiply matching rows fail.

Contradiction ordinal is the exact positive selected `AcceptanceEvidenceRecord.evidence_ordinal`;
it is not densified. Contradictions are increasing by ordinal with unique `(owner,observation)` and
exact effect/owner/observation equality. Reducer-semantic orders are reconstructed only from these
ordinals. Derived current authority summaries must equal the candidate's current summaries.

## 7. Exact persistence records and API

`persistence/records.py` adds these public frozen/slotted records in field order:

```python
class RuntimeCheckpointPayloadRecord:
    application_generation_id: ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    currentness_head_ordinal: int
    checkpoint_version_ordinal: int
    payload_bytes: bytes
    payload_length: int
    payload_sha256: str

class RuntimeCheckpointSelectionRequest:
    application_generation_id: ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    expected_checkpoint: KernelCheckpointRecord | None
    target_currentness_head_ordinal: int
    target_checkpoint_version_ordinal: int

class RuntimeCheckpointLoadRequest:
    application_generation_id: ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str

class RuntimeCheckpointSelectionProof:       # init=False
    request: RuntimeCheckpointSelectionRequest
    application_generation: ApplicationGenerationRecord
    execution_profile: ExecutionConnectionProfile
    market_source_profile: MarketDataSourceProfile
    predecessor_checkpoint: KernelCheckpointRecord | None
    selection_commitment: bytes
    _selection: _RuntimeCheckpointSelectionSet
    _binding: bytes
    _issuer: object

class RuntimeCheckpointWriteReceipt:         # init=False
    payload: RuntimeCheckpointPayloadRecord
    predecessor_checkpoint: KernelCheckpointRecord | None
    resulting_checkpoint: KernelCheckpointRecord
    selection_commitment: bytes
    _binding: bytes
    _issuer: object
```

`_RuntimeCheckpointSelectionSet` fields are tuples, in this order: scopes, controllers,
protection authorities, generations, generation-current rows, streams, cursors, effects, claims,
owners, acceptance sets, evidence, closure heads, root routes, roots, fact heads, current facts,
then absences and query-row-counts. `_RuntimeCheckpointAbsence` is `(family: str,
canonical_key: bytes)`. Explicit absence families are claim/effect, acceptance/effect,
evidence/set, owner/effect, closure/owner, route/owner, fact-head/root, current-fact/root,
stream/generation, and cursor/stream.

Constructor-hidden proof/receipt classes reject subclassing. Payload records validate exact types,
positive length, exact byte length, digest text, and digest equality. Requests require canonical
profiles, non-negative target head, positive target version, and either: absent predecessor plus
target version 1; or exact predecessor plus target version predecessor+1 and target head greater
than or equal to predecessor head.

The exact public additions are:

```python
# checkpoint_codec.py
encode_runtime_checkpoint(envelope: RuntimeCheckpointEnvelope) -> bytes

# repository.py
select_runtime_checkpoint(connection, request)
    -> RepositoryOutcome[RuntimeCheckpointSelectionProof]
store_runtime_checkpoint(connection, proof, envelope, *, capability)
    -> RepositoryOutcome[RuntimeCheckpointWriteReceipt]
load_runtime_checkpoint_payload(connection, application_generation_id,
    currentness_head_ordinal, checkpoint_version_ordinal, payload_sha256)
    -> RepositoryOutcome[RuntimeCheckpointPayloadRecord]
load_runtime_checkpoint(connection, request)
    -> RepositoryOutcome[RuntimeCheckpointEnvelope]
```

The private projector is
`_project_runtime_checkpoint(selection_proof, venue: VenueRecoveryBook, authority:
ExecutionAuthorityState, scope_owners: tuple[_RuntimeCheckpointScopeOwners,...])`, where each scope
owner tuple is exact `(scope_id, AcquisitionControllerState, ExecutionSnapshot,
PositionProtectionState)`. It authenticates the proof and owners, proves exact scope-set equality,
point-validates durable references, creates only inert carriers, canonicalizes immediately, and
issues a `PROJECTED` envelope.

Outcome and exception sets are closed. `select_runtime_checkpoint` returns `FOUND`, `ABSENT`
(application absent), `CONFLICT` (profile or expected predecessor differs), or
`INTEGRITY_FAILURE`; it never returns `APPLIED`. `store_runtime_checkpoint` returns `APPLIED`,
`CONFLICT` (predecessor/payload identity/CAS conflict), or `INTEGRITY_FAILURE`; it never returns
`FOUND`. Both load methods return `FOUND`, `ABSENT`, `CONFLICT` (only a changed head during composed
load), or `INTEGRITY_FAILURE`. Repository methods convert SQLite integrity errors to these exact
outcomes and never leak partial records. `encode_runtime_checkpoint` raises `TypeError` for a
non-exact envelope, `ValueError` for issuer/binding/canonical failure, and `OverflowError` only for
a refusal limit.

`records.__all__` adds only the five named records. `checkpoint_codec.__all__` is exactly
`InertRuntimeCheckpointComponent`, `RuntimeCheckpointEnvelope`,
`RuntimeCheckpointScopeCandidate`, `encode_runtime_checkpoint`; repository adds only the four
methods above. None is root-exported. Private selection, absence, projector, decoder, proof issuer,
load proof, CAS SQL, and sentinels remain private.

Binding domains are exactly `execution-core/runtime-checkpoint/{selection-request,selection-set,
selection-proof,component,scope-candidate,projected-envelope,load-proof,loaded-envelope,
write-receipt}/v1`, one literal domain per value. Distinct private sentinels exist for selection,
projected, loaded, load-proof, and receipt issuance. Selection binds every request, predecessor,
selected record, count, and absence; projected envelopes bind selection plus owner commitments and
bytes; loaded envelopes bind load proof plus bytes/digest.

## 8. Fixed query manifest

All query text is a module constant with `?` parameters. Fixed repository column constants may be
interpolated only at import time; runtime identifiers, caller `IN` lists, fallback SQL, and per-row
repository calls are forbidden. Every variable query uses `LIMIT 65536`; 65,536 means overflow.
Scope query uses `LIMIT 4097`. Overflow is refusal, never truncation.

The exact record column vectors are the dataclass field order already frozen in `records.py`.
Joined queries prepend an exact `0|1` presence integer to each nullable record vector. Zero requires
all-null; one requires a complete exact record. Tuple-length/storage-class mismatch is integrity
failure.

The common generation CTE is:

```sql
WITH selected_scope(scope_id) AS MATERIALIZED (
 SELECT scope_id FROM acquisition_scope
 WHERE application_generation_id=? AND execution_profile_id=?
), selected_generation(acquisition_generation_id,scope_id) AS MATERIALIZED (
 SELECT g.acquisition_generation_id,g.scope_id
 FROM selected_scope s JOIN symbol_controller c ON c.scope_id=s.scope_id
 JOIN acquisition_generation g ON g.acquisition_generation_id=c.live_acquisition_generation_id
 JOIN acquisition_generation_current gc
   ON gc.acquisition_generation_id=g.acquisition_generation_id AND gc.scope_id=g.scope_id
 WHERE c.live_acquisition_generation_id IS NOT NULL AND g.status='LIVE'
 UNION
 SELECT gc.acquisition_generation_id,gc.scope_id
 FROM selected_scope s JOIN acquisition_generation_current gc
   INDEXED BY ix_acquisition_generation_current_checkpoint_unresolved
   ON gc.scope_id=s.scope_id
 JOIN acquisition_generation g
   ON g.acquisition_generation_id=gc.acquisition_generation_id AND g.scope_id=gc.scope_id
 WHERE (gc.unresolved_effect_count>0 OR gc.active_protection_count>0)
   AND g.status='RETIRED_UNSERVING'
), qualifying_effect(effect_id) AS MATERIALIZED (
 SELECT e.effect_id FROM selected_generation g JOIN venue_effect e
   INDEXED BY ix_venue_effect_generation_disposition
   ON e.acquisition_generation_id=g.acquisition_generation_id
  AND e.disposition IN ('OPEN','INVALIDATED')
 UNION
 SELECT e.effect_id FROM selected_generation g JOIN venue_identity_owner o
   INDEXED BY ix_venue_owner_checkpoint_late
   ON o.owner_generation_id=g.acquisition_generation_id
  AND o.admitted_after_effect_closed=1
 JOIN venue_effect e ON e.effect_id=o.effect_id AND e.scope_id=g.scope_id
  AND e.acquisition_generation_id=g.acquisition_generation_id
 WHERE e.disposition='CLOSED'
)
```

The successful selection executes exactly 11 SELECT statements:

| Query | Exact root/result/order |
| --- | --- |
| Q1 | exact application ID joins exact selected execution/market profiles and left-joins predecessor kernel head; application/profile records plus explicit head presence; cardinality 0/1 |
| Q2 | application/profile scopes left-join controller and protection; scope/controller/protection vectors; `ORDER BY scope_id LIMIT 4097`; missing required current rows refuses |
| Q3 | `selected_generation` joins generation/current; generation/current vectors; `ORDER BY scope_id,successor_ordinal,generation_id LIMIT 65536` |
| Q4 | `qualifying_effect` joins effect; `VenueEffectRecord`; `ORDER BY created_ordinal,effect_id LIMIT 65536` |
| Q5 | qualifying effects left-join owners; effect ID plus owner presence/vector; `ORDER BY effect_id,owner_external,observation_external LIMIT 65536` |
| Q6a | qualifying effects left-join claims; effect ID plus claim presence/vector; `ORDER BY effect_id LIMIT 65536` |
| Q6b | qualifying effects left-join acceptance sets; effect ID plus set presence/vector; `ORDER BY effect_id LIMIT 65536` |
| Q6c | qualifying sets left-join all evidence using `ix_acceptance_evidence_set`; set ID plus evidence presence/vector; `ORDER BY effect_id,evidence_ordinal,evidence_id LIMIT 65536` |
| Q7 | selected owners left-join the single closure head using `ix_closure_chain_head`; owner key plus head presence/vector; `ORDER BY effect_id,owner_external LIMIT 65536` |
| Q8 | selected owners left-join root route by exact effect/owner/observation, then required root and optional fact head/current fact; owner key plus presence and record vectors; `ORDER BY effect_id,owner_external,root_fill_key_id LIMIT 65536` |
| Q9 | selected generations left-join stream authority then cursor; generation ID plus presence and record vectors; `ORDER BY generation_id,stream_generation_id LIMIT 65536` |

Each left-join parent produces exactly one absence marker when it has no child; many-child families
produce one row per child and no absence row. Complementary found/absence vectors must partition
the complete parent key vector. Q4 independently rechecks
`disposition!='CLOSED' OR selected late owner exists`. Q8 selects only roots reachable from
selected standing owners, not every historical root in a selected generation. Q9 requires the
payload stream-generation set to equal the selected rows/absences.

Load runs exact current-head lookup, exact payload lookup by all four identity coordinates, Q1-Q9,
private decode/proof issuance, then the identical head lookup. Including Q6a-c, selection is 11
fixed queries and successful load is 14 fixed SELECTs. Initial/final application, head, digest,
version, and both profile coordinates must match.

## 9. Static index and CAS candidate

Static DDL adds exactly:

```sql
CREATE INDEX ix_acquisition_scope_checkpoint
ON acquisition_scope (application_generation_id, execution_profile_id, scope_id);

CREATE INDEX ix_acquisition_generation_current_checkpoint_unresolved
ON acquisition_generation_current (scope_id, acquisition_generation_id)
WHERE unresolved_effect_count > 0 OR active_protection_count > 0;

CREATE INDEX ix_venue_owner_checkpoint_late
ON venue_identity_owner (owner_generation_id, effect_id, owner_external)
WHERE admitted_after_effect_closed = 1;

CREATE INDEX ix_market_stream_authority_checkpoint_generation
ON market_stream_authority (acquisition_generation_id, scope_id, stream_generation_id);
```

R1's effect index is deleted as redundant; Q4 uses existing
`ix_venue_effect_generation_disposition`. These statements are static design only. Changed DDL
execution remains held for Ameen's exact commit/tree/digest/byte-count/test approval.

Store authenticates capability, proof, and a `PROJECTED` envelope bound to that proof; derives the
payload record; rereads the predecessor; inserts payload; then uses exactly one branch:

```sql
INSERT INTO kernel_checkpoint(application_generation_id,currentness_head_ordinal,
 checkpoint_sha256,checkpoint_version_ordinal)
SELECT ?,?,?,? WHERE NOT EXISTS (
 SELECT 1 FROM kernel_checkpoint WHERE application_generation_id=?)
```

for an absent predecessor, or:

```sql
UPDATE kernel_checkpoint SET currentness_head_ordinal=?,checkpoint_sha256=?,
 checkpoint_version_ordinal=?
WHERE application_generation_id=? AND currentness_head_ordinal=?
 AND checkpoint_sha256=? AND checkpoint_version_ordinal=?
```

for a found predecessor. Parameter order is statement column order, then the exact predecessor
record order. Exactly one affected row succeeds; zero is `CONFLICT`. It rereads and verifies the
result. No UPSERT or transaction control exists. Caller rollback is mandatory after any non-
`APPLIED` result so an inserted but unheaded payload cannot commit.

## 10. Finite failure-capable matrix

The exact named tests/mutants are:

| ID | Test | Mutant killed |
| --- | --- | --- |
| C01 | `test_runtime_checkpoint_literal_key_octets_and_composite_frames` | swap octet; remove count/length |
| C02 | `test_runtime_checkpoint_scalar_and_size_boundaries` | bool as int; off-by-one; skip parent size |
| C03 | `test_runtime_checkpoint_enum_tags_and_canonical_reencode` | alias owner; skip byte compare |
| A01 | `test_selection_proof_binding_covers_literal_coordinate_cases` | omit each request/predecessor/selection/count/absence |
| A02 | `test_projected_envelope_rejects_object_new_and_setattr_forgery` | omit issuer/binding |
| A03 | `test_loaded_envelope_cannot_be_stored_as_projected` | merge provenance issuers |
| I01 | `test_execution_and_protection_decode_to_exact_inert_components` | call either serving decoder/constructor |
| I02 | `test_bootstrap_rows_preserve_every_proof_cursor_summary_member` | omit each nested member/book commitment |
| I03 | `test_authority_descriptors_preserve_active_and_inactive_permits` | remove descriptor map/resolve check |
| I04 | `test_effect_owner_and_contradiction_source_order` | identity sort; gap/tie/inversion; dense contradiction |
| Q01 | `test_checkpoint_query_manifest_is_literal_and_count_bounded` | dynamic SQL/per-row/fallback/cap removal |
| Q02 | `test_checkpoint_selection_discovers_unresolved_retired_generation` | remove partial root/index |
| Q03 | `test_checkpoint_selection_includes_closed_effect_with_late_owner` | omit CLOSED union/effect |
| Q04 | `test_checkpoint_selection_absence_vectors_partition_parent_sets` | inner join; false/missing absence |
| Q05 | `test_checkpoint_query_plans_are_index_searches_under_unrelated_history` | remove each required index; accept SCAN |
| W01 | `test_checkpoint_store_requires_matching_projected_envelope_and_proof` | forged/spliced payload/proof |
| W02 | `test_checkpoint_store_cas_compares_every_predecessor_coordinate` | omit each CAS predicate/absence check |
| W03 | `test_checkpoint_store_faults_are_old_complete_or_new_complete` | caller commits non-APPLIED/partial write |
| W04 | `test_checkpoint_repository_never_controls_transaction` | BEGIN/COMMIT/ROLLBACK/SAVEPOINT |
| L01 | `test_checkpoint_load_rechecks_every_head_and_profile_coordinate` | omit final read/comparison |
| L02 | `test_checkpoint_load_rejects_digest_length_canonical_and_selection_splice` | omit each integrity gate |
| X01 | `test_runtime_checkpoint_exports_are_exact` | extra/missing export |
| X02 | `test_runtime_checkpoint_has_no_serving_constructor_or_second_engine` | serving factory/reducer/root export |
| X03 | `test_runtime_checkpoint_sql_exists_only_in_repository` | SQL outside repository |

`A01`, `W02`, and `L01` use literal case tables, not reflection. Pure C01-C03, A01-A03, I01-I04,
W01-W02, L02, and X01-X03 run before the DDL gate. Q01-Q05, W03-W04, and L01 are the named fresh
`tmp_path` file-database tests held behind Ameen's changed-DDL approval. Every test has a committed
RED method: missing symbol for new surface, one named source mutation for each listed mutant, or
pre-existing behavior assertion for no-change constraints. GREEN must fail if the asserted
exception is broadened to arbitrary `Exception`.

## 11. Held serving boundary

WO-0169 remains solely responsible for owner lock, a fresh current-head check, cold/startup fence,
private serving constructors, repository omitted-history replay/nonmembership, and atomic bounded
behavioral-commitment cutover across every acquisition consumer. Until then, both `PROJECTED` and
`LOADED` envelopes are inert storage/inspection data and no runtime work may consume them.
