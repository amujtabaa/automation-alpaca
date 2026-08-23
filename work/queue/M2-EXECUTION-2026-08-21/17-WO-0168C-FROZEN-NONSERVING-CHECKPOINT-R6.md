# WO-0168c frozen non-serving checkpoint contract — R6 closure

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO SOURCE OR DATABASE AUTHORITY**

Date: 2026-08-23

Parent: `ef10b6b`

## 1. Recursively closed authority

R6 is this file plus these immutable objects. The two R5 objects are the implementation base; the
two R4 objects supply only the clauses that R5 explicitly retained; the remaining exact imports
are those listed in R5 section 1.

| Full coordinate | SHA-256 | Authority |
| --- | --- | --- |
| `2a096f100644191764b9d12403f3eb5fee823e39:work/queue/M2-EXECUTION-2026-08-21/15-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R5.md` | `ffa9fe8c794dbee0fc84d5bcf426eb071d03843cee30bffda3b584b05e739d39` | all R5 contract text except the exact replacements in R6 |
| `2a096f100644191764b9d12403f3eb5fee823e39:work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md` | `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525` | all R5 SQL/DDL text except the vector-count correction in R6 |
| `7ebc50dd34ba77d7de3adfd01806846e5ed1739d:work/queue/M2-EXECUTION-2026-08-21/13-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R4.md` | `5366ef50830b2bd83b9948e9dd75c85003aa971084fc7daaaa18728df81b7f43` | sections 3-4 public/private types, APIs, exports, outcomes, exceptions; section 5 PACK/COMMIT/INT/TEXT/BYTES/BOOL/NONE/SOME/SEQ and non-envelope formulas; section 7 payload/CAS SQL; section 8 tests only where R5/R6 retains them |
| `7ebc50dd34ba77d7de3adfd01806846e5ed1739d:work/queue/M2-EXECUTION-2026-08-21/14-WO-0168C-R4-SQL-MANIFEST.md` | `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39` | Q2 and Q3a exact SQL only, as corrected by R5/R6 |

R5's six exact imported coordinates and hashes are recursively part of this graph with their R5
clause limits. R4's file-level superseded label means it is not a candidate by itself; the exact
clauses above are intentionally incorporated bytes. R6 wins over R5, then R5 over the named R4
clauses, then R5's earlier imports. Cross-references remain excluded unless this graph names them.

The authority wire additionally imports from R5's exact contract-07 coordinate these exact
section-4.2 children required by the R2 authority top: `VenueRef`; the
`EffectAuthorizationRows` wrapper and `EffectAuthorization` row (R2's `CurrentEffectRows` token is
exactly this wrapper); ClaimRow and its two variants; the `ManualRows` wrapper and ManualFlatten
row; EmergencyGrant; AcquisitionCurrentness; AcquisitionClaimPermit; and
AcquisitionEffectPermit. No contract-07 authority top, descriptor-top, or slot-top form is added.
R2's `m2.authority.Checkpoint/v1`, descriptor, and slot forms remain the sole winners.

No unnamed file, line, conversation, or transitive cross-reference is authority.

## 2. Exact envelope authenticity formulas

`RuntimeCheckpointEnvelope._owner_preimage` is
`_RuntimeCheckpointOwnerPreimage | None`. It is non-null only for `PROJECTED`; it is null only for
`LOADED`. `_provenance` remains a private exact string and is always bound.

Owner rows and owner preimage are exact:

```text
OWNER_ROW(scope,acquisition,execution,protection) =
  COMMIT("execution-core/runtime-checkpoint/scope-owner-row/v1",
         FIELD_INT(scope),FIELD_BYTES(acquisition),FIELD_BYTES(execution),
         FIELD_BYTES(protection))

OWNER_ROWS(rows) =
  SEQ_DOMAIN("execution-core/runtime-checkpoint/scope-owner-rows/v1",
             OWNER_ROW(row) in strictly increasing scope order)

OWNER_PREIMAGE(value) =
  COMMIT("execution-core/runtime-checkpoint/owner-preimage/v1",
         FIELD_BYTES(value.selection_proof_binding),
         FIELD_BYTES(value.venue_owner_commitment),
         FIELD_BYTES(value.authority_owner_commitment),OWNER_ROWS(value.scope_owner_commitments))
```

