# WO-0168c frozen non-serving checkpoint contract — R1

Status: **PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Base: `341a881` (REV-0077 R0 findings and disposition preserved)

## 1. Boundary and authority

WO-0168c creates a complete, immutable, **non-serving** checkpoint candidate. It does not restore
runtime authority. The only valid sequence is:

```text
staged state rows -> repository selection proof -> inert projection -> canonical bytes
-> immutable payload row -> kernel-head advance -> caller commit

current kernel head -> exact payload -> repository load proof -> canonical decode
-> inert RuntimeCheckpointEnvelope
```

`RuntimeCheckpointEnvelope` cannot be passed to an existing reducer and cannot construct
`VenueRecoveryBook`, `ExecutionAuthorityState`, `AcquisitionControllerState`,
`_M2ExecutionObservationProof`, `_M2ProtectionAuthorityProof`, or any other serving type.
WO-0169 is the sole future authority to convert a candidate after owner lock, a fresh head check,
and the bounded-behavior cutover in section 10.

Checkpoint members have only two provenance classes:

- **database-discoverable**: the repository selects the complete qualifying row set and proves its
  exact keys, records, counts, and explicit absences; or
- **payload-owned semantics**: an authentic owner projects a member not represented completely in
  the database, the selection proof point-validates every referenced durable identity, and the
  immutable payload/head digest authenticates that member on load.

No payload-owned family may be described as database-complete. No digest is treated as authority.

## 2. Closed canonical grammar

All values are exact JSON arrays. Objects, maps, floats, booleans in integer positions, NaN,
infinities, byte-order marks, unknown fields, and trailing data fail. Canonical bytes are UTF-8
from `json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))`; decode must
re-encode and byte-compare.

The exact scalar notation is: `I` = JSON integer in `0..2^63-1`; `Z` = JSON integer in
`-2^63..2^63-1`; `B` = Boolean; `T` = nonblank NFC text without C0/DEL, at most 4,096 UTF-8 bytes;
`X` = lowercase even-length hex for at most 1,048,576 bytes; `H` = 64 lowercase hex characters;
`N` = null only where stated; `A(v)` = exact WO-0165 durable atom; `E(owner,v)` = `[owner,v.value]`;
`C(tag,rows)` = `[tag,len(rows),rows]`. Exact M2 operation values named below use their accepted
type-specific codecs from `persistence/operations.py`; reflection, `repr`, pickle, `asdict`,
`__dict__`, generic dispatch, and fallback encoding are forbidden.

Every keyed collection is strictly ordered by an injective canonical key frame:
`type_octet || uint64-be(byte_length) || canonical_json_bytes`; components use distinct octets for
null, Boolean, non-negative integer, signed integer, text, bytes, durable atom, enum, and tagged
array. Ordered witness paths preserve source order and are never sorted. Duplicate keys, alternate
empty forms, count mismatches, and unknown tags fail.

Limits are refusal limits: 4,096 scopes; 65,535 rows per other family; 256 children per persistent
map node; `len(key_bytes)+1` witness nodes; 2,097,152 bytes per row; 67,108,864 bytes per
collection or component; and 268,435,456 bytes for the whole payload. There is no truncation,
pagination, digest substitution, or partial candidate.

`K(domain,row)` is the existing length-framed `_commit_parts(domain,
canonical_json_utf8(row))`. A row carrying its derived commitment is committed with that final
member omitted. A collection commitment covers its count-bearing wrapper.

## 3. Outer envelope

The sole public codec value is the immutable, exact-type, non-subclassable,
constructor-hidden `RuntimeCheckpointEnvelope`:

```text
[1,"m2.runtime-checkpoint/v1", A(application_generation_id),
 H(execution_profile_sha256), H(market_source_profile_sha256),
 I(currentness_head_ordinal), I(checkpoint_version_ordinal),
 VenueCandidate, AuthorityCandidate, ScopeCandidates]

ScopeCandidates = C("m2.runtime-checkpoint.scopes/v1", [
 ["m2.runtime-checkpoint.scope/v1", A(scope_id), PositionScope,
  AcquisitionCandidate, ExecutionState, ProtectionCheckpoint], ...])
```

