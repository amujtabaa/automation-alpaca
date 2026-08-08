# REV-0058 R11 R1 independent static pre-flight result

Status: **INDEPENDENT STATIC REVIEW -- DOCUMENTATION ONLY**

## Exact candidate and review integrity

- Reviewed branch and HEAD: `codex/arch-reset-2026-07-r1` at
  `7c96e6b29c39652d66c6cf41d9896974dbec5f53`, exactly the manifest review
  base. The base commit exists and is the current `HEAD`.
- Recomputed SHA-256 for every manifest row: **32 matched, 0 mismatched**.
- Exact-path `git status` confirmed that R11, R11 R1, their requests/manifests,
  and the retained R11 result are additive worktree packet artifacts at that
  base, while the pinned application/test files are the documented modified
  feasibility context. No unpinned repository artifact was used as review
  authority or feasibility evidence.
- Read order was specification-first: ADR-020 R2, ADR-021 R2, ADR-023 R1,
  active WO-0151, R2 through R11, then R11 R1. The retained initial R11 result
  was read only after that derivation, and the pinned application/test context
  only afterward.
- `WO-0151-R11-CONSTRUCTIBILITY-NOTES.md` was not opened or read. Searches were
  confined to explicit manifest-listed files. No application, test, database,
  SQL, broker, network, CI, or runtime work ran.

## Findings

No P0, P1, or P2 findings.

## Closure of the initial R11 P1

The initial P1 is closed by a complete producer/consumer split rather than by
weakening SELL eligibility:

1. R11 R1 restores `begin_acquisition_preemption(...)` to its transition-free
   public signature and makes protection the sole producer of a private,
   sealed `PREEMPT_BUY_ONLY` relation from the exact current raw state and
   `AcquisitionProtectionContext` (`WO-0151-RED-CONTRACT-R11-R1.md:14-25` and
   `:45-76`). The projector requires positive bounded exposure, exact
   `EXIT_NORMAL`/`HARD_BAIL`, true `waiting_buy_resolution`, and authentic
   protection provenance. It does not accept a caller goal or carry SELL,
   guard, deadline, rate, effect, or claim authority.
2. Goal eligibility is expressly irrelevant to this relation. Halt,
   baseline-required, market exhaustion, formula unavailability, and other
   conservative goal-suppression conditions do not prevent safe BUY stand-down
   (`WO-0151-RED-CONTRACT-R11-R1.md:78-82`). This directly removes the
   contradiction identified in retained `result-r11.md:28-112`.
3. A standalone preemption authenticates a `CURRENT` refresh and exact current
   raw protection context. An already-applied retired or abnormal-current fact
   obtains the same relation from its immediate owner-produced state/context
   inside the composite, without an intermediate refresh or second
   registration (`WO-0151-RED-CONTRACT-R11-R1.md:84-91`). This makes both the
   late-retired-A/no-B-baseline case and the abnormal current first-root case
   constructible.
4. Acquisition consumes the relation only for its fixed purpose. Authority
   remains the final mutation owner and rechecks controller head, generation,
   scope, currentness, direct effect owner, residual exposure, acceptance,
   closure, reconciliation, and single-flight state. The result can invalidate
   one unclaimed BUY or stage at most one bounded cancel; claimed, unknown,
   OPEN, INVALIDATED, cancellation-only, stale, mismatched, already-cancelled,
   or wrong-owner work remains waiting/reconciliation-only
   (`WO-0151-RED-CONTRACT-R11-R1.md:93-102`).
5. SELL remains a separate route. Its private intent requires a current
   authentic `APPLIED ProtectionTransition` with an owner-produced SELL goal,
   exact resulting raw state/context, false `waiting_buy_resolution`, positive
   residual, and current formula/market/halt/baseline/exhaustion/mandate/goal
   conditions. Authority then repeats BUY-closure, head, residual, guard,
   budget, ownership, and currentness checks
   (`WO-0151-RED-CONTRACT-R11-R1.md:104-138`). A preemption relation cannot be
   supplied to or upgraded into this
   route.

The pinned protection seam corroborates constructibility without serving as
implementation acceptance: current state already seals policy, quantity,
waiting status, market latches, and exit provenance into its semantic context
(`app/execution_core/protection.py:725-759`), and its goal producer already
suppresses SELL for waiting BUY, halt, baseline, exhaustion, formula loss,
nonpositive/excessive residual, blocking work, or stale execution
(`app/execution_core/protection.py:2461-2506`). R11 R1 therefore separates
cancel-only authority at the correct owner boundary instead of changing those
goal rules.

## Route-completeness re-derivation

