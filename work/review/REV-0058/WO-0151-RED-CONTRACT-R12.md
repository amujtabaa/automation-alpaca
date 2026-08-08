# WO-0151 RED contract R12 -- controller-lifetime market-stream provenance

Status: **DRAFT REPLACEMENT PRE-FLIGHT CANDIDATE -- documentation only**

R12 is an additive correction to the accepted R2-R11/R11-R1 E2 composite. It
replaces only the insufficient immediate-predecessor MarketStreamGenerationId
comparison in successor admission with controller-lifetime direct ownership.
Every prior accepted requirement remains controlling except where this
contract makes that ownership proof more exact. R12 grants no source or test
implementation until its exact manifest receives a fresh independent
`ACCEPT`, P0=0/P1=0.

## 1. Unchanged public contract

No public signature, type, enum, export, authority command, venue/protection
surface, or controller status field changes. In particular,
`GenerationRegistry.empty()`, `GenerationRegistry.record(...)`,
`initialize_acquisition_controller(...)`, and
`begin_acquisition_generation(...)` retain their current public signatures.
No public stream-history reader, iterator, map escape hatch, caller-provided
ownership proof, or controller retired-generation collection is added.

## 2. Private direct ownership representation

`GenerationRegistry` gains exactly one private immutable sub-index alongside
its existing direct generation-record map. It maps a domain-separated,
fixed-size key derived from the exact canonical `MarketStreamGenerationId` to
one sealed private route binding:

- the exact stream identity;
- the exact `GenerationBindingView` / acquisition generation identity;
- its application generation, PositionScope, ordinal, complete dual-mandate
  binding commitment, predecessor-or-genesis head commitment, and equal
  emergency-recovery-compatibility provenance through the bound generation
  view; and
- an owner seal that includes the stream and exact binding commitment.

The map is non-enumerable and has no public accessor. Its only permitted
operation is one direct key lookup/insert on a fixed-size derived key. The
registry seal binds both record-map and stream-route-map commitments. The exact
empty registry retains the established E1 empty identity; every nonempty
registry uses a new versioned commitment domain. A pre-R12 nonempty registry
lacking the sub-index is unauthentic and fails closed; M1 performs no upgrade,
hydration, persistence migration, or backfill.

The implementation defines one private owner-local direct lookup helper,
`_registry_market_stream_route(registry, stream_generation)`. It accepts only
an authentic exact registry and canonical stream identity, returns only an
authentic private route or `None`, and is not exported or caller-facing.
`None` means the exact derived key is absent only. If that key exists but its
route is malformed, noncanonical, or key/stream/binding mismatched, the helper
raises `ValueError`; it must never collapse such an entry to `None`. After
first establishing that the retained current state is authentic, successor
admission catches only that candidate-route failure and returns its ordinary
exact `REFUSED` transition. This is the exact test-owned mutation seam for the
candidate lookup; no broad persistent-map monkeypatch or textual source rewrite
is permitted.

## 3. Genesis, successor, replacement, and authenticity rules

1. `initialize_acquisition_controller(...)` seeds one exact route for A's
   complete approved mandate before publishing the controller state.
2. `begin_acquisition_generation(...)` retains every current exact source,
   terminality, flatness, scope/session, distinct identity/binding, equal
   compatibility, ordinal, bootstrap, admission, and immediate-predecessor
   stream inequality check. Before it invokes successor authority registration,
   it performs one direct lookup of the candidate mandate's exact stream in
   the registry. An authentic retained route, or a malformed retained route for
   the *candidate* stream, refuses with the exact prior state, supplied
   refresh/authority/protection references, no receipt, no effect, no claim,
   and no venue transition. A missing or malformed route for the *current*
   mandate makes the predecessor state unauthentic and fails closed as invalid
   input; it does not fabricate a `REFUSED` transition from an unauthentic
   state.
3. A valid fresh stream is inserted atomically in the same pure registry
   transition that retires the old LIVE record and inserts the successor. The
   route is never deleted, reassigned, or replaced by retirement, canonical
   fact/economics replacement, semantic rebase, preemption, exit, or normal
   controller-state rebuilding.
4. Controller-state authenticity directly resolves the current mandate's stream
   and requires its sealed route to match the exact current generation binding,
   application generation, PositionScope, ordinal, and binding commitment.
   Missing, key-mismatched, cross-scope, malformed, stale, or mismatched route
   data is non-authentic. A value-equivalent immutable route copy is not an
   identity failure; only its exact derived-key, stream, and binding relation
   are authority. No authenticity check enumerates a map or walks predecessors.

The index is scope-local because it lives in the one exact serial controller.
Cross-scope reuse is not newly forbidden. `authority.py` must not receive a
duplicate stream index: its currentness slot is intentionally replaceable and
cannot own retired provenance.

## 4. Required failure-capable E2 RED controls

All new controls live in `tests/execution_core/test_acquisition.py` and use
the existing exact E2 test-owned construction seams only.

1. **Nonadjacent reuse:** authenticated A -> B -> fresh complete candidate with
   new acquisition/protection/binding identities but A's stream must return
   `REFUSED` before authority registration. State, authority, venue,
   execution, protection, receipt/effect/claim, and lineage references remain
   exact predecessor values.
2. **Fresh serial successor:** A -> B -> C with three distinct streams remains
   `APPLIED`, advances exactly one ordinal/head/currentness registration, and
   maintains at most one LIVE generation.
3. **Replacement retention:** after an authentic canonical fact replaces a
   generation record, a fresh candidate that reuses that generation's stream
   still refuses. This proves the stream route survives record/economics
   replacement without a scan.
4. **Authenticity fence:** targeted single-field forgeries of the private
   stream route/map or current route relation make controller-state authenticity
   fail closed. A malformed current state must raise/reject as invalid input
   without mutation rather than fabricate a refusal transition. The test must
   not treat a raw stream value, a key-rebound/value-altered route, or a
   caller-built commitment as authority; it must also prove a value-equivalent
   immutable route copy is semantically equivalent rather than relying on
   object identity.
5. **Malformed candidate route:** a state whose current stream route is exact
   but whose candidate-derived key contains a forged or key-mismatched route
   must return the ordinary nonmutating `REFUSED` transition. It may not treat
   that retained malformed entry as a fresh absent stream.
6. **Mutation controls:** (a) bypassing the direct candidate stream lookup
   makes the nonadjacent-reuse control turn RED; (b) dropping/polluting the
   route map during record replacement makes the retention/authenticity control
   turn RED. Restore every mutation before subsequent evidence.

The frozen E3 trace may be re-run only after R12 implementation as external
public confirmation. It cannot be substituted for these E2-owned controls.

## 5. Scope and stop conditions

R12 may change only:

- `app/execution_core/acquisition.py`;
- `tests/execution_core/test_acquisition.py`; and
- directly necessary WO-0151/WO-0152, PKL, ledger, ratification/provenance,
  and REV-0058/REV-0059 evidence records.

It may not add a public API, edit `authority.py`, retain controller history,
scan a registry/audit collection, alter the unchanged 93% gate, introduce a
database/SQL/DDL fixture, touch runtime/broker/network/credentials, change CI,
begin M2, merge, delete, clean up, force-push, or rebase. If the direct index
proves nonconstructible without any one of those exclusions, stop and return
the exact conflict rather than widening the repair.
