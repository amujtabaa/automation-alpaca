# WO-0168c frozen non-serving checkpoint contract — R4

Status: **SUPERSEDED BY R5 — EVIDENCE ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `05e5204`

## 1. Closed authority and precedence

R4 is the complete WO-0168c candidate. Its normative authority is this file plus
`14-WO-0168C-R4-SQL-MANIFEST.md`. The following predecessor bytes are imported only through the
named clauses below; their hashes make every import immutable:

| File | SHA-256 | Imported clauses |
| --- | --- | --- |
| `07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md` | `1a0c68ffcf0d6305560abe6e762116ac966639008d647e9c4e7241237adf03bd` | section 2.2 exact reused semantic arrays; section 2.3 literal enum spellings; section 3.3 exact named venue semantic rows; section 4.2 exact named authority rows; section 5.2 exact named acquisition rows |
| `10-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R2.md` | `767c1249c29e3235602a555a1d49022706022ed1c1ca4990b7f9d657ef3473e1` | section 2 canonical grammar; section 4 exact bootstrap rows; section 5 exact authority top/descriptor/slot rows; section 6 source-order authority |
| `11-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R3.md` | `ee31dda649c700438dc55642a91daee42dc6b2eac8634119ae159aea519fa3cb` | sections 2, 4-7 and 9, except every surface replaced below |
| `12-WO-0168C-R3-SQL-MANIFEST.md` | `f1cae0c9af8a6b906497864e03311158ecdfae2ff37a7f7cd23c59c542bbd069` | section 2 storage vectors and Q1/Q4b/Q5/Q6a/Q6b/Q6c/Q7/Q8/Q9 only, as amended by the R4 SQL manifest |

An imported clause imports its literal arrays, tags, enum members, ordering, limits, and validation
rules only. Cross-references from an imported clause are not transitively imported unless named in
this table. The following predecessor claims are explicitly excluded: serving/owner/proof
construction; standalone R13-H scope; old top-level payload rows; witness rows; old selection or
history-completeness rules; target coordinates in a request; sentinel fields; twelve-query counts;
Q2/Q3/Q4a SQL; old plan/sort expectations; old CAS/API/export/outcome/binding text; and every
superseded test matrix. If text conflicts, R4 wins, then the R4 SQL manifest, then a named import.
No conversation or unnamed predecessor prose is authority.

## 2. Frozen non-serving payload

The canonical outer payload is exactly ten members:

```text
[1,"m2.runtime-checkpoint/v1",A(application_generation_id),
 H(execution_profile_id),H(market_source_profile_id),I(currentness_head_ordinal),
 I(checkpoint_version_ordinal),VenueCandidate,AuthorityCandidate,ScopeCandidates]

ScopeCandidates = C("m2.runtime-checkpoint.scopes/v1",rows)
ScopeRow = ["m2.runtime-checkpoint.scope/v1",I(scope_id),PositionScope,
 AcquisitionCandidate,ExecutionComponent,ProtectionComponent]
```

Scope rows are strictly increasing by non-negative integer `scope_id`, unique, complete for the
selected scope set, and capped at 4,096. ExecutionComponent is the exact 21-member
`m2.position.execution-state/v1` row and ProtectionComponent is the exact 32-member
`m2.protection.checkpoint/v1` row frozen in R3 section 2. Venue/bootstrap, authority/acquisition,
source-order, scalar frames, semantic arrays, and enum spellings are only the exact named imports
in section 1. No R4 decoder constructs a serving owner, proof, reducer, or startup capability.

Database-complete and payload-owned families, repository-derived target head/version, static DDL,
store-time full reselection, caller-owned transaction rule, load revalidation, and held WO-0168b/
WO-0169 obligations are exactly R3 sections 4-7 and 9, subject to the corrected surfaces below.

## 3. Exact public and private type surface

All listed dataclasses are frozen, slotted, exact-type, non-subclassable where constructor-hidden,
and validate every field. No `_issuer` or copyable sentinel field exists.

`records.py` adds exactly these public records in this field order:

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

class RuntimeCheckpointLoadRequest:
    application_generation_id: ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str

