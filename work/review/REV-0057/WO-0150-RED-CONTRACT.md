# WO-0150 RED contract — E1 acquisition-generation lineage

Status: **EXACT-COMMIT REVIEW CANDIDATE — documentation only**

This contract freezes the smallest proposed E1 public surface and RED obligations before
WO-0150 activation. It creates no application or test implementation authority. Its immutable
candidate is the Git commit that first contains this file; the independent result must record that
commit exactly.

## Authority and slice boundary

This contract implements the E1 boundary in ratified ADR-020 R2 sections 2–4 and ratified
ADR-021 R2 sections 2 and 5, as narrowed by
work/queue/WO-0150-reset-kernel-e1-generation-lineage.md.

E1 owns only deterministic identity, bounded records, permanent direct lineage indexes, and
authority-free read projections. It does **not** decide whether a mandate is approved, whether a
scope may start or roll over, compatibility equality, controller currentness, a generation's
admission, protection behavior, aggregate position effects, claim eligibility, or broker effects.
Those semantic decisions remain E2 work.

The following existing design distinction is binding:

- GenerationRegistry has exactly one bounded record for each genuine acquisition generation.
- AcquisitionLineageIndex owns the separate direct request/effect/owner/root/fact indexes. It
  can grow with retained immutable bindings; it is neither a controller collection nor a field of
  a GenerationRecord.
- The later E2 composite reducer is the sole semantic producer of an authenticated admission or
  currentness result. E1 may carry its opaque commitments but cannot infer their meaning.

No E1 transition may call or materialize VenueRecoveryBook.effects, owners,
closure_history, input_records, human_coverages, broker_coverages,
coverage_for_leg, broker_coverage_for_leg, or effect(). The sole permitted venue bridge uses
direct current indexes internally, returns an immutable sealed projection, and returns None for
anything it cannot prove exactly.

## Frozen identity wire contract

AcquisitionGenerationId is a 64-character lowercase SHA-256 hexadecimal identity, with the
same exact-type, decoded-byte, and sealed-value discipline as MarketStreamGenerationId. A raw
instance is only data; it is never authority.

Its private derivation is exactly the SHA-256 digest of _pack_parts with domain
execution-core/acquisition-generation-id/v1 and these ordered byte parts:

1. _encode_text(application_generation_id.value);
2. _encode_position_scope(position_scope);
3. _encode_int(successor_ordinal);
4. the exact 32-byte dual_mandate_binding_commitment;
5. the exact 32-byte predecessor controller-head or canonical genesis-head commitment; and
6. the exact 32-byte emergency-recovery-compatibility commitment.

For a first controller coordinate, the fifth part is the private canonical genesis commitment
derived with the domain execution-core/acquisition-controller-genesis-head/v1,
the application generation text, and the exact position scope. For a successor coordinate, it is
the exact opaque controller-head commitment supplied only by the authenticated E2 admission result.

The first ordinal is 0. An ordinal is an exact int, not bool, in the inclusive range
0..2**64 - 1; requesting a successor after the maximum rejects without wrap, replacement, or
state change. Any absent, non-32-byte, copied, cross-scope, duplicate, forked, stale, or
out-of-order coordinate rejects closed. Replaying the same complete authenticated coordinate
reproduces exactly the same identity.

E1 treats the dual-mandate, predecessor/genesis, and emergency-compatibility parts only as opaque
committed bytes. It may validate their exact type and length, but must not parse, compare, approve,
or otherwise interpret their policy content.

## Frozen public surface

The only new package exports proposed by E1 are below. Public views use init=False, exact-type
validation, a private seal, and reject normal construction/subclassing. The two .empty()
constructors create inert, no-authority containers only; they cannot mint an identity, bind a
route, create an effect, or make any generation serving.

~~~
class AcquisitionGenerationId(_ExactIdentity): ...

class VenueAcquisitionCorrelation:  # opaque/read-only
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    request_occurrence_id: RequestOccurrenceId
    effect_id: EffectId
    leg_key: VenueLegKey | None
    root_key: RootFillKey | None
    correlation_commitment: bytes

