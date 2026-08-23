# WO-0168c frozen non-serving checkpoint contract — R5

Status: **PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `7ebc50d`

## 1. Closed authority graph

R5 is this file plus `16-WO-0168C-R5-SQL-MANIFEST.md`. It imports only the following immutable
objects. Each coordinate is full `commit:path`; the SHA-256 is over that object's file bytes.

| Coordinate | SHA-256 | Exact imported material |
| --- | --- | --- |
| `8d70951d69f034da98bf6f13ce0dd42eff336b48:work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md` | `41d8b423ae6b471b12325cd0ad0e5e73cdcd17bf872dad8bc273b0ce8d0a6ba1` | R12.5 exact runtime/setup capability and test-support boundary only |
| `8d70951d69f034da98bf6f13ce0dd42eff336b48:work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md` | `1a0c68ffcf0d6305560abe6e762116ac966639008d647e9c4e7241237adf03bd` | 2.2 semantic arrays; 2.3 enum spellings; 3.2 23-member venue top; 3.3 venue rows except the old 23-member `M2VenueTransitionProof` and its old BootstrapTarget forms; 4.2 only ClaimRow, AcquisitionClaimPermit, ManualFlatten, EmergencyGrant, AcquisitionCurrentness, and AcquisitionEffectPermit rows; 5.2 acquisition rows |
| `8d70951d69f034da98bf6f13ce0dd42eff336b48:work/queue/M2-EXECUTION-2026-08-21/10-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R2.md` | `767c1249c29e3235602a555a1d49022706022ed1c1ca4990b7f9d657ef3473e1` | section 2 canonical wire grammar; section 4 corrected 25-member active bootstrap and corrected 25-member `m2.venue.ProtectionTransitionProof/v1`; section 5 14-member `m2.authority.Checkpoint/v1`, descriptor and slot rows; section 6 source-order rules |
| `05e5204d4b90f3ed67345f62f59438485921c137:work/queue/M2-EXECUTION-2026-08-21/11-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R3.md` | `ee31dda649c700438dc55642a91daee42dc6b2eac8634119ae159aea519fa3cb` | sections 2, 4, 5, 6, 7 and 9 except every type/API/binding/query/index/test surface replaced by R5 |
| `8d70951d69f034da98bf6f13ce0dd42eff336b48:work/queue/M2-EXECUTION-2026-08-21/12-WO-0168C-R3-SQL-MANIFEST.md` | `f1cae0c9af8a6b906497864e03311158ecdfae2ff37a7f7cd23c59c542bbd069` | section 2 flattened storage vectors only |
| `8d70951d69f034da98bf6f13ce0dd42eff336b48:app/execution_core/persistence/schema.py` | `39605a430c24a69d8dd985535cf5923122c2fe8eb451b26d79aaebab72c394ce` | accepted SQL storage classes, nullability, keys, relationships, and pre-R5 indexes only; R5's explicit static delta overrides it |

Imports include literal rows, tags, scalar forms, enum members, limits, ordering, and validations
inside the named material. They do not import cross-references unless separately named above.
Explicitly excluded from contract 07 are its authority top (`m2.authority.State/v1`), authority
descriptor/slot top forms, old transition proof, old active/consumed bootstrap forms, serving owner
construction, R13-H scope, and completeness claims. R2's corrected bootstrap and
`m2.authority.Checkpoint/v1` always win. Explicitly excluded from R2/R3 are issuer sentinels,
request target coordinates, old APIs/CAS/outcomes, twelve-query claims, prior SQL/DDL/index/plan
text, and old test matrices. R5 wins over its SQL manifest only for non-SQL policy; the R5 SQL
manifest wins for query/index/vector mechanics. Nothing else is authority.

## 2. Frozen payload and provenance boundary

The exact outer 10-member payload, integer-scope row, exact 21-member execution component, exact
32-member protection component, database-complete families, payload-owned semantics,
repository-derived target head/version, store-time reselection, caller transaction ownership,
load revalidation, application-scoped checkpoint version correction, and successor obligations are
the named R3 imports. Venue is the exact 23-member top from contract 07 with the corrected R2
bootstrap rows. Authority is only the R2 14-member `m2.authority.Checkpoint/v1`. No old authority
top or old transition proof is admitted.

The result is inert and non-serving. It constructs no existing owner, serving proof, reducer,
startup capability, or alternate authority source. WO-0168b owns production transaction
composition; WO-0169 alone owns owner-locked serving conversion and startup eligibility.

## 3. Complete object and API surface