class RuntimeCheckpointSelectionProof:  # init=False
    request: RuntimeCheckpointSelectionRequest
    application_generation: ApplicationGenerationRecord
    execution_profile: ExecutionConnectionProfile
    market_source_profile: MarketDataSourceProfile
    predecessor_checkpoint: KernelCheckpointRecord | None
    target_currentness_head_ordinal: int
    target_checkpoint_version_ordinal: int
    selection_commitment: bytes
    _selection: _RuntimeCheckpointSelectionSet
    _binding: bytes

class RuntimeCheckpointWriteReceipt:  # init=False
    payload: RuntimeCheckpointPayloadRecord
    predecessor_checkpoint: KernelCheckpointRecord | None
    resulting_checkpoint: KernelCheckpointRecord
    selection_commitment: bytes
    _binding: bytes
```

`checkpoint_codec.py` adds exactly:

```python
class InertRuntimeCheckpointComponent:  # init=False
    tag: str
    canonical_bytes: bytes
    commitment_sha256: str
    _binding: bytes

class RuntimeCheckpointScopeCandidate:  # init=False
    scope_id: int
    position_scope: InertRuntimeCheckpointComponent
    acquisition: InertRuntimeCheckpointComponent
    execution: InertRuntimeCheckpointComponent
    protection: InertRuntimeCheckpointComponent
    _binding: bytes

class RuntimeCheckpointEnvelope:  # init=False
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
    _provenance: str  # exactly PROJECTED or LOADED
    _selection_binding: bytes
    _binding: bytes
```

The private `_RuntimeCheckpointSelectionSet` has tuples in this exact order: scopes, controllers,
protection authorities, LIVE generations, LIVE generation-current rows, unresolved generations,
unresolved generation-current rows, effects, owners, claims, acceptance sets, evidence, closure
heads, root routes, roots, fact heads, current facts, streams, cursors, ten absence vectors, and
thirteen query row counts. Each absence is `(family: str, canonical_key: bytes)`. The ten families
are `owner/effect`, `claim/effect`, `acceptance/effect`, `evidence/acceptance`, `closure/owner`,
`route/owner`, `fact-head/root`, `current-fact/root`, `stream/generation`, `cursor/stream` in that
literal order. Every tuple is canonical-key ordered and duplicate-free.

Private parser-local values for venue transition, bootstrap, execution, and protection rows are
not object fields and carry no independent authenticity claim. They are parsed, validated,
re-encoded, and discarded while the registered component retains the exact canonical bytes.

## 4. Exact APIs, exports, outcomes, and exceptions

```python
# checkpoint_codec.py
encode_runtime_checkpoint(envelope: RuntimeCheckpointEnvelope) -> bytes

# repository.py
select_runtime_checkpoint(connection, request: RuntimeCheckpointSelectionRequest)
    -> RepositoryOutcome[RuntimeCheckpointSelectionProof]
store_runtime_checkpoint(connection, proof: RuntimeCheckpointSelectionProof,
    envelope: RuntimeCheckpointEnvelope, *, capability)
    -> RepositoryOutcome[RuntimeCheckpointWriteReceipt]
load_runtime_checkpoint_payload(connection, application_generation_id,
    currentness_head_ordinal, checkpoint_version_ordinal, payload_sha256)
    -> RepositoryOutcome[RuntimeCheckpointPayloadRecord]
load_runtime_checkpoint(connection, request: RuntimeCheckpointLoadRequest)
    -> RepositoryOutcome[RuntimeCheckpointEnvelope]
```

The private projector signature is exactly:

```python
_project_runtime_checkpoint(selection_proof, venue: VenueRecoveryBook,
    authority: ExecutionAuthorityState,
    scope_owners: tuple[_RuntimeCheckpointScopeOwners, ...])