class VenueRecoveryBook:
    def acquisition_correlation(
        self,
        request_occurrence_id: RequestOccurrenceId,
        effect_id: EffectId,
        *,
        leg_key: VenueLegKey | None = None,
        root_key: RootFillKey | None = None,
    ) -> VenueAcquisitionCorrelation | None: ...

class GenerationServingClass(Enum):
    LIVE = "LIVE"
    RETIRED_UNSERVING = "RETIRED_UNSERVING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

class GenerationRouteKind(Enum):
    REQUEST = "REQUEST"
    EFFECT = "EFFECT"
    OWNER = "OWNER"
    ROOT = "ROOT"
    FACT = "FACT"

class GenerationBindingView:  # opaque/read-only
    generation_id: AcquisitionGenerationId
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    successor_ordinal: int
    dual_mandate_binding_commitment: bytes
    predecessor_or_genesis_head_commitment: bytes
    emergency_recovery_compatibility_commitment: bytes
    binding_commitment: bytes

class GenerationRecordView:  # opaque/read-only
    binding: GenerationBindingView
    economics_head_commitment: bytes
    serving_class: GenerationServingClass
    closure_summary_commitment: bytes

class GenerationRouteView:  # opaque/read-only
    route_kind: GenerationRouteKind
    source_commitment: bytes
    generation_id: AcquisitionGenerationId

class GenerationRegistry:  # opaque/non-enumerable
    @classmethod
    def empty(cls) -> GenerationRegistry: ...
    def record(
        self, generation_id: AcquisitionGenerationId
    ) -> GenerationRecordView | None: ...

class AcquisitionLineageIndex:  # opaque/non-enumerable
    @classmethod
    def empty(cls) -> AcquisitionLineageIndex: ...
    def route_request(
        self, request_occurrence_id: RequestOccurrenceId
    ) -> GenerationRouteView | None: ...
    def route_effect(self, effect_id: EffectId) -> GenerationRouteView | None: ...
    def route_owner(self, leg_key: VenueLegKey) -> GenerationRouteView | None: ...
    def route_root(self, root_key: RootFillKey) -> GenerationRouteView | None: ...
    def route_fact(
        self, fact_key: ExecutionFactKey
    ) -> GenerationRouteView | None: ...
~~~

LIVE in a read projection records a classification supplied by a later authenticated controller
transition; it does not itself grant E1 any authority. E1 has no public begin, rollover,
register, bind, mint, retire, advance, iteration, or mutable-map API. Its real private
reducers must accept only sealed, reducer-produced inputs. They are production building blocks for
the later E2 composite reducer, not test-only shortcuts, and all public callers remain limited to
the views and direct lookups above.

VenueAcquisitionCorrelation and VenueRecoveryBook.acquisition_correlation are the sole E1 venue
bridge. The query verifies request/effect ownership directly; when leg_key is supplied it verifies
the exact owner; when root_key is supplied it verifies the exact direct root-to-owner chain and
rejects a mismatch. It returns the canonical leg when the root mapping proves one. The bridge is
backed by one private direct RootFillKey-to-immutable-correlation map in VenueRecoveryBook. Every
canonical broker root accepted for E1 correlation, including broker-correlated human coverage,
must have exactly one entry in that map. The entry contains only the immutable
request/effect/leg/root provenance; current economics remain in ExecutionSnapshot root heads.
The query must use the direct request/effect, owner, and root maps only; it must not call
_current_effect or inspect effective state. It preserves the exact application generation and
position scope, exposes no book/private map, and never enumerates an audit collection. No other
acquisition module access to venue private fields or audit readers is permitted.

## State ownership and invariants

GenerationRegistry stores one record per identity, with an immutable binding, one replaceable
generation economics-head commitment, a serving classification, and one bounded closure-summary
commitment. A record contains no root/effect/owner/fact map, recursive predecessor collection,
audit collection, or controller state.

AcquisitionLineageIndex has separately keyed immutable bindings for each accepted request,
effect, owner, root, and canonical fact/revision. A stored route contains only route kind, source
commitment, and exact AcquisitionGenerationId. It never stores a mutable economics head or serving
class. To obtain current generation state, a consumer first performs exactly one direct route lookup
and then exactly one direct GenerationRegistry.record(route.generation_id) lookup. A missing or
mismatched route or record is reconciliation-only; there is never a current-symbol/generation
fallback.

