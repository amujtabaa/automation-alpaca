# Proposed ADR — Position protection and side-symmetric liquidity execution

## Status

Proposed. Becomes Accepted only when Ameen approves the exact packet hashes and M0 lands this text
unchanged under an available canonical ADR number.

## Context

ADR-010 correctly established immutable bounded human authority, fill-only quantity, single-flight
execution, and conservative broker ambiguity. It incorrectly overloaded `floor_price` as a
minimum allowed SELL limit. The intended hard floor is an escalation trigger; a collapsing market
may require an authorized limit/fill below it.

The current all-purpose envelope also combines immutable authority, mutable progress, venue
attempts, and projections. BUY acquisition has no equivalent liquidity-aware supervisor.

## Decision

### Separate types and ownership

- `AcquisitionMandate`: immutable human-approved BUY scope.
- `ProtectionMandate`: immutable human-approved hard-bail and trail-activation formula
  parameters, execution guards, evidence policy, session, data, quantity, rate, and configuration
  authority. It does not store a fill-dependent absolute trigger as if that price were known
  before execution.
- `PositionProtectionState`: mutable
  `FLOOR_ONLY | TRAIL_ACTIVE | EXIT_NORMAL | HARD_BAIL | FLAT` plus the derived armed
  hard-bail trigger, activation price, watermark, trail, and retained owning-mandate/exit
  provenance.
- `ExecutionGoal`: side, residual, urgency, guard, deadline, session, and owning mandate.
- `VenueAttempt`: reducer-owned order lifecycle.
- `BrokerEffect`: transport request lifecycle.
- `VenueObservation`: immutable correlated broker fact with provenance.

Every acquisition mandate immutably references a complete approved protection mandate before any
BUY effect may be created/claimed. Its first fill activates `FLOOR_ONLY` and derives the first
armed trigger and activation price from that exact formula authority plus the just-applied
fill-derived long average cost.

### Position and integrity

Only first-occurrence canonical fill-family execution facts change raw position quantity:
ordinary fills add one root contribution, while a valid broker correction/bust atomically
replaces that root's current contribution. Same-ID/same-economics is an economic no-op.
Same-ID/different-economics preserves the first fact and enters conflict reconciliation.

Broker-authoritative overfills are applied exactly, including a negative position, and set
permanent `OVERFILL_QUARANTINE`. Authorized residual SELL becomes zero; autonomous work stops.
Local/synthetic malformed fills are rejected before mutation. No acknowledgement changes
quantity.

Operator-supplied economic evidence is a separate `HUMAN_ATTESTED` fill authority. It can change
position only through the canonical fill transition after exact-leg, order-capacity, cumulative
quantity, actor, reason, evidence, and long-only checks. It cannot use the
broker-authoritative overfill exception.

Canonical economic truth includes immutable `FILL`, `TRADE_CORRECT`, and `TRADE_BUST`
fill-family facts. Every fact has a unique source-event ID and exact
broker/environment/account/order/symbol/side scope. A correction or bust also names its exact
predecessor and broker-authoritative root fill. `FILL` carries positive absolute quantity/price; `TRADE_CORRECT` carries positive
revised absolute quantity/price; `TRADE_BUST` carries revised absolute quantity zero.

Only a broker-authoritative correction/bust linked to the current predecessor head of a broker-
authoritative root with exact scope may replace the root contribution. The transition substitutes the new head at the original
root-fill sequence, reapplies the accepted ordered long-only average-cost fold, and atomically
commits the old-fold-to-new-fold delta. It never naively subtracts an earlier root from basis after
later dependent facts, mutates or deletes prior facts, or treats the replacement as another
positive fill. Missing,
branched, stale, out-of-order, or scope-conflicting lineage enters reconciliation, keeps the
symbol non-serving, and causes zero economic mutation. Exact full-payload retries are no-ops;
changed retries conflict. Valid broker-authoritative replacement economics remain exact even
when they reveal negative quantity, which sets permanent overfill quarantine.
`HUMAN_ATTESTED` authority remains a capacity-capped `FILL` and cannot be corrected or busted
directly. Overlapping later broker evidence remains in reconciliation until exact leg-level mapping
proves how to avoid double counting.

