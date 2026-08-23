# WO-0168a frozen operation, state, and persistence contract

Status: **PREFLIGHT REMEDIATION CANDIDATE — NO SOURCE AUTHORITY**

Date: 2026-08-22

Accepted predecessor: WO-0167 closeout
`0777fab62598f85ce189f40eb1a69319791282c2`, tree
`1db6fe831fc7d7785d032c224072b131cd5643e9`.

This record closes the contract gap found by `REV-0074/result.md`. The exact remediation commit and
tree are bound by `REV-0074/request-r1.md`; a later commit cannot inherit its verdict. Names below
are implementation contracts, not suggestions. Existing public M1 exports remain unchanged unless
an exact row below explicitly says otherwise.

## 1. Frozen architectural decision

M2 will not serialize `ExecutionSnapshot`, `VenueRecoveryBook`, `ExecutionAuthorityState`,
`GenerationRegistry`, or `AcquisitionLineageIndex` as Python objects. Those reference-model values
retain history-shaped indexes and cannot be a bounded restart representation.

WO-0168a instead introduces bounded, immutable M2 current-proof values and extracts the owning pure
transition calculation used by both routes:

1. the existing public in-memory reducer projects its opaque state to the exact bounded proof and
   calls the shared owning transition kernel; and
2. the future SQLite unit of work loads the same proof from direct current rows and calls the same
   kernel with an authenticated technical-dedupe fact.

There is one transition algorithm. A test-only reference route and a SQLite route may adapt inputs
and persistence, but neither may copy or independently reimplement a semantic branch. Public M1
entry points and dispositions remain compatibility ratchets.

## 2. Exact package-internal API

The following names live in `app/execution_core/persistence/operations.py` and form its complete
`__all__`:

```python
__all__ = (
    "AcquisitionOperationCoordinates",
    "AuthorityOperation",
    "BeginAcquisitionGenerationOperation",
    "BeginAcquisitionPreemptionOperation",
    "BrokerExecutionOperation",
    "ClaimAcquisitionEffectOperation",
    "CreateAcquisitionEffectOperation",
    "ExecutionOperationCoordinates",
    "InputDedupeFact",
    "InputDedupeKind",
    "M2Operation",
    "MarketOccurrenceOperation",
    "MarketOperationCoordinates",
    "OperationDomain",
    "VenueOperationCoordinates",
    "VenueRecoveryOperation",
    "decode_m2_operation",
    "encode_m2_operation",
)
```

Every class is an exact, frozen, slotted dataclass and rejects subclass instances. The type aliases
are literal unions, not protocols or caller-extensible registries.

### 2.1 Coordinate values

| Type | Exact ordered members |
| --- | --- |
| `ExecutionOperationCoordinates` | `application_generation_id: ApplicationGenerationId`; `execution_profile_id: str`; `scope_id: int` |
| `VenueOperationCoordinates` | the three execution members; `session_id: SessionId | None` |
| `AcquisitionOperationCoordinates` | the venue members; `acquisition_generation_id: AcquisitionGenerationId` |
| `MarketOperationCoordinates` | the acquisition members; `market_source_profile_id: str`; `stream_generation_id: MarketStreamGenerationId` |

Integers and strings require exact runtime scalar types; profile strings are nonblank canonical
identities already present in the accepted profile rows. Optional session is permitted only for a
venue observation whose owning public type has no session coordinate. Every authority,
acquisition, and market operation requires a non-null exact session matching current authority.

### 2.2 Technical input classification

`InputDedupeKind` is exactly `UNSEEN`, `EXACT_REPLAY`, or `IDENTITY_CONFLICT`.
`InputDedupeFact` has ordered members `kind`, `input_domain`, `input_identity_sha256`,
`payload_sha256`, and `retained_outcome_sha256: str | None`.

Only the repository creates this fact after an exact direct lookup. `EXACT_REPLAY` requires equal
domain, identity, coordinates, version, canonical payload bytes, and payload digest.
`IDENTITY_CONFLICT` means the exact domain/identity is retained with any unequal member. Reducers
never infer technical dedupe from their in-memory history maps on the SQLite path.

