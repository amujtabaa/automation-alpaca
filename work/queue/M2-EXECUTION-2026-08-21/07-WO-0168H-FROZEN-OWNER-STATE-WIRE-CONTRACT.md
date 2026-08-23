# WO-0168h frozen owner-state wire and sealed-proof contract

Status: **PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE AUTHORITY**

Date: 2026-08-23

Accepted base: WO-0168a closeout `58f23ff9ea6d446379f7339075e1203c42a33e96`, tree
`163d89c1f32963ef2f17c952fe2a94940bf93eb3`.

This contract resolves the R13-H gap identified by the accepted R13/R13-R1 partition. It does not
authorize source changes until a fresh `REV-0076` verdict returns `ACCEPT` with `P0=0/P1=0`. It
does not authorize the R13-C outer envelope, persistence payload rows, changed-DDL installation,
or any SQLite-bearing test.

## 1. One bounded authority model

The complete checkpoint payload, not an SQL row and not a digest alone, owns the semantic values
that are absent from the accepted relational model. Repository-issued sealed proofs corroborate
the payload's exact application/profile/scope/currentness coordinates and selected immutable/current
rows. Each domain owner reconstructs its own opaque object, re-derives every seal, commitment,
index, count, and cross-reference, and then byte-compares a canonical re-projection.

There is no second reducer and no history replay. The checkpoint contains only:

1. fixed current scalars;
2. bounded current, active, or unresolved semantic rows;
3. exact proof rows needed to authenticate those values; and
4. derived commitments.

Audit ledgers, insertion order, and terminal history are excluded. A targeted late fact may add one
directly named retired-generation slice; it does not open an unbounded historical scan.

## 2. Canonical grammar

### 2.1 Scalar forms

All rows are exact JSON arrays. Objects, maps, floats, NaN, infinities, byte-order marks, and JSON
extensions are forbidden. Canonical JSON is UTF-8 from `json.dumps(..., ensure_ascii=True,
allow_nan=False, separators=(",", ":"))`; decode must re-encode and byte-compare.

The notation below is normative:

| Symbol | Exact representation |
| --- | --- |
| `I` | exact JSON integer; booleans are rejected; non-negative where the member says count, ordinal, epoch, quantity, or time |
| `B` | exact JSON `true` or `false` |
| `T` | nonblank NFC text with no C0/DEL control character |
| `X` | lowercase, even-length hexadecimal text for exact bytes |
| `H` | exactly 64 lowercase hexadecimal characters for 32 bytes |
| `N` | JSON `null`, used only where the schema says optional |
| `A(v)` | exact three-member durable atom `["1", TYPE_TAG, FIELDS]` produced by `encode_m1_value(v)` and re-decoded by `decode_m1_value` |
| `E(owner,v)` | exact two-member enum array `[owner, v.value]` |
| `R(tag,...)` | exact array `[tag, ...]`; its stated length includes the tag |
| `C(tag,rows)` | exact three-member array `[tag, len(rows), rows]` |

`A(v)` is admitted only for the closed WO-0165 durable type set. `X` permits empty bytes only where
the named owning constructor permits them; every commitment/digest uses `H`. Optional values use
`null`, never an empty string, zero, sentinel digest, empty array, or omitted member.

### 2.2 Closed reused semantic arrays

The following public values use the exact fixed arrays already frozen and implemented at the
accepted base by the named type-specific functions in `persistence/operations.py`; this list is
closed and is not permission for reflection or arbitrary object encoding:

- `PositionScope`, `ExecutionScope`, `BrokerFillFact`, `BrokerTradeCorrectFact`,
  `BrokerTradeBustFact`, and `HumanAttestedFillFact`;
- `BrokerEffectRequest`, `BeginManualFlatten`, `AcquisitionEffectTerms`,
  `ProtectionMandate`, and `AcquisitionMandate`; and
- their exact nested `Fraction`, `ExecutionGuard`, `EvidencePolicy`,
  `EmergencyRecoveryCompatibility`, `AcquisitionOrderTypes`, enum, durable-atom, and byte forms.

For each, the R13-H encoder must return the same JSON value as its exact `_encode_m2_*` function at
the accepted base, and decode through the matching exact `_decode_m2_*` constructor. A generic
dispatch registry, dataclass-field walk, `repr`, pickle, `asdict`, `__dict__`, or fallback encoder is
forbidden. R13-C may relocate shared pure codec helpers without changing their accepted bytes.

### 2.3 Enum spellings

Only these owner/value pairs are admitted by rows in this contract:

- `m1.authority.EnginePhase`: `BOOTSTRAPPING`, `RECONCILING`, `SERVING`;
- `m1.authority.TradingMode`: `ACTIVE`, `REDUCING`, `HALTED`;
- `m1.authority.SupervisorFence`: `UNAUTHENTICATED`, `RECONCILIATION_ONLY`,
  `PAPER_MUTATION_ELIGIBLE`;
- `m1.authority.FlattenPhase`: `WAITING`, `READY`, `SELL_CREATED`;
- `m1.authority.AcquisitionCurrentnessSourceKind`: `BOOTSTRAP`, `CANONICAL_FACT`,
  `AUTHORITY_MUTATION`, `PROTECTION_REBASE`;
