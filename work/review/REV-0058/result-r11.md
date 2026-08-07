# REV-0058 R11 independent static pre-flight result

Status: **INDEPENDENT STATIC REVIEW — DOCUMENTATION ONLY — NON-ACCEPTANCE**

## Exact candidate and review integrity

- Reviewed branch and HEAD: `codex/arch-reset-2026-07-r1` at
  `7c96e6b29c39652d66c6cf41d9896974dbec5f53`, exactly the R11 manifest review
  base.
- Recomputed SHA-256 for every manifest row: **28 matched, 0 mismatched**.
- The accepted ADRs, active WO-0151, R2-R10 bodies, and retained R10 evidence are
  unchanged tracked files at the review base. R11's contract, request, and
  manifest are additive untracked packet files. The manifest-excluded
  `WO-0151-R11-CONSTRUCTIBILITY-NOTES.md` was not opened or read.
- Application and test files were treated only as static feasibility context.
  No application, test, database/SQL, broker, network, CI, or runtime work ran.
- Review-integrity limitation: after the specification-first derivation, one
  overly broad read-only text search printed isolated matching-line snippets
  from out-of-manifest PKL, completed-work, and prior-review paths. Those files
  were not opened, and none of those snippets is used as authority or evidence
  in this result. Because the request imposed an exact-set boundary, this is
  disclosed as packet contamination. This result is a non-acceptance result and
  must not be reused as a future acceptance seat; a changed candidate requires a
  fresh exact freeze and fresh independent review.

## Findings

### [P1] Cancellation preemption is gated by a SELL goal that unresolved-BUY recovery states cannot lawfully produce

**Requirement.** WO-0151 FR-07 and FR-08 require one atomic fact result to stale
or preempt current BUY authority, including the retired-fact
`MIXED_GENERATION_RECOVERY/HARD_BAIL` route
(`work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md:176` and
`:183`). R11 likewise requires a retired fact to perform at most one safe
current-BUY stand-down/cancel in its single ordered mutation
(`work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md:257`).

**Evidence.** The only R11 intent projector accepts an authentic `APPLIED`
`ProtectionTransition` **only when it has a non-`None` owner-produced SELL
goal**, and it rechecks the halt, baseline, and exhaustion gates
(`work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md:160` and `:166`). Both
`begin_acquisition_preemption(...)` and the SELL-exit operation must obtain that
same intent; preemption is expressly the branch used while BUY resolution is
still required (`work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md:177`). The
failure-control table further requires halted, baseline-required, or exhausted
state to be unable to mint this authority
(`work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md:286`).

That producer rule is incompatible with the required preemption state:

1. An unresolved BUY is exactly the work preemption must stand down or cancel.
2. The pinned protection semantic center suppresses `ExecutionGoal` when
   `waiting_buy_resolution` is true or a blocking effect exists, as well as
   during halt, baseline, or exhaustion
   (`app/execution_core/protection.py:2461`). A non-goal transition therefore
   cannot serve R11; allowing one would contradict the projector's exact
   `non-None`-goal rule.
3. A protection state initialized from a first positive fact is returned as raw
   `PositionProtectionState`, not an `APPLIED ProtectionTransition`
   (`app/execution_core/protection.py:3449`), and its new market state is
   baseline-required (`app/execution_core/protection.py:2325`). ADR-023 also
   requires baseline recovery to suppress goal emission until recovery is
   complete (`docs/adr/ADR-023-bounded-market-occurrence-authority.md:236`). Feeding that
   state back through the same current venue projection is exact replay with no
   goal (`app/execution_core/protection.py:3515`). Thus an abnormal authentic
   first root with residual BUY work has neither the required transition nor an
   eligible goal.
4. The same contradiction is unavoidable for the explicit retired-fact race in
   which successor B has created BUY work but has no first root/protection yet:
   late A economics must create aggregate `HARD_BAIL` and preempt B, while a
   newly derived protection state necessarily lacks recovered market baseline.
   R11 requires section 3 intent for any protective action even for a
   conservative non-normal fact result
   (`work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md:249`), but section 3 forbids
   the only intent that could authorize the cancel.

Changing the existing goal producer to emit a goal while BUY resolution is
pending would not close the full gap: baseline/halt/exhaustion suppression is
separately required by the accepted market-authority contract and by R11's own
projector/control. Conversely, accepting a non-goal transition as the current
projector is written is not lawful.

**Impact.** A valid late retired fact or non-normal first fact can stale future
claims but cannot stand down an unclaimed BUY or stage the one bounded cancel
needed to stop already-live BUY exposure. The composite cannot satisfy
FR-07/FR-08 atomically, and the required retired-fact/preemption route is not
constructible from the frozen producer/consumer chain. This is a capital-safety
and lifecycle-completeness defect, not an implementation detail.