R4 sections 3-4 are retained with these exact corrections.

`RuntimeCheckpointEnvelope` adds one constructor-hidden field:

```python
_owner_preimage: _RuntimeCheckpointOwnerPreimage
```

The private frozen/slotted exact `_RuntimeCheckpointOwnerPreimage` has fields in order:

```python
selection_proof_binding: bytes
venue_owner_commitment: bytes
authority_owner_commitment: bytes
scope_owner_commitments: tuple[tuple[int, bytes, bytes, bytes], ...]
```

Scope tuples are strictly increasing by scope ID and contain exact acquisition, execution, and
protection owner commitments. Projection builds this value only after authenticating each source
owner. Projected-envelope binding is freshly re-derived from this retained preimage plus public
payload fields. Store requires `preimage.selection_proof_binding` to equal the supplied authentic
proof binding and every scope coordinate to equal the envelope scopes before accepting registry
authenticity. Registry metadata remains only `(weakref, binding, provenance)`; it is never a
substitute for re-derivation. Loaded envelopes retain an exact empty owner preimage whose selection
proof binding is the private load-proof binding and whose two owner commitments and scope tuple are
empty; provenance separates that formula and store rejects it.

Exact signatures are:

```python
encode_runtime_checkpoint(envelope: RuntimeCheckpointEnvelope) -> bytes

select_runtime_checkpoint(connection: _SQLiteConnectionProtocol,
    request: RuntimeCheckpointSelectionRequest)
    -> RepositoryOutcome[RuntimeCheckpointSelectionProof]

store_runtime_checkpoint(connection: _SQLiteConnectionProtocol,
    proof: RuntimeCheckpointSelectionProof,
    envelope: RuntimeCheckpointEnvelope, *, capability: _WriteCapability)
    -> RepositoryOutcome[RuntimeCheckpointWriteReceipt]

load_runtime_checkpoint_payload(connection: _SQLiteConnectionProtocol,
    application_generation_id: ApplicationGenerationId,
    currentness_head_ordinal: int, checkpoint_version_ordinal: int,
    payload_sha256: str) -> RepositoryOutcome[RuntimeCheckpointPayloadRecord]

load_runtime_checkpoint(connection: _SQLiteConnectionProtocol,
    request: RuntimeCheckpointLoadRequest)
    -> RepositoryOutcome[RuntimeCheckpointEnvelope]
```

The connection is the same exact object retained by a capability. Production checkpoint store
admits only exact `_RuntimeWriteCapability`, current for that connection and transaction. Exact
`_SetupWriteCapability` is admitted only when issued through
`tests/execution_core/persistence_setup_support.py` for a fresh `tmp_path` fixture connection; no
`app/**` caller may obtain/import it. Missing, forged, subclassed, stale, cross-connection, or
out-of-transaction runtime authority raises the existing exact `TypeError`/`ValueError` from
`_require_write_capability`; repository outcome translation starts only after authority succeeds.
Tests substitute runtime/setup/forged/cross-connection tokens at the exact boundary and enforce
this production-versus-fixture policy.

Exports and outcomes remain R4 section 4. The payload load does not require a transaction;
selection, store, and composed load require `connection.in_transaction is True` and return
`INTEGRITY_FAILURE` if the caller has not established a stable transaction.

## 4. Byte-complete binding grammar

R4 PACK, COMMIT, INT, TEXT, BYTES, BOOL, NONE, SOME, SEQ and nine top-level domains remain exact.
The following removes every remaining shorthand.

Scalar field bindings are exactly:

```text
FIELD_NONE = COMMIT("execution-core/runtime-checkpoint/field/absent/v1")
FIELD_BOOL(v) = COMMIT("execution-core/runtime-checkpoint/field/bool/v1", BOOL(v))
FIELD_INT(v) = COMMIT("execution-core/runtime-checkpoint/field/int/v1", INT(v))
FIELD_TEXT(v) = COMMIT("execution-core/runtime-checkpoint/field/text/v1", TEXT(v))
FIELD_BYTES(v) = COMMIT("execution-core/runtime-checkpoint/field/bytes/v1", BYTES(v))
```

The M1 field algorithm is exact and recursive:

```text
ATOM_TEXT(v) = COMMIT("execution-core/runtime-checkpoint/atom-text/v1", TEXT(v))
ATOM(atom) = COMMIT("execution-core/runtime-checkpoint/durable-atom/v1",
                    TEXT(atom.contract_version), TEXT(atom.type_tag), INT(len(atom.fields)),
                    each(ATOM_TEXT(field) when exact str else ATOM(field)))
FIELD_M1(v) = COMMIT("execution-core/runtime-checkpoint/field/m1-value/v1",
                     ATOM(encode_m1_value(v)))
```