### 2.3 Admitted WO-0168b operation union

| Operation type | Exact ordered operation members | Exact payload union / identity |
| --- | --- | --- |
| `BrokerExecutionOperation` | `coordinates`; `fact` | `BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact`; identity is `fact.key` |
| `VenueRecoveryOperation` | `coordinates`; `item` | `RecordTransportOutcome | RecoverClaimedEffect | DiscoverVenueLeg | ObserveVenueStatus | IngestHumanAttestedFill | ReleaseVenueLeg | RecordBrokerFillEvidence | RecordBrokerRevisionEvidence`; identity is `item.input_id` |
| `AuthorityOperation` | `coordinates`; `command` | `CreateBrokerEffect | ClaimEffect | ClaimBrokerQuery | EngageKill | BeginManualFlatten | AdvanceManualFlatten`; identity is `command.input_id` |
| `BeginAcquisitionGenerationOperation` | `coordinates`; `input_id`; `successor_mandate` | `AuthorityInputId`; exact `AcquisitionMandate` |
| `CreateAcquisitionEffectOperation` | `coordinates`; `input_id`; `terms` | `AuthorityInputId`; exact `AcquisitionEffectTerms` |
| `ClaimAcquisitionEffectOperation` | `coordinates`; `input_id`; `effect_id`; `claim_occurrence_id` | exact M1 identities |
| `BeginAcquisitionPreemptionOperation` | `coordinates`; `input_id` | exact `AuthorityInputId` |
| `MarketOccurrenceOperation` | `coordinates`; `occurrence` | exact `MarketOccurrence`; identity is `occurrence.occurrence_id` |

`M2Operation` is the literal union of those eight operation classes. `OperationDomain` has exactly
the corresponding eight enum values. No generic callback, mapping, protocol, `Any`, arbitrary
dataclass, or plugin registration is admitted. Exact payload member order is the declaration order
at the accepted predecessor head; the operation codec uses an explicit encoder/decoder per exact
concrete payload type and never reflection.

The following current public inputs are deliberately **not** top-level durable operations:

- `RequestedEffect`, `RecordDispatchClaim`, `CancelBeforeDispatch`,
  `RecordPendingVenueOperation`, and `CloseAcceptanceSet` are authority-minted derivatives;
- `CatchUpExecutionRegistry` and `RegisterAcquisitionCurrentness` are execution/currentness
  derivatives;
- `CreateAcquisitionEffect`, `ClaimAcquisitionEffect`, `BeginAcquisitionPreemption`, and
  `CreateAcquisitionProtectionExit` from `authority.py` are sealed acquisition derivatives;
- `ProtectionVenueProjection`, `ProtectionTransition`, `AcquisitionContextRefresh`,
  `AcquisitionAdmissionProjection`, and `VenueRecoveryTransition` are reducer-minted proof;
- acquisition initialization is startup/bootstrap work owned by WO-0169; and
- market invalidation/rebase is a WO-0169 startup derivative, not caller input.

Passing any of those as a top-level operation, or passing a subclass/proxy, raises before a
transaction begins.

## 3. Finite operation-to-reducer-to-write matrix

Every row first performs the common sequence `C0..C9`:

`C0` exact operation/type validation; `C1` `BEGIN IMMEDIATE`; `C2` schema/profile/application/
scope/session verification; `C3` durable-input insert or direct dedupe classification; `C4` direct
current-proof load; `C5` shared pure transition; `C6` row writes in the frozen order below; `C7`
checkpoint payload/head; `C8` mandatory receipt plus terminal outcome; `C9` commit and only then
publish eligibility. `IDENTITY_CONFLICT` stops after C3 and writes no semantic/checkpoint/outbox
row. `EXACT_REPLAY` returns the retained outcome without invoking a reducer.