When later economic facts make the ordered basis refold non-local, the valid canonical
correction/bust and exact raw-quantity delta still commit immediately. Basis becomes unavailable
under `BASIS_RECONCILIATION_PENDING`; cancellation/reconciliation effects are recorded for
exposure-increasing BUYs and newly oversized SELLs, entry is blocked, and every positive long
residual enters restricted `HARD_BAIL`. Actual broker outcomes remain occurrence-tracked. While a
conflicting leg/set remains potentially live, only cancel/query/reconcile may claim; after the
ordinary uncertainty gate passes, quantity-capped, basis-independent risk reduction under the
retained emergency guard becomes eligible. A slow-path basis candidate has no authority until a sequenced transaction
revalidates the exact chain high-water and restores checkpoint basis/formula values atomically.

`FLAT` requires raw fill-derived zero and no attempt that may execute. A fill may establish zero;
if ownership remains ambiguous, a later correlated terminal fact may finalize `FLAT` without
changing quantity. A later first-occurrence owned BUY fill or valid correction/bust that restores
positive long quantity applies economics first and atomically returns the retained mandate to
`HARD_BAIL`, recomputes the residual, and emits a critical alert. It never leaves positive
quantity in `FLAT` or invents new protection authority.

### Hard-bail and trail

`ProtectionMandate` approves an immutable hard-bail loss formula and favorable activation
formula, both referencing fill-derived long average cost; `PositionProtectionState` owns their
derived prices. After every accepted economic execution fact, position and basis update first.
The armed hard-bail trigger is the first derived candidate or
`max(previous_armed_trigger, candidate)`, so later economics may tighten but never loosen it.
While `FLOOR_ONLY`, the activation price is recomputed from current average cost; once activated,
the trail never deactivates merely because later fill/correction/bust economics change basis.

Mandate validation requires `0 < loss_fraction < 1` and `approved_gain > 0`. Formula arithmetic
is exact before one tick conversion. The hard-bail loss candidate rounds upward to the least valid
tick at or above the exact result that is still strictly below long average cost; the activation
candidate rounds upward to the least valid tick at or above its exact result. Thus protection is
not loosened by downward rounding and trail authority is not granted below the approved gain.
Incompatible scale/tick data or absence of a required valid tick refuses mandate admission. If an
authoritative broker execution fact exposes the incompatibility later, its exact economic delta
still commits first; only derived-price authority is withheld, and any positive long remains
restricted/non-serving `HARD_BAIL`. The fact is never rejected, clamped, or delayed.

The derived `armed_hard_bail_trigger_price` changes protection state and urgency. It is not a
minimum order/fill price and guarantees no fill. `normal_execution_guard` and
`emergency_execution_guard` separately bound child price/slippage relative to validated current
liquidity.

Hard-bail evidence is evaluated before trail evidence and is sticky until flat. Eligible evidence
is either two distinct, fresh, consecutive valid best-bid source occurrences at/below trigger,
with the second proving a new source occurrence by greater source sequence when available or by a
different adapter-stable identity that is not derived from local receive time, or a fresh trade plus best bid
at/below within the versioned window with distinct retained source-occurrence identities. The
aggregate retains those identities; an exact replay, including after restart with a new local
receive time, cannot advance corroboration. Suspect/crossed/stale/nonfinite data emits no order.

While `FLOOR_ONLY`, the versioned favorable activation price is
`average_cost * (1 + approved_gain)`. Eligible favorable evidence at/above that price activates
the trail. After activation:

\[
H_t=\max(H_{t-1}, bid_t)
\]

\[
T_t=\max(T_{t-1}, H_t(1-p), H_t-k\,ATR_t, T_{\text{structure if available}})
\]

Unavailable components are omitted. The tick-rounded trail never decreases and is durably
committed before the higher trigger gains authority.

### Liquidity executor