Scopes are strictly ordered by `scope_id` and include every selected application-generation
scope exactly once. `ExecutionState` and `ProtectionCheckpoint` are the exact existing component
arrays from `persistence/checkpoint_codec.py`; decode creates inert component carriers, never their
private serving proof types. `payload_sha256 = sha256(payload_bytes).hexdigest()` and is not
embedded recursively in the payload.

## 4. Venue candidate

The exact top row is:

```text
["m2.venue.CheckpointCandidate/v1", VenueScope, I(account_authority_epoch),
 I(unresolved_account_execution_reconciliation_count), I(registry_count)|N,
 H(registry_commitment)|N, H(registry_transition_head)|N,
 AuthorityEpochRows, EffectRows, ClaimRows, OwnerAttemptRows,
 AcquisitionCorrelationRows, ClosureHeadRows, EconomicHighWaterRows,
 HumanCoverageRows, BrokerCoverageRows, CoverageProvenanceRows,
 ReconciliationRows, ExecutionReconciliationRows, ExecutionScopeRows,
 BootstrapTargetRows, ProtectionCursorRows, H(candidate_commitment)]
```

`VenueScope = ["m2.venue.Scope/v1",A(application_generation_id),A(broker),
A(environment),A(account)]`. Registry count/commitment are wholly null or `(I,H)`.
`candidate_commitment` uses `execution-core/m2-venue/checkpoint-candidate/v1`; it is payload
integrity and is not the history-shaped `VenueRecoveryBook` commitment.

The collection tags, keys, and exact rows are closed:

| Collection tag; key | Exact row after tag |
| --- | --- |
| `m2.venue.AuthorityEpochs/v1`; `PositionScope` | `m2.venue.AuthorityEpoch/v1, PositionScope, I(epoch)` |
| `m2.venue.Effects/v1`; `effect_id` | `m2.venue.EffectCurrent/v1, I(source_ordinal), VenueEffectScope, E(BrokerEffectState), E(AcceptanceSetState), A(claim_id)\|N, AcceptanceProof\|N, ContradictionRows, I(operator_epoch)\|N, I(account_epoch)\|N` |
| `m2.venue.Claims/v1`; `effect_id` | `m2.venue.DispatchClaim/v1, A(effect_id), A(claim_id)` |
| `m2.venue.OwnerAttempts/v1`; `VenueLegKey` | `m2.venue.OwnerAttempt/v1, I(source_ordinal), A(leg), A(effect), A(observation), VenueAttempt\|N` |
| `m2.venue.AcquisitionCorrelations/v1`; `RootFillKey` | `m2.venue.AcquisitionCorrelation/v1, A(app_generation), PositionScope, A(request), A(effect), A(leg), A(root)` |
| `m2.venue.ClosureHeads/v1`; `VenueLegKey` | `VenueTerminalClosure` |
| `m2.venue.EconomicHighWaters/v1`; `VenueLegKey` | `m2.venue.EconomicHighWater/v1, A(leg), I(high_water)` |
| `m2.venue.HumanCoverages/v1`; `(root,effect,leg)` | `HumanCoverage` |
| `m2.venue.BrokerCoverages/v1`; `(root,effect,leg)` | `BrokerCoverage` |
| `m2.venue.CoverageProvenances/v1`; `PositionScope` | `m2.venue.CoverageProvenance/v1, PositionScope, C(m2.venue.CoveredRoots/v1,[m2.venue.CoveredRoot/v1,A(root),H(fact)]...), H(root_heads)\|N` |
| `m2.venue.Reconciliations/v1`; `VenueInputId` | `FillReconciliation \| RevisionReconciliation` |
| `m2.venue.ExecutionReconciliations/v1`; `VenueInputId` | `ResolvedRegistryProjection \| UnresolvedRegistryAdvance` |
| `m2.venue.ExecutionScopes/v1`; `PositionScope` | `m2.venue.ExecutionScopeCurrent/v1, ExecutionState, VenueExecutionCheckpoint` |
| `m2.venue.BootstrapTargets/v1`; `PositionScope` | `BootstrapCandidate` |
| `m2.venue.ProtectionCursors/v1`; `PositionScope` | `m2.venue.ProtectionCursor/v1, PositionScope, I(ordinal), H(head), A(mandate)\|N, H(execution)\|N, VenueExecutionCheckpoint\|N` |

