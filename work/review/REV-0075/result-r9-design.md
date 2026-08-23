# REV-0075 R9 design result

Exact candidate reviewed: `5932294ee28a848c58aa6bcfda665b96c42526e4`, tree
`4b51e1c60d59d7d497f461cabae0b3fb574e10c5`.

## P1 — Protection hydration copies rather than proves checkpoint scope

Location: `app/execution_core/persistence/checkpoint_codec.py:495`.

Mechanism: `_m2_protection_authority_proof_from_current_proof()` takes the
position scope from the decoded checkpoint. The sealed `CurrentProofSlice`
carries only a repository `ScopeRecord` symbol and the later equality check is
therefore tautological.

Impact: a self-consistent current proof for one repository scope can hydrate a
checkpoint with a different position scope if the selected authority row's
commitment matches that checkpoint.

Smallest complete correction: bind an exact repository-issued `PositionScope`
or equivalent complete scope commitment into `CurrentProofSlice`, require it
to equal `checkpoint.mandate.position_scope` before issuing the protection
proof, and add an otherwise-authentic cross-scope rejection control.

## P1 — Durable-input records accept noncanonical payloads and invalid session coordinates

Location: `app/execution_core/persistence/records.py:300`.

Mechanism: `DurableInputRecord` verifies only payload presence and digest. It
does not decode/re-encode the operation or bind its domain, coordinates, and
primary identity to retained fields. The existing test accepts arbitrary bytes
for a sessionless venue operation, even though only `ObserveVenueStatus` may
omit a session.

Impact: caller-shaped/noncanonical durable inputs can cross the persistence
boundary with incorrect coordinate semantics.

Smallest complete correction: at durable-input construction, decode and
canonical-reencode the operation; require exact domain,
application/profile/scope/session/acquisition/market/stream coordinates and
derived primary identity, allowing a null venue session only for decoded
`ObserveVenueStatus`.

## P1 — Authority semantic keys can attach across application generations

Location: `app/execution_core/persistence/records.py:337`.

Mechanism: the authority-key coordinates bind one application generation but
the record did not require that value to equal the owning durable-input
application generation.

Impact: a semantic identity can be claimed in one application generation's
collision domain while resolving to another's durable input.

Smallest complete correction: require equality for authority-key rows and add
a two-valid-but-distinct application-id rejection test; preserve deliberate
cross-generation venue-key behavior.

## P2 — Protection canonicality control remains unproven

Location: `tests/execution_core/test_protection.py:10144`.

Mechanism: the test does not mutate the protection encoder to prove that the
decoder's final re-encode comparison executes, and malformed-member controls
accept either `TypeError` or `ValueError`.

Impact: a bypass of the protection component's final canonicality gate can
remain green.

Smallest complete correction: use a targeted encoder substitution that makes
the re-encoding differ and pin the exact canonicality failure; tighten
field-local exception assertions.

## Verified prior concerns

- Independent protection expected-wire helpers no longer reuse production
  policy/optional-value codecs.
- The real-state corpus and per-position vectors distinguish all 31 fixed
  protection positions.
- Execution direct-row radix membership, enum/order, null, copied-shape, and
  post-construction controls are present.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=3, P2=1.

Unverified: the reviewer did not rerun pytest, Ruff, mypy, or diff-check.
No SQLite, database creation, runtime composition, network, broker, or order
code was invoked.