| Row | Owning public reducer / shared-kernel owner | Exact owner dispositions | Conditional semantic write order after C5 | Named derivatives |
| --- | --- | --- | --- | --- |
| O1 broker fact | `position.apply_broker_execution_fact` | `APPLIED`, `EXACT_REPLAY`, `FACT_CONFLICT`, `RECONCILIATION_REQUIRED` | root fill; execution fact/head; symbol controller; acquisition route/current; protection authority | venue execution-registry catch-up; acquisition fact reduction; protection venue reduction; acquisition protection rebase; optional protection exit/effect |
| O2 venue/recovery | `venue.apply_venue_recovery_input` | `APPLIED`, `EXACT_REPLAY`, `CONFLICT`, `RECONCILIATION_REQUIRED`, `REFUSED` | effect; owner; route; acceptance/evidence; closure; execution fact/head/root; controller/acquisition current; protection authority | position fact application when reducer emits canonical economics; acquisition reduction; protection reduction/rebase; optional protection exit/effect |
| O3 authority | `authority.apply_execution_authority_input` | `APPLIED`, `REFUSED`, `EXACT_REPLAY`, `CONFLICT` | effect; dispatch claim; acceptance/closure edge; controller/acquisition current; authority checkpoint members | internal venue authority bridges; protection/acquisition catch-up; outbox eligibility only for a committed exact claim |
| O4 begin generation | `acquisition.begin_acquisition_generation` | `APPLIED`, `EXACT_REPLAY`, `REFUSED` | acquisition generation/current; symbol controller; market stream/cursor; protection authority; acquisition checkpoint members | sealed currentness registration and neutral protection rebase |
| O5 create acquisition effect | `acquisition.create_acquisition_effect` | `APPLIED`, `EXACT_REPLAY`, `REFUSED` | venue effect; controller/acquisition current; acquisition/authority checkpoint members | sealed authority create and venue request |
| O6 claim acquisition effect | `acquisition.claim_acquisition_effect` | `APPLIED`, `EXACT_REPLAY`, `REFUSED` | dispatch claim; venue effect; controller/acquisition current; acquisition/authority checkpoint members | sealed authority claim and venue dispatch claim; outbox eligibility after commit |
| O7 begin preemption | `acquisition.begin_acquisition_preemption` | `APPLIED`, `EXACT_REPLAY`, `REFUSED` | effect/acceptance changes; protection authority; controller/acquisition current; acquisition/authority checkpoint members | sealed authority preemption; venue stand-down/cancel; protection catch-up; optional exit effect |
| O8 market occurrence | `protection.reduce_position_protection_market` | `APPLIED`, `EXACT_REPLAY`, `STALE`, `REFUSED` | market cursor; protection authority; controller/acquisition current | acquisition protection rebase; if a goal is emitted, sealed acquisition protection exit and its venue effect |

For each row, a disposition that produces no semantic state change still writes the immutable
durable input, mandatory receipt, terminal outcome, and—only if its exact checkpoint currentness
changes—checkpoint. A refused/conflict/replay receipt is explanatory and cannot advance any current
authority. Exact owner enum text and a domain tag are retained; a generic disposition never
silently translates owner semantics.

The write list is a closed superset. A row-specific implementation table in
`persistence/unit_of_work.py` names the exact repository calls in order; a ratchet test fails on
missing, extra, reordered, dynamically selected, or wildcard calls. A reducer output cannot select
an unlisted table family.

## 4. Complete state-member inventory and bounded substitute

### 4.1 Execution state

| Existing member | Classification | M2 representation |
| --- | --- | --- |
| `PositionState._scope`, `raw_quantity`, `basis_authority`, `cost_basis`, `basis_price_metadata`, `tail_fold_input`, `integrity_floor` | bounded current state | exact canonical checkpoint fields, cross-checked with controller/root current rows |
| `PositionState._root_fill_sequence`, `_effective_head_ids` | history-shaped | omitted; targeted `root_fill` plus `execution_fact_head` direct rows and aggregate quantity/head commitments supply the operation proof |
| `ExecutionSnapshot.integrity` and binding/currentness cursor | bounded current state | exact checkpoint fields plus controller/checkpoint coordinates |
| `ExecutionSnapshot.root_heads`, `seen_facts` | history-shaped maps | omitted; direct root/source-fact lookups plus immutable fact/head rows supply technical and semantic first-observation proof |

