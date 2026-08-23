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
    "InputSemanticKey",
    "InputSemanticKeyKind",
    "M2Operation",
    "MarketOccurrenceOperation",
    "MarketOperationCoordinates",
    "OperationDomain",
    "VenueOperationCoordinates",
    "VenueRecoveryOperation",
    "decode_m2_operation",
    "decode_m2_semantic_key",
    "encode_m2_operation",
    "encode_m2_semantic_key",
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
identities already present in the accepted profile rows. `VenueOperationCoordinates.session_id` is
`None` only for an exact `ObserveVenueStatus` payload; every other `VenueRecoveryOperation`, and
every authority, acquisition, and market operation, requires a non-null exact session matching
current authority. The missing-session status observation is passive evidence only: C2 must verify
its profile/scope binding and it must never mint, default, or replace an authority session.

### 2.2 Technical input classification

`InputDedupeKind` is exactly `UNSEEN`, `EXACT_REPLAY`, or `IDENTITY_CONFLICT`.
`InputDedupeFact` has ordered members `kind`, `input_domain`, `input_identity_sha256`,
`payload_sha256`, `retained_outcome_sha256: str | None`, and
`semantic_matches: tuple[InputSemanticKey, ...]`.

Only the repository creates this fact after exact primary and alternate-key lookups. `EXACT_REPLAY` requires equal
domain, identity, coordinates, version, canonical payload bytes, and payload digest.
`IDENTITY_CONFLICT` means the exact primary domain/identity is retained with any unequal member.
An unseen primary identity with a retained alternate semantic key remains `UNSEEN` and carries the
matching key proof to the owning reducer; it is not prematurely translated to replay, conflict, or
refusal. Reducers never infer technical or alternate-key dedupe from history maps on the SQLite
path.

`InputSemanticKeyKind` is exactly `VENUE_COMMAND_V2`, `VENUE_EXECUTION_FACT_V1`,
`VENUE_COVERAGE_ROOT_V1`, `VENUE_COVERAGE_INTERVAL_V1`, `VENUE_BROKER_FACT_V1`,
`AUTHORITY_QUERY_CLAIM_V1`, `AUTHORITY_MANUAL_FLATTEN_V1`, or
`AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1`. `InputSemanticKey` has ordered members `kind`,
`canonical_key_bytes`, `key_sha256`, `retained_input_domain`, and
`retained_input_identity_sha256`. Bytes, not a digest alone, are authority; decode rehashes and
byte-compares them.

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

### 2.3.1 Exact operation wire table (R4 amendment)

The operation document's canonical JSON top value is exactly:

```text
[1, "m2.operation/v1", ["m2.operations.OperationDomain", DOMAIN], COORDINATES, PAYLOAD]
```

`DOMAIN` is the exact `OperationDomain` enum value. `COORDINATES` is one of the four fixed arrays
below; `PAYLOAD` is exactly one concrete aggregate from the closed table below. There is no generic
dataclass encoder, tag interpolation, class-name lookup, module import, registration, or fallback
decoder. Code writes one explicit `type(value) is ...` branch for every row and calls the owning
constructor/hydration seam named here on decode.

| Coordinates type | Exact canonical array |
| --- | --- |
| `ExecutionOperationCoordinates` | `["m2.operations.ExecutionOperationCoordinates/v1", application_generation_atom, execution_profile_id, scope_id]` |
| `VenueOperationCoordinates` | `["m2.operations.VenueOperationCoordinates/v1", application_generation_atom, execution_profile_id, scope_id, session_atom_or_null]` |
| `AcquisitionOperationCoordinates` | `["m2.operations.AcquisitionOperationCoordinates/v1", application_generation_atom, execution_profile_id, scope_id, session_atom, acquisition_generation_atom]` |
| `MarketOperationCoordinates` | `["m2.operations.MarketOperationCoordinates/v1", application_generation_atom, execution_profile_id, scope_id, session_atom, acquisition_generation_atom, market_source_profile_id, stream_generation_atom]` |

Every `*_atom` is the section-5 M1 durable atom array, never an identity string surrogate. Raw
bytes are lowercase even-length hex text. A direct `Fraction` is exactly
`["m2.scalar.Fraction/v1", numerator, denominator]`, with exact JSON integers, a positive
denominator, and relatively-prime components. The only non-M1 collection is an approved mandate's
order-type tuple, which is exactly
`["m2.acquisition.AcquisitionOrderTypes/v1", ["m1.authority.AcquisitionOrderType", "LIMIT"]]`.
No other collection length or order is admitted.

The following owner tags are literal and closed. A row's fields are the listed order; an M1 value
means its complete durable atom, an enum means the exact enum pair in the enum table, and `null`
means the only permitted absence. Derived/cache/seal fields are omitted only where the last column
explicitly says so and are re-derived/verified by the owner before encode and after decode.

