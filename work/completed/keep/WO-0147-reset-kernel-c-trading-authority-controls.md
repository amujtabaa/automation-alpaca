---
type: Work Order
title: "Reset kernel C: trading authority and manual controls"
status: CLOSED
work_order_id: WO-0147
wave: RESET-M1C
model_tier: strong
risk: high
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
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

## Pre-implementation static finding and bounded correction

Static clause comparison found one inherited M1B mismatch before any WO-0147 production edit.
`VenueEffectScope` currently requires `client_order_id` for every effect kind and carries no exact
cancel target. The accepted reset persistence contract requires nonempty creating identities only
for `SUBMIT`/`REPLACE`; `CANCEL` must retain `client_order_id=NULL`, target an existing identity
through immutable payload, and create no new venue owner. Treating a cancel as a creating effect
would make the new final-claim authority inconsistent with the accepted M2 representation.

The user's standing in-flight-remediation authority re-gates only the directly necessary correction
inside the already allowed `venue.py`, authority source, and execution-core tests: make creating
identity kind-aware; bind `CANCEL`/`REPLACE` to an exact existing target; prevent cancel effects from
creating owners; and add failure-first kind/target/identity/claim/replay tests. Do not edit or execute
the proposed DDL, persistence, adapters, runtime, or accepted ADRs. If the pure model cannot express
that contract without widening those paths, stop instead of inventing a second cancel authority.

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

## RED checkpoint 1 - public authority boundary (2026-08-02)

Before any production edit, the two new pure authority suites were frozen against activation SHA
`632c907`. Ruff check and format-check passed. The exact isolated run under
`BROKER_ADAPTER=mock` failed 17 tests: package-root raw capability export, two direct raw venue
admission bypasses, thirteen missing authority API/reducer contracts, and the generated public-
genesis machine. The tests now exercise positive create/final-claim/query mechanics through the
real reducer from a test-local forged environmental predecessor; they do not ship or require a
production hydrate/promote/refill/grant/test-state mint. No database, SQL/DDL, broker, credential,
network, runtime, artifact cleanup, or prohibited R1 result was used. This RED output is admissible
only as failure-first evidence; it makes no implementation claim.

## RED checkpoint 2 - complete authority contract (2026-08-02)

Independent review of checkpoint 1 found three P1 test gaps: the symbol and manual-flatten machines
and independent slow oracle were absent; final claims were not changed between creation and claim;
and the reconciliation-only fence was not distinguished from mutation authority. Production stayed
untouched while the RED contract was rebuilt to close those gaps and the remaining named work-order
obligations.

The candidate now contains exactly three bounded state machines (`ClaimAuthorityMachine`,
`SymbolGateMachine`, and `ManualFlattenMachine`), a materialized canonical symbol oracle, scalar and
same-scope execution-binding drift between effect creation and final claim, full target-bound
`CANCEL` identity/no-owner/acknowledgement semantics, BUY/SELL and exact residual boundaries,
query-only versus mutation fences, reserved budget use, one-shot emergency-grant scope and
consumption, manual-flatten stand-down/cancel/parent-closure progression, replay/conflict atomicity,
and audit-materialization traps on hot authority paths.

Two independent static re-reviews then found additional failure-capability gaps while production
remained untouched. The RED contract was corrected so `BeginManualFlatten` atomically creates the
exact target-bound cancel, kill-before-claim atomically stands down unclaimed requested work while
kill-after-claim preserves the claim, a final SELL claim re-reads a canonically reduced residual,
different-symbol execution drift advances an account-wide reconciliation epoch, the exact target
exemption cannot hide a safely-local sibling, and `RECONCILIATION_ONLY` cannot admit `CANCEL`.
Every reducer input is also applied twice from the same predecessor, and invalid effect-shape
examples now require the exact semantic `ValueError` instead of accepting a missing API as success.

The next two independent mutation reviews still found surviving simple wrong implementations, so
production remained frozen for a third RED repair. The exact candidate now also isolates the
book-owned account epoch from the execution flag; traps every audit materializer and persistent
sequence traversal on hot paths; rejects missing, terminal, cross-account, cross-symbol, and
economically mismatched cancel targets; distinguishes requested, claimed, acknowledged, rejected,
and outcome-unknown cancel effects; re-gates a cancel claim after a fence downgrade; proves the
normal `reserve + 1` boundary and reserved query exhaustion; proves query venue non-mutation and
identity conflicts; rejects every authority-command subclass; and persists replay/conflict
semantics across kill, begin-flatten, advance-flatten, effect-claim, and query-claim successors.
Manual-flatten histories now combine a safely-local BUY with multiple known cancellable legs,
refuse mixed safely-local/unknown work all-or-none, enforce session/mode/kill and one-final-SELL
boundaries, and re-gate the final manual SELL after both residual and supervisor-fence drift.

A subsequent exact re-review caught two permanent-test risks and three remaining edge gaps. The
account-epoch case now builds an independently clean snapshot rather than attempting to clear a
sticky reconciliation latch; the history guard permits bounded indexed reads while rejecting
materialization and more than a fixed small read count over 32-entry histories; and sealed command
classes may reject subclass creation before reducer entry. The contract additionally requires
account-wide kill to stand down all unclaimed requests across symbols while preserving claims,
one multi-acceptance BUY to emit one cancel per owned leg, mixed local/known/unknown flatten work to
refuse without partial mutation, a cancel target to remain cancellable at final claim, and an
emergency SELL to re-check late venue uncertainty and canonical residual shrink without consuming
its grant or budget.

Ruff check and format-check passed for both authority suites. The isolated pure run with
`BROKER_ADAPTER=mock` collected 99 tests and produced the intended `99 failed, 0 passed`. Every
deterministic example and each of the three bounded state machines is implementation-sensitive;
there is no inherited or accidental green case. No SQL/DDL, database, fixture that initializes a
database, broker, credential, network, persistence, runtime wiring, or prohibited R1 result was
used. This checkpoint remains failure-first evidence only and must pass an independent
test-contract re-review before production implementation starts.

