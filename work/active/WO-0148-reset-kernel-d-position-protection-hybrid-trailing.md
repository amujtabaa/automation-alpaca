---
type: Work Order
title: "Reset kernel D: position protection and hybrid trailing"
status: ACTIVE
work_order_id: WO-0148
wave: RESET-M1D
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-08-02
branch: codex/arch-reset-2026-07-r1
base_sha: 3e39ee6a857ae61d850da1b841e85008b9a59fbb
staged_source: work/queue/ARCH-RESET-2026-07/06-roadmap.md#M1--Pure-reference-kernel
predecessor: WO-0147
activation_ci: "GitHub Actions run 30794934357 (#687): Python 3.11 job 91626251701 SUCCESS; Python 3.12 job 91626251758 SUCCESS"
---

# WO-0148 - Reset kernel D: position protection and hybrid trailing

`[FABLE - FULL - verification: DIRECT + generated histories + mutation + independent review - task: pure position protection]`

## Activation and authority

Ameen authorized completing every remaining M1 slice, resolving in-flight findings, and producing
an independently accepted M2-ready milestone. This work order activates only after immutable
predecessor closeout `3e39ee6a857ae61d850da1b841e85008b9a59fbb` passed unchanged GitHub Actions
run #687 on Python 3.11 and 3.12. `WO-0145` through `WO-0147` are effective `CLOSED`; only
`WO-0148` is active. `WO-0149` and M2 remain inactive.

This slice is pure, deterministic, and unwired. It grants no operational authority. Do not
discover or use credentials, call Alpaca Paper, perform broker/network I/O, execute SQL/DDL,
initialize or mutate a database, alter persistence, wire runtime code, authenticate or mint a
supervisor fence, merge, or delete/clean any ref, worktree, or artifact. Existing full-suite
fixtures may use only the previously authorized mock/disposable-test path. The prohibited R1 DDL
result remains inadmissible.

## Goal

Build one broker-neutral protection semantic center that derives and retains position protection
from exact accepted execution truth, exact venue ownership, immutable human-approved formula
authority, and validated market occurrences. It owns the trigger/guard split, monotone floor and
trail policy, orthogonal BUY-resolution waiting, flat finalization, late-fill re-protection, and a
typed SELL execution goal. It creates no venue effect and cannot bypass M1C admission/final claim.

## Fable gate

```yaml
fable_gate:
  goal: "Implement pure fail-closed position protection without runtime, persistence, or broker authority."
  assumptions:
    - claim: "Execution economics and venue ownership already have canonical immutable current-state reducers."
      status: VERIFIED
      evidence: "WO-0145/0146 are closed; app.execution_core exposes bound ExecutionSnapshot and opaque VenueRecoveryBook values."
    - claim: "Protection policy can remain a separate semantic center while consuming those canonical values."
      status: VERIFIED
      evidence: "ADR-020/021 separate execution truth, venue attempts/effects, PositionProtectionState, and ExecutionGoal."
    - claim: "A caller-authored may_execute, waiting, formula_valid, or protection-ready flag would be unsafe."
      status: VERIFIED
      evidence: "Flat and wait release depend on exact effect-parent closure, symbol uncertainty, and execution binding; M1B already owns those facts."
  approach: "Freeze activation; write RED examples and bounded state machines; independently refute the test contract; implement one opaque reducer and one narrow venue-owned projection; kill named mutants; refactor; freeze for blind review."
  alternatives_considered:
    - "Extend legacy app/protection.py - rejected because the incumbent runtime is frozen evidence."
    - "Embed protection fields in PositionState - rejected because execution economics and protection policy have different authority and replay lifecycles."
    - "Accept caller-computed closure or eligibility booleans - rejected because stale or forged inputs could release waiting or mark exposure flat."
    - "Build liquidity child-order logic now - rejected because M1.4 owns policy output, not M3 execution behavior."
  blast_radius: "Pure app.execution_core source, isolated tests, and WO/review/PKL records only."
  rollback: "Revert only WO-0148 commits while preserving closed WO-0145 through WO-0147 and every retained artifact."
```

## Normative design contract

1. `ProtectionMandate` is immutable, exact-type validated, and distinct from mutable protection
   state. It retains mandate/scope/session/data/config identity; loss, activation, percent-trail,
   and ATR parameters; tick authority; evidence policy; normal/emergency execution guards; and
   quantity/rate bounds. Construction validates authority shape only and never authenticates a
   human, feed, account, or operational fence.
2. `PositionProtectionState` is opaque and reducer-owned. Its policy is exactly `FLOOR_ONLY`,
   `TRAIL_ACTIVE`, `EXIT_NORMAL`, `HARD_BAIL`, or `FLAT`, plus exact execution/venue high-water,
   owning mandate, derived trigger/activation/watermark/trail, evidence branches, wait condition,
   restriction/alert state, and prior exit provenance.
3. Protection advances economic state only from an exact reducer-constructed opaque venue recovery
   transition carrying an authenticated predecessor/successor execution-and-venue high-water. The
   resulting canonical `ExecutionSnapshot` is consumed after its economics. A positive exact-basis
   first fill arms `FLOOR_ONLY`; pending basis, incompatible formula metadata, reconciliation, or
   overfill is fail-closed. No protection input changes position quantity or reimplements a fold.
4. The protection reducer consumes exact venue ownership only through one narrow venue-owned
   bounded projection paired to that high-water. `venue.py` may change solely to produce this
   opaque transition proof/projection from its canonical indexes; it may not expose raw closure or
   mutation capability. Protection never accepts a caller-authored `may_execute`, parent-closed,
   BUY-clear, binding-valid, or flat-ready boolean and never scans audit history on the hot path.
5. `FLAT` requires raw quantity zero, exact current execution binding, clear account
   reconciliation, and zero effects/attempts that may execute. An `OPEN` or `INVALIDATED` parent,
   outcome ambiguity, a known live leg, or a stale/mismatched book cannot finalize or preserve flat.
6. A first-occurrence owned BUY fact or valid correction/bust restoring positive quantity after
   `FLAT` applies economics first, atomically restores the retained mandate to sticky `HARD_BAIL`,
   recomputes residual, and raises a deterministic critical-alert output. It never invents a new
   mandate or returns to unarmed `FLOOR_ONLY`.
7. BUY-resolution waiting is orthogonal. It preserves `EXIT_NORMAL` versus `HARD_BAIL` and the
   matching guard/urgency. Only exact current venue truth with every BUY leg closed and each parent
   acceptance set `CLOSED` releases it; known-leg terminality, `OPEN`, and `INVALIDATED` do not.
8. Mandate admission requires `0 < loss_fraction < 1`, `approved_gain > 0`, valid trail
   parameters, positive exact bounds, and valid tick/scale authority. Derived arithmetic uses
   `Fraction` and one final upward valid-tick conversion. The hard-bail candidate must remain
   strictly below average cost; activation cannot occur below the approved gain.
9. After accepted execution truth, armed hard bail becomes first candidate or
   `max(previous, candidate)` and never loosens. `FLOOR_ONLY` activation recomputes from current
   basis. Once activated, later economics never deactivates the trail. If formula authority becomes
   unavailable, the economic state still advances; positive long remains restricted `HARD_BAIL`
   and no stale candidate may trigger or authorize a goal.