- `m1.acquisition.AcquisitionRecoveryClass`: `NORMAL`, `RECONCILIATION_REQUIRED`,
  `MIXED_GENERATION_RECOVERY`, `MIXED_GENERATION_RECONCILIATION_REQUIRED`;
- `m1.acquisition.RouteKind`: `REQUEST`, `EFFECT`, `OWNER`, `ROOT`, `FACT`;
- `m1.venue.EffectKind`: `SUBMIT`, `CANCEL`, `REPLACE`;
- `m1.venue.BrokerEffectState`: `REQUESTED`, `CANCELED_BEFORE_DISPATCH`,
  `DISPATCH_CLAIMED`, `ACKNOWLEDGED`, `REJECTED`, `OUTCOME_UNKNOWN`, `NEEDS_REVIEW`,
  `OPERATOR_RECONCILED`;
- `m1.venue.AcceptanceSetState`: `OPEN`, `CLOSED`, `INVALIDATED`;
- `m1.venue.AcceptanceProofKind`: `NEVER_DISPATCHED`, `CONTRACT_COMPLETE_RESPONSE`,
  `COVERED_RECONCILIATION`;
- `m1.venue.VenueAttemptState`: `WORKING`, `PARTIALLY_FILLED`, `FILLED`, `CANCELED`,
  `REJECTED`, `EXPIRED`, `REPLACED`, `NEEDS_REVIEW`, `OPERATOR_RECONCILED`;
- `m1.venue.PendingVenueOperation`: `NONE`, `SUBMIT`, `CANCEL`, `REPLACE`;
- `m1.venue.VenueClosureKind`: `BROKER_TERMINAL`, `BROKER_ECONOMIC`,
  `OPERATOR_RECONCILED`;
- `m1.venue.VenueRecoveryDisposition`: `APPLIED`, `EXACT_REPLAY`, `CONFLICT`,
  `RECONCILIATION_REQUIRED`, `REFUSED`;
- `m1.venue.ProtectionTransitionSourceKind`: `ORDINARY`,
  `SERIAL_SUCCESSOR_ROLLOVER`;
- `m1.venue.BootstrapSourceKind`: `EMPTY_ACCOUNT`, `SAME_ACCOUNT_SOURCE`;
- `m1.venue.ResolvedProjectionKind`: `REGISTRY_ADVANCE`,
  `RECONCILIATION_CURSOR_ADVANCE`;
- `m1.position.BasisAuthority`: `AVAILABLE`, `BASIS_RECONCILIATION_PENDING`;
- `m1.fills.FactKind`: `FILL`, `TRADE_CORRECT`, `TRADE_BUST`;
- `m1.fills.ExecutionAuthority`: `BROKER_AUTHORITATIVE`, `HUMAN_ATTESTED`; and
- every other enum appearing inside a reused semantic array is restricted to the exact closed
  encoder/decoder pair named in section 2.2.

Unknown owner tags, aliases, case changes, integer substitutes, and unknown values fail.

### 2.4 Collection limits and ordering

Every variable collection uses `C(tag, rows)`. The declared count must equal the array length.
Rows are strictly increasing by the stated canonical key and duplicate keys fail. Comparison is
unsigned lexicographic comparison of the concatenated canonical identity bytes, with each component
encoded as `uint32-be(length) || UTF-8`; integer components use unsigned `uint64-be`.

Global hard limits are:

- at most 4,096 scope rows in one checkpoint;
- at most 65,535 rows in any other family;
- at most one directly targeted retired generation per scope;
- at most 256 children per persistent-map witness node; and
- at most `len(key_bytes) + 1` witness nodes.

These are refusal limits, not truncation instructions. A selected family above its limit cannot
produce a serving checkpoint. Pagination, partial snapshots, and silent dropping are forbidden.

## 3. Venue state

### 3.1 Complete 57-member classification

Every existing `VenueRecoveryBook` field appears exactly once:

| Class | Exact fields |
| --- | --- |
| payload scalar | `scope`; `_account_authority_epoch`; `_unresolved_account_execution_reconciliation_count`; `execution_registry_count`; `execution_registry_commitment`; `_registry_transition_head_commitment` |
| payload semantic row | `_effect_by_id`; `_authority_epoch_by_scope`; `_claim_by_effect`; `_owner_by_leg`; `_acquisition_correlation_by_root`; `_leg_current_by_leg`; `_closure_head_by_leg`; `_economic_high_water_by_leg`; `_human_coverage_by_root`; `_broker_coverage_by_root`; `_coverage_provenance_by_scope`; `_reconciliation_by_input`; `_execution_reconciliation_by_input`; `_execution_snapshot_by_scope`; `_bootstrap_bound_target_by_scope`; `_protection_cursor_by_scope` |
| derived index/count | `_effect_by_request_occurrence`; `_effect_by_client_order`; `_claim_by_occurrence`; `_leg_summary_by_effect`; `_cancel_target_reservation_by_leg`; `_authority_contribution_by_effect`; `_authority_summary_by_scope`; `_account_unclaimed_requested_effect_ids`; `_reconciliation_count_by_effect`; `_coverage_current_by_leg`; `_coverage_total_by_effect`; `_attributed_broker_root_count_by_scope`; `_human_interval_index`; `_human_broker_fact_index`; `_unresolved_reconciliation_count_by_leg`; `_canonical_revision_count_by_leg`; `_unresolved_execution_reconciliation_count_by_scope`; `_binding_by_scope` |
| omitted audit/history | `_effect_order`; `_contradiction_order_by_effect`; `_claim_order`; `_owner_order`; `_closure_ledger`; `_closure_by_id`; `_input_ledger`; `_input_by_id`; `_direct_input_by_semantic`; `_first_input_by_fact`; `_human_coverage_ledger`; `_broker_coverage_ledger`; `_reconciliation_ledger`; `_execution_reconciliation_ledger`; `_registry_transition_ledger`; `_binding_order`; `_protection_transition_ledger` |