| Public operation / route | Bounded producer -> authenticated consumer -> mutation owner -> result and negative behavior | Conclusion |
|---|---|---|
| Venue acquisition context, bootstrap, and fact projections | Venue derives target-local context and bootstrap facts from exact book/execution pairs and derives canonical fact relations from the owner-sealed `VenueRecoveryTransition`. Acquisition consumes only exact projections and direct keys. Wrong scope/generation, stale pair, wrong source kind, altered transition, missing direct owner/root/effect/request route, or unresolved reconciliation is non-serving. Projection is read-only. | Complete. |
| Authority context, admission, effect view, and context refresh | Authority derives target context/admission/effect view from its exact state and uses the venue-owned account-current seam for `CURRENT`, one-transition `REFRESHED`, R8 `UNBOUND_BOOTSTRAP`, or component-free `REFUSED`. Wrong account/generation/scope, stale/non-prefix source, altered transition cardinality, unresolved reconciliation, or copied handoff refuses before acquisition mutation. | Complete. |
| Protection context, semantic projection, neutral construction, mixed recovery, and the two purpose intents | Protection authenticates raw state plus exact venue/execution context. Semantic rebase consumes an owner transition; neutral reprojection consumes one zero-economic refresh transition; mixed recovery consumes its private proof; preemption consumes current state/context without a goal; SELL consumes a current goal-bearing transition. Acquisition does not reconstruct policy, provenance, urgency, guard, or terms. | Complete. |
| `initialize_acquisition_controller` | R8 handoff + exact venue bootstrap + `GENESIS_EMPTY` admission feed acquisition; authority installs the sole ordinal-zero `BOOTSTRAP` registration. Wrong source, nonflat/active target, second initialization, wrong scope/session/generation, or partial handoff changes nothing. No protection, effect, or claim is created. | Complete. |
| `begin_acquisition_generation` | Acquisition composes exact refresh/bootstrap/admission with derived `ABORTED` or `COMPLETED` predecessor terminality. Authority owns the one successor registration; acquisition retires A, inserts one LIVE B, advances ordinal/head once, and returns `protection=None`. Temporary flatness, old raw protection, nonclosed/unknown/live work, reconciliation, incompatible compatibility, reused stream, or stale/forked head leaves A unchanged. The same path repeats for B -> C with direct retained provenance. | Complete. |
| `reduce_acquisition_controller` -- current first/follow-on/revision | Venue supplies one authentic already-applied FILL/CORRECT/BUST relation. Acquisition uses direct lineage/registry, protection initializes or reduces once, and authority supplies exactly one currentness result. Normal first root is fresh `FLOOR_ONLY`; conservative results are retained non-serving and may produce the preemption-only relation when BUY resolution is required. Replay, wrong owner, stale head, fork, or altered relation cannot reapply economics or register again. | Complete. |
| `reduce_acquisition_controller` -- retired fact | Direct root/effect/owner/fact keys select the retired record without scanning. Protection owns mixed recovery. With no authority mutation, `CANONICAL_FACT` is the sole registration; with current BUY work, one `AUTHORITY_MUTATION` receipt adopts the fact result, performs at most one stand-down/cancel, stales claim authority, and advances the head once. It must not also register `CANONICAL_FACT`. Claimed/unknown/conflicting work yields the bounded wait/reconciliation result, not a partial composite. | Complete. |
| `rebase_acquisition_protection` -- semantic | Exact semantic projection + `CURRENT` refresh + R9/R10 predecessor-semantic predicate feed acquisition; authority owns the single `PROTECTION_REBASE` registration. Wrong union member/disposition, replay-only or altered projection, stale raw state/context/head, or changed authority/venue relation refuses unchanged. | Complete. |
| `rebase_acquisition_protection` -- neutral | Exact stale raw state + one `REFRESHED` sibling catch-up let the private protection helper derive the current raw state. Acquisition rechecks the complete R7 authority pair and the helper matcher. Controller/head/ordinal, registry, lineage, semantic commitments, currentness, permits, effects, and claims remain byte-identical. Wrong cursor/execution/scope/mandate, nonzero or multiple transitions, semantic change, copied neutral projection, or any partial refresh returns the predecessor component set. | Complete. |
| `create_acquisition_effect` | Serving refresh + exact current protection/no-protection context + bounded terms feed the private authority permit. Authority rechecks mandate, capacity, head, owner, global gates, and currentness and alone creates the specialized BUY/receipt. Generic BUY remains refused. Changed terms, cap, stale refresh/head, wrong owner/scope, or replay cannot create a second effect. | Complete. |
| `claim_acquisition_effect` | Direct effect view + current refresh/protection feed a fresh claim permit. Authority performs the immediate final ownership/currentness/acceptance recheck and returns the sole claim receipt. A retired fact, changed head, stale refresh, claimed/unknown/conflicting work, wrong occurrence, or replay refuses before I/O authority. | Complete. |
| `begin_acquisition_preemption` | Exact `CURRENT` refresh/state/context -> protection-owned `PREEMPT_BUY_ONLY` relation -> acquisition composition -> authority final permit/mutation -> one stand-down or bounded cancel and one receipt/head result. The immediate fact route uses the same producer before a refresh exists. False waiting, wrong policy/provenance/context/owner, stale head, duplicate cancel, replay, claimed/unknown work, or conflict is fail-closed. | Complete; the initial R11 P1 is closed. |
| `create_acquisition_protection_exit` | After exact BUY closure, a current authentic `APPLIED` transition and owner-produced SELL goal -> protection-owned `CREATE_PROTECTION_EXIT_ONLY` intent -> acquisition composition -> authority final closure/residual/guard/budget/head/ownership recheck -> at most one protective SELL creation/claim. Goal-less, caller-goal, preemption-only, copied/altered/old/replay-only transition, stale raw context, baseline/halt/exhaustion/formula denial, changed terms/head, or final-claim race refuses. | Complete and purpose-separated. |
| `project_acquisition_controller` | Acquisition authenticates its own current state and returns only constant-size immutable status fields. No map, iterator, raw owner state, policy constructor, or action capability escapes. | Complete. |

