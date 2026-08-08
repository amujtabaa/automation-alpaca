# WO-0151 RED contract R1 -- serial acquisition controller and bounded recovery

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

R1 supersedes neither the accepted ADRs nor the retained R0 candidate. It is a
replacement RED candidate addressing the R0 pre-flight result. It authorizes
no implementation until a fresh independent review accepts this exact body
with P0=0/P1=0 and the work order is activated. It grants no runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, or cleanup authority.

## Governing model

The E2 composition is one pure, deterministic state transition. It does not
add a writer, service, policy engine, durable store, history reader, or
runtime. `SymbolAcquisitionController` remains constant-size and owns only the
current scope head, ordinal, live-generation coordinate, recovery class, and
current component commitments. Retained generation economics and direct source
routes stay in the separate opaque `GenerationRegistry` and
`AcquisitionLineageIndex`; the controller never contains a retired-generation
collection.

Every successful E2 operation receives authenticated component values and
returns the complete next pure component set together. M2 alone will make that
set durable atomically. The E2 reducer never applies or reconstructs an
execution fact: it accepts the exact canonical execution result already
produced by the venue/execution reducers and binds it once to controller,
protection, and authority currentness.

The only source of target venue truth is a venue-owned, sealed projection from
bounded current indexes. Other-symbol account history neither authorizes nor
blocks a target decision. A target mismatch, unclear reconciliation, uncertain
ownership, nonflat execution, incompatible binding, stale component, or
missing sealed relation is non-serving and non-mutating.

## Module ownership and one-way dependencies

R1 fixes ownership before freezing behavior:

| Module | E2 ownership | May import E2 concepts from |
|---|---|---|
| `identity.py` | `AcquisitionMandateId` only | no E2 module |
| `venue.py` | target-scoped bootstrap/fact projections and transition source proof | no E2 module |
| `protection.py` | `EmergencyRecoveryCompatibility`, compatibility-bound `ProtectionMandate`, mixed-recovery proof/consumer | `venue.py`, `identity.py` |
| `authority.py` | specialized acquisition registrations, permits, descriptor/read projection, and authority commands | `venue.py`, `identity.py`, `position.py` |
| `acquisition.py` | mandate/binding, controller state, registry/lineage transitions, and public composite functions | the four modules above |

`venue.py` must not import `acquisition.py`, `protection.py`, or `authority.py`.
`protection.py` and `authority.py` must not import `acquisition.py` or each
other. `acquisition.py` may use only the literal public symbols below plus its
listed private mint/verify helpers; it must not use a private venue member.
No local/dynamic import, reflection, `object.__new__` factory outside the
declared owning module, public mapping/iterator escape, audit materializer, or
time/random source is permitted in the E2 path.

## Frozen public interface

The following is the complete proposed E2 public surface. Omitted names are
not part of E2.