The 6 + 16 + 18 + 17 entries above are all 57 fields. A new field added to the owner before R13-C
requires this contract to be revised and re-reviewed.

### 3.2 Exact venue state row

`_M2VenueState` is the exact 24-member array:

```text
["m2.venue.State/v1",
 VenueScope, account_authority_epoch,
 unresolved_account_execution_reconciliation_count,
 execution_registry_count_or_null, execution_registry_commitment_or_null,
 registry_transition_head_or_null,
 AuthorityEpochRows, EffectRows, ClaimRows, OwnerAttemptRows,
 AcquisitionCorrelationRows, ClosureHeadRows, EconomicHighWaterRows,
 HumanCoverageRows, BrokerCoverageRows, CoverageProvenanceRows,
 ReconciliationRows, ExecutionReconciliationRows, ExecutionScopeRows,
 BootstrapTargetRows, ProtectionCursorRows, direct_selection_commitment,
 state_commitment]
```

`VenueScope` is
`R("m2.venue.Scope/v1", A(generation), A(broker), A(environment), A(account))` (length 5).
The registry count/commitment pair is wholly null or `(I,H)`. The transition head is `N|H`.
`direct_selection_commitment` and `state_commitment` are `H` and are re-derived.

### 3.3 Venue semantic rows

All lengths include the tag.

| Collection and key | Exact row |
| --- | --- |
| `AuthorityEpochRows`, key `(broker,environment,account,symbol)` | `R("m2.venue.AuthorityEpoch/v1", PositionScope, I)` length 3 |
| `EffectRows`, key `effect_id` | `R("m2.venue.EffectCurrent/v1", VenueEffectScope, E(BrokerEffectState), E(AcceptanceSetState), A(claim_occurrence_id)\|N, AcceptanceProof\|N, ContradictionRows, operator_epoch\|N, account_epoch\|N)` length 9 |
| `ClaimRows`, key `effect_id` | `R("m2.venue.DispatchClaim/v1", A(effect_id), A(claim_occurrence_id))` length 3; the effect scope is resolved from `EffectRows` |
| `OwnerAttemptRows`, key `VenueLegKey` | `R("m2.venue.OwnerAttempt/v1", A(leg_key), A(effect_id), A(observation_id), VenueAttempt\|N)` length 5 |
| `AcquisitionCorrelationRows`, key `RootFillKey` | `R("m2.venue.AcquisitionCorrelation/v1", A(application_generation_id), PositionScope, A(request_occurrence_id), A(effect_id), A(leg_key), A(root_key))` length 7 |
| `ClosureHeadRows`, key `VenueLegKey` | `VenueTerminalClosure` below |
| `EconomicHighWaterRows`, key `VenueLegKey` | `R("m2.venue.EconomicHighWater/v1", A(leg_key), I(high_water))` length 3 |
| `HumanCoverageRows`, key `(RootFillKey,effect_id,leg_key)` | `HumanCoverage` below |
| `BrokerCoverageRows`, key `(RootFillKey,effect_id,leg_key)` | `BrokerCoverage` below |
| `CoverageProvenanceRows`, key `PositionScope` | `R("m2.venue.CoverageProvenance/v1", PositionScope, C("m2.venue.CoveredRoots/v1", ["m2.venue.CoveredRoot/v1",A(root_key),H(fact_commitment)]...), root_heads_commitment\|N)` length 4 |
| `ReconciliationRows`, key `VenueInputId` | tagged `FillReconciliation` or `RevisionReconciliation` below |
| `ExecutionReconciliationRows`, key `VenueInputId` | tagged `ResolvedRegistryProjection` or `UnresolvedRegistryAdvance` below |
| `ExecutionScopeRows`, key `PositionScope` | `R("m2.venue.ExecutionScopeCurrent/v1", ExecutionState, ExecutionProof, VenueExecutionCheckpoint)` length 4 |
| `BootstrapTargetRows`, key `PositionScope` | `BootstrapTarget` below |
| `ProtectionCursorRows`, key `PositionScope` | `R("m2.venue.ProtectionCursor/v1", PositionScope, I, H, A(mandate_id)\|N, H_execution_commitment\|N, VenueExecutionCheckpoint\|N)` length 7; the last two are wholly present or null |

Nested rows are exact:

```text
VenueEffectScope = ["m2.venue.EffectScope/v1", A(generation), A(broker),
 A(environment), A(account), A(effect_id), A(request_occurrence_id), A(mandate_id),
 E("m1.venue.EffectKind",kind), A(client_order_id)|N, A(symbol_id),
 E("m1.fills.ExecutionSide",side), A(quantity), X(economic_scope), A(target_leg_key)|N]

AcceptanceProof = ["m2.venue.AcceptanceProof/v1", E("m1.venue.AcceptanceProofKind",kind),
 A(effect_id), A(claim_occurrence_id)|N, A(evidence_reference), H(evidence_digest)]

ContradictionRows = ["m2.venue.Contradictions/v1", count,
 [["m2.venue.AcceptanceContradiction/v1",A(leg_key),A(observation_id)],...]]

VenueAttempt = ["m2.venue.Attempt/v1", A(leg_key),
 E("m1.venue.VenueAttemptState",status),
 E("m1.venue.PendingVenueOperation",pending_operation), A(cumulative_quantity),
 A(last_observation_id)]

VenueTerminalClosure = ["m2.venue.TerminalClosure/v1", A(leg_key), A(closure_id), I(ordinal),
 A(predecessor_closure_id)|N, E("m1.venue.VenueAttemptState",status),
 A(cumulative_quantity), A(observed_cumulative_quantity), A(evidence_reference),
 E("m1.venue.VenueClosureKind",kind), A(source_input_id), A(observation_id)|N,
 A(source_event_id)|N, E("m1.venue.VenueAttemptState",broker_terminal_state)|N,
 A(actor)|N, T(reason)|N, H(evidence_digest)|N]

HumanCoverage = ["m2.venue.HumanCoverage/v1", A(effect_id), A(leg_key),
 HumanAttestedFillFact, A(source_input_id), B(broker_corroborated),
 BrokerFillFact|N, H(broker_evidence_digest)|N, A(broker_source_input_id)|N]

BrokerCoverage = ["m2.venue.BrokerCoverage/v1", A(effect_id), A(leg_key),
 A(prior_cumulative_quantity), A(resulting_cumulative_quantity), BrokerFillFact,
 H(evidence_digest), A(root_source_input_id), BrokerExecutionFact,
 H(head_evidence_digest), A(head_source_input_id), B(mapping_exact)]

FillReconciliation = ["m2.venue.FillReconciliation/v1", A(input_id), A(effect_id),
 A(leg_key), A(prior_cumulative_quantity), A(resulting_cumulative_quantity),
 BrokerFillFact, H(evidence_digest), T(reason)]

RevisionReconciliation = ["m2.venue.RevisionReconciliation/v1", A(input_id), A(effect_id),
 A(leg_key), A(prior_root_quantity), A(prior_venue_cumulative_quantity),
 A(resulting_venue_cumulative_quantity), BrokerTradeCorrectFact|BrokerTradeBustFact,
 H(evidence_digest), B(canonical_applied), T(reason)]

VenueExecutionCheckpoint = ["m2.venue.ExecutionCheckpoint/v1", PositionScope, I(registry_count),
 H(registry_commitment), H(position_commitment), H(root_heads_commitment), I(integrity_bits),
 B(account_reconciliation_required), I(reconciliation_transition_count),
 H(reconciliation_transition_head)]

ResolvedRegistryProjection = ["m2.venue.ResolvedRegistryProjection/v1", A(input_id),
 H(command_commitment), VenueExecutionCheckpoint, VenueExecutionBinding,
 I(resulting_registry_count), H(resulting_registry_commitment), T(reason),
 T(projection_kind)]

UnresolvedRegistryAdvance = ["m2.venue.UnresolvedRegistryAdvance/v1", A(input_id),
 H(command_commitment), VenueExecutionCheckpoint, I(prior_account_registry_count),
 H(prior_account_registry_commitment), VenueExecutionBinding, VenueExecutionBinding,
 I(resulting_registry_count), H(resulting_registry_commitment), T(reason)]

VenueExecutionBinding = ["m2.venue.ExecutionBinding/v1", PositionScope,
 H(position_commitment), H(root_heads_commitment), I(integrity_bits)]
```

`BootstrapTarget` is a closed discriminated union. Active form has 24 semantic members, in source
order, from `_BootstrapBoundTargetRecord`: application generation; position scope; source kind;
source/genesis/target execution commitments; `VenueExecutionBinding`; account registry count and
commitment; reconciliation transition count/head; bootstrap input ID/commitment; immutable
bootstrap target execution/count/commitment/transition-count/transition-head; bootstrap neutral
proof commitment and full `ProtectionTransitionProof`; checkpoint input ID/command commitment;
neutral proof commitment and full `ProtectionTransitionProof`. The map seal, commitment, and seal
are derived and absent from bytes. Its tag is `m2.venue.BootstrapTargetActive/v1` and length is 25.
Consumed form is length 6:
`["m2.venue.BootstrapTargetConsumed/v1", ActiveForm, A(effect_id),
A(request_occurrence_id), A(request_input_id), H(effect_scope_commitment)]`.
All retained seals and commitments are re-derived and compared, never trusted.

`ProtectionTransitionProof` is the exact length-25 array:

```text
["m2.venue.ProtectionTransitionProof/v1", PositionScope,
 ProtectionCursor, ProtectionCursor, VenueScope, VenueScope,
 H(predecessor_book_commitment), H(book_commitment),
 H(predecessor_execution_commitment), H(execution_commitment),
 VenueExecutionCheckpoint, VenueExecutionCheckpoint,
 SymbolAuthoritySummary, SymbolAuthoritySummary,
 VenueExecutionBinding|N, VenueExecutionBinding|N,
 B(predecessor_execution_binding_matches), B(execution_binding_matches),
 B(predecessor_account_reconciliation_clear), B(account_reconciliation_clear),
 H(command_commitment), E("m1.venue.VenueRecoveryDisposition",disposition),
 I(quantity_delta), E("m1.venue.ProtectionTransitionSourceKind",source_kind),
 H(source_binding)]
```

`ProtectionCursor` is the length-6 semantic array
`["m2.venue.ProtectionTransitionCursor/v1",I(ordinal),H(head),A(mandate_id)|N,
H(execution_commitment)|N,VenueExecutionCheckpoint|N]`; the last two members are wholly present
or null. `SymbolAuthoritySummary` is
`["m2.venue.SymbolAuthoritySummary/v1",I(effect_count),I(blocking_effect_count),
I(blocking_buy_effect_count),I(stand_downable_buy_count),
C("m2.venue.StandDownEffects/v1",A(effect_id)...),
C("m2.venue.CancellableBuyLegs/v1",A(leg_key)...),
C("m2.venue.CancelPendingBuyLegs/v1",A(leg_key)...),
I(waiting_buy_parent_count),I(unknown_buy_effect_count)]` (length 10).
No nested map or audit ledger is admitted.

### 3.4 Venue selection completeness

For the selected application generation, execution profile, and scope, `EffectRows` is exactly the
set satisfying:

```text
disposition <> CLOSED
OR EXISTS owner WHERE owner.effect_id = effect.effect_id
                    AND owner.admitted_after_effect_closed = true
```

It includes unresolved predecessor-generation effects that still satisfy the predicate. Claims,
owners, attempts, closure heads, coverage, reconciliations, bindings, bootstrap targets, and cursors
are the exact rows reachable from that set or from a selected current scope. Every reference must
resolve exactly once. A terminal unrelated row is forbidden; a required reachable row missing from
the payload is forbidden. Selection uses canonical external identities, never internal SQL row IDs.

## 4. Authority state

### 4.1 Complete 20-member classification

| Class | Exact fields |
| --- | --- |
| payload scalar | `phase`; `mode`; `supervisor_fence`; `kill_engaged`; `session_id`; `budget`; `_emergency_grant` |
| sealed owner reference | `venue` |
| payload semantic row | `_effect_authority_by_id`; `_manual_by_id`; `_acquisition_currentness_by_scope`; `_acquisition_descriptor_by_scope`; `_acquisition_active_by_scope` |
| derived index | `_claim_by_effect`; `_claim_by_occurrence`; `_manual_flatten_by_scope`; `_acquisition_descriptor_by_effect` |
| omitted direct/history | `_input_by_id`; `_query_by_id`; `_consumed_grant_ids` |

These 7 + 1 + 5 + 4 + 3 entries are all 20 fields.

### 4.2 Exact authority state and rows

`_M2AuthorityState` is the exact 14-member array:

```text
["m2.authority.State/v1", E(EnginePhase), E(TradingMode), E(SupervisorFence),
 B(kill_engaged), A(session_id)|N,
 ["m2.authority.RequestBudget/v1",I(remaining),I(safety_reserve)],
 VenueRef, EmergencyGrant|N, EffectAuthorizationRows, ManualRows,
 AcquisitionSlotRows, direct_selection_commitment, state_commitment]
```

`VenueRef` is length 7:
`["m2.authority.VenueRef/v1",A(application_generation_id),A(broker),A(environment),
A(account),H(venue_state_commitment),H(venue_proof_commitment)]`.

`EffectAuthorizationRows` is keyed by `effect_id`. Each exact length-6 row is
`["m2.authority.EffectAuthorization/v1", BrokerEffectRequest, A(session_id),
A(manual_flatten_id)|N, A(emergency_grant_id)|N, ClaimRow|N]`.
`ClaimRow` is either exact `ClaimEffect` or exact `ClaimAcquisitionEffect`, encoded by the accepted
operation codec and required to name the same effect and canonical occurrence.

`ManualRows` is keyed by `flatten_id`. Each row is
`["m2.authority.ManualFlatten/v1", BeginManualFlatten,
E("m1.authority.FlattenPhase",phase), C("m2.authority.CancelEffects/v1",A(effect_id)...),
A(sell_effect_id)|N]` (length 5). Cancel effects are strictly ordered by effect ID.

`EmergencyGrant` is
`["m2.authority.EmergencyGrant/v1",A(grant_id),A(account),A(symbol_id),A(session_id),
A(actor),T(reason),A(evidence_reference)]` (length 8).

`AcquisitionSlotRows` is keyed by `PositionScope`; one row owns all formerly duplicated scope maps:

```text
["m2.authority.AcquisitionSlot/v1", PositionScope,
 Currentness,
 ["m2.authority.AcquisitionDescriptorActive/v1", AcquisitionEffectPermit]|
 ["m2.authority.AcquisitionDescriptorInactive/v1", A(predecessor_effect_id),
  H(predecessor_descriptor_commitment), A(successor_generation_id)] | null,
 ["m2.authority.AcquisitionActive/v1",A(effect_id),H(descriptor_commitment)] |
 ["m2.authority.AcquisitionInactive/v1",A(predecessor_effect_id),
  H(predecessor_descriptor_commitment),A(successor_generation_id)] | null]
```

`Currentness` is the exact source-order array of the 15 semantic members of
`_AcquisitionCurrentnessEntry` before derived `commitment` and `_seal`, tagged
`m2.authority.AcquisitionCurrentness/v1`: source kind, application generation, position scope,
session, generation, acquisition mandate, protection mandate, binding commitment, compatibility
commitment, controller head, successor ordinal, scope execution commitment, venue commitment,
optional protection commitment, and predecessor-slot commitment. Commitment and seal are absent
from bytes and re-derived.

```text
["m2.authority.AcquisitionCurrentness/v1",
 E("m1.authority.AcquisitionCurrentnessSourceKind",source_kind),
 A(application_generation_id), PositionScope, A(session_id), A(generation_id),
 A(acquisition_mandate_id), A(protection_mandate_id), H(binding_commitment),
 H(emergency_recovery_compatibility_commitment), H(controller_head), I(successor_ordinal),
 H(scope_execution_commitment), H(venue_commitment), H(protection_commitment)|N,
 H(predecessor_slot_commitment)]
```

`AcquisitionEffectPermit` is tagged `m2.authority.AcquisitionEffectPermit/v1` and contains its
first 21 semantic members in source order before derived `commitment` and `_seal`:
input/application/scope/session/generation and
mandate identities; binding and compatibility commitments; predecessor/current controller heads;
successor ordinal; execution/scope/venue/authority/protection commitments; exact
`AcquisitionEffectTerms`; and effect/request/client identities. Length 22 including the tag.
Permit, descriptor, active, and inactive commitments and seals are absent from bytes and re-derived.

Unseen scope is represented by no slot row. A present slot cannot omit currentness. Descriptor and
active values are both null for no admitted effect, both active for a current effect, or both the
same inactive predecessor/successor triple. Mixed variants, orphan descriptor/effect indexes, and
defaulted nulls fail.

## 5. Acquisition state

### 5.1 Complete 13-member classification

| Class | Exact fields |
| --- | --- |
| payload scalar/current | `application_generation_id`; `position_scope`; `scope_execution_commitment`; `venue_commitment`; `authority_context_commitment`; `protection_commitment`; `controller_commitment`; `_controller`; `_mandate` |
| bounded semantic rows | `registry`; `lineage` |
| derived | `commitment`; `_seal` |

The registry wire contains only LIVE, optional directly targeted retired, and optional active stream
route. The lineage wire contains only current/active/unresolved routes plus directly targeted
late-fact routes. The owner's existing full-history registry/lineage seals are not reused as bounded
state commitments.

### 5.2 Exact acquisition state

`_M2AcquisitionState` is the exact 17-member array:

```text
["m2.acquisition.State/v1", A(application_generation_id), PositionScope,
 H(scope_execution_commitment), H(venue_commitment), H(authority_context_commitment),
 H(protection_commitment)|N, Controller, AcquisitionMandate,
 GenerationLive, GenerationTargetedRetired|N, MarketStreamRoute|N,
 LineageRows, direct_selection_commitment, bounded_registry_commitment,
 bounded_lineage_commitment, state_commitment]
```

`Controller` is the exact source-order semantic array
`["m2.acquisition.Controller/v1", A(application_generation_id),PositionScope,H(controller_head),
I(successor_ordinal),A(live_generation_id)|N,E(AcquisitionRecoveryClass),
H(scope_execution_commitment),H(venue_commitment),H(authority_context_commitment),
H(protection_commitment)|N,H(binding_commitment),H(compatibility_commitment),H(commitment)]`.
The private seal is re-derived.

`AcquisitionMandate` is the exact accepted array from section 2.2. Its binding, protection mandate,
compatibility, and every terms commitment are re-derived and cross-checked with `Controller`.

Generation rows are:

```text
["m2.acquisition.Generation/v1", A(generation_id), A(application_generation_id),
 PositionScope, I(successor_ordinal), H(dual_mandate_binding_commitment),
 H(predecessor_or_genesis_head_commitment), H(emergency_compatibility_commitment),
 H(economics_head_commitment), T(serving_class), H(closure_summary_commitment), H(commitment)]
```

The LIVE row is mandatory when controller `live_generation_id` is non-null and absent otherwise.
The targeted-retired row is present only when the operation proof names a late fact or unresolved
predecessor-generation route. It must differ from LIVE. The active stream route is
`["m2.acquisition.MarketStreamRoute/v1",A(stream_generation_id),A(generation_id),H(commitment)]`
and must resolve to the LIVE row.