```

Each private scope-owner value contains exactly `(scope_id, AcquisitionControllerState,
ExecutionSnapshot, PositionProtectionState)`.

- selection returns only `FOUND`, `ABSENT` for absent application, `CONFLICT` for profile or
  expected-predecessor mismatch, or `INTEGRITY_FAILURE`;
- store returns only `APPLIED`, `CONFLICT` for stale/identity/CAS conflict, or
  `INTEGRITY_FAILURE`;
- payload load returns only `FOUND`, `ABSENT`, or `INTEGRITY_FAILURE`;
- composed load returns only `FOUND`, `ABSENT`, `CONFLICT` for a changed head/profile across the
  composed load, or `INTEGRITY_FAILURE`.

SQLite integrity exceptions are translated to the listed outcome and never carry a partial
record. `encode_runtime_checkpoint` raises `TypeError` for a non-exact envelope, `ValueError` for
authenticity/binding/canonical failure, and `OverflowError` only for a contract limit. No API
controls a transaction.

`records.__all__` adds only the five record names above. `checkpoint_codec.__all__` is exactly
`("InertRuntimeCheckpointComponent", "RuntimeCheckpointEnvelope",
"RuntimeCheckpointScopeCandidate", "encode_runtime_checkpoint")`. `repository.__all__` adds only
the four repository functions above to its pre-candidate exact export tuple. None is exported from
`execution_core` or `persistence` package roots. Registry, projector, decoder, binding helpers,
selection/load proof issuers, SQL, and CAS constants remain private.

## 5. Non-copyable issuance and byte-exact bindings

Each constructor-hidden public proof/component/scope/envelope/receipt is registered after
construction under a module-private `RLock`:

```text
registry[id(value)] = (weakref.ref(value, cleanup), exact_binding, literal_provenance)
```

Authenticity requires an entry, the retained weak reference to resolve to the same object by `is`,
stored binding equality with fresh re-derivation, and exact provenance. Cleanup deletes only when
the retained weakref object is the callback argument. Registries, locks, and registration/lookup
functions are private. Copy, `object.__new__`, `object.__setattr__`, copied binding, recomputed
unkeyed hash, and reused object ID cannot issue a value.

All binding bytes use these literal primitives; no `repr`, reflection, platform encoding, JSON,
or delimiter concatenation is permitted:

```text
PACK(domain, parts...) = uint32be(len(domain)) || domain ||
                         each(uint64be(len(part)) || part)
COMMIT(domain, parts...) = SHA256(PACK(domain, parts...))
INT(v) = sign-octet(00 nonnegative, 01 negative) ||
         uint32be(len(minimal-big-endian(abs(v), at least one octet))) || magnitude
