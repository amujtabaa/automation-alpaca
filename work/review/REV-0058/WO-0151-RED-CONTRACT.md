# WO-0151 RED contract — serial acquisition controller and bounded recovery

Status: **DRAFT PRE-FLIGHT CANDIDATE — documentation only**

This contract narrows the already ratified ADR-020 R2 and ADR-021 R2 rules
into an implementable pure-M1E interface. It does not activate implementation
until an independent review accepts this exact candidate with no unresolved
P0/P1 items. It grants no runtime, persistence, database, broker, credential,
network, CI-workflow, M2, merge, deletion, or cleanup authority.

## Governing model and explicit assumptions

The controller is the one state owner for an exact `PositionScope`, not a new
writer, service, policy engine, or durable store. It combines existing
execution, venue, protection, and authority values into one pure transition
result; M2 alone will make that result durable atomically.

`AcquisitionMandate` is structurally complete, immutable operator-approved
policy data. Constructing it does not authenticate a human, credential,
broker, runtime fence, or session. Admission must still derive all current
serving authority from the exact controller, venue transition, execution
snapshot, and authority state.

The first-controller gate is a direct implementation of ADR-020 R2 sections
2–4 and ADR-021 R2 sections 2–4: target execution must be flat, consistent,
and clear; target ownership must be closed and non-executable; the current
bounded venue summary must be clear. Account history for other symbols is not
a predicate. The only permitted data source is a venue-produced, target-scoped
projection from current indexes; it must not inspect audit materializers.

If any required predicate cannot be represented by that projection without a
history scan or a new policy choice, implementation stops with
`BLOCKED — NARROW GENESIS ADR CLARIFICATION REQUIRED`.

## Frozen public interface

The names below are the complete proposed E2 delta. Existing E1 public names
remain public but cease to be inert only through these reducers. No alternate
factory, raw-currentness constructor, private venue accessor, or compatibility
alias is permitted.

```python
class AcquisitionOrderType(Enum):
    LIMIT = "LIMIT"

class AcquisitionMandate:  # immutable, exact type
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
    emergency_recovery_compatibility: EmergencyRecoveryCompatibility

class AcquisitionEffectTerms:  # immutable untrusted candidate terms
    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    client_order_id: ClientOrderId
    quantity: Quantity
    limit_price: ReportedPrice
    order_type: AcquisitionOrderType
    evaluation_time: int

class AcquisitionControllerDisposition(Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    REFUSED = "REFUSED"

class AcquisitionRecoveryClass(Enum):
    NORMAL = "NORMAL"
    MIXED_GENERATION_RECOVERY = "MIXED_GENERATION_RECOVERY"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

class SymbolAcquisitionController: ...  # opaque, reducer-constructed only
class AcquisitionAuthorityProjection: ...  # opaque, reducer-constructed only
class AcquisitionExitProjection: ...  # opaque, reducer-constructed only
class AcquisitionControllerStatus: ...  # bounded, read-only, authority-free
class AcquisitionControllerTransition:
    controller: SymbolAcquisitionController
    registry: GenerationRegistry
    lineage: AcquisitionLineageIndex
    execution: ExecutionSnapshot
    protection: PositionProtectionState | None
    authority_projection: AcquisitionAuthorityProjection
    exit_projection: AcquisitionExitProjection | None
    disposition: AcquisitionControllerDisposition

def initialize_acquisition_controller(
    application_generation_id: ApplicationGenerationId,
    mandate: AcquisitionMandate,
    venue_projection: AcquisitionVenueProjection,
) -> AcquisitionControllerTransition: ...

def begin_acquisition_generation(
    controller: SymbolAcquisitionController,
    successor_mandate: AcquisitionMandate,
    venue_projection: AcquisitionVenueProjection,
) -> AcquisitionControllerTransition: ...

def reduce_acquisition_controller(
    controller: SymbolAcquisitionController,
    registry: GenerationRegistry,
    lineage: AcquisitionLineageIndex,
    venue_projection: AcquisitionVenueProjection,
) -> AcquisitionControllerTransition: ...

def authorize_acquisition_effect(
    controller: SymbolAcquisitionController,
    terms: AcquisitionEffectTerms,
) -> AcquisitionAuthorityProjection: ...

def project_acquisition_controller(
    controller: SymbolAcquisitionController,
) -> AcquisitionControllerStatus: ...

class VenueRecoveryBook:
    def project_acquisition_venue(
        self,
        transition: VenueRecoveryTransition,
        position_scope: PositionScope,
        *,
        request_occurrence_id: RequestOccurrenceId | None = None,
        effect_id: EffectId | None = None,
        leg_key: VenueLegKey | None = None,
        root_key: RootFillKey | None = None,
    ) -> AcquisitionVenueProjection: ...

class RegisterAcquisitionCurrentness: ...
class CreateAcquisitionEffect: ...
class BeginAcquisitionPreemption: ...
class CreateAcquisitionProtectionExit: ...
```

`AcquisitionMandateId`, `DualMandateBinding`, and
`EmergencyRecoveryCompatibility` are exact immutable identities/values added
in `identity.py`. A `DualMandateBinding` commits both full mandate commitments,
their distinct IDs, exact scope/session/configuration, and the compatibility
commitment. The compatibility value commits the exact scope/session fence,
emergency guard, rate/budget/deadline limits, aggregate ceiling, configuration,
and compatibility identity; it excludes every normal entry/trail/cursor rule.

`AcquisitionVenueProjection` is opaque and may be minted only by the listed
method from an exact `VenueRecoveryTransition` and exact current book. It binds
the target scope, execution commitment, current venue commitment, transition
predecessor/current cursor, target flat/clear/basis/integrity predicates,
bounded target ownership counts, exact direct correlation (when selectors are
present), and source kind. It returns a non-serving projection on every
mismatch. It must use direct indexes/summaries only. It must not call or
otherwise obtain `effects`, `claims`, `owners`, `active_attempts`,
`closure_heads`, `closure_history`, `input_records`, coverage ledgers, or an
unbounded predecessor chain.