10. Market evidence carries exact scope/source/session/occurrence identity, source sequence/time,
    explicit evaluation time, market epoch, kind, and exact price/tick data. Eligibility is derived
    inside the reducer: positive aligned prices, non-crossed quote, freshness, non-regression,
    session/halt epoch, and step-deviation policy. No wall clock, float, or local-receive identity
    participates in authority.
11. Hard-bail evidence is evaluated before activation/trail evidence and remains sticky until
    proven flat. Trigger corroboration requires two distinct consecutive eligible bids with strict
    source-sequence advance when present, or a distinct fresh trade-plus-bid pair inside the
    versioned window. Replay/restart delivery is an evidence no-op. Trigger changes reset the
    relevant branch so old observations cannot gain retroactive authority.
12. Eligible best bids maintain monotone high water. One eligible best-bid occurrence at or above
    the current activation price activates the trail; this follows the accepted singular favorable-
    evidence clause, while eligibility still enforces stable identity, freshness, sequence/time,
    tick, quote, session, and step-deviation checks. After activation, independently available
    percentage, ATR, and structure candidates are exact/tick-rounded; unavailable components are
    omitted. Trail candidates round upward to the first valid tick so the implementation cannot
    silently loosen protection. The trail is `max(previous, candidates)`, never decreases, and
    commits before its higher trigger can be evaluated.
13. The reducer emits at most a typed `ExecutionGoal` for `EXIT_NORMAL` or `HARD_BAIL`, bound to
    current execution/protection commitments, exact SELL residual, mandate/session, urgency,
    deadline, and the normal/emergency guard. It emits none while waiting, flat, nonpositive,
    overfilled, stale, or otherwise non-serving.
14. `ExecutionGoal` is policy data, not broker authority. Any later effect must still enter through
    public M1C `BrokerEffectRequest -> CreateBrokerEffect -> ClaimEffect`, which rechecks current
    execution, venue uncertainty, mode, kill, fence, budget, residual, and optional scoped grant.
    WO-0148 adds no positive serving-state, grant, claim, dispatch, or broker capability.
15. WO-0149 owns acquisition-mandate binding, BUY creation integration, and cross-side preemption.
    WO-0148 must expose the complete protection contract it needs but may not create or claim BUYs.

### Bounded resolutions of underspecified data/executor choices

- M1.4 consumes optional exact ATR and structure candidates as already validated market-policy
  inputs. It does not choose Wilder versus simple ATR, bar correction, warm-up, or session-boundary
  semantics; those remain unavailable/omitted until a later data work order selects and proves one.
- Normal and emergency guards are immutable typed policy authorities retained in the mandate and
  goal. M1.4 does not reinterpret them as a static floor or choose broker child-price mechanics;
  M3 must select and prove the liquidity-relative representation before effect translation.
- Therefore WO-0148 proves trigger/state/goal policy, not end-to-end child-price enforcement. An
  opaque `economic_scope` is not evidence that a guard was enforced.

## Allowed paths

```yaml
allowed_paths:
  - app/execution_core/protection.py
  - app/execution_core/identity.py
  - app/execution_core/venue.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_protection.py
  - tests/execution_core/test_protection_stateful.py
  - tests/execution_core/test_import_boundary.py
  - work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md
  - work/completed/keep/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md
  - work/review/REV-0050/**
  - work/ledger.jsonl
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/log.md
activation_only_paths:
  - README.md
  - docs/04_IMPLEMENTATION_PLAN.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
```

Everything else is forbidden unless this work order is explicitly re-gated. In particular, do not
edit `fills.py`, `position.py`, `recovery.py`, `values.py`, `authority.py`, accepted ADR bodies,
staged packet records, the retirement manifest, incumbent `app/protection.py`, stores, events,
broker/adapter, API/UI, runtime, configuration, or CI workflows.

### Scope-check boundary

The activation commit is an immutable eight-path exception: this new work order, the three
`activation_only_paths`, the three PKL paths, and one append-only ledger reconciliation. After that
commit, every implementation scope check uses its exact SHA as base and the standard checker over
`allowed_paths`. Activation-only files may not change again inside the implementation range.

## RED-first proof obligations

- `test_protection.py`: exact immutable mandate/public-capability seal; formula boundary table;
  first-fill arm and execution-first updates; pending-basis/incompatible-tick fail-closed behavior;
  trigger/guard separation; hard-bail priority/stickiness; activation/watermark/trail ratchets;
  distinct evidence and replay/restart negatives; wait preservation/release; safe flat and late-BUY
  recovery; goal binding; overfill/nonpositive refusal; M1C denial composition.
- `test_protection_stateful.py`: separate bounded `ProtectionEconomicsMachine` and
  `ProtectionMarketMachine`, each replaying every input from the same predecessor and comparing
  against a test-only slow oracle that does not call the production classifier/reducer.
- Generated histories include AR-06 through AR-09, formula/tick incompatibility, basis loss and
  restoration, above-trigger interruption, sequence/time regression, halt/reopen epoch, missing
  ATR/structure components, trigger ratchet branch reset, venue-book rollback/substitution, and
  current-execution mismatch.
- Import/public-surface pins fail if protection gains a clock, I/O, incumbent dependency, dynamic
  import, operational authority constructor, raw venue-closure seam, or second public transition
  path.

## Required mutation controls

At minimum kill and restore mutants that: round either candidate downward; loosen armed trigger or
trail; let activation/trail outrank hard bail; count a duplicate occurrence twice; accept a
non-advancing sequence; reuse observations after trigger change; trust a caller closure flag;
release `OPEN`/`INVALIDATED`; erase `EXIT_NORMAL` while waiting; mark quantity zero flat with a live
attempt; leave late positive quantity flat; reuse stale formula authority; emit an overfill goal;
or bypass M1C kill/fence/final-claim gates. Record exact command, expected failure, actual failure,
restoration, and restored hash for each group.

## Review and completion gates

1. Freeze the complete RED contract before production implementation and obtain a fresh independent
   test-contract review with zero P0/P1. A platform interruption before findings is not a verdict.
2. Implement from the accepted RED freeze with one semantic writer. Same-lifecycle findings are
   fixed at the owning invariant; a second defect at one edge triggers a bounded redesign/re-gate,
   not another local patch.
3. Pass focused deterministic/stateful suites, ruff check/format-check, Python 3.11 static target,
   import graph/AST/public-surface checks, R2 oracle, work-order scope/disposition/ledger/PKL checks,
   full repository tests, and raw branch-coverage floor.
4. Freeze an exact candidate and submit `REV-0050` to an independent fresh model. Resolve every
   P0/P1 and rerun every affected gate. The implementation seat cannot self-accept.
5. Reconcile the active WO to `work/completed/keep`, append the ledger, and update PKL without an
   evidence-only successor after external success. Push the immutable closeout and require unchanged
   exact-head Python 3.11/3.12 CI before `WO-0149` activation.

## RED contract freeze