An atom field that is neither exact `str` nor exact `DurableAtom` fails. No source-current-proof
domain is reused. Selection request and envelope application IDs use FIELD_M1. Repository records
bind their exact flattened storage vector from the R3 vector import after record validation and
deterministic storage projection: SQL NULL uses FIELD_NONE; declared Boolean columns use
FIELD_BOOL; declared integer columns use FIELD_INT; BLOB columns use FIELD_BYTES; all other SQL
text columns use FIELD_TEXT. The declared Boolean columns are OWNER.admitted_after_effect_closed,
ROOT.price_present, FACT.price_present, and every schema Boolean inside no other imported vector;
all `CASE ... presence` values and query counts are FIELD_INT, not Boolean. PAYLOAD.payload_bytes is
the sole BLOB column. Every remaining vector column's storage class is fixed by the accepted
schema and its R3 vector order; a storage-class mismatch fails before binding.

Each of the exact nineteen record sequences has its own literal sequence domain:

```text
execution-core/runtime-checkpoint/records/{scopes,controllers,protections,
live-generations,live-generation-current,unresolved-generations,
unresolved-generation-current,effects,owners,claims,acceptance-sets,evidence,
closure-heads,root-routes,roots,fact-heads,current-facts,streams,cursors}/v1
```

Each item is
`COMMIT("execution-core/runtime-checkpoint/record/v1",TEXT(record-tag),INT(field-count),fields...)`.
Record tags are exactly `scope/v1`, `controller/v1`, `protection/v1`, `generation/v1`,
`generation-current/v1`, `effect/v1`, `owner/v1`, `claim/v1`, `acceptance/v1`, `evidence/v1`,
`closure/v1`, `route/v1`, `root/v1`, `fact-head/v1`, `fact/v1`, `stream/v1`, and `cursor/v1`;
LIVE/unresolved sequences share the same generation tags. Sequence order is section 3's exact
nineteen-field order.

Absence-key bytes are exact commitments:

| Family | Domain suffix | Ordered key preimage |
| --- | --- | --- |
| `owner/effect` | `owner-effect` | FIELD_INT(effect_id) |
| `claim/effect` | `claim-effect` | FIELD_INT(effect_id) |
| `acceptance/effect` | `acceptance-effect` | FIELD_INT(effect_id) |
| `evidence/acceptance` | `evidence-acceptance` | FIELD_INT(acceptance_set_id) |
| `closure/owner` | `closure-owner` | FIELD_INT(scope_id), FIELD_TEXT(owner_external) |
| `route/owner` | `route-owner` | FIELD_INT(effect_id), FIELD_TEXT(owner_external), FIELD_TEXT(observation_external) |
| `fact-head/root` | `fact-head-root` | FIELD_INT(root_fill_key_id) |
| `current-fact/root` | `current-fact-root` | FIELD_INT(root_fill_key_id) |
| `stream/generation` | `stream-generation` | FIELD_TEXT(acquisition_generation_id) |
| `cursor/stream` | `cursor-stream` | FIELD_TEXT(stream_generation_id) |

For suffix `s`, key bytes are
`COMMIT("execution-core/runtime-checkpoint/absence-key/" || ASCII(s) || "/v1", parts...)`.
An absence item is
`COMMIT("execution-core/runtime-checkpoint/absence/v1",TEXT(literal-family),BYTES(key))`.
Each absence vector uses
`SEQ_DOMAIN("execution-core/runtime-checkpoint/absences/" || ASCII(s) || "/v1", items)`, where
`SEQ_DOMAIN(domain,items)=COMMIT(domain,INT(count),*items)`. The selection set commits nineteen
record sequences, then these ten absence sequences in table order, then
`SEQ_DOMAIN("execution-core/runtime-checkpoint/query-counts/v1", FIELD_INT(count)...)` for exactly
thirteen counts.

The selection proof and projected/loaded envelope formulas are R4 section 5 with the corrected
owner preimage above. `selection_commitment` is the exact selection-set COMMIT. Every private
field appears in its value's formula.

Binding known-answer tests contain independently calculated literal packed/digest hex for:

- FIELD_NONE, FIELD_BOOL(false), FIELD_BOOL(true), FIELD_INT(-1/0/1/255/256), empty/non-ASCII
  FIELD_TEXT, empty/non-empty FIELD_BYTES, a leaf atom, and one nested atom;
