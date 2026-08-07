# WO-0151 RED contract R11 R1 -- purpose-separated preemption and exit intent

Status: **DRAFT REPLACEMENT PRE-FLIGHT CANDIDATE -- documentation only**

R11 R1 is an additive correction to the R2-R11 composite. It replaces R11
section 3 and the R11 controls that depended on one shared goal-bearing intent.
Every other R2-R11 provision remains controlling. The retained initial R11
review is non-acceptance evidence and cannot satisfy this candidate's review.

R11 R1 grants no application or test implementation, activation, runtime,
persistence, database, SQL/DDL, broker, credential, network, CI-workflow, M2,
merge, deletion, cleanup, force-push, rebase, or later-work-order authority.

## 1. Exact public operation signatures

`begin_acquisition_preemption(...)` retains its R6 signature. It does not
accept a caller goal, transition, intent, policy, or cancel terms:

```python
def begin_acquisition_preemption(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
```

Only `create_acquisition_protection_exit(...)` gains the existing opaque
protection transition that owns a SELL goal:

```python
def create_acquisition_protection_exit(
    state: AcquisitionControllerState,
    refresh: AcquisitionContextRefresh,
    protection: PositionProtectionState | None,
    transition: ProtectionTransition,
    input_id: AuthorityInputId,
) -> AcquisitionControllerTransition: ...
```

R11's prior addition of `ProtectionTransition` to
`begin_acquisition_preemption(...)` is withdrawn. No other public signature,
type, enum, command, currentness source, or export changes.

## 2. Protection-owned preemption-only intent

Add one exact private value and private projector, importable only by
`acquisition.py`:

```python
class _AcquisitionPreemptionIntent: ...  # exact, immutable, sealed, cancel-only

def _project_acquisition_preemption_intent(
    state: PositionProtectionState,
    current_context: AcquisitionProtectionContext,
) -> _AcquisitionPreemptionIntent | None: ...
```

The projector returns an intent only when:

1. `state` is exact and protection-authentic;
2. `current_context` is exact, protection-authentic, and matches that exact
   raw state, application generation, scope, scope-execution commitment,
   semantic protection commitment, source protection commitment, and current
   venue value;
3. quantity is positive and no greater than the mandate maximum;
4. policy is exactly `EXIT_NORMAL` or `HARD_BAIL`;
5. `waiting_buy_resolution` is true; and
6. the state carries authentic protection-owned exit or mixed-recovery
   provenance rather than caller-selected policy or reason text.

The intent binds a fixed `PREEMPT_BUY_ONLY` purpose, application generation,
scope, raw and semantic protection commitments, execution/context values,
mandate, quantity, policy, waiting status, owner provenance, and its own seal.
It contains no SELL goal, side, order type, guard, deadline, rate, broker
effect, claim, or generic cancellation authority.

Goal eligibility is intentionally irrelevant to this projector. A halted,
baseline-required, market-exhausted, formula-unavailable, or otherwise
conservative state may still require risk-reducing BUY stand-down while SELL
creation remains unavailable. The projector must not weaken the conditions
that suppress an `ExecutionGoal`.

For the standalone operation, `begin_acquisition_preemption(...)` first
authenticates an exact `CURRENT` refresh and current raw protection context,
then obtains this intent itself. For an already-applied current or retired fact
whose same atomic result creates a mixed or conservative protection state,
`reduce_acquisition_controller(...)` may obtain the same private intent from
that immediate owner-produced state and its exact resulting protection
context. It does not require an intermediate serving refresh or separate
currentness registration.

Acquisition passes only the purpose-bound relation into the existing private
authority permit seam. Authority rechecks the exact controller head,
generation, scope, currentness, effect owner, residual exposure, acceptance,
closure, reconciliation, and single-flight state immediately before mutation.
The result may invalidate one unclaimed BUY or stage at most the one exact
bounded cancel allowed by the accepted authority/venue rules. Claimed,
unknown, OPEN, INVALIDATED, cancellation-only, stale, mismatched, or already-
cancelled work remains waiting or reconciliation-only. The preemption intent
can never create or claim a SELL and can never serve
`create_acquisition_protection_exit(...)`.

## 3. Separate goal-bearing protection-exit intent

Replace the R11 exit projector with:

```python
class _AcquisitionProtectionExitIntent: ...  # exact, immutable, sealed, SELL-only

def _project_acquisition_protection_exit_intent(
    transition: ProtectionTransition,
    current_context: AcquisitionProtectionContext,
) -> _AcquisitionProtectionExitIntent | None: ...
```

The projector accepts only an authentic `APPLIED` reducer transition with a
non-`None` owner-produced goal. Its resulting state must be the exact current
raw state authenticated by `current_context`; policy must be `EXIT_NORMAL` or
`HARD_BAIL`; quantity must be positive; `waiting_buy_resolution` must be
false; and the goal must be SELL and bind the exact execution, raw protection,
residual quantity, urgency, guard, deadline, session, mandate, rate, and real
exit provenance. All formula, market-generation, halt, baseline, exhaustion,
quantity, mandate, and goal conditions remain protection-owned and are
rechecked. The sealed intent is fixed to a `CREATE_PROTECTION_EXIT_ONLY`
purpose and performs no venue or authority decision.

`create_acquisition_protection_exit(...)` requires an exact `CURRENT` refresh,
the supplied `protection` to be the exact authentic value represented by
`transition.state`, and
the resulting current protection context to match every controller/refresh
fence. This is value/commitment equivalence, not object identity. It obtains
the intent itself. Authority then rechecks BUY closure,
reconciliation, acceptance, single-flight, controller head, residual quantity,
guard, budget, currentness, and existing SELL ownership immediately before
creating or claiming at most one protective SELL. Caller-created goals,
preemption-only intents, old transitions, replay-only transitions, stale raw
state/context, or changed terms cannot serve.