The package-internal owner types are `_M2ExecutionState` and `_M2ExecutionObservationProof` in
`position.py`; `_m2_execution_state_from_snapshot`, `_m2_execution_state_from_direct_proof`, and
`_m2_apply_broker_execution_fact` are the only construction/kernel seams. The existing public
reducer must delegate its economic classification to `_m2_apply_broker_execution_fact`.

### 4.2 Venue state

Every `VenueRecoveryBook` member is classified below; a name not listed is a preflight failure.

| Classification | Exact existing members | M2 representation |
| --- | --- | --- |
| fixed/current scalars | `scope`, `_account_authority_epoch`, `_unresolved_account_execution_reconciliation_count`, `execution_registry_count`, `execution_registry_commitment`, `_registry_transition_head_commitment` | checkpoint scalar fields, independently matched to direct controller/fact authority |
| current/active/unresolved maps | `_effect_by_id`, `_effect_by_request_occurrence`, `_effect_by_client_order`, `_authority_epoch_by_scope`, `_claim_by_effect`, `_claim_by_occurrence`, `_owner_by_leg`, `_acquisition_correlation_by_root`, `_leg_current_by_leg`, `_leg_summary_by_effect`, `_cancel_target_reservation_by_leg`, `_authority_contribution_by_effect`, `_authority_summary_by_scope`, `_account_unclaimed_requested_effect_ids`, `_reconciliation_count_by_effect`, `_closure_head_by_leg`, `_economic_high_water_by_leg`, `_human_coverage_by_root`, `_broker_coverage_by_root`, `_coverage_provenance_by_scope`, `_coverage_current_by_leg`, `_coverage_total_by_effect`, `_attributed_broker_root_count_by_scope`, `_human_interval_index`, `_human_broker_fact_index`, `_reconciliation_by_input`, `_unresolved_reconciliation_count_by_leg`, `_canonical_revision_count_by_leg`, `_execution_reconciliation_by_input`, `_unresolved_execution_reconciliation_count_by_scope`, `_binding_by_scope`, `_execution_snapshot_by_scope`, `_bootstrap_bound_target_by_scope`, `_protection_cursor_by_scope` | only records reachable from current/active/unresolved effects, current scopes, and the targeted input; loaded by exact keys from accepted rows plus checkpoint indexes; terminal history excluded |
| audit/order/history | `_effect_order`, `_contradiction_order_by_effect`, `_claim_order`, `_owner_order`, `_closure_ledger`, `_closure_by_id`, `_input_ledger`, `_input_by_id`, `_direct_input_by_semantic`, `_first_input_by_fact`, `_human_coverage_ledger`, `_broker_coverage_ledger`, `_reconciliation_ledger`, `_execution_reconciliation_ledger`, `_registry_transition_ledger`, `_binding_order`, `_protection_transition_ledger` | omitted from checkpoint; immutable table rows and durable input/outcome/receipt provide direct lookup/audit; none is replayed to serve |

Current maps are filtered, not copied wholesale. Their canonical payload includes a count and
lexicographically ordered identity references; each reference must resolve to one matching direct
row. The owner types/seams are `_M2VenueState`, `_M2VenueObservationProof`,
`_m2_venue_state_from_book`, `_m2_venue_state_from_direct_proof`, and `_m2_apply_venue_input` in
`venue.py`. Public `apply_venue_recovery_input` delegates the semantic branch to that kernel.

### 4.3 Authority state

| Existing member | Classification and M2 representation |
| --- | --- |
| `phase`, `mode`, `supervisor_fence`, `kill_engaged`, `session_id`, `budget`, `_emergency_grant` | bounded current state retained exactly in the checkpoint |
| `venue` | represented by the verified `_M2VenueState` reference and commitment, never nested arbitrary object bytes |
| `_effect_authority_by_id`, `_claim_by_effect`, `_claim_by_occurrence`, `_manual_by_id`, `_manual_flatten_by_scope`, `_acquisition_currentness_by_scope`, `_acquisition_descriptor_by_scope`, `_acquisition_descriptor_by_effect`, `_acquisition_active_by_scope` | active/unresolved entries only, ordered by canonical identity and resolved against current direct rows |
| `_input_by_id`, `_query_by_id`, `_consumed_grant_ids` | history-shaped; omitted and replaced by durable-input/outcome direct lookup; a currently live query/grant remains an active entry in the checkpoint |