- one nonempty representative of every record tag and all nineteen sequence domains, including
  every optional storage field both absent and present across the finite case table;
- one nonempty key/item/vector for every absence family, plus all ten empty vectors;
- zero and thirteen nonzero query counts; genesis and found-predecessor requests/proofs;
- component, scope, projected envelope with nonempty owner preimage, loaded envelope, and receipt.

Expected bytes/digests are literals in tests and may not be generated by production helpers.
Every domain, polarity, sign, length, tag, field storage class, optional, order, key member, private
preimage member, count, and digest has a named single-source mutant.

## 5. Selection and persistence corrections

The exact R5 SQL manifest replaces all prior query/index/plan text. Q1 selects by application ID
alone, allowing `ABSENT` versus profile `CONFLICT`. Q2 has complete present/missing null rules.
Q3b uses two predicate-matched partial-index arms inside one separately capped query. Every later
generation CTE includes the same current-row join as Q3a and the same two unresolved arms under a
stable caller snapshot. No impossible runtime comparison is claimed; a static exact-fragment test
and child-parent checks prove parity.

After Q3a and Q3b validation, the repository forms their canonical coordinate union and refuses a
65,536th combined selected generation before Q4. Q3b and the combined union are canonical-sorted
in Python only after bounded admission; no unbounded SQL sort is used.

Every variable child family is admitted with `LIMIT 65536` before canonical sorting. A returned
65,536th sentinel refuses without constructing a selection set. Tests exercise 65,535 and 65,536
rows attached to selected parents, not only unrelated history.

Payload INSERT and absent/found head CAS remain exactly R4 section 7. Store reruns all thirteen
queries and compares the complete selection binding before payload insert. It returns `APPLIED`
only after exact head reread and receipt registration.

## 6. Complete persistence fault matrix

The fresh-file caller harness owns BEGIN/ROLLBACK/COMMIT. It injects at every exact boundary:

| ID | Boundary |
| --- | --- |
| F00 | before payload INSERT |
| F01 | after payload INSERT, before head CAS |
| F02 | head CAS raises |
| F03 | head CAS affects zero rows (`CONFLICT`) |
| F04 | after successful head CAS, before exact reread |
| F05 | exact reread raises |
| F06 | exact reread returns mismatch |
| F07 | after exact reread, before receipt construction |
| F08 | receipt construction or identity registration raises |
| F09 | caller COMMIT raises with outcome unknown |
| F10 | successful COMMIT control |

For F00-F08, any exception or non-`APPLIED` result forces caller rollback, connection close, and
independent reopen. Reopen must show the exact predecessor head, no candidate payload row, no head
reference to candidate digest/version, and unchanged reverse-edge counts. F03 also proves a
competing exact head remains intact. F09 closes without a second commit/rollback attempt and
reopens to classify only exact old-complete or new-complete; an orphan payload, missing payload for
head, mixed head coordinates, or duplicate version fails. F10 proves exact new payload, head,
digest/length/version, reverse edge, and authentic receipt. Mutants independently commit after
each F00-F08 boundary, skip rollback, retry ambiguous commit, omit each reopen assertion, and issue
a receipt before reread.

## 7. Final named test controls and gate

R4's matrix remains with these replacements/additions:

- B01 covers every literal known answer in section 4; B02 covers registry identity reuse; B03
  removes every retained owner-preimage and private field independently;
- Q01 pins exact SQL/fragments/vectors/counts and the full `commit:path` authority table;
- Q02 covers Q1 absence/profile conflict and Q2 valid inactive/missing/partial-null cases;
- Q03 covers both unresolved partial-index arms, LIVE-current parity, each cap boundary, and
  selected-parent child cap before sort;
- Q04 covers counters, all nonempty absence keys, and all partitions;
- Q05 covers exact aliases/index names, allowed bounded sorts, hard-index absence, and reachable
  `NOT INDEXED` scans;
- W00 substitutes setup/runtime/forged/stale/cross-connection capabilities;
- W03 is the exact F00-F10 table; W04 proves repository requires but never controls transaction.

Pure binding/wire/authenticity tests may run only after REV-0077 accepts R5 and exact source paths
are released. All SQL/query/DDL/CAS/load/fault tests remain held behind Ameen's changed-DDL gate.
No source, test, DDL, SQLite, serving, runtime-composition, external-I/O, promotion, or merge action
is authorized by this documentation candidate.