## 4. Neutral refresh and cross-side composition

Neutral reprojection remains transport-only and emits no goal, alert, intent,
receipt, registration, effect, or claim. Its fresh raw result cannot orphan a
sticky exit requirement:

- if BUY resolution is still required, the preemption-only projector consumes
  the fresh current raw state and context without requiring a SELL goal;
- if BUY resolution is clear and SELL eligibility is valid, the existing pure
  protection reducer may produce a fresh authentic goal-bearing transition
  from the same bounded venue transition inside the atomic operation, and the
  exit projector consumes that transition; and
- an old goal-bearing transition never becomes current merely because its
  target semantic commitment is unchanged.

No old book/snapshot graph or raw-state cache is retained after the atomic
operation. A preemption-only intent is not upgraded after cancellation; a
fresh current protection state/context and fresh goal-bearing transition are
required for SELL creation. If market baseline, halt, exhaustion, formula, or
another protection gate still suppresses the goal, SELL creation remains
unavailable even though safe BUY stand-down was permitted.

For a retired fact with current BUY work, the one combined
`AUTHORITY_MUTATION` receipt may bind the exact fact relation, mixed-recovery
result, preemption-only intent, exit permit, and ordered venue transitions.
It adopts fact economics once, invalidates or cancels at most one current BUY,
stales its claim authority, and advances the controller/currentness head once.
It does not also register `CANONICAL_FACT`. When no authority mutation is
needed, the existing canonical-fact source remains the only registration.

## 5. Preserved ownership and boundedness

Both intent values and projectors are private to protection and imported only
by acquisition. They are not exported, persisted as public controller state,
accepted from a caller, or inspected by authority. Acquisition consumes each
immediate owner result only for its fixed purpose and invokes the already
bounded private authority permit seam. `protection.py` imports neither
`authority.py` nor `acquisition.py`; `authority.py` imports no protection
symbol. Acquisition never reconstructs protection policy, provenance, goal,
urgency, guard, SELL terms, or preemption need from public fields.

Neither intent is a fifth currentness source, broker capability, generic
cancel/BUY/SELL path, map entry, audit record, or history-derived decision.
Every R2-R11 direct-index, exact-head, no-scan, single-writer, and final-claim
boundary remains controlling.

## 6. Replacement failure-capable controls

These controls replace the R11 exit-intent and cross-side control rows and add
the missing composition cases. All other R11 controls remain controlling.

| Requirement | Failure-capable control |
|---|---|
| Preemption producer totality | B has one unresolved unclaimed or cancellable BUY and no recovered protection baseline when a late retired-A fact produces current mixed `HARD_BAIL`. The composite obtains one preemption-only owner intent, invalidates or cancels at most one BUY, advances fact/currentness exactly once, and creates no SELL eligibility. Repeat for an abnormal current first root. |
| Preemption purpose | A goal-less current state with exact waiting/provenance can preempt only its current BUY. Wrong state/context, false waiting, wrong policy/provenance, nonpositive or excessive quantity, stale head, wrong effect owner, duplicate cancel, or a mutant that requires a SELL goal turns the control RED. |
| No preemption-to-SELL escalation | Supplying a preemption intent, preemption result, baseline-required state, unresolved BUY, caller goal, or copied terms to the protection-exit route cannot create or claim a SELL. Removing the purpose distinction turns the control RED. |
| Goal-bearing exit | After exact BUY closure and recovered protection conditions, only a current authentic `APPLIED` transition with its owner-produced SELL goal can create the exit intent. Old/replay-only/goal-less/altered transition, stale raw state/context, changed residual/guard/deadline/mandate/rate, halt/baseline/exhaustion, or changed head refuses. |
| Neutral continuity | After one sibling catch-up, the fresh raw state can still produce preemption-only intent while waiting. A prior goal transition is stale; when SELL conditions are valid, only a freshly derived transition matching the neutral result can produce exit intent. No controller/currentness mutation occurs merely to transport the raw state. |
| Combined fact ordering | Retired and abnormal-current facts before BUY create, after create, and before final claim prove one aggregate application and one head advance. The preemption branch emits at most one cancel and no SELL; exact replay cannot add a second receipt, registration, cancel, effect, or claim. |
| Structural boundary | Static controls reject either intent as a public export/input, a raw `ExecutionGoal` input, policy reconstruction in acquisition/authority, protection imports in authority, authority imports in protection, extra currentness sources, raw-context caches, generic cancel/SELL routing, or history materialization. |

Named mutations must independently remove the preemption purpose, current
state/context matcher, waiting/provenance check, goal independence, exit-goal
requirement, current transition/state binding, one-cancel cap, single head
advance, and final-claim revalidation and demonstrate that the corresponding
control turns RED.

## 7. Focused acceptance

A fresh independent reviewer must verify the exact R2-R11-plus-R11-R1
composite and re-derive all remaining routes. The review must specifically
disprove the initial R11 P1 for unresolved-BUY/no-baseline preemption, ensure
the purpose-separated intents cannot substitute for each other, and repeat the
neutral, abnormal-first-root, retired-fact, combined-registration, and final-
claim counterexamples. Acceptance requires P0=0 and P1=0. The initial R11
review and its packet-contamination disclosure remain retained negative
evidence and cannot satisfy R11 R1 acceptance. Any material change requires a
new exact freeze and focused review.
