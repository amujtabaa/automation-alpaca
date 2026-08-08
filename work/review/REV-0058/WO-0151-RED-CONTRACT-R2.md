# WO-0151 RED contract R2 -- serial acquisition controller and bounded recovery

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

R2 is a complete replacement RED candidate. R0 and R1 remain retained negative
evidence and neither is accepted. R2 grants no implementation until an
independent review accepts this exact body with P0=0/P1=0 and the work order is
activated. It grants no runtime, persistence, database, broker, credential,
network, CI-workflow, M2, merge, deletion, or cleanup authority.

## One coherent pure state model

E2 has one pure composite result, not a new writer or service. The canonical
execution/venue reducer remains the sole aggregate fact applier. E2 receives
its exact authenticated outcome once, classifies direct acquisition lineage,
updates only the affected generation record/controller currentness, rebases
the authority state, and returns the complete next pure component set. M2 alone
will make that set durable atomically.

`SymbolAcquisitionController` is constant-size: scope, head, ordinal, one LIVE
generation coordinate, recovery class, component commitments, and immutable
compatibility commitment. It contains no retired generation or route collection.
`GenerationRegistry` owns generation-local current economics/closure/serving
state; `AcquisitionLineageIndex` owns immutable direct routes. Both remain
opaque/non-enumerable direct readers.

Every serving decision needs all relevant sealed components: venue proof,
authority proof, protection state/proof, controller state, and canonical
execution. A missing/mismatched/stale/forked/copied component is non-serving
and leaves every component unchanged. No decision may scan audit/history
materializers or reconstruct a fact from a snapshot.

## Module ownership and fixed dependency direction

| Module | R2 ownership | May import R2 concepts from |
|---|---|---|
| `identity.py` | `AcquisitionMandateId`, `EmergencyRecoveryCompatibilityId` | no E2 module |
| `venue.py` | target bootstrap/fact relation projections | no E2 module |
| `protection.py` | compatibility, sealed protection transition/rebase projection, mixed recovery | `identity.py`, `venue.py` |
| `authority.py` | admission proof, currentness/permit/receipt types, specialized commands and effect view | `identity.py`, `position.py`, `venue.py` |
| `acquisition.py` | mandate/binding, state/registry/lineage, composite reducers | all four modules above |

`venue.py` imports no acquisition/protection/authority module. `protection.py`
and `authority.py` import neither acquisition nor each other. `acquisition.py`
uses no private venue member. No local/dynamic import, reflection, time/random
source, unlisted raw factory, public mapping/iterator escape, or history
materializer is permitted in the R2 path.

## Frozen public interface