```python
# identity.py
class AcquisitionMandateId: ...  # canonical immutable identity

# venue.py
class AcquisitionVenueSourceKind(Enum):
    BOOTSTRAP = "BOOTSTRAP"
    CANONICAL_BROKER_FACT = "CANONICAL_BROKER_FACT"

class AcquisitionVenueProjection:  # opaque, venue-constructed only
    source_kind: AcquisitionVenueSourceKind
    position_scope: PositionScope
    predecessor_execution_commitment: bytes | None
    execution_commitment: bytes
    predecessor_venue_commitment: bytes | None
    venue_commitment: bytes
    source_commitment: bytes

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
class EmergencyRecoveryCompatibility:  # exact immutable value
    position_scope: PositionScope
    session_id: SessionId
    configuration_version: str
    emergency_guard: ExecutionGuard
    maximum_goal_rate: int
    deadline: int
    aggregate_emergency_quantity: Quantity
    commitment: bytes

class ProtectionMandate:
    ...
    emergency_recovery_compatibility: EmergencyRecoveryCompatibility
    commitment: bytes

class AcquisitionMixedRecoveryProof: ...  # opaque, reducer-constructed only

# private helper; exact import permitted only from acquisition.py
def _mint_acquisition_mixed_recovery_proof(...) -> AcquisitionMixedRecoveryProof: ...

def force_acquisition_mixed_recovery(
    prior_state: PositionProtectionState | None,
    mandate: ProtectionMandate,
    venue_projection: ProtectionVenueProjection,
    proof: AcquisitionMixedRecoveryProof,
) -> ProtectionTransition: ...

# authority.py
class AcquisitionOrderType(Enum):
    LIMIT = "LIMIT"

class AcquisitionEffectTerms:  # exact immutable candidate economics only
    quantity: Quantity
    limit_price: ReportedPrice
    order_type: AcquisitionOrderType
    evaluation_time: int

class AcquisitionCurrentnessRegistration: ...  # opaque
class AcquisitionEffectPermit: ...             # opaque
class AcquisitionClaimPermit: ...              # opaque
class AcquisitionExitPermit: ...               # opaque
class AcquisitionEffectView: ...               # bounded, read-only

# private helpers; exact imports permitted only from acquisition.py
def _mint_acquisition_currentness_registration(...) -> AcquisitionCurrentnessRegistration: ...
def _mint_acquisition_effect_permit(...) -> AcquisitionEffectPermit: ...
def _mint_acquisition_claim_permit(...) -> AcquisitionClaimPermit: ...
def _mint_acquisition_exit_permit(...) -> AcquisitionExitPermit: ...

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

def project_acquisition_effect(
    state: ExecutionAuthorityState,
    effect_id: EffectId,
) -> AcquisitionEffectView | None: ...

# acquisition.py
class DualMandateBinding: ...                 # opaque, reducer-constructed only
class AcquisitionMandate:                     # exact immutable approved policy
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

class SymbolAcquisitionController: ...        # opaque, constant-size only
class AcquisitionControllerState: ...          # opaque; owns controller + E1 readers
class AcquisitionExitProjection: ...           # opaque
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

class AcquisitionControllerTransition:
    state: AcquisitionControllerState
    venue: VenueRecoveryBook
    execution: ExecutionSnapshot
    protection: PositionProtectionState | None
    authority: ExecutionAuthorityState
    disposition: AcquisitionControllerDisposition
    created_effect_id: EffectId | None
    fresh_claim: object | None

def initialize_acquisition_controller(
    application_generation_id: ApplicationGenerationId,
    mandate: AcquisitionMandate,
    bootstrap: AcquisitionVenueProjection,
    execution: ExecutionSnapshot,
    authority: ExecutionAuthorityState,
) -> AcquisitionControllerTransition: ...

def begin_acquisition_generation(
    state: AcquisitionControllerState,
    successor_mandate: AcquisitionMandate,
    bootstrap: AcquisitionVenueProjection,
    execution: ExecutionSnapshot,
    authority: ExecutionAuthorityState,
) -> AcquisitionControllerTransition: ...

def reduce_acquisition_controller(
    state: AcquisitionControllerState,
    transition: VenueRecoveryTransition,
    protection: PositionProtectionState | None,
    authority: ExecutionAuthorityState,
) -> AcquisitionControllerTransition: ...

def create_acquisition_effect(
    state: AcquisitionControllerState,
    execution: ExecutionSnapshot,
    authority: ExecutionAuthorityState,
    terms: AcquisitionEffectTerms,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...

def claim_acquisition_effect(
    state: AcquisitionControllerState,
    execution: ExecutionSnapshot,
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

`AcquisitionControllerState` exposes only authenticated direct readers for its
E1 `GenerationRegistry` and `AcquisitionLineageIndex`; both remain
non-enumerable. `AcquisitionControllerStatus` is the only public controller
summary and is exact, immutable, and authority-free. Every opaque value is
exact-type only, non-subclassable, seal-verified by its owner, and refuses
copied-field construction.

## Sealed venue sources

`VenueRecoveryTransition` gains a private, reducer-created acquisition-source
proof. The proof exists only when the transition applied one canonical broker
`FILL`, `TRADE_CORRECT`, or `TRADE_BUST` through the existing recovery path. It
binds the transition's predecessor/current execution and venue commitments,
fact key, root key, effect ID, request occurrence, owner/leg relation, target
scope, and source command commitment. It is created from the recovery command
inside `venue.py`, not from a parameter exposed by the projector.

`project_acquisition_fact(transition)` consumes that proof and rechecks the
current direct request/effect/owner/root indexes once. It has no selector
parameters. It returns a non-serving projection for replay, conflict,
unattributed fact, noncanonical source, cross-scope source, changed
book/execution pair, missing owner, or any failed direct relation.

`project_acquisition_bootstrap(execution, scope)` is deliberately separate. It
requires the exact current execution/book pair and produces only a BOOTSTRAP
projection. It evaluates target-scope, bounded summary/index predicates:
flatness; consistent basis/integrity; clear reconciliation; no potentially
executable BUY/SELL ownership; all relevant target acceptance sets CLOSED; and
no target operation, cancellation reservation, protection exit, flatten, or
single-flight conflict. It never inspects another symbol to make the target
decision and never materializes audit/history collections. Other-symbol
history is ignored after the exact account/book binding check succeeds.

The projection methods verify their own seals and exact book/execution
relationship. `acquisition.py` consumes only `matches_bootstrap` and
`matches_fact_transition`/`matches_predecessor_book`; it does not inspect `VenueRecoveryBook` internals,
call `acquisition_correlation`, or pass source selectors.

## Composite state and transitions

`AcquisitionControllerState` binds exactly one `SymbolAcquisitionController`,
one `GenerationRegistry`, and one `AcquisitionLineageIndex` with a controller
commitment. The controller stores no retired record or route collection; the
registry stores per-generation current economics/closure/serving class and the
lineage index stores immutable source -> generation routes.

For a fact transition, the reducer accepts the **pre** acquisition state and
authority state plus the authenticated venue transition. It requires the
state's retained execution/venue/controller commitments and the pre-authority
venue state to equal the source proof's predecessor values. It accepts the
post execution only through the transition, validates the sealed fact
projection, and returns the exact post venue/execution, updated acquisition
state, updated protection state, and rebased authority state together. A
replay returns the retained state; a mismatch returns `REFUSED` without
changing any component.

Genesis and successor admission use an exact BOOTSTRAP projection, an exact
current execution snapshot, and an authority state bound to the same current
venue. Genesis mints ordinal zero with E1's canonical genesis head. A
successor requires a terminal predecessor, exact retained head/ordinal,
distinct complete dual binding and ADR-023 stream, flat/closed/clear target
state, and equal compatibility. It retires the predecessor, preserves old
registry/lineage evidence, installs exactly one LIVE successor, and creates no
second controller.

Every state-changing controller operation creates a new controller head and a
new sealed currentness registration inside the same returned transition. The
authority state may advance its venue reference only from the exact
venue-transition proof; no caller may substitute a book, snapshot, or
commitment.

## Mandates, binding, and protection recovery

`AcquisitionMandate` validates quantity/notional/price/session/expiry/deadline
/child/participation/cancel-reprice limits and binds exactly one complete
`ProtectionMandate`. `DualMandateBinding` commits the acquisition mandate, the
full protection-mandate commitment, distinct mandate IDs, exact
scope/session/configuration, and the compatibility commitment.

`EmergencyRecoveryCompatibility` is an immutable committed field of
`ProtectionMandate`; it is not duplicated as an independently caller-chosen
acquisition value. It commits exactly the scope/session fence, configuration,
emergency guard, rate, deadline, and aggregate emergency ceiling. The
acquisition binding derives and compares that one value. Normal entry/trail or
market-cursor rules are excluded from compatibility.

For a current-generation first root, the composite reducer calls the existing
venue-to-protection projector with the linked mandate and creates fresh normal
`FLOOR_ONLY` state. It never transfers a predecessor cursor, policy, market
stream, or normal authority.

For a valid retired-generation economic change, `acquisition.py` creates an
opaque `AcquisitionMixedRecoveryProof` only after direct lineage resolution.
The proof binds the exact retired relation, predecessor/current controller
heads, post execution and venue commitments, current dual binding,
compatibility, linked protection-mandate commitment, and any prior protection
commitment. `force_acquisition_mixed_recovery` verifies all of them with an
exact `ProtectionVenueProjection` and returns one current `HARD_BAIL` state.
It works both when the successor has normal protection and when no successor
normal state exists; it never allocates a second normal controller/protection
state, credits successor capacity, or restores ordinary BUY authority.

## Authority route and exact term retention

Generic `CreateBrokerEffect` refuses every BUY `SUBMIT` and `REPLACE` before
ordinary mode/budget handling. Generic `ClaimEffect` refuses a BUY that is
registered as acquisition-owned. Only the specialized acquisition commands
are admitted for an acquisition BUY.

`acquisition.py` mints opaque currentness, creation, claim, and exit permits
from exact state after validating controller head, generation/binding,
execution, venue, protection, scope/session, lifecycle, capacity, and target
ownership. `authority.py` is the only consumer of those permits. It stores one
direct currentness entry per scope and one direct acquisition descriptor per
created effect. Registration, creation, and final claim each recheck the
stored current registration against the permit; a later controller, venue,
execution, protection, preemption, kill/fence, terminal, cap, or session
change refuses.

An `AcquisitionCurrentnessRegistration` privately retains either an exact
fact-projection/`VenueRecoveryTransition` pair or an exact bootstrap
projection, together with the predecessor and successor controller,
execution, venue, protection, binding, and scope/session commitments. The four
named registration/permit mint helpers are private to `authority.py` and may
be imported only by `acquisition.py`. `RegisterAcquisitionCurrentness` verifies the
registration's own seal, verifies the predecessor venue through
`matches_predecessor_book`, verifies the post execution/transition through the
projection, and only then rebases `ExecutionAuthorityState.venue` to the
transition's exact post book. Genesis/successor registrations have no fact
transition and require the exact current bootstrap book instead. Thus an
authority state cannot be advanced with a copied book or a transition that did
not start from its retained venue state.

`AcquisitionEffectTerms` intentionally contains no effect, request, or client
order identity. On an accepted create, `authority.py` derives all three by
domain-separated commitment from the sealed permit, terms, and replay input
ID. A caller therefore cannot choose an identity that becomes generation
ownership. The stored `AcquisitionEffectDescriptor` retains the exact terms
and its commitment is carried through the existing `economic_scope` field into
the venue request/effect/claim path. `project_acquisition_effect` exposes the
same immutable terms only as a read projection; no generic effect shape is
widened and no M1 broker dispatch is introduced.

`create_acquisition_effect` binds the derived request/effect route only after
the specialized authority command returns the exact venue transition. It then
updates the direct registry/lineage and currentness in the same composite
result. `claim_acquisition_effect` derives a fresh permit from current state
immediately before the specialized final-claim command. Replayed, colliding,
forked, cross-scope, stale, copied, or changed-term input refuses without
mutating prior authority.

`begin_acquisition_preemption` accepts only a current sealed exit permit. It
may stand down safely local unclaimed acquisition work and create at most one
exact current-leg cancellation. `create_acquisition_protection_exit` requires
the same current exit permit plus the existing protection goal and a bounded
venue proof that all relevant BUY ownership is closed. Known terminal status,
cancel acknowledgement, flat aggregate, OPEN/INVALIDATED acceptance, claimed
work, or unknown ownership stays in the existing wait/reconciliation path.

## Required semantics

1. **Serial admission.** A -> B -> C is predecessor-linked and deterministic.
   There is one controller and at most one LIVE generation. Same binding,
   stale/forked head, wrong ordinal, incompatible recovery value, reused market
   stream, nonterminal predecessor, or positive target exposure refuses.
2. **Direct lineage.** Request/effect/owner/root/fact relations use one direct
   source lookup and one registry lookup. A late A correction/bust changes only
   A's current record and the controller head; it never rewrites B/C routes or
   scans a collection.
3. **Exactly-once fact application.** The upstream venue/execution transition
   is the sole aggregate fact application. E2 binds that exact output once and
   never folds a fact or quantity again.
4. **Current and retired behavior.** The first current root starts fresh
   `FLOOR_ONLY`; a retired economic fact advances its own record and controller
   head, stales/preempts current BUY work, and takes the sole
   `MIXED_GENERATION_RECOVERY`/`HARD_BAIL` route. It never increases successor
   capacity or creates more than one eligible protective effect.
5. **Failure behavior.** All failed predicates are non-serving/non-mutating.
   No raw effect, correlation, route, closure, approval, currentness,
   compatibility, execution snapshot, venue book, or authority permit becomes
   authoritative by caller construction.

## RED controls

| Requirement | Failure-capable control |
|---|---|
| Selector-free fact relation | A current book with an older valid root cannot make a different transition serve; copied selectors cannot reach the projector; a transition source mismatch refuses. |
| Target bootstrap | Other-symbol history permits a clear target bootstrap; every target nonflat/reconciliation/basis/integrity/ownership/closure/reservation/exit/flatten conflict refuses. Audit readers are tripwired. |
| Serial state threading | A/B/C known answers pin state head/ordinal/binding; wrong pre-state, post-state, authority venue, registry, or lineage relation refuses without replacement. |
| Direct routes | Many A routes plus a late A correction prove one record update, no route iteration/rewrite, and unchanged B/C lookups. |
| Recovery bridge | Current first root yields fresh FLOOR_ONLY; a retired A fill/correct/bust before/after B is HARD_BAIL with no second normal state or B capacity change. |
| Specialized BUY | Generic BUY submit/replace and generic claim refuse. A sealed permit creates/claims only while current; copied/colliding/forked/cross-scope/stale permits and changed terms refuse. |
| Term retention | Exact limit/order terms are visible from the authority read projection and their commitment equals the venue economic scope; substituted terms fail revalidation. |
| Cross-side wait | Only one safe cancellation is staged; SELL is unavailable before exact BUY closure and remains unavailable for claimed, unknown, OPEN, or INVALIDATED cases. |
| Structural boundary | AST checks pin literal imports/exports/mutation definitions, reject private venue members, reverse imports, dynamic imports, history materialization, and authority-capable public container escapes. |

Each control must fail for its stated reason before the corresponding
production behavior is written. Controls must exercise the actual production
module as well as narrow negative snippets.

## Literal static-boundary freeze

The E2 AST/import check must pin these facts rather than a broad pattern:

- `venue.py` exports only the two acquisition venue projection names added by
  E2 and does not import acquisition/protection/authority.
- `protection.py` exports exactly the compatibility/mixed-recovery additions;
  it imports no acquisition/authority symbol.
- `authority.py` exports exactly the named specialized types/commands and
  `project_acquisition_effect`; it imports no acquisition/protection symbol.
- `acquisition.py` exports exactly the public types/functions listed above.
  Its only private cross-module imports are
  `_mint_acquisition_currentness_registration`, `_mint_acquisition_effect_permit`,
  `_mint_acquisition_claim_permit`, `_mint_acquisition_exit_permit`, and
  `_mint_acquisition_mixed_recovery_proof`. It imports no underscore-prefixed
  name from venue.
- `acquisition.py` may call only `project_acquisition_bootstrap`,
  `project_acquisition_fact`, `matches_bootstrap`, `matches_fact_transition`,
  `matches_predecessor_book`,
  `project_protection_venue`, `force_acquisition_mixed_recovery`, and the
  listed authority reducer/projection interfaces across E2 boundaries.
- The actual acquisition production AST must contain the exact public mutation
  functions frozen above and no additional E2 mutation factory. It must not
  read `effects`, `claims`, `owners`, `active_attempts`, `closure_heads`,
  `closure_history`, `input_records`, coverage ledgers, or an unbounded
  predecessor chain.

## Allowed implementation delta after acceptance

- `app/execution_core/identity.py`
- `app/execution_core/acquisition.py`
- `app/execution_core/authority.py`
- `app/execution_core/protection.py`
- `app/execution_core/venue.py`
- `app/execution_core/__init__.py`
- the six exact execution-core tests named by WO-0151
- the active/completed WO-0151 file, `work/ledger.jsonl`, the named PKL pages,
  `pkl/log.md`, and this `work/review/REV-0058/` packet.

No other application path, database activity, runtime wiring, work-order
activation, or later work order is implied.

## Pre-flight completion condition

An independent reviewer must compare R1 against ADR-020 R2, ADR-021 R2,
ADR-023 R1, WO-0151, the R0 negative result, and the current public code
seams. Acceptance requires P0=0/P1=0 and a concrete conclusion that the
literal public surface can meet the requirements without private venue access,
account-history authority, a second aggregate writer, or an import cycle.
