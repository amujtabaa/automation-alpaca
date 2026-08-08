# WO-0151 RED contract R13 -- atomic serial-successor protection-cursor rollover

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

R13 retains all accepted R11/R11-R1/R12-R1 semantics and corrects only the
completed-flat serial-successor cursor constructibility gap exposed by frozen
WO-0152 FR-08 evidence. It grants no implementation authority.

## 1. Unchanged boundaries

No public signature, type, enum, export, authority input, acquisition currentness
source kind, protection API, runtime path, persistence path, database path, or
E3 contract changes. `begin_acquisition_generation`, ordinary
`project_protection_venue`, and public venue inputs retain their signatures and
ordinary semantics. `protection.py` and public exports are not R13 paths.

R13 MUST NOT transfer A's positive protection state, true-FLAT marker, trail,
capacity, market cursor, ordinary policy, or acquisition authority to B. It
MUST NOT add a public rollover command, generic mandate rollover, history scan,
controller history, authority-side duplicate index, cursor reset/deletion,
policy merge, or caller-shaped authority.

## 2. Exact root correction

### FR-01 -- venue-owned serial rollover proof

`venue.py` MUST add one private, domain-separated protection-transition source
usable only for a completed-flat serial successor. It MUST bind the exact:

- target `PositionScope`, predecessor cursor/head/ordinal, and A mandate;
- distinct B protection mandate;
- unchanged exact execution snapshot, checkpoint, binding, book envelope,
  authority summary, and clear reconciliation state; and
- successor currentness-registration commitment supplied only by authority.

It MUST produce one authentic zero-quantity `VenueRecoveryTransition` whose
only semantic book change is the direct scope cursor and its predecessor-linked
proof ledger entry. It MUST NOT create or change an effect, claim, owner, root,
acceptance set, execution economics, session, budget, or public authority.

`_ProtectionTransitionProof` MAY gain a private source-kind and source-binding
coordinate for this purpose. The ordinary proof source retains its absolute
no-bound-mandate-change invariant. A raw commitment, copied proof, direct
private call, or ordinary/public venue input is not authority to publish B.

### FR-02 -- authority-only atomic composition

Only `_register_acquisition_currentness` MAY invoke the exact private venue
bridge, and only after all existing successor, flatness, closure, binding,
single-flight, integrity, and reconciliation gates pass but before it publishes
the B currentness entry. The bridge MUST be the sole private venue import/call
site in authority; acquisition MUST NOT import it.

For an authentic completed-flat A-to-B successor, authority MUST accept exactly
one authentic rollover transition with zero quantity delta, unchanged execution,
and a source binding equal to the exact successor registration. Authority MUST
install the rolled venue book and B currentness in one immutable state result,
record one ordered venue-transition commitment in the acquisition receipt, and
return that one transition. Any mismatch or failure MUST return the exact
predecessor state, venue, execution, controller inputs, and no receipt/effect/
claim/currentness mutation.

For an authentic aborted/unrooted A-to-B-to-C successor, authority MUST retain
the existing zero-venue-transition route and unbound cursor. It MUST NOT mint a
rollover merely because the next mandate differs.

### FR-03 -- serving compatibility fence

Venue MUST expose only a private bounded predicate for authority composition:
for an exact scope, the retained cursor is either unbound or has the exact
protection mandate recorded in the retained currentness entry. The central
acquisition-authority serving projection MUST use this predicate. Thus an old
A venue book coupled with B currentness is non-serving even if other retained
coordinates are authentic. The check MUST use one direct scope lookup only and
MUST NOT expose a public reader or materialize retained history.

### FR-04 -- unchanged first-root and late-fact behavior

After an accepted completed A-to-B rollover, B's first canonical BUY fill MUST
use the unchanged strict ordinary protection projector and yield fresh B
`FLOOR_ONLY` protection under B's distinct mandated stream. Late retired-A
FILL/CORRECT/BUST facts before or after B's first fill MUST remain exact A
lineage, advance economics/currentness exactly once, and enter compatible
mixed `HARD_BAIL` without creating B normal capacity. The frozen E3 detector
is the downstream public confirmation; R13 must not edit it.

### FR-05 -- structural containment

The private bridge and its source proof MUST be sealed and non-public. No
venue-to-authority import is permitted. Receipt binding MUST not create a
cyclic proof: venue owns local transition authenticity; authority separately
requires the opaque proof source binding to equal its sealed registration.

## 3. Required RED controls

| ID | Failure-capable control |
|---|---|
| AC-01 / FR-01-02 | Completed rooted flat A-to-B produces exactly one authentic, zero-delta, receipt-bound A-to-B cursor rollover and B first fill is `APPLIED` with fresh B `FLOOR_ONLY`. |
| AC-02 / FR-02 | Aborted/unrooted A-to-B-to-C remains `APPLIED` with zero rollover transitions and unbound cursors. |
| AC-03 / FR-03 | An authentic old-A venue book paired with B currentness is non-serving; normal B authority remains serving only against the rolled book. |
| AC-04 / FR-01-02 | Missing, duplicated, copied/rebound, wrong-scope, same-mandate, wrong-old/new-mandate, nonflat, unclear-reconciliation, live/unknown/cancellable ownership, or registration-mismatched rollover refuses atomically. |
| AC-05 / FR-01,05 | Public venue inputs and generic authority routes cannot mint rollover authority; an ordinary transition attempting to change a bound mandate remains invalid. |
| AC-06 / FR-04 | Late retired-A facts before and after B first fill remain A lineage and force B-compatible `HARD_BAIL`, never B normal capacity. |
| AC-07 / FR-05 | Static boundary controls permit the bridge only at the authority successor-registration site and reject acquisition private-venue imports, public/private command exposure, history materialization, or a public cursor reader. |
| AC-08 / FR-01-05 | Scoped mutations removing the completed-flat gate, old/new mandate distinction, source-registration binding, receipt transition binding, exact-one transition check, or serving-compatibility predicate make their named controls fail, then restore. |

All ordinary invalid-but-type-correct inputs use established fail-closed
transition conventions. An inauthentic predecessor state remains invalid input
rather than a fabricated trusted refusal envelope.

## 4. Proposed exact implementation paths

R13 may change only after independent acceptance, ratification, and activation:

- `app/execution_core/venue.py`;
- `app/execution_core/authority.py`;
- `app/execution_core/acquisition.py`;
- `tests/execution_core/test_acquisition.py`;
- `tests/execution_core/test_authority.py`;
- `tests/execution_core/test_venue_recovery.py`;
- `tests/execution_core/test_protection.py` only for the retained strict
  ordinary projector control; and
- `tests/execution_core/test_import_boundary.py` only for exact private-import
  and static-owner controls.

Directly necessary current work-order, active WO-0152 dependency, PKL, ledger,
ratification, and exact `REV-0060` evidence records are permitted. No other
path is implied.

## 5. Gate and stop conditions

No R13 source or test implementation begins until this exact contract and an
exact manifest independently `ACCEPT` at P0=0/P1=0, the user ratifies that
packet, and a separate activation record reconciles its exact publication SHA.
After implementation, R13 must pass focused and full predecessor gates plus
independent implementation acceptance before the unchanged E3 detector reruns.

Stop for a new decision if the correction needs an ADR amendment, public API,
venue-to-authority import, a history scan, a second controller, policy/cursor
transfer, database/runtime work, or an E3 expectation change. The paired E2/E3
unchanged 93% exact-head closeout remains mandatory.