A valid late first-occurrence FILL, predecessor-linked TRADE_CORRECT, or predecessor-linked
TRADE_BUST for retired A may update A's own record/head exactly once after its direct route is
proved. It cannot create a BUY effect, change B/C routing or capacity, reopen A, or make a policy
choice. Actual controller-head advancement, staleness/preemption, aggregate economics, and
protection classification are explicit E2 obligations.

All direct lookups are bounded. The registry grows only once per genuine generation, and the
lineage index grows only once per immutable accepted binding. A late fact updates one registry
record and may append its one new fact route; it must never rewrite, replace, or iterate existing
request/effect/owner/root routes for that generation. Neither growth enters the future
constant-size controller, and no E1 live decision traverses retired records, predecessor links,
or audit history.

## Required RED controls

The RED suite must be written before E1 production code and fail against the absent surface for
the named reason. It must use normal canonical fixtures and sealed production paths—never
object.__new__, monkeypatched authenticity checks, a test-only factory, or caller-built
authority.

1. **Known answers and replay.** Literal genesis and successor known answers pin the exact domain,
   part order, encoding, 64-character result, and replay. Independently changing each of the six
   coordinates changes the id.
2. **Identity refusals.** Missing/non-32-byte commitments, wrong scope/application generation,
   copied or substituted predecessor/genesis head, duplicate/forked/reused identity,
   non-integer/bool/negative/out-of-order ordinal, and exhausted successor all refuse without
   mutation.
3. **Direct immutable routing.** A serial A → B → C fixture binds request/effect/owner/root/fact
   values once. A late A fill, correction, and bust each resolve directly to A; a duplicate is
   idempotent; B/C routes and classifications remain unchanged. The route returns A's immutable
   id, and one direct registry lookup returns A's newly changed head/class.
4. **No fallback.** Missing, ambiguous, cross-scope, mismatched-order, mismatched-owner, or
   unbound root/revision returns no serving route and cannot resolve to B merely because B is
   current for the same symbol.
5. **Boundedness.** A long serial fixture retains the earliest route while poisoned audit views,
   history materializers, predecessor traversal, and registry/lineage iteration fail if touched.
   A many-route A fixture then applies one late A correction and one late A bust while route
   replacement/iteration traps fail if touched; it proves that only A's record changes, a direct
   registry join returns the new A head/class, and B/C remain unchanged. The test pins constant
   controller-shaped input and one-record/one-lookup work, not an unrealistic claim of constant
   total retained storage.
6. **Projection discipline.** Views are immutable and schema-neutral; they expose no private map,
   registrar, constructor capability, callable, mutable record, or missing required commitment.
7. **Boundary discipline.** Static controls reject imports of authority.py, protection.py,
   recovery.py, store/broker/runtime modules, I/O/clocks/randomness, private venue access, and
   a variable-cardinality collection disguised as controller state. Package exports and the exact
   public-surface oracle must agree.

Named mutation controls must fail if they omit a coordinate, permit ordinal wrap, map a missing
root to current B, replace a routed A with B, copy mutable A state into a route, rewrite A's old
routes after a late fact, skip exact root/fact/owner equality, omit a broker-correlated human root
from the direct root-correlation map, allow raw caller-built binding data into the registry, access
an audit materializer, or export a mutation or enumeration capability.

## Acceptance and stop rules

The independent exact-commit preflight must return ACCEPT with P0=0 and P1=0 before activation
or application/test edits. It must specifically disprove a hidden authority constructor,
policy/controller interpretation in E1, an unbounded per-generation map, private venue access,
and a history-materializing correlation path.

Stop and return to planning if satisfying a control requires E1 to decide admission/currentness,
parse mandate/compatibility policy, construct an AcquisitionLineageRelation, scan retained
history, make an effect eligible, touch protection/authority/recovery, or add persistence/runtime
 behavior. Those are not E1 fixes.
