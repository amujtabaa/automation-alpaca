# WO-0151 RED contract R11 -- remaining-route constructibility closure

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R11 candidate is the exact R2 through R10 composite pinned by the
R10 manifest, plus this amendment. Every earlier provision remains controlling
unless R11 expressly replaces it. R10 remains the controlling exact-immutable-
replay clarification for semantic protection rebase.

R11 grants no application or test implementation, activation, runtime,
persistence, database, SQL/DDL, broker, credential, network, CI-workflow, M2,
merge, deletion, cleanup, force-push, rebase, or later-work-order authority.
It closes three bounded constructibility gaps found before the remaining RED
suite was written: neutral raw-state refresh, protection-owned exit intent, and
exhaustive handling of an authentic applied fact. It also makes predecessor
terminality exact without adding a duplicate persisted lifecycle field.

## 1. One disjoint source union for protection rebase

Replace the R6 declaration with exactly:

```python
def rebase_acquisition_protection(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    source: AcquisitionProtectionRebaseProjection | PositionProtectionState,
) -> AcquisitionControllerTransition: ...
```

Dispatch is by exact type and exact refresh disposition:

| Exact `source` type | Exact refresh | Permitted branch |
|---|---|---|
| `AcquisitionProtectionRebaseProjection` | `CURRENT` | `SEMANTIC_REBASE` only, with every R6/R7 check and the R9/R10 predecessor-semantic matcher |
| `PositionProtectionState` | `REFRESHED` | `NEUTRAL_REPROJECTION` only |

An exact union member used with the wrong disposition returns the ordinary
non-mutating `REFUSED` result. A value outside the union, including `None`, is a
type error before mutation. A caller-supplied projection whose kind is
`NEUTRAL_REPROJECTION` always refuses, including an exact immutable copy of a
valid helper result. A raw state never enters the semantic branch.

This adds no fourth parameter, public factory, currentness source, authority
command, controller field, raw-context cache, or retained old book/snapshot.

## 2. Protection-owned neutral construction and matcher

Add exactly this second narrow read-only method to the existing opaque
protection-owned projection:

```python
class AcquisitionProtectionRebaseProjection:
    def matches_neutral_reprojection(
        self,
        expected_scope_protection_commitment: bytes,
        current_context: AcquisitionProtectionContext,
        source_venue_transition_commitment: bytes,
    ) -> bool: ...
```

It returns `True` only when all of the following are exact:

1. `self` is owner-authentic and its kind is `NEUTRAL_REPROJECTION`;
2. both supplied commitments are exact 32-byte `bytes` values, and the source
   tuple has exactly one entry equal to the supplied venue-transition
   commitment;
3. the sealed predecessor context recomputes from the projection's application
   generation, scope, predecessor scope-execution and raw-source fields plus
   the supplied controller semantic-protection commitment;
4. `current_context` is protection-authentic and matches the projection's
   application generation, scope, current scope-execution and venue values,
   context commitment, raw-source commitment, and exact resulting state;
5. `current_context.scope_protection_commitment` equals the supplied
   predecessor semantic commitment; and
6. predecessor/current raw protection and full execution commitments differ,
   while predecessor/current target scope-execution, venue, and semantic
   protection commitments are equal.

It returns `False` for malformed input, semantic projections, changed target
semantics, a mismatched source transition, or an unauthentic result. It accepts
no authority value and grants no registration, effect, claim, or action
authority.

Replace R6's private neutral-helper signature with:

```python
# private helper; exact import permitted only from acquisition.py
def _project_acquisition_neutral_reprojection(
    prior_state: PositionProtectionState,
    predecessor_execution: ExecutionSnapshot,
    predecessor_venue_context: AcquisitionVenueContext,
    transition: VenueRecoveryTransition,
    venue_context: AcquisitionVenueContext,
) -> AcquisitionProtectionRebaseProjection | None: ...
```

