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
| `Z` | exact signed JSON integer; booleans are rejected; used only for position raw quantity and economic deltas |
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
- `m1.acquisition.GenerationRouteKind`: `REQUEST`, `EFFECT`, `OWNER`, `ROOT`, `FACT`;
- `m1.acquisition.GenerationServingClass`: `LIVE`, `RETIRED_UNSERVING`,
  `RECONCILIATION_REQUIRED`;
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
- `m2.protection.AuthorityClass`: `NORMAL`, `HARD_BAIL`;
- `m1.position.BasisAuthority`: `AVAILABLE`, `BASIS_RECONCILIATION_PENDING`;
- `m1.fills.ExecutionSide`: `BUY`, `SELL`;
- `m1.fills.FirstObservationClassification`: `APPLIED_AVAILABLE`,
  `APPLIED_BASIS_PENDING`, `APPLIED_OVERFILL_QUARANTINE`,
  `APPLIED_PENDING_OVERFILL`, `CORROBORATED_ZERO_ECONOMIC`,
  `RECONCILIATION_REQUIRED`;
- `m1.fills.FactKind`: `FILL`, `TRADE_CORRECT`, `TRADE_BUST`;
- `m1.fills.ExecutionAuthority`: `BROKER_AUTHORITATIVE`, `HUMAN_ATTESTED`; and
- `m1.protection.MarketSequenceMode`: `SEQUENCED`, `SOURCE_TIME`;
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

### 2.5 Commitment construction

For every new R13-H commitment, `K(domain,row)` means the existing length-framed SHA-256
`_commit_parts(domain, canonical_json_utf8(row))`. A row that carries its own derived commitment
is committed with that final member omitted. Collection commitments cover the complete
count-bearing wrapper, not a concatenation with implicit boundaries.

The closed new domains are:

| Value | Domain |
| --- | --- |
| venue direct selection / state / transition proof / observation proof | `execution-core/m2-venue/direct-selection/v1`; `execution-core/m2-venue/state/v1`; `execution-core/m2-venue/transition-proof/v1`; `execution-core/m2-venue/observation-proof/v1` |
| authority direct selection / state / observation proof | `execution-core/m2-authority/direct-selection/v1`; `execution-core/m2-authority/state/v1`; `execution-core/m2-authority/observation-proof/v1` |
| acquisition direct selection / bounded registry / bounded lineage / state / observation proof | `execution-core/m2-acquisition/direct-selection/v1`; `execution-core/m2-acquisition/bounded-registry/v1`; `execution-core/m2-acquisition/bounded-lineage/v1`; `execution-core/m2-acquisition/state/v1`; `execution-core/m2-acquisition/observation-proof/v1` |

Existing M1 commitments, execution proof commitments, protection proof commitments, and exact
private-row seals keep their current owner domains and constructors. A digest is checked only after
all semantic bytes needed to re-derive it are present.

The dependency graph is acyclic and evaluated only in this order:

1. canonical leaf atoms/enums/scalars and owner-existing semantic commitments;
2. semantic rows with their derived private commitments omitted;
3. M2 venue-transition proofs and bootstrap-target rows;
4. count-bearing collection wrappers and per-family row commitments;
5. owner direct-selection commitment;
6. acquisition bounded-registry and bounded-lineage commitments;
7. owner state commitment over the state row with only its final state commitment omitted;
8. owner-state byte digest, then owner observation-proof commitment over the proof row with only
   its final proof commitment omitted; and
9. in R13-C only, scope-component commitment, complete outer payload bytes, then outer payload
   digest.

No value may include itself, a later value, or the future outer digest in its preimage.

## 3. Venue state

### 3.1 Complete 57-member classification

Every existing `VenueRecoveryBook` field appears exactly once:

| Class | Exact fields |
| --- | --- |
| payload scalar | `scope`; `_account_authority_epoch`; `_unresolved_account_execution_reconciliation_count`; `execution_registry_count`; `execution_registry_commitment`; `_registry_transition_head_commitment` |
| payload semantic row | `_effect_order` as bounded source ordinal on each retained effect; `_effect_by_id`; `_authority_epoch_by_scope`; `_claim_by_effect`; `_owner_order` as bounded source ordinal on each retained owner; `_owner_by_leg`; `_acquisition_correlation_by_root`; `_leg_current_by_leg`; `_closure_head_by_leg`; `_economic_high_water_by_leg`; `_human_coverage_by_root`; `_broker_coverage_by_root`; `_coverage_provenance_by_scope`; `_reconciliation_by_input`; `_execution_reconciliation_by_input`; `_execution_snapshot_by_scope`; `_bootstrap_bound_target_by_scope`; `_protection_cursor_by_scope` |
| derived index/count | `_effect_by_request_occurrence`; `_effect_by_client_order`; `_contradiction_order_by_effect` rebuilt from each retained effect's contradiction rows; `_claim_by_occurrence`; `_leg_summary_by_effect`; `_cancel_target_reservation_by_leg`; `_authority_contribution_by_effect`; `_authority_summary_by_scope`; `_account_unclaimed_requested_effect_ids`; `_reconciliation_count_by_effect`; `_coverage_current_by_leg`; `_coverage_total_by_effect`; `_attributed_broker_root_count_by_scope`; `_human_interval_index`; `_human_broker_fact_index`; `_unresolved_reconciliation_count_by_leg`; `_canonical_revision_count_by_leg`; `_unresolved_execution_reconciliation_count_by_scope`; `_binding_by_scope` |
| omitted audit/history | `_claim_order`; `_closure_ledger`; `_closure_by_id`; `_input_ledger`; `_input_by_id`; `_direct_input_by_semantic`; `_first_input_by_fact`; `_human_coverage_ledger`; `_broker_coverage_ledger`; `_reconciliation_ledger`; `_execution_reconciliation_ledger`; `_registry_transition_ledger`; `_binding_order`; `_protection_transition_ledger` |

The 6 + 18 + 19 + 14 entries above are all 57 fields. A new field added to the owner before R13-C
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
| `EffectRows`, key `effect_id` | `R("m2.venue.EffectCurrent/v1", I(source_ordinal), VenueEffectScope, E(BrokerEffectState), E(AcceptanceSetState), A(claim_occurrence_id)\|N, AcceptanceProof\|N, ContradictionRows, operator_epoch\|N, account_epoch\|N)` length 10 |
| `ClaimRows`, key `effect_id` | `R("m2.venue.DispatchClaim/v1", A(effect_id), A(claim_occurrence_id))` length 3; the effect scope is resolved from `EffectRows` |
| `OwnerAttemptRows`, key `VenueLegKey` | `R("m2.venue.OwnerAttempt/v1", I(source_ordinal), A(leg_key), A(effect_id), A(observation_id), VenueAttempt\|N)` length 6 |
| `AcquisitionCorrelationRows`, key `RootFillKey` | `R("m2.venue.AcquisitionCorrelation/v1", A(application_generation_id), PositionScope, A(request_occurrence_id), A(effect_id), A(leg_key), A(root_key))` length 7 |
| `ClosureHeadRows`, key `VenueLegKey` | `VenueTerminalClosure` below |
| `EconomicHighWaterRows`, key `VenueLegKey` | `R("m2.venue.EconomicHighWater/v1", A(leg_key), I(high_water))` length 3 |
| `HumanCoverageRows`, key `(RootFillKey,effect_id,leg_key)` | `HumanCoverage` below |
| `BrokerCoverageRows`, key `(RootFillKey,effect_id,leg_key)` | `BrokerCoverage` below |
| `CoverageProvenanceRows`, key `PositionScope` | `R("m2.venue.CoverageProvenance/v1", PositionScope, C("m2.venue.CoveredRoots/v1", ["m2.venue.CoveredRoot/v1",A(root_key),H(fact_commitment)]...), root_heads_commitment\|N)` length 4 |
| `ReconciliationRows`, key `VenueInputId` | tagged `FillReconciliation` or `RevisionReconciliation` below |
| `ExecutionReconciliationRows`, key `VenueInputId` | tagged `ResolvedRegistryProjection` or `UnresolvedRegistryAdvance` below |
| `ExecutionScopeRows`, key `PositionScope` | `R("m2.venue.ExecutionScopeCurrent/v1", ExecutionState, VenueExecutionCheckpoint)` length 3 |
| `BootstrapTargetRows`, key `PositionScope` | `BootstrapTarget` below |
| `ProtectionCursorRows`, key `PositionScope` | `R("m2.venue.ProtectionCursor/v1", PositionScope, I, H, A(mandate_id)\|N, H_execution_commitment\|N, VenueExecutionCheckpoint\|N)` length 7; the last two are wholly present or null |