The failure-first contract is frozen from activation SHA
`d75806b1a79d1769db25ae962c0977cd9388a886`. The public vocabulary selected for this bounded slice
is explicit rather than inferred: `MarketDataSourceId`, `MarketOccurrenceId`, `EvidencePolicy`,
`ExecutionGuard`, `ProtectionMandate`, `MarketOccurrence`, the five protection-policy values, typed
disposition/urgency/alert values, opaque `PositionProtectionState` and
`ProtectionVenueProjection`, immutable `ExecutionGoal` and `ProtectionTransition`, and exactly
three public entry points: `project_protection_venue`, `initialize_position_protection`, and
`reduce_position_protection`. Times/deadlines are non-negative exact integers; guard policy
commitments and all retained commitments are exactly 32 bytes. These choices are now the M1.4
interface that WO-0149 may consume; they do not authenticate an operator or grant execution.

The venue seam is likewise frozen before production code. Every reducer-constructed
`VenueRecoveryTransition` must retain a private domain-separated proof over exact predecessor and
resulting execution checkpoints, bounded all-effect and BUY-effect authority summaries, command
and disposition, reducer-derived quantity delta, and a per-position-scope monotone cursor. A
state-mutating `APPLIED` or `RECONCILIATION_REQUIRED` transition advances that scoped cursor;
`EXACT_REPLAY`, refusal, conflict, or a non-mutating reconciliation result does not. Protection
accepts only a projection extracted from this proof, requires its predecessor to match the state
it already retained, and recomputes the seal before use. Counts without the cursor are
inadmissible because sibling forks and equal-count ABA histories can otherwise look current.

Fresh RED evidence before any production implementation:

- `python -m pytest --collect-only -q` over the deterministic, stateful, and import-boundary files
  collected 76 tests: 61 deterministic examples, two bounded generated-history machines, and 13
  import/public-boundary tests.
- The same focused run produced exactly 67 expected failures and nine existing boundary passes.
  Every failure traced to the deliberately absent `app.execution_core.protection` semantic center
  or the boundary inventory/export delta caused by that absence; there was no collection error.
- Ruff check and format-check passed for all three changed test files; `git diff --check` passed.
- Hostile pre-build review added direct proof forgery, sibling-fork, exact-replay, equal-count ABA,
  rollback/substitution, all-effect flatness, correction/bust, pending-basis, overfill, trigger
  reset, optional-component, emergency-wait, and late-positive recovery controls. Production work
  remains barred until an independent reviewer accepts the frozen RED commit with zero P0/P1.

### Independent RED review and second freeze

A fresh independent Sol review reproduced the first freeze at `0271f0f5c398` and returned `BLOCK`
with thirteen P1 test-contract gaps. The findings were test-strength findings, not production
defects: generated histories were too shallow; the venue seal omitted command/disposition/delta
and predecessor-summary mutation pins; cursor tests did not isolate per-position scope or every
non-advancing outcome; the no-scan test could miss private traversal; flatness omitted account
reconciliation; late-positive recovery omitted correction/bust; post-activation economics were not
exercised; market eligibility, corroboration-window, and activation edges were incomplete; exact
value validation and goal binding were partial; and the M1C example never reached final claim.

The second freeze closes those findings at their owning boundaries:

- deterministic tests now authenticate the complete transition envelope, donated-proof rejection,
  predecessor/current summaries, per-position cursor interleaving, exact replay/refusal/conflict/
  non-mutating-reconciliation cursor behavior, constant-work map access, and AST-forbidden raw
  ledger traversal;
- zero-quantity account reconciliation, late ordinary BUY plus late correction/bust restoration,
  fill/correction/bust after trail activation, pending/incompatible formula authority, and exact
  all-effect flatness are separate failure-capable examples;
- exact-type/range/commitment validation, freshness/quote/time/step/tick/session/epoch edges,
  both trade-bid orders at the exact corroboration-window boundary, and the exact rounded
  activation edge are pinned without conflating eligibility causes;
- generated histories now cover revision/bust/restoration, incompatible tick loss/restoration,
  projection substitution, stale rollback, flat/late-positive recovery, duplicate/non-advancing/
  max-step evidence, halt/reopen epochs, optional trail inputs, and normal-exit wait/release; and
- goals now carry complete current policy bindings and are translated through genuine M1C create
  and final-claim denial checks for kill and reconciliation fence, without claiming that opaque
  economic scope authenticates the guard.

Fresh second-freeze evidence: collection succeeds for 169 focused tests (154 deterministic, two
state machines, and 13 import/public-boundary tests). RED execution yields 160 expected failures and
nine existing boundary passes; every failure is caused by the deliberately absent protection module
or its required export/import-boundary delta. Ruff check and format-check pass, `git diff --check`
passes, and direct pure venue probes validate the new cross-symbol, non-mutating reconciliation,
zero-quantity account-reconciliation, closed-parent revision, and tick-restoration fixtures.
Production remains barred until a fresh independent review accepts this second freeze with zero
P0/P1.

### Independent second-freeze review and third freeze

A second fresh Sol review re-derived the RED contract at
`9ceae2aa5cbf0cc69af2a082ec6598e86bcbae65`. It found no P0 and fourteen P1 test-strength gaps.
The gaps concerned exact public shape, state/projection authenticity, cursor anchoring, bypassable
constant-work inspection, positive overfill and mandate caps, formula loss/restoration, sticky
post-activation economics, market-kind ownership, evaluation-time monotonicity, optional trail
validity, all-effect SELL uncertainty, complete commitment sensitivity, and isolated rather than
composed generated histories. They were not production defects; production remained absent and
barred throughout the re-gate.

The third freeze closes each review class at its owning boundary:

1. Every reducer-owned state field, projection field, and retained venue-transition proof input is
   individually mutated; unauthentic state or projection is `REFUSED` with no goal or alert.
2. The public module exports only the frozen vocabulary and three functions. Enum members are
   exact: `MarketKind(BEST_BID, TRADE)`,
   `ProtectionPolicy(FLOOR_ONLY, TRAIL_ACTIVE, EXIT_NORMAL, HARD_BAIL, FLAT)`,
   `ProtectionUrgency(NORMAL, EMERGENCY)`,
   `ProtectionDisposition(APPLIED, EXACT_REPLAY, STALE, REFUSED)`, and
   `ProtectionAlert(LATE_POSITIVE_AFTER_FLAT)`.
3. Frozen public fields are exact: `EvidencePolicy(source_id, max_age, corroboration_window,
   max_step_fraction)`; `ExecutionGuard(guard_id, policy_commitment)`;
   `ProtectionMandate(mandate_id, position_scope, session_id, configuration_version,
   loss_fraction, approved_gain, percent_trail_fraction, atr_multiple, tick, normal_guard,
   emergency_guard, evidence_policy, maximum_quantity, maximum_goal_rate, deadline)`;
   `MarketOccurrence(occurrence_id, source_id, position_scope, session_id, market_epoch,
   source_sequence, source_time, evaluation_time, kind, best_bid, best_ask, trade_price,
   atr_distance, structure_trail, halted)`; `PositionProtectionState(policy, mandate,
   raw_quantity, execution_commitment, formula_available, armed_hard_bail_trigger,
   activation_price, high_watermark, trail, waiting_buy_resolution, commitment)`;
   `ProtectionVenueProjection(predecessor_cursor_ordinal, predecessor_cursor_head,
   cursor_ordinal, cursor_head, predecessor_execution_commitment, execution_commitment,
   predecessor_blocking_effect_count, predecessor_blocking_buy_effect_count,
   blocking_effect_count, blocking_buy_effect_count, predecessor_execution_binding_matches,
   execution_binding_matches, predecessor_account_reconciliation_clear,
   account_reconciliation_clear)`; `ExecutionGoal(side, residual, urgency, guard, deadline,
   session_id, mandate_id, maximum_goal_rate, execution_commitment, protection_commitment)`; and
   `ProtectionTransition(state, disposition, goal, critical_alert)`. Public value classes expose no
   behavioral or broker-mutating surface.