```python
# identity.py
class AcquisitionMandateId: ...
class EmergencyRecoveryCompatibilityId: ...

# venue.py
class AcquisitionVenueSourceKind(Enum):
    BOOTSTRAP = "BOOTSTRAP"
    CANONICAL_ECONOMIC_FACT = "CANONICAL_ECONOMIC_FACT"
    CANONICAL_ECONOMIC_FACT_RECONCILIATION = (
        "CANONICAL_ECONOMIC_FACT_RECONCILIATION"
    )

class AcquisitionFactRelation:  # opaque, venue-constructed, read-only
    position_scope: PositionScope
    fact_key: ExecutionFactKey
    root_key: RootFillKey
    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    leg_key: VenueLegKey
    source_commitment: bytes

class AcquisitionVenueProjection:  # opaque, venue-constructed only
    source_kind: AcquisitionVenueSourceKind
    position_scope: PositionScope
    predecessor_execution_commitment: bytes | None
    execution_commitment: bytes
    predecessor_venue_commitment: bytes | None
    venue_commitment: bytes
    source_commitment: bytes

    def fact_relation(self) -> AcquisitionFactRelation | None: ...
    def matches_bootstrap(
        self,
        execution: ExecutionSnapshot,
        book: VenueRecoveryBook,
        position_scope: PositionScope,
    ) -> bool: ...
    def matches_fact_transition(
        self,
        transition: VenueRecoveryTransition,
        position_scope: PositionScope,
    ) -> bool: ...
    def matches_predecessor_book(
        self,
        book: VenueRecoveryBook,
        position_scope: PositionScope,
    ) -> bool: ...

class VenueRecoveryBook:
    def project_acquisition_bootstrap(
        self,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> AcquisitionVenueProjection: ...
    def project_acquisition_fact(
        self,
        transition: VenueRecoveryTransition,
    ) -> AcquisitionVenueProjection: ...

# protection.py
class EmergencyRecoveryCompatibility:
    compatibility_id: EmergencyRecoveryCompatibilityId
    position_scope: PositionScope
    session_id: SessionId
    configuration_version: str
    configuration_commitment: bytes
    emergency_guard: ExecutionGuard
    maximum_goal_rate: int
    emergency_effect_budget: int
    deadline: int
    aggregate_emergency_quantity: Quantity
    commitment: bytes

class ProtectionMandate:
    ...
    emergency_recovery_compatibility: EmergencyRecoveryCompatibility
    commitment: bytes

class ProtectionTransition:  # opaque, reducer-constructed only
    state: PositionProtectionState
    disposition: ProtectionDisposition
    goal: ExecutionGoal | None
    critical_alert: ProtectionAlert | None

class AcquisitionProtectionRebaseProjection:  # opaque, protection-constructed
    position_scope: PositionScope
    predecessor_protection_commitment: bytes | None
    protection_commitment: bytes
    execution_commitment: bytes
    source_commitment: bytes

class AcquisitionMixedRecoveryProof: ...  # opaque, reducer-constructed only

def project_acquisition_protection_rebase(
    transition: ProtectionTransition,
) -> AcquisitionProtectionRebaseProjection: ...

def force_acquisition_mixed_recovery(
    prior_state: PositionProtectionState | None,
    mandate: ProtectionMandate,
    venue_projection: ProtectionVenueProjection,
    proof: AcquisitionMixedRecoveryProof,
) -> ProtectionTransition: ...

# private helper; exact import permitted only from acquisition.py
def _mint_acquisition_mixed_recovery_proof(...) -> AcquisitionMixedRecoveryProof: ...

# authority.py
class AcquisitionAdmissionProjection:  # opaque, authority-constructed
    position_scope: PositionScope
    execution_commitment: bytes
    venue_commitment: bytes
    authority_commitment: bytes
    source_commitment: bytes

class AcquisitionAuthorityOperation(Enum):
    REGISTER = "REGISTER"
    CREATE = "CREATE"
    CLAIM = "CLAIM"
    PREEMPT = "PREEMPT"
    PROTECTION_EXIT = "PROTECTION_EXIT"

class AcquisitionAuthorityReceipt:  # opaque, authority-constructed
    operation: AcquisitionAuthorityOperation
    position_scope: PositionScope
    predecessor_controller_head: bytes
    controller_head: bytes
    predecessor_execution_commitment: bytes
    execution_commitment: bytes
    predecessor_venue_commitment: bytes
    venue_commitment: bytes
    predecessor_authority_commitment: bytes
    authority_commitment: bytes
    ordered_venue_transition_commitments: tuple[bytes, ...]
    permit_commitment: bytes
    commitment: bytes

class AcquisitionOrderType(Enum):
    LIMIT = "LIMIT"

class AcquisitionEffectTerms:
    quantity: Quantity
    limit_price: ReportedPrice
    order_type: AcquisitionOrderType
    evaluation_time: int
    commitment: bytes

class AcquisitionCurrentnessRegistration: ...  # opaque
class AcquisitionEffectPermit: ...             # opaque
class AcquisitionClaimPermit: ...              # opaque
class AcquisitionExitPermit: ...               # opaque
class AcquisitionClaimReceipt:                 # opaque, read-only
    effect_id: EffectId
    claim_occurrence_id: ClaimOccurrenceId
    controller_head: bytes
    execution_commitment: bytes
    venue_commitment: bytes
    commitment: bytes

class AcquisitionEffectView:                   # bounded, read-only
    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    client_order_id: ClientOrderId
    position_scope: PositionScope
    generation_id: AcquisitionGenerationId
    binding_commitment: bytes
    controller_head: bytes
    terms: AcquisitionEffectTerms
    terms_commitment: bytes
    economic_scope: bytes
    serving: bool
    commitment: bytes

class RegisterAcquisitionCurrentness:
    input_id: AuthorityInputId
    registration: AcquisitionCurrentnessRegistration
class CreateAcquisitionEffect:
    input_id: AuthorityInputId
    permit: AcquisitionEffectPermit
class ClaimAcquisitionEffect:
    input_id: AuthorityInputId
    effect_id: EffectId
    claim_occurrence_id: ClaimOccurrenceId
    permit: AcquisitionClaimPermit
class BeginAcquisitionPreemption:
    input_id: AuthorityInputId
    permit: AcquisitionExitPermit
class CreateAcquisitionProtectionExit:
    input_id: AuthorityInputId
    permit: AcquisitionExitPermit

class ExecutionAuthorityTransition:
    ...
    acquisition_receipt: AcquisitionAuthorityReceipt | None
    acquisition_claim_receipt: AcquisitionClaimReceipt | None

def project_acquisition_admission(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> AcquisitionAdmissionProjection: ...
def project_acquisition_effect(
    state: ExecutionAuthorityState,
    effect_id: EffectId,
) -> AcquisitionEffectView | None: ...

# private helpers; exact imports permitted only from acquisition.py
def _mint_acquisition_currentness_registration(...) -> AcquisitionCurrentnessRegistration: ...
def _mint_acquisition_effect_permit(...) -> AcquisitionEffectPermit: ...
def _mint_acquisition_claim_permit(...) -> AcquisitionClaimPermit: ...
def _mint_acquisition_exit_permit(...) -> AcquisitionExitPermit: ...

# acquisition.py
class DualMandateBinding: ...  # opaque, reducer-constructed only
class AcquisitionMandate:
    acquisition_mandate_id: AcquisitionMandateId
    position_scope: PositionScope
    session_id: SessionId
    configuration_version: str
    maximum_quantity: Quantity
    maximum_notional: Fraction
    maximum_entry_price: ReportedPrice
    allowed_order_types: tuple[AcquisitionOrderType, ...]
    expiry: int
    deadline: int
    fixed_child_cap: Quantity
    certified_participation_cap: Fraction | None
    cancel_reprice_budget: int
    protection_mandate: ProtectionMandate
    binding: DualMandateBinding

class AcquisitionControllerDisposition(Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    REFUSED = "REFUSED"
class AcquisitionRecoveryClass(Enum):
    NORMAL = "NORMAL"
    MIXED_GENERATION_RECOVERY = "MIXED_GENERATION_RECOVERY"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
class SymbolAcquisitionController: ...  # opaque, constant-size only

class AcquisitionControllerState:  # opaque, reducer-constructed only
    position_scope: PositionScope
    execution_commitment: bytes
    venue_commitment: bytes
    protection_commitment: bytes | None
    controller_commitment: bytes
    registry: GenerationRegistry
    lineage: AcquisitionLineageIndex
    commitment: bytes

class AcquisitionControllerStatus:
    position_scope: PositionScope
    controller_head: bytes
    successor_ordinal: int
    live_generation_id: AcquisitionGenerationId | None
    recovery_class: AcquisitionRecoveryClass
    execution_commitment: bytes
    venue_commitment: bytes
    protection_commitment: bytes | None
    controller_commitment: bytes

class AcquisitionControllerTransition:  # opaque, reducer-constructed only
    state: AcquisitionControllerState
    venue: VenueRecoveryBook
    execution: ExecutionSnapshot
    protection: PositionProtectionState | None
    authority: ExecutionAuthorityState
    disposition: AcquisitionControllerDisposition
    created_effect_id: EffectId | None
    fresh_claim: AcquisitionClaimReceipt | None

def initialize_acquisition_controller(
    application_generation_id: ApplicationGenerationId,
    mandate: AcquisitionMandate,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
    execution: ExecutionSnapshot,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
) -> AcquisitionControllerTransition: ...
def begin_acquisition_generation(
    state: AcquisitionControllerState,
    successor_mandate: AcquisitionMandate,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
    execution: ExecutionSnapshot,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
) -> AcquisitionControllerTransition: ...
def reduce_acquisition_controller(
    state: AcquisitionControllerState,
    transition: VenueRecoveryTransition,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
) -> AcquisitionControllerTransition: ...
def rebase_acquisition_protection(
    state: AcquisitionControllerState,
    execution: ExecutionSnapshot,
    transition: ProtectionTransition,
    authority: ExecutionAuthorityState,
) -> AcquisitionControllerTransition: ...
def create_acquisition_effect(
    state: AcquisitionControllerState,
    execution: ExecutionSnapshot,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
    terms: AcquisitionEffectTerms,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
def claim_acquisition_effect(
    state: AcquisitionControllerState,
    execution: ExecutionSnapshot,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
    effect_id: EffectId,
    claim_occurrence_id: ClaimOccurrenceId,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
def begin_acquisition_preemption(
    state: AcquisitionControllerState,
    execution: ExecutionSnapshot,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
def create_acquisition_protection_exit(
    state: AcquisitionControllerState,
    execution: ExecutionSnapshot,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
def project_acquisition_controller(
    state: AcquisitionControllerState,
) -> AcquisitionControllerStatus: ...
```