Two independent final static re-reviews of these exact staged obligations returned `ACCEPT` with
no P0/P1 finding. One re-derived clause completeness and false-RED risk; the other re-derived the
named mutation controls, bounded-read proof, exact-type sealing, and account-wide kill behavior.
Neither reviewer ran tests or changed state. Production implementation may begin only from the
immutable commit containing this 99/99 RED checkpoint.

## In-flight implementation re-gate 1 - kill, cancel, and grant hardening

The implementation crossed the work order's same-lifecycle finding threshold during live review,
so work stopped at the failing focused gate and this section re-gates only the disclosed repairs
under Ameen's standing explicit authority to resolve all in-flight M1 findings. Paths and all
operational exclusions remain unchanged; this does not activate WO-0148 or any later work.

Fresh failure-capable review found that: a failed best-effort venue stand-down could prevent the
kill latch itself; manual-flatten readiness did not require its own generated cancel acceptance
parents to be `CLOSED`; two distinct cancel effects or flatten workflows could reserve the same
active target before any transport outcome; and a cancel command could carry an emergency SELL
grant, then consume an unchecked grant during claim. The first kill regression failed before its
fix and now passes. Three new cancel/grant negatives failed exactly while a definitive `REJECTED`
cancel correctly allowed one retry (`1 passed, 3 failed`), proving the added controls are live.
The same review also proved the first immutable authority indexes copied all accumulated applied
identity records on each transition. A 32-entry bounded-operation regression failed against that
implementation before replacement with the kernel's structurally shared persistent current map.

Authorized bounded repair: always latch kill while preserving the prior venue book if atomic local
cleanup cannot be established; require every retained flatten cancel parent to be closed before
`READY`; maintain one canonical active cancel-target reservation in the venue checkpoint and its
hydration/validation path; reject grants on every action except an exact reduce-only `SUBMIT SELL`;
and consume a grant only on that validated final claim. Add exact replay/rejection/release tests,
replace any history-copying authority index with bounded structurally shared current state, rerun
the full pure authority and affected venue suites, and submit the repaired candidate to a new
independent static and mutation pass. No persistence, SQL/DDL, adapter, runtime, broker, credential,
network, merge, deletion, cleanup, or later-slice work is authorized by this re-gate.

## In-flight implementation re-gate 2 - hydration and permanent identity hardening

Independent review reproduced a second cluster in the cancel lifecycle, triggering the work
order's explicit same-lifecycle stop condition again. The candidate was invalidated, the broad
execution-core run was stopped, and no later slice was activated. Ameen's standing explicit
authority to resolve in-flight M1 findings re-gates only these directly necessary repairs inside
the existing allowed paths and exclusions.

Fresh failure-first tests establish four boundaries. First, a canonically acknowledged cancel
places its target in pending `CANCEL`, but audit hydration rejects that reachable state because its
fold derives pending state only from explicit pending-operation inputs. Second, a forged cancel
whose target never had an owner hydrates successfully because ordered hydration does not validate
target history and reservation acquisition. The exact two-test run failed twice, once with
`active attempt requires exact observation and pending provenance` and once because the required
`ValueError` was not raised. Third, after registering one account symbol, an exact flat snapshot
for a second symbol is incorrectly rejected even though the venue reducer has a bounded new-symbol
registration path. Fourth, reused permanent request-occurrence and client-order identities are
classified only after mutable authority gates; under fence/kill/budget drift they return transient
`REFUSED` rather than stable `CONFLICT`. The exact three-case authority run failed three times with
those dispositions.

Authorized bounded repair: make ordered hydration derive target pending state from correlated
cancel acknowledgement and outcome-unknown inputs; validate each cancel/replace target's prior
owner, active state, economics, and exclusive reservation in input order, including release only
after a definitive non-dispatch/rejection outcome; admit a first effect for a later account symbol
only when the supplied registry state exactly matches the book-owned account registry; and expose
one private bounded venue-identity preflight so all permanent effect, request-occurrence, and
client-order conflicts precede mutable authority gates. Add exact reachable-state, forged-target,
temporal-overlap, later-symbol, and drifted-identity regressions. No persistence, SQL/DDL, adapter,
runtime, broker, credential, network, merge, deletion, cleanup, or later-slice work is authorized
by this re-gate.

### Re-gate 2 failure-capable repair checkpoint

Follow-up parity review widened the same authorized chronology repair without changing paths or
scope. Two exact tests proved that hydration admitted a target-bound claim after its target became
pending and admitted a pending-operation record before leg discovery (`2 failed`). Further ordered
counterexamples proved that a retry could be moved before the first cancel's definitive rejection,
a state-changing semantic pending alias could be ignored, a `CANCEL` effect could be forged as a
new venue-leg owner, and a first `SUBMIT` leg discovery could be moved before dispatch progress.
Each counterexample was reproduced against the candidate before its repair; none used operational
I/O, SQL/DDL, a database, broker access, or runtime wiring.

The bounded repair now folds every applied input in exact ledger order; acquires, retains, and
releases the one cancel reservation under the same states as the live reducer; rechecks the exact
target at both request and claim; derives cancel pending state from acknowledgement and recovery;
requires pending operations to follow discovery; refuses cancel-owned legs; and requires first
discovery to have live dispatch progress or a previously closed acceptance set. Exact semantic
rediscovery remains valid. On the exact current candidate, the focused ownership suite passes
47/47, authority plus the six affected venue files pass 407/407, all `tests/execution_core` pass
671/671, and the R2 conformance oracle passes 61/61 from a fresh workspace-local disposable test
directory.

`authority.py` crossed the work order's approximate 800-line review trigger. An independent split
review treated effect authority, manual controls, query authority, grants, and reducer state as
separate responsibilities and found no independently safe public or capability boundary to split.
Keeping one cohesive private semantic center avoids an additional importable grant/control seam;
the review therefore accepted the single module, subject to the same bounded-index and public-
surface tests. The latest authority-specific re-review returned `ACCEPT` with no P0/P1.