4. Refusal, conflict, replay, and non-mutating reconciliation are anchored to the exact current
   venue cursor. They are `EXACT_REPLAY` at that cursor and become `STALE` after a genuine advance.
5. The constant-work oracle walks the extractor's transitive venue-local call graph and rejects raw
   ledgers, private radix roots, dynamic or aggregate iteration, non-map method indirection, loops,
   comprehensions, and recursion, in addition to comparing bounded-map access counts across small
   and large books.
6. Authentic positive overfill retains economics but is quarantined; residual above
   `maximum_quantity` is never truncated or emitted. Favorable and emergency-shaped evidence both
   remain non-serving `HARD_BAIL` with no goal.
7. Loss of exact formula authority discards stale market evidence. Restoration recomputes exact
   formula state but requires a fresh corroboration branch before any goal.
8. Economics after trail activation may tighten hard-bail authority but cannot deactivate or
   loosen the trail; later correction or bust cannot undo the tightened trigger.
9. `BEST_BID` owns exactly bid/ask payload and may activate, ratchet, or trail-exit. `TRADE` owns
   exactly trade price and may only corroborate hard bail with a distinct eligible bid; it cannot
   activate, ratchet, or satisfy trail exit.
10. Evaluation time is nondecreasing for one source/scope/session/epoch stream, equality is
    allowed, regression is inert, and `source_time <= evaluation_time` remains required.
11. Exact percent, ATR, and structure candidates compete independently. Invalid optional ATR or
    structure data omits only that candidate, grants no trail authority, and cannot suppress valid
    hard-bail or percent-trail behavior; non-unit tick rounding and structure dominance are exact.
12. Any unresolved owned SELL suppresses both normal and emergency goals through terminal leg
    state; only exact parent closure releases a goal with the correct guard.
13. Protection and goal commitments change with mandate/session/configuration, every formula and
    evidence-policy parameter, tick, guard, quantity/rate/deadline, execution quantity/economics,
    and exit provenance.
14. Revision/bust/restore, incompatible-tick loss/restore, epoch interruption/reopen, and unresolved
    BUY terminal/parent closure now advance the same generated machine histories. A structural pin
    prevents those high-risk rules from regressing into isolated `_start` scenarios.

The bounded resolutions used by this freeze are: state/projection forgery fails closed; a residual
above the mandate maximum is not a partial-goal authority; invalid optional trail components are
omitted rather than poisoning independent valid candidates; evaluation time may equal but not
precede the retained evaluation time; and non-advancing venue outcomes are current replay until a
real cursor advance makes them stale. These are clause clarifications inside the accepted ADRs,
not new architecture or runtime authority.

Fresh third-freeze evidence: collection succeeds for 213 focused tests (197 deterministic, two
state machines, one composition-strength pin, and 13 import/public-boundary tests). Exact RED
execution yields 203 expected failures and ten passes; all failures are the deliberately absent
protection module or its required export/import-boundary delta, with no collection or unrelated
failure. Ruff check and format-check pass, `git diff --check` passes, and the activation-base scope
check reports `SCOPE CHECK PASSED`. As a hostile preservation pre-flight, all 698 pre-existing
execution-kernel tests outside the deliberately RED import/protection files pass. Production
remains barred until a new independent review accepts the exact third-freeze commit with zero
unresolved P0/P1.

### Independent third-freeze review and fourth freeze

A third fresh Sol review independently re-derived the exact RED commit
`235fe9ffb64304b82f52672118a1eac3559072d8`. It found no P0 and returned `BLOCK` with eight P1
test-strength findings. Production remained absent and barred. The findings were that inherited
public capability could escape the value-object seal; saved replay and non-mutating projections
were not proven stale after a genuine later advance; callable aliases could escape the
constant-work call graph; later BUY economics did not cross the mandate-cap and broker-overfill
boundaries; evaluation-time authority was not proven to reset and then remain monotone inside a
new market epoch; an `INVALIDATED` SELL was not pinned as an all-effect blocker; commitment
sensitivity omitted position scope and independently varied guard/tick leaves; and the generated
history pin did not prove Hypothesis rule registration, reachability, or execution.

The fourth freeze closes each finding through a failure-capable owning-boundary control:

1. The public-value seal walks the complete static MRO and detects inherited methods and
   descriptors, including a dedicated inherited broker-capability mutant.
2. Exact replay and non-mutating reconciliation projections first reduce as current
   `EXACT_REPLAY`; a verified same-position cursor/head advance then makes the saved projection
   `STALE` without changing current protection state.
3. The constant-work oracle resolves the transitive venue-local call graph and defaults unresolved
   local, default-argument, closure, callable-object, and opaque targets to failure. Five synthetic
   bypass forms prove the oracle is failure-capable while the runtime bounded-map access comparison
   remains intact.
4. A real later owned BUY crosses both boundaries from an initially serving state: aggregate
   quantity above the mandate cap remains exact and non-serving, and broker-authoritative quantity
   above the effect capacity retains `OVERFILL_QUARANTINE`. Favorable and emergency-shaped market
   histories cannot emit a goal after exact parent closure.
5. A halt/new-epoch history accepts a lower first evaluation watermark for the new epoch, rejects
   an evaluation-time regression inside that epoch, and accepts a later monotone occurrence as the
   second fresh corroborator.
6. Both normal and emergency SELL-blocking histories now continue after apparent release into a
   late discovered leg and `INVALIDATED` parent. The all-effect summary blocks the goal without
   rewriting the retained exit policy.
7. Commitment sensitivity now varies `PositionScope`, each normal/emergency guard identity and
   policy-commitment leaf, every evidence-policy leaf, and all other retained mandate/execution/
   exit inputs. Separate same-execution non-serving controls independently vary tick units and
   scale so nested tick authority cannot hide behind an execution-commitment change.
8. The generated-history control discovers actual Hypothesis `Rule` registrations, requires live
   preconditions, and invokes the registered functions. One economics history composes
   correction/bust/restore with incompatible-tick loss/restore; one market history composes an
   unresolved BUY with halt/reopen hard bail, leg terminality, and exact parent-close release.

Fresh fourth-freeze evidence before any production implementation:

- focused collection succeeds for 229 tests: 212 deterministic examples, two registration/
  directed-composition controls, two bounded state machines, and 13 import/public-boundary tests;
- exact RED execution yields 213 expected failures and 16 passes. The only failure classes are the
  deliberately absent `app.execution_core.protection` module and the required protection export,
  module-inventory, and import-boundary deltas; the seven new pre-production meta controls pass;
