---
type: Work Order
title: "Reset kernel C: trading authority and manual controls"
status: ACTIVE
work_order_id: WO-0147
wave: RESET-M1C
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-08-02
branch: codex/arch-reset-2026-07-r1
base_sha: 7d1c9e5babe5f60bcbbe9e54c6d6dd0bfecf5551
staged_source: work/queue/ARCH-RESET-2026-07/06-roadmap.md#M1--Pure-reference-kernel
predecessor: WO-0146
activation_ci: "GitHub Actions run 30752961917 (#685): Python 3.11 job 91510146946 SUCCESS; Python 3.12 job 91510146979 SUCCESS"
---

# WO-0147 - Reset kernel C: trading authority and manual controls

`[FABLE - FULL - verification: DIRECT + mutation + independent review - task: pure execution authority]`

## Activation and authority

Ameen authorized completing every remaining M1 slice and resolving in-flight findings through a
stable M2-ready milestone. This work order is activated only after immutable predecessor closeout
`7d1c9e5babe5f60bcbbe9e54c6d6dd0bfecf5551` passed unchanged GitHub Actions run #685 on Python
3.11 and 3.12. `WO-0145` and `WO-0146` are closed; `WO-0148` and later work remain inactive.

This slice is pure and unwired. It grants no operational broker authority. Do not discover or use
credentials, call Alpaca Paper, perform broker/network I/O, execute SQL/DDL, initialize or mutate a
database, alter persistence, wire runtime code, merge, or delete/clean any ref, worktree, or
artifact. Existing full-suite fixtures may use only the previously authorized disposable test
SQLite path with `BROKER_ADAPTER=mock`. The prohibited R1 DDL result is inadmissible.

## Goal

Build one deterministic execution-authority semantic center answering whether one exact action may
be admitted, created, or finally claimed now. It owns trading mode, kill/manual controls, a shared
request budget, symbol-wide venue uncertainty, scoped emergency reduction, and atomic final claim.
It does not decide protection or acquisition policy and cannot authenticate a real supervisor.

## Fable gate

```yaml
fable_gate:
  goal: "Implement pure deny-by-default execution authority without operational I/O or persistence."
  assumptions:
    - claim: "The accepted ADRs require one action-aware classifier at admission, creation, and final claim."
      status: VERIFIED
      evidence: "ADR-021 lines 197-215 and the M1 item-3 roadmap contract agree."
    - claim: "M1 cannot honestly authenticate a human, credential, or broker fence."
      status: VERIFIED
      evidence: "M2 persists and hydrates the fence; actual Alpaca Paper origin/account/credential verification and promotion require the later M4/cutover gates in ADR-020/022."
    - claim: "Existing raw effect-request and dispatch-claim exports would bypass the new authority boundary."
      status: VERIFIED
      evidence: "Consumer inventory is confined to the pure venue module and its tests; no runtime consumer requires those public exports."
  approach: "Freeze this activation, write RED examples and three bounded state machines, implement one reducer/classifier with narrow venue hooks, mutate real gates, refactor, then submit an exact freeze to blind review."
  alternatives_considered:
    - "Extend the legacy envelope - rejected because it is frozen evidence and conflates policy, progress, venue state, and authority."
    - "Cache a caller-supplied may_execute boolean - rejected because it becomes stale and mintable authority."
    - "Build clocks, refills, or a token bucket - rejected because M1 needs only deterministic shared-capacity semantics."
  blast_radius: "Only app.execution_core pure source, isolated tests, and WO/review/PKL records."
  rollback: "Revert only WO-0147 commits while preserving both closed predecessor slices and all retained artifacts."
```

## Normative design contract

1. One supported public reducer, `apply_execution_authority_input`, owns admission, effect creation,
   final claim, query claim, and manual-control progression.
2. Raw `RequestedEffect`, `RecordDispatchClaim`, and direct raw venue admission are internal
   capabilities, absent from the package public API.
3. Public initialization is exact `BOOTSTRAPPING + HALTED + UNAUTHENTICATED`, with zero request
   capacity. No public M1 input may enter `ACTIVE`/`REDUCING`, clear kill, replenish budget, issue an
   emergency grant, or grant `PAPER_MUTATION_ELIGIBLE`.
4. Actor, reason, and evidence metadata are attribution only; they never authenticate authority.
5. `ACTIVE` permits otherwise-valid normal work. `REDUCING` refuses exposure-increasing BUY work
   while permitting quantity-capped reduce-only SELL plus cancel/query/reconcile. `HALTED` or kill
   refuses submit, replace, ordinary flatten, and hard-bail SELL; cancel/query/reconcile remain
   eligible. An emergency SELL additionally needs one exact immutable grant.
6. Emergency grants are account/symbol/session scoped, non-stackable, reduce-only, and consumed
   only by the exact successful claim. Ambient, mismatched, reused, or refusal-consumed grants fail.
7. SELL quantity is capped by `PositionState.authorized_residual_sell`; negative raw quantity
   authorizes zero. A stale oversized request is refused, never silently clamped.
8. Final claim reloads canonical authority, exact venue state, exact execution binding, current
   position, mode/kill, uncertainty, budget, and optional grant. The input carries no caller-derived
   authority view, summary, residual, or boolean.
9. Venue claim, one shared-budget debit, and optional grant consumption are one all-or-none pure
   transition. Refusal and exact replay debit or consume nothing.
10. One account request budget covers mutating work and sequenced query/cancel/reconcile claims.
    Normal work cannot cross the safety reserve. Query claims consume capacity but create no effect,
    owner, or venue attempt. Clocks and refill scheduling remain M2.