All opaque types are exact-type, immutable, non-subclassable, seal-verified by
their owner, and reject copied-field construction. The public state/reader
shapes above expose no action or factory and no enumerable collection.

## Venue proof: target facts only

`VenueRecoveryTransition` gains a private reducer-created source proof. It is
made only when existing recovery logic canonically applies a broker FILL,
TRADE_CORRECT, or TRADE_BUST. It binds predecessor/current execution and venue
commitments, fact/root/effect/request/owner/leg direct relation, target scope,
and source command commitment.

`project_acquisition_fact` has no caller selectors. It returns a non-serving
projection unless the proof and current direct request/effect/owner/root maps
agree. `fact_relation()` returns the sealed, non-authoritative direct-key
projection only for a valid fact source. Acquisition uses those keys for one
lineage lookup and one registry lookup; it never reads venue internals.

The source class is `CANONICAL_ECONOMIC_FACT` when canonical economics applied
without a reconciliation consequence. It is
`CANONICAL_ECONOMIC_FACT_RECONCILIATION` when canonical economics applied once
but existing recovery also requires reconciliation. The latter updates the
affected generation and controller head exactly once, selects
`RECONCILIATION_REQUIRED`, and grants no new BUY, normal-protection, or
protective-effect eligibility. Replay/conflict/unattributed/noncanonical
transitions are non-serving.