- Ruff check and format-check pass for both protection test files, `git diff --check` passes, and
  the activation-base work-order scope check reports `SCOPE CHECK PASSED`;
- direct pure venue probes pass for the alternate-position fixture and both later-BUY cap/overfill
  histories through exact parent closure; and
- the hostile preservation pre-flight remains green: all 698 predecessor execution-kernel tests
  outside the deliberately RED protection/import files pass in 179.60 seconds.

The fourth freeze adds no production code or runtime authority. Production remains barred until a
fresh independent reviewer accepts the exact immutable fourth-freeze commit with zero unresolved
P0/P1.

### Independent fourth-freeze review and fifth freeze

A fresh Sol reviewer independently re-derived exact fourth-freeze commit
`fa737f446d746e19bef40c0fbe6f33a80595cf1d`. It found no P0 and returned `BLOCK` with four P1
test-strength findings. Production remained absent and barred. The findings were that the public
value seal ignored capability-bearing special methods; the constant-work oracle trusted every
method named `get`; the later-BUY cap/overfill negative did not first prove its exact predecessor
could serve a goal; and position-scope commitment sensitivity was confounded by changing the
execution commitment at the same time.

The fifth freeze closes each finding at the failure-capable test boundary:

1. The complete-MRO public-value seal now also rejects inherited `__call__`, dynamic lookup,
   descriptor, indexing, and iteration hooks. A mutant with inherited callable and `__getattr__`
   broker-capability escape is detected without invoking it.
2. The constant-work oracle now permits `.get` only on the three exact bounded protection map
   fields. A global `SlowGetter.get` mutant that hides an input-ledger materialization is rejected
   by the same method-call classifier used against the production extractor.
3. Both later-BUY boundaries now branch the identical closed-parent pre-BUY state and projection
   through their supplied favorable or emergency market histories and prove the expected normal or
   emergency goal before applying the BUY that crosses the mandate cap or broker overfill.
4. A same-execution exact-replay control changes only the retained mandate `PositionScope`; every
   other mandate field, execution commitment, and raw quantity remains identical. The forged state
   must be `REFUSED` unchanged with no goal or alert.

Fresh fifth-freeze evidence before any production implementation:

- focused collection succeeds for 231 tests: 214 deterministic examples, two stateful meta
  controls, two bounded state machines, and 13 import/public-boundary tests;
- exact RED execution yields 214 expected failures and 17 passes. The only failure classes remain
  the deliberately absent protection module and required export/module/import-boundary deltas; all
  eight pre-production meta controls pass;
- Ruff check and format-check pass, `git diff --check` passes, both changed protection test files
  parse at the Python 3.11 grammar target, and the activation-base scope checker reports
  `SCOPE CHECK PASSED`;
- the hostile preservation pre-flight remains green: all 698 predecessor execution-kernel tests
  outside the deliberately RED protection/import files pass in 186.84 seconds; and
- no Python 3.11 interpreter is installed locally, so actual 3.11 execution remains an exact-head
  CI obligation rather than a local acceptance claim.

The fifth freeze still adds no production code or operational authority. Production remains barred
until a fresh independent reviewer accepts its exact immutable commit with zero unresolved P0/P1.

### Independent fifth-freeze review and seventh freeze

A fresh Sol review independently attacked exact fifth-freeze commit
`4daf322e67b5cf433be5552976c63209a8d873d2`. It found no P0 and six P1 oracle-bypass classes:
unsafe type truth/equality and hidden function metadata in lifecycle validation; custom-metaclass
equality/hash spoofing; replaced dataclass slot descriptors; enum-member capability payloads;
extractor helper/wrapper/aggregate/descriptor escapes; and private-field/enum-representation
overfitting. Production remained absent and barred while each class was repaired.

Two fresh read-only audits then attacked the repaired worktree before it was frozen. They found no
P0 and four further P1 classes: venue-local rebinding of the trusted bounded-map `get`; arbitrary
`<string>` code impersonating dataclass-generated freeze methods; source-location forgery causing
the lifecycle AST oracle to inspect benign text while different bytecode executed; and executable
or forged dataclass annotations, documentation, field tables, and frozen parameters. Those audits
also raised two P2 design cautions: positively pin every accepted inert enum payload type, and avoid
mistaking the selected three-map venue projection for an ADR-level universal representation.

The seventh freeze closes every P1 at the owning proof boundary:

1. Passive-value dispatch is identity-only. Exact built-in slot descriptors are pinned before any
   field read, custom metaclasses cannot reach equality/hash protocols, enum class/member state is
   sealed, and arbitrary private implementation fields remain recursively capability-checked.
2. Dataclass annotations, documentation, exact field/parameter metadata, slots, match arguments,
   defaults, and generated methods are verified before `dataclasses` helpers can traverse them.
   Generated behavior must match a fresh same-shape interpreter reference, including executable
   code and closures; forged mutable dataclasses and forged freeze methods are direct mutants.
3. Lifecycle functions have no defaults, closures, decorators, attributes, or capability-bearing
   annotations. Their executable bytecode must match the inspected source before the sequential
   exact-type validation grammar is accepted. A source-location/code-swap mutant proves this gate
   can fail without first executing its payload, while a valid sequential lifecycle remains green.
4. The extractor is exactly one cached position-scope key plus three direct bounded-map reads in
   fixed semantic order. Helper, wrapper, aggregate, descriptor, alias, and rebinding mutants fail.
   The imported `_PersistentKeyMap` has exact canonical identity; venue source cannot alias, capture,
   mutate, dynamically recover, or module-qualify the class; and its `get` bytecode is tied to the
   canonical `fills.py` source before access counts are measured.
5. Plain and string enums remain representation-neutral within the exact inert payload set. Direct
   positive controls cover `bool`, `bytes`, `int`, `str`, `Decimal`, `Fraction`, and `None` so a
   future narrowing mutation fails.

The three-map extractor shape is retained deliberately as the smallest non-duplicative extension:
M1B already owns the authority-summary and execution-binding indexes, and M1D adds only the scoped
protection cursor. A new aggregate projection map would duplicate those semantic sources and add a
second synchronization invariant. This is an implementation freeze, not an ADR claim that every
future bounded projection must use three maps.

Fresh seventh-freeze evidence before any production implementation:

- focused collection succeeds for 245 tests;
- exact RED execution yields 207 expected failures and 38 passes; the only error lines are the
  deliberately absent `app.execution_core.protection` module and its resulting import failure;
- all 37 passive-seal and constant-work meta controls pass, including every new negative mutant;
- Ruff check and format-check pass, `git diff --check` passes, the protection test parses at the
  Python 3.11 grammar target, and the post-activation scope checker reports `SCOPE CHECK PASSED`;
- the canonical bounded-map source/provenance check passes independently of the absent production
  module; and
- no Python 3.11 interpreter is installed locally, so actual 3.11 execution remains an exact-head
  CI obligation rather than a local acceptance claim.

The seventh freeze adds no production code, database/broker/runtime activity, or operational
authority. Production remains barred until a fresh independent reviewer accepts its exact immutable
commit with zero unresolved P0/P1.

### Independent seventh-freeze review and eighth re-gate