One pure side-symmetric executor accepts an approved `ExecutionGoal` and validated
`LiquiditySnapshot`. It chooses bounded `PASSIVE`, `IMPROVE`, `CROSS`, or `SWEEP` child behavior.
Quantity is capped by authoritative residual, fixed child cap, approved risk cap, and only
certified liquidity/volume participation inputs.

Outside RTH there is no silent market-order fallback. `HARD_BAIL` may relax participation and
passivity but not residual, reduce-only, identity, session, capability, or emergency guard.
Predictive velocity/imbalance has no beta authority.

### Attempt, effect, and observation

Transport acknowledgement is not order terminality:

- cancel acknowledgement leaves `VenueAttempt=CANCEL_PENDING`;
- replace acknowledgement does not prove predecessor terminal;
- only correlated broker-terminal observations release single-flight ownership;
- delayed statuses cannot regress terminal/higher state;
- new canonical economic execution facts are always processed through their exact lineage rules.

Unknown mutating requests retain exact immutable occurrence and economic scope. Query failure or
one lagging not-found is not absence. ADR-002/012 targeted-query, durable `needs_review`, and
operator-attested release semantics remain binding. No new attempt is created in the release
transition.

A stable client/effect ID does not imply one broker order. Every creating client ID is nonempty,
unique in its application-generation/Paper account, and bound to the canonical generation/broker/
environment/account/occurrence tuple. One effect may own multiple immutable concrete `VenueLeg`
identities. Each is bound by a composite parent key to the exact effect, client binding,
occurrence/economic scope, contributes independently to `symbol_may_execute`, receives its own
cumulative-fill/status evidence, and must close independently. A second acceptance is never
collapsed into a singular mutable broker ID.

Every created mutating occurrence has one canonical `broker_effects.acceptance_set_state`; the
checkpoint carries no durable copy. `OPEN` remains potentially live even after every known leg is
terminal. `CLOSED` requires either a locally canceled occurrence with no immutable
`broker_effect_claims` row, an adapter-certified complete response, or an exact-occurrence query
with complete cursor/interval coverage. Leg terminality, one not-found response, and position
parity are insufficient. Once a claim row commits, it cannot be updated/deleted and makes
`NEVER_DISPATCHED` impossible; decision receipts do not prove absence. A delayed acceptance after
closure preserves the closure proof and moves only to permanently non-releasable `INVALIDATED`
with append-once contradiction evidence. An in-memory/persisted mismatch enters reconciliation and
remains non-serving.

ADR-012 remains an explicit two-command boundary. Missing executions are first ingested as
capacity-capped `HUMAN_ATTESTED` canonical fills. The later non-economic release requires exact
leg/occurrence identity, broker-terminal state, and equality between attested cumulative venue
quantity and fills attributed to that leg. Only that leg may transition
`NEEDS_REVIEW -> OPERATOR_RECONCILED`; sibling legs, overfill quarantine, other ambiguity, and
position quantity are unchanged. Changed retries conflict, and release emits no successor effect.
Later broker evidence for an attested cumulative interval is reconciled against the leg total
before applying any delta; it cannot double-count the attested execution.

One pure `symbol_may_execute` classifier is consumed at command admission, effect creation, and
final claim by acquisition, protection, flatten, emergency reduce, and native/local handoff.
Safely local unclaimed BUY work may be stood down atomically; a venue-uncertain BUY or an
`OPEN`/`INVALIDATED` parent acceptance set blocks a SELL. Only exact `CLOSED` can release the parent.

### Trading mode and manual controls

- `ACTIVE`: normal approved work.
- `REDUCING`: deny exposure increase; allow quantity-capped reduce-only SELL and cancels.
- `HALTED`/kill: deny every new submit/replace/ordinary flatten, including hard-bail SELL; allow
  cancel/query/reconcile.

An emergency reduce in `HALTED` requires an explicit, audited, immutable, account/symbol/session-
scoped one-shot grant carried by the command. It remains reduce-only, uses the smaller trustworthy
long quantity, is consumed only by a successful claim, and cannot bypass venue uncertainty.