11. Venue state maintains bounded private per-effect contributions and per-symbol aggregates from
    canonical before/after state, not command kind or disposition. Admission/claim performs no
    audit-history scan. One account-wide unresolved reconciliation count/epoch blocks lazily.
12. A target exemption applies only to the exact `REQUESTED`, unclaimed, ownerless,
    reconciliation-clean target. It cannot exempt sibling safely-local work.
13. Manual flatten atomically stands down exact safely-local BUY work, requests cancellation for
    exact known cancellable BUY legs, treats cancel acknowledgement as nonterminal, waits for exact
    parent `CLOSED`, refuses unknown or potentially-live work, and re-reads residual at final claim.
14. Until WO-0148/0149 supplies policy and the later M4/cutover supervisor gate authenticates the
    Alpaca Paper fence, no normal operational BUY or SELL claim is publicly reachable.

## Allowed paths

```yaml
allowed_paths:
  - app/execution_core/authority.py
  - app/execution_core/identity.py
  - app/execution_core/venue.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_authority.py
  - tests/execution_core/test_authority_stateful.py
  - tests/execution_core/test_import_boundary.py
  - tests/execution_core/test_venue_ownership.py
  - tests/execution_core/test_venue_recovery.py
  - tests/execution_core/test_venue_stateful.py
  - tests/execution_core/test_venue_binding_recovery.py
  - tests/execution_core/test_venue_checkpoint_hardening.py
  - tests/execution_core/test_venue_provenance_hardening.py
  - work/active/WO-0147-reset-kernel-c-trading-authority-controls.md
  - work/completed/keep/WO-0147-reset-kernel-c-trading-authority-controls.md
  - work/review/REV-0049/**
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
edit `fills.py`, `position.py`, `recovery.py`, `values.py`, accepted ADR bodies, staged reset packet
records, the retirement manifest, stores, events, broker/adapter, API/UI, runtime, or CI workflow.

### Scope-check boundary

The activation commit is an immutable seven-path exception consisting of this new work order, the
three `activation_only_paths`, and the three PKL paths above. After that commit, every implementation
scope check uses its exact SHA as the base and the standard checker over `allowed_paths`. Closeout
also inventories the cumulative predecessor-to-target range and requires every path to belong to
the union of `allowed_paths` and `activation_only_paths`; activation-only files may not change again
inside the implementation range.

## RED-first and generated proof obligations

- `test_authority.py`: public-capability seal; deny-only initialization; action x mode x kill x
  grant table; exact residual cap; atomic claim/debit/grant; normal/reserved/query budget boundaries;
  exact grant scope/replay; target-only exemption; manual-flatten progression; no caller-minted view.
- `test_authority_stateful.py` contains three bounded machines rather than one broad model:
  `ClaimAuthorityMachine`, `SymbolGateMachine`, and `ManualFlattenMachine`.
- Every input is replayed from the same predecessor to prove determinism and predecessor immutability.
- A test-only slow symbol oracle independently materializes current views and is compared after every
  generated transition. It must not call the production classifier.
- Composed histories cover both kill/claim orders, `ACTIVE`/`REDUCING`/`HALTED`, stale residual,
  budget reserve, grant/session mismatch, safely-local BUY, claimed-no-leg BUY, cancellable leg,
  cancel acknowledgement, terminal leg with `OPEN` parent, exact closure, and late fill.

## Required live mutation controls

At minimum kill and restore mutants that remove or invert: public-capability sealing; fence, mode,
kill, exact-binding, residual, uncertainty, account-epoch, or budget checks; BUY/SELL asymmetry;
reserved capacity; exact target exemption; terminal-readiness delta; atomic debit/grant consumption;
grant account/symbol/session/one-shot scope; query metering; cancel-ack nonterminality; manual-flatten
unknown-work refusal; exact-type checks; and no-history-scan behavior. Also kill `abs(raw_quantity)`,
`<`/`<=` residual-boundary, caller-supplied boolean/summary, subclass, and boolean-as-integer mutants.

## Evidence and done criteria

- Capture a genuine RED result before production implementation.
- Focused authority/affected-venue suites and all `tests/execution_core` pass.
- Ruff check and format-check, mypy over every execution-core module, six import contracts, AI-OS
  install/version/ledger/PKL/disposition/Fable checks, and exact-scope checks pass.
- Every named live mutant fails decisively before exact source restoration.
- R2 passes 61/61 with `BROKER_ADAPTER=mock`.
- The full repository suite passes the unchanged combined branch-coverage floor using only fresh
  disposable test fixtures; collection/result arithmetic and coverage artifact hashes are recorded.
- `authority.py` stays focused. Crossing roughly 800 lines triggers split review before continuing;
  `venue.py` receives only narrow private seam/index changes.
- Blind reviewer-owned `REV-0049` returns no unresolved P0/P1.
- One immutable final closeout SHA passes exact-head Python 3.11 and 3.12 CI before WO-0148 is
  activated. No post-success evidence-only successor is permitted.

## Stop conditions

Stop and re-gate if operational success requires a public/importable M1 supervisor or grant mint;
if a caller-derived authority view is needed; if correctness needs audit-history scanning; if
persistence, clock/refill, adapter inference, credentials, runtime wiring, protection/acquisition
policy, or another module outside scope is required; if a second defect appears in one lifecycle
edge; if two P0s or three same-root P1s emerge; or if accepted ADR authority conflicts.

## Durable campaign checkpoint

This work order, its RED/FIX/evidence sections, reviewer packet, PKL updates, and immutable commits
are the continuity mechanism across context compactions. After every freeze or review stop, record
the exact SHA, admissible/invalidated evidence, remaining gates, and successor boundary here before
continuing. Conversation memory is never treated as authority.