| Literal aggregate tag | Exact fields | Decode/verification rule |
| --- | --- | --- |
| `m1.fills.PositionScope/v1` | broker, environment, account, symbol_id | `PositionScope(...)` |
| `m1.fills.ExecutionScope/v1` | broker, environment, account, order_id, symbol_id, side | `ExecutionScope(...)` |
| `m1.fills.BrokerFillFact/v1` | key, scope, root_fill_id, quantity, price | `BrokerFillFact(...)` |
| `m1.fills.BrokerTradeCorrectFact/v1` | key, scope, root_fill_id, predecessor_source_event_id, revised_quantity, revised_price | `BrokerTradeCorrectFact(...)` |
| `m1.fills.BrokerTradeBustFact/v1` | key, scope, root_fill_id, predecessor_source_event_id, reported_price_or_null | `BrokerTradeBustFact(...)` |
| `m1.fills.HumanAttestedFillFact/v1` | key, scope, root_fill_id, leg_key, request_occurrence_id, claim_occurrence_id, quantity, prior_cumulative_quantity, resulting_cumulative_quantity, price, actor, reason, evidence_reference | `HumanAttestedFillFact(...)` |
| `m1.venue.RecordTransportOutcome/v1` | input_id, effect_id, state | `RecordTransportOutcome(...)` |
| `m1.venue.RecoverClaimedEffect/v1` | input_id, effect_id | `RecoverClaimedEffect(...)` |
| `m1.venue.DiscoverVenueLeg/v1` | input_id, effect_id, leg_key, observation_id | `DiscoverVenueLeg(...)` |
| `m1.venue.ObserveVenueStatus/v1` | input_id, leg_key, status, observation_id, cumulative_quantity, closure_id_or_null, evidence_reference_or_null | `ObserveVenueStatus(...)` |
| `m1.recovery.IngestHumanAttestedFill/v1` | input_id, effect_id, fact | `IngestHumanAttestedFill(...)` |
| `m1.recovery.ReleaseVenueLeg/v1` | input_id, effect_id, leg_key, claim_occurrence_id, venue_cumulative_quantity, broker_terminal_state, actor, reason, evidence_reference, closure_id, evidence_digest | `ReleaseVenueLeg(...)` |
| `m1.recovery.RecordBrokerFillEvidence/v1` | input_id, effect_id, leg_key, prior_cumulative_quantity, resulting_cumulative_quantity, fact, evidence_digest, closure_id_or_null, evidence_reference_or_null | `RecordBrokerFillEvidence(...)` |
| `m1.recovery.RecordBrokerRevisionEvidence/v1` | input_id, effect_id, leg_key, prior_root_quantity, prior_venue_cumulative_quantity, resulting_venue_cumulative_quantity, fact, evidence_digest, closure_id_or_null, evidence_reference_or_null | `RecordBrokerRevisionEvidence(...)` |
| `m1.authority.BrokerEffectRequest/v1` | effect_id, request_occurrence_id, mandate_id, kind, client_order_id_or_null, symbol_id, side, quantity, economic_scope, target_leg_key_or_null | `BrokerEffectRequest(...)` |
| `m1.authority.CreateBrokerEffect/v1` | input_id, session_id, request, manual_flatten_id_or_null, emergency_grant_id_or_null | `CreateBrokerEffect(...)` |
| `m1.authority.ClaimEffect/v1` | input_id, effect_id, claim_occurrence_id | `ClaimEffect(...)` |
| `m1.authority.ClaimBrokerQuery/v1` | input_id, query_claim_id, symbol_id, kind | `ClaimBrokerQuery(...)` |
| `m1.authority.EngageKill/v1` | input_id, actor, reason, evidence_reference | `EngageKill(...)` |
| `m1.authority.BeginManualFlatten/v1` | input_id, flatten_id, session_id, symbol_id, actor, reason, evidence_reference, emergency_grant_id_or_null | `BeginManualFlatten(...)` |
| `m1.authority.AdvanceManualFlatten/v1` | input_id, flatten_id | `AdvanceManualFlatten(...)` |
| `m1.authority.AcquisitionEffectTerms/v1` | quantity, limit_price, order_type, evaluation_time | `AcquisitionEffectTerms(...)`; `commitment` is re-derived and must match owner authentication |
| `m1.protection.ExecutionGuard/v1` | guard_id, policy_commitment | `ExecutionGuard(...)` |
| `m1.protection.EvidencePolicy/v1` | source_id, stream_generation, sequence_mode, max_age, corroboration_window, max_step_fraction | `EvidencePolicy(...)` |
| `m1.protection.EmergencyRecoveryCompatibility/v1` | compatibility_id, position_scope, session_id, configuration_version, configuration_commitment, emergency_guard, maximum_goal_rate, emergency_effect_budget, deadline, aggregate_emergency_quantity | `EmergencyRecoveryCompatibility(...)`; `commitment` is re-derived and owner-authenticated |
| `m1.protection.ProtectionMandate/v1` | mandate_id, position_scope, session_id, configuration_version, loss_fraction, approved_gain, percent_trail_fraction, atr_multiple, tick, normal_guard, emergency_guard, evidence_policy, maximum_quantity, maximum_goal_rate, deadline, emergency_recovery_compatibility | `ProtectionMandate(...)`; `commitment` is re-derived and owner-authenticated |
| `m1.acquisition.AcquisitionMandate/v1` | acquisition_mandate_id, position_scope, session_id, configuration_version, maximum_quantity, maximum_notional, maximum_entry_price, allowed_order_types, expiry, deadline, fixed_child_cap, certified_participation_cap_or_null, cancel_reprice_budget, protection_mandate | acquisition-owned `_m2_hydrate_acquisition_mandate(...)` must mint the sole `DualMandateBinding`, construct `AcquisitionMandate(...)`, and prove `_acquisition_mandate_is_authentic`; the supplied binding, commitments, and seals are never independently accepted |
| `m1.protection.MarketOccurrence/v1` | source_id, stream_generation, position_scope, session_id, market_epoch, source_sequence_or_null, source_time, evaluation_time, kind, best_bid_or_null, best_ask_or_null, trade_price_or_null, atr_distance_or_null, structure_trail_or_null, halted | `MarketOccurrence(...)`; `occurrence_id` is re-derived and `_market_occurrence_is_authentic` must hold |

| Exact enum pair owner tag | Admitted enum type |
| --- | --- |
| `m2.operations.OperationDomain` | `OperationDomain` |
| `m1.fills.ExecutionSide` | `ExecutionSide` |
| `m1.venue.EffectKind` | `EffectKind` |
| `m1.venue.BrokerEffectState` | `BrokerEffectState` |
| `m1.venue.VenueAttemptState` | `VenueAttemptState` |
| `m1.authority.AuthorityQueryKind` | `AuthorityQueryKind` |
| `m1.authority.AcquisitionOrderType` | `AcquisitionOrderType` |
| `m1.protection.MarketKind` | `MarketKind` |
| `m1.protection.MarketSequenceMode` | `MarketSequenceMode` |

The domain-to-coordinate/payload closure is exact: `BROKER_EXECUTION` uses execution coordinates
and one of the three broker fact tags; `VENUE_RECOVERY` uses venue coordinates and one of the eight
venue/recovery tags; `AUTHORITY` uses execution coordinates and one of the six authority-command
tags; `BEGIN_ACQUISITION_GENERATION` uses acquisition coordinates with
`["m2.acquisition.BeginAcquisitionGeneration/v1", input_id, successor_mandate]`;
`CREATE_ACQUISITION_EFFECT` uses acquisition coordinates with
`["m2.acquisition.CreateAcquisitionEffect/v1", input_id, terms]`;
`CLAIM_ACQUISITION_EFFECT` uses acquisition coordinates with
`["m2.acquisition.ClaimAcquisitionEffect/v1", input_id, effect_id, claim_occurrence_id]`;
`BEGIN_ACQUISITION_PREEMPTION` uses acquisition coordinates with
`["m2.acquisition.BeginAcquisitionPreemption/v1", input_id]`; and `MARKET_OCCURRENCE` uses market
coordinates with `["m2.protection.MarketOccurrenceOperation/v1", occurrence]`. No coordinate or
payload tag may be shared across domains except the explicitly nested value rows above.

### 2.4 Exact alternate-key projection

The operation codec or authenticated current proof derives semantic keys; callers cannot supply
them. C3 directly looks up input-derived keys, and C4 directly looks up state-derived keys. A key
is inserted only at C6 when the owning reducer output proves that the corresponding historical map
would acquire it; a refused input cannot consume a semantic identity.

| Operation/payload | Required lookup | Exact insertion condition / placement |
| --- | --- | --- |
| every `VenueRecoveryOperation` | `VENUE_COMMAND_V2` equal to venue's accepted `_semantic_input_key(item)` bytes (input ID excluded) | C6 only when the owner emits a new `VenueInputRecord`; aliases retain the original owning input and do not overwrite it |
| venue payload with exact `.fact.key` | `VENUE_EXECUTION_FACT_V1` for that exact `ExecutionFactKey` | C6 only when the owner establishes the first-input-for-fact row |
| human/broker coverage payload | `VENUE_COVERAGE_ROOT_V1`; where applicable exact leg/prior/resulting `VENUE_COVERAGE_INTERVAL_V1` and broker-fact `VENUE_BROKER_FACT_V1` | C6 only with matching new human/broker coverage authority emitted by the owner |
| `ClaimBrokerQuery` | `AUTHORITY_QUERY_CLAIM_V1` for exact `query_claim_id` | C6 only on `AuthorityDisposition.APPLIED`, beside the budget/query checkpoint write |
| `BeginManualFlatten` | `AUTHORITY_MANUAL_FLATTEN_V1` for exact `flatten_id` | C6 only on `APPLIED`; `AdvanceManualFlatten` only looks up the retained key and active manual state |
| `ClaimEffect` whose authenticated retained effect authorization carries an emergency grant | state-derived `AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1` for that exact grant ID | C6 only on the exact applied claim that consumes the grant; effect creation/refusal never consumes it |