The owner types/seams are `_M2AuthorityState`, `_M2AuthorityObservationProof`,
`_m2_authority_state_from_reference`, `_m2_authority_state_from_direct_proof`, and
`_m2_apply_execution_authority_input` in `authority.py`. Public
`apply_execution_authority_input` delegates its decision branches to that kernel.

### 4.4 Protection state

`PositionProtectionState` is fixed-size. The checkpoint retains every member exactly:
`policy`, `mandate`, `raw_quantity`, `execution_commitment`, `formula_available`,
`armed_hard_bail_trigger`, `activation_price`, `high_watermark`, `trail`,
`waiting_buy_resolution`, `commitment`, `_cursor_ordinal`, `_cursor_head`,
`_market_occurrence_epoch`, `_market_committed_epoch`, `_market_expected_epoch`,
`_market_source_sequence`, `_market_source_time`, `_market_evaluation_time`,
`_market_occurrence_identity`, `_market_halted`, `_market_baseline_required`,
`_market_exhausted`, `_market_last_primary`, `_hard_bid_identity`, `_hard_bid_source_time`,
`_trade_identity`, `_trade_source_time`, `_trail_bid_identity`, `_trail_bid_source_time`, and
`_exit_provenance`.

`_m2_position_protection_from_checkpoint` in `protection.py` is an exact validating constructor;
it re-derives and checks the owning commitment and the accepted `protection_authority` row. It may
use `object.__new__` internally only as the owning class's verified constructor, never as a generic
persistence decoder. The shared kernels are `_m2_reduce_position_protection`,
`_m2_reduce_position_protection_market`, and `_m2_invalidate_position_protection_market`; public
reducers delegate to them.

### 4.5 Acquisition state

| Existing member | Classification and M2 representation |
| --- | --- |
| `AcquisitionControllerState.application_generation_id`, `position_scope`, `scope_execution_commitment`, `venue_commitment`, `authority_context_commitment`, `protection_commitment`, `controller_commitment`, `commitment`, `_controller`, `_mandate`, `_seal` | bounded current state; exact checkpoint fields plus direct generation/controller/current rows; all commitments re-derived |
| `registry._records`, `registry._market_stream_routes`, `registry._seal` | history-shaped registry; only LIVE plus directly targeted retired generation and active stream route are loaded; all other generation lookups use direct rows |
| `lineage._request_routes`, `_effect_routes`, `_owner_routes`, `_root_routes`, `_fact_routes`, `_seal` | history-shaped indexes; only current/active/unresolved and targeted late-fact routes are loaded from exact direct rows |

The owner types/seams are `_M2AcquisitionState`, `_M2AcquisitionObservationProof`,
`_m2_acquisition_state_from_reference`, `_m2_acquisition_state_from_direct_proof`, and the shared
operation-specific kernels `_m2_begin_acquisition_generation`, `_m2_reduce_acquisition_controller`,
`_m2_rebase_acquisition_protection`, `_m2_create_acquisition_effect`,
`_m2_claim_acquisition_effect`, `_m2_begin_acquisition_preemption`, and
`_m2_create_acquisition_protection_exit` in `acquisition.py`. Existing public functions delegate.

### 4.6 Checkpoint envelope

`RuntimeCheckpointEnvelope` lives in `persistence/checkpoint_codec.py` and is the module's only
public data type. Its exact ordered members are:

1. `contract_version` (literal `1`);
2. `application_generation_id`;
3. `execution_profile_id`;
4. `market_source_profile_id`;
5. `currentness_head_ordinal`;
6. `checkpoint_version_ordinal`;
7. `authority_state`;
8. `scope_states` (tuple ordered by exact `scope_id`);
9. `active_or_unresolved_effect_refs` (tuple ordered by canonical effect identity);
10. `active_or_unresolved_route_refs` (tuple ordered by domain then canonical identity); and
11. `payload_sha256` (derived, never accepted as proof without bytes).