Each lineage row is length 5:
`["m2.acquisition.LineageRoute/v1",E("m1.acquisition.RouteKind",kind),Identity,A(generation_id),
H(commitment)]`. `Identity` is `A(request_occurrence_id)`, `A(effect_id)`, `A(venue_leg_key)`,
`A(root_fill_key)`, or `A(execution_fact_key)` according to family. Family order is exactly REQUEST,
EFFECT, OWNER, ROOT, FACT; within a family it is the canonical identity-byte order from section
2.4. Python `repr` is never wire authority.

`bounded_registry_commitment`, `bounded_lineage_commitment`, and `state_commitment` use the new
domains `execution-core/m2-acquisition/bounded-registry/v1`,
`execution-core/m2-acquisition/bounded-lineage/v1`, and
`execution-core/m2-acquisition/state/v1`. They bind the canonical row bytes and counts. They do not
claim equality with history-shaped `GenerationRegistry._seal`, `AcquisitionLineageIndex._seal`, or
the old full-map `AcquisitionControllerState.commitment`.

## 6. Execution proof encoding

`_M2ExecutionObservationProof` is exactly:

```text
["m2.position.ExecutionObservationProof/v1",
 H(state_commitment), H(root_heads_commitment), H(seen_facts_commitment),
 H(root_head_map_commitment), H(seen_fact_map_commitment), H(root_claim_map_commitment),
 BrokerExecutionFact, SeenFact|N, RootHead|N, SeenFact|N, B(root_claimed),
 PersistentMapWitness, PersistentMapWitness, PersistentMapWitness|N,
 PersistentMapWitness, H(proof_commitment)]
```

Length is 17. `SeenFact` is
`["m2.position.SeenFact/v1",BrokerExecutionFact,E("m1.fills.FirstObservationClassification",v),
PositionScope|N]`. `RootHead` is the exact 12-member semantic source-order row tagged
`m2.position.RootHead/v1`: root key, original sequence, execution scope, execution authority,
current source-event ID, fact kind, quantity, optional price, prefix-heads commitment,
prefix-proof commitment, and re-derived row commitment.

`PersistentMapWitness` is
`["m2.position.PersistentMapWitness/v1",X(key_bytes),I(map_size),
C("m2.position.WitnessNodes/v1",nodes)]`. A node is
`["m2.position.WitnessNode/v1",B(has_value),H(value_commitment)|N,
C("m2.position.WitnessChildren/v1",children)]`; a child is
`["m2.position.WitnessChild/v1",I(byte_label),H(child_commitment)]`. Child labels are 0..255 and
strictly increasing. The path and branching limits in section 2.4 are mandatory.

Decode reconstructs the exact owner proof through its owner-only constructor, rechecks all four
witnesses against the three aggregate map commitments, re-derives the proof commitment, and
byte-compares. An absent predecessor witness is legal only where the fact has no predecessor.

## 7. Protection proof encoding

`_M2ProtectionAuthorityProof._CurrentRows` is exactly:

```text
["m2.protection.CurrentRows/v1", A(application_generation_id), T(execution_profile_id),
 T(market_source_profile_id), I(scope_id), PositionScope,
 I(controller_currentness_head_ordinal), A(live_acquisition_generation_id)|N,
 T(authority_class), A(active_stream_generation_id),
 A(active_acquisition_generation_id)|N, H(active_generation_mandate_commitment),
 T(active_source_profile_id), A(active_session_id),
 E("m1.protection.MarketSequenceMode",active_sequence_mode),
 I(expected_controller_head_ordinal), H(state_commitment), I(version_ordinal),
 A(market_source_id)]
```

Length is 19. The proof is
`["m2.protection.AuthorityProof/v1", CurrentRows, H(proof_commitment)]` (length 3).
Only the checkpoint-codec issuer may mint `_CurrentRows`; the protection owner re-derives the seal
and verifies source/profile/session/stream, live generation, mandate, state commitment, expected
controller head, currentness head, and version before construction. The current rows are not a
caller-shaped tuple and cannot be detached from their repository proof binding.

## 8. Repository-issued owner proofs

Each owner proof is an opaque exact type. Its canonical row is:

```text
[OWNER_PROOF_TAG,
 A(application_generation_id), T(execution_profile_id),
 T(market_source_profile_id)|N, I(currentness_head_ordinal), I(checkpoint_version_ordinal),
 H(owner_state_bytes_sha256), H(owner_state_commitment),
 C(FAMILY_COUNTS_TAG, [[family_tag,count,predicate_tag,family_rows_commitment],...]),
 C(DIRECT_ROWS_TAG, exact_direct_rows),
 C(ABSENCE_ROWS_TAG, exact_negative_lookup_coordinates),
 H(proof_commitment)]
```

The owner-state byte digest is deliberately not the future outer checkpoint digest: binding a proof
contained inside that checkpoint to the checkpoint's own digest would be circular. R13-C binds the
already sealed owner state/proof bytes into the outer payload and derives the outer digest last.