The nested `VenueEffectScope`, `AcceptanceProof`, contradiction, attempt, closure, coverage,
reconciliation, execution-checkpoint, projection, and execution-binding arrays are byte-for-byte
the exact arrays in superseded contract 07 section 3.3, lines 316-379. This is a closed row
definition import only; its selection, source-ordinal, transition-proof, cursor-head, serving, and
commitment claims have no authority here.

`BootstrapCandidate` is the exact currently retained active (length 25) or consumed (length 6)
bootstrap semantic array, including its existing transition-proof candidate bytes. It is inert
evidence: decode does not allocate the existing proof, cursor, bootstrap owner, or book. No new
transition proof or cursor-head formula is introduced. `ProtectionCursor` above is the only
checkpoint cursor row and retains the existing ordinal/head without re-derivation.

Database-discoverable venue families are effects, claims, acceptance/evidence, owners, closure
heads, roots/routes/current fact heads, and current kernel/profile coordinates. Venue source
ordinals, authority epochs, coverage/reconciliation summaries, execution snapshots,
bootstrap candidates, and protection cursors are payload-owned semantics. At issuance, every
durable identity they reference must resolve by exact repository key and agree with the selection
proof; on load, their provenance is the immutable payload/head digest. WO-0168c does not claim
that omitted history can reproduce them.

## 5. Authority candidate

The exact 13-member row is:

```text
["m2.authority.Checkpoint/v1", E(EnginePhase), E(TradingMode), E(SupervisorFence),
 B(kill_engaged), A(session_id)|N,
 ["m2.authority.RequestBudget/v1",I(remaining),I(safety_reserve)],
 VenueRef, EmergencyGrant|N, CurrentEffectRows, ManualFlattenRows,
 AcquisitionSlotRows, H(checkpoint_commitment)]
```

`VenueRef = ["m2.authority.VenueRef/v1",A(application_generation_id),A(broker),
A(environment),A(account),H(venue_candidate_commitment)]`.
`EmergencyGrant = ["m2.authority.EmergencyGrant/v1",A(grant),A(account),A(symbol),
A(session),A(actor),T(reason),A(evidence_reference)]`.

- `CurrentEffectRows = C("m2.authority.CurrentEffects/v1", rows)`, keyed by effect ID; each row is
  `["m2.authority.CurrentEffect/v1",BrokerEffectRequest,A(session),A(flatten)|N,
  A(grant)|N,ClaimRow|N]`. `ClaimRow` is the exact existing ordinary or acquisition claim array.
- `ManualFlattenRows = C("m2.authority.ManualFlattens/v1", rows)`, keyed by flatten ID; each row is
  `["m2.authority.ManualFlatten/v1",BeginManualFlatten,E(FlattenPhase),
  C("m2.authority.CancelEffects/v1",A(effect_id)...),A(sell_effect)|N]`.
- `AcquisitionSlotRows = C("m2.authority.AcquisitionSlots/v1", rows)`, keyed by `PositionScope`;
  each row is `["m2.authority.AcquisitionSlot/v1",PositionScope,AcquisitionCurrentness,
  SlotValue]`. `SlotValue` is exactly one of `m2.authority.AcquisitionSlotEmpty/v1`,
  `m2.authority.AcquisitionSlotActive/v1` with its exact existing permit/descriptor semantics, or
  `m2.authority.AcquisitionSlotInactive/v1` with predecessor effect/descriptor commitments and
  successor generation. No separate descriptor collection exists.

`AcquisitionCurrentness`, acquisition permit, and descriptor members are their exact existing
source-order semantic arrays from contract 07 section 4.2; derived seals are absent and re-derived.
The authority checkpoint commitment uses `execution-core/m2-authority/checkpoint/v1` and is not
the existing history-shaped serving commitment.

Current effect/claim durable references are database-discoverable. Engine mode/fence/budget,
grant, manual state, currentness, slot semantics, and their closed-map completeness are
payload-owned. Issuance requires an authentic authority owner and exact point validation of every
durable reference; load trusts only the anchored payload as provenance. No database-completeness
claim is made for owner-only maps.

## 6. Acquisition candidate

The exact 17-member row is:

```text
["m2.acquisition.State/v1", A(application_generation_id), PositionScope,
 H(scope_execution_commitment), H(venue_commitment), H(authority_context_commitment),
 H(protection_commitment)|N, Controller, AcquisitionMandate,
 GenerationLive, MarketStreamRouteLive,
 UnresolvedGenerationRows, UnresolvedMarketStreamRouteRows,
 LineageRows, H(bounded_registry_commitment), H(bounded_lineage_commitment),
 H(snapshot_commitment)]
```

`Controller` has tag plus application generation, scope, controller head, successor ordinal,
optional live generation, `AcquisitionRecoveryClass`, scope execution, venue, authority,
optional protection, binding, compatibility, and final commitment (14 members total).
`Generation` has tag plus generation, application generation, scope, successor ordinal,
dual-mandate binding, predecessor/genesis head, emergency compatibility, economics head,
`GenerationServingClass`, closure summary, and commitment (12 members).
`MarketStreamRoute = ["m2.acquisition.MarketStreamRoute/v1",A(stream_generation),
A(generation),H(commitment)]`.

Unresolved generation and stream wrappers use literal tags
`m2.acquisition.UnresolvedGenerations/v1` and
`m2.acquisition.UnresolvedMarketStreamRoutes/v1`, are strictly generation-ID ordered, and have
identical generation sets. `LineageRows = C("m2.acquisition.LineageRoutes/v1",rows)`; each row is
`["m2.acquisition.LineageRoute/v1",E(GenerationRouteKind),Identity,A(generation),
SourceBinding,H(commitment)]`, ordered by family `REQUEST,EFFECT,OWNER,ROOT,FACT` then canonical
identity. REQUEST/EFFECT bind `m2.acquisition.LineageEffectSource/v1,A(effect)`; OWNER binds
`m2.acquisition.LineageOwnerSource/v1,A(scope),A(owner)`; ROOT binds
`m2.acquisition.LineageRootSource/v1,A(root)`; FACT binds
`m2.acquisition.LineageFactSource/v1,A(fact)`.

The three payload-only commitments use exactly:

- `execution-core/m2-acquisition/bounded-registry/v1` over
  `["m2.acquisition.BoundedRegistry/v1",GenerationLive,MarketStreamRouteLive,
  UnresolvedGenerationRows,UnresolvedMarketStreamRouteRows]`;
- `execution-core/m2-acquisition/bounded-lineage/v1` over
  `["m2.acquisition.BoundedLineage/v1",LineageRows]`; and
- `execution-core/m2-acquisition/state/v1` over the candidate without its final member.

They are not `GenerationRegistry._seal`, `AcquisitionLineageIndex._seal`, or the existing
history-shaped `AcquisitionControllerState.commitment`. Current/unresolved generation, stream,
effect, owner, root route, and current fact-head rows are database-discoverable. Controller,
mandate, and semantic commitment fields are payload-owned and point-validated at issuance.

## 7. Proofs, APIs, and acyclic persistence

The exact public additions are `RuntimeCheckpointPayloadRecord`,
`RuntimeCheckpointSelectionRequest`, `RuntimeCheckpointSelectionProof`,
`RuntimeCheckpointLoadRequest`, `RuntimeCheckpointLoadProof`, `RuntimeCheckpointEnvelope`,
`select_runtime_checkpoint`, `store_runtime_checkpoint_payload`,
`load_runtime_checkpoint_payload`, `load_runtime_checkpoint_proof`,
`encode_runtime_checkpoint`, and `decode_runtime_checkpoint`. Proof and envelope constructors are
hidden; exact exports are pinned. No generic serializer or owner constructor is public.

The pre-persistence `select_runtime_checkpoint(connection, request)` issues a
`RuntimeCheckpointSelectionProof` bound to generation, profile digests, predecessor kernel head,
target head/version, every database-discoverable record/key/count/absence vector, and a private
issuer seal. It runs after all state rows for the target are staged in the caller transaction and
before any payload exists. Package-private projection accepts exact authentic owners plus this
proof, supplies payload-owned semantics, point-validates their durable references, and returns the
inert envelope. Encoding accepts only that exact envelope.

The write sequence is indivisible and exact: (1) stage state rows; (2) select proof; (3) project
and encode; (4) insert immutable payload; (5) call the existing insert/advance kernel-checkpoint
primitive with the payload digest; (6) return an inert receipt; (7) caller commits. Repository
methods never begin, commit, roll back, savepoint, attach, detach, or change pragmas. A fault before
caller commit leaves the prior complete state after rollback.

