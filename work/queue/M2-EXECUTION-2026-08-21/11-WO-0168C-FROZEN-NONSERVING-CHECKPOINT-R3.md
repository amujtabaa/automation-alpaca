# WO-0168c frozen non-serving checkpoint contract — R3

Status: **SUPERSEDED BY R4 — EVIDENCE ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `a0e966d`

## 1. Closed authority

R3 consists only of this file and `12-WO-0168C-R3-SQL-MANIFEST.md`. It retains R2 sections 2,
4-6, 10, and 11 only where R3 does not replace them. Earlier contracts are evidence, not a source
of unstated fields or behavior.

The result remains a complete non-serving checkpoint candidate. No serving owner, proof, reducer,
or startup capability is constructed in WO-0168c.

## 2. Exact outer and fixed component wire

The canonical payload is this exact 10-member array:

```text
[1,"m2.runtime-checkpoint/v1",A(application_generation_id),
 H(execution_profile_id),H(market_source_profile_id),I(currentness_head_ordinal),
 I(checkpoint_version_ordinal),VenueCandidate,AuthorityCandidate,ScopeCandidates]

ScopeCandidates = C("m2.runtime-checkpoint.scopes/v1",rows)
ScopeRow = ["m2.runtime-checkpoint.scope/v1",I(scope_id),PositionScope,
 AcquisitionCandidate,ExecutionComponent,ProtectionComponent]
```

Scope rows are strictly increasing by non-negative integer `scope_id`; every selected scope appears
once. Profile IDs are exact lowercase SHA-256 text and equal the selected profile record IDs.

ExecutionComponent is exactly 21 members in this order:

```text
["m2.position.execution-state/v1",PositionScope,Z(raw_quantity),
 ["m2.position.BasisAuthority",value],Fraction|N,A(price_metadata)|N,TailFoldInput|N,
 ["m2.position.PositionIntegrity",integrity_floor],
 ["m2.position.PositionIntegrity",integrity],B(account_reconciliation_required),
 I(reconciliation_transition_count),H(reconciliation_transition_head),I(root_count),
 H(root_order_commitment),H(head_ids_commitment),H(root_heads_commitment),
 H(seen_facts_commitment),H(root_head_map_commitment),H(seen_fact_map_commitment),
 H(root_claim_map_commitment),H(state_commitment)]
```

ProtectionComponent is exactly the current 32-member `m2.protection.checkpoint/v1` array, in the
current encoder's field order: tag; literal policy enum; mandate; raw quantity; execution
commitment; formula flag; four optional price values; waiting-buy flag; checkpoint commitment;
cursor ordinal/head; six optional market ordinals/times; optional occurrence ID; three market
flags; optional last primary; optional hard-bid ID/time; optional trade ID/time; optional trail-bid
ID/time; exit provenance. Its bytes-only parser names and validates all 31 fields separately.

Venue, bootstrap, authority, descriptor, slot, acquisition, source-order, canonical-frame, limit,
and commitment rows are exactly R2 sections 2 and 4-6. No line-range import remains.

## 3. Non-copyable issuance and exact preimages

Every constructor-hidden public proof/component/scope/envelope/receipt uses
`weakref_slot=True` and is registered after construction in a module-private identity registry:

```text
registry[id(value)] = (weakref.ref(value, cleanup), exact_binding, provenance)
```

Registry operations hold one private `RLock`. Authenticity requires the entry to exist, the weak
reference to be the same object by `is`, the stored binding to equal a fresh re-derivation, and the
stored provenance to match. The cleanup callback removes only the entry whose weak reference is
itself. Registry objects, lock, registration function, and lookup function are private and never
stored on issued values. Copying a visible field, sentinel, binding, or object ID cannot register a
forgery; ID reuse cannot match the retained weak reference.

Bindings use `_commit_parts` and exact field order:

- selection request: application ID, execution profile ID, market profile ID, optional expected
  checkpoint's four fields;
- selection set: every record family in section 5 order, then every derived absence family in
  literal family/key order, then twelve query counts;
- selection proof: request binding, actual predecessor or literal `ABSENT`, derived target head,
  derived target version, selection-set binding;
- component: literal tag, canonical bytes, SHA-256 text;
- scope: integer scope ID, then four component bindings in wire order;
- projected envelope: selection-proof binding, venue owner commitment, authority owner commitment,
  ordered `(scope_id, acquisition commitment, execution snapshot commitment, protection
  commitment)` tuples, canonical payload bytes, payload digest;
- private load proof: request fields, initial head, payload record's eight fields, fresh selection-
  set binding;
- loaded envelope: load-proof binding, canonical payload bytes, payload digest; and
- receipt: payload eight fields, optional predecessor four fields, resulting four fields,
  selection commitment.

The four private nested inert carriers are not separately authenticatable API values; they exist
only inside a registered public component/envelope and retain exact canonical bytes. Tests forge
with copied registry-visible fields, copied bindings, recomputed unkeyed bindings, altered owner
commitments, and ID-reuse cleanup.

## 4. Provenance boundary without circular lookups

Database-complete families are only: application/profile/head, scopes/controllers/protection
rows, LIVE or counter-unresolved generation/current rows, qualifying effects, all owners/claims/
acceptance/evidence for those effects, current closure heads for those owners, root routes/roots/
current fact heads reachable from those owners, and streams/cursors for selected generations.

Only durable identities inside those families are repository-point-validated. The following are
explicitly payload-owned semantics authenticated from exact source owners at projection and from
the immutable payload/head at load: inactive descriptor/permit history, bootstrap input IDs and
nested predecessor proof fields, authority manual/query/grant history, coverage/reconciliation
source IDs, venue source ordinals, acquisition controller/mandate semantic fields, and existing
execution/protection commitments. They are not described as database-present, absent, complete,
or independently reconstructed in WO-0168c.

