# WO-0151 RED contract R8 -- authenticated unbound-target bootstrap

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R8 candidate is the exact R2 body at SHA-256
`343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5`, the
exact R3, R4, R5, R6, and R7 amendments named in the R8 manifest, and this
R8 amendment. Every earlier provision remains controlling unless R8 expressly
replaces it. R0 through R7 remain retained evidence; only R7 is accepted
pre-flight evidence, and none of those artifacts accepts this R8 candidate.

R8 grants no implementation, test implementation, runtime, persistence,
database, broker, credential, network, CI-workflow, M2, merge, deletion, or
cleanup authority. It resolves one contract feasibility gap: an exact-flat
target with no retained venue checkpoint must first become an authenticated,
account-current target before it can establish its first controller. It must
not treat a refused refresh, a caller-shaped snapshot, a target-only serving
exception, or a private venue read as authority.

## 1. Authority-owned unbound-target registry bootstrap

Add one value to the existing authority-owned enum:

```python
class AcquisitionContextRefreshDisposition(Enum):
    CURRENT = "CURRENT"
    REFRESHED = "REFRESHED"
    UNBOUND_BOOTSTRAP = "UNBOUND_BOOTSTRAP"
    REFUSED = "REFUSED"
```

`AcquisitionContextRefresh` remains the sole public non-fact handoff. R8 adds
no public factory, projection type, raw-book input, raw-map input, caller
namespace, or alternate authority route. A `UNBOUND_BOOTSTRAP` result is
exact-type, immutable, authority-constructed, seal-verified, and usable only
while its existing `matches_current(...)` method authenticates its exact
returned authority state and bound target pair.

`refresh_acquisition_context(state, source_execution, position_scope)` MAY
mint `UNBOUND_BOOTSTRAP` only by invoking one private venue-owned,
authority-selected bootstrap primitive. That primitive performs one bounded,
zero-economic target registry/binding projection and MAY mint the result only
when all of these conditions hold:

1. `position_scope` is under the exact application-generation, broker,
   environment, and account fence of `state.venue`.
2. The exact target is derived owner-side as `ExecutionSnapshot.flat(position_scope)`.
   It has no retained `VenueExecutionBinding`, no retained target execution
    checkpoint, no target effect/ownership/closure/reservation/protection-exit/
    single-flight summary, no target acquisition currentness/descriptor/active
    authority entry, no manual-flatten entry, no preemption or exit pointer,
    and no target reconciliation or integrity concern.
   A nonflat, root-bearing, unresolved, unknown, target-active, or already
   bound target refuses.
3. The source is one of exactly two owner-authenticated cases:
   - an empty-account origin: `source_execution` is the exact derived target
     flat snapshot, the account book/registry/reconciliation cursor is at
     genesis, and no account-level input, effect, or binding exists; or
   - an authenticated same-account source: `source_execution` is a current,
     bound, reconciliation-clear snapshot under the same venue fence. The
     source is only a bounded account-freshness witness; it supplies no target
     policy, target ownership, mandate, controller, or effect authority.
4. In the source-backed case, the source binding, registry high-water, account
   fence, source attribution, and reconciliation checks remain exactly those
   required by R6/R7. Only for `UNBOUND_BOOTSTRAP`, R7's requirement that the
   source be a predecessor of an already retained target is replaced by proof
   that the current source registry has the owner-derived exact-flat target
   genesis registry as its prefix, together with the direct target-absence proof
   in item 2. The primitive then creates that first retained target pair
   atomically. A foreign, unbound, stale, non-prefix, unresolved, copied, or
   target-substituted source refuses.
5. The primitive derives the exact flat target snapshot by projecting the
   authenticated source registry and reconciliation cursor onto the target's
   unchanged economics. It atomically publishes one exact, replay-stable,
   zero-economic venue transition that retains that snapshot and its direct
   target binding. Its resulting book and target must satisfy the ordinary full
   `_execution_matches(...)` / context-currentness checks without an exception.
6. The primitive creates no broker effect, claim, permit, currentness
   registration, controller state/head, aggregate change, canonical fact,
   `PositionProtectionState`, or normal protection authority. It may change
   only the returned authority state's venue book by adding the target
   registry/binding projection, its one internal provenance record, and the
   inert venue checkpoint proof needed to authenticate that binding. A rejected
   or replay-mismatched attempt changes nothing.