The collection wrappers above are literal and closed:

| Symbolic collection | Literal `C` tag |
| --- | --- |
| `AuthorityEpochRows` | `m2.venue.AuthorityEpochs/v1` |
| `EffectRows` | `m2.venue.Effects/v1` |
| `ClaimRows` | `m2.venue.Claims/v1` |
| `OwnerAttemptRows` | `m2.venue.OwnerAttempts/v1` |
| `AcquisitionCorrelationRows` | `m2.venue.AcquisitionCorrelations/v1` |
| `ClosureHeadRows` | `m2.venue.ClosureHeads/v1` |
| `EconomicHighWaterRows` | `m2.venue.EconomicHighWaters/v1` |
| `HumanCoverageRows` | `m2.venue.HumanCoverages/v1` |
| `BrokerCoverageRows` | `m2.venue.BrokerCoverages/v1` |
| `CoverageProvenanceRows` | `m2.venue.CoverageProvenances/v1` |
| `ReconciliationRows` | `m2.venue.Reconciliations/v1` |
| `ExecutionReconciliationRows` | `m2.venue.ExecutionReconciliations/v1` |
| `ExecutionScopeRows` | `m2.venue.ExecutionScopes/v1` |
| `BootstrapTargetRows` | `m2.venue.BootstrapTargets/v1` |
| `ProtectionCursorRows` | `m2.venue.ProtectionCursors/v1` |

Each wrapper is exactly `[literal_tag,count,rows]`, uses the key and ordering declared in the
semantic-row table, and has the sole empty form `[literal_tag,0,[]]`. Unknown or substituted tags,
count mismatches, alternate empty forms, and rows outside strict key order fail.

Nested rows are exact:

```text
VenueEffectScope = ["m2.venue.EffectScope/v1", A(generation), A(broker),
 A(environment), A(account), A(effect_id), A(request_occurrence_id), A(mandate_id),
 E("m1.venue.EffectKind",kind), A(client_order_id)|N, A(symbol_id),
 E("m1.fills.ExecutionSide",side), A(quantity), X(economic_scope), A(target_leg_key)|N]

AcceptanceProof = ["m2.venue.AcceptanceProof/v1", E("m1.venue.AcceptanceProofKind",kind),
 A(effect_id), A(claim_occurrence_id)|N, A(evidence_reference), H(evidence_digest)]

ContradictionRows = ["m2.venue.Contradictions/v1", count,
 [["m2.venue.AcceptanceContradiction/v1",I(source_evidence_ordinal),
   A(leg_key),A(observation_id)],...]]

VenueAttempt = ["m2.venue.Attempt/v1", A(leg_key),
 E("m1.venue.VenueAttemptState",status),
 E("m1.venue.PendingVenueOperation",pending_operation)|N, A(cumulative_quantity),
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
 E("m1.venue.ResolvedProjectionKind",projection_kind)]

UnresolvedRegistryAdvance = ["m2.venue.UnresolvedRegistryAdvance/v1", A(input_id),
 H(command_commitment), VenueExecutionCheckpoint, I(prior_account_registry_count),
 H(prior_account_registry_commitment), VenueExecutionBinding, VenueExecutionBinding,
 I(resulting_registry_count), H(resulting_registry_commitment), T(reason)]

VenueExecutionBinding = ["m2.venue.ExecutionBinding/v1", PositionScope,
 H(position_commitment), H(root_heads_commitment), I(integrity_bits)]
```

`pending_operation=null` is the canonical absence form. The enum member
`PendingVenueOperation.NONE` is never accepted as a substitute. Effect and owner source ordinals
are the dense integers `0..retained_count-1`. The issuer verifies effect rank against increasing
`VenueEffectRecord.created_ordinal` and owner rank against the increasing
`DurableInputRecord.created_ordinal` for each owner's exact discovery observation. Rows remain
identity-sorted on the wire, but `_effect_order`,
`_owner_order`, and per-effect leg sequences are rebuilt by increasing retained source ordinal.
This preserves behavior-significant discovery order without retaining unrelated history.
Contradiction rows are strictly increasing by `source_evidence_ordinal`, reject duplicate ordinal
or `(leg_key,observation_id)`, and rebuild `_contradiction_order_by_effect`. Every row must resolve
to exactly one selected `AcceptanceEvidenceRecord` for the same effect whose
`evidence_ordinal`, `contradiction_owner_id`, and `contradiction_observation_id` equal the three
wire members. Thus contradiction order is direct-source order, not caller-selected tuple order.

`BootstrapTarget` is a closed discriminated union. Active form is exactly:

```text
["m2.venue.BootstrapTargetActive/v1",
 A(application_generation_id), PositionScope,
 E("m1.venue.BootstrapSourceKind",source_kind),
 H(source_execution_commitment), H(target_genesis_execution_commitment),
 H(target_execution_commitment), VenueExecutionBinding,
 I(account_registry_count), H(account_registry_commitment),
 I(reconciliation_transition_count), H(reconciliation_transition_head),
 A(bootstrap_input_id), H(bootstrap_input_commitment),
 H(bootstrap_target_execution_commitment), I(bootstrap_account_registry_count),
 H(bootstrap_account_registry_commitment),
 I(bootstrap_reconciliation_transition_count),
 H(bootstrap_reconciliation_transition_head),
 H(bootstrap_neutral_checkpoint_proof_commitment), M2VenueTransitionProof,
 A(checkpoint_input_id), H(checkpoint_command_commitment),
 H(neutral_checkpoint_proof_commitment), M2VenueTransitionProof]
```

This is length 25. The map seal, commitment, and seal are derived and absent from bytes.
Consumed form is length 6:
`["m2.venue.BootstrapTargetConsumed/v1", ActiveForm, A(effect_id),
A(request_occurrence_id), A(request_input_id), H(effect_scope_commitment)]`.
All retained seals and commitments are re-derived and compared, never trusted.

`M2VenueTransitionProof` is the exact length-23 array:

```text
["m2.venue.M2TransitionProof/v1", PositionScope,
 ProtectionCursor, ProtectionCursor, VenueScope, VenueScope,
 H(predecessor_execution_commitment), H(execution_commitment),
 VenueExecutionCheckpoint, VenueExecutionCheckpoint,
 SymbolAuthoritySummary, SymbolAuthoritySummary,
 VenueExecutionBinding|N, VenueExecutionBinding|N,
 B(predecessor_execution_binding_matches), B(execution_binding_matches),
 B(predecessor_account_reconciliation_clear), B(account_reconciliation_clear),
 H(command_commitment), E("m1.venue.VenueRecoveryDisposition",disposition),
 Z(quantity_delta), E("m1.venue.ProtectionTransitionSourceKind",source_kind),
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

This is a new bounded owner proof minted by the venue reducer from exact predecessor/current books
at transition time. It carries every protection-relevant scope, cursor, execution checkpoint,
summary, binding, reconciliation, command, source, and result member directly. It deliberately
contains no whole-book or predecessor-book digest: those legacy digests commit omitted history and
cannot be re-derived from serving bytes. The owner validates the resulting cursor, summary,
binding, execution checkpoint, and reconciliation flags against current venue state; predecessor
members are bounded sealed transition provenance. Bootstrap records retain this bounded proof
prospectively. A legacy history-bound proof digest cannot be substituted, and no unrelated
terminal history is needed to authenticate it.
Both bootstrap proof-commitment members are exactly
`K("execution-core/m2-venue/transition-proof/v1", proof_row)`; R13-H changes the in-memory
bootstrap record to retain these M2 proofs rather than carrying the legacy proof object forward.

The resulting cursor head is independently derived as:

```text
CursorHeadPreimage = ["m2.venue.CursorHeadPreimage/v1",
 H(predecessor_cursor_commitment), PositionScope, A(resulting_mandate_id)|N,
 VenueScope(predecessor), VenueScope(resulting),
 H(predecessor_execution_commitment), H(execution_commitment),
 VenueExecutionCheckpoint(predecessor), VenueExecutionCheckpoint(resulting),
 SymbolAuthoritySummary(predecessor), SymbolAuthoritySummary(resulting),
 VenueExecutionBinding|N, VenueExecutionBinding|N,
 B(predecessor_execution_binding_matches), B(execution_binding_matches),
 B(predecessor_account_reconciliation_clear), B(account_reconciliation_clear),
 H(command_commitment), E("m1.venue.VenueRecoveryDisposition",disposition),
 Z(quantity_delta), E("m1.venue.ProtectionTransitionSourceKind",source_kind),
 H(source_binding)]