Load is separately current: (1) load current kernel head; (2) load its exact payload by composite
identity; (3) select its database-discoverable rows; (4) issue `RuntimeCheckpointLoadProof` bound
to exact head, payload bytes/digest/length, records, keys, counts, and absences; (5) decode and
canonical-byte compare; (6) re-read and compare the current head before returning the inert
envelope. A selection proof is never accepted as a load proof. A prior authentic load proof is
stale after any head change.

## 8. Exact repository query and index matrix

Every query is fixed SQL with bound parameters and an explicit connection. There are no per-row
queries, Python `IN` expansion, dynamic SQL, full-history reads, or fallback scans.

| ID | Complete result | Required access path |
| --- | --- | --- |
| Q1 | application generation, profiles, current kernel head | existing exact unique keys |
| Q2 | all scopes for application generation, scope/current generation/controller/protection rows | existing application-generation/scope and current-row indexes |
| Q3 | OPEN/INVALIDATED effects for the exact generation/profile set | `ix_venue_effect_checkpoint_current` |
| Q4 | late owners for selected current/unresolved generations | `ix_venue_owner_checkpoint_late` |
| Q5 | claims, acceptance/evidence, owner attempts, and current closure heads joined from Q3/Q4 | existing effect/owner/closure exact indexes |
| Q6 | selected root routes, root/head/current fact, acquisition routes and stream rows | existing direct route/root/head/generation keys |
| Q7 | exact immutable payload by kernel composite identity | existing payload primary/unique key |

Q2-Q6 use joins/CTEs rooted in exact application/generation/profile coordinates, not caller-built
key lists. Query count is constant in history length; returned work is linear only in bounded
selected state. `EXPLAIN QUERY PLAN` must prove SEARCH/range access for every base family under
large unrelated history.

The current schema lacks two proof-bearing paths. Static implementation may add only:

```sql
CREATE INDEX ix_venue_effect_checkpoint_current
ON venue_effect(application_generation_id, execution_profile_id, disposition, effect_id);

CREATE INDEX ix_venue_owner_checkpoint_late
ON venue_identity_owner(owner_generation_id, effect_id, owner_external)
WHERE admitted_after_effect_closed = 1;
```

These exact statements are design authority, not execution authority. Any resulting `SCHEMA_DDL`
byte identity must be committed and returned to Ameen with SHA-256, UTF-8 byte count, and the
named fresh-file tests before changed DDL is installed or any SQLite-bearing test runs.

## 9. Failure-capable implementation evidence

Pure tests must first prove RED, then GREEN, for canonical round trips; every scalar/tag/count/
order/duplicate/optional/limit mutant; ordered witness paths; payload commitment changes; inert
type exactness; and inability of bytes/proofs to mint serving types. Mutation must kill omission
of canonical re-encoding, proof issuer checks, every coordinate comparison, point validation, and
the final current-head recheck.

After the exact DDL human gate, named fresh `tmp_path` file-database tests must prove: selection
set completeness and explicit absence; stale/spliced/replaced proofs; extra/missing qualifying
rows; Q1-Q7 count boundedness and index SEARCH under unrelated history; immutable payload and
reverse-edge constraints; old-complete/new-complete atomic fault cases; caller-owned transaction
behavior; exact exports and inert imports; no configured or `:memory:` database; and no SQL outside
repository operations. Focused, full `tests/execution_core`, ruff, mypy, import-boundary,
governance, and diff checks are required before REV-0078.

## 10. Held WO-0169 serving boundary

WO-0169 must independently freeze and review all of the following before any checkpoint can
serve: one owner-locked composition transaction; a fresh kernel-head/load-proof revalidation;
startup/cold-recovery fencing; exact private constructors for execution/protection/venue/
authority/acquisition owners; repository replay and nonmembership checks for omitted history; and
a scope-local bounded behavioral commitment replacing history-shaped acquisition commitments
atomically across status, create, successor, preemption, protection exit, canonical fact, and
protection rebase consumers. Account-wide proof data may not enter that scope-local commitment.

Until WO-0169 is accepted, `RuntimeCheckpointEnvelope` is storage-and-inspection data only. No
runtime composition, startup eligibility, reducer invocation, broker/network action, order,
promotion, or merge is authorized.