`project_acquisition_bootstrap` proves venue-owned target facts only: exact
current execution/book pairing, flatness, basis/integrity/reconciliation,
target ownership/closure, cancellation reservation, protection exit, and
single-flight summary. It makes no claim about authority-only state. It uses
bounded target indexes/summaries and does not materialize account/audit
history; unrelated-symbol history is ignored once the exact account binding
passes.

## Separate authority admission and mutation evidence

`project_acquisition_admission(authority, execution, scope)` is an
authority-owned, bounded, opaque read proof. It verifies the authority state,
exact current venue/execution binding, scope/session fence, and authority-only
conditions including manual flatten, prior acquisition preemption/exit
pointers, and conflicting authority reservations. It exposes no map or action.
Genesis and successor admission require both a BOOTSTRAP venue projection and
this exact admission projection; registration rechecks both. A clear venue
book therefore cannot conceal a live authority-only flatten or reservation.

Every specialized authority command returns an
`AcquisitionAuthorityReceipt`. A receipt is created only by `authority.py` and
binds the command/permit, pre/post controller head supplied by the sealed
permit, pre/post execution/venue/authority commitments, and the exact ordered
venue-transition commitments. A currentness registration may use exactly one
of four sealed sources:

1. BOOTSTRAP -- exact venue plus authority admission proof;
2. CANONICAL_FACT -- exact venue fact projection;
3. AUTHORITY_MUTATION -- one matching specialized authority receipt; or
4. PROTECTION_REBASE -- one sealed protection rebase projection.