Manual flatten atomically stands down safely local work, cancels and awaits terminal known
cancellable work, refuses on unknown potentially-live work, re-reads quantity/exposure at final
claim, and never becomes a generic replacement path.

If either `EXIT_NORMAL` or `HARD_BAIL` requires an exit while a BUY is outcome-unknown, the
durable orthogonal condition is `EXIT_WAITING_BUY_RESOLUTION(policy_state)`. The policy state is
preserved: normal exit retains its normal guard; hard bail remains sticky and retains emergency
urgency/guard. Waiting alone cannot promote normal authority into emergency authority. The delay
may be unbounded; it has an alert, elapsed exposure, targeted reconciliation, and the accepted
operator-release boundary. Closing every known BUY leg is insufficient: the parent occurrence
must be exactly `CLOSED`; `OPEN` or quarantined `INVALIDATED` never releases the wait.

### RTH/native ownership

Ownership is explicit:
`LOCAL_EMULATED | HANDOFF_TO_NATIVE | NATIVE_CONFIRMED | HANDOFF_TO_LOCAL |
OWNERSHIP_AMBIGUOUS`.

Both directions cancel/reconcile the incumbent, ingest all fills, establish broker parity,
recompute residual, and atomically claim at most that residual before the successor. Native
confirmation requires exact scope plus broker-authoritative working/accepted state, not HTTP
acknowledgement. Timeout, mismatch, or late fill enters ambiguity and blocks new work.

No zero-gap guarantee is claimed. Handoff remains separately human-gated after paper traces.

## Preserved authority

This ADR preserves ADR-001, ADR-002, ADR-003, ADR-008, ADR-010's non-floor safety clauses, ADR-012,
and Spine INV-1…INV-9 as mapped in the clause matrix. It supersedes only the all-purpose envelope
type, floor-as-minimum-limit rule, and live history-fold policy.

## Consequences

- The present sell-side code is a reference corpus, not the new authority.
- BUY/SELL share execution mechanics but not supervisor states.
- Exit safety may stall on unresolved BUY/SELL ambiguity; it never guesses absence.
- Handoff, native replace, partial-profit tranches, structure authority, and depth authority remain
  gated.

## Required evidence

- Hypothesis state machines for fill/correction/bust lineage, attempts, effects, distinct trigger
  observations, kill/claim, cross-side preemption, multi-acceptance, human-attested fill/release,
  ambiguity, overfill, and flat finalization.
- Named counterexamples prove: `BUY 10 @ 100 -> BUST` contributes zero;
  `BUY 10 @ 100 -> CORRECT 7 @ 101` leaves quantity 7/basis 707; missing, branched, stale,
  out-of-order, and scope-conflicting predecessors mutate no economics and make the symbol
  non-serving.
- Duplicate/restart replay of one below-trigger source occurrence cannot satisfy two-observation
  corroboration.
- Generated histories preserve `EXIT_NORMAL` versus `HARD_BAIL` while waiting for BUY resolution,
  and a late owned BUY fill after `FLAT` atomically restores `HARD_BAIL` rather than leaving
  positive quantity flat.
- Named composed histories prove that pending basis plus kill/`HALTED` emits no SELL without the
  scoped grant, an `OPEN`/`INVALIDATED` BUY parent permits only cancel/query/reconcile, and manual
  flatten still obeys uncertainty and final-claim residual gates.
- Tick/scale incompatibility after an authoritative broker fact withholds only formula authority;
  a mutant that rejects or delays the economic fact fails.
- Null/duplicate/cross-generation creating-client identities, owner-scope substitution, a cleared
  effect row after immutable claim, and late acceptance after `CLOSED` are all refusal/non-release
  counterexamples.
- A named restart property for human-attested cumulative fill followed by matching and
  mismatching broker-authoritative evidence.
- Mutation proof for every capital invariant.
- Simulator crash/reorder histories.
- Adapter conformance and paper traces before broker effects.
- Independent milestone review.