**Required root resolution.** Separate protection-owned **preemption-only**
intent from SELL-exit eligibility. A private protection-owned state/context
projector can close the gap without adding public authority: it must accept only
an exact authentic current `PositionProtectionState` and
`AcquisitionProtectionContext` (plus exact transition/fact provenance when one
exists), rederive and seal the need for BUY resolution inside `protection.py`,
and return an opaque purpose-bound intent that can authorize only safe
stand-down/one cancel. It must carry no SELL effect authority and must not
bypass stale/currentness, ownership, or final authority checks. The existing
goal-bearing path should remain mandatory for `PROTECTION_EXIT` after BUY
closure. Acquisition may consume the two purpose-bound intents, while
`authority.py` remains the sole mutation/final-permit owner. This is a material
change to R11's exact private seam/intent semantics and therefore requires a new
exact freeze and focused review; no new public type, enum, command, source kind,
or policy writer is needed.

Add a failure-capable composition control with B's unresolved unclaimed or
cancellable BUY plus a late retired-A fact while B has no protection baseline.
It must prove one preemption-only owner intent and at most one cancel, no SELL
eligibility, and atomic fact/currentness advancement. Mutants that require a
SELL goal, accept caller state/context, omit purpose binding, or let the intent
serve `PROTECTION_EXIT` must turn that control red. Add the analogous abnormal
current-first-root case.

## Route-completeness re-derivation

The following table enumerates the remaining public E2 operations and their
bounded producer-to-result paths. “Constructible” means the pinned public
surface and named private owner seams are sufficient; it is not implementation
acceptance.

| Public operation / route | Producer → authenticated consumer → mutation owner → result and negative behavior | Conclusion |
|---|---|---|
| `VenueRecoveryBook.project_acquisition_bootstrap` / `project_acquisition_fact` | Venue owns target-local bootstrap and direct fact relation production. Acquisition consumes owner-authentic projections; wrong scope, source kind, predecessor, altered transition, or forged proof is non-serving. The operations are read-only. | Constructible. |
| `project_acquisition_admission`, `project_acquisition_effect`, and `refresh_acquisition_context` | Authority derives admission/effect views and one target refresh from its authentic state and an account-current snapshot. `CURRENT`, one-transition `REFRESHED`, R8 unbound-bootstrap, and `REFUSED` are sealed owner results. Wrong generation/scope, stale source, fork, multiple transitions, or partial target recovery refuses before an acquisition mutation. | Constructible. |
| Protection context, semantic rebase projection, neutral projection, and mixed recovery | Protection authenticates raw state plus venue/execution context. Semantic projection comes only from an authentic applied protection transition. Neutral projection is minted only by the R11 private helper from the one zero-quantity sibling transition. Mixed recovery consumes the private exact acquisition proof. No policy is reconstructed in acquisition. | Constructible, subject to the separate preemption-intent P1. |
| `initialize_acquisition_controller` | Venue bootstrap + authority admission + serving refresh + exact no-protection state feed acquisition's genesis reducer; authority registration is the only currentness mutation. Target-unsafe, nonflat, nonclosed, wrong-owner, stale, or partial input returns the unchanged component set. A repeated call against advanced authority is stale; a repeated pure predecessor call is deterministic. | Constructible. |
| `begin_acquisition_generation` | The reducer derives `ABORTED` only for never-rooted/no-protection clear state and `COMPLETED` only for rooted, exact raw/semantic FLAT, closed/no-work state. Acquisition atomically retires A, inserts one LIVE B, advances ordinal/head/currentness once, and returns `protection=None`; authority owns registration. Wrong head/ordinal, temporary flat, stale raw state, live work, reconciliation, reused stream, or incompatible mandate leaves A unchanged. | Constructible for A → B → C with direct retained provenance. |
| `reduce_acquisition_controller` — current first/follow-on/revision | Venue supplies one authentic already-applied FILL/CORRECT/BUST relation; protection initializes or reduces once; acquisition records direct lineage and generation economics; authority registers the one `CANONICAL_FACT` currentness result. Replay/stale/fork/wrong relation cannot reapply aggregate economics. Reconciliation and conservative classifications are retained non-serving rather than dropped. | Fact recording is constructible; a non-normal fact needing BUY cancellation is blocked by the P1. |
| `reduce_acquisition_controller` — retired fact | Direct root/effect/owner/fact indexes classify the retired generation without scanning. Mixed recovery is protection-owned. With no current BUY mutation, one `CANONICAL_FACT` registration advances the head. With preemption, R11 specifies one ordered authority mutation and forbids a second registration. Replay or later revision updates only the direct retired record and aggregate binding once. | Direct fact/economics handling is constructible; the required combined fact/preemption branch is not constructible in the P1 state. |
| `rebase_acquisition_protection` — semantic | Exact `AcquisitionProtectionRebaseProjection` + `CURRENT` refresh + R9/R10 predecessor-semantic matcher feed acquisition; authority owns the single `PROTECTION_REBASE` registration. Wrong kind/disposition, stale state/head/context, altered projection, or post-success replay refuses unchanged. | Constructible. |
| `rebase_acquisition_protection` — neutral | Exact stale raw state + one `REFRESHED` sibling catch-up let the private protection helper independently derive the current raw state. The controller, registry, lineage, semantic commitments, currentness, permits, effects, and claims remain unchanged. The helper validates the transition relation rather than requiring the now-non-serving predecessor venue context to serve. Altered/nonzero/multiple transitions, stale cursor, copied neutral projection, semantic change, partial refresh, or repeated post-success call refuses all components. | Constructible. A goal-eligible caller can separately reproduce an authentic fresh protection transition from the same pure venue transition; neutral transport itself correctly emits none. |
| `create_acquisition_effect` | Serving refresh + exact current protection + complete terms feed acquisition's private permit mint; authority rechecks mandate/cap/head/currentness and alone creates the specialized BUY effect/receipt. Generic BUY remains refused. Changed terms, stale refresh/head, wrong scope/owner, cap, or replay cannot create a second effect. | Constructible. |
| `claim_acquisition_effect` | Direct effect view + serving refresh + exact current protection feed a fresh claim permit. Authority performs the final immediate currentness/ownership recheck and returns the sole fresh claim receipt; acquisition does not advance a head merely for a claim record. Retired-fact, changed head, claimed/unknown/open-invalid evidence, wrong occurrence, or replay refuses/no-ops without I/O authority. | Constructible. |
| `begin_acquisition_preemption` | R11 intends protection transition → private intent → acquisition permit request → authority-owned safe stand-down/one cancel → one ordered receipt/head result. Stale head, duplicate cancel, claimed/unknown work, and wrong owner are bounded refusals. | **Not total:** no lawful intent producer for the unresolved/baseline-gated cases identified in the P1. A non-goal transition cannot lawfully serve the current contract. |
| `create_acquisition_protection_exit` | After exact BUY closure, an authentic current applied transition with owner-produced SELL goal feeds the protection intent; authority rechecks residual/guard/budget/single-flight/currentness and alone creates or claims at most one protective SELL. Caller goals, stale transitions, wrong residual/guard/deadline, baseline/halt/exhaustion, duplicate work, or a final-head race refuse. | Constructible after BUY resolution; it must not be used to patch the preemption-only gap. |
| `project_acquisition_controller` | Acquisition authenticates its own current state and emits only bounded immutable status values, with no map, iterator, raw owner state, or authority capability. | Constructible. |