Envelope common public fields are bound in this exact order:

```text
ENVELOPE_PUBLIC(value) =
  COMMIT("execution-core/runtime-checkpoint/envelope-public/v1",
         FIELD_M1(value.application_generation_id),
         FIELD_TEXT(value.execution_profile_id),FIELD_TEXT(value.market_source_profile_id),
         FIELD_INT(value.currentness_head_ordinal),
         FIELD_INT(value.checkpoint_version_ordinal),
         COMPONENT_BINDING(value.venue),COMPONENT_BINDING(value.authority),
         SEQ_DOMAIN("execution-core/runtime-checkpoint/scope-candidates/v1",
                    SCOPE_BINDING(scope) in exact wire order),
         FIELD_BYTES(value.canonical_payload_bytes),FIELD_TEXT(value.payload_sha256))
```

`COMPONENT_BINDING` and `SCOPE_BINDING` are the exact R4 component/scope top-level formulas.
Before either envelope formula, encoding every public coordinate/component/scope must reproduce
`canonical_payload_bytes` byte-for-byte; its length and SHA-256 text must also match. Therefore a
public-field mutation cannot remain coherent merely because old payload bytes are retained.

Projected binding is exactly:

```text
COMMIT("execution-core/runtime-checkpoint/projected-envelope/v1",
       ENVELOPE_PUBLIC(value),FIELD_TEXT("PROJECTED"),
       FIELD_BYTES(value._selection_binding),OWNER_PREIMAGE(value._owner_preimage))
```

It additionally requires `_selection_binding == owner_preimage.selection_proof_binding` and exact
equality to the supplied authentic selection proof at store. Loaded binding is exactly:

```text
COMMIT("execution-core/runtime-checkpoint/loaded-envelope/v1",
       ENVELOPE_PUBLIC(value),FIELD_TEXT("LOADED"),
       FIELD_BYTES(value._selection_binding),FIELD_NONE)
```

For LOADED, `_selection_binding` is the private load-proof binding and `_owner_preimage is None`.
`_binding` is the formula result and is not recursively included. Tests alter every public field,
every component/scope binding, provenance, selection binding, owner row/member/order, payload byte,
and digest independently through `object.__setattr__`; each must fail fresh re-derivation.

## 3. Vector and storage-class corrections

The imported inventory is exactly 22 vectors in this order:

```text
APP, EXEC_PROFILE, MARKET_PROFILE, HEAD, SCOPE, CONTROLLER, PROTECTION, GENERATION,
GENERATION_CURRENT, EFFECT, OWNER, CLAIM, ACCEPTANCE, EVIDENCE, CLOSURE, ROUTE, ROOT,
FACT_HEAD, FACT, STREAM, CURSOR, PAYLOAD
```

Q01 pins this count, order, every member, and every final expansion. The exact BLOB fields are
`EFFECT.economic_scope` and `PAYLOAD.payload_bytes`; both use FIELD_BYTES. No other imported vector
field is BLOB. Known answers include distinct nonempty values and storage-class mutants for both.

## 4. Runtime transaction-generation lease

The current connection/seal-only runtime token is accepted historical substrate but is not
production-sufficient. Before WO-0168b may issue any production runtime capability, it must add
this exact private lease lifecycle in `repository.py`:

```text
active_runtime_lease[id(connection)] =
    (connection, monotonically_increasing_process_generation, lease_identity)

_RuntimeWriteCapability fields = (_connection, _generation, _lease_identity, _seal)
```