A fresh Sol seat independently reviewed exact seventh-freeze commit
`83b0a3ae4c3bb4ab32239b03e41e40b6bb4d6ce9` over `d75806b..83b0a3a`. It confirmed that
production remained absent, found no P0, and returned `BLOCK` with nine P1 test-contract gaps:

1. The canonical bounded-map getter was tied to its own source and bytecode but not to the exact
   identity and executable provenance of transitive globals such as `_child_at`.
2. The lifecycle grammar allowed a nested exact-slotted execution-core class without proving that
   class's own attribute-access behavior passive.
3. The three public protection entry points were pinned by source syntax but not by exact runtime
   identity, inert function metadata, source/bytecode correspondence, or post-definition rebinding.
4. No-access lookalikes did not yet prove exact argument-type rejection before every public-boundary
   field read.
5. Reducer-authenticity mutation changed only one representative nested leaf rather than every
   independently retained dataclass/tuple authority leaf.
6. A stable market-occurrence identity could be reused with changed payload and an advancing or
   absent source sequence without a direct equivocation control.
7. Corroboration-window controls advanced source and evaluation clocks together, leaving the owning
   time authority ambiguous.
8. No control proved that a trail tightened by an occurrence governs that same occurrence before
   trigger evaluation.
9. No composed normal/emergency exit history proved exact residual rebinding after partial SELL
   economics and final venue-parent closure.

The review also raised two P2 record/design cautions. The recorded `245 collected / 207 failed /
38 passed` command covers `test_protection.py` alone; the complete three-file focused contract
collects 262 and yields 214 expected failures / 48 passes while production is absent. The exact
two-statement extractor remains a deliberately temporary implementation freeze and is not promoted
to an ADR-level representation rule.

These are oracle findings, not production findings and not a goal-level blocker. Production remains
barred. The implementation seat will repair all nine P1s at their owning test/provenance boundaries,
record both narrow and complete-focus evidence precisely, freeze a new exact commit, and obtain a
new independent zero-P0/P1 review before any production edit.

### Eighth RED repairs and hostile pre-flight

The implementation seat closed all nine seventh-freeze P1s at their owning test boundaries without
adding production code:

1. The bounded-map oracle now authenticates the exact identity, inert metadata, inspected source,
   and bytecode correspondence of every executable transitive global used by `get`, while admitting
   only an explicit exact set of inert external constants.
2. Lifecycle validation now rejects a nested guarded type with custom `__getattribute__` or
   `__getattr__` before any payload access; exact passive nested values remain accepted.
3. Each public entry point now has one exact canonical runtime function binding, inert metadata,
   exact annotations/signature, no wrapper/rebinding/closure/defaults/function attributes, and
   matching inspected source and bytecode.
4. Every non-`None` accepted public argument type must retain an unconditional, source/bytecode-
   authenticated terminal `TypeError` subclass seal, `NoneType` is pinned independently, and every
   argument position rejects a hostile unrelated lookalike before any instance or type protocol.
5. State and projection authenticity now mutate every independently retained scalar, enum,
   dataclass, tuple, frozenset, and empty-container leaf exactly once with deterministic collision
   fallback, while independently proving one changed path and preserving the opaque venue book.
6. Reusing one occurrence identity with changed payload is refused for advancing and absent source
   sequences across bid and trade kinds.
7. Bid/trade corroboration is proven to use source time, not evaluation time, in both arrival orders
   and on both sides of the inclusive window boundary.
8. A newly tightened ATR- or structure-owned trail governs the same occurrence that tightened it.
9. Normal and emergency exit histories prove that partial SELL economics rebind the next goal to the
   exact residual only after exact leg and parent closure.

The bounded simplification pass removed redundant sibling/container assertions from the exhaustive
leaf-walker meta-test. Its independent expected-path inventory, exact cardinality, stable-order pin,
exact root-type pin, and `changed_leaf_paths == {path}` oracle retain the same completeness and
one-leaf locality proof.

Fresh eighth-candidate evidence on local Python 3.12.13:

- the complete focused contract collects 282 tests: 265 deterministic protection, 4 stateful, and
  13 import-boundary tests;
- exact RED execution yields 227 expected failures and 55 passes: 224 failures are caused solely by
  deliberate absence of `app.execution_core.protection`, and 3 are the required module-inventory,
  AST-import, and public-export deltas; no oracle helper fails;
- eight selected provenance, no-access, lifecycle, exhaustive-leaf, and bounded-map meta controls
  pass independently;
- the unchanged execution-core predecessor corpus passes all 698 tests with the three new protection
  files excluded; and
- a fresh hostile Sol pre-flight first reproduced one subclass bypass in the unrelated-lookalike
  matrix, then accepted the unconditional all-argument-type seal repair with no remaining P0/P1.

Actual Python 3.11 execution remains an exact-head CI obligation. This pre-flight is not the required
independent exact-commit RED acceptance. Production remains absent and barred until the eighth
candidate is frozen and a fresh independent seat accepts that immutable commit with zero P0/P1.

### Independent eighth-freeze review and ninth re-gate

A fresh Sol seat independently reviewed exact eighth RED commit
`7beda3f61e4d44f035143e883d7efa35a424f661` against activation base
`d75806b1a79d1769db25ae962c0977cd9388a886`. It reproduced the complete focused RED
classification, all 698 predecessor tests, static/format/grammar/diff/scope gates, and accepted ADR
digests. Production remained absent. The reviewer found no P0 and returned `BLOCK` with two P1
test-contract gaps:

1. A restart replay with the same adapter-stable source occurrence and changed local evaluation
   context was proven not to corroborate, but was not required to be `EXACT_REPLAY` with byte-for-
   byte unchanged state. It could therefore advance a retained evaluation watermark and suppress a
   later valid occurrence. Accepted ADR-021 makes the changed local context an evidence no-op, not
   source-payload equivocation.
2. The purity scanner rejected I/O modules and several effectful calls but allowed direct `print`
   and nested `sys.stdout.write`; the future pure reducer could emit observable output without
   failing the RED boundary.

Both findings are accepted and repaired at their owning oracle:

- the restart history now pins `EXACT_REPLAY`, complete state/commitment equality, no goal/alert,
  and a valid advancing successor whose evaluation time lies between the original and replay
  delivery contexts; and
- a package-wide AST effect detector rejects effectful builtins, forbidden modules, imported
  aliases, dynamic call targets, and stream capabilities. A protection-specific positive capability
  model accepts only exact builtin, local, imported, attribute-call, decorator, base-class, and
  callback bindings from an exact top-level import manifest. It rejects module, nested,
  conditional, and duplicate imports; rebinding; fake approved roots; unauthenticated callbacks;
  implicit imported protocols; mutable or dynamic attribute access; and dynamic type construction.
  Runtime capture independently requires each public entry point to leave stdout and stderr empty.