TEXT(v) = uint64be(len(utf8(v))) || utf8(v)
BYTES(v) = uint64be(len(v)) || v
BOOL(v) = 00 for false, 01 for true
NONE = COMMIT("execution-core/runtime-checkpoint/optional/absent/v1")
SOME(x) = COMMIT("execution-core/runtime-checkpoint/optional/present/v1", x)
SEQ(items) = COMMIT("execution-core/runtime-checkpoint/sequence/v1", INT(count), *items)
```

Domains are ASCII bytes. The nine top-level domains are exactly:

```text
execution-core/runtime-checkpoint/selection-request/v1
execution-core/runtime-checkpoint/selection-set/v1
execution-core/runtime-checkpoint/selection-proof/v1
execution-core/runtime-checkpoint/component/v1
execution-core/runtime-checkpoint/scope-candidate/v1
execution-core/runtime-checkpoint/projected-envelope/v1
execution-core/runtime-checkpoint/load-proof/v1
execution-core/runtime-checkpoint/loaded-envelope/v1
execution-core/runtime-checkpoint/write-receipt/v1
```

Each scalar field is first committed under the exact field domains
`execution-core/runtime-checkpoint/field/{absent,bool,int,text,bytes,m1-value}/v1`. M1 values use
their WO-0165 durable atom and then
`COMMIT("execution-core/runtime-checkpoint/field/m1-value/v1", atom-binding)`. Each repository
record is `COMMIT("execution-core/runtime-checkpoint/record/v1", TEXT(literal-record-tag),
INT(field-count), field-bindings...)`; literal record tags are the uppercase storage-vector names
from R3 SQL section 2 lowercased with underscores changed to hyphens and `/v1` appended. Fields are
the exact flattened vector order. Optional records use `NONE`/`SOME(record-binding)`.

Top-level parts, in exact order, are:

- selection request: application M1 binding, execution profile text, market profile text,
  optional expected HEAD binding;
- selection set: one `SEQ(record-bindings)` per exact field in section 3, then one
  `SEQ(COMMIT(absence/v1,TEXT(family),BYTES(key)))` per absence vector, then
  `SEQ(INT(count))` for thirteen counts;
- selection proof: request binding, application/execute-profile/market-profile record bindings,
  optional predecessor HEAD, target head INT, target version INT, selection-set binding;
- component: TEXT(tag), BYTES(canonical bytes), TEXT(lowercase SHA-256);
- scope: INT(scope ID), then position/acquisition/execution/protection component bindings;
- projected envelope: selection-proof binding, BYTES(venue owner commitment), BYTES(authority owner
  commitment), `SEQ` of scope rows `(INT(scope), acquisition/execution/protection source-owner
  commitments each encoded with BYTES)`, BYTES(payload), TEXT(payload digest);
- load proof: three request coordinates, initial HEAD binding, PAYLOAD binding, fresh selection-set
  binding;
- loaded envelope: load-proof binding, BYTES(payload), TEXT(payload digest);
- receipt: PAYLOAD binding, optional predecessor HEAD, resulting HEAD, selection commitment.

`selection_commitment` is exactly the 32-byte selection-set binding. Private `_binding` fields are
exactly their top-level COMMIT result. Provenance is registry metadata, not a caller field.

Known-answer tests independently implement PACK/INT/TEXT/BYTES and pin: empty-part PACK; INT values
`-1,0,1,255,256`; empty/non-ASCII TEXT; NONE; empty and two-item SEQ; a genesis selection request;
the same request with a HEAD; empty-scope selection set with all ten empty absences and thirteen
counts; one component; one scope; projected and loaded envelopes over the same bytes; and one
receipt. Each test contains literal expected packed hex or digest hex, not a call to production
helpers. Mutating one domain, sign, length, count, list order, optional marker, record tag, record
field, private field, query count, absence, provenance, owner commitment, payload byte, or digest
must change the known answer or fail authenticity.

## 6. Selection, write, and load invariants

Selection uses the thirteen exact queries in the R4 SQL manifest inside a caller-owned stable-read
transaction. The repository refuses selection/store/composed-load with `INTEGRITY_FAILURE` when
`connection.in_transaction` is false; it never starts that transaction. Q2 returns every selected scope
even when controller/protection is missing; either missing presence vector is
`INTEGRITY_FAILURE`. Q3a is capped before Q3b runs. Q3b is capped before any combined selected-
generation CTE runs. The two generation sets are duplicate-free, agree with their generation-
current rows, and may overlap only on exact identical `(generation_id, scope_id)` coordinates;
their canonical deduplicated union feeds Q4a-Q9.

Each scope has at most one LIVE generation equal to its controller. Protection active coordinates
are either wholly absent or equal that LIVE generation/stream. Sum of selected unresolved counters
is capped at 65,535 before Q4. Q4a and Q4b are independently capped; their unique effect union
equals that sum. Every later family is independently capped. Complements prove all ten absence
families without per-parent SQL.

Store authenticates the capability, proof, and `PROJECTED` envelope; reruns all thirteen selection
queries on the same connection; and requires complete proof equality before inserting payload.
It then uses the exact SQL and parameter order in section 7. A caller must roll back every
non-`APPLIED` outcome. WO-0168b owns the production transaction context and commit-ambiguity rule.

Load performs initial head, exact payload, all thirteen selection queries in the same caller-owned
stable-read transaction, bytes-only decode and
canonical re-encode, then final head/profile comparison. Successful load is exactly sixteen
SELECTs. It registers only a `LOADED` envelope, which store refuses.

## 7. Exact payload and head CAS

Payload insert columns and parameters are exact PAYLOAD storage-vector order:

```sql
INSERT INTO runtime_checkpoint_payload(
 application_generation_id,execution_profile_id,market_source_profile_id,
 currentness_head_ordinal,checkpoint_version_ordinal,payload_bytes,payload_length,payload_sha256)
VALUES (?,?,?,?,?,?,?,?)
```

For an absent predecessor:

```sql
INSERT INTO kernel_checkpoint(application_generation_id,currentness_head_ordinal,
 checkpoint_sha256,checkpoint_version_ordinal)
SELECT ?,?,?,? WHERE NOT EXISTS (
 SELECT 1 FROM kernel_checkpoint WHERE application_generation_id=?)
```

Parameters are resulting HEAD record order followed by the same application ID. For a found
predecessor:

```sql
UPDATE kernel_checkpoint SET currentness_head_ordinal=?,checkpoint_sha256=?,
 checkpoint_version_ordinal=?
WHERE application_generation_id=? AND currentness_head_ordinal=?
 AND checkpoint_sha256=? AND checkpoint_version_ordinal=?