The current book and execution come only from the authentic transition. The
helper receives no authority state/context/commitment, refresh object, caller
namespace, predecessor book, or caller-selected semantic value.

The helper authenticates the raw prior state and the venue transition through
the existing protection projection/reducer proof. It requires one `APPLIED`,
zero-quantity target catch-up; exact scope and mandate; raw state execution and
cursor equal to the transition predecessor; supplied predecessor execution and
target-local venue values equal to the authenticated refresh predecessor; and
the current venue context serving for the transition's exact returned book and
execution. It derives the fresh raw state internally, emits no goal or alert,
requires the old and new protection semantic commitments to be equal, and
mints exactly one neutral projection bound to the transition proof.

The predecessor venue context is target-local source evidence and is expected
to be non-serving after a clean sibling registry advance. Neither module may
require `predecessor_venue_context.matches_current(...)` at that point.
Instead, `acquisition.py` first authenticates the whole refresh with
`refresh.matches_current(...)`, rechecks the complete R7 predecessor/current
authority pair, requires equal target-local scope-execution, venue, authority,
and semantic commitments, and requires exactly the one transition. Protection
then independently validates the raw state/cursor/execution relation against
that transition. The immediate helper result must pass
`matches_neutral_reprojection(...)` before it can serve.

Neutral success returns only the refresh's current authority/book/execution and
the helper-derived fresh raw protection state. Controller state/head/ordinal,
registry, lineage, currentness, permits, effects, claims, and every retained
semantic commitment remain byte-for-byte unchanged. There is no receipt,
registration, command, goal, alert, fact, effect, or claim. Neutral failure
returns the predecessor authority/book/execution and raw protection state; a
partially refreshed composite is forbidden.

## 3. One transition-derived protection exit intent

The raw `PositionProtectionState` is not itself permission to derive SELL
economics outside `protection.py`, and caller-constructed `ExecutionGoal` is
not authority. Replace the two R6 declarations with exactly:

```python
def begin_acquisition_preemption(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    transition: ProtectionTransition,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...

def create_acquisition_protection_exit(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    transition: ProtectionTransition,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
```

Add one private, opaque, protection-owned exit-intent value and one private
projector, both importable only by `acquisition.py`:

```python
class _AcquisitionProtectionExitIntent: ...  # exact, immutable, sealed

def _project_acquisition_protection_exit_intent(
    transition: ProtectionTransition,
    current_context: AcquisitionProtectionContext,
) -> _AcquisitionProtectionExitIntent | None: ...
```

The projector accepts only an authentic `APPLIED` reducer transition with a
non-`None` owner-produced goal. Its resulting state must be the exact current
raw state authenticated by `current_context`. The goal must be SELL and must
bind that state's execution and protection commitments, authoritative residual
quantity, normal or emergency urgency, exact guard, deadline, session,
protection mandate, rate, BUY-resolution status, and real exit provenance.
All protection-owned formula, market-generation, halt, baseline, exhaustion,
quantity, mandate, and deadline conditions are rechecked. The intent binds the
transition seal, state/context/goal commitments, scope, terms, and its own
seal. It performs no venue or authority decision.

`begin_acquisition_preemption(...)` and
`create_acquisition_protection_exit(...)` require the supplied `protection` to
be the exact current authentic `transition.state`, construct its current
protection context from the refresh's current book/execution/venue context,
and call the projector themselves. No caller supplies an intent or goal, and
an old authentic transition cannot serve a newer current context. Preemption
consumes an intent whose current state requires BUY resolution and may only
stand down an unclaimed BUY or stage the one exact bounded cancel permitted by
the existing venue/authority rules. Protection exit consumes an intent only
after BUY resolution is clear and the authority owner rechecks exact closure,
reconciliation, single-flight, controller head, residual quantity, guard,
budget, and currentness immediately before creating or claiming a SELL.
Unknown, claimed, OPEN, INVALIDATED, cancellation-only, stale, or mismatched
work remains waiting or reconciliation-only.