The venue-owned private primitive may use the existing pure execution-registry
projection only to derive and retain the target snapshot described above. It
must derive its internal input identity from the exact venue generation, target
scope, source kind, source commitment, prior account registry pair, target
genesis commitment, and reconciliation cursor; no caller supplies an input ID
or namespace. It must use one direct target-scope absence check and one exact
source proof; it must not scan or materialize effects, owners, closures, audit
records, or account history. `acquisition.py` may not import or call that
primitive.

### 1.1 Invariant-preserving bootstrap-bound representation

The primitive must add one private, sealed direct record indexed only by exact
`PositionScope` (called a *bootstrap-bound target record* in this contract).
It is a bounded current-state index, not an effects/owners/audit history and
not a public projection. The record binds at least the exact venue generation,
target scope, source kind, source execution commitment, target genesis and
resulting execution commitments, target `VenueExecutionBinding`, account
registry count/commitment, reconciliation cursor, internal bootstrap-input
commitment, and neutral checkpoint-proof commitment. The record's seal and its
map root are included in the book commitment.

The book validation model admits exactly this one binding-with-zero-effect
state, subject to all of the following:

1. Active bootstrap-bound scopes and effect scopes are disjoint, and every
   binding belongs to exactly one of those two direct sets. No arbitrary bound
   zero-effect scope is valid.
2. An active bootstrap-bound record has no target effect, owner, attempt,
   claim, closure, operation, cancellation reservation, manual flatten,
   preemption, protection exit, ordinary protection authority, or acquisition
   descriptor/active entry. It retains exactly one target snapshot and direct
   binding. The only permissible concurrent authority state is the exact
   ordinal-zero `BOOTSTRAP` registration installed by section 2.1; the record
   never itself acts as a currentness entry or source.
3. The account registry count/commitment is present exactly when there are
   effects or active bootstrap-bound records. For an empty-account origin it
   records the exact empty registry; for a source-backed origin it records the
   exact authenticated source high-water. It is never a dummy effect or a
   synthetic market fact.
4. Each bootstrap-bound target has exactly one advancing, zero-quantity,
   neutral venue checkpoint proof/cursor in the existing bounded transition
   provenance model. The proof binds the pre/post book, exact target execution
   checkpoint, direct binding, clear summary, bootstrap input, and source kind.
   It is not a `PositionProtectionState`, protection policy, protection permit,
   or acquisition fact relation.
5. The retained target snapshot, direct binding, registry pair, reconciliation
   cursor, bootstrap record, and neutral proof must mutually authenticate. A
   changed component makes the book invalid rather than merely non-serving.

The first successful exact `RequestedEffect` for that scope consumes the active
bootstrap-bound record atomically as it adds the ordinary effect. Its permanent
input/provenance proof remains retained, but the active record may never remain
alongside an effect or authorize a second first-request path. A refused request
does not consume it.

### 1.2 Narrow transition and pair gates

R8 does not broaden any generic public or ordinary venue admission rule. The
private bootstrap primitive is the only additional pre-effect transition
permitted by the venue evolver. Its precondition is the exact unbound target
plus the source/absence proof above; its postcondition is the exact
bootstrap-bound record and neutral checkpoint proof above. The generic
`CatchUpExecutionRegistry` remains unbroadened.

The fast book/execution-pair check and its shared venue-authority view may
recognize an active bootstrap-bound target only when every direct record,
binding, snapshot, registry, cursor, and neutral proof component exactly
matches. That one shared predicate authenticates the bootstrap primitive's own
returned `APPLIED` transition and may then be consumed only by the exact first
specialized `RequestedEffect` on that target. No other external or effect
lifecycle input may start from it. On an accepted first request the record is
consumed atomically. A normal bound/effect pair remains governed by the
unchanged ordinary rule. This is not a general zero-effect-bound exception.

For `UNBOUND_BOOTSTRAP`, predecessor target execution/context fields are absent
because no retained target existed before the projection. The predecessor
authority is the exact input state; the current authority is its exact returned
replacement, the current execution is the newly retained/bound target snapshot,
and the current venue/authority contexts satisfy ordinary currentness. Exactly
one ordered venue transition is present and sealed to the source commitment and
target bootstrap identity. A raw initial target snapshot, a source snapshot
commitment, a scope token, or a copied result is not a substitute for the
owner-sealed handoff. `REFUSED` remains component-free and non-serving.

