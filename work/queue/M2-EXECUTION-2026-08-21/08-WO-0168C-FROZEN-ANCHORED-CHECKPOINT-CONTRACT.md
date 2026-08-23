# WO-0168c frozen anchored-checkpoint contract

Status: **PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Base: `0efd9be94d6ecc1238094515fba5accd0e892606`

## 1. Controlling correction

WO-0168h is superseded because snapshot integrity and serving authority were split across functions
that did not possess the same facts. This contract makes one boundary authoritative:

```text
canonical inert bytes
  + repository-issued exact checkpoint proof
  + byte-for-byte current-head binding
  -> one serving checkpoint composition
```

Bytes alone never construct `VenueRecoveryBook`, `ExecutionAuthorityState`,
`AcquisitionControllerState`, `_M2ExecutionObservationProof`,
`_M2ProtectionAuthorityProof`, or any other serving type. Repository rows alone never substitute
for semantic state absent from the relational model. Only the package-private compositor may join
both, and it refuses unless every coordinate and commitment matches.

This contract does not change any existing reducer, cursor, bootstrap, state, proof, or behavior
commitment. It adds no transition proof and does not reinterpret legacy state.

## 2. Closed source annex

The exact scalar, durable-atom, enum, fixed-row, count-wrapper, ordering, limit, and commitment
grammar needed by this contract is the named wire material in
`07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`, SHA-256
`1a0c68ffcf0d6305560abe6e762116ac966639008d647e9c4e7241237adf03bd`, limited to:

- sections 2.1 through 2.4, except that an ordered witness path is never sorted;
- the exact semantic arrays named in sections 3.2 through 5.2; and
- the exact execution-state and protection-checkpoint component arrays already implemented in
  `persistence/checkpoint_codec.py`.

Nothing else in that superseded file is authority. In particular, the following are deleted from
the candidate: `M2VenueTransitionProof`, every replacement cursor-head formula, proof bytes that
decode into an existing serving proof type, owner-only selection predicates that use repository
facts, `TARGETED_LATE_FACT_V1`, operation capabilities, mutable-generation proposals, and sections
8 through 12.

The annex is used only to avoid restating already-fixed field arrays. If an implementation needs a
row not in the closed list above, this contract must be revised and re-reviewed before source work.

## 3. Canonical inert document

`RuntimeCheckpointEnvelope` is the sole public checkpoint value. It is immutable, exact-type,
non-subclassable, and constructor-hidden. Its payload bytes are canonical JSON:

```text
[1,"m2.runtime-checkpoint/v1",
 application_generation_atom,
 execution_profile_sha256,
 market_source_profile_sha256,
 currentness_head_ordinal,
 checkpoint_version_ordinal,
 VenueSnapshot,
 AuthoritySnapshot,
 ScopeSnapshots]
```

`ScopeSnapshots` is `["m2.runtime-checkpoint.scopes/v1",count,rows]`, strictly ordered by
`scope_id`; each row is:

```text
["m2.runtime-checkpoint.scope/v1",scope_id,
 PositionScope,
 AcquisitionSnapshot,
 ExecutionState,
 ProtectionCheckpoint]
```

There is exactly one account-wide venue snapshot and one authority snapshot. Every persisted scope
for the application generation appears exactly once. No operation-targeted proof, receipt, outbox
row, query result, audit ledger, or terminal history appears in payload bytes.

The complete payload is at most 268,435,456 UTF-8 bytes; each owner component is at most
67,108,864 bytes; each collection is at most 65,535 rows; scope count is at most 4,096. Exceeding a
limit refuses checkpoint issuance. There is no truncation, pagination, digest substitution, or
partial serving checkpoint.

`payload_sha256 = sha256(payload_bytes).hexdigest()`. The digest is not inside its own payload.
Every inner commitment is re-derived before the outer digest is accepted.

## 4. Repository-owned completeness proof

`CheckpointProofRequest` contains exactly application generation, execution-profile digest,
market-source-profile digest, currentness head, and checkpoint version. The repository method
`load_checkpoint_proof(connection, request)` runs inside the caller's existing transaction and
returns constructor-hidden `CheckpointProofBundle` only when all of the following are true:

1. the selected application generation and both profiles match exactly;
2. the selected `kernel_checkpoint` matches request head/version and the payload digest;
3. the immutable payload row matches generation/profiles/head/version/digest/length/bytes;
4. every application-generation scope is selected once in increasing `scope_id` order;
5. each scope has exact current acquisition generation, controller, protection authority, and
   optional active market-stream/cursor rows;
6. every active or unresolved venue effect, its claim, late owner, acceptance state/evidence, and
   current closure head needed by the venue snapshot is selected by repository predicates;
7. each current execution root/head and acquisition root route needed by a selected scope is
   selected by direct indexed keys; and
8. exact counts and family commitments over the selected rows equal those recorded in the inert
   document.

The bundle retains the exact immutable records, explicit absence markers, query request, payload
digest, and a private issuer identity plus a seal over every member. It exposes no mutation method.
Construction outside `repository.py` and member replacement fail authenticity.