cursor.head = K("execution-core/m2-venue/protection-cursor-head/v1", CursorHeadPreimage)
```

The resulting cursor ordinal is predecessor ordinal plus one; mandate, execution commitment, and
execution checkpoint equal the corresponding resulting members. The ordinal-zero cursor remains
the exact existing genesis with head
`_commit_parts("execution-core/protection-cursor-genesis/v1")`, null mandate, and null execution
pair. Every new ordinal-positive cursor uses the M2 formula. A legacy v2 ordinal-positive cursor is
non-serving and cannot be silently converted; because no R13-C payload has yet been installed, the
fresh M2 lane starts from genesis or explicit reconciliation rather than migrating hidden history.

### 3.4 Venue selection completeness

One `_M2VenueState` is account-wide for its exact `VenueScope`; it is never duplicated per
symbol. `ExecutionScopeRows` is the exact identity-sorted set of every current `PositionScope`
reachable from an included effect, execution binding/snapshot, bootstrap target, protection cursor,
authority epoch, coverage provenance, or unresolved reconciliation. The future R13-C per-scope
components reference this one venue-state commitment and proof commitment.

For the selected application generation, execution profile/account, and complete included-scope
set, `EffectRows` is exactly the set satisfying:

```text
disposition <> CLOSED
OR EXISTS owner WHERE owner.effect_id = effect.effect_id
                    AND owner.admitted_after_effect_closed = true
```

It includes every qualifying AAPL/MSFT/etc. effect across the account, including unresolved
predecessor-generation effects that still satisfy the predicate. Claims,
owners, attempts, closure heads, coverage, reconciliations, bindings, bootstrap targets, and cursors
are the exact rows reachable from that set or from a selected current scope. Every reference must
resolve exactly once. A terminal unrelated row is forbidden; a required reachable row missing from
the payload is forbidden. Selection uses canonical external identities, never internal SQL row IDs.
For every selected owner, exactly one current terminal form exists: a non-null attempt forbids a
closure head; a null attempt requires exactly one closure head.

## 4. Authority state

### 4.1 Complete 20-member classification

| Class | Exact fields |
| --- | --- |
| payload scalar | `phase`; `mode`; `supervisor_fence`; `kill_engaged`; `session_id`; `budget`; `_emergency_grant` |
| sealed owner reference | `venue` |
| payload semantic row | `_effect_authority_by_id`; `_manual_by_id`; `_acquisition_currentness_by_scope`; `_acquisition_descriptor_by_scope`; `_acquisition_descriptor_by_effect`; `_acquisition_active_by_scope` |
| derived index | `_claim_by_effect`; `_claim_by_occurrence`; `_manual_flatten_by_scope` |
| omitted direct/history | `_input_by_id`; `_query_by_id`; `_consumed_grant_ids` |

These 7 + 1 + 6 + 3 + 3 entries are all 20 fields.

The three omitted maps are replaced only at an explicit behavioral boundary, not defaulted empty.
The M2 authority kernel is callable only with an opaque repository-minted
`_AuthorityInputDedupeFact`; the publicly constructible WO-0167 `InputDedupeFact` is transport data
and is not sufficient authority. The opaque fact contains the exact primary classification and
semantic matches plus `request_kind`, `request_commitment`, `connection_snapshot_id`, and a private
seal over all those members. Its constructor remains private. Repository issuance and the pure
legacy adapter call the same private mint after independently deriving the same canonical rows;
the kernel re-derives and checks the seal immediately before any decision. Forging, copying across
a request kind/commitment or snapshot, omitting a match, or supplying an extra match fails closed.

The exact semantic-key lookup-cardinality matrix is (`exactly 1` means one mandatory lookup
coordinate; its retained match cardinality is exactly zero or one and is sealed separately):

| Authority command | `AUTHORITY_QUERY_CLAIM_V1` | `AUTHORITY_MANUAL_FLATTEN_V1` | `AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1` |
| --- | ---: | ---: | ---: |
| `ClaimBrokerQuery` | exactly 1 for `query_claim_id` | 0 | 0 |
| `BeginManualFlatten` (its optional grant field is not admitted by the reducer) | 0 | exactly 1 for `flatten_id` | 0 |
| `CreateBrokerEffect` without `emergency_grant_id` | 0 | 0 | 0 |
| `CreateBrokerEffect` with `emergency_grant_id` | 0 | 0 | exactly 1 for `emergency_grant_id` |
| `ClaimEffect` whose retained authorization has an `emergency_grant_id` | 0 | 0 | exactly 1 for that retained `emergency_grant_id` |
| `ClaimEffect` whose retained authorization has no grant | 0 | 0 | 0 |
| every other exact `_AuthorityCommand` variant | 0 | 0 | 0 |

Every command also requires exactly one primary durable-input classification for its exact
`(application_generation_id,input_domain,input_identity_sha256,payload_sha256)`; exact replay,
payload conflict, semantic conflict, and unseen are mutually exclusive. Each required semantic row
must match the command-derived canonical key bytes and retained primary input, and no semantic kind
outside the row above is admitted. Primary durable-input lookup owns exact replay/conflict formerly
decided by `_input_by_id`; query claim owns uniqueness formerly decided by `_query_by_id`; grant
consumption owns one-use state formerly decided by `_consumed_grant_ids`. The kernel must not run
when the primary fact or any required match is absent, unsealed, duplicated, or extra. Thus no
hydrated owner can bypass or repeat those decisions, and no second replay algorithm is introduced.

### 4.2 Exact authority state and rows

`_M2AuthorityState` is the exact 15-member array:

```text
["m2.authority.State/v1", E(EnginePhase), E(TradingMode), E(SupervisorFence),
 B(kill_engaged), A(session_id)|N,
 ["m2.authority.RequestBudget/v1",I(remaining),I(safety_reserve)],
 VenueRef, EmergencyGrant|N, EffectAuthorizationRows, ManualRows,
 AcquisitionDescriptorRows, AcquisitionSlotRows,
 H(direct_selection_commitment), H(state_commitment)]