## In-flight implementation re-gate 3 - failure-capability and literal coverage closure

The first complete full-repository coverage run passed its configured whole-percent gate but
reported a raw combined result of only `25037 / 26951 = 92.89822270045639%`. That result was kept
as diagnostic evidence but rejected for the work order's literal 93% obligation. Seven focused
refusal/corruption cases then covered 32 previously missing authority line/branch outcomes and all
three venue authority-index validator limbs without changing intended production behavior.

A read-only false-green pass subsequently found that the close-before-claim hydration case made
two claim guards true at once. The candidate was invalidated. The second guard was redundant for
constructor-valid non-`NEVER_DISPATCHED` proofs, so it was removed; the retained exact-claim guard
remains the sole authority. The repaired test passes, while temporarily removing only that guard
fails with `DID NOT RAISE`. Further hardening added an explicit complete-enum pin, independent
forgery of each cached authority-index limb, and the missing composition in which `EngageKill`
must close an unclaimed `CANCEL`, release its target reservation, and permit a distinct cancel
retry while kill remains engaged.

The original mutation matrix killed 22/22 isolated mutants. `authority.py` remains at the exact
hash reviewed by that matrix. Both original venue-owned mutants were rerun against the current
venue hash and failed: raw `RequestedEffect` export and unknown-BUY flatten bypass. Six additional
exact-current mutants also failed independently: removal of the exact closure-claim guard; adding
an unclassified trading mode; removal of each of the three authority-index validation limbs; and
filtering `CANCEL` out of account-wide kill cleanup. Each temporary edit was restored in `finally`.
The reconciled mutation result is therefore 28/28 killed with zero survivor.

## Pre-review freeze checkpoint

The exact current production hashes are:

- `authority.py`: `751930a15922e0339e8383747b635bae5782d44f21e61069393c73bf4c7fb968`
- `venue.py`: `d465b85ff2113b49b6367c6244b327a25a68fbb5e6673b16c57969317cab7fe4`
- `identity.py`: `029beb0bf22af76c262aa707e90357633fb65336784e53ac5979518908ef9338`
- `__init__.py`: `6a2c4ab3e54754aab78025ada0163f41140e54a4ca4f01c1f2f85b6efa9acd65`

The definitive full-repository run collected 5,259 tests across 216 files and completed with
5,247 passed, 11 skipped, 1 expected xfail, and zero failures in 1,362.1 seconds. Raw combined
coverage is `93.02808801157657%` (`18,576/19,591` statements and `6,496/7,360` branches covered).
The retained exact evidence artifacts are:

- `.coverage_wo0147_full_authorized_6` SHA-256
  `ee68691cf8ad22b7d898ae1eb6cc2abd3981ad0e4b8bab23c5d4f32fecc09eca`
- `.coverage_wo0147_full_authorized_6.json` SHA-256
  `2a5dd6337cfe5b7e22f0d9fa8d21c478f54fb551776de5775fc95e7dc51f9698`

Ruff check and format-check pass over 20 execution-core source/test files, mypy reports no issue
across 8 execution-core modules, all 6 import contracts are kept, and `git diff --check` passes.
AI-OS install, version (`v0.9.1`), ledger, PKL, disposition, and exact-scope checks pass. The exact
scope inventory is 4 implementation files, 9 tests, and this active work order; no accepted ADR,
reset-queue record, legacy/runtime source, or CI workflow changed. Retained coverage artifacts are
evidence, not implementation scope, and were neither overwritten nor cleaned.

No `INV-*` identifier was added or amended since `REV-0048`; `INV-1` through `INV-9` remain
preserved rather than redefined. T1.1, T1.2, T1.3, T1.5, and T1.7 apply and now have enum,
mutation, cached-projection, choke-point, and consumable-lifecycle evidence. T1.4, T1.6, and T1.8
are narrowly not applicable because this slice is deterministic, pure, unwired, and has no clock,
store, persistence, or broker-write boundary. `REV-0049`, final disposition/Fable closeout, and
exact-head Python 3.11/3.12 CI remain mandatory; no review or completion verdict is claimed here.

## Independent-review re-gate 4 - provenance and lifecycle closure

The reviewer-owned `REV-0049/result.md` returned `BLOCK` and is preserved byte-for-byte in
`90b5bc4ed2e1ffb2c0056192fd85204d700c4b32` (19,168 bytes; SHA-256
`4ae21045ef136dd07f721400419409c575bedd54bf01bb9a2925fff56490e8ee`). The result reports one
reproduced P0 and two P1s. No conclusion from the interrupted reviewer turn was accepted; the same
independent seat completed the result from its already performed review work without expanding
scope.

The P0 proves that the public venue reducer accepts a caller-constructed
`CONTRACT_COMPLETE_RESPONSE`, closes an unresolved claimed BUY occurrence, clears canonical venue
uncertainty, and thereby permits a fresh final dispatch claim. The first P1 proves that a canonical
late residual change correctly refuses a manual-flatten SELL claim but leaves the stale unclaimed
SELL and flatten workflow permanently stranded. The second P1 proves that a positive forged/hydrated
predecessor may claim a broker query while still `BOOTSTRAPPING` because query admission omits the
engine phase.

Ameen's standing explicit authority to resolve all in-flight M1 findings re-gates only these three
repairs inside the existing allowed paths and exclusions. Before production changes, add
failure-capable controls that reproduce the public completeness-proof release, prove the close
capability is absent from package and module export lists and refused at the public reducer choke
point, exercise the complete query phase table with permanent identity before mutable phase, and
prove a late residual mismatch can retire only its exact unclaimed local manual SELL and claim one
fresh exact-residual replacement exactly once.

Authorized bounded repair:

- M1 fails closed on acceptance-set closure provenance. The public venue reducer admits no
  `CloseAcceptanceSet` command, and `AcceptanceProof`, `AcceptanceProofKind`, and
  `CloseAcceptanceSet` are removed from both public export lists. Their private representation and
  private reducer path remain only for deterministic audit hydration/replay, internal locally
  proven `NEVER_DISPATCHED` closure, and future M2 adapter-certified coverage integration. A shaped
  digest, evidence reference, or proof enum never grants public closure authority.
- Query claims explicitly allow only `RECONCILING` and `SERVING`; `BOOTSTRAPPING` refuses with
  `PHASE_BLOCKED` before any budget, query index, venue, or claim mutation. Permanent query identity
  replay/conflict remains earlier than this mutable policy gate.
- Reuse `AdvanceManualFlatten` rather than add a new public command. From `SELL_CREATED`, it may
  atomically stand down only the exact residual-stale, unclaimed, ownerless, reconciliation-clean
  local SELL and return that same workflow to `READY`. It retains all permanent effect,
  occurrence, client, authorization, and input tombstones; debits no budget and mints no claim.
  A replacement uses fresh identities and must pass the ordinary create and final-claim gates.

If closing the P0 requires trusting a caller coverage boolean, parsing adapter payloads, adding a
public certification capability, or pulling persistence/runtime/adapter work into M1, stop. If the
manual retry cannot use the existing atomic local stand-down proof without weakening final claim,
stop. No SQL/DDL, database, broker, credential, network, runtime wiring, cleanup, deletion, merge,
or later work-order activation is authorized by this re-gate. After RED, repair, focused/full
verification, and mutation controls, freeze a new implementation SHA and submit only the delta to
`REV-0049/request-addendum-01.md` for a fresh independent result addendum. WO-0148 remains inactive.

### Re-gate 4 RED checkpoint

Production remained byte-identical to implementation freeze `1d294e0`. Four focused test files
added only the disclosed failure-capable controls. The exact combined pure run under
`BROKER_ADAPTER=mock` collected 152 tests and produced `146 passed, 6 failed`. All six failures are
intentional and specific: the exact package surface still contains the three close/proof exports;
the explicit root/root-`__all__`/venue-`__all__` seal reports those same exposures; each of
`CONTRACT_COMPLETE_RESPONSE` and `COVERED_RECONCILIATION` is still accepted by the direct public
venue reducer; a `BOOTSTRAPPING` query incorrectly returns `APPLIED`; and a residual-stale
`SELL_CREATED` manual workflow incorrectly returns `REFUSED / MANUAL_FLATTEN_INVALID` instead of
performing safe local retirement.

The positive controls passed: both permitted query phases, permanent query identity before mutable
phase, claimed-SELL non-retirement, the unresolved BUY's exact `OPEN`/blocking projection, and all
pre-existing cases in the four files. Each isolated test pass and the combined run used no SQL,
database, broker, network, credential, runtime, or persistence action. Ruff check/format-check and
`git diff --check` pass for the RED files. This checkpoint proves missing behavior only; it makes no
repair or completion claim.

### Re-gate 4 FIX and GREEN checkpoint

FIX-P0 removes the unauthenticated public closure capability rather than trying to make a shaped
proof object trustworthy. `apply_venue_recovery_input` now refuses `CloseAcceptanceSet` together
with every other authority-changing internal capability, and `AcceptanceProof`,
`AcceptanceProofKind`, and `CloseAcceptanceSet` are absent from both package and venue export lists.
The internal representation remains available only to audit hydration/replay and reducer-owned
`NEVER_DISPATCHED` proof. The end-to-end regression first proves that the unresolved claimed BUY
blocks a control final SELL claim, then proves that each former public proof kind raises without
changing the book or authority view, and finally proves that another final SELL remains refused.

FIX-P1-query places an explicit phase allowlist after permanent query-identity replay/conflict and
before mutable query, venue, budget, or claim state. Only `RECONCILING` and `SERVING` may admit a
new query; `BOOTSTRAPPING` refuses with `PHASE_BLOCKED`. FIX-P1-flatten reuses
`AdvanceManualFlatten` at `SELL_CREATED`: only an exact residual-stale, unclaimed, ownerless,
reconciliation-clean local SELL can be stood down, and the same workflow returns to `READY` with
all permanent identity and authorization tombstones intact. A claimed SELL or any unresolved
sibling venue uncertainty remains non-retirable. The replacement must use fresh identities and
passes the ordinary create and final-claim gates exactly once.

The first post-FIX full state-machine run exposed a Hypothesis health-check failure at seed
`107785317444399141024773401385808604381`: only 9 generated examples satisfied a narrow manual
flatten precondition while 50 were filtered. This was a test-harness defect, not a production
failure. Adding an always-valid, non-mutating stage-audit rule made the exact seed pass without a
health-check suppression or weakened assertion. The final complete execution-core run passed
681/681 tests.

The exact-current mutation campaign killed 15/15 isolated mutants with zero survivor. Five P0
mutants removed the public close refusal or restored each forbidden root/module export. Ten P1
mutants removed or reordered the query phase gate, excluded a permitted phase, disabled residual
retry, removed its exact-residual or target-only clearance proof, discarded the returned venue,
broke `READY` restoration, retained the stale SELL identity, or erased authority tombstones. Every
mutant failed a focused control and every production file was restored byte-for-byte in `finally`.
The resulting production hashes are:

- `authority.py`: `e54ac1fe5ccdc74fceee096fc6cc506f0d3ddb4c5b4329860c4afcfc2247bd65`
- `venue.py`: `497af6f962f5a9f946da746385fc549631a41f69f896d7f859e0b289232eeffe`
- `identity.py`: `029beb0bf22af76c262aa707e90357633fb65336784e53ac5979518908ef9338`
- `__init__.py`: `51662457b0844331030821bbc1dcf1bd93bf0ea489425c021488766c316d125b`

Fresh exact-tree verification under `BROKER_ADAPTER=mock` passed:

- 152/152 focused re-gate tests and 420/420 affected authority/venue tests;
- 681/681 complete `tests/execution_core` tests;
- 61/61 R2 conformance-oracle tests;
- 5,269 collected repository tests: 5,257 passed, 11 skipped, 1 expected xfail, zero failures and
  zero errors in 1,336.922 seconds;
- raw combined coverage `93.02179069077972%`: 18,595/19,612 statements and 6,506/7,372 branches
  covered;
- Ruff check and format-check, mypy over all 8 execution-core modules, all 6 import contracts,
  `git diff --check`, and AI-OS install/version (`v0.9.1`)/ledger/PKL/disposition checks.

The repository-wide run exercised existing disposable test-only SQLite fixtures under the standing
authorized validation gate. It made no broker connection, used no credentials, changed no
persistent application database, and is not relied upon to prove the pure reducer semantics; the
failure-capable focused and mutation controls above supply that proof. Retained exact full-run
artifacts are:

- `.coverage_wo0147_rev0049_fix_full_1` (1,867,776 bytes), SHA-256
  `3cd154b7959e1965ec4113a8e43a1d0035fed7d79d95e8c9cf4f93ab08c474f3`;
- `.coverage_wo0147_rev0049_fix_full_1.json` (1,848,548 bytes), SHA-256
  `140da42695e891a025509d12a9cd80eaed357290b1449e618a052b26e26700c4`;
- `.pytest_wo0147_rev0049_fix_full_1.xml` (839,713 bytes), SHA-256
  `35de775e94f5b7440b0b859486e3ab304708aa36e450a7c7e43a3c56b37ba5d9`.

This checkpoint closes the author's three disclosed repair obligations but does not supersede the
reviewer's `BLOCK`. A new immutable implementation freeze and independent
`REV-0049/result-addendum-01.md` remain mandatory before any WO-0147 acceptance, disposition,
closeout, push, or WO-0148 activation.

## Author-side re-gate 5 - private closure and hydration certification

The first repaired freeze `98855655a5a51f04b7be95ba65c0c58fbef44b39` is preserved as negative
evidence and is not submitted for independent addendum acceptance. A hostile read-only preflight
disproved its P0 closure through two fresh pure probes. Direct explicit import of the module-private
proof/close types plus `_apply_venue_input` accepted caller-shaped external completeness metadata,
closed a claimed unresolved BUY, and changed a control final SELL from `VENUE_UNCERTAIN` refusal to
a fresh claimed dispatch effect with budget debit. Separately, `_audit_hydrate_book` accepted a
caller-replaced closed effect plus matching forged close input record and rebuilt the canonical
blocking projection from one to zero. The public wrapper and export lists remained sealed, but
underscore/`__all__` convention alone was not an execution barrier.

Both probes ran only pure in-memory Python against the exact freeze. No database, SQL, broker,
credential, network, persistence, runtime wiring, cleanup, or deletion occurred. The draft
`request-addendum-01.md` was not committed or delivered to a reviewer, and no reviewer verdict is
claimed. WO-0148's repaired-interface fit separately returned PASS with no new predecessor seam,
but its activation hold remains unchanged.

The standing authority to resolve in-flight M1 findings re-gates this exact P0 inside the existing
allowed paths and exclusions. External `CONTRACT_COMPLETE_RESPONSE` and
`COVERED_RECONCILIATION` proof values remain representable for exhaustive schema/state validation,
but they are inert authority in M1:

- fresh live closure through every reducer seam refuses unless the proof is exact reducer-derived
  `NEVER_DISPATCHED` with local cancel, no immutable claim, no claim record, and no active leg;
- full audit hydration rejects introducing or retaining an externally closed effect/proof/input
  because M1 has no adapter-certified complete-response or exact-query/coverage producer;
- future M2 must add a dedicated certified input derived from concrete adapter/query coverage
  facts and must never treat raw `AcceptanceProof` as the capability;
- positive tests of future post-certification lifecycle behavior may use a narrowly scoped test-only
  monkeypatch of one private default-deny certification predicate, but no shipping caller-mintable
  token or allow switch is permitted; and
- an AST/name boundary scans all production `app/**/*.py` outside `venue.py` and fails if code
  imports or references `_apply_venue_input`, `_audit_hydrate_book`, the close/proof representations,
  or the default-deny external-certification predicate. This is defense in depth; default reducer
  and hydration refusal are the primary control.

Before production changes, RED must independently reproduce both external proof kinds through the
private reducer, reproduce matching forged hydration, and prove the resulting closed parent releases
final claim authority on the failed freeze. It must also pin that no production module currently
references the forbidden internals. GREEN must leave the book/view unchanged and the final SELL
blocked, retain exact replay only for already canonical inputs, preserve reducer-owned
`NEVER_DISPATCHED` closure and hydration, and preserve future closed/invalidated lifecycle tests only
under the explicit scoped simulation.

Mutation controls must kill removal of live default-deny certification, admission of either
external kind, hydration validation removal, effect-only or input-only hydration checks, movement of
the gate after mutation, loss of exact replay, loss of `NEVER_DISPATCHED`, and weakening of the
production AST/name boundary. If complete hydration rejection cannot be proven without accepting a
caller boolean/token, or if M1 must parse/claim adapter evidence to pass, stop and leave the external
closure claim deferred to M2. No addendum review, acceptance, disposition, closeout, push, or later
work-order activation may begin until a new immutable freeze passes this re-gate.

### Re-gate 5 RED checkpoint

Production remained byte-identical to failed freeze
`98855655a5a51f04b7be95ba65c0c58fbef44b39`. The exact pure focused run under
`BROKER_ADAPTER=mock` collected 31 tests and produced 27 passes plus four intended failures. Each
external proof kind separately fails because `_apply_venue_input` returns `APPLIED` instead of
`REFUSED`, and each matching forged effect/input-ledger hydration fails with `DID NOT RAISE`.