The intent never becomes a fifth currentness source or generic broker permit.
`protection.py` still imports neither `authority.py` nor `acquisition.py`.
Acquisition may not reconstruct exit policy, provenance, urgency, guard, or
SELL terms from public state fields. The existing `ProtectionTransition` is
the only additional public operation input; no public goal factory, exit
projection, or policy constructor is introduced.

## 4. Exact derived predecessor terminality

R11 adds no caller-selected lifecycle status and no duplicate controller phase.
For `begin_acquisition_generation(...)`, predecessor terminality is one derived,
atomic composition of the already sealed owners:

- `ABORTED` is derivable only when the exact live generation has never accepted
  a first root (`state.protection_commitment is None` and the supplied raw
  protection is `None`) and the exact bootstrap/admission/refresh proofs show
  flat execution, clear reconciliation/integrity/basis, CLOSED or absent
  acceptance sets, and no active/pending/unknown/unmatched/unclosed BUY or SELL,
  operation, cancellation, reservation, exit, flatten, or single-flight work.
- `COMPLETED` is derivable only when the controller retains a non-`None`
  protection semantic commitment, the exact current raw protection context is
  `FLAT` at quantity zero and non-serving for further acquisition work, and the
  same bootstrap/admission/refresh closure and no-work conditions hold.

Every retained controller, live generation record, binding, head, ordinal,
compatibility value, and currentness slot must match those proofs. Temporary
flatness, an old raw state, OPEN/INVALIDATED/unknown evidence, a live pointer,
or a stale/forked head is not terminal. The successor transition itself
atomically changes the exact predecessor record to `RETIRED_UNSERVING`, installs
one new LIVE record and mandate, advances the ordinal/head/currentness once,
and returns `protection=None` until the successor's first valid root. There is
never a separately writable terminal flag or a history-derived decision.

Authority may represent its one scope-local creation/preemption/exit pointer as
a sealed phaseful current record so terminal closure can become non-serving and
a successor can replace it. Permanent descriptor-by-effect and venue/lineage
provenance remain intact. Generic persistent-map deletion, map enumeration, and
clearing immutable provenance are not required or permitted.

## 5. Total handling of an authentic applied acquisition fact

R2's fact rule is clarified: after a venue-authentic first-occurrence canonical
`FILL`, predecessor-linked `TRADE_CORRECT`, or `TRADE_BUST` is classified as a
generation-relevant fact, E2 may not leave the controller/registry/lineage at
the predecessor merely because the resulting protection classification is not
normal `FLOOR_ONLY`.

The direct relation must classify exactly one of current first root, current
follow-on/revision, or retired root. Both
`CANONICAL_ECONOMIC_FACT` and
`CANONICAL_ECONOMIC_FACT_RECONCILIATION` are valid fact-proof kinds. The one
composite result records the direct routes and generation-local economics,
binds the already-applied aggregate exactly once, updates the raw protection or
mixed-recovery result, and advances the controller/currentness head exactly
once. A reconciliation-bearing result is retained but non-serving. It grants
no BUY or ordinary effect authority and does not need a serving refresh.

FR-06 and AC-04 continue to require `FLOOR_ONLY` for a valid normal first root.
If the owner-authentic protection result is instead conservative `HARD_BAIL`
or another non-normal safe classification because of basis/formula/cap/
integrity conditions, the fact is still recorded exactly once and new BUY is
unavailable. Any protective action requires the section 3 intent and all
authority gates. The implementation must not convert an authentic applied fact
into a state-preserving refusal, fabricate `FLOOR_ONLY`, or reapply economics.