Broker-fact primary identity, dispatch claim effect/occurrence identity, request/client-order
identity, acquisition generation/routes, and market occurrence identity already have exact unique
authority in `durable_input` or accepted M2-I2 rows and are not duplicated as semantic keys.

### 2.5 Semantic-key byte and collision-domain contract

Semantic keys use this exact grammar, separate from the document kinds in section 5:

```text
key = ASCII("execution-core/m2-semantic-key/v1\n")
      || kind-octet || uint64-be(json-byte-length) || canonical-json-utf8
```

Canonical JSON uses section 5's settings and is exactly
`[1, KIND_NAME, COORDINATES, SOURCE]`. Kind octets are `0x01` through `0x08` in the enum order in
section 2.2. Venue-kind coordinates are exactly `[execution_profile_id]`; they intentionally span
application generations and sessions for the same immutable account/profile authority. Authority-
kind coordinates are exactly `[application_generation_id.value, execution_profile_id, scope_id]`;
session, acquisition generation, market profile, and stream are payload/current-proof checks but
do not create a fresh one-use collision domain.

Exact source arrays are:

- command: `["venue-semantic-digest", lowercase_hex(_semantic_input_key(item))]`;
- execution/broker fact: `["execution-fact-key", broker, environment, account, source_event_id]`;
- coverage root: `["root-fill-key", broker, environment, account, root_fill_id]`;
- coverage interval: `["coverage-interval", broker, environment, account, order_id, prior, resulting]`;
- query/manual/grant: respectively `["query-claim-id", value]`,
  `["manual-flatten-id", value]`, and `["emergency-grant-id", value]`.

All identity strings are the exact owning M1 `.value`; integers are exact JSON integers. Decode
checks kind-specific array length/types, re-encodes, and byte-compares. Repository code accepts no
other bytes. For fixture identities `ep`, `app`, scope `7`, single-letter M1 components, and an all-
zero venue semantic digest, the exact canonical JSON payload and complete-key SHA-256 known answers
are:

| Kind | Canonical JSON UTF-8 | Bytes | Complete-key SHA-256 |
| --- | --- | ---: | --- |
| `VENUE_COMMAND_V2` | `[1,"VENUE_COMMAND_V2",["ep"],["venue-semantic-digest","0000000000000000000000000000000000000000000000000000000000000000"]]` | 122 | `1843bf3067f4b195fedfc5f91f3e16eb2709d030dee8df7501057e1ab96faa52` |
| `VENUE_EXECUTION_FACT_V1` | `[1,"VENUE_EXECUTION_FACT_V1",["ep"],["execution-fact-key","b","e","a","s"]]` | 75 | `156419b82505dabe31bc5c20c5cd6db14eec7656039af3069e868a938ef52a03` |
| `VENUE_COVERAGE_ROOT_V1` | `[1,"VENUE_COVERAGE_ROOT_V1",["ep"],["root-fill-key","b","e","a","r"]]` | 69 | `450a3e32afee6722f0eb8b37fd11be884ee2fc491a5324e032b4f5f0bbe7afc6` |
| `VENUE_COVERAGE_INTERVAL_V1` | `[1,"VENUE_COVERAGE_INTERVAL_V1",["ep"],["coverage-interval","b","e","a","o",0,1]]` | 81 | `1691d21d732c6b202ee02a1fc0d271091c99ffa325dcd373bb830cf98d93b7bc` |
| `VENUE_BROKER_FACT_V1` | `[1,"VENUE_BROKER_FACT_V1",["ep"],["execution-fact-key","b","e","a","s"]]` | 72 | `666308088204232ad04268ca34e07b8f256ab0b8990875756542fde18a59b4d5` |
| `AUTHORITY_QUERY_CLAIM_V1` | `[1,"AUTHORITY_QUERY_CLAIM_V1",["app","ep",7],["query-claim-id","q"]]` | 68 | `2f9b20479eb5e93934f56c5ec3e026c732d747d12f1692a185102bf740aa05f3` |
| `AUTHORITY_MANUAL_FLATTEN_V1` | `[1,"AUTHORITY_MANUAL_FLATTEN_V1",["app","ep",7],["manual-flatten-id","m"]]` | 74 | `9e83b189cecd3c6dda3bfc422ee8ac66a71acca705829bbba220fd1bdbb527ff` |
| `AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1` | `[1,"AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1",["app","ep",7],["emergency-grant-id","g"]]` | 88 | `b1b571b9462e44a139c62a1e8ae93d3c6c104b78f83db3416b9e916727aabce4` |

The byte count column is the JSON payload length; the complete key also contains the fixed prefix,
kind octet, and eight-byte length.

## 3. Finite operation-to-reducer-to-write matrix

Every row first performs the common sequence `C0..C9`:

`C0` exact operation/type validation; `C1` `BEGIN IMMEDIATE`; `C2` schema/profile/application/
scope/session verification; `C3` durable-input claim plus exact input-derived alternate-key
lookups; `C4` direct current proof plus state-derived alternate-key lookup; `C5` shared pure
transition; `C6` conditional owner-authorized semantic-key and row writes in frozen order; `C7`
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

### R7 direct-proof binding amendment

`_M2ExecutionState` additionally retains the exact aggregate commitments of the current
`root_heads` and `seen_facts` registries. `_M2ExecutionObservationProof` is an opaque,
owner-constructed, fixed-field value: it binds the state commitment, both aggregate commitments,
the exact broker fact, the direct prior-observation/current-root/predecessor rows, the root-claim
bit, and its own re-derived commitment. A type-owned constructor may mint it only from one coherent
`ExecutionSnapshot` after exact keyed lookup verifies each retained direct row and both aggregate
commitments. The direct-proof seam re-derives that proof commitment and rejects a substituted,
absent, cross-state, or stale aggregate slice before classification. No map, history replay,
generic record, reflection, or caller-shaped tuple becomes proof.

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
| `_effect_authority_by_id`, `_claim_by_effect`, `_claim_by_occurrence`, `_manual_by_id`, `_manual_flatten_by_scope`, `_acquisition_currentness_by_scope`, `_acquisition_descriptor_by_scope`, `_acquisition_descriptor_by_effect`, `_acquisition_active_by_scope` | active/unresolved entries only, ordered by canonical identity and resolved against current direct rows; terminal manual IDs use the semantic-key ledger below |
| `_input_by_id` | history-shaped; omitted and replaced by primary `durable_input`/outcome direct lookup |
| `_query_by_id` | history-shaped alternate-key authority; omitted and replaced by immutable `AUTHORITY_QUERY_CLAIM_V1` rows; a different input ID with the same query ID is still presented to the owner as a retained semantic match |
| `_consumed_grant_ids` | history-shaped one-use authority; omitted and replaced by immutable `AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1` rows; the active unconsumed `_emergency_grant` remains in the checkpoint |

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
it re-derives and checks the owning commitment and an opaque
`_M2ProtectionAuthorityProof`, never a caller-supplied tuple. That fixed, owner-constructed proof
binds the selected application generation, execution and market-source profiles, scope,
controller-currentness head, live acquisition generation, and the exact protection-authority row.
Its factory verifies that the authority's expected controller head equals the current head, its
active acquisition generation equals the live generation, and its source/profile/session/stream,
mandate, state-commitment, and version coordinates are exact. The hydrator re-derives the proof
commitment and compares every state-relevant coordinate to the rebuilt protection state. A future
checkpoint codec must use the proof's selected envelope coordinates exactly; it may not translate a
bare row or independently select profiles/currentness. The constructor may use `object.__new__`
internally only as the owning class's verified constructor, never as a generic persistence decoder.
The shared kernels are `_m2_reduce_position_protection`,
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