The remediated complete focus collects 284 tests and yields 228 expected RED failures / 56 passes:
225 failures are caused solely by deliberate absence of the protection module and 3 are its required
inventory/AST/export deltas. The structural mutant matrix and positive skeleton pass; all current
execution-core sources have zero effect-call violations. Ruff check/format-check, Python 3.11
grammar, diff, activation-base scope, and production-absence gates pass. Iterative hostile re-review
found and drove closure of callback donation, fake approved roots, arbitrary relative callables,
conditional import binding, and relative module implicit-protocol paths. Its final current-worktree
verdict is `ACCEPT` with zero P0/P1. The original reviewer result remains unchanged in
`RED-EIGHTH-RESULT.md`; the accepted disposition is separate. Production remains absent and barred
pending a ninth immutable freeze and fresh independent zero-P0/P1 exact-commit acceptance.

## Stop conditions

Stop rather than widen scope if the contract requires an ADR change, a new dependency, persistence,
runtime/broker/credential activity, a positive supervisor/grant mint, direct dispatch authority,
or edits outside the allowed paths. Ordinary RED failures, in-scope findings, compaction recovery,
and a running external CI gate are progress states, not goal blockers.

## Durable campaign checkpoint

- Activation base: `3e39ee6a857ae61d850da1b841e85008b9a59fbb`.
- Predecessor proof: GitHub Actions run `30794934357` (#687), Python 3.11 job
  `91626251701` and Python 3.12 job `91626251758`, both `SUCCESS` at the exact base.
- Closed predecessors: `WO-0145`, `WO-0146`, `WO-0147`; no unresolved accepted P0/P1.
- Active slice: only `WO-0148`; `WO-0149`, M2, runtime, persistence, merge, and deletion inactive.
- Preserved local state: main tracked tree and all registered auxiliary worktrees verified clean;
  retained untracked WO-0145/0146/0147 evidence remains untouched.
- Pre-build clause map: one new protection reducer plus narrow identity, venue projection, exports,
  and two test suites; existing position/authority reducers stay unchanged.
- Current RED state: eighth freeze `7beda3f61e4d44f035143e883d7efa35a424f661` received
  independent `BLOCK` with no P0 and two P1 oracle gaps. Both are repaired at their owning
  invariants. Complete focus is 284 collected / 228 expected RED / 56 pass, predecessor
  preservation is 698 pass, all final static gates pass, and hostile current-worktree re-review is
  `ACCEPT` with zero P0/P1. Production remains absent and barred.
- Next action: freeze the ninth RED candidate and obtain fresh independent exact-commit acceptance
  with zero unresolved P0/P1 before production begins.

### Independent ninth-freeze review and successor re-gate

A fresh Sol seat independently reviewed exact ninth RED commit
`706ed536790179fcb673aaedf96b3b728ee33d3c` against activation base
`d75806b1a79d1769db25ae962c0977cd9388a886`. It reproduced the complete focused RED
classification, all 698 predecessor tests, static/format/grammar/diff/scope gates, accepted ADR
digests, and production absence. It returned `BLOCK` with no P0 and three P1 contract gaps:

1. changed-delivery replay exactness covered only sequenced `BEST_BID`, not both market kinds with
   source sequence present and absent or the full generated between-time-successor composition;
2. pattern-capture names were absent from the binding inventory, permitting a match-capture chain
   to launder runtime output through an approved import; and
3. the purity model did not reject ambient/subscript writes, retained default or closure state, or
   `object.__setattr__` against caller-owned inputs.

All findings are accepted. The successor contract adds the four-cell replay matrix and a registered
generated-history generalization; exhaustive Python 3.11 capture-name inventory; a conservative
write/persistence grammar; and a bounded fresh-allocation proof for straight-line construction of
the two opaque result types. `object.__getattribute__` is removed from the protection allowlist.
Exact reviewer mutants and positive construction skeletons are pinned. A hostile Terra pre-flight
then found and drove closure of one further implicit `with`/context-manager dispatch path, after
which it returned `ACCEPT` with zero P0/P1.

Fresh successor evidence on local Python 3.12.13 is 288 focused tests with 232 expected RED
failures / 56 passes, comprising 229 protection-module-absence failures plus the three required
inventory/AST/export deltas; no helper fails. The unchanged predecessor corpus passes 698/698.
Ruff, format, Python 3.11 grammar, diff, activation-base scope, accepted ADR digest, production-
absence, and eight-file current-source effect gates pass. The exact ninth result remains unchanged;
its accepted disposition is recorded separately in `RED-NINTH-DISPOSITION.md`.

Production remains absent and barred. Next action is to freeze this successor RED candidate and
obtain a fresh independent exact-commit acceptance with zero P0/P1 before production begins.

### Claude clean-room comparator adjudication before successor freeze

The comparator at remote commit `b56ce60043e0609bd73989f8429b573539cedd93` was read with
`git show` and not merged. Its claims were re-derived against current authority and tests. Three
current P1 gaps were accepted:

1. the lifecycle grammar still rejected the exact `Fraction` guard required by clauses 1 and 8
   because `Fraction` has `ABCMeta`;
2. the passive metadata seal still indexed the Python-3.12-only `_DataclassParams.slots` member
   unconditionally, so the declared Python 3.11 CI target could not execute the controls; and
3. optional `None` leaves still mutated only to a wrong-type sentinel, permitting a free exact-type
   rejection rather than proving the declared union/value boundary.

The lifecycle type gate now admits only the exact standard metaclass identities used by ordinary
classes, enums, and `Fraction`, and runs the no-user-attribute-dispatch seal before class metadata
reads. A real `Fraction` sequential guard is an executable RED meta control. Dataclass `slots`
metadata is version-optional while the version-independent exact `__slots__` inventory remains
mandatory. The leaf walker now requires an explicit valid union member for every `None` leaf;
`high_watermark` and `trail` use real `ReportedPrice` alternatives, and missing private optional
coverage fails closed.

The old seventh-freeze `value`-argument collision was reproduced from exact commit `433a5fb` and is
already closed by the current clone receiver name. The executable RED meta control now exercises
same-root-type mutation on real `MandateId`, `PriceUnits`, `ReportedPrice`, and
`VenueRecoveryTransition` values and pins all four nested `ReportedPrice` leaf paths. Current C1
guarded-dispatch and C2 public-entrypoint-provenance repairs were independently rechecked. The
comparator's C3 downgrade is stale against this amended WO's explicit protocol-free rejection
obligation; PEP-562, universal subclass sealing, and proof-removal suggestions remain non-blocking
advisories and do not weaken this re-freeze.

Local execution is Python 3.12.13 and no local Python 3.11 interpreter is installed. Actual 3.11
restoration is therefore not claimed and remains routed to unchanged exact-head CI. Full
adjudication and command evidence are in `CLAUDE-COMPARATOR-DISPOSITION.md`. The complete focus
remains 288 collected / 232 expected RED failures / 56 passes, selected executable meta controls
pass, and predecessor preservation remains 698/698. Production remains absent and barred pending a
fresh immutable successor freeze and independent zero-P0/P1 exact-commit acceptance.

### Bounded successor purity redesign and tenth RED freeze candidate

Three hostile post-comparator passes found a related family of static-oracle gaps: mutable
class/function metadata and defaults; local-helper, callback, or venue-extractor donation; an
opaque-factory right-hand side that could throw after allocation; recursive, looping, or
process-exit control flow; and insufficiently exact opaque class decorators. Because these repeated
at the same purity edge, review gate 2 triggered one bounded redesign rather than another local
exception list. Production remained absent throughout.

The replacement grammar now admits only direct deterministic imports, inert retained literals,
passive enums/dataclasses, finite straight-line/branching functions, and authenticated calls. It
rejects module hooks, mutable containers, defaults/callbacks, callable-as-data aliases, static
metadata reads, dynamic calls/attributes, loops/recursion, suspension, context/try/match machinery,
implicit iteration/unpacking/subscription/membership, and unsupported arithmetic operators. The
venue extractor has one direct call edge owned by `project_protection_venue`; public roles cannot
call one another. Every source-reachable private helper and referenced imported binding is tied to
its canonical source/runtime identity without executing production.

`PositionProtectionState` and `ProtectionVenueProjection` must each be an exact field-only
`@dataclass(frozen=True, slots=True, init=False)` and have exactly one straight-line factory. All
validation/computation occurs before allocation; after allocation, each declared field is written
once from its already-validated same-named parameter and the fully populated local is returned
directly. Exact mutable-class, metadata/default, extractor-role, helper-donation/rebinding,
throwing-RHS, partial-factory, recursion, loop, `SystemExit`, implicit-iteration, dynamic-surface,
and positive-construction controls are executable.

A final Terra attack exposed missing reflected numeric tripwires in the wrong-type sentinel. The
sentinel now covers format, truth, ordering, forward/reflected arithmetic, conversion, indexing,
membership, and iteration. Together with the seven-position public wrong-type matrix and recursive
passive exact-type seals, it proves rejection precedes user protocol dispatch; the Terra recheck
returned `ACCEPT` with zero P0/P1 against the complete two-layer contract.

Fresh local Python 3.12.13 evidence is 290 focused tests with 233 expected RED failures / 57 passes:
230 failures are caused by deliberate protection-module absence and three by the required module-
inventory, AST/import, and package-export deltas; no helper or meta-control fails. The correctly
excluded predecessor corpus passes 698/698. Production `app/execution_core/protection.py` remains
absent. Actual Python 3.11 execution remains deferred to unchanged exact-head CI; no local 3.11 pass
is claimed. The next action is an immutable successor commit and fresh independent tenth RED review
with zero unresolved P0/P1 before any production edit.

### Tenth-review interruption and import-contract successor

The external tenth-review attempt ended before findings were produced because of a platform-level
interruption. It created no `RED-TENTH-RESULT.md`, supplied no verdict, and did not accept exact
candidate `5c5bee9543b78fc2fa8f612c61d75d4fdbf52bae`.

Author reconstruction and two read-only critical pre-flight passes then found five P1 contract
issues and no P0: the exact public surface contradicted the blanket refusal of renamed imports; an
ordinary future-annotations directive retained a public `annotations` name; imported annotation
spellings and optional replacement resolution did not follow the required private bindings; an
explicit annotation string was not tied to its imported name; and the accepted union/container
grammar initially lacked complete positive controls.

The successor repairs the owning contract rather than weakening `__all__`. Public imported names
must use exactly `Name as _Name`; already-private imports remain unaliased; and future annotations
uses `_annotations`. Module and wildcard imports, arbitrary or redundant aliases, duplicates, and
rebinding remain refused. Imported annotations use their retained private names, with exact runtime
expectations for `_VenueRecoveryTransition`, `_ReportedPrice`, `_Decimal`, and `_Fraction`.
Annotation expressions are limited to loaded names, PEP 604 unions, `None`, and exact
`frozenset[...]`, `tuple[...]`, or `type[...]` forms; explicit annotation strings and malformed
ellipsis tuples are refused.

Failure-first evidence reproduced the original import contradiction and the quoted-annotation
case before their respective checker changes. A test-only executable module now proves canonical
private imports retain an exact public surface, while direct controls cover each accepted grammar
branch and every retained refusal. Fresh local Python 3.12.13 evidence is **292 collected / 233
expected RED failures / 59 passes**. Ruff check/format-check, Python 3.11 grammar parsing,
`git diff --check`, all accepted ADR digests, the eight-file current-source effect scan, and
production absence pass. The correctly excluded predecessor corpus passes **698/698** in 157.08
seconds; its sole warning is the pre-existing inability to write `.pytest_cache`, which did not
affect collection or execution.

The final current-worktree critical pre-flight verdict is `ACCEPT`, P0=0/P1=0. That verdict is not
immutable exact-commit acceptance. Production remains absent and barred until the corrected
successor is frozen and a fresh independent functional-conformance review returns `ACCEPT` with
zero unresolved P0/P1.

### Eleventh exact review and tuple-grammar narrowing

Independent review of exact candidate `8d441d6bbbf90c634e073337ea28b2a758070bc4` reproduced the
292-test RED classification, all 698 predecessor tests, and the static evidence. It returned
`BLOCK`, P0=0/P1=1: the grammar accepted the distinct one-element `tuple[T]` annotation form even
though no requirement or production-shaped sample needed it, and removing only that branch left
the owning positive controls green.

The finding is accepted and repaired by narrowing. One-element tuple annotations are now refused
in both `tuple[T]` and runtime-equivalent `tuple[T,]` spellings; accepted tuple annotations are
fixed multi-element tuples and the exact homogeneous `tuple[T, ...]` form. Direct altered-source
controls reproduced each missing refusal before its owning grammar change and pass afterward. The
existing positive construction continues to exercise both retained tuple forms, and the malformed
extra-element ellipsis form remains refused.

Fresh affected evidence is 2/2 focused controls passed, while the complete focus remains **292
collected / 233 expected RED failures / 59 passes**. Ruff check/format-check pass and production
remains absent. A fresh correctly excluded predecessor run passes **698/698** in 172.26 seconds;
its sole warning is the pre-existing inability to write `.pytest_cache`, which did not affect
collection or execution. The exact eleventh result is preserved unchanged in
`RED-ELEVENTH-RESULT.md`; author disposition is separate in `RED-ELEVENTH-DISPOSITION.md`.
Final post-eleventh current-worktree pre-flight is `ACCEPT`, P0=0/P1=0/P2=0; its live expression
matrix passes 6 accepted and 8 refused forms, and independent in-memory restorations prove both
one-item tuple controls can fail. Production remains barred pending a new immutable successor and
fresh independent exact-commit `ACCEPT` with zero unresolved P0/P1.

### Twelfth exact RED acceptance

A fresh independent Sol seat reviewed exact candidate
`0b87a8756d999d81989bb5de1bb895a0ca0d44eb` and returned **ACCEPT, P0=0/P1=0**. It independently
reproduced 292 collected / 233 expected RED failures / 59 passes; 698/698 predecessor tests; the
6/6 accepted and 8/8 refused annotation-expression matrix; separate failure-capable restorations
for both one-element tuple spellings; Ruff, Python 3.11 grammar, diff/scope, accepted-ADR digests,
the eight-file current-source effect scan, all nine auxiliary worktrees clean, and production
absence.

The exact result is `RED-TWELFTH-RESULT.md`. Actual Python 3.11 execution remains deferred to
unchanged exact-head CI. This acceptance authorizes only the next WO-0148 production-implementation
gate; it does not accept production, close WO-0148, activate WO-0149, or authorize runtime,
persistence, broker, credential, database, merge, deletion, or cleanup activity.