The three tags are `m2.venue.ObservationProof/v1`,
`m2.authority.ObservationProof/v1`, and `m2.acquisition.ObservationProof/v1`. Family-count rows are
strictly ordered by the family order declared in this contract. `predicate_tag` is one of:
`CURRENT_SCOPE_V1`, `ACTIVE_OR_UNRESOLVED_EFFECT_V1`, `REACHABLE_OWNER_V1`,
`CURRENT_HEAD_V1`, `TARGETED_LATE_FACT_V1`, `ACTIVE_AUTHORITY_V1`,
`LIVE_GENERATION_V1`, or `ACTIVE_LINEAGE_V1`. Direct rows use the exact accepted typed persistence
record arrays frozen in WO-0167/R13-S, not caller dictionaries. Negative rows bind a complete direct
key and the sealed absent result.

The issuer must bind one connection snapshot and verify:

1. application generation, profiles, scope, current controller head, and checkpoint version;
2. exact family counts and selection predicates;
3. every positive direct row and required negative lookup;
4. every payload row's direct coordinates and digest-bearing semantic bytes;
5. currentness equality across kernel, controller, acquisition, execution, protection, and market;
6. the owner's canonical state bytes and commitment; and
7. proof commitment over all preceding members.

R13-H implements owner proof types and owner reconstruction only. Repository issuance and the outer
payload binding remain R13-C; tests in R13-H use owner-owned authentic reference projection, never a
public proof constructor or forged tuple.

## 9. Owner construction equivalence

Construction order is fixed:

1. validate exact runtime types and scalar grammar;
2. validate counts, limits, order, uniqueness, and closed tags;
3. construct leaf values through their owning constructors;
4. validate the sealed direct proof and all cross-owner coordinates;
5. install payload-owned base rows;
6. rebuild venue indexes in this order: effect indexes, claim indexes, owner/current-leg summaries,
   cancel reservations, authority summaries, coverage indexes, reconciliation counts, execution
   bindings, bootstrap targets, protection cursors;
7. rebuild authority indexes in this order: effect claims, manual scope, acquisition descriptor by
   effect, acquisition active/currentness coherence;
8. rebuild acquisition bounded registry and lineage, then its controller/mandate binding;
9. re-derive all owner commitments and seals; and
10. project canonical rows again and require byte equality.

Owner-local constructors are the only allocation seams:

- venue: `_m2_venue_state_from_book` and `_m2_venue_state_from_direct_proof`;
- authority: `_m2_authority_state_from_reference` and `_m2_authority_state_from_direct_proof`;
- acquisition: `_m2_acquisition_state_from_reference` and
  `_m2_acquisition_state_from_direct_proof`; and
- existing execution/protection constructors named by the R13 predecessor.

`object.__new__` is permitted only inside the owning verified constructor. No codec, repository,
unit of work, or caller may allocate an opaque owner.

## 10. Genesis and edge cases

- Authority genesis is exactly `BOOTSTRAPPING`, `HALTED`, `UNAUTHENTICATED`, kill engaged, no
  session, zero normal/reserve budget, empty matching venue, empty row collections, and no grant.
- Empty venue collections are legal only when all six scalars and proof counts establish an empty
  matching account/scope state.
- Optional pairs/groups are atomic; partial optional groups fail.
- An unresolved predecessor-generation effect remains selected with its exact directly targeted
  retired generation and reachable routes.
- One targeted late broker fact may add its exact FACT/ROOT/OWNER lineage and retired generation.
  It cannot admit unrelated retired rows.
- Header-only payloads, state commitment without bytes, proof commitment without direct rows,
  history-shaped maps, terminal unrelated rows, and truncated over-limit families are non-serving.

## 11. Failure-capable implementation proof

R13-H tests must kill at least these independent mutants for every applicable owner:

1. missing, extra, reordered, duplicated, and wrong-tag row;
2. count mismatch and over-limit family;
3. same-digest/different-bytes or commitment-only substitution;
4. substituted application/profile/scope/session/generation/currentness/version;
5. omitted unresolved predecessor effect and unrelated terminal-history inclusion;
6. forged proof type, forged seal, stale direct row, and absent required negative lookup;
7. derived-index bytes added to the payload or one derived index not rebuilt;
8. cross-effect claim, cross-owner closure/coverage, cross-scope execution/protection row;
9. generation route using `repr`, wrong family order, or unselected generation;
10. malformed witness path, child order, map size, membership, and nonmembership;
11. header-only checkpoint accepted as owner state; and
12. a second reducer branch or generic serializer introduced.

Positive proof includes exact genesis and nontrivial reducer-produced states with active effect,
claim, owner attempt, closure head, coverage/reconciliation, execution/protection proofs, active
authority/manual/acquisition slot, LIVE generation, stream route, and targeted late-fact cases.
Imports remain inert. R13-H tests are pure and open no SQLite connection.

## 12. Boundary to R13-C

R13-H ends with authentic typed owner projection/hydration and complete proof row encodings. It does
not create `RuntimeCheckpointEnvelope`, payload persistence records, store/load methods, head
eligibility, or transaction composition. R13-C must bind these accepted owner values into the exact
kind-`0x02` document, add repository issuance on one connection, and return the exact changed-DDL
candidate identity for Ameen Mujtabaa's fresh gate before any changed schema is installed or any
SQLite-bearing test executes.