R8 replaces R6's generic non-`REFUSED` refresh-shape validation only for this
one disposition. Its dedicated validator requires: exact source execution and
predecessor authority; absent predecessor target execution, venue context,
authority context, and their commitments; present current authority, bound
target execution, current venue/authority contexts, and their exact retained
tokens; and exactly one `APPLIED`, zero-quantity bootstrap transition whose
book/execution are the returned current pair. `matches_current(...)` for this
disposition must re-derive that one bootstrap primitive from the sealed
predecessor authority/source/scope and require exact equality to the returned
pair and transition. It must not call the ordinary target-pair helper, which
correctly requires a pre-existing retained target. No other disposition,
missing component, second transition, or caller-built field arrangement is
serving.

The existing `unbound_flat_target` serving shortcut in
`VenueRecoveryBook.project_acquisition_context` is removed or made
non-serving. On a nonempty account, a raw target-only flat snapshot cannot
become serving; only this owner-side projection can establish the target's
ordinary binding/currentness. Generic `CatchUpExecutionRegistry` continues to
refuse an unbound target and is not broadened for this lifecycle.

## 2. Narrow permitted lifecycle

R6 section 4 is replaced only for first-controller initialization. Every other
R6 operation continues to accept only a serving `CURRENT` or `REFRESHED`
handoff.

### 2.1 First-controller initialization

`initialize_acquisition_controller(...)` accepts `UNBOUND_BOOTSTRAP` only
when all of the following are exact:

1. `application_generation_id`, mandate scope/session, handoff scope, target
   venue context, and target authority context match.
2. The supplied `BOOTSTRAP` projection and `GENESIS_EMPTY` admission match the
   handoff's sealed derived target execution and contexts.
3. The handoff has exactly one sealed bootstrap transition and its current
   authority contains the exact newly retained target binding/checkpoint. It
   has no effect, claim, permit, controller state, or currentness registration.
4. The controller derives the canonical genesis head, ordinal zero, and first
   generation ID exclusively through the existing E1 helpers.
5. Authority retains the existing `BOOTSTRAP` currentness source kind and owns
   a deterministic, domain-separated bootstrap-registration input derived from
   the sealed `UNBOUND_BOOTSTRAP` handoff/one transition plus the exact
   bootstrap/admission commitments. Neither the caller nor `acquisition.py`
   supplies a raw `AuthorityInputId` or a registration coordinate.

Initialization consumes the returned replacement authority and installs only
the sealed ordinal-zero BOOTSTRAP registration plus the corresponding pure
controller state. It adds no second venue binding/checkpoint or venue
transition, and creates no effect, claim, permit, protection state, fact route,
or controller-head advance beyond initial registration. A second initialization,
nonempty slot, copied handoff, wrong scope/generation/session, changed source,
or any target safety concern refuses without mutation.

The initialization composite result retains the sealed handoff and the ordinary
dispatcher registration receipt together. The receipt continues to report zero
venue transitions and must never claim it created the bootstrap transition;
that transition is authenticated only by the handoff. Conversely, a detached
bootstrap/admission token or detached post-bootstrap authority state cannot
substitute for the handoff at initialization.

### 2.2 Return to the ordinary first-BUY route

`UNBOUND_BOOTSTRAP` is consumed only by
`initialize_acquisition_controller(...)`. Before any first specialized BUY,
the caller must obtain a fresh ordinary `CURRENT` (or, if an independently
valid later registry advance occurs, `REFRESHED`) result from the replacement
authority state and its returned target snapshot. The normal specialized
`create_acquisition_effect(...)` route then sees the exact retained target
binding/current snapshot it already requires.

`create_acquisition_effect`, `begin_acquisition_generation`,
`claim_acquisition_effect`, `begin_acquisition_preemption`,
`create_acquisition_protection_exit`, `rebase_acquisition_protection`, and
every later create MUST reject `UNBOUND_BOOTSTRAP`. The bootstrap result may
not be replayed as an effect permit, a claim source, a successor admission, or
a later currentness proof. `reduce_acquisition_controller` remains driven only
by an authenticated canonical venue transition and never treats this bootstrap
transition as an economic fact source.