Completeness is database-owned: SQL selects the full qualifying key set and the codec compares
exact key/count/commitment vectors. It never asks an owner-only projector to infer
`disposition`, late admission, created ordinal, or historical FACT membership. Negative absence is
proved by the selected key set and exact count, not by a caller-supplied Boolean.

All queries are fixed SQL with bound parameters. Query count is constant in history length and
row work is linear only in the bounded selected state. `EXPLAIN QUERY PLAN` must show indexed
search/range access for every family; an unindexed scan, per-row query, dynamic SQL, or hidden
fallback is a failure.

## 5. Projection and decode responsibilities

The encoder accepts exact authentic serving owners plus a matching repository proof bundle. It
uses repository rows to choose the complete bounded set, owner accessors only to supply semantic
members absent from those rows, and refuses any disagreement. Repository-created ordinals define
database discovery order. Ordered execution witness paths remain root-to-terminal; keyed child
sets remain byte-label ordered. The encoder never changes the supplied owners.

The parser accepts payload bytes and creates only private inert component values. It checks exact
JSON, tags, lengths, enum owners/values, scalar types, optionals, counts, ordering, uniqueness,
limits, internal references, child commitments, owner commitments, and canonical re-encoding. It
does not allocate existing serving proof or owner types.

The compositor accepts only `(inert_envelope, authentic_checkpoint_proof_bundle)`. It verifies the
outer coordinates/digest/bytes and every selected-row commitment, then invokes closed private
owner constructors. Execution state is reconstructed only through an execution proof issued from
the bundle's exact root/head/fact witnesses. Protection state is reconstructed only through the
existing `_m2_protection_authority_proof_from_current_proof` path using bundle-derived authentic
`CurrentProofSlice` values. No proof is decoded from payload bytes.

The resulting owners must canonically re-encode to the identical payload bytes before the
compositor returns. Any missing/extra/stale/spliced row, commitment mismatch, constructor failure,
or byte mismatch refuses the whole checkpoint. There is no partially serving result.

## 6. Existing behavior remains authoritative

- Existing venue cursor/bootstrap objects and commitments are serialized exactly as retained and
  reconstructed only by their existing validators. R13-C adds no reducer-time write.
- Existing acquisition state commitment remains behavior authority. The payload must carry enough
  semantic members to reproduce it exactly; otherwise composition refuses.
- Existing execution/protection commitments and proof issuers remain unchanged.
- Retired generation rows remain repository direct authority outside the checkpoint. Only LIVE or
  unresolved rows required by selected current state enter bytes. A late retired-generation fact
  is handled by a separately authenticated operation proof, never by standing checkpoint history.
- Startup remains non-serving until WO-0169 verifies owner lock, cold-recovery fence, and all
  composed owners. This codec alone does not start runtime work.

## 7. Persistence and atomicity

Public persistence additions are exactly `RuntimeCheckpointPayloadRecord`,
`store_runtime_checkpoint_payload`, `load_runtime_checkpoint_payload`,
`CheckpointProofRequest`, `CheckpointProofBundle`, `load_checkpoint_proof`,
`RuntimeCheckpointEnvelope`, `encode_runtime_checkpoint`, and `decode_runtime_checkpoint`.
No generic serializer or public direct-owner constructor is added.

The caller-owned transaction writes the immutable payload before inserting/advancing
`kernel_checkpoint`; the existing reverse-edge triggers require their exact composite identity.
Rollback removes both or retains the old complete head. Load verifies the payload record before
issuing a bundle. Repository methods never begin, commit, roll back, savepoint, attach, detach, or
change pragmas.

The current static `SCHEMA_DDL` candidate is 178,011 UTF-8 bytes with SHA-256
`0460ac5a69d35684ad1ac4ee6571b1a7f04824ed936e0998dac4db645f95544a`. It already contains
`runtime_checkpoint_payload` and the payload-to-head reverse edges. This contract proposes no new
DDL. Any byte change creates a new digest and requires a fresh human gate.

## 8. Failure-capable evidence

Before implementation review, tests and mutants must prove:

1. bytes alone cannot construct any serving proof/owner;
2. a forged/replaced bundle, stale head, profile/scope swap, row splice, false absence, missing or
   extra selected row, or altered count/commitment fails;
3. each existing cursor/bootstrap/acquisition/execution/protection commitment is unchanged;
4. witness path order and keyed-child order are independently pinned;
5. all scalar/tag/length/order/duplicate/optional/limit mutations fail;
6. payload/head write faults yield old-complete or new-complete state;
7. exact payload load is bounded and indexed under large unrelated history;
8. imports are inert and exports are exact; and
9. no source path calls SQLite except repository operations using an explicit connection.

Pure codec RED/GREEN may run after REV-0077 acceptance. No changed-DDL install and no
SQLite-bearing test may run until Ameen approves the exact committed candidate, DDL bytes/digest,
and named fresh-file test plan.

## 9. Held boundary

WO-0168c does not implement unit-of-work reducer composition, startup/owner lock, cold-recovery
fencing, configured database access, migration, runtime wiring, credentials, external I/O, broker
calls, orders, promotion, or merge. WO-0168b, WO-0169, and WO-0170 remain separate reviewed work
orders after this substrate closes.