For an operation document, section 2.3.1 is the complete outer-array, coordinate, aggregate, enum,
derived-field, and domain/payload authority. A field whose name ends `_or_null` has exactly the
specified owner type or JSON `null`; no omitted element, default, inferred binding, or alternate
tag is accepted.

## 6. Frozen schema and repository extension

WO-0168a authors one schema-v2 fresh-database candidate. It changes no existing accepted table or
trigger semantics except the schema version/catalog identity and adds exactly these families:

| Family | Required authority |
| --- | --- |
| `runtime_checkpoint_payload` | one exact canonical payload per `kernel_checkpoint` version; bytes, length, digest, version, application/profile binding |
| `durable_input` | immutable domain/identity/coordinates/version/payload bytes+digest and technical state `CLAIMED|TERMINAL|RECONCILIATION_PENDING` |
| `durable_input_semantic_key` | immutable application/profile/scope-bound key kind, canonical key bytes+digest, and exact owning input FK; unique on coordinates+kind+bytes, never digest alone |
| `decision_receipt` | append-only receipt bytes+digest and exact input correlation; explanatory only |
| `durable_input_outcome` | one terminal owner-domain/disposition/result digest/checkpoint reference plus mandatory receipt FK |
| `broker_outbox` | immutable post-commit effect/dispatch-claim payload and committed sequence; no external-success state |

`durable_input_semantic_key` has exactly these ordered columns: `key_kind`,
`key_application_generation_id` (nullable only for venue kinds), `execution_profile_id`,
`key_scope_id` (nullable only for venue kinds), `canonical_key_bytes`, `key_sha256`,
`input_application_generation_id`, `input_domain`, `input_identity_sha256`, and
`created_ordinal`. Venue rows require both nullable key coordinates to be null; authority rows
require both non-null. Two partial unique indexes freeze the collision domains exactly:

1. venue: `(execution_profile_id, key_kind, canonical_key_bytes)` for venue kinds; and
2. authority: `(key_application_generation_id, execution_profile_id, key_scope_id, key_kind,
   canonical_key_bytes)` for authority kinds.

`key_sha256` is lookup acceleration/integrity evidence, never uniqueness authority. The row has an
exact composite FK to its owning `durable_input`, immutable insert ordinal, and no update/delete
route. `DurableInputSemanticKeyRecord` exposes those ten columns in that order and re-derives the
kind, coordinates, bytes, and digest before repository use.

Required uniqueness, immutable-byte triggers, coordinate/profile FKs, monotonic checkpoint/outbox
ordinals, and no-update/no-delete rules are part of the DDL. An outcome cannot exist without its
receipt; every semantic key is claimed atomically with its input and cannot be updated or deleted;
a checkpoint head cannot advance without its exact payload; an outbox row cannot exist
without the exact immutable dispatch claim and matching effect/profile/generation. A receipt or
outbox row cannot be referenced as economic/currentness/owner/closure authority.

The DDL, records, and repository methods may be implemented and statically reviewed. No changed
DDL is installed and no SQLite-bearing test executes until Ameen approves the exact SHA-256, byte
length, candidate commit/tree, and named temporary-file test command. Any byte drift returns to
that gate.

Exact new record/repository surface:

- records: `RuntimeCheckpointPayloadRecord`, `DurableInputRecord`,
  `DurableInputSemanticKeyRecord`,
  `DecisionReceiptRecord`, `DurableInputOutcomeRecord`, `BrokerOutboxRecord`;
- repository: `store/load_runtime_checkpoint_payload`, `claim/load_durable_input`,
  `store/load_durable_input_semantic_key`, `load_durable_input_by_semantic_key`,
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
  - app/execution_core/fills.py
  - app/execution_core/position.py
  - app/execution_core/venue.py
  - app/execution_core/recovery.py
  - app/execution_core/authority.py
  - app/execution_core/protection.py
  - app/execution_core/acquisition.py
  - app/execution_core/persistence/operations.py
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/persistence/unit_of_work.py
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
  - tests/execution_core/persistence_setup_support.py
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
  - tests/execution_core/test_import_boundary.py