```

`VenueRef` is length 7:
`["m2.authority.VenueRef/v1",A(application_generation_id),A(broker),A(environment),
A(account),H(venue_state_commitment),H(venue_proof_commitment)]`.

The four variable state collections use exact wrappers:
`EffectAuthorizationRows = C("m2.authority.EffectAuthorizations/v1",rows)`,
`ManualRows = C("m2.authority.ManualFlattens/v1",rows)`,
`AcquisitionDescriptorRows = C("m2.authority.AcquisitionDescriptors/v1",rows)`, and
`AcquisitionSlotRows = C("m2.authority.AcquisitionSlots/v1",rows)`. Their keys are respectively
`effect_id`, `flatten_id`, `effect_id`, and canonical `PositionScope`; each is strictly key-ordered,
duplicate-free, and has exact empty form `[literal_tag,0,[]]`.

`EffectAuthorizationRows` is keyed by `effect_id`. Each exact length-6 row is
`["m2.authority.EffectAuthorization/v1", BrokerEffectRequest, A(session_id),
A(manual_flatten_id)|N, A(emergency_grant_id)|N, ClaimRow|N]`.
`ClaimRow` is either
`["m2.authority.ClaimEffect/v1",A(input_id),A(effect_id),A(claim_occurrence_id)]` or
`["m2.authority.ClaimAcquisitionEffect/v1",A(input_id),A(effect_id),
A(claim_occurrence_id),AcquisitionClaimPermit]`. `AcquisitionClaimPermit` is the exact length-22
array tagged `m2.authority.AcquisitionClaimPermit/v1` containing, in source order, its first 21
semantic members through `active_commitment`; its derived commitment and seal are absent and
re-derived. Every claim must name the same effect and canonical occurrence as its authorization.

```text
["m2.authority.AcquisitionClaimPermit/v1", A(input_id),
 A(application_generation_id), PositionScope, A(session_id), A(generation_id),
 A(acquisition_mandate_id), A(protection_mandate_id), H(binding_commitment),
 H(emergency_recovery_compatibility_commitment), H(controller_head), I(successor_ordinal),
 H(execution_snapshot_commitment), H(scope_execution_commitment), H(venue_commitment),
 H(authority_context_commitment), H(protection_commitment)|N, A(effect_id),
 A(claim_occurrence_id), H(currentness_commitment), H(descriptor_commitment),
 H(active_commitment)]
