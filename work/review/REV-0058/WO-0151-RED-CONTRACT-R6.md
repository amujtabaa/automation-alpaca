# WO-0151 RED contract R6 -- target-local continuity and authenticated refresh

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R6 candidate is the exact R2 body at SHA-256
343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5, the
exact R3 amendment at SHA-256
8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31, the
exact R4 amendment at SHA-256
bd1f4cabb9071d45586ddfa908f0f4db0c538869b53ee34e0a5b16ee0fa1ae91, the
exact R5 amendment at SHA-256
a83bf31578e66b92fdb0e0f27987b9070a127037be2f50490347464a07fffbad, and
this R6 amendment. Every earlier provision remains controlling unless R6
expressly replaces it. R0 through R5 are retained negative evidence and none
is acceptance evidence.

R6 grants no implementation, test implementation, activation, runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, or cleanup authority. It corrects only the remaining target-context
commitment and authenticated refresh seams identified during R5 review.

## 1. Exact replacement of retained venue-context meaning

This section replaces R4 section 1's definition of
`AcquisitionVenueContext.commitment`, and every R4/R5 sentence that makes a
reconciliation cursor, full `ExecutionSnapshot.commitment`, or other
account-wide registry value part of a retained `venue_commitment`.

`AcquisitionVenueContext.commitment` is a domain-separated, venue-owned
commitment of only:

1. the exact `ApplicationGenerationId` and `PositionScope` fence, including
   its application/broker/environment/account coordinates;
2. `scope_execution_commitment` as defined by R5; and
3. the bounded direct target-scope venue summaries required by E2: exact
   `VenueExecutionBinding`, target authority/ownership/closure state,
   cancellation reservation, single-flight state, and direct protection-exit
   state.

It excludes the full `ExecutionSnapshot.commitment`, `SeenFactIndex`
commitment/count, account registry commitment/count, whole
`VenueRecoveryBook` commitment, account-map roots, any reconciliation-required
boolean, reconciliation cursor/count/head, audit/effect/owner/closure history,
every raw venue protection cursor/proof or protection-book envelope, and every
other-symbol direct record. The long-lived
`AcquisitionAuthorityContext.venue_commitment`, controller state/status,
registration, permit, descriptor/view, receipt, projection, and rebase field
named `venue_commitment` or `predecessor_venue_commitment` is exactly this
target-only commitment and no other value.

The full snapshot, account registry, and reconciliation cursor remain required
ephemeral owner checks before a context is minted or accepted. They prove that
the source snapshot is current and coherent; they are never controller
currentness, a retained venue key, or a substitute for one. A clean resolved
other-symbol registry catch-up may therefore change the full source snapshot
and venue book while leaving the target scope token, target venue commitment,
controller head, registration, and target authority commitment exact.

E2 does not retain a raw E1 protection cursor as an acquisition venue key. Its
protection correctness remains bound by the supplied exact
`PositionProtectionState` and its sealed
`AcquisitionProtectionRebaseProjection`; venue context carries only direct
target protection-exit/ownership safety state. This prevents an otherwise
irrelevant E1 registry projection, whose proof may advance a raw protection
cursor, from changing a controller-context commitment.

## 2. Authority-owned authenticated target refresh

Add this public authority-owned, opaque read/result seam. It is the only E2
route that can obtain a fresh target snapshot from an authenticated
account-current source after another symbol advanced the registry:

```python
class AcquisitionContextRefreshDisposition(Enum):
    CURRENT = "CURRENT"
    REFRESHED = "REFRESHED"
    REFUSED = "REFUSED"

class AcquisitionContextRefresh:  # opaque, authority-constructed only
    disposition: AcquisitionContextRefreshDisposition
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    source_execution_snapshot_commitment: bytes | None
    predecessor_execution_snapshot_commitment: bytes | None
    execution_snapshot_commitment: bytes | None
    predecessor_scope_execution_commitment: bytes | None
    scope_execution_commitment: bytes | None
    predecessor_venue_commitment: bytes | None
    venue_commitment: bytes | None
    predecessor_authority_commitment: bytes | None
    authority_commitment: bytes | None
    ordered_venue_transition_commitments: tuple[bytes, ...]
    venue_transitions: tuple[VenueRecoveryTransition, ...]
    predecessor_authority: ExecutionAuthorityState | None
    predecessor_execution: ExecutionSnapshot | None
    predecessor_venue_context: AcquisitionVenueContext | None
    predecessor_authority_context: AcquisitionAuthorityContext | None
    authority: ExecutionAuthorityState | None
    execution: ExecutionSnapshot | None
    venue_context: AcquisitionVenueContext | None
    authority_context: AcquisitionAuthorityContext | None
    commitment: bytes

    def matches_current(
        self,
        state: ExecutionAuthorityState,
        application_generation_id: ApplicationGenerationId,
        position_scope: PositionScope,
    ) -> bool: ...

def refresh_acquisition_context(
    state: ExecutionAuthorityState,
    source_execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> AcquisitionContextRefresh: ...
```