Positive controls prove the public reducer and export lists remain sealed, the unresolved claimed
BUY begins with one blocking effect, and the new AST/name scan finds no production module outside
`venue.py` that references the private close/proof, generic reducer, hydration, or certification
names. The failure is therefore the missing default-deny semantic gate itself, not an already wired
runtime import. Ruff check/format-check and `git diff --check` pass. The RED run used no database,
SQL, broker, credential, network, persistence, or runtime action and makes no repair claim.

### Re-gate 5 FIX/GREEN and Sol hostile pre-flight

The repair keeps both external proof kinds representable but makes them inert authority in M1. One
private predicate returns `False` unconditionally for external closure. The live reducer refuses a
fresh non-`NEVER_DISPATCHED` close unless that predicate certifies it, and constructor/audit
hydration rejects any retained external proof under the same default-deny rule. Positive tests of
future M2 lifecycle behavior patch that predicate only inside a scoped test context. Shipping code
contains no caller token, boolean, public export, or allow switch. Reducer-owned
`NEVER_DISPATCHED` still requires `CANCELED_BEFORE_DISPATCH`, no occurrence claim, no immutable
claim record, and no active leg.

Replay identity remains prior to fresh authority evaluation. A close first applied inside the
test-only certified simulation replays outside that simulation as `EXACT_REPLAY`; a changed command
with the same input identity returns `CONFLICT`. Neither outcome changes the book, execution
snapshot, or quantity. The production-name boundary now pins the exact six protected spellings and
proves each is detected independently as a name, attribute, import, and literal string in synthetic
production syntax.

The first hostile mutation pass against the exact current production hash killed seven of eight
semantic mutants but exposed the missing replay-order pin; independent removal of each of the six
AST denylist members also survived. After adding the two controls above, the former replay survivor
failed both external-kind cases, and every individual denylist-member removal failed both the exact-
set assertion and its matching synthetic negative control. Reconciled re-gate-5 mutation evidence is
therefore 8/8 semantic mutants plus 6/6 boundary mutants killed, with zero survivor. Every temporary
edit was restored exactly. Relevant restored SHA-256 values are:

- `app/execution_core/venue.py`:
  `8a8a99161f0a0e5299d57700b97fe0c1739be948d93ca314c2e7b00936fb582c`;
- `tests/execution_core/test_import_boundary.py`:
  `8fb6a0d2920380bcdf8d83842293739e5296834d2fabbfda9564c5dff49d3cca`;
- `tests/execution_core/test_venue_provenance_hardening.py`:
  `4f427eab31a76de7c7be36648fce7fcb3fb56032274c942f968c159725ad9412`.

The Sol-led hostile read then re-derived the controls rather than relying on green output. Raw
external proof cannot close through the private reducer or constructor; exact replay cannot mint or
transfer authority; malformed same-ID input conflicts; no protected name occurs in production
outside `venue.py`; and the AST guard is only defense in depth, not the semantic boundary. No new
P0/P1 was found. This author-side conclusion is not independent acceptance.

Fresh exact-tree verification under `BROKER_ADAPTER=mock` passed:

- 39/39 focused provenance/import-boundary tests;
- 692/692 complete `tests/execution_core` tests;
- 61/61 R2 conformance-oracle tests using the verified-new disposable
  `.pytest_tmp_wo0147_regate5_r2_1` workspace after the restricted default temp root failed before
  fixture execution;
- Ruff check and format-check, mypy over all 8 execution-core modules, and all 6 import contracts;
- AI-OS install, version (`v0.9.1`), ledger, PKL, disposition, and exact activation-to-worktree
  scope checks; and
- `git diff --check`.

The definitive fresh full-repository run collected 5,280 tests and completed with 5,268 passed, 11
skipped, 1 expected xfail, zero failures, and zero errors in 1,257.711 seconds. Raw combined branch
coverage is `93.03101033677892%`: 18,601/19,617 statements and 6,509/7,374 branches, or
25,110/26,991 combined opportunities. The unchanged literal 93% floor passed. JUnit records the
expected xfail inside its 12 skipped outcomes. Retained artifacts are:

- `.coverage_wo0147_regate5_full_1` (1,867,776 bytes), SHA-256
  `6b0630f1a3714b041d3026ce68cdc3723e5fe5945e36841d82de2be4b4503455`;
- `.coverage_wo0147_regate5_full_1.json` (1,849,293 bytes), SHA-256
  `0939088464d2a1aba6fe913510ab6ac70cf5b501bcb12884c3282dce615c1545`;
- `.pytest_wo0147_regate5_full_1.xml` (838,295 bytes), SHA-256
  `628594ce31149d5c46f8b4ea67c6ff5c96d9c1b688fa8fd73b48a207144f4d5b`.

The repository-wide run used only existing disposable test-only SQLite fixtures under the standing
authorized validation gate. It made no broker connection, used no credentials, changed no
persistent application database, and is not relied upon to prove the pure reducer semantics. The
focused RED/GREEN, mutation, and hostile-preflight controls above carry that proof.

A bounded Terra read-only successor fit returned advisory PASS, and Sol independently re-derived
it: roadmap item 4 protection/trailing can continue through the public `CreateBrokerEffect`,
`ClaimEffect`, and authority reducer path without raw acceptance closure or private venue access.
Roadmap item 5 owns cross-side integration. WO-0149 activation must explicitly forbid scanning the
audit-only `VenueRecoveryBook.effects` collection and use authority-led handling or an approved
bounded projection instead. This does not activate WO-0148 or WO-0149.

The implementation is author-green but not accepted. A new immutable implementation freeze, an
updated `REV-0049/request-addendum-01.md`, a fresh independent `result-addendum-01.md` with no
unresolved P0/P1, closeout disposition, one final immutable SHA, push, and unchanged exact-head
Python 3.11/3.12 CI remain mandatory before WO-0148 activation.

## Independent-review interruption and author re-gate 6 (2026-08-02)