## Required semantics

1. **Genesis and successor admission.** `initialize_acquisition_controller`
   permits only a clear, exact-flat target projection and mints ordinal zero
   with E1's canonical genesis head. It sets one immutable compatibility and
   one LIVE generation. `begin_acquisition_generation` permits only a
   terminal, exact-flat predecessor, exact controller head/next ordinal,
   distinct complete binding and market stream, clear projection, and exactly
   equal compatibility. It retires the predecessor, creates fresh normal
   protection state, and never moves its cursor or policy state to the
   successor.

2. **Direct lineage and bounded state.** The registry holds each generation's
   immutable binding, mutable current economics head, closure summary, and
   serving class. The lineage index holds immutable `source -> generation_id`
   routes only. A route result joins the registry once; it never copies a
   mutable record field, scans routes, or rewrites every route after a late
   fact. The controller itself contains no retired-generation collection.

3. **One composite fact transition.** For a valid canonical fill family
   transition, `reduce_acquisition_controller` accepts only an opaque current
   venue projection. It routes a direct root/effect/owner/fact relation,
   applies that fact's generation economics and the supplied canonical
   aggregate snapshot once, advances the controller head, updates one record,
   and returns all changed components together. A duplicate returns exact
   replay; missing, cross-scope, stale, forked, or ambiguous lineage is
   non-serving/refused without inference.

4. **Protection and recovery.** The first accepted root of the current live
   generation starts a new `FLOOR_ONLY` protection state from the exact linked
   mandate and post-transition snapshot. A valid retired-generation economic
   change advances that retired record and controller head, makes current BUY
   authority stale, and enters the sole controller-level
   `MIXED_GENERATION_RECOVERY` / `HARD_BAIL` route. It never credits successor
   capacity, creates a second normal protection state, transfers old normal
   policy/cursor state, or emits more than one eligible protective effect.

5. **Authority route.** Generic `CreateBrokerEffect` must refuse every BUY
   `SUBMIT` and `REPLACE`, regardless of mode or a caller-provided value.
   `CreateAcquisitionEffect` may derive a BUY request only from an authentic,
   registered, current `AcquisitionAuthorityProjection`; its request is bound
   to exact terms, controller head, generation/binding, execution/venue
   commitments, scope, and session. The authority state rechecks the registered
   head and all inherited gates at creation and at final claim. Any newer
   controller/protection/venue/execution head, preemption, mismatch, cap,
   fence, kill, terminal lifecycle, or uncertainty refuses. A target-derived
   BUY cancellation remains possible only through a current sealed preemption
   projection; it never reopens entry authority.

6. **Cross-side resolution.** `BeginAcquisitionPreemption` accepts only an
   authentic current exit projection from the controller and can stand down
   safely-local unclaimed BUY work plus create at most one exact current-leg
   cancel. A protection SELL is eligible only after the bounded venue projection
   proves all relevant BUY ownership is closed; known terminal status, a cancel
   acknowledgement, a flat aggregate, `OPEN`, or `INVALIDATED` never suffice.
   The wait state preserves normal versus emergency protection meaning.

7. **Failure behavior.** No caller-supplied correlation, route, currentness,
   compatibility, closure, owner, approval, or raw effect is authoritative.
   Every failed check is non-mutating and non-serving. Generic market-stream
   reuse, positive-exposure mandate transfer, policy composition, concurrent
   generations, audit scans, persistence, runtime, and broker I/O are absent.

## RED controls and review matrix

| Requirement | Failure-capable control |
|---|---|
| Target-scoped bootstrap | Other-symbol account history permits genesis; target live/pending/unknown/unclosed ownership, nonflat/basis/integrity/reconciliation failure, reservation, exit, flatten, or mismatch refuses. Audit readers are tripwired. |
| Serial A→B→C | Known answers pin ordinal/head/generation lineage; stale, forked, cross-scope, exhausted, same-binding, incompatible, or nonterminal candidates refuse without altering the prior slot. |
| Direct routes | Many A routes followed by a late A correction/bust prove one registry-record change, no lineage iteration/rewrite, current A lookup, and unchanged B/C routes. |
| First vs retired fact | Current first root is fresh `FLOOR_ONLY`; late A fill/correct/bust after B/C is `HARD_BAIL`, advances controller head, preempts BUY, and never changes B capacity. |
| Create and claim | Generic BUY submit/replace refuses. A sealed registered route succeeds only while current; fresh controller/venue/execution/preemption state makes the same effect claim refuse. |
| Cross-side safety | A protection exit stages one safe cancel at a time; no SELL is eligible before exact closure. Claim/unknown/invalidated cases stay in the wait/reconciliation route. |
| Structural boundaries | AST/import controls pin exact E2 imports/exports, deny private venue reach-through, history materialization, dynamic loading, time/randomness, raw `object.__new__` authority factories, and public mapping/iterator escapes. |

Each control must demonstrate the intended failure before the corresponding
production behavior is implemented. Every public opaque output requires normal
construction, subclass, copied-field, and stale-head negative controls.

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

No other application path, database activity, runtime wiring, or work-order
activation is implied.

## Pre-flight completion condition

An independent reviewer must compare this document against ADR-020 R2,
ADR-021 R2, ADR-023 R1, the active public code seams, and the retained
WO-0149 evidence. Acceptance requires P0=0/P1=0 and a concrete confirmation
that the public interface can meet every listed requirement without private
venue access, account-history authority, or a second writer.