```

`ManualRows` is keyed by `flatten_id`. Each row is
`["m2.authority.ManualFlatten/v1", BeginManualFlatten,
E("m1.authority.FlattenPhase",phase), C("m2.authority.CancelEffects/v1",A(effect_id)...),
A(sell_effect_id)|N]` (length 5). Cancel effects are strictly ordered by effect ID.

`EmergencyGrant` is
`["m2.authority.EmergencyGrant/v1",A(grant_id),A(account),A(symbol_id),A(session_id),
A(actor),T(reason),A(evidence_reference)]` (length 8).

`AcquisitionDescriptorRows` is keyed by `effect_id`. Each row is
`["m2.authority.AcquisitionDescriptor/v1",A(effect_id),AcquisitionEffectPermit]`.
It retains every active or predecessor descriptor still reachable from an acquisition slot or
unresolved predecessor-generation effect. This collection is the source for
`_acquisition_descriptor_by_effect`; a commitment-only inactive slot cannot replace it.

`AcquisitionSlotRows` is keyed by `PositionScope`; one row owns the three scope maps:

```text
["m2.authority.AcquisitionSlot/v1", PositionScope,
 Currentness,
 ["m2.authority.AcquisitionDescriptorActive/v1", A(effect_id),
  H(descriptor_commitment)]|
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
Each active descriptor reference must resolve to exactly one `AcquisitionDescriptorRows` permit.
Each inactive predecessor must also resolve to its retained descriptor row; this preserves the
source owner's by-effect map after successor registration.

```text
["m2.authority.AcquisitionEffectPermit/v1", A(input_id),
 A(application_generation_id), PositionScope, A(session_id), A(generation_id),
 A(acquisition_mandate_id), A(protection_mandate_id), H(binding_commitment),
 H(emergency_recovery_compatibility_commitment), H(predecessor_controller_head),
 H(controller_head), I(successor_ordinal), H(execution_snapshot_commitment),
 H(scope_execution_commitment), H(venue_commitment), H(authority_context_commitment),
 H(protection_commitment)|N, AcquisitionEffectTerms, A(effect_id),
 A(request_occurrence_id), A(client_order_id)]
```

Unseen scope is represented by no slot row. A present slot cannot omit currentness. Descriptor and
active values are both null for no admitted effect, both active for a current effect, or both the
same inactive predecessor/successor triple. Mixed variants, orphan descriptor/effect indexes, and
defaulted nulls fail.

`EffectAuthorizationRows` is exactly the union of effects selected by the account-wide venue
predicate plus effects referenced by a retained manual row, acquisition descriptor row, or active
claim. It does not copy unrelated terminal authorization history. Every selected claim appears
inside its matching authorization row exactly once; both claim indexes are then derived.

## 5. Acquisition state

### 5.1 Complete 13-member classification

| Class | Exact fields |
| --- | --- |
| payload scalar/current | `application_generation_id`; `position_scope`; `scope_execution_commitment`; `venue_commitment`; `authority_context_commitment`; `protection_commitment`; `controller_commitment`; `_controller`; `_mandate` |
| bounded semantic rows | `registry`; `lineage` |
| derived | `commitment`; `_seal` |

The owner-state registry wire contains only the LIVE generation and its active stream route. The
owner-state lineage wire contains only current/active/unresolved routes. A directly targeted retired
generation, historical stream route, and late-fact lineage chain belong only to the sealed operation
proof and are never installed as standing owner state. The owner's existing full-history
registry/lineage seals are not reused as bounded state commitments.

### 5.2 Exact acquisition state

`_M2AcquisitionState` is the exact 16-member array:

```text
["m2.acquisition.State/v1", A(application_generation_id), PositionScope,
 H(scope_execution_commitment), H(venue_commitment), H(authority_context_commitment),
 H(protection_commitment)|N, Controller, AcquisitionMandate,
 GenerationLive, MarketStreamRouteLive,
 LineageRows, H(direct_selection_commitment), H(bounded_registry_commitment),
 H(bounded_lineage_commitment), H(state_commitment)]
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
 H(economics_head_commitment),
 E("m1.acquisition.GenerationServingClass",serving_class),
 H(closure_summary_commitment), H(commitment)]
```

Every present acquisition owner requires a non-null controller `live_generation_id`, its exact
matching current-role row, and a non-null stream route for the mandate evidence-policy stream. The
route must resolve to that current generation. The current-role row's serving class is exactly
`LIVE` or `RECONCILIATION_REQUIRED`; the latter requires controller recovery class
`RECONCILIATION_REQUIRED` or `MIXED_GENERATION_RECONCILIATION_REQUIRED`. Controller recovery
`NORMAL` or `MIXED_GENERATION_RECOVERY` requires current serving class `LIVE`.
The active stream route is
`["m2.acquisition.MarketStreamRoute/v1",A(stream_generation_id),A(generation_id),H(commitment)]`
and must resolve to the LIVE row. The bounded standing registry therefore always has exactly one
route for its one selected generation and passes the owner's record/route cardinality and binding
checks. A targeted retired row is carried only by `TARGETED_LATE_FACT_V1`, has serving class exactly
`RETIRED_UNSERVING`, differs from LIVE, and is paired there with its exact historical stream route.

Each lineage row is length 5:
`["m2.acquisition.LineageRoute/v1",E("m1.acquisition.GenerationRouteKind",kind),Identity,A(generation_id),
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

R13-H replaces that history-shaped behavioral dependency at its source. The canonical
`AcquisitionControllerState.commitment` becomes the M2 state commitment derived from the bounded
current serving view (LIVE generation and stream route, active/current/unresolved lineage, current
controller and mandate); a targeted retired slice is operation proof and is not part of the
ordinary standing commitment. Both the legacy in-memory state adapter and hydrated-state adapter
derive this same commitment through one private helper. Every existing consumer of
`state.commitment` -- status, create, successor, preemption, protection exit, canonical fact, and
protection rebase -- therefore receives identical bytes before and after hydration. No consumer may
retain or recompute the former full-registry/full-lineage digest. Equivalence tests construct two
states with identical serving projections but different unrelated terminal history and require
equal M2 state commitments and equal next controller heads for every transition family; changing
any serving row must change both. This is a deliberate one-time semantic replacement, not a claim
that the old history-shaped digest can be reconstructed.

Their exact preimages are:

```text
BoundedRegistry = ["m2.acquisition.BoundedRegistry/v1",
 GenerationLive, MarketStreamRouteLive]

BoundedLineage = ["m2.acquisition.BoundedLineage/v1",
 C("m2.acquisition.LineageRoutes/v1",lineage_rows)]
```

`bounded_registry_commitment = K("execution-core/m2-acquisition/bounded-registry/v1",
BoundedRegistry)`; `bounded_lineage_commitment =
K("execution-core/m2-acquisition/bounded-lineage/v1",BoundedLineage)`. Child generation and route
commitment members remain present exactly as shown in their rows; lineage child commitments remain
present exactly as shown. Targeted retired rows are excluded from this standing commitment and are
committed by the owner observation proof instead.

`LineageRows` is therefore exactly
`C("m2.acquisition.LineageRoutes/v1",rows)`, ordered first by the closed family order REQUEST,
EFFECT, OWNER, ROOT, FACT and then by canonical identity bytes. Its sole empty form is
`["m2.acquisition.LineageRoutes/v1",0,[]]`. The fixed generation and stream-role members are not
variable wrappers; their explicit position in `BoundedRegistry` is their role and cardinality.

## 6. Execution proof encoding

The existing `_M2ExecutionState` component remains the exact length-21 array already implemented
at the accepted base:

```text
["m2.position.execution-state/v1", PositionScope, Z(raw_quantity),
 E("m2.position.BasisAuthority",basis_authority), Fraction(cost_basis)|N,
 A(basis_price_metadata)|N, TailFoldInput|N,
 ["m2.position.PositionIntegrity",I(integrity_floor_bits)],
 ["m2.position.PositionIntegrity",I(integrity_bits)],
 B(account_reconciliation_required), I(reconciliation_transition_count),
 H(reconciliation_transition_head), I(root_count), H(root_order_commitment),
 H(head_ids_commitment), H(root_heads_commitment), H(seen_facts_commitment),
 H(root_head_map_commitment), H(seen_fact_map_commitment),
 H(root_claim_map_commitment), H(state_commitment)]
```

`TailFoldInput` is
`["m2.position.tail-fold-input/v1",Z(raw_quantity),Fraction(cost_basis),
A(price_metadata)|N,PositionScope|N,A(tail_root_key)|N,I(prefix_count),
H(prefix_heads_commitment)]`. It must be bound. Basis authority is exactly `AVAILABLE` or
`BASIS_RECONCILIATION_PENDING`; integrity bits contain only the closed
`CONSISTENT|EXECUTION_FACT_CONFLICT|EXECUTION_RECONCILIATION_REQUIRED|OVERFILL_QUARANTINE` mask.

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
`["m2.position.SeenFact/v1",CanonicalExecutionFact,E("m1.fills.FirstObservationClassification",v),
PositionScope|N]`, where `CanonicalExecutionFact` is exactly
`BrokerExecutionFact|HumanAttestedFillFact`. `RootHead` is the exact length-11 semantic
source-order row tagged
`m2.position.RootHead/v1`: root key, original sequence, execution scope, execution authority,
current source-event ID, fact kind, quantity, optional price, prefix-heads commitment,
and prefix-proof commitment. The two prefix commitments use `X` because the authentic genesis
form is empty bytes; nonempty values must be 32 bytes. The row commitment is absent from bytes and
re-derived.

`PersistentMapWitness` is
`["m2.position.PersistentMapWitness/v1",X(key_bytes),I(map_size),
C("m2.position.WitnessNodes/v1",nodes)]`. A node is
`["m2.position.WitnessNode/v1",B(has_value),X(value_commitment),
C("m2.position.WitnessChildren/v1",children)]`; a child is
`["m2.position.WitnessChild/v1",I(byte_label),H(child_commitment)]`. Child labels are 0..255 and
strictly increasing. A true node requires a 32-byte value commitment; a false node requires exact
empty bytes, not null or a zero digest. The path and branching limits in section 2.4 are mandatory.

Decode reconstructs the exact owner proof through its owner-only constructor, rechecks all four
witnesses against the three aggregate map commitments, re-derives the proof commitment, and
byte-compares. An absent predecessor witness is legal only where the fact has no predecessor.

This fact-specific proof is not a mandatory member of `ExecutionScopeRows`. It appears only in
the separately keyed targeted-operation direct-proof family for the exact incoming broker fact.
Genesis and ordinary checkpoint state therefore carry `ExecutionState` plus
`VenueExecutionCheckpoint` without inventing a distinguished fact. A targeted execution proof is
complete only for its exact `ExecutionFactKey` and cannot authenticate another input.

## 7. Protection proof encoding

`_M2ProtectionAuthorityProof._CurrentRows` is exactly:

```text
["m2.protection.CurrentRows/v1", A(application_generation_id), T(execution_profile_id),
 T(market_source_profile_id), I(scope_id), PositionScope,
 I(controller_currentness_head_ordinal), A(live_acquisition_generation_id)|N,
 E("m2.protection.AuthorityClass",authority_class), A(active_stream_generation_id),
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

`scope_id`, both currentness-head ordinals, and every count are at least zero;
`version_ordinal` is at least one. Negative values, version zero, and boolean substitutes fail.

## 8. Repository-issued owner proofs

Each owner proof is an opaque exact type. Its canonical row is:

```text
[OWNER_PROOF_TAG,
 A(application_generation_id), T(execution_profile_id),
 T(market_source_profile_id), I(currentness_head_ordinal), I(checkpoint_version_ordinal),
 AccountScopeVector,
 H(owner_state_bytes_sha256), H(owner_state_commitment),
 C(FAMILY_COUNTS_TAG, [[family_tag,count,predicate_tag,PredicateCoordinates,
                        family_rows_commitment],...]),
 C(DIRECT_ROWS_TAG, exact_direct_rows),
 TargetedExecutionProofRows,
 H(proof_commitment)]
```

This is exact length 13. `AccountScopeVector` is
`C("m2.owner.AccountScopes/v1",rows)`, where each row is
`["m2.owner.AccountScope/v1",I(scope_id),PositionScope,
 A(live_generation_id)|N,I(controller_currentness_head_ordinal)]`. It is strictly ordered by
`(scope_id,canonical PositionScope bytes)`, duplicate-free, and exactly equals
`ExecutionScopeRows` plus each scope's current controller row. A non-null live generation requires
exactly one matching LIVE-generation direct row and one LIVE-stream direct row. Null is the sole
legal pre-generation form and forbids both rows; it is never replaced by an invented identity.

`TargetedExecutionProofRows` is
`C("m2.position.TargetedObservationProofs/v1",rows)`; each row is
`["m2.position.TargetedObservationProof/v1",A(execution_fact_key),
ExecutionObservationProof]`. It is strictly key-ordered and has count zero for an ordinary
checkpoint or exactly one for the currently targeted broker operation/late fact. The proof's fact
key must equal its row key. The wrapper is a direct member of the owner-proof commitment; omitted,
duplicate, extra, or wrong-key targeted proofs fail.

Currentness is at least zero and checkpoint version is at least one. The
three profile/application coordinates must equal the future outer envelope exactly.

The owner-state byte digest is deliberately not the future outer checkpoint digest: binding a proof
contained inside that checkpoint to the checkpoint's own digest would be circular. R13-C binds the
already sealed owner state/proof bytes into the outer payload and derives the outer digest last.

The three tags are `m2.venue.ObservationProof/v1`,
`m2.authority.ObservationProof/v1`, and `m2.acquisition.ObservationProof/v1`. Family-count rows are
strictly ordered by the family order declared in this contract. `predicate_tag` is one of:
`HEADER_IDENTITY_V1`, `CURRENT_SCOPE_V1`, `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1`,
`REACHABLE_OWNER_V1`,
`CURRENT_HEAD_V1`, `TARGETED_LATE_FACT_V1`, `ACTIVE_AUTHORITY_V1`,
`LIVE_GENERATION_V1`, `ACTIVE_LINEAGE_V1`, or `SOURCE_ATTRIBUTION_V1`. Direct rows use the exact
accepted typed persistence record arrays frozen in WO-0167/R13-S, not caller dictionaries.

The symbolic wrapper names in the shape above resolve to these exact literal tags:

| Owner | family counts | direct rows |
| --- | --- | --- |
| venue | `m2.venue.ProofFamilyCounts/v1` | `m2.venue.ProofDirectRows/v1` |
| authority | `m2.authority.ProofFamilyCounts/v1` | `m2.authority.ProofDirectRows/v1` |
| acquisition | `m2.acquisition.ProofFamilyCounts/v1` | `m2.acquisition.ProofDirectRows/v1` |

Each family-count entry is the exact length-6 row
`["m2.owner.ProofFamily/v1",T(family_tag),I(count),T(predicate_tag),
PredicateCoordinates,H(family_rows_commitment)]`. Its family commitment is
`K("execution-core/m2-owner/proof-family/v1", C(family_tag, exact_rows))`.
Direct-selection commitment is, in argument order,
`K(owner_direct_selection_domain,
[AccountScopeVector,owner_family_counts_wrapper,owner_direct_rows_wrapper])`.
Owner state commitment is `K(owner_state_domain,state_row_without_state_commitment)`.
Owner proof commitment is `K(owner_observation_proof_domain,proof_row_without_proof_commitment)`.

Family order is exact and closed:

- venue: `APPLICATION_GENERATION`, `EXECUTION_PROFILE`, `MARKET_SOURCE_PROFILE`, `SCOPE`,
  `ACQUISITION_CURRENT`, `SYMBOL_CONTROLLER`, `LIVE_GENERATION`, `VENUE_EFFECT`, `ACCEPTANCE_SET`,
  `ACCEPTANCE_EVIDENCE`, `DISPATCH_CLAIM`, `VENUE_OWNER`, `CLOSURE_HEAD`,
  `ACQUISITION_ROOT_ROUTE`, `ROOT_FILL`, `EXECUTION_FACT_HEAD`, `EXECUTION_FACT`,
  `DURABLE_INPUT`, `DURABLE_INPUT_SEMANTIC_KEY`, `DURABLE_INPUT_OUTCOME`,
  `MARKET_STREAM_AUTHORITY`, `PROTECTION_AUTHORITY`;
- authority: `APPLICATION_GENERATION`, `EXECUTION_PROFILE`, `SCOPE`,
  `ACQUISITION_CURRENT`, `SYMBOL_CONTROLLER`, `LIVE_GENERATION`, `VENUE_EFFECT`, `DISPATCH_CLAIM`,
  `DURABLE_INPUT`, `DURABLE_INPUT_SEMANTIC_KEY`, `DURABLE_INPUT_OUTCOME`; and
- acquisition: `APPLICATION_GENERATION`, `EXECUTION_PROFILE`, `MARKET_SOURCE_PROFILE`, `SCOPE`,
  `ACQUISITION_CURRENT`, `SYMBOL_CONTROLLER`, `LIVE_GENERATION`,
  `TARGETED_RETIRED_GENERATION`, `LIVE_MARKET_STREAM_AUTHORITY`,
  `TARGETED_RETIRED_MARKET_STREAM_AUTHORITY`, `VENUE_EFFECT`,
  `VENUE_OWNER`, `ACQUISITION_ROOT_ROUTE`, `ROOT_FILL`, `EXECUTION_FACT_HEAD`,
  `EXECUTION_FACT`.

### 8.1 Closed direct-row union

`exact_direct_rows` uses only the explicit arrays below. There is one handwritten branch per tag;
reflection and a generic record fallback are forbidden. Members appear in the listed order after
the literal tag. Exact integers, booleans, text, bytes, nulls, M1 atoms, and profile members use the
section-2 scalar forms; enum-like persisted text is still validated by the exact record constructor.

| Literal tag | Exact ordered members |
| --- | --- |
| `m2.direct.ApplicationGeneration/v1` | `application_generation_id, selected_execution_profile_id, selected_market_source_profile_id, activation_ordinal` |
| `m2.direct.ExecutionProfile/v1` | `connection_profile_id, application_generation, broker_provider, environment_class, account_identity, trade_command_origin, order_query_origin, order_event_origin, credential_handle_fingerprint, adapter_contract_version, capability_profile_sha256, deployment_identity, profile_commitment_sha256` |
| `m2.direct.MarketSourceProfile/v1` | `market_source_profile_id, provider, environment_or_feed, source_origin, entitlement_class, normalization_contract_version, data_capability_profile_sha256, source_profile_commitment_sha256` |
| `m2.direct.Scope/v1` | `scope_id, application_generation_id, execution_profile_id, symbol` |
| `m2.direct.AcquisitionGeneration/v1` | `acquisition_generation_id, scope_id, status, successor_ordinal, predecessor_generation_id, mandate_commitment_sha256, emergency_compatibility_sha256` |
| `m2.direct.AcquisitionCurrent/v1` | `acquisition_generation_id, scope_id, current_economics_head_ordinal, unresolved_effect_count, active_protection_count` |
| `m2.direct.SymbolController/v1` | `scope_id, application_generation_id, execution_profile_id, live_acquisition_generation_id, aggregate_quantity, integrity_state, currentness_head_ordinal, controller_version_ordinal, emergency_compatibility_sha256` |
| `m2.direct.VenueEffect/v1` | `effect_id, effect_external, scope_id, application_generation_id, execution_profile_id, acquisition_generation_id, generation_mandate_commitment_sha256, expected_controller_head_ordinal, expected_protection_version_ordinal, authority_class, request_occurrence_id, mandate_id, effect_kind, client_order_id, target_order_id, side, quantity, economic_scope, lifecycle_state, disposition, closure_proof_kind, closure_proof_digest, closure_proof_evidence_id, closure_proof_claim_id, created_ordinal` |
| `m2.direct.DispatchClaim/v1` | `claim_id, effect_id, execution_profile_id, claim_occurrence_id, claim_ordinal` |
| `m2.direct.AcceptanceSet/v1` | `acceptance_set_id, effect_id` |
| `m2.direct.AcceptanceEvidence/v1` | `evidence_id, acceptance_set_id, effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal, contradiction_owner_id, contradiction_observation_id` |
| `m2.direct.VenueOwner/v1` | `scope_id, execution_profile_id, owner_id, observation_id, effect_id, root_fill_key_id, owner_generation_id, admitted_after_effect_closed` |
| `m2.direct.ClosureHead/v1` | `closure_id, scope_id, owner_id, ordinal, effect_id, closure_kind, predecessor_closure_id` |
| `m2.direct.AcquisitionRootRoute/v1` | `root_fill_key_id, scope_id, application_generation_id, execution_profile_id, acquisition_generation_id, effect_id, owner_id, observation_id` |
| `m2.direct.RootFill/v1` | `root_fill_key_id, scope_id, application_generation_id, execution_profile_id, owner_generation_id, root_fill_id, current_fact_id, current_kind, current_authority, current_side, current_quantity, current_price, economics_head_ordinal` |
| `m2.direct.ExecutionFactHead/v1` | `root_fill_key_id, fact_id, fact_ordinal` |
| `m2.direct.ExecutionFact/v1` | `fact_id, scope_id, application_generation_id, execution_profile_id, root_fill_key_id, source_event_id, order_id, side, kind, authority, quantity, price, request_occurrence_id, claim_occurrence_id, prior_cumulative_quantity, resulting_cumulative_quantity, actor_id, reason_text, evidence_reference, predecessor_fact_id, fact_ordinal` |
| `m2.direct.MarketStreamAuthority/v1` | `stream_generation_id, scope_id, application_generation_id, acquisition_generation_id, generation_mandate_commitment_sha256, source_profile_id, session_id, sequence_mode` |
| `m2.direct.ProtectionAuthority/v1` | `scope_id, authority_class, active_stream_generation_id, active_acquisition_generation_id, active_generation_mandate_commitment_sha256, active_source_profile_id, active_session_id, active_sequence_mode, expected_controller_head_ordinal, state_commitment_sha256, version_ordinal` |
| `m2.direct.DurableInput/v1` | `application_generation_id, execution_profile_id, scope_id, input_domain, session_id, acquisition_generation_id, market_source_profile_id, stream_generation_id, input_identity_sha256, operation_contract_version, canonical_payload_bytes, payload_sha256, technical_state, created_ordinal` |
| `m2.direct.SemanticKey/v1` | `key_kind, key_application_generation_id, execution_profile_id, key_scope_id, canonical_key_bytes, key_sha256, input_application_generation_id, input_domain, input_identity_sha256, created_ordinal` |
| `m2.direct.DurableInputOutcome/v1` | `application_generation_id, input_domain, input_identity_sha256, owner_domain, owner_disposition, terminal_technical_state, result_sha256, checkpoint_currentness_head_ordinal, checkpoint_version_ordinal, checkpoint_payload_sha256, receipt_ordinal, receipt_sha256, canonical_outcome_bytes, outcome_length, outcome_sha256` |

Every positive array is decoded by constructing that exact accepted class (or exact profile owner),
then re-encoded and byte-compared. Profile secrets are absent by design. A field not present in the
accepted class cannot be added to its direct row.

Direct rows are grouped in the exact owner family order above. Each family appears once in
`ProofFamilyCounts` even when its count is zero. It admits only the like-named direct tag
(`TARGETED_RETIRED_GENERATION` uses `m2.direct.AcquisitionGeneration/v1`;
`LIVE_GENERATION` uses the same tag in its distinct slot; both stream-role families use
`m2.direct.MarketStreamAuthority/v1` in distinct slots). Within a family, rows are strictly
increasing by the exact direct uniqueness key listed below. Duplicate tag/key pairs fail.
The number of positive direct rows with that family tag equals its family count and their complete
wrapper hashes to `family_rows_commitment`. `exact_direct_rows` is the concatenation of these
already sorted family groups. A row cannot appear in two families except the two distinct fixed
generation roles and two distinct stream roles, whose identities must differ whenever both are
present.

No `KernelCheckpointRecord` appears in an inner owner proof. Its `checkpoint_sha256` is the future
outer payload digest, so including it here would be circular. R13-C seals owner states and proofs,
derives and inserts the complete payload, computes its digest, and only then inserts or advances the
kernel checkpoint head referencing that digest in the same caller-owned transaction. The
predecessor head coordinates may appear in the outer operation, but the new head is never an input
to its own payload.

The application/profile fixed families have count one. Scope/controller/current families have one
coordinate per `AccountScopeVector` row, except an acquisition-current coordinate is false when the
scope's live generation is null. Other family counts equal their exact predicate result.

The accepted direct uniqueness key members are, in order:

- profiles/application/scope/controller/current:
  `[profile_id]`, `[application_generation_id]`, `[scope_id]`, `[scope_id]`,
  or `[scope_id]` as applicable;
- generation/stream/effect/claim/acceptance/evidence/owner/closure:
  `[scope_id,generation_id]`, `[scope_id,stream_generation_id]`, `[effect_id]`,
  `[effect_id]`, `[effect_id]`, `[acceptance_set_id,evidence_ordinal]`,
  `[scope_id,owner_id]`, or `[scope_id,owner_id,ordinal]`;
- root route/root/fact head/fact/protection:
  `[root_fill_key_id]`, `[root_fill_key_id]`, `[root_fill_key_id]`, `[fact_id]`,
  or `[scope_id]`; and
- input/semantic/outcome:
  `[application_generation_id,input_domain,input_identity_sha256]`,
  `[key_kind,key_application_generation_id,execution_profile_id,key_scope_id,
  canonical_key_bytes]`, or
  `[application_generation_id,input_domain,input_identity_sha256]`.

Each key member uses its exact scalar/atom form. Missing, extra, reordered, non-key, or digest-only
coordinates fail. Negative lookup evidence is represented only by a false predicate coordinate as
defined below; there is no independently omittable absence wrapper.

Record construction alone is not validation. Before construction, each handwritten branch enforces
the accepted schema's exact scalar, optional-group, and cross-field rules. At minimum the closed
persisted sets are: generation status `LIVE|RETIRED_UNSERVING`; effect authority
`NORMAL|HARD_BAIL`; effect kind `SUBMIT|CANCEL|REPLACE`; side `BUY|SELL`; lifecycle state the
eight `BrokerEffectState` values; disposition `OPEN|CLOSED|INVALIDATED`; closure proof the three
`AcceptanceProofKind` values or null; closure kind
`TERMINAL_LEG|ACCEPTANCE_CLOSED|INVALIDATED_TERMINAL`; sequence mode
`SEQUENCED|SOURCE_TIME`; input technical state
`CLAIMED|TERMINAL|RECONCILIATION_PENDING`; outcome owner domain
`POSITION|VENUE_RECOVERY|AUTHORITY|ACQUISITION|PROTECTION`; and terminal technical state
`TERMINAL|RECONCILIATION_PENDING`. Unknown text is refused even if the current record dataclass
lacks `__post_init__`.

All identifiers/text/hex/byte lengths, numeric lower bounds, wholly-present optional groups,
predecessor/ordinal rules, digest-to-byte checks, profile/application/scope equality, and
root/effect/owner/fact/current-head relations are the exact accepted WO-0166 schema constraints and
WO-0167 record invariants, applied by pure explicit validators before the exact record constructor.
R13-H tests pin each closed set and at least one optional, numeric, digest, and cross-field mutant
per direct tag; R13-C repository issuance re-runs the same validators after SQL load.

`PredicateCoordinates` is always the exact count-bearing wrapper
`C("m2.owner.PredicateCoordinates/v1",rows)`. Each row is
`["m2.owner.PredicateCoordinate/v1",T(predicate_tag),B(expected_present),
C("m2.owner.ProofKey/v1",key_members)]`. It is strictly ordered by canonical key bytes and
duplicate-free. `expected_present=true` requires exactly one matching direct row;
`expected_present=false` requires zero. The family `count` equals the number of true coordinates,
and the direct-row key set must equal the true-coordinate key set exactly. Therefore every
positive and negative lookup has one committed coordinate and no absence list can be selectively
omitted. A set-returning predicate also executes one count query in the bound snapshot; its count
must equal both the true-coordinate count and returned row count. A zero-row family still carries
the exact deterministic false coordinates described below, or the exact empty wrapper when the
operation declares no lookup key.

The predicate-coordinate key preimages are:

- `HEADER_IDENTITY_V1`: the exact fixed application/profile key, with header application,
  execution-profile, market-profile, currentness and version appended as cross-check coordinates;
- `CURRENT_SCOPE_V1`: one row per `AccountScopeVector` scope, containing scope ID, canonical
  `PositionScope`, optional live generation, controller head, header currentness, and version;
- `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1`: one true row per result of the section-3.4 predicate,
  keyed by effect ID and prefixed by the complete `VenueScope` and `AccountScopeVector`;
- `REACHABLE_OWNER_V1`: one row per effect/owner key reachable from the account effect set;
- `CURRENT_HEAD_V1`: one row per selected root/current-fact key for the reachable owner;
- `TARGETED_LATE_FACT_V1`: rows use
  `[scope_id,retired_generation_id,retired_stream_generation_id,request_occurrence_id,effect_id,
  owner_id,root_fill_key_id,fact_id,source_event_id]`; all are true for a targeted operation and
  the wrapper is empty for an ordinary checkpoint;
- `ACTIVE_AUTHORITY_V1`: rows are keyed by the command-derived primary/semantic/outcome keys and
  prefixed by session, kill state, exact request kind, and request commitment;
- `LIVE_GENERATION_V1`: one row per scope with a non-null live generation, keyed by scope and
  generation and binding its returned stream generation and mandate commitment; a null live
  generation instead supplies one false generation coordinate and forbids a stream coordinate;
- `ACTIVE_LINEAGE_V1`: one row per exact `(route_family,canonical_identity_bytes,generation_id)`;
  the closed family order is REQUEST, EFFECT, OWNER, ROOT, FACT; and
- `SOURCE_ATTRIBUTION_V1`: one row per retained venue source object keyed by its durable input or
  semantic/outcome key and binding the source object's direct `created_ordinal`.

Identity values use `A(v)`; profile and predicate literals use `T`; numeric coordinates use `I`;
booleans use `B`. The arrays themselves, not prose SQL or a digest-only summary, are the proof
preimage. Optional singleton families use one deterministic coordinate per parent key: claim and
acceptance-set coordinates per selected effect, closure-head coordinates per selected owner,
protection-authority coordinates per selected scope, and outcome coordinates per selected input.
Their `expected_present` bit is derived from the parent state. Variable child families such as
acceptance evidence execute the exact parent-key set/count query and include every returned child
coordinate. These rules completely determine zero, positive, and absent cardinality.

The owner/family mapping is exhaustive and closed:

| Owner | Family | Sole predicate |
| --- | --- | --- |
| venue | `APPLICATION_GENERATION` | `HEADER_IDENTITY_V1` |
| venue | `EXECUTION_PROFILE` | `HEADER_IDENTITY_V1` |
| venue | `MARKET_SOURCE_PROFILE` | `HEADER_IDENTITY_V1` |
| venue | `SCOPE` | `CURRENT_SCOPE_V1` |
| venue | `ACQUISITION_CURRENT` | `CURRENT_SCOPE_V1` |
| venue | `SYMBOL_CONTROLLER` | `CURRENT_SCOPE_V1` |
| venue | `LIVE_GENERATION` | `LIVE_GENERATION_V1` |
| venue | `VENUE_EFFECT` | `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1` |
| venue | `ACCEPTANCE_SET` | `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1` |
| venue | `ACCEPTANCE_EVIDENCE` | `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1` |
| venue | `DISPATCH_CLAIM` | `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1` |
| venue | `VENUE_OWNER` | `REACHABLE_OWNER_V1` |
| venue | `CLOSURE_HEAD` | `REACHABLE_OWNER_V1` |
| venue | `ACQUISITION_ROOT_ROUTE` | `REACHABLE_OWNER_V1` |
| venue | `ROOT_FILL` | `CURRENT_HEAD_V1` |
| venue | `EXECUTION_FACT_HEAD` | `CURRENT_HEAD_V1` |
| venue | `EXECUTION_FACT` | `CURRENT_HEAD_V1` |
| venue | `DURABLE_INPUT` | `SOURCE_ATTRIBUTION_V1` |
| venue | `DURABLE_INPUT_SEMANTIC_KEY` | `SOURCE_ATTRIBUTION_V1` |
| venue | `DURABLE_INPUT_OUTCOME` | `SOURCE_ATTRIBUTION_V1` |
| venue | `MARKET_STREAM_AUTHORITY` | `LIVE_GENERATION_V1` |
| venue | `PROTECTION_AUTHORITY` | `CURRENT_SCOPE_V1` |
| authority | `APPLICATION_GENERATION` | `HEADER_IDENTITY_V1` |
| authority | `EXECUTION_PROFILE` | `HEADER_IDENTITY_V1` |
| authority | `SCOPE` | `CURRENT_SCOPE_V1` |
| authority | `ACQUISITION_CURRENT` | `CURRENT_SCOPE_V1` |
| authority | `SYMBOL_CONTROLLER` | `CURRENT_SCOPE_V1` |
| authority | `LIVE_GENERATION` | `LIVE_GENERATION_V1` |
| authority | `VENUE_EFFECT` | `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1` |
| authority | `DISPATCH_CLAIM` | `ACCOUNT_ACTIVE_OR_UNRESOLVED_EFFECT_V1` |
| authority | `DURABLE_INPUT` | `ACTIVE_AUTHORITY_V1` |
| authority | `DURABLE_INPUT_SEMANTIC_KEY` | `ACTIVE_AUTHORITY_V1` |
| authority | `DURABLE_INPUT_OUTCOME` | `ACTIVE_AUTHORITY_V1` |
| acquisition | `APPLICATION_GENERATION` | `HEADER_IDENTITY_V1` |
| acquisition | `EXECUTION_PROFILE` | `HEADER_IDENTITY_V1` |
| acquisition | `MARKET_SOURCE_PROFILE` | `HEADER_IDENTITY_V1` |
| acquisition | `SCOPE` | `CURRENT_SCOPE_V1` |
| acquisition | `ACQUISITION_CURRENT` | `CURRENT_SCOPE_V1` |
| acquisition | `SYMBOL_CONTROLLER` | `CURRENT_SCOPE_V1` |
| acquisition | `LIVE_GENERATION` | `LIVE_GENERATION_V1` |
| acquisition | `TARGETED_RETIRED_GENERATION` | `TARGETED_LATE_FACT_V1` |
| acquisition | `LIVE_MARKET_STREAM_AUTHORITY` | `LIVE_GENERATION_V1` |
| acquisition | `TARGETED_RETIRED_MARKET_STREAM_AUTHORITY` | `TARGETED_LATE_FACT_V1` |
| acquisition | `VENUE_EFFECT` | `TARGETED_LATE_FACT_V1` |
| acquisition | `VENUE_OWNER` | `TARGETED_LATE_FACT_V1` |
| acquisition | `ACQUISITION_ROOT_ROUTE` | `ACTIVE_LINEAGE_V1` |
| acquisition | `ROOT_FILL` | `TARGETED_LATE_FACT_V1` |
| acquisition | `EXECUTION_FACT_HEAD` | `TARGETED_LATE_FACT_V1` |
| acquisition | `EXECUTION_FACT` | `TARGETED_LATE_FACT_V1` |

A family/predicate pairing outside this table fails. For targeted acquisition proof, the retired
generation and retired stream families are either both count one with exact generation/mandate
bindings or both count zero with an empty targeted predicate wrapper. The issuer obtains the live
stream by the unique `(scope_id,acquisition_generation_id)` selection and the targeted retired
stream by the fully named `retired_stream_generation_id`; ambiguity or count other than one fails.

The issuer must bind one connection snapshot and verify:

1. application generation, profiles, scope, current controller head, and checkpoint version;
2. exact family counts and selection predicates;
3. every positive direct row and every committed false predicate coordinate;
4. every payload row's direct coordinates and digest-bearing semantic bytes;
5. currentness equality across controller, acquisition, execution, protection, and market;
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
6. rebuild venue indexes in this order: retained effect/owner source-order sequences, effect
   indexes, claim indexes, owner/current-leg summaries,
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
- One targeted late broker fact adds exactly one retired generation and the complete prerequisite
  route chain used by the owner: its REQUEST and EFFECT routes plus the required OWNER, ROOT, and
  FACT routes. All five must name the same selected retired generation and their identities must
  match the effect/claim/owner/root/fact direct rows. It cannot admit unrelated retired rows.
- Header-only payloads, state commitment without bytes, proof commitment without direct rows,
  history-shaped maps, terminal unrelated rows, and truncated over-limit families are non-serving.

## 11. Failure-capable implementation proof

R13-H tests must kill at least these independent mutants for every applicable owner:

1. missing, extra, reordered, duplicated, and wrong-tag row;
2. count mismatch and over-limit family;
3. same-digest/different-bytes or commitment-only substitution;
4. substituted application/profile/scope/session/generation/currentness/version;
5. omitted unresolved predecessor effect and unrelated terminal-history inclusion;
6. forged proof type, forged seal, stale direct row, and omitted or flipped false predicate coordinate;
7. derived-index bytes added to the payload or one derived index not rebuilt;
8. cross-effect claim, cross-owner closure/coverage, cross-scope execution/protection row;
9. generation route using `repr`, wrong family order, or unselected generation;
10. malformed witness path, child order, map size, membership, and nonmembership;
11. header-only checkpoint accepted as owner state; and
12. a second reducer branch or generic serializer introduced.

The mutation set also includes: `pending_operation=null` changed to enum `NONE`; retained
effect/owner source ordinals swapped while identity order is unchanged; one included account symbol
omitted; legacy history-bound bootstrap commitment substituted for the bounded commitment; one
acquisition-claim permit-only member changed with claim IDs fixed; targeted retired stream route or
one prerequisite REQUEST/EFFECT route omitted; human-first `SeenFact` changed to broker-only;
empty root-head prefix changed to null/zero digest; version ordinal changed from one to zero; and
every direct/predicate wrapper tag and key order changed independently; a null-live pre-generation
scope changed to an invented generation; an authority dedupe fact copied across request/snapshot;
one required or one forbidden authority semantic key changed; contradiction evidence ordinals
swapped; the old history-bound acquisition commitment retained at one transition consumer; and the
new outer checkpoint row inserted into its own inner owner proof.

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