## 3. Preserved boundaries

R8 does not weaken any of the following:

- Generic exposure-increasing `CreateBrokerEffect(BUY)` remains refused before
  and after initial registration while a bootstrap-bound target record is
  active; only the specialized post-registration first-request route may consume
  that record.
- No caller-shaped bootstrap, admission, authority context, refresh, target
  snapshot, registry projection, controller head, ordinal, registration,
  permit, receipt, lineage, or closure is authoritative.
- The first unbound handoff performs exactly one target-local, zero-economic
  venue registry/binding projection. It is not a currentness-registration
  source, effect route, claim route, or economic fact source.
- Controller/currentness records retain target scope/venue/authority/protection
  continuity values only; they retain neither the raw source snapshot nor an
  account-history commitment. The bootstrap provenance remains only in the
  owner-side venue record required to authenticate its one transition.
- Same-account other-symbol history may provide one authenticated source, but
  it never authorizes a target condition that is not otherwise exact and
  target-safe.
- No history scan, second aggregate writer, policy composition, runtime,
  persistence, broker activity, or M2 behavior is introduced.

## 4. R8 failure-capable controls and acceptance

The composite candidate adds these controls:

| Requirement | Failure-capable control |
|---|---|
| Empty-account bootstrap | An exact empty-account target receives `UNBOUND_BOOTSTRAP`; the one internal zero-economic projection retains the exact flat target/binding, active bootstrap-bound record, and neutral checkpoint proof, then initialization derives ordinal zero and installs one registration without creating an effect, claim, `PositionProtectionState`, or normal protection authority. A second bootstrap or initialization is refused. |
| Other-symbol continuity | A current bound same-account source projects one exact flat target snapshot at the source registry high-water and atomically retains its direct target binding, record, and neutral proof. A raw stale/unbound target flat snapshot on a nonempty account is refused; unrelated history alone does not block the valid bounded projection. |
| Source and target fences | Foreign, unbound, stale, non-prefix, unresolved, copied, nonflat, target-bound, target-active, manual-flattened, preempted, exit-pending, or target-substituted sources/results refuse with no usable component. The special source rule permits no retained-target predecessor requirement only for `UNBOUND_BOOTSTRAP`; generic unbound `CatchUpExecutionRegistry` remains refused. |
| Book representation | A binding without an effect is valid only when its exact active bootstrap-bound record, registry pair, retained target snapshot, and neutral cursor/proof mutually match. A missing, copied, extra, effect-sharing, or mismatched record/proof invalidates the book rather than admitting a partial state. |
| First-create boundary | `UNBOUND_BOOTSTRAP` can initialize only the exact first controller. Its replacement authority then requires an ordinary `CURRENT` or `REFRESHED` result before the first specialized BUY. Only that first request may consume the matching active record atomically; no first-BUY exception or raw target snapshot is accepted. |
| Generic-BUY boundary | `CreateBrokerEffect(BUY)` refuses an active bootstrap-bound target both before and after initial registration. A matching venue view/record cannot substitute for the specialized post-registration authority route. |
| No hidden authority | Treating `REFUSED` or a raw unbound target as serving, retaining the `unbound_flat_target` shortcut, copying private fields/records, offering a raw registry projection, invoking the venue primitive from acquisition, or using `UNBOUND_BOOTSTRAP` for successor/claim/preemption/exit/rebase/BUY refuses before mutation. |
| Replay and identity | The private venue bootstrap input, direct record, and controller bootstrap-registration input are deterministically derived from their sealed commitments. Exact replay is stable; changed source, mandate, handoff, record, or input cannot replace the retained target binding or registered slot. |

An independent reviewer must compare the exact R2+R3+R4+R5+R6+R7+R8 composite
against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, retained R0-R7 evidence,
and the E1 execution/venue seams. Acceptance requires P0=0/P1=0 and a
concrete conclusion that unbound first-generation bootstrap preserves one
bounded controller, current full-input provenance, direct target safety, and
one canonical aggregate writer. Any change requires a new exact freeze and
focused review before implementation resumes.