For a retired fact that also requires current BUY preemption, one specialized
authority mutation may bind the exact fact transition, retired relation,
mixed-recovery proof, current controller, and exit permit and return one
ordered receipt. That receipt is the single currentness source for the combined
mutation; a second canonical-fact registration is forbidden. It first adopts
the authenticated fact's venue/execution result, then performs at most the one
safe current-BUY stand-down/cancel transition, and advances the controller head
once. If no authority mutation is needed, the existing `CANONICAL_FACT` source
remains the single registration source. No fifth source or second aggregate
writer is introduced.

## 6. Remaining-route constructibility boundary

No other public signature, enum, command, currentness-source kind, or module
dependency is changed by R11. Follow-on fills, corrections/busts, successor
registry insertion, direct retired lookup, mixed recovery, preemption, exit,
and final-claim invalidation must be implemented through the R2-R10 public
surface plus the two exact private protection helpers named by R2 and R11.
Internal phaseful pointers and specialized permits remain bounded direct
current-state records; they expose no map, iterator, policy constructor, raw
venue member, or history scan.

## 7. Failure-capable controls

| Requirement | Failure-capable control |
|---|---|
| Disjoint neutral source | Semantic projection plus `CURRENT` succeeds only through R9/R10. That projection with `REFRESHED`, raw state with `CURRENT`, `None`, wrong type, and any caller-supplied neutral projection cannot serve. |
| Neutral source proof | One clean sibling catch-up plus the exact stale raw protection state produces one fresh raw state. Old/post-refresh cursor, wrong execution/scope/mandate, altered transition, nonzero delta, changed target semantic value, or missing R7 pair refuses with no partial refresh. |
| Neutral transport only | Mutants that advance controller/currentness, retain stale raw protection, emit goal/alert/receipt/effect/claim, or use neutral as a fact or registration fail. |
| Exit-intent ownership | Caller goal, caller-built or stale transition, acquisition-derived SELL terms, wrong policy/provenance, changed quantity/guard/deadline/mandate, halted/baseline/exhausted state, or stale raw context cannot mint preemption/exit authority. |
| Cross-side sequence | Exit before exact BUY resolution, duplicate cancel, claimed/unknown/OPEN/INVALIDATED evidence, stale controller head, or changed residual quantity refuses; at most one protective effect becomes eligible. |
| Derived terminality | Initialized-unused clear state derives only ABORTED; rooted exact-flat closed state derives only COMPLETED. Temporary flat, stale protection, live work, nonclosed evidence, incompatible mandate, reused stream, or wrong head/ordinal leaves A untouched. |
| Applied-fact totality | Current first/follow-on and retired FILL/CORRECT/BUST, with and without source reconciliation and with normal/abnormal protection outcomes, each update direct state/head exactly once. A mutant that refuses after the aggregate fact, folds economics again, or registers twice fails. |
| Race and retirement | A retired fact before create, after create, and before final claim stales the exact successor authority; old claim refuses, permanent A/B/C routes remain direct, and no scope pointer or controller collection grows with audit history. |
| Structural boundary | Static controls reject extra public exports, a private venue import in acquisition, authority imports in protection, raw-context caches, generic BUY/CANCEL/SELL routes, dynamic access, map/history materialization, or edits outside the active allowed paths. |

Named mutation controls must independently remove each owner matcher, semantic
comparison, cursor/execution link, terminal no-work condition, exit-intent
condition, exact-once head update, and final-claim revalidation and demonstrate
that the corresponding control turns RED.

## 8. Focused acceptance

Before R11 can be ratified, a fresh independent reviewer must re-derive the
R2-R11 composite from ADR-020 R2, ADR-021 R2, ADR-023 R1, active WO-0151, the
current E1/E2 seams, and retained review evidence. The review must enumerate
every remaining public route and show either a complete producer/consumer/
mutation path or a concrete gap. It must perform counterexamples for neutral
source production, exit-intent ownership, terminal predecessor derivation,
reconciliation facts, abnormal first roots, retired fact/preemption ordering,
and final-claim races. Acceptance requires P0=0 and P1=0. Any material change
requires a new exact freeze and focused review.