The function derives its application generation only from
`state.venue.scope.generation`. It requires an exact source snapshot and
accepts it only when the existing venue-owned account-current validation proves
it authentic. It
uses the existing private E1 `_authority_execution_for_scope` helper internally
with a deterministic authority-owned namespace derived from the exact
application-generation/target-scope fence, complete target
`VenueExecutionCheckpoint`, prior registry pair, prior source binding, and
authenticated source snapshot commitment; no caller selects any part of that
namespace. `acquisition.py` neither imports nor calls that helper. This gives
each distinct registry advance, including a cursor-only target refresh, one
distinct replay-stable internal catch-up identity.

`CURRENT` is valid only when the retained target snapshot already satisfies the
full owner-side binding, registry, and reconciliation checks. It has no ordered
venue transition and returns the exact existing authority state plus fresh
target contexts. Its predecessor/current source and target-local fields are
equal. `REFRESHED` is valid only when the helper produces one exact
authenticated target registry catch-up. It returns the exact replacement
authority state with that returned book, its exact target snapshot, freshly
projected predecessor/current target venue/authority contexts, and one exact
opaque `VenueRecoveryTransition` whose commitment is the sole entry in both
transition fields. `REFUSED` returns no usable components and leaves the input
authority state unchanged.

The refresh accepts no raw `VenueRecoveryBook`, `CatchUpExecutionRegistry`,
`VenueInputId`, `AuthorityInputId`, controller state/head, registration,
permit, receipt, effect, or caller-selected namespace. It creates no broker
effect, claim, currentness registration, controller transition, or authority
receipt. A refresh is not a currentness-registration source and may never
advance, retire, replace, or replay a controller coordinate. It changes only
the returned authority state's venue book when its authenticated E1 catch-up
is required. Its source snapshot commitment and ordered transition commitment
are sealed source proof only; neither is retained in a controller/currentness
record. The exposed transition may feed only the neutral protection alignment
defined below; it is never a fact relation, aggregate-registration source, or
specialized authority command input.

`AcquisitionContextRefresh` is exact-type, immutable, non-subclassable,
owner-sealed, and rejects copied-field construction. Its `matches_current`
method requires the exact application-generation/scope fence, exact returned
authority state, exact target full-input validation, target venue context, and
target authority context. A `REFUSED` result, copied result, wrong generation,
wrong target scope, stale source, unresolved reconciliation, altered target
binding, or a full snapshot commitment offered in place of its scope token is
non-serving and non-mutating.

## 3. Protection semantic continuity and neutral reprojection

This section replaces every retained E2 field named `protection_commitment` or
`predecessor_protection_commitment` that previously meant a raw
`PositionProtectionState.commitment`. A raw protection state necessarily
contains its full `ExecutionSnapshot.commitment` and venue protection cursor;
those remain exact source-freshness proof, never controller currentness.

Add this protection-owned opaque context and sealed rebase projection. The
projection declaration below replaces R3's
`AcquisitionProtectionRebaseProjection` declaration; its explicit full source
pair is immediate proof only and its retained controller-facing values are the
target semantic contexts below:

```python
class AcquisitionProtectionContext:  # opaque, protection-constructed only
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    scope_execution_commitment: bytes
    scope_protection_commitment: bytes | None
    source_protection_commitment: bytes | None
    commitment: bytes

    def matches_current(
        self,
        book: VenueRecoveryBook,
        execution: ExecutionSnapshot,
        venue_context: AcquisitionVenueContext,
        state: PositionProtectionState | None,
    ) -> bool: ...

class AcquisitionProtectionRebaseKind(Enum):
    SEMANTIC_REBASE = "SEMANTIC_REBASE"
    NEUTRAL_REPROJECTION = "NEUTRAL_REPROJECTION"

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
    predecessor_authority_commitment: bytes | None
    authority_commitment: bytes | None
    predecessor_context_commitment: bytes
    context_commitment: bytes
    predecessor_source_protection_commitment: bytes | None
    source_protection_commitment: bytes | None
    resulting_state: PositionProtectionState | None
    source_venue_transition_commitments: tuple[bytes, ...]
    source_commitment: bytes

def project_acquisition_protection_context(
    state: PositionProtectionState | None,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    venue_context: AcquisitionVenueContext,
) -> AcquisitionProtectionContext | None: ...

def project_acquisition_protection_rebase(
    prior_state: PositionProtectionState | None,
    transition: ProtectionTransition,
    predecessor_context: AcquisitionProtectionContext,
    current_context: AcquisitionProtectionContext,
) -> AcquisitionProtectionRebaseProjection | None: ...

# private helper; exact import permitted only from acquisition.py
def _project_acquisition_neutral_reprojection(
    prior_state: PositionProtectionState | None,
    predecessor_book: VenueRecoveryBook,
    predecessor_execution: ExecutionSnapshot,
    predecessor_venue_context: AcquisitionVenueContext,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    venue_context: AcquisitionVenueContext,
    venue_transitions: tuple[VenueRecoveryTransition, ...],
) -> AcquisitionProtectionRebaseProjection | None: ...
```

`project_acquisition_protection_context` derives application generation only
from its exact venue context and returns a valid no-protection context when
`state` is `None`; it returns `None` for any invalid or stale non-`None` state.
For a present state, `scope_protection_commitment` is domain-separated and
binds its target protection semantics: exact mandate, policy, quantity,
formula availability, hard-bail trigger, activation/high-water/trail values,
waiting-BUY-resolution state, market-generation/occurrence state, and exit
provenance. It also binds the exact target scope execution token. It excludes
the raw protection-state commitment, raw execution snapshot commitment, raw
venue cursor ordinal/head/proof, whole book/registry/reconciliation data, and
all account maps. `matches_current` nevertheless requires the full exact raw
state/book/execution/cursor relation at the immediate serving boundary.

Every long-lived controller/currentness/permit/effect/claim/rebase value named
`protection_commitment` now means that target
`scope_protection_commitment`, or `None` for the valid no-protection context.
Raw source-protection commitments in the projection are immediate proof only.
Normal semantic protection changes use `SEMANTIC_REBASE`, retain exact
predecessor/current raw source proof, and keep the existing registered
`PROTECTION_REBASE` route.

`NEUTRAL_REPROJECTION` is a separate, transport-only branch. It is valid only
for the exact zero-economic, reconciliation-clear, one-transition catch-up
returned by `AcquisitionContextRefresh`; the pre/post target scope execution
tokens, target venue commitments, target authority commitments, and protection
semantic commitments must all be equal. The private helper derives the fresh
raw `PositionProtectionState` from the sealed venue transition without issuing
a goal or alert. It refuses if the transition changes a target economic,
binding, integrity, ownership, closure, reservation, single-flight,
protection-exit, reconciliation, or protection-semantic value.

The neutral branch may replace only the raw protection state, returned
authority/book, and returned full target snapshot in the composite result. It
must preserve the controller state/head/ordinal, currentness registration,
permit, effect, claim, and all retained semantic commitments byte-for-byte. It
must not call `RegisterAcquisitionCurrentness`, create a broker effect, claim,
goal, alert, or other authority operation. A semantic change is never
reclassified as neutral; it must take the existing sealed semantic-rebase or
canonical-fact route.

## 4. One public handoff into non-fact acquisition operations

Replace the raw `(execution, authority)` input pair in these R2 public
acquisition operations with one serving `AcquisitionContextRefresh`:

```python
def initialize_acquisition_controller(
    application_generation_id: ApplicationGenerationId,
    mandate: AcquisitionMandate,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
) -> AcquisitionControllerTransition: ...

def begin_acquisition_generation(
    state: AcquisitionControllerState,
    successor_mandate: AcquisitionMandate,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
) -> AcquisitionControllerTransition: ...

def rebase_acquisition_protection(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    projection: AcquisitionProtectionRebaseProjection,
) -> AcquisitionControllerTransition: ...

def create_acquisition_effect(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    terms: AcquisitionEffectTerms,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...

def claim_acquisition_effect(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    effect_id: EffectId,
    claim_occurrence_id: ClaimOccurrenceId,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...

def begin_acquisition_preemption(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...

def create_acquisition_protection_exit(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
```

Each operation accepts only a `CURRENT` or `REFRESHED` result that matches its
exact application-generation/scope fence. It uses only the result's sealed
target `authority`, `execution`, `venue_context`, and `authority_context`.
Before serving, it projects an exact current `AcquisitionProtectionContext`
from its supplied raw protection state and those result components; a stale raw
protection state is non-serving even when its semantic commitment is unchanged.
When a `REFRESHED` result has a present protection state, the neutral
reprojection must first establish that fresh raw state, or the operation
refuses. Bootstrap/admission projections must match the exact refreshed
contexts, and every specialized command rechecks them immediately before
mutation. A refresh does not relax any existing phase/mode/session/kill/budget,
protection, lineage, controller-head, or final-claim check.

`reduce_acquisition_controller` remains driven by an authenticated canonical
`VenueRecoveryTransition`; its full predecessor/current source proof comes
only from that transition. It does not treat a refresh or neutral reprojection
as a fact relation or registration source. This preserves one canonical fact
applier and prevents a registry catch-up from becoming an aggregate transition.

## 5. R6 failure-capable controls

The composite candidate adds these controls:

| Requirement | Failure-capable control |
|---|---|
| Target-local retained continuity | After a clean other-symbol canonical fact and resolved registry catch-up, a direct stale target snapshot refuses. The authenticated refresh changes the raw full target snapshot, raw E1 protection cursor, and raw protection-state commitment, while the retained target scope execution, venue, authority, and protection semantic commitments, controller head/ordinal, currentness registration, permits, effects, and claims remain byte-for-byte equal. |
| Neutral protection freshness | A current EXIT or HARD_BAIL protection state survives the clean catch-up only through `NEUTRAL_REPROJECTION`; it emits no goal or alert and cannot invoke a currentness registration. A stale raw protection state, missing alignment, wrong transition cardinality, or a nonzero/economically relevant transition refuses. |
| Owner-only refresh | A raw `CatchUpExecutionRegistry` offered directly as an E2 refresh/handoff, private venue helper import/call, caller-made refresh, caller namespace/input ID, unrelated source snapshot, stale/non-prefix/cross-scope source, altered returned transition, or a repeated distinct catch-up with a reused internal identity refuses without any controller or authority mutation. This does not alter the existing E1 authority to apply a valid raw catch-up through its own venue reducer. |
| Full-input versus retained proof | A full snapshot/account-registry/reconciliation or raw protection-state commitment offered as a scope, venue, or protection semantic token refuses. A valid refresh proves full source currency transiently but cannot advance/replay a controller or currentness registration. |
| Relevant target change | A target position/root/integrity/direct binding, target ownership/closure/reservation/single-flight/protection-exit, application-generation, authority, or protection-semantic change alters the relevant target context and makes the old refresh non-serving. |
| Reconciliation safety | An unresolved target or account reconciliation condition produces `REFUSED`, no usable component, no effect eligibility, and no changed controller/currentness state. |
| Current/no-op path | A current target still requires an authenticated account-current source and a fully current raw protection state. `CURRENT` exposes no venue transition, preserves authority state identity, and a second identical refresh is exact and does not add history or state. |

## 6. Focused acceptance

An independent reviewer must compare the exact R2+R3+R4+R5+R6 composite
candidate against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, all retained
R0-R5 results, and the current E1 public seams. Acceptance requires P0=0/P1=0
and a concrete conclusion that the public refresh and neutral protection
reprojection are bounded, authenticated, acyclic, source-compatible, and
preserve one pure controller/fact-applier without history scans, private
acquisition-to-venue access, whole-account retained staleness, a hidden
fifth currentness source, or a second aggregate writer. Any change requires a
new exact freeze and focused review before activation.