An inactive descriptor is retained exactly when an authentic retained slot or selected unresolved
predecessor effect references it. Its permit and commitments are source-owner authenticated; no
query is invented for a resolved historical effect. WO-0169 must either accept the anchored
payload as serving-constructor provenance or add a separately reviewed repository proof; R3 does
not pretend to perform both.

## 5. Repository-derived target and selection proof

`RuntimeCheckpointSelectionRequest` has exactly four fields: application generation ID, execution
profile ID, market profile ID, and optional expected `KernelCheckpointRecord`. It contains no
target head/version.

Selection executes the exact SQL manifest. For each scope, controller head must equal protection
`expected_controller_head_ordinal`; active protection generation/stream coordinates must equal
the selected LIVE generation/stream or be wholly absent. The target currentness head is derived as
`max(controller.currentness_head_ordinal)`; with no scopes it is the predecessor head, or zero at
genesis. It must be at least the predecessor head. Target version is predecessor version plus one,
or one at genesis. These derived values are sealed in the proof and outer bytes.

The private selection set fields are, in exact order: scopes, controllers, protection authorities,
generations, generation-current rows, effects, owners, claims, acceptance sets, evidence, closure
heads, root routes, roots, fact heads, current facts, streams, cursors, then ten complementary
absence vectors and twelve query counts. Absence vectors are computed as sorted set complements of
complete parent and found-key vectors; no SQL absence row consumes a child-family limit.

After Q3, require the sum of selected `unresolved_effect_count` values to be at most 65,535. Q4a
selects non-CLOSED effects; Q4b selects late owners paired with their CLOSED effects. Each is
independently capped before the deduplicating qualifying-effect CTE is used. The unique effect
union must equal the Q3 counter sum. This gates CTE work even when one CLOSED effect has many late
owners. Every later found family is independently capped at 65,535 with `LIMIT 65536`.

## 6. Store-time currentness and atomicity

Before inserting bytes, `store_runtime_checkpoint` reruns the entire selection manifest on the
same connection using the proof request. It requires the new proof's predecessor, derived target,
all records, absences, counts, and selection commitment to equal the supplied proof. This makes a
cross-database, post-transaction, or stale-snapshot proof harmless unless the complete selected
state is identical.

Store then requires an authentic `PROJECTED` envelope registered against that exact proof,
derives the payload record, inserts payload, and performs R2's exact absent/found predecessor CAS.
It rereads the resulting head and returns `APPLIED` only on exact equality.

Repository methods never control transactions. Therefore WO-0168c claims only: before caller
commit, the transaction contains either the staged payload plus advanced head or a non-`APPLIED`
result requiring rollback. It does not claim to prevent a malicious caller from committing an
orphan payload. The production `BEGIN IMMEDIATE` owner and mandatory rollback/commit-ambiguity
policy are exact WO-0168b obligations. WO-0168c's file-database fault test uses a named caller
harness that always rolls back non-`APPLIED` and proves old-current/new-current visibility.

Load performs initial head, exact payload, the complete manifest, private load-proof issuance,
bytes-only decode/re-encode, then final head and selected profile comparison. It returns a
registered `LOADED` envelope only after all fields match. Store rejects `LOADED` provenance.

## 7. Application-scoped checkpoint version DDL

The kernel table's current declaration
`checkpoint_version_ordinal INTEGER NOT NULL UNIQUE CHECK (checkpoint_version_ordinal >= 1)` is
replaced exactly by
`checkpoint_version_ordinal INTEGER NOT NULL CHECK (checkpoint_version_ordinal >= 1)`.
The application-generation primary key already scopes the sole current row, while historical
payload identity remains `(application_generation_id, checkpoint_version_ordinal)`. No query or
foreign key relies on global checkpoint-version uniqueness.

R3's complete static DDL delta is the UNIQUE removal plus exactly these indexes:

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

R2's proposed effect index remains deleted because the accepted schema's generation/disposition
index serves the exact manifest. Any resulting DDL bytes require Ameen's exact commit/tree/
SHA-256/byte-count/test-plan approval before execution.

## 8. R3 failure controls

R2's finite matrix remains, with these replacements/additions:

- outer known answer pins the exact 10-member payload and integer `I(scope_id)`;
- execution cases pin all seven map/order commitments by name;
- authenticity cases forge copied/recomputed bindings and simulate weak-registry cleanup/ID reuse;
- selection cases mutate every controller/protection head and derived max/version equation;
- store cases use cross-connection and post-transaction proofs whose predecessor matches but
  selected state differs;
- provenance cases require no DB row for a valid payload-owned inactive descriptor/bootstrap ID
  while refusing the same missing row in a database-complete family;
- Q01 compares every final SQL constant and storage vector to the R3 manifest;
- counter tests prove `cap`, `cap+1`, sum mismatch, and no qualifying CTE before failed sum gate;
- family tests prove found rows and computed absences are independently capped; and
- DDL tests prove two application generations may each use version 1 while duplicate payload
  versions within one application remain refused.

Pure tests remain pre-DDL. Query/plan/DDL/CAS/load/fault cases remain named fresh `tmp_path` file-
database tests behind Ameen's exact changed-DDL gate.

## 9. Held WO-0169/0168b obligations

WO-0168b owns the production transaction context and mandatory rollback on non-`APPLIED`.
WO-0169 alone owns serving constructors, owner lock, omitted-history replay/nonmembership, fresh
head revalidation, bounded behavioral-commitment cutover, and startup/cold fence. No R3 object can
serve before both successors are accepted.
