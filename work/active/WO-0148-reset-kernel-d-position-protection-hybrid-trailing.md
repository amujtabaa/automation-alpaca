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
- Next action: commit this fourth RED freeze, obtain fresh independent exact-commit acceptance with
  zero unresolved P0/P1, and only then begin production code from the accepted immutable checkpoint.