```

### R6 import-boundary test-scope amendment

The existing M1 import-boundary oracle reconstructs a retained legacy view of
`protection.py`.  The contractually required M2 direction is now public reducer
to shared package-private kernel, which is a semantics-preserving extraction of
the retained public body.  The oracle must therefore model that extraction when
it reconstructs its legacy view, rather than treating the required kernel as an
unresolved external call.  This amendment adds only the existing
`tests/execution_core/test_import_boundary.py` path so that exact legacy-model
correction and its failure-capable pin can be made.  It adds no source path,
operation, state member, schema family, persistence authority, DDL execution,
runtime composition, or safety relaxation.

No change to that test path is permitted until a fresh REV-0074 R6
documentation review accepts this exact amendment with P0=0/P1=0.  The normal
REV-0075 implementation review and changed-DDL human gate remain independent.

### R7 owner-proof binding amendment

The R1 interim implementation review identified that direct execution proof slices and the
protection checkpoint authority input were self-consistent but not fully bound to retained current
state. This amendment freezes the two narrow owner-proof constructions described in sections 4.1
and 4.4: aggregate-bound execution observation proof and typed, sealed protection-currentness
proof. It adds no source or test path, operation, schema family, persistence write authority, DDL
execution, runtime composition, external activity, or safety relaxation. It prohibits bare tuples
at either proof boundary and requires mutation tests for every previously unbound coordinate.

No source or test change implementing this amendment may be made until a fresh REV-0074 R7
documentation review accepts this exact amendment with P0=0/P1=0. The normal REV-0075
implementation review and any changed-DDL human gate remain independent.

### R8 authenticated direct-proof amendment

R7's aggregate commitments are necessary but do not themselves prove that a selected direct row is
a member (or non-member) of the committed current index. `fills.py` therefore provides exact,
key-bounded radix membership and non-membership witnesses for the direct `root_head`, `seen_fact`,
and root-claim maps. A witness retains only the queried key, key-bounded path commitments, and at a
non-member terminal the at-most-256 labelled child commitments needed to prove the requested edge is
absent. It never retains a map, history, arbitrary container, or replay input. `_M2ExecutionState`
retains the corresponding three map commitments; `_M2ExecutionObservationProof` carries one exact
witness for each selected or absent direct row and the owner validates each against its map
commitment before classification.

`_M2ProtectionAuthorityProof` no longer accepts a caller-constructed current-row carrier. Its only
issuance route is the package-private checkpoint-codec adapter after it verifies one typed
repository `CurrentProofSlice`: selected application/profile/scope rows, current controller head,
live acquisition generation, and protection-authority row must agree exactly before the owner seals
the proof. The pure hydrator receives only that sealed proof and rechecks all state-relevant
coordinates; a direct tuple, raw rows, or independently selected envelope is forbidden.

This amendment adds only `app/execution_core/fills.py` to the R8 implementation surface. It adds no
new operation, schema family, database execution, runtime composition, external activity, or safety
exception. No source or test change implementing R8 may be made until a fresh REV-0074 R8
documentation review accepts this exact amendment with P0=0/P1=0. The normal REV-0075
implementation review and changed-DDL human gate remain independent.

### R9 sound authenticated-proof amendment

R8 is not accepted: its aggregate-only path witness leaves an algebraic substitution route under the
existing XOR child aggregate, and its ordinary `CurrentProofSlice` cannot establish repository
provenance or a read-time currentness boundary. This amendment makes the two smallest root
corrections without replacing the radix map or adding a runtime layer.

For each traversed radix node, a witness carries the complete canonical tuple of labelled child
commitments, sorted strictly by the unsigned byte label, together with that node's exact
`has_value`/value commitment. The verifier recomputes the node's XOR child aggregate from that
tuple and requires the queried next-byte edge to lead to the next authenticated node. At the terminal
node it either requires the queried value commitment or proves absence by the exact complete child
tuple not containing the requested next byte. Thus every node commitment is authenticated from
complete bounded input rather than from an unconstrained sibling aggregate. A witness contains only
the queried key, one at-most-256 child tuple per key byte plus its terminal node, and fixed-size
commitments; it retains no map, history, arbitrary caller container, or replay input.

`CurrentProofSlice` remains a public result type but becomes opaque (`init=False`) and can be sealed
only by a repository-private issuer after `load_current_proof` has verified the exact
`CurrentProofRequest` and its direct-current rows. Its seal binds the request, selected
application/execution-profile/market-profile/scope coordinates, live acquisition generation,
controller currentness head, protection-authority version, and the exact verified row relationships.
The checkpoint codec accepts only a slice whose issuer and seal revalidate; it never accepts a raw
row carrier, tuple, independently selected envelope, or caller-constructed slice. Freshness is a
transactional property, not a claim a detached object can make: the eventual caller-owned unit of
work must load and consume the sealed slice on its one connection before its guarded conditional
write, using the bound currentness/version coordinates as write preconditions. A cached or replayed
slice is not an admitted write input.

R9 uses only already-named WO-0168a source paths: `fills.py`, `position.py`, `protection.py`,
`persistence/records.py`, `persistence/repository.py`, and `persistence/checkpoint_codec.py`; and
only already-named direct tests: `test_position.py`, `test_protection.py`,
`test_persistence_repository.py`, `test_persistence_checkpoint_codec.py`, and
`test_import_boundary.py`. It adds no operation, schema family, database execution, runtime
composition, external activity, or safety exception. No R9 source or test change may be made until
a fresh REV-0074 R9 documentation review accepts the exact amendment with P0=0/P1=0. The normal
REV-0075 implementation review and changed-DDL human gate remain independent.

### R10 complete nonmembership amendment

R9 is not accepted because it did not state the terminal-prefix nonmembership case. The authenticated
radix verifier has exactly two absence outcomes. Before the queried key is fully consumed, the
authenticated current node's complete canonical child tuple must omit the next queried byte label.
After every queried key byte is consumed, the authenticated terminal node must have
`has_value=False`; its complete canonical child tuple remains part of the node commitment and may
contain descendants for longer keys. Membership, conversely, consumes every queried byte, requires
the terminal `has_value=True`, and requires the exact selected value commitment. No third terminal
or inferred absence case is admitted.

`test_position.py` must contain a failure-capable negative control built from the existing private
persistent-map primitive: a map containing a longer key must prove its shorter prefix absent, and a
mutated prefix-terminal witness must be refused. This is a proof-primitive test only; it adds no
history, schema, repository, runtime, database execution, or external surface. No R10 source or
test change may be made until a fresh REV-0074 R10 documentation review accepts the exact amendment
with P0=0/P1=0. The normal REV-0075 implementation review and changed-DDL human gate remain
independent.

### R11 terminal-nonmembership mutation-proof amendment

R10 is not accepted because its longer-key-only prefix test could still pass if the verifier forgot
the terminal `has_value=False` rule. Retain that positive absence case, and add one separate
authenticated negative control: construct a map containing both a prefix key and a descendant key,
obtain the valid witness for the retained prefix, then ask the verifier to treat that witness as
nonmembership. It must refuse specifically because the exhausted-key terminal has
`has_value=True`, even though every node commitment and every child tuple is otherwise authentic.
The pair proves both prefix absence and rejection of a genuine present-prefix witness misclassified
as absent. No fabricated commitment is an adequate substitute for this control.

R11 changes only the already named `test_position.py` proof primitive expectation. It adds no source
path, map redesign, history, schema, repository, runtime, database execution, external activity, or
safety exception. No R11 source or test change may be made until a fresh REV-0074 R11 documentation
review accepts the exact amendment with P0=0/P1=0. The normal REV-0075 implementation review and
changed-DDL human gate remain independent.

Governance paths are the queue/active/completed WO-0168a file, this frozen contract, the additive
post-I3 map, `work/ledger.jsonl`, and `work/review/REV-0074/**` plus the separately assigned
implementation review directory. No other path is implied.

The decisive RED/GREEN set must prove exact union/export ratchets, byte known answers, every
decode mutant, complete member classification, reference/direct semantic parity for every matrix
row and owner disposition, history-independent checkpoint size/query counts, all six new schema
families, different-input-ID query/grant/manual/venue-semantic reuse, mandatory receipt rollback,
outbox non-authority, and capability bypasses. Target and
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

## R12 persisted-document and write-capability closure amendment

**Status: draft — documentation only; no source, test, DDL installation, or SQLite authority.**

R12 addresses the remaining R9 root cause: a self-consistent component proof is not a
persistence-level authenticity anchor. The anchor is one immutable retained checkpoint document
whose exact bytes are bound to the selected current `kernel_checkpoint` head. Component codecs
remain owner-local construction helpers; they must not be used as a standalone restart/hydration
entry point or treated as proof of a database selection.

R12 also closes the missing exact columns, primary identities, lifecycle transition owner,
receipt/outcome linkage, outbox snapshot, and capability matrix identified by
`REV-0075/result-r9-preflight.md`. It intentionally adds no operation, reducer branch, runtime
composition, or external activity.

### R12.1 Retained checkpoint anchor and outer checkpoint document

`RuntimeCheckpointPayloadRecord` has exactly these ordered persisted members:

1. `application_generation_id`;
2. `execution_profile_id`;
3. `market_source_profile_id`;
4. `currentness_head_ordinal`;
5. `checkpoint_version_ordinal`;
6. `payload_bytes`;
7. `payload_length`; and
8. `payload_sha256`.

`payload_bytes` is exactly one kind-`0x02` document. Its canonical JSON is:

```text
[1, "m2.runtime-checkpoint/v1", application_generation_atom,
 execution_profile_id, market_source_profile_id,
 currentness_head_ordinal, checkpoint_version_ordinal,
 authority_state, scope_states,
 active_or_unresolved_effect_refs, active_or_unresolved_route_refs]
```

The array has exactly eleven members. `application_generation_atom` is the section-5 M1 durable
atom for the exact `ApplicationGenerationId`; profile identities are lowercase SHA-256 text;
the two ordinals are exact nonnegative/positive JSON integers respectively. The four tail
members are the explicitly typed, fixed-order owner representations in section 4; they are never
generic objects, maps, reflected dataclasses, or opaque Python bytes. `scope_states` is ordered
strictly by `scope_id`; effect references are ordered by canonical effect identity; route
references are ordered by domain then canonical identity. `payload_sha256` is the document digest
and is deliberately not serialized as an eleventh self-reference.

For every R12 canonical document, its retained length member is exactly `len(document_bytes)`:
runtime-checkpoint `payload_length == len(payload_bytes)`, decision-receipt
`receipt_length == len(canonical_receipt_bytes)`, durable-input-outcome
`outcome_length == len(canonical_outcome_bytes)`, and broker-outbox
`payload_length == len(canonical_payload_bytes)`. Record construction, repository store/load, and
the outer checkpoint decoder must recheck that equality as well as the digest; a changed length
with unchanged bytes is an integrity failure.

`RuntimeCheckpointEnvelope` remains the only public checkpoint data type. Its two public codec
entry points are exactly `encode_runtime_checkpoint(envelope) -> bytes` and
`decode_runtime_checkpoint(payload_record, current_proofs) -> RuntimeCheckpointEnvelope`.
`decode_runtime_checkpoint` accepts no raw bytes, caller-shaped scope, or caller-shaped proof.
It requires an exact `RuntimeCheckpointPayloadRecord` and the complete, sealed,
repository-issued `CurrentProofSlice` tuple selected for that payload. Before any owner hydrator
runs it must require all of the following:

1. `payload_sha256 == SHA256(payload_bytes)` and the payload parses/re-encodes byte-for-byte;
2. the document header equals every record coordinate;
3. the record coordinates and digest equal the selected `kernel_checkpoint` current head;
4. every proof is exact, authentic, belongs to that application/profile/head, and is selected
   once only for its stated direct rows; and
5. every reconstructed owner state is semantically equal to its canonical component and its
   derived commitment equals the retained component commitment.

Until an owner has its complete section-4 typed wire row and complete direct-proof tuple,
`decode_runtime_checkpoint` must refuse that state rather than hydrate an approximation. In
particular, the existing R7--R11 execution and protection component helpers are not a retained
payload decoder and cannot establish persistence-level authenticity by themselves. The eventual
outer decoder is the only place that may pass a checkpoint `PositionScope` to a protection
hydrator: it is first anchored by retained bytes and then compared to the exact selected scope
state. It must not derive a `PositionScope` from an execution profile, whose provider token,
environment token, and account fingerprint are deliberately not M1 position identities.

`runtime_checkpoint_payload` is immutable historical data, while `kernel_checkpoint` is a
mutable current-head pointer. They therefore cannot use a normal child foreign key: updating the
head would orphan every retained older payload. The schema-v2 candidate instead has these exact
relations:

- primary key `(application_generation_id, checkpoint_version_ordinal)` on
  `runtime_checkpoint_payload`;
- unique `(application_generation_id, currentness_head_ordinal, checkpoint_version_ordinal,
  payload_sha256)` on that table;
- foreign keys from its application/profile coordinates to the accepted application-generation
  selections; immutable insert-only/no-delete triggers; and
- `BEFORE INSERT` and `BEFORE UPDATE OF currentness_head_ordinal, checkpoint_sha256,
  checkpoint_version_ordinal` triggers on `kernel_checkpoint`. Each trigger refuses unless one
  matching payload row already exists with
  `(NEW.application_generation_id, NEW.currentness_head_ordinal,
  NEW.checkpoint_version_ordinal, NEW.checkpoint_sha256)`.

The exact profile foreign keys are `(application_generation_id, execution_profile_id)` to
`application_generation(application_generation_id, selected_execution_profile_id)` and
`(application_generation_id, market_source_profile_id)` to
`application_generation(application_generation_id, selected_market_source_profile_id)`. A
checkpoint reference from a receipt or outcome is the exact composite
`(application_generation_id, checkpoint_currentness_head_ordinal,
checkpoint_version_ordinal, checkpoint_payload_sha256)` foreign key to the payload-table unique
key above. It is either fully null or fully present.

The sole allowed write order is therefore: insert the immutable new payload first, then insert or
advance `kernel_checkpoint` in the same caller-owned transaction. The payload's application/profile
foreign keys are ordinary; no foreign key points at mutable `kernel_checkpoint`. This is the
necessary reverse-edge constraint: a payload may refer to history, but a serving head cannot exist
without its exact retained payload. A static DDL review and fresh-file test must prove both
directions, historical payload survival after head advance, and refusal of an unpaired head.

### R12.2 Primary input identity and durable-input lifecycle

The primary identity is derived only after `decode_m2_operation` has accepted and canonicalized the
payload. Its bytes are:

```text
input-identity = ASCII("execution-core/m2-input-identity/v1\n")
                 || uint64-be(json-byte-length)
                 || canonical-json-utf8([1, DOMAIN, PRIMARY_ATOM])
input_identity_sha256 = lowercase-hex(SHA256(input-identity))
```

`DOMAIN` is the exact `OperationDomain.value`; `PRIMARY_ATOM` is the section-5 M1 durable atom of
the decoded operation's exact technical identity: `fact.key` for broker execution,
`item.input_id` for venue recovery, `command.input_id` for authority,
the operation's `input_id` for each acquisition row, and `occurrence.occurrence_id` for market.
There is no caller-provided primary digest, alternate-key substitution, coordinate-derived digest,
or raw payload hash substitute. The application generation, domain, and identity digest together
are the primary key; unequal coordinates or bytes at that key are an identity conflict.

`DurableInputRecord` has exactly these ordered persisted members:

1. `application_generation_id`;
2. `execution_profile_id`;
3. `scope_id`;
4. `input_domain`;
5. `session_id_or_null`;
6. `acquisition_generation_id_or_null`;
7. `market_source_profile_id_or_null`;
8. `stream_generation_id_or_null`;
9. `input_identity_sha256`;
10. `operation_contract_version` (literal `1`);
11. `canonical_payload_bytes`;
12. `payload_sha256`;
13. `technical_state`; and
14. `created_ordinal`.

Its exact primary key is `(application_generation_id, input_domain,
input_identity_sha256)`. It has a unique immutable `created_ordinal`; foreign keys
`(application_generation_id, execution_profile_id)` to the selected execution profile;
`(scope_id, application_generation_id, execution_profile_id)` to `acquisition_scope`; optional
`(acquisition_generation_id, scope_id)` to `acquisition_generation`; optional
`(application_generation_id, market_source_profile_id)` to the selected market profile; and
optional `stream_generation_id` to `market_stream_authority`; plus immutable-byte/no-delete
triggers. Its
constructor and repository load path must decode/re-encode the operation and require the row's
domain, every coordinate, primary identity, version, bytes, and digest to match that decoded
operation. A null venue session is allowed only when the decoded payload is exact
`ObserveVenueStatus`; it is never accepted merely because a row has a venue domain.

`claim_durable_input` is the sole creation method and accepts only `technical_state == "CLAIMED"`.
`finalize_durable_input` is the sole transition method and is called only by the finite
`unit_of_work.py` row-write table after the matching receipt and outcome are stored. It allows
exactly one transition from `CLAIMED` to either:

- `TERMINAL` for every owner disposition except `RECONCILIATION_REQUIRED`; or
- `RECONCILIATION_PENDING` only for `RECONCILIATION_REQUIRED`.

Neither terminal state may change in WO-0168a. A schema trigger refuses either transition unless
the exact one outcome/receipt pair described below exists and has the same terminal technical
state. An exact replay reads that retained outcome and writes no new receipt, outcome, checkpoint,
or outbox row. An identity conflict writes none of those rows. This is a lifecycle fact, not a
claim that a broker action succeeded.

### R12.3 Outcome and decision-receipt documents

`OwnerDomain` is the closed text set `POSITION`, `VENUE_RECOVERY`, `AUTHORITY`,
`ACQUISITION`, and `PROTECTION`. Its admitted dispositions are exactly the row-specific sets in
section 3; a generic outcome name is refused. A `result_sha256` is independently derived from:

```text
ASCII("execution-core/m2-reducer-result/v1\n")
|| uint64-be(json-byte-length)
|| canonical-json-utf8(
     [1, owner_domain, owner_disposition, terminal_technical_state,
      checkpoint_reference_or_null]
   )
```

`checkpoint_reference_or_null` is either `null`, or exactly
`[currentness_head_ordinal, checkpoint_version_ordinal, payload_sha256]`. All three members are
present together or absent together. It is a reference to the immutable payload row, not a
receipt or outbox authority.

`DecisionReceiptRecord` has these ordered persisted members:

1. `receipt_ordinal`;
2. `application_generation_id`;
3. `input_domain`;
4. `input_identity_sha256`;
5. `owner_domain`;
6. `owner_disposition`;
7. `terminal_technical_state`;
8. `result_sha256`;
9. `checkpoint_currentness_head_ordinal_or_null`;
10. `checkpoint_version_ordinal_or_null`;
11. `checkpoint_payload_sha256_or_null`;
12. `canonical_receipt_bytes`;
13. `receipt_length`; and
14. `receipt_sha256`.

Its primary key is `receipt_ordinal`; the input identity tuple is unique; it has a foreign key to
that exact durable input; it has a unique
`(application_generation_id, input_domain, input_identity_sha256, receipt_ordinal,
receipt_sha256)` key for the outcome link; its nullable checkpoint reference has the R12.1
composite foreign key; its canonical document is kind `0x04`; and it has the immutable
row/no-delete rules. The JSON array is exactly:

```text
[1, "m2.decision-receipt/v1", application_generation_atom,
 ["m2.operations.OperationDomain", DOMAIN], input_identity_sha256,
 receipt_ordinal, owner_domain, owner_disposition, terminal_technical_state,
 result_sha256, checkpoint_reference_or_null]
```

`DurableInputOutcomeRecord` has these ordered persisted members:

1. `application_generation_id`;
2. `input_domain`;
3. `input_identity_sha256`;
4. `owner_domain`;
5. `owner_disposition`;
6. `terminal_technical_state`;
7. `result_sha256`;
8. `checkpoint_currentness_head_ordinal_or_null`;
9. `checkpoint_version_ordinal_or_null`;
10. `checkpoint_payload_sha256_or_null`;
11. `receipt_ordinal`;
12. `receipt_sha256`;
13. `canonical_outcome_bytes`;
14. `outcome_length`; and
15. `outcome_sha256`.

Its primary key is the durable-input identity tuple; it has an exact foreign key to that input and
an exact composite foreign key to the receipt identity tuple
`(application_generation_id, input_domain, input_identity_sha256, receipt_ordinal,
receipt_sha256)`. A nullable checkpoint reference has an exact composite foreign key to the
immutable payload row. Its canonical document is kind `0x03` and is exactly:

```text
[1, "m2.durable-input-outcome/v1", application_generation_atom,
 ["m2.operations.OperationDomain", DOMAIN], input_identity_sha256,
 owner_domain, owner_disposition, terminal_technical_state, result_sha256,
 checkpoint_reference_or_null, receipt_ordinal, receipt_sha256]
```

`store_decision_receipt` and `store_durable_input_outcome` accept only a write capability and
exact record. They decode/re-encode their own bytes, recompute all digests, and require every
duplicate field and foreign coordinate to agree. The receipt is explanatory evidence only: no
reducer, currentness, claim, closure, recovery, outbox, or serving query may take it as an input
authority. A receipt must be inserted before its outcome; neither row is updateable or deletable.

Before an outcome is inserted, a null-safe schema trigger must require that its receipt has equal
`owner_domain`, `owner_disposition`, `terminal_technical_state`, `result_sha256`, and every member
of `checkpoint_reference_or_null`. The durable-input finalization trigger rechecks the same
coherent pair, not terminal state alone. A mutation of any one duplicated member is refused.

### R12.4 Immutable broker outbox snapshot

`BrokerOutboxRecord` has these ordered persisted members:

1. `outbox_sequence`;
2. `application_generation_id`;
3. `execution_profile_id`;
4. `scope_id`;
5. `acquisition_generation_id`;
6. `input_domain`;
7. `input_identity_sha256`;
8. `effect_id`;
9. `claim_id`;
10. `canonical_payload_bytes`;
11. `payload_length`; and
12. `payload_sha256`.

Its primary key is `outbox_sequence`, which must be the next global positive sequence at insert;
`(effect_id, claim_id)` is unique; `input_domain` is exactly `AUTHORITY` or
`CLAIM_ACQUISITION_EFFECT`; and it has exact foreign keys from
`(application_generation_id, input_domain, input_identity_sha256)` to durable input,
`(effect_id, scope_id, application_generation_id, execution_profile_id,
acquisition_generation_id)` to the venue-effect coordinate key, and `(effect_id, claim_id)` to
dispatch claim. The repository also compares the decoded snapshot to all immutable fields of the
retained effect and claim before accepting or loading it; an ID-only foreign key is insufficient.

The kind-`0x05` canonical JSON array is exactly:

```text
[1, "m2.broker-outbox/v1", outbox_sequence, application_generation_atom,
 execution_profile_id, scope_id, acquisition_generation_atom,
 ["m2.operations.OperationDomain", DOMAIN], input_identity_sha256,
 effect_id, effect_external_atom, request_occurrence_atom, mandate_atom,
 generation_mandate_commitment_sha256,
 expected_controller_head_ordinal, expected_protection_version_ordinal,
 authority_class, effect_kind, client_order_atom_or_null, target_order_atom_or_null,
 side, quantity_atom, economic_scope_hex,
 claim_id, claim_occurrence_atom, claim_ordinal]
```

Every `_atom` is the section-5 M1 durable atom, `economic_scope_hex` is lowercase even-length
hex for the exact retained bytes, and each enum/value has the section-5 owner tag. The encoded
`outbox_sequence` must equal the persisted primary-key value, so a sequence-only substitution is
an integrity failure. This is the
complete immutable dispatch snapshot; a later dispatcher must not reconstruct a broker command
from mutable effect lifecycle fields. The outbox has no delivered, acknowledged, success, retry,
or broker-result state. Later observed venue activity remains a separately durable input. An
outbox row is eligible only after the caller-owned transaction commits; it is never economic,
currentness, closure, or recovery authority.

### R12.5 Exact capability and test-support boundary

`tests/execution_core/persistence_setup_support.py` is the only setup-capability issuer and is
added to the exact test scope. It may import the private setup issuer from `repository.py`; only
`test_persistence_schema.py`, `test_persistence_repository.py`,
`test_persistence_directness.py`, `test_persistence_input_receipt.py`, and
`test_persistence_write_capability.py` may import that
support module. No `app/**` module may import it or a setup capability.

`_RuntimeWriteCapability` is a private exact, non-subclassable, connection- and transaction-bound
type. Its constructor raises; only `unit_of_work.py` may obtain it after `BEGIN IMMEDIATE` and
exact schema/application/profile verification. `_SetupWriteCapability` is likewise private,
exact, non-subclassable, and connection-bound. Its constructor raises; the named support module
may obtain it only for a fresh `tmp_path` fixture connection. These are structural controls, not a
claim that hostile arbitrary Python cannot inspect process memory.

All `load_*` repository functions, including `load_current_proof`, are **read-only** and accept no
capability. Every production mutator below is a runtime mutator: it accepts a runtime capability
in production and a setup capability only through the named test-support route. The seven genesis
entries may be used in production only by the exact bootstrap transaction below; there is no
production setup-token bypass.

| Class | Exact mutators |
| --- | --- |
| runtime, genesis only | `store_execution_profile`, `store_market_source_profile`, `store_application_generation`, `store_scope`, `store_kernel_checkpoint`, `store_symbol_controller`, `store_protection_authority` |
| runtime | `store_acquisition_generation`, `retire_acquisition_generation`, `advance_kernel_checkpoint`, `advance_symbol_controller`, `store_root_fill`, `store_execution_fact`, `store_venue_effect`, `advance_venue_effect`, `store_venue_identity_owner`, `store_acquisition_root_route`, `store_dispatch_claim`, `store_acceptance_set`, `store_acceptance_evidence`, `store_closure`, `store_market_stream_authority`, `store_market_cursor`, `advance_market_cursor`, `advance_protection_authority`, `claim_durable_input`, `finalize_durable_input`, `store_runtime_checkpoint_payload`, `store_durable_input_semantic_key`, `store_decision_receipt`, `store_durable_input_outcome`, `store_broker_outbox` |

`unit_of_work.py` owns one package-private `begin_genesis_bootstrap` route for the otherwise
cyclic first durable baseline. It is not an admitted top-level operation and may be called only by
WO-0169 startup after that order is separately activated. It begins one immediate transaction,
verifies the exact schema, and requires all of the following target keys to be absent before it
issues a runtime capability: the exact execution profile, market profile, application generation,
scope, kernel checkpoint, symbol controller, and protection-authority row. Its exact validated
seed tuple, in write order, is:

1. `ExecutionConnectionProfile`;
2. `MarketDataSourceProfile`;
3. `ApplicationGenerationRecord` selecting exactly those two profiles;
4. `ScopeRecord` bound to that application/profile;
5. `RuntimeCheckpointPayloadRecord` with head `0` and version `1`;
6. `KernelCheckpointRecord` with the same application, head, version, and payload digest;
7. `SymbolControllerRecord` for that scope with head `0`, aggregate quantity `0`, no live
   acquisition generation, and `CONSISTENT` integrity; and
8. `ProtectionAuthorityRecord` for that scope with `NORMAL` authority and no active stream.

The plan validates every listed profile/application/scope relation before its first insert and the
payload-first/head-second rule before inserts 5--6. It does not create an acquisition generation,
market stream, effect, claim, outbox, or external eligibility; those remain ordinary later runtime
steps. It refuses until the exact complete outer-checkpoint typed rows required by R12.1 are
implemented; no bootstrap may substitute a partial component document for that payload. Any
nonempty target row, coordinate mismatch, nonzero/noninitial baseline, or repeated bootstrap is
refused. This resolves the bootstrap cycle without allowing production code to mint a setup
capability.

Static and runtime boundary tests must enumerate this table, all private issuer names, direct
aliases, wrapped connections/cursors, subclass attempts, and every `store_`, `advance_`,
`retire_`, `claim_`, and `finalize_` export. A source method not in this table is a preflight stop,
not a defaulted capability choice.

### R12.6 Scope, proof, and stop rule

R12 adds only `tests/execution_core/persistence_setup_support.py` to section 8 and the active work
order's allowed paths. It adds no production path beyond those already named. The decisive future
tests include known-answer and byte-mutant controls for kinds `0x02`--`0x05`, primary-identity
cross-coordinate conflicts, passive-session refusal, lifecycle/receipt rollback, immutable
historical payload survival, unpaired-head refusal, outbox snapshot mismatch, and every capability
matrix bypass. Static DDL authoring remains allowed; installation and every SQLite-bearing test
remain stopped at the exact changed-DDL human gate.

No source or test implementation of R12 is authorized until a fresh `REV-0074` R12 documentation
review accepts the exact amendment candidate with `P0=0/P1=0`. The normal `REV-0075`
implementation review, changed-DDL human gate, no-runtime-composition rule, and all safety
boundaries remain independent and unchanged.

### R12-R1 independent-review remediation

The first fresh R12 review identified two additional relational requirements that must be frozen
before schema authoring. For `durable_input_semantic_key`, a table-local insert trigger must
enforce the already-required record rule at the database boundary:

- for authority kinds, `key_application_generation_id` and `key_scope_id` are non-null,
  `key_application_generation_id == input_application_generation_id`, and the owning
  `durable_input` row has exactly the same execution profile and `scope_id == key_scope_id`; and
- for venue kinds, both key coordinates are null and the owning durable-input row has the same
  execution profile and `VENUE_RECOVERY` domain.

The trigger runs in addition to the existing composite input foreign key and partial unique
indexes. Two otherwise-valid distinct application generations with a cross-bound authority key
must be rejected; this is the relational counterpart to the R9 record validation.

The decisive R12 test set also includes length-only mutants for all four document kinds,
an outbox-sequence-only mutant, one mutation for each receipt/outcome shared result member,
the cross-generation semantic-key rejection, a `test_persistence_input_receipt.py` setup-import
control, and both rejected/replayed genesis-bootstrap controls. These corrections add no source
or DDL execution authority; they remain subject to a fresh R12-R1 documentation review, the
normal REV-0075 implementation review, and the exact changed-DDL human gate.
