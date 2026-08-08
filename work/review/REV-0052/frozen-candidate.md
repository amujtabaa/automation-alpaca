---
type: Work Order
title: "Reset kernel E: acquisition and cross-side integration"
status: DRAFT
work_order_id: WO-0149
wave: RESET-M1E
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-08-05
branch: codex/arch-reset-2026-07-r1
base_sha: 2462fb557172dd28a7475a763eca0b440c0298e3
staged_source: work/queue/ARCH-RESET-2026-07/06-roadmap.md#M1--Pure-reference-kernel
predecessor: WO-0148
activation_ci: "GitHub Actions push run 30996686588 (#693): Python 3.11 job 92275345844 SUCCESS; Python 3.12 job 92275345943 SUCCESS"
implementation_authority: NOT_GRANTED
---

# WO-0149 — Reset kernel E: acquisition and cross-side integration

`[FABLE • FULL • verification: DIRECT • task: pure acquisition and cross-side integration]`

## Activation and authority

This draft may become active only because the immutable predecessor closeout
`2462fb557172dd28a7475a763eca0b440c0298e3` passed unchanged GitHub Actions push run
`30996686588` (#693): Python 3.11 job `92275345844` and Python 3.12 job
`92275345943` both concluded `SUCCESS`. WO-0145 through WO-0148 are therefore effectively
`CLOSED`. Failed run #691 remains negative evidence only and is not an acceptance input.

The activation is documentation/specification only. **No WO-0149 application or test implementation
is authorized by this work order's activation.** A later explicit authorization must name the
implementation and test boundary before a source or test file changes. Until then, no credential
discovery/use, Alpaca or broker activity, network/broker I/O, SQL/DDL, database initialization,
persistent database change, runtime wiring, CI-workflow change, PR/merge, deletion, cleanup,
WO-0150/later activation, or M2 work is allowed. The prohibited R1 DDL incident remains
inadmissible for every claim.

## Goal

Specify one pure, deterministic M1E semantic center that binds an operator-approved BUY acquisition
mandate to one complete approved protection mandate; derives bounded BUY work only through a sealed
authority route; and gives protection a bounded, exact cross-side preemption path. It must make the
first canonical owned BUY fill update acquisition and protection in one sequenced transition while
preserving M1A fill truth, M1B venue authority, M1C final-claim checks, and M1D protection policy.
It creates no broker call, runtime loop, persistent state, or human authentication.

## Context packet

Read only these first:

- `AGENTS.md` and the permanent safety core in `CLAUDE.md`;
- `docs/adr/ADR-020-current-state-execution-kernel.md`;
- `docs/adr/ADR-021-position-protection-liquidity-execution.md`;
- `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md`;
- `docs/adr/ADR-023-bounded-market-occurrence-authority.md`;
- `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`;
- `pkl/project/goals.md`, `pkl/architecture/architecture-map.md`, and `pkl/safety/invariants-rationale.md`;
- `work/queue/ARCH-RESET-2026-07/03-domain-specification.md` sections “Acquisition
  supervisor” and “Side-symmetric liquidity executor”;
- completed `WO-0145` through `WO-0148`, especially their public-contract, allowed-path,
  and closeout sections;
- `app/execution_core/{authority,protection,venue,position,identity}.py` and their directly
  named execution-core tests.

## Fable gate

```yaml
fable_gate:
  goal: "Implement pure, sealed acquisition and cross-side integration without operational I/O, persistence, or caller-minted authority."
  assumptions:
    - claim: "The accepted ADRs already authorize an immutable AcquisitionMandate linked to a complete ProtectionMandate and first-fill protection activation."
      status: VERIFIED
      evidence: "ADR-021 lines 22-39; domain specification lines 252-288."
    - claim: "Existing M1B/M1C owning indexes prove a bounded cross-side seam is feasible without an audit-history scan."
      status: VERIFIED
      evidence: "venue.py bounded authority summaries and authority.py final-claim/current-venue checks; WO-0147 explicitly routes M1E away from VenueRecoveryBook.effects. M1E-GATE-ACTIVE-LEGS must add and prove one narrow current next-leg projection before implementation review."
    - claim: "Generic CreateBrokerEffect(BUY) is insufficient because its mandate_id and economic_scope are caller-shaped."
      status: VERIFIED
      evidence: "authority.py CreateBrokerEffect/BrokerEffectRequest currently validates mode, fence, venue, budget, and residual but no complete acquisition/protection binding."
    - claim: "A dual acquisition-owner/protection-authority binding is required in canonical bounded effect/projection state."
      status: VERIFIED
      evidence: "ADR-021 distinguishes AcquisitionMandate from ProtectionMandate; venue.py protection cursor currently derives only RequestedEffect.mandate_id."
  approach: "Freeze a sealed acquisition/preemption public contract; write RED examples and bounded state machines; prove named mutants fail; implement one pure composite reducer plus narrow authority/venue/protection seams; independently review an immutable candidate."
  alternatives_considered:
    - "Reuse generic CreateBrokerEffect(BUY) with an arbitrary MandateId/economic_scope: rejected because callers could create or later claim unbound BUY work."
    - "Reuse one mandate ID for acquisition and protection: rejected because it destroys the required distinct immutable authority/provenance link."
    - "Use VenueRecoveryBook.effects or other audit collections for preemption: rejected because hot-path authority must use bounded current indexes."
    - "Reuse manual-flatten private helpers as the M1E API: rejected because that would make a private, differently-gated control flow the new acquisition/protection authority."
    - "Build broker child-price selection, authentication, persistence, or runtime serving now: rejected as M2-M6 scope."
  out_of_scope:
    - "WO-0149 application or test implementation until separate recorded authority names the boundary"
    - "SQL/DDL, database initialization or persistent-database work, runtime wiring, broker/Alpaca/network activity, credentials, CI workflow changes, PR/merge, deletion, cleanup, M2, and later work-order activation"
  done_when:
    - behavior: "The active work order accurately records WO-0148's immutable external closeout and specifies one pure M1E acquisition/preemption boundary without granting implementation authority."
      test: "One final independent static planning preflight (`REV-0052`) issues ACCEPT with no unresolved P0/P1 against the exact frozen candidate."
      command: "File hashes, exact-delta review, git diff --check, and AI Project OS static governance checks pass without application or test execution."
    - behavior: "A separately authorized implementation admits only sealed, current, dual-mandate acquisition work and preserves exact cross-side cancellation/wait behavior."
      test: "RED-first unit, generated-history, stateful, import-boundary, mutation, and independent-review controls prove the named counterexamples fail."
      command: "Run only the separately authorized commands in Required commands after a separately authorized implementation, then obtain exact-head Python 3.11/3.12 CI."
  blast_radius: "New pure acquisition semantic module; narrow authority, venue, protection, identity, package-export, direct execution-core tests, review/evidence, and current-status records only."
  rollback: "Revert only WO-0149 commits while preserving effective closure of WO-0145 through WO-0148 and all retained evidence."
```

## Normative M1E contract

### FR-01 — Immutable dual mandate authority

1. `AcquisitionMandate` MUST be exact-type, immutable, and scope-bound to one account/symbol and
   BUY side. It MUST retain a distinct `AcquisitionMandateId`, configuration version, maximum
   quantity, maximum notional, maximum entry price, allowed session and order-type policy,
   non-negative expiry/deadline, fixed child cap, optional certified-participation cap, bounded
   cancel/reprice budget, and a complete exact `ProtectionMandate` reference.
2. The linked `ProtectionMandate` MUST have the same position scope, session, and configuration
   authority as the acquisition mandate. Matching ID alone is insufficient: changed protection
   fields, scope, session, configuration, guard, formula, evidence policy, or budget authority
   must refuse. The distinct acquisition-owner and protection-authority identities plus their
   full immutable commitments must be retained in bounded canonical state.
3. Construction validates structural policy authority only. It MUST NOT authenticate an actor,
   credential, broker, supervisor fence, or live serving state.

### FR-02 — One opaque bounded acquisition lifecycle

1. The new reducer-owned `AcquisitionState` MUST be opaque, sealed, and bounded. It implements
   the domain lifecycle exactly: `READY -> WORKING|ABORTED`; `WORKING -> WORKING|COMPLETED|
   CANCELING|OUTCOME_UNKNOWN`; `CANCELING -> ABORTED|OUTCOME_UNKNOWN`; and
   `OUTCOME_UNKNOWN -> WORKING|COMPLETED|ABORTED` only through exact reconciliation. Once a
   protection preemption occurs, no path may return to `WORKING`; after the exact BUY closure it
   is `ABORTED`. `COMPLETED` and `ABORTED` never reopen from a later correction/bust or retry; a
   new mandate is required for a new entry.
2. Acquisition residual and every quantity/notional cap MUST be derived in fixed-point units from
   canonical, owned BUY root fill-family economics through a bounded venue-owned projection,
   never from net position, caller quantity, or an audit-history scan. A broker-authoritative
   over-price, over-quantity, or over-notional fact is applied exactly; it is not rejected or
   clamped. It immediately blocks further BUY work and drives cancellation/abort as required,
   while the same fact still updates protection. Protection SELLs and net-position changes never
   replenish acquisition capacity. Correction/bust handling preserves M1A's ordered canonical
   truth and never double counts.
3. M1E derives residual, maximum price, allowed session/order types, and fixed child,
   participation, cancel/reprice, expiry, and deadline ceilings from sealed mandate state plus
   exact current projections. It does not select a liquidity-dependent child price or broker
   syntax. No policy may be smuggled only in `economic_scope: bytes`.

### FR-03 — Sealed BUY route and create/claim revalidation

1. A generic caller-built exposure-increasing BUY `SUBMIT` or BUY `REPLACE` request MUST be
   refused. An admitted exposure-increasing BUY must originate only from a reducer-produced, opaque
   acquisition authorization/projection carrying the exact acquisition mandate, linked full
   protection mandate, current execution/venue/protection commitments, and derived bounded policy
   ceilings. A target-derived BUY `CANCEL` is not new exposure: it follows the existing M1C
   safety-preserving cancellation route only when its exact current target leg, dual-mandate binding,
   and cancellation scope are derived from the bounded current-leg projection. It remains eligible
   after entry work is halted or killed, but neither a generic caller-built cancel nor a cancel may
   re-open or extend acquisition authority.
2. The sole source of that authorization MUST be one reducer-owned, monotonically advancing
   composite currentness projection. Its sealed head binds the exact acquisition state, protection
   commitment/projection, execution snapshot commitment, and current venue/authority commitment
   for one scope. The authority-owned state registers that head before it creates any effect and
   compares it again at final claim; it never accepts a command-supplied assertion that a seal is
   current. A newer protection exit, venue transition, cap, fence, kill, or scope change therefore
   invalidates a prior BUY authorization at both boundaries.
3. The authority boundary MUST revalidate the registered sealed acquisition authorization at both
   effect creation and final claim for BUY `SUBMIT` and BUY `REPLACE`. It MUST re-read exact
   execution binding, acquisition/protection commitment, account/symbol/session scope, mode, kill,
   supervisor fence, request budget, venue uncertainty, authoritative residual, mandate caps, and
   cross-side state. A stale or preempted exposure-increasing BUY cannot claim. A target-derived BUY
   `CANCEL` instead revalidates its exact current leg and cancellation authority at creation and
   claim without requiring an entry-serving state.
4. Canonical effect/projection ownership MUST bind distinct acquisition and protection identities.
   Neither a single overloaded `MandateId` nor hidden linkage in `economic_scope` is sufficient.
   The bounded protection projection/cursor retains the protection authority while the effect
   retains the acquisition owner, so cross-substitution is refused.

### FR-04 — Atomic first-fill protection integration

1. An accepted first-occurrence owned BUY `FILL` MUST consume the one exact venue transition whose
   post-transition execution snapshot contains the canonical economics, then update acquisition
   state and position protection in the same composite sequenced reducer transition. It MUST NOT
   perform a second fill fold, independently reconstruct execution economics, or partially publish
   an acquisition/protection result.
2. That same transition MUST initialize or update `FLOOR_ONLY` from the linked exact protection
   mandate and current fill-derived average cost. It MUST NOT wait for acquisition completion or
   permit a committed positive BUY exposure with missing/stale protection authority.
3. Late owned BUY fills or valid correction/bust replacements after `FLAT` MUST apply economics
   first and restore sticky `HARD_BAIL` under the retained linked protection mandate. They MUST
   never silently leave positive quantity flat, invent a mandate, or return to unarmed
   `FLOOR_ONLY`.

### FR-05 — Protection preempts acquisition through current bounded authority

1. A protection exit can be acted upon only from a new opaque, protection-owned exit projection
   minted by the composite reducer from exact authentic protection state and its current bounded
   protection/venue proof. It carries the matching composite head and scope. A direct
   `ProtectionTransition`, `ExecutionGoal`, boolean, closure claim, or copied commitment MUST NOT
   mint preemption authority, even when it embeds an otherwise authentic state.
2. The authority-owned preemption transition MUST compare that exit projection to its registered
   current composite head, atomically latch preemption/wait and stand down only safely-local
   unclaimed BUY requests. It MUST NOT claim that all BUY cancellations occur in that one
   transition. A venue-owned current-leg projection exposes at most one exact cancellable BUY leg
   for each sequenced cursor advance; that step emits one target-derived BUY `CANCEL`, then the next
   exact venue transition/reconciliation advances the cursor. The preemption latch remains until no
   next leg exists and every relevant parent acceptance set is exactly `CLOSED`. This route cannot
   enumerate `effects`, `owners`, `active_attempts`, or another lifetime history, and it must not
   materialize an unbounded active-leg collection merely to begin preemption.
3. A protection SELL MUST remain blocked until every relevant BUY leg is resolved and each BUY
   parent acceptance set is exactly `CLOSED`. Cancel acknowledgement, known-leg terminality,
   position parity, `OPEN`, and `INVALIDATED` never release it.
4. Waiting preserves `EXIT_NORMAL` versus `HARD_BAIL`; waiting does not promote normal exit to
   emergency authority, and hard bail stays sticky. A late BUY during the wait preserves both its
   economics and the waiting/protection restrictions.

### FR-06 — Cross-side ownership and pure boundary

1. One symbol-wide bounded current-authority classifier MUST govern acquisition admission,
   exposure-increasing BUY `SUBMIT`/`REPLACE` creation and final claim, target-derived BUY `CANCEL`,
   preemption, and subsequent SELL creation/final claim. Exposure-increasing BUY work remains
   blocked while any incompatible SELL ownership or exit is live; target-derived safety cancellation
   remains available under its inherited M1C rules; SELL remains blocked while BUY uncertainty is
   unresolved.
2. M1E may emit typed, broker-neutral BUY policy ceilings and sealed M1C authority inputs. It MAY
   validate a supplied abstract term against the immutable ceilings, but MUST NOT select a
   liquidity-dependent child price or broker syntax, claim a broker effect, call an adapter,
   authenticate an operator, grant serving/fence state, persist state, or perform I/O.
3. All hot-path decisions MUST consume existing public authority-led contracts or a newly sealed
   bounded projection. M1E MUST NOT scan `VenueRecoveryBook.effects`, `claims`, `owners`,
   attempts, closure ledgers, input ledgers, or another unbounded/audit-only collection; MUST NOT
   import private state as a shortcut; and MUST NOT duplicate the fill fold, venue closure logic,
   or protection formula reducer.

## Design-time full war-game

### M1 — traced decision claims

| Decision | Status | Evidence or named implementation gate |
|---|---|---|
| Distinct immutable acquisition and protection mandates are required before BUY work. | TRACED | ADR-021 lines 22-39; domain specification lines 252-269. |
| Generic exposure-increasing BUY admission is unsafe without a sealed current acquisition authorization, while target-derived BUY cancellation remains safety-preserving. | TRACED | `authority.py:_create_gate_reason` and `_claim_gate_reason` admit a generic BUY by mode/kill/fence/budget only; `BrokerEffectRequest` distinguishes SUBMIT/REPLACE from a target-leg CANCEL. |
| Current bounded venue summaries, not audit collections, can drive cross-side preemption. | TRACED | `authority.py:_authority_begin_symbol_flatten`; `venue.py:_venue_authority_view` and compact per-symbol indexes. |
| First fill and protection must share one sequencing boundary. | INHERITED | ADR-021 lines 36-39 and 88-93. M1E-GATE-ATOMIC must consume the exact post-venue-transition execution snapshot once and return one composite acquisition/protection result; no partial publication or second fill fold. |
| A public `ProtectionTransition` is not itself current exit authority. | TRACED | `protection.py` exposes a constructible transition/goal; M1E-GATE-EXIT must require an opaque protection-owned exit projection matched to the authority-owned composite head. |
| All future readers/writers of new acquisition artifacts are known before GREEN. | IMPLEMENTATION GATE | M1E-GATE-CONSUMERS requires a complete reader/writer inventory and import-boundary pin; unknown consumer blocks review. |

### M2 — lifecycle totality

| Artifact | Birth and legal progression | Terminal rule / writer |
|---|---|---|
| `AcquisitionMandate` | exact structural construction; immutable full protection reference | immutable for its lifetime; only the M1E reducer reads its sealed commitment |
| `AcquisitionState` | domain-exact READY/WORKING/CANCELING/OUTCOME_UNKNOWN/COMPLETED/ABORTED graph; an irrevocable `preempted`/abort-required latch permits reconciliation to return to WORKING only when no protection preemption has occurred | when preempted, reconciliation can resolve only COMPLETED/ABORTED and exact closure ends ABORTED; COMPLETED/ABORTED never create another BUY; reducer only |
| sealed composite currentness projection | emitted from exact current acquisition/protection/venue/execution state and registered in authority-owned current state | invalidated by any newer head, exit preemption, mismatch, terminal acquisition, cap, fence, or uncertainty; authority is sole create/claim reader |
| protection-owned exit projection | emitted only by the composite reducer from exact authentic protection state plus current bounded proof | one scope/head only; authority rejects a direct transition, goal, copied commitment, stale head, or caller-supplied currentness |
| bounded dual-mandate effect/projection binding | appended only by the authority/venue transition that admits the sealed BUY | cannot be replaced by caller bytes or a different mandate identity; projection/authority only |

### M3 — consumer/control-action inventory

| Artifact | Planned readers | Required control result |
|---|---|---|
| `AcquisitionState` | M1E reducer; sealed BUY authorization derivation; cross-side preemption; test import boundary | no reader may revive terminal entry, bypass protection, or cause unbounded traversal |
| dual mandate binding | acquisition reducer; authority create/claim; venue current projection; protection projection | a changed/single/hidden link is refused at every reader |
| BUY preemption result | authority current-index path; protection integration | one atomic preemption latch/stand-down plus one target-derived cancel per sequenced current-leg cursor advance; no stale SELL release or indefinite phantom local BUY |
| bounded acquisition economic projection | acquisition residual/cap reducer; property tests | fixed-point canonical owned economics account for corrections/busts and over-cap facts; capacity never derives from net position or a protection SELL |

M1E-GATE-CONSUMERS must search the exact candidate for all readers/writers of these types and
classify each as unaffected, affected, or prohibited before independent review. Any unknown reader
or private/audit collection consumer is a blocking finding.

### M4a — prospective hindsight

Assume M1E shipped and caused an unsafe second entry or an unprotected late long. The likely causes
were: generic exposure-increasing BUY creation accepted arbitrary approval bytes; an acquisition and protection mandate
were confused because they shared an ID; a first fill committed before protection caught up; a
public transition was treated as current exit authority; a stale BUY seal survived a later exit; or
a broad BUY refusal accidentally blocked a target-derived safety cancel; a preemption transition
attempted to enumerate all legs; or a bounded decision quietly became an audit-history scan.
FR-01 through FR-06 and the named negative controls exist to make each route fail closed. No other
cause is treated as resolved merely because it is described here.

### M4b — independent refutation

The final fresh independent review packet at `work/review/REV-0052/` must attempt to disprove this
decision block from accepted authority and current public code. Activation may proceed only after
each finding is resolved in the draft or retained as a named implementation gate, with no unresolved
P0/P1.

## Required RED contract and future proof obligations

Before any production implementation:

1. Freeze exact public names/signatures, then write RED tests first. The public surface must expose
   only sealed state/transition/projection values needed by consumers; no raw authority factory or
   private venue accessor becomes public.
2. Add unit and generated/stateful histories for: mandate field/scope/session/config/guard/formula
   substitution; generic exposure-increasing BUY rejection plus valid target-derived BUY-cancel
   preservation; invalid or stale authorization/exit input; direct public
   `ProtectionTransition`/`ExecutionGoal` preemption; a newer protection or venue head between
   create and claim; first-fill non-atomicity or second-fold attempt; correction/bust owned-fill
   accounting; broker-authoritative over-cap facts; net-position or protection-SELL capacity
   substitution; quantity/notional/maximum-price/child/participation/cancel/reprice boundary
   mutations; expiry and terminal re-entry; mode/kill/fence/budget changes between create and
   claim; BUY/SELL races; unclaimed versus claimed/unknown multi-acceptance BUY preemption;
   atomic preemption latch with deterministic one-leg-per-cursor cancellation behavior;
   `OPEN`/`INVALIDATED` versus exact `CLOSED`;
   normal-versus-hard-bail wait preservation; and late fill after `FLAT`.
3. Add failure-capable scan/import controls: instrument every audit-only VenueRecoveryBook
   materializer, lifetime owner/attempt collection, and private acquisition/venue path so a hot-path
   call fails; prove the bounded current-index active-leg projection/cursor still passes. Include a
   history-scaling/tripwire control.
4. Each material mutant above must fail for the claimed reason. Tests must state the lifetime/
   restart invariant and vary free parameters per Fable v3.1; every ingress to derived authority
   receives a negative validity case.
5. The later implementation review must rederive all requirements blind/spec-first, inspect the
   exact candidate, and issue `ACCEPT` with P0=0/P1=0 before closeout. Exact-head Python 3.11/3.12
   CI remains the external closeout gate.

## Allowed paths

```yaml
allowed_paths:
  - app/execution_core/acquisition.py
  - app/execution_core/authority.py
  - app/execution_core/protection.py
  - app/execution_core/venue.py
  - app/execution_core/identity.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_acquisition.py
  - tests/execution_core/test_acquisition_stateful.py
  - tests/execution_core/test_authority.py
  - tests/execution_core/test_authority_stateful.py
  - tests/execution_core/test_protection.py
  - tests/execution_core/test_protection_stateful.py
  - tests/execution_core/test_venue_ownership.py
  - tests/execution_core/test_venue_recovery.py
  - tests/execution_core/test_venue_stateful.py
  - tests/execution_core/test_venue_binding_recovery.py
  - tests/execution_core/test_venue_checkpoint_hardening.py
  - tests/execution_core/test_venue_provenance_hardening.py
  - tests/execution_core/test_import_boundary.py
  - work/active/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md
  - work/queue/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md
  - work/completed/keep/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md
  - work/completed/keep/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md
  - work/review/REV-0051/**
  - work/review/REV-0052/**
  - work/ledger.jsonl
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/log.md
  - README.md
  - docs/04_IMPLEMENTATION_PLAN.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
activation_only_paths:
  - README.md
  - docs/04_IMPLEMENTATION_PLAN.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/log.md
  - work/ledger.jsonl
  - work/active/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md
  - work/queue/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md
  - work/completed/keep/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md
  - work/review/REV-0051/**
  - work/review/REV-0052/**
```

Everything else is forbidden unless this work order is explicitly re-gated. In particular, do not
change `fills.py`, `position.py`, `recovery.py`, `values.py`, accepted ADR bodies, the staged
reset packet, branch-retirement manifest, any store/event/broker/adapter/API/UI/runtime path,
`.github/workflows/**`, or retained artifacts. The sole retained-record exception is one append-only
WO-0148 external-success addendum required by this activation; it may state the run #693 provenance
but may not rewrite historical closeout text or alter retained evidence. `activation_only_paths`
are unavailable to later application/test implementation unless a separate work order explicitly
re-gates them. Future use of existing mock/disposable SQLite fixtures, SQL, or DDL is not authorized
by this activation and requires explicit recorded authority.

## Required commands after a separately authorized implementation

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_acquisition.py tests/execution_core/test_acquisition_stateful.py
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core
.\.venv\Scripts\python.exe -m pytest -q tests/r2_conformance_oracle.py
ruff check app/execution_core tests/execution_core
ruff format --check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app
lint-imports
git diff --name-only <activation-commit-sha>..HEAD | .\.venv\Scripts\python.exe .ai-os\scripts\check_work_order_scope.py work/active/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md
.\.venv\Scripts\python.exe .ai-os\scripts\check_work_order_disposition.py
.\.venv\Scripts\python.exe .ai-os\scripts\check_ledger.py
.\.venv\Scripts\python.exe .ai-os\scripts\check_pkl.py
git diff --check
```

The implementation start gate must replace `<activation-commit-sha>` with the exact
documentation-only activation commit in the piped `git diff` invocation. It must not start while
that SHA, the RED contract, or the preflight packet is missing.

## Stop conditions

Stop and return `BLOCKED` before implementation if any of the following occurs:

- an accepted ADR conflict or a required architectural decision not already accepted;
- a required consumer cannot be enumerated or must use a private/audit-history seam;
- a sealed dual-mandate binding cannot be represented through bounded current state;
- generic exposure-increasing BUY admission cannot be closed while preserving target-derived
  safety cancellation under the authorized predecessor contract;
- a one-leg-per-cursor cancellation route cannot be supplied without an audit/private seam, or it
  cannot preserve the preemption latch until exact parent closure;
- atomic first-fill/preemption semantics require a persistent/runtime/broker change;
- any P0/P1 remains in the independent preflight; or
- authority, scope, or external-evidence provenance cannot be reconciled exactly.

## Activation acceptance criteria

- [ ] AC-01 (FR-01): Exact dual-mandate authority, field-level matching, and structural-only
  admission are specified and independently reviewed.
- [ ] AC-02 (FR-02/03): The sealed acquisition lifecycle, exposure-increasing BUY refusal,
  target-derived BUY-cancel preservation, and create-claim revalidation routes are specified with
  failure-capable controls.
- [ ] AC-03 (FR-03/04): Bounded dual-mandate effect/projection binding and one atomic first-fill
  integration transition are specified; no net-position or caller-byte substitute is accepted.
- [ ] AC-04 (FR-05/06): Current-index cross-side preemption and exact `CLOSED` wait release are
  specified without private/audit scans or policy promotion.
- [ ] AC-05: M1-M4 war-game has no unaddressed `ASSUMED` decision claim, and independent
  preflight returns `ACCEPT` with P0=0/P1=0.
- [ ] AC-06: WO-0148 current status is reconciled atomically from run #693 without rewriting its
  historical conditional closeout or using #691 as a success claim.
- [ ] AC-07: The active work order explicitly bars all application/test implementation pending
  separate authorization and preserves all earlier exclusions.

## Completion disposition

Complete only after a separately authorized implementation and closeout:

- [ ] PKL_UPDATED
- [ ] RESULT_SUMMARY_KEPT

## Distillation checklist

- [ ] Durable acquisition/cross-side facts captured in PKL or an accepted ADR if a new decision is required.
- [ ] Failure lessons captured in the project log or review packet.
- [ ] Compact result/evidence retained.
- [ ] Ledger updated.
- [ ] Work order moved and dispositioned only on actual closeout.