## Focused counterexamples and ordering

- **Late retired A with unresolved B BUY and no baseline:** the already-applied
  fact produces current mixed `HARD_BAIL` plus exact context; the goal-independent
  preemption projector can authorize only stand-down/one cancel. Fact economics,
  retired economics, aggregate binding, and controller/currentness advance once;
  no SELL intent exists.
- **Abnormal current first root:** the raw owner-produced conservative state is
  sufficient; no fabricated `ProtectionTransition` or SELL goal is required.
  Halt, baseline-required, exhaustion, or formula unavailability still suppress
  SELL while permitting safe BUY preemption when the exact waiting/provenance
  relation holds.
- **Standalone/replay/wrong-context preemption:** standalone use requires a
  current refresh; immediate-fact use is restricted to that composite. False
  waiting, wrong provenance, copied/spliced state, changed owner/head, duplicate
  cancellation, or replay cannot produce a second mutation. Claimed/unknown
  work remains wait/reconciliation.
- **SELL after BUY closure:** cancellation does not upgrade the preemption
  relation. A fresh current raw state/context and a fresh owner-produced
  goal-bearing transition are required. Old, replay-only, goal-less, altered,
  baseline-gated, halted, exhausted, formula-unavailable, changed-head, or
  final-claim-race inputs refuse.
- **Neutral sticky-exit continuity:** neutral refresh transports raw freshness
  only. A fresh waiting state can still produce preemption without a goal; a
  pre-refresh goal transition is stale; a later fresh transition may serve SELL
  only when all protection and authority gates are current.
- **Combined ordering:** before BUY create, the fact's one head advance makes an
  old create source stale. After create or before final claim, the combined
  `AUTHORITY_MUTATION` receipt adopts the fact and performs at most one cancel;
  no second `CANONICAL_FACT` registration is allowed. Exact replay adds no
  receipt, registration, cancel, effect, claim, or second aggregate delta.
- **A -> B -> C and other routes:** derived terminality, direct retained lineage,
  semantic/neutral rebase, create/claim, current/follow-on/reconciliation facts,
  final-claim revalidation, and no-scan/no-cache boundaries remain unchanged and
  require no new public surface, hidden state, policy writer, or second aggregate
  writer.

## Failure-control adequacy and limits

R11 R1's replacement controls are failure-capable in shape. They pair a
positive no-baseline/goal-less producer case with purpose-confusion, stale
context, false waiting/provenance, duplicate-cancel, old-transition, changed-
terms/head, neutral-transport, double-registration, and final-claim negative
controls (`WO-0151-RED-CONTRACT-R11-R1.md:186-205`). The named mutations remove
the owning matcher or material gate one at a time, so each can fail for its
intended reason. The retained R11 controls continue to cover terminality,
fact-totality, exact-once ordering, race, and structural boundaries.

This is static RED-contract acceptance only. Future implementation, test
execution, mutation execution, runtime/persistence behavior, broker behavior,
and CI remain unverified and are not accepted, ratified, or authorized here.

## Verdict

**ACCEPT**

- P0: 0
- P1: 0
- P2: 0

Route-completeness conclusion: **Yes.** Every remaining R2-R11-plus-R11-R1
public operation has a bounded owner-produced input, authenticated consumer,
single mutation owner, complete result path, and fail-closed stale/replay/wrong-
owner/conflict behavior. The initial R11 preemption-producer P1 is affirmatively
closed, and `PREEMPT_BUY_ONLY` cannot substitute for the separately goal-bearing
SELL exit route.
