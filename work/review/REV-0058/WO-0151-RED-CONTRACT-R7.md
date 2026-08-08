# WO-0151 RED contract R7 -- lawful authority composition and same-account refresh

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R7 candidate is the exact R2 body at SHA-256
343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5, the
exact R3 amendment at SHA-256
8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31, the
exact R4 amendment at SHA-256
bd1f4cabb9071d45586ddfa908f0f4db0c538869b53ee34e0a5b16ee0fa1ae91, the
exact R5 amendment at SHA-256
a83bf31578e66b92fdb0e0f27987b9070a127037be2f50490347464a07fffbad, the
exact R6 amendment at SHA-256
58839fb965e3bd962ed5ffa0914eed6957a8e7097e35f9ccc8d64c2889a6ff64, and
this R7 amendment. Every earlier provision remains controlling unless R7
expressly replaces it. R0 through R6 are retained negative evidence and none
is acceptance evidence.

R7 grants no implementation, test implementation, activation, runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, or cleanup authority. It corrects only the two source-ownership and
same-account refresh defects found in R6.

## 1. Protection projection carries only protection-owned proof

This section replaces the R6 declaration of
`AcquisitionProtectionRebaseProjection`. It has every R6 field except
`predecessor_authority_commitment` and `authority_commitment`:

```python
class AcquisitionProtectionRebaseProjection:  # opaque, protection-constructed
    kind: AcquisitionProtectionRebaseKind
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    predecessor_execution_snapshot_commitment: bytes | None
    execution_snapshot_commitment: bytes | None
    predecessor_scope_execution_commitment: bytes | None
    scope_execution_commitment: bytes | None
    predecessor_venue_commitment: bytes | None
    venue_commitment: bytes | None
    predecessor_context_commitment: bytes
    context_commitment: bytes
    predecessor_source_protection_commitment: bytes | None
    source_protection_commitment: bytes | None
    resulting_state: PositionProtectionState | None
    source_venue_transition_commitments: tuple[bytes, ...]
    source_commitment: bytes
```

Those two removed values are authority-owned facts, not protection facts.
Neither `project_acquisition_protection_rebase` nor
`_project_acquisition_neutral_reprojection` accepts, synthesizes, or seals an
authority context, authority commitment, authority state, or caller-provided
authority bytes. Their sealed proof remains limited to the predecessor/current
protection contexts, venue/execution source proof, and the exact resulting
protection state that `protection.py` can authenticate without importing
`authority.py`.

For `NEUTRAL_REPROJECTION`, `acquisition.py` is the composition owner. Before
it accepts the protection-owned projection, it must verify the complete sealed
authority pair inside its `AcquisitionContextRefresh`:

1. the refresh is exact `REFRESHED`, and its predecessor/current authority,
   execution, venue-context, and authority-context components are all present
   and mutually exact;
2. each sealed `AcquisitionAuthorityContext` matches its corresponding sealed
   authority/execution/venue-context triple through its public matcher;
3. the controller state's application-generation, scope, predecessor scope,
   venue, and protection values match the refresh predecessor and
   protection-projection predecessor values, and its
   `authority_context_commitment` equals
   `refresh.predecessor_authority_context.commitment`; and
4. `refresh.predecessor_authority_context.commitment` exactly equals
   `refresh.authority_context.commitment`, their target
   `authority_commitment` values exactly equal, and the current
   venue/execution contexts match the protection projection's current values.

The comparison uses only fields from the opaque authority-owned refresh and
public matchers. It does not expose an authority map, create an authority
command, or allow a caller to supply a comparison pair. If any component,
matcher, equality, or semantic protection check fails, the neutral route
refuses without changing the controller, currentness, permit, effect, claim,
or authority state. Normal semantic rebase and canonical-fact behavior remain
unchanged.

## 2. Exact same-account source rule for refresh

R6's refresh source rule is clarified as follows. `source_execution` may be
either the exact target `PositionScope` or a different `PositionScope` only
when its broker, environment, and account coordinates exactly equal the target
scope and the current `ExecutionAuthorityState.venue.scope` fence. Its
application generation is therefore the authority-derived generation already
sealed by the venue book; the source never selects or supplies a generation.

Regardless of whether the source symbol is the target or another symbol, the
existing venue-owned checks must prove that the source is exactly bound to the
current book, current at the account registry high-water, reconciliation-prefix
valid, and a valid predecessor of the retained target snapshot. The target
checkpoint, target binding, and returned target context remain exact and are
never selected by the source.

The refresh refuses a source with any foreign broker, environment, account, or
venue generation; a source that is unbound, stale, non-prefix, unresolved,
incoherent, or substituted for the retained target; or any caller-assembled
context/result. “Cross-scope” in R6's negative controls means one of those
foreign or spliced cases, not an authenticated other-symbol source under the
same exact account fence.

## 3. R7 failure-capable controls and acceptance

The composite candidate adds these controls:

| Requirement | Failure-capable control |
|---|---|
| Lawful neutral composition | A protection projection carries no authority pair. A neutral reprojection accepts only when the opaque refresh supplies matching predecessor/current authority contexts that independently match their sealed state/execution/venue triples and the retained controller authority context. A caller-supplied pair, missing component, mismatched authority context, or direct protection-to-authority dependency refuses before mutation. |
| Same-account source boundary | An exact current source from another symbol under the same broker/environment/account and authority generation performs the required target refresh. A foreign-account/environment/broker/generation source, unbound/stale/non-prefix source, or source substituted for the target checkpoint refuses. |
| Existing neutral boundary | The valid clean catch-up still changes only the returned raw authority/book/target snapshot/protection state. Controller head/ordinal, currentness, retained semantic commitments, permits, effects, claims, goals, alerts, registrations, and fact/aggregate authority remain unchanged. |

An independent reviewer must compare the exact R2+R3+R4+R5+R6+R7 composite
candidate against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, all R0-R6
retained results, and current E1 source seams. Acceptance requires P0=0/P1=0
and a concrete conclusion that authority-pair validation has one lawful owner,
same-account cross-symbol source refresh is precise, and the bounded pure
controller/fact path remains unchanged. Any change requires a new exact freeze
and focused review before activation.
