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
- Next action after activation: freeze failure-first tests, independently refute their ability to
  detect wrong implementations, then begin production code only from that immutable RED checkpoint.