The registration mint helper accepts no raw book, snapshot, route, or
commitment from a public caller. It verifies the source, predecessor/current
component commitments, scope/session/binding, and expected controller head.
For a fact source it can rebase `ExecutionAuthorityState.venue` only from the
exact authenticated transition. For an authority receipt it accepts only the
receipt's ordered post transitions. For a protection rebase it preserves the
exact current venue/execution pair. Any disagreement refuses.

Generic `CreateBrokerEffect` refuses every BUY SUBMIT/REPLACE and every CANCEL
whose direct target is acquisition-owned. Generic `ClaimEffect` refuses every
acquisition-owned effect. The specialized commands are the sole E2 mutation
route for the acquisition lifecycle, including preemption cancellation.

`AcquisitionEffectTerms` carries economics only, not effect/request/client
identity. The specialized create command derives each identity from its sealed
permit, terms commitment, and replay input ID. `authority.py` retains the exact
terms in a direct descriptor; its commitment is the existing venue
`economic_scope`. `AcquisitionEffectView` is the only public readback. Changed
terms, copied/colliding/forked/cross-scope permits, stale registration, or
changed current protection/execution/venue/head refuse.

`AcquisitionClaimReceipt` is the sole claim value that can leave a composite
transition. It is a read receipt, not a capability. Claim uses a fresh sealed
permit created from the current controller state and exact current protection;
it rechecks the current registration immediately before the existing claim
operation.

## Mandates, current protection, and recovery

`EmergencyRecoveryCompatibility` is a committed field of `ProtectionMandate`,
not a second caller-selected acquisition value. Its exact identity, scope,
session, configuration commitment, emergency guard, rate, effect budget,
deadline, and aggregate emergency quantity are all committed and enforced in
successor equality and the mixed-recovery/exit route. Its normal entry/trail
and market-cursor rules are absent.

`DualMandateBinding` commits the complete acquisition mandate, complete
protection mandate commitment, distinct mandate IDs, exact scope/session/
configuration, and this compatibility commitment. A successor has a new
complete binding and ADR-023 stream but must equal the controller's immutable
compatibility exactly.

`AcquisitionControllerState` retains one exact current protection commitment,
or `None` before first root. All admission, create, claim, preemption, exit,
fact, and protection-rebase operations receive the corresponding
`PositionProtectionState | None` as shown above. They require an exact match;
`None` is accepted only when the state commits none. Successor admission
requires its predecessor normal protection state to be exact, flat/non-serving,
and leaves the successor with no normal state until its first root.

The first valid current-generation root builds fresh normal FLOOR_ONLY state
through the existing venue-to-protection projection. A valid retired-generation
economic change uses a sealed `AcquisitionMixedRecoveryProof` and
`force_acquisition_mixed_recovery`; it returns one current HARD_BAIL state,
never a second normal state, transfer, or successor-capacity credit.

All existing protection reducers return a sealed `ProtectionTransition`.
`project_acquisition_protection_rebase` accepts only that result and binds its
predecessor/current protection commitment, scope, execution commitment, and
source. `rebase_acquisition_protection` rechecks the controller and authority
currentness, advances the controller head only when the protection classification
changes, and registers the exact PROTECTION_REBASE outcome. It does not replay
policy, create an effect, or expose a policy constructor. This covers existing
venue, market, and invalidation protection transitions without a second policy
writer.

## Required behavior

1. **Serial A -> B -> C.** One controller and at most one LIVE generation.
   Genesis/successor require exact flat, clear, closed, target-safe venue and
   authority admission proofs, predecessor head/ordinal, distinct binding and
   stream, and exact compatibility. Wrong/stale/forked/nonterminal/incompatible
   input leaves A untouched.
2. **Direct lineage.** Request/effect/owner/root/fact routes are immutable.
   A late A fact updates only A's registry record/controller head; B/C routes
   are neither scanned nor rewritten.
3. **Exactly once.** Only the upstream canonical venue/execution reducer
   changes aggregate quantity/basis. E2 binds that one post-state and never
   folds a fact a second time.
4. **Currentness.** Controller-owned capacity/preemption/exit changes are
   registered through their exact authority receipt. Final claim does not
   advance the controller merely because a claim record exists, but it must
   verify a fresh current permit. Every non-no-op relevant fact, admission,
   controller protection-classification change, capacity/preemption/exit
   change advances the controller head exactly once.