Each scope state holds the exact bounded execution, venue, acquisition, protection, and market
members classified above. Duplicate scope or reference identities, unordered tuples, unresolved
references, cross-profile/generation/session members, commitment mismatch, or a row not reachable
from current/active/unresolved state is refused.

## 5. Exact canonical byte contract

`encode_m2_operation`, `decode_m2_operation`, `encode_runtime_checkpoint`, and
`decode_runtime_checkpoint` use one type-specific canonical document grammar:

```text
document = ASCII("execution-core/m2-document/v1\n")
           || kind-octet
           || uint64-be(json-byte-length)
           || canonical-json-utf8
digest   = lowercase-hex(SHA256(document))
```

Kind octets are `0x01` operation, `0x02` checkpoint, `0x03` input outcome, `0x04` decision receipt,
and `0x05` outbox payload. Canonical JSON is emitted with UTF-8, `ensure_ascii=True`,
`allow_nan=False`, and separators `(',', ':')`. The top value is an array, never an object.
Integers are exact JSON integers; booleans are exact JSON booleans; absence is `null`; bytes are
lowercase even-length hex text; enums are `[qualified-owner-tag, value]`; M1 durable values are
`[contract_version, type_tag, ordered_fields]`; and every aggregate is a fixed-position array with
an exact type tag in position zero. Maps are forbidden. Sets are encoded as schema-owned sorted
tuples only.

Decode uses duplicate-free fixed arrays, exact type tags, explicit type-owned decoders, and owning
constructors. It re-encodes and byte-compares the result before returning. Unknown kind/version,
missing/extra/reordered values, noncanonical integer/text/hex/enum/atom, subclass, cross-coordinate
substitution, digest mismatch, or semantically unequal round trip fails. `pickle`, `marshal`,
`repr`, reflection over dataclass fields, dynamic import, and generic object construction are
forbidden and mutation-pinned.

## 6. Frozen schema and repository extension

WO-0168a authors one schema-v2 fresh-database candidate. It changes no existing accepted table or
trigger semantics except the schema version/catalog identity and adds exactly these families:

| Family | Required authority |
| --- | --- |
| `runtime_checkpoint_payload` | one exact canonical payload per `kernel_checkpoint` version; bytes, length, digest, version, application/profile binding |
| `durable_input` | immutable domain/identity/coordinates/version/payload bytes+digest and technical state `CLAIMED|TERMINAL|RECONCILIATION_PENDING` |
| `decision_receipt` | append-only receipt bytes+digest and exact input correlation; explanatory only |
| `durable_input_outcome` | one terminal owner-domain/disposition/result digest/checkpoint reference plus mandatory receipt FK |
| `broker_outbox` | immutable post-commit effect/dispatch-claim payload and committed sequence; no external-success state |

Required uniqueness, immutable-byte triggers, coordinate/profile FKs, monotonic checkpoint/outbox
ordinals, and no-update/no-delete rules are part of the DDL. An outcome cannot exist without its
receipt; a checkpoint head cannot advance without its exact payload; an outbox row cannot exist
without the exact immutable dispatch claim and matching effect/profile/generation. A receipt or
outbox row cannot be referenced as economic/currentness/owner/closure authority.

The DDL, records, and repository methods may be implemented and statically reviewed. No changed
DDL is installed and no SQLite-bearing test executes until Ameen approves the exact SHA-256, byte
length, candidate commit/tree, and named temporary-file test command. Any byte drift returns to
that gate.

Exact new record/repository surface:

- records: `RuntimeCheckpointPayloadRecord`, `DurableInputRecord`,
  `DecisionReceiptRecord`, `DurableInputOutcomeRecord`, `BrokerOutboxRecord`;
- repository: `store/load_runtime_checkpoint_payload`, `claim/load_durable_input`,
  `store/load_decision_receipt`, `store/load_durable_input_outcome`, and
  `store/load_broker_outbox`;