```

Parameters are resulting head/currentness, digest, version, then predecessor HEAD record order.
Exactly one affected row followed by an exact reread succeeds. Zero rows is `CONFLICT`. No UPSERT,
REPLACE, dynamic SQL, transaction statement, or fallback write exists.

## 8. Final failure-capable matrix

| ID | Test | Named source mutant killed |
| --- | --- | --- |
| C01 | `test_runtime_checkpoint_wire_known_answers` | alter outer/scope member, tag, scalar frame, enum owner, or canonical byte comparison |
| C02 | `test_runtime_checkpoint_size_and_collection_boundaries` | change any limit or parent-before-child validation |
| B01 | `test_runtime_checkpoint_binding_known_answers` | alter PACK/INT/TEXT/BYTES/optional/SEQ/domain/field order |
| B02 | `test_runtime_checkpoint_identity_registry_rejects_forgery_and_id_reuse` | accept exact type/binding without live identical weakref registry entry |
| B03 | `test_runtime_checkpoint_binding_covers_every_private_and_semantic_field` | omit each listed request/set/proof/component/scope/envelope/load/receipt part |
| I01 | `test_checkpoint_projection_and_load_create_only_inert_values` | call serving decoder, owner/proof constructor, reducer, or root export |
| I02 | `test_checkpoint_nested_rows_preserve_all_members_and_source_order` | omit bootstrap/proof/cursor/summary/descriptor/slot/source ordinal |
| Q01 | `test_checkpoint_sql_and_storage_manifest_are_exact` | alter literal SQL/vector/count or introduce dynamic/per-row/fallback SQL |
| Q02 | `test_checkpoint_scope_presence_vectors_refuse_missing_controller_or_protection` | change either Q2 LEFT JOIN to INNER JOIN or skip presence refusal |
| Q03 | `test_checkpoint_generation_discovery_gates_before_union` | combine Q3a/Q3b before both cap checks or remove either LIMIT 65536 |
| Q04 | `test_checkpoint_qualifying_effect_counters_and_absences_partition` | alter effect union/counter equality or any complement partition |
| Q05 | `test_checkpoint_query_plans_are_direct_under_unrelated_history` | remove hard index or substitute the named weak-index/SCAN mutant |
| W01 | `test_checkpoint_store_requires_current_matching_projected_proof` | skip full reselection/binding/provenance comparison |
| W02 | `test_checkpoint_store_cas_compares_every_coordinate` | omit payload field, NOT EXISTS, predecessor predicate, or exact reread |
| W03 | `test_checkpoint_store_faults_are_old_complete_or_new_complete` | caller harness commits any non-APPLIED/partial path |
| W04 | `test_checkpoint_repository_requires_but_never_controls_transaction` | accept no transaction or add BEGIN/COMMIT/ROLLBACK/SAVEPOINT |
| L01 | `test_checkpoint_load_rechecks_head_profile_payload_and_selection` | omit initial/final coordinate or complete fresh selection |
| L02 | `test_checkpoint_load_rejects_digest_length_canonical_and_spliced_state` | omit digest/length/re-encode/proof comparison |
| X01 | `test_runtime_checkpoint_exports_are_exact` | add or remove any named export/root export |
| X02 | `test_runtime_checkpoint_has_no_serving_constructor_or_second_engine` | add serving factory, reducer, replay store, or alternate state authority |

Pure C01-C02, B01-B03, I01-I02, W01-W02, L02, X01-X02 run before the DDL gate without opening a
SQLite connection. Q01-Q05, W03-W04, and L01 are fresh `tmp_path` file-database tests held behind
Ameen's exact changed-DDL approval. Every test has its named source mutant above; arbitrary
`Exception` assertions fail review.

## 9. Human gate and successor boundary

R4 authorizes no source, test, DDL, SQLite, or serving action until REV-0077 returns `ACCEPT` with
`P0=0/P1=0` and the work order releases exact paths. Static DDL implementation may then proceed,
but no changed-DDL install or SQLite-bearing test may run until Ameen approves the exact candidate
commit/tree, DDL SHA-256/byte count, and named fresh-file plan.

WO-0168c remains non-serving. WO-0168b owns runtime transaction composition. WO-0169 alone owns
owner-locked serving conversion, omitted-history replay/nonmembership, fresh-head revalidation,
behavioral commitment cutover, and startup/cold fencing.