### Required counterexample conclusions

- **Neutral union:** `CURRENT` accepts semantic projection only;
  `REFRESHED` accepts exact raw-state neutral reprojection only. Wrong-disposition
  union members are ordinary refusal, non-union input is a pre-mutation type
  error, and a caller-supplied neutral projection cannot serve. One sibling
  catch-up is sufficient; a serving predecessor venue context is correctly not
  required. No partial composite or second registration is needed.
- **Exit intent:** caller-built goals, copied/inauthentic/stale transitions,
  changed raw context, residual, guard, deadline, provenance, head, or final
  claim are bounded by the owner seals and authority recheck. The disproof is
  the missing preemption-only producer, not a need to weaken SELL exit gates.
- **Terminality and A → B → C:** initialized-unused maps only to derived
  `ABORTED`; rooted exact-flat maps only to derived `COMPLETED`. Temporary flat,
  old protection, nonclosed/reconciliation/live work, reused stream, or
  incompatible mandate remains nonterminal. One phaseful current authority
  pointer may be replaced while immutable descriptor/lineage provenance remains
  direct; no history-derived decision or provenance deletion is needed.
- **Facts and races:** current/retired first/follow-on FILL/CORRECT/BUST relations
  and reconciliation variants can be classified directly and bound to the
  already-applied aggregate once. The one-receipt combined mutation avoids a
  second registration in shape, and a retired fact changes the head before
  final claim. It nevertheless cannot complete the combined mutation when the
  only exit intent is unavailable, which is the P1 above.
- **Boundedness and ownership:** no new public cache, iterator, scan, authority
  writer, policy constructor, venue private import, or currentness source is
  otherwise required. Persistent direct provenance indexes may grow as audit
  truth; live decisions use direct keys and constant-size current controller and
  authority pointers.

## Control adequacy and unverified limits

R11's neutral, terminality, fact-totality, race, and structural controls are
conceptually failure-capable and proportionate. The exit-ownership and
cross-side controls are individually negative but fail to compose the required
producer case: they demand both “no goal while unsafe” and “a goal-bearing
intent before cancel.” The additional preemption-only composition controls in
the finding are required before the RED contract is complete.

No runtime or failure-control execution was permitted, and no implementation
behavior is accepted. The large pinned application/test delta remains
feasibility context only. No ratification, implementation, persistence, broker,
or merge authority is granted by this result.

## Verdict

**BLOCK**

- P0: 0
- P1: 1
- P2: 0

Route-completeness conclusion: **No.** Every remaining route is constructible
except preemption when current BUY resolution is required but protection must
lawfully suppress SELL goal eligibility, including the required late-retired-
fact/no-current-baseline case. R11 cannot be accepted until that owner-intent
producer is separated and the changed exact candidate receives a fresh review.