Two fresh independent Sol review contexts inspected the immutable re-gate-5 target
`41c7e956d1c49b450615a03374bd0ef7ee730357`. Both were interrupted by platform content
classification before either could write the designated `result-addendum-01.md`; no independent
verdict artifact exists, and none will be reconstructed by the implementation seat. The original
request and addendum remain unchanged historical evidence. Both contexts restored the exact tracked
baseline, and the branch remained clean apart from retained untracked evidence.

Before interruption, two independently reproduced findings were reported to the implementation
seat and then re-derived locally with pure in-memory transitions:

- **P0 - coordinated audit-checkpoint omission.** `_audit_hydrate_book` accepts a replacement in
  which an unresolved claimed BUY and every correlated effect, claim, identity, input, binding, and
  registry tuple are omitted together. The internally consistent empty result changes the bounded
  venue view from one blocking BUY to zero blockers. A control SELL is `VENUE_UNCERTAIN`; installing
  the accepted empty reconstruction changes creation and final claim to `APPLIED` and debits budget.
- **Blocking malformed-authority-state finding.** Reducer entry checks the exact outer state type
  but not its fields. Raw strings equal the string-valued phase/fence enums, and integer zero is
  false in the manual-kill guard. Fresh local cases admitted a query for raw phase/fence values and
  began manual flatten for `kill_engaged=0`. Exact severity remains for the next independent seat to
  adjudicate, but the finding blocks acceptance as at least P1.

Standing in-flight-remediation authority reopens only the existing WO-0147 allowed source, test,
review, and governance paths. RED must first pin coordinated total omission plus shallow exact types
for every top-level authority field. The bounded FIX is: M1 audit hydration verifies only an exact
semantic reconstruction of the supplied opaque checkpoint, while loading a distinct authenticated
persisted snapshot remains M2; and one constant-work state-shape validator runs before authority
replay, policy, property access, or mutation. No retained-history scan, caller approval value,
persistence, adapter, runtime, credential, broker, or database work is needed or permitted.

All re-gate-5 tests, coverage, and static results remain evidence for that frozen predecessor only.
Any production repair invalidates them for acceptance. The repaired target requires fresh focused,
execution-core, R2, repository-coverage, static/import/scope/AI-OS, failure-capability, Sol-led
failure-oriented pre-flight, and independent-review evidence before closeout or WO-0148 activation.

### Re-gate 6 RED, repair, and failure-capability checkpoint

The initial focused checkpoint exercised one coordinated omission case plus exact shallow
validation of all 15 top-level authority fields and the manual-flatten kill boundary. Before
production changed, all 17 cases failed: the empty-but-internally-consistent hydration replacement was accepted; raw
enum strings and integer-false kill state reached authority decisions; and malformed retained
state either passed or failed later through incidental attribute access instead of the reducer
entry boundary.

The bounded repair adds two private controls only. `_audit_hydrate_book` now compares the complete
semantic projection of its reconstructed result to the supplied opaque checkpoint and rejects any
replacement that omits correlated authority history. `_validate_authority_state` performs exact,
constant-work shallow validation before replay or decision logic, including exact enum/value
objects, exact Boolean kill state, non-negative integer budget fields, every retained index, and
the optional emergency grant. It does not scan history, create a public capability, accept caller
certification, or implement the deferred persisted-snapshot loader. The focused checkpoint then
passed 17/17, and the complete execution-core suite passed 709/709. Author pre-flight then found
that those tests did not distinguish validation before exact replay return from validation after
it. With that weakened ordering active, a new exact-replay case failed RED; restoring the entry
ordering made the expanded checkpoint pass 18/18 and the complete execution-core suite 710/710.

Five reversible failure-capability checks proved the new controls are causal rather than
decorative:

- removing the exact hydration projection comparison made the coordinated-omission test fail;
- removing reducer-entry state validation made 6 of 16 malformed-state cases fail decisively;
- weakening exact Boolean validation to equality-based membership made both integer-kill cases
  fail; and
- omitting `_query_by_id` from retained-index validation made its exact targeted case fail; and
- moving validation past the exact replay return made the dedicated replay-order case fail.

Every temporary edit was restored before continuing. Restored SHA-256 values are:

- `app/execution_core/authority.py`:
  `2ff53c9d790615c3594d13e3c08710c15d31c5ebebf661faf8e8bb50f13b8a6e`;
- `app/execution_core/venue.py`:
  `32d7d56a218a5ae35eefbe484723548778bb2fb9ef497a7bb4a3ec9ed560b276`;
- `tests/execution_core/test_authority.py`:
  `3bb281e30e9014926c7a2e2f1ef442cc3240cd47e80cf88d5180092ed0d6b79d`;
- `tests/execution_core/test_venue_provenance_hardening.py`:
  `0ebbe68d354d95ac8a0b3c619b5321963ebf2fd9767d8a633fdc56426bba19eb`.

Fresh exact-tree verification under `BROKER_ADAPTER=mock` passed:

- 18/18 focused re-gate tests and 710/710 complete `tests/execution_core` tests;
- 61/61 R2 conformance-oracle tests in the verified-new disposable
  `.pytest_tmp_wo0147_regate6_r2_2` workspace;
- Ruff check and format-check over all 20 execution-core source/test files, mypy over all 8
  execution-core modules, and all 6 import contracts;
- AI-OS install, version (`v0.9.1`), ledger, PKL, disposition, Fable, and exact
  activation-to-worktree scope checks; and
- `git diff --check`.

The first re-gate-6 repository run and its `_full_1` artifacts are retained but superseded because
the replay-order pre-flight added one failure-capable test afterward. The definitive exact-tree
repository run collected 5,298 tests and completed with 5,286 passed, 11 skipped, 1 expected
xfail, zero failures, and zero errors in 1,182.3 seconds (JUnit test time 1,176.538 seconds). Raw
combined branch coverage is `93.02945093976616%`: 18,621/19,640 statements and 6,523/7,388
branches, or 25,144/27,028 combined opportunities. The unchanged
literal 93% floor passed. JUnit records the expected xfail inside its 12 skipped outcomes. Fresh
retained artifacts are:

- `.coverage_wo0147_regate6_full_2` (1,867,776 bytes), SHA-256
  `0e293a1e089f05c1cf8b7cb1e7b3ef8bac769d34a9b8160e52d9503ce1349643`;
- `.wo0147_regate6_full_2.coverage.json` (1,851,366 bytes), SHA-256
  `7598598d565a1ca531a0ac7d0b6d49e52ad76fb7438b6dd629d2f020a5fcc424`;
- `.pytest_wo0147_regate6_full_2.xml` (841,048 bytes), SHA-256
  `90944e250030aaa1e72c2500170533cda577aec7769cc01828212c9b5582bab9`.

The full run used only authorized mock configuration and existing disposable test-only fixtures.
It made no broker connection, used no credentials, and changed no persistent application database.
At that checkpoint the author-side candidate was green but not accepted. Freeze, a new neutrally
worded independent review request/result pair, zero unresolved P0/P1, closeout reconciliation,
final push, and exact-
head Python 3.11/3.12 CI remain mandatory; WO-0148 remains inactive.

## Independent acceptance and conditional closeout

The final implementation freeze is `4e935851edd26f9f38ea93a9544815f5b49ecf88`. Neutral request
commit `e3936f07dbab9df534e75312062d8f3d1382e363` preserved the frozen target and assigned a fresh
independent Sol seat without inherited conversation context. Reviewer-owned result commit
`49e76c21659e5efcec8902f2403522750bdd53af` added only
`work/review/REV-0049/result-addendum-02.md`. The 13,236-byte result has SHA-256
`72bc191b9480e7aab3ae76e1eb69b612d4276c6cf7e871417c27c8c2b86e838e`.

The result returned `ACCEPT`. It independently closed the original completion-metadata P0, manual-
residual P1, and query-phase P1; the later private-closure P0; the coordinated checkpoint-omission
P0; and the malformed-state finding. Five fresh pure scenarios, 18/18 focused cases, 710/710
execution-core tests, static/type/import/diff checks, and two reversible failure-capability checks
passed. Baseline and final hashes matched the implementation freeze, and no new P0/P1 was found.
The two earlier platform-classified attempts remain no-verdict provenance and were not used as
acceptance evidence.

Final implementation-seat evidence is 18/18 focused cases, 710/710 execution-core tests, 61/61 R2
cases under `BROKER_ADAPTER=mock`, all static/import/AI-OS/scope checks, and a 5,298-test repository
run with 5,286 passed, 11 skipped, one expected xfail, zero failures/errors, and raw combined
coverage `93.02945093976616%`. The retained exact-tree artifacts and hashes are recorded in the
re-gate-6 checkpoint above.

This atomic documentation/governance reconciliation creates the immutable closeout candidate. Its
exact commit SHA is recorded externally by Git and as `HEAD` in the append-only ledger to avoid a
self-referential or evidence-only successor. The proposed `CLOSED` disposition becomes effective
only if that exact SHA passes the unchanged Python 3.11 and 3.12 workflow. Until then effective
lifecycle remains `REVIEW`; WO-0148 and every later slice remain inactive. A failed, canceled,
incomplete, or mismatched-head run reopens this same WO. No post-success evidence-only closeout
successor is permitted.

## Reconciled done criteria

```yaml
fable_done:
  task: "WO-0147 reset kernel C: trading authority and manual controls"
  done_when_results:
    - item: "Pure execution authority, request budgets, query claims, and manual controls are exact and deterministic."
      status: MET
      evidence: "The implementation freeze passed 710 execution-core tests; focused cases cover phase/mode/fence/kill/session, final claims, budgets, grants, venue uncertainty, query identity, manual lifecycle, malformed state, and exact replay."
    - item: "Caller-shaped closure or checkpoint state cannot mint authority, and every new safety control is failure-capable."
      status: MET
      evidence: "Five author controls and two independent controls turned the intended focused cases red before exact restoration; coordinated omission and malformed replay state both fail closed."
    - item: "Focused, static, R2, and repository coverage gates pass without runtime, persistence, credential, or broker dependency."
      status: MET
      evidence: "18 focused, 710 pure, 61 R2, all static/import/AI-OS/scope checks, and 5,298 repository tests passed; raw combined coverage is 93.02945093976616%."
    - item: "Independent review has no unresolved P0/P1."
      status: MET
      evidence: "REV-0049 result-addendum-02 returned ACCEPT at target 4e935851edd26f9f38ea93a9544815f5b49ecf88 after independently closing all six issue classes and restoring exact source/test hashes."
    - item: "Allowed paths and operational exclusions remain respected."
      status: MET
      evidence: "All implementation and closeout paths are allowed. No broker/Paper activity, credential use, persistent application database, runtime wiring, PR/merge, deletion, cleanup, or prohibited-R1-DDL reliance occurred."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "No in-scope P0/P1 remains. Persisted hydration, adapters, protection, acquisition, runtime composition, and cutover remain later gated work."
  deferred:
    - "External exact-head Python 3.11/3.12 CI is the effectiveness gate for this immutable closeout candidate; effective lifecycle remains REVIEW until it succeeds."
  status: VERIFIED
  verification_scope: "Implementation, static, scope, evidence, and independent-review gates only; no in-commit claim that later CI has passed."
  acceptance_condition: "EXTERNAL_EXACT_HEAD_CI_REQUIRED_BEFORE_WO_0148"
```

WO-0147 is retained with `[PKL_UPDATED, RESULT_SUMMARY_KEPT]`. No ADR changed. No packet, accepted
ADR, runtime, persistence, broker, credential, branch/worktree, or retained evidence artifact was
mutated or removed. The prohibited R1 DDL result was not used for any design, test, review, or
acceptance conclusion.