One private RLock guards the registry and monotonically increasing process-local generation.
`_activate_runtime_write_lease(connection)` is callable only from `unit_of_work.py` after its exact
`BEGIN IMMEDIATE` succeeds and `connection.in_transaction is True`; it refuses an existing active
lease, increments generation, creates an uncopyable lease identity, registers it, and returns one
exact capability. `_require_write_capability` accepts runtime authority only when exact type,
seal, connection identity, generation, lease identity, active registry entry, and current
transaction all match. `_retire_runtime_write_lease` removes only the exact matching entry and is
called in the unit-of-work `finally` path immediately before every COMMIT or ROLLBACK attempt. A
commit-return ambiguity therefore has no surviving token. T2 activation on the same connection
always has a new generation/identity and T1's token fails.

WO-0168c implements no production issuer and performs no production runtime write. Its checkpoint
tests use only the exact fresh-fixture setup capability inside an explicit test transaction.
WO-0168b must implement and behavior-test the lease before any runtime path can use checkpoint
store or another runtime mutator. This held obligation is part of WO-0168b's activation preflight,
not an assertion that current source already supplies it.

W00 is split into:

- W00a: checkpoint store rejects missing, arbitrary, forged, subclassed, wrong-seal,
  cross-connection, and out-of-transaction capabilities before any SQL trace or outcome
  translation;
- W00b: the only accepted setup token comes through the named test-support module, on a fresh
  `tmp_path` connection in an explicit transaction; static imports reject every `app/**` or
  unlisted-test issuer/import and behavioral tests reject cross-connection tokens; and
- WO-0168b-W00c: T1 commit and T1 rollback followed by T2 on the same connection each reject the T1
  token, exact lease turnover occurs once, and every exceptional path retires once.

Each case has a source mutant that skips its specific check. Trace assertions prove zero SQL before
authority success.

## 5. Reachable persistence fault table

R5 F00-F10 is replaced by:

| ID | Reachable boundary and expected control |
| --- | --- |
| F00 | injected before payload INSERT; rollback call required despite unchanged durable state |
| F01 | payload INSERT raises SQLite integrity or operational error, which returns INTEGRITY_FAILURE; a non-SQLite injected exception propagates; every variant then rolls back |
| F02 | after successful payload INSERT, before CAS; rollback |
| F03 | CAS execute raises; rollback |
| F04 | test-only CAS-parameter/source mutant forces zero affected rows after full reselection; returns CONFLICT, rollback, and predecessor remains exact |
| F05 | stale full reselection conflict before INSERT; no CAS, rollback |
| F06 | after successful CAS, before reread; rollback |
| F07 | reread raises or separately returns mismatch; rollback |
| F08 | after exact reread, before receipt construction; rollback |
| F09 | receipt construction or identity registration raises; rollback |
| F10 | caller COMMIT raises/returns ambiguously; retire lease, close, reopen, classify old-complete or new-complete only |
| F11 | successful COMMIT control; exact new-complete state and authentic receipt |

The harness records exact BEGIN, INSERT, CAS, reread, receipt, ROLLBACK, COMMIT, close, and reopen
call counts. F00 is killed by a skip-rollback mutant through the call count, not through equivalent
durable state. F04 is not presented as a concurrency schedule: it is a reachable source/parameter
negative control proving the zero-row branch. F05 separately proves stale reselection. F01 has
distinct integrity and operational exception cases and a mutant that continues to CAS.

F00-F09 require one rollback, zero commit, close/reopen, exact predecessor head, no candidate
payload, no candidate head coordinates, and unchanged reverse-edge counts. F10 forbids a second
commit/rollback attempt and accepts only exact old-complete or new-complete after reopen. F11
requires one commit, zero rollback, exact payload/head/digest/length/version/reverse edge, and
receipt. Every omitted call/state assertion has a named mutant.

## 6. Final closure and stop

R5's SQL/DDL, exact APIs/outcomes/exports, remaining binding grammar, known-answer coverage,
selection rules, and test matrix remain unchanged except above. REV-0077 must return exact R6
`ACCEPT` with `P0=0/P1=0` before source/test paths are released. Changed DDL still cannot be
installed and no SQLite-bearing test may run until Ameen approves the exact source candidate
commit/tree, DDL SHA-256/byte count, and named fresh-file test plan.

No serving authority, second engine, configured/in-memory database, migration, runtime
composition, credentials, network/broker/order action, promotion, or merge is authorized.