5. **Cross-side safety.** A sealed exit permit can stand down safe unclaimed
   BUY work and stage at most one target cancel. A protection SELL requires
   exact bounded BUY closure; OPEN/INVALIDATED/claimed/unknown/cancel-only/
   flat evidence remains wait/reconciliation.
6. **Failure behavior.** No caller-built currentness, closure, relation,
   approval, raw effect, book, snapshot, compatibility, or receipt becomes
   authoritative. Failure is non-serving and non-mutating.

## RED controls

| Requirement | Failure-capable control |
|---|---|
| Venue fact source | A current book with an old root cannot serve a different transition; copied selectors and missing direct keys refuse. |
| Reconciliation fact | A canonical correction/bust with reconciliation advances its own record/head once and disables new effect eligibility. |
| Split bootstrap proof | Other-symbol history permits a clear target; target venue failure or authority-only manual flatten/preemption/reservation refuses. |
| Serial state/protection | A/B/C pins direct state; stale/copy/changed protection at successor/create/claim refuses without replacement. |
| Direct bounded routes | Many A routes plus late A correction change one record only and leave B/C routes unchanged. |
| Compatibility | Changed identity, configuration commitment, guard, rate, budget, deadline, or aggregate ceiling refuses successor/recovery. |
| Specialized lifecycle | Generic BUY and acquisition-target CANCEL/claim refuse; specialized create/claim/preempt/exit need matching current permit/receipt. |
| Terms/read shapes | Derived identities cannot be caller chosen; exact terms round-trip through `AcquisitionEffectView` and committed economic scope. |
| Protection rebase | Valid sealed venue/market/invalidation transitions rebase currentness; a copied/stale transition or changed controller/authority refuses. |
| Cross-side wait | Only one safe cancel; SELL unavailable before exact closure and for claimed/unknown/OPEN/INVALIDATED cases. |
| Structural boundary | Actual production AST pins exact imports/exports/mutation functions and rejects private venue reach-through, reverse imports, dynamic imports, history materialization, or enumerable authority state. |

Each control must be RED for the intended missing behavior before its code is
implemented. The control suite must exercise actual production modules as well
as narrow negative snippets.

## Literal static boundary

- `venue.py` owns `AcquisitionVenueProjection`/`AcquisitionFactRelation` and
  imports no E2 peer module.
- `protection.py` owns compatibility, sealed `ProtectionTransition`, rebase
  projection, and mixed recovery; it imports no acquisition/authority symbol.
- `authority.py` owns admission/permit/receipt/effect-view types and imports no
  acquisition/protection symbol.
- `acquisition.py` exports only the public names frozen here. Its only private
  cross-module imports are `_mint_acquisition_currentness_registration`,
  `_mint_acquisition_effect_permit`, `_mint_acquisition_claim_permit`,
  `_mint_acquisition_exit_permit`, and `_mint_acquisition_mixed_recovery_proof`.
  It imports no underscore-prefixed venue name.
- `acquisition.py` may consume only the named public venue, protection, and
  authority methods/types above. It may not read `effects`, `claims`, `owners`,
  `active_attempts`, `closure_heads`, `closure_history`, `input_records`,
  coverage ledgers, or an unbounded predecessor chain.

## Allowed delta after acceptance

- `app/execution_core/identity.py`
- `app/execution_core/acquisition.py`
- `app/execution_core/authority.py`
- `app/execution_core/protection.py`
- `app/execution_core/venue.py`
- `app/execution_core/__init__.py`
- the six exact execution-core tests named by WO-0151
- active/completed WO-0151, `work/ledger.jsonl`, named PKL pages, `pkl/log.md`,
  and `work/review/REV-0058/`.

No other application path, persistence/runtime work, database activity, later
work-order activation, or M2 work is implied.

## Acceptance condition

An independent reviewer must compare this R2 body against ADR-020 R2,
ADR-021 R2, ADR-023 R1, WO-0151, R0/R1 retained results, and active E1 seams.
Acceptance requires P0=0/P1=0 and a concrete conclusion that the frozen
surface is implementable without private venue access, account-history
authority, a second aggregate writer, or an import cycle.