- all operations accept an explicit verified connection and a write capability where applicable;
  none begins, commits, rolls back, retries, discovers a path, or performs semantic reduction.

## 7. Runtime and setup write capabilities

`repository.py` defines two opaque package-private exact types:

- `_RuntimeWriteCapability`: constructed only by `_issue_runtime_write_capability` in
  `unit_of_work.py` after `BEGIN IMMEDIATE` and exact schema/application/profile verification. It is
  connection-identity-bound and transaction-bound. Every capital-relevant write refuses a missing,
  stale, wrong-connection, subclassed, or setup token.
- `_SetupWriteCapability`: constructed only by `_issue_setup_write_capability` for fresh temporary
  schema fixtures. A static allowlist permits calls only from the named persistence test support
  module and schema/repository tests. It is never imported by `app/` runtime composition.

The private constructors raise. Issuance uses an owning factory seal rather than caller data. This
is structural control, not a security claim against arbitrary hostile Python. Exact AST/import and
runtime proxy tests enumerate every repository mutator and kill alias, wrapper, cursor, and
subclass bypasses.

WO-0168a introduces the token requirement and fixture issuance. Because WO-0168b does not yet
exist, runtime issuance remains absent/unreachable until that order implements it.

## 8. Exact implementation scope and tests

After fresh preflight acceptance, WO-0168a activation may name only these source paths:

```yaml
source_paths:
  - app/execution_core/position.py
  - app/execution_core/venue.py
  - app/execution_core/recovery.py
  - app/execution_core/authority.py
  - app/execution_core/protection.py
  - app/execution_core/acquisition.py
  - app/execution_core/persistence/operations.py
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/persistence/records.py
  - app/execution_core/persistence/repository.py
  - app/execution_core/persistence/schema.py
```

Exact test paths:

```yaml
test_paths:
  - tests/execution_core/test_persistence_operations.py
  - tests/execution_core/test_persistence_checkpoint_codec.py
  - tests/execution_core/test_persistence_reducer_parity.py
  - tests/execution_core/test_persistence_input_receipt.py
  - tests/execution_core/test_persistence_write_capability.py
  - tests/execution_core/test_persistence_schema.py
  - tests/execution_core/test_persistence_repository.py
  - tests/execution_core/test_persistence_directness.py
  - tests/execution_core/test_position.py
  - tests/execution_core/test_venue.py
  - tests/execution_core/test_recovery.py
  - tests/execution_core/test_authority.py
  - tests/execution_core/test_protection.py
  - tests/execution_core/test_acquisition.py
```

Governance paths are the queue/active/completed WO-0168a file, this frozen contract, the additive
post-I3 map, `work/ledger.jsonl`, and `work/review/REV-0074/**` plus the separately assigned
implementation review directory. No other path is implied.

The decisive RED/GREEN set must prove exact union/export ratchets, byte known answers, every
decode mutant, complete member classification, reference/direct semantic parity for every matrix
row and owner disposition, history-independent checkpoint size/query counts, all five new schema
families, mandatory receipt rollback, outbox non-authority, and capability bypasses. Target and
stress fixtures are 64 and 2,048 unrelated terminal facts/inputs/effects respectively; canonical
checkpoint bytes and direct query count for one unchanged active set must be identical at both
sizes.

## 9. Fault edges and stop rules

WO-0168a codec/repository tests name `F00` before claim, `F01` after input claim, `F02` after proof
load, `F03` after reducer, `F04` after each row-family write, `F05` before checkpoint payload,
`F06` after payload/before head, `F07` before receipt, `F08` after receipt/before outcome, `F09`
before commit, `F10` commit-return unknown, and `F11` after commit/before publication. WO-0168a
proves the records and pure plan for those edges; WO-0168b owns transaction execution and full
crash proof.

Fresh preflight must return P0=0/P1=0 before source work. Changed DDL stops at the exact human gate
before installation or SQLite tests. A parity failure, missing member, need for a ninth top-level
operation, or need for an unlisted source path stops for a head-bound work-order amendment and
fresh review; it is not handled through a wildcard or local assumption.
