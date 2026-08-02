# REV-0049 independent review result

## Pre-registered attack properties

Recorded before reading the frozen implementation, implementation tests, or the later
RED/re-gate/evidence checkpoints in WO-0147. These properties are derived only from `AGENTS.md`,
ADR-020, ADR-021, the reset-beta scope/exclusions in ADR-022, M1 roadmap item 3, and WO-0147 from
`Activation and authority` through `Stop conditions`.

| ID | Property to falsify | Pre-registered counterexample / attack |
|---|---|---|
| AP-01 | The only supported public semantic center is `apply_execution_authority_input`; raw request, dispatch-claim, supervisor/fence promotion, grant mint, and positive-predecessor capabilities are not package-root importable. | Enumerate package exports and direct module callability; try public construction, re-export, subclass, duck type, dataclass replacement, forged enum/value, and raw venue input paths that could create positive authority without the reducer. |
| AP-02 | Public genesis is exactly `BOOTSTRAPPING + HALTED + UNAUTHENTICATED`, zero capacity, no grant, and no positive authority predecessor. No public M1 input promotes phase/mode/fence, clears kill, replenishes capacity, or mints a grant. | Construct every public state/input type directly, including copied/replaced dataclasses and booleans used as integers; search for any constructor/default/import that permits `ACTIVE`, `REDUCING`, `SERVING`, `PAPER_MUTATION_ELIGIBLE`, positive budget, kill clearance, flatten progression, or an emergency grant. |
| AP-03 | Actor, reason, evidence, truthy objects, semantic aliases, and raw venue facts are attribution/data only and never authenticate authority. Exact enum/type totality is deny-by-default. | Supply metadata that claims supervisor approval, `True` where an integer is expected, subclasses/duck types, wrong enum families with equal-looking values, raw strings, and a newly simulated unclassified enum member. |
| AP-04 | One action-aware classifier is used at admission, effect creation, and final claim, with permanent identity/replay conflicts checked before mutable policy gates. | Create valid work, drift phase/mode/fence/kill/session/binding/residual/account epoch/venue uncertainty/target/budget/grant before final claim, and compare create-versus-claim decisions; replay permanent IDs after mutable denial to see whether stable conflict is incorrectly downgraded to transient refusal. |
| AP-05 | `ACTIVE`, `REDUCING`, and `HALTED`/kill have the exact asymmetric permissions: exposure-increasing BUY is denied outside `ACTIVE`; reduce-only capped SELL is allowed in `REDUCING`; `HALTED` denies submit/replace/ordinary flatten/hard-bail SELL but still permits cancel/query/reconcile. | Exhaust the action x mode x kill x side/effect table, including semantic aliases and cancel/replace target variants; attempt to use emergency or manual paths as a generic replacement/submit bypass. |
| AP-06 | SELL authority uses the current exact `authorized_residual_sell`; negative quantity means zero and oversized or stale requests refuse rather than clamp/`abs`. | Create a SELL under valid authority, then lower/zero/negative residual before claim; try quantities at, below, and one unit above the boundary and verify no venue/budget/grant/manual partial mutation on refusal. |
| AP-07 | Symbol execution authority is canonical, account-wide where required, and cannot be bypassed by a target exemption, sibling/cross-symbol hiding, stale account epoch, copied history, caller summary, or per-symbol cache. | Combine target plus sibling effects across symbols and account epochs: safely-local, claimed-without-leg, cancellable, unknown, and `OPEN`/`INVALIDATED` parent states; attempt exemption of anything except the exact `REQUESTED`, unclaimed, ownerless, reconciliation-clean target. |
| AP-08 | All four safety projections (`_cancel_target_reservation_by_leg`, `_authority_contribution_by_effect`, `_authority_summary_by_scope`, `_account_unclaimed_requested_effect_ids`) have canonical producers/updaters, hydration rebuilders, validators, and executable consumers; no hot path scans unbounded audit history. | Trace each index from genesis/import through create, claim, cancel/recovery/hydration, terminal closure, replay/conflict, and readiness; corrupt or omit each cache in a test-local copy/monkeypatch and require validation or a decisive behavior failure rather than trusted caller state. |
| AP-09 | Acceptance/ownership ambiguity is conservative: acknowledgement, outcome-unknown, terminal leg, not-found, `OPEN`/`INVALIDATED` parent, checkpoint reordering, alias, or forged cancel owner cannot release symbol or flatten readiness; only exact `CLOSED` does. | Build multi-leg and cancel histories where known legs become terminal but parent remains `OPEN`, inject late acceptances/reordered checkpoint data, and forge cancel target/owner scope; verify ambiguity remains and closure cannot be copied or inferred. |
| AP-10 | Kill latches and stands down account work atomically without altering already claimed work or blocking the cancel/query/reconcile operations needed to resolve uncertainty; cancel reservations cannot be stranded. | Apply kill before and after create/claim across symbols, replay kill, combine it with outstanding cancel reservations and grants, and look for partial stand-down, resurrection, claimed-effect mutation, or loss of recovery actions. |
| AP-11 | Manual flatten is an all-or-none state machine: safely-local BUY work is stood down, exact known cancellable BUY legs reserve/request cancellation, acknowledgement remains nonterminal, unknown/potentially-live work refuses, every parent must be `CLOSED`, residual is re-read at final claim, and at most one final SELL is emitted. | Use multiple BUY effects/legs with mixed local, claimed, cancellable, acknowledged, terminal, `OPEN`, `INVALIDATED`, and unknown states; reorder progress, replay commands, drift residual, and force one refusal mid-transition to detect partial mutation, duplicate final SELLs, budget/grant consumption, or generic replace behavior. |
| AP-12 | One account budget meters mutating claims and query/cancel/reconcile claims. Normal work cannot consume the safety reserve. Success debits exactly once; refusal, conflict, and exact replay debit nothing. Query claims create no effect/owner/attempt. | Exercise zero/reserve/boundary capacity, cross-symbol competition, exact replay, changed replay, query reservation, cancel reservation, release/retention, and a boolean-as-integer amount; inspect whether any query or recovery route is unmetered or creates venue state. |
| AP-13 | Emergency reduction is an immutable account/symbol/session-scoped, non-stackable, one-shot grant used only for an eligible reduce-only SELL in `HALTED`; it uses the smaller trustworthy long quantity, cannot bypass uncertainty, and is consumed only in the same successful claim transition. | Try ambient/missing/mismatched/cross-scoped/reused grants, two grants, non-SELL and ordinary actions, stale/oversized residual, venue uncertainty, insufficient budget, replay, and late state drift; verify no refusal consumes or transfers the grant. |
| AP-14 | Cancel reservations are exact per leg/target, cannot be forged or cross-scoped, remain while cancellation is unresolved, and are released only by canonical terminal/closure state without double debit or capacity leakage. | Reserve against one leg then substitute effect/client/owner/account/symbol/occurrence, replay or change the request identity, acknowledge without terminality, close siblings or parents out of order, hydrate, and attempt a second reservation/claim. |
| AP-15 | Every enum and reused side/effect/acceptance/disposition member is explicitly total; adding an unclassified member fails decisively. Every safety pin has a failure-capable test rather than a vacuous green assertion. | Inspect exhaustive branches and test parametrization; independently monkeypatch a real final-claim, cancel-reservation, cache, kill, or manual-control choke point and require a focused test or public counterexample to fail. |
| AP-16 | This M1 slice stays pure and deterministic: no I/O, clock/UUID/random read, persistence/SQL/ORM/schema/migration, broker SDK/network, runtime/API/UI wiring, logging-as-authority, or audit-history-derived decision; claim data is not dispatch. | Inventory imports/calls and exact changed paths, scan for prohibited modules and side effects, replay identical predecessor/input, and distinguish an immutable claim from any broker call or dispatch-success assertion. |
| AP-17 | Frozen-object and scope claims are exact: target is `1d294e0ac29dcd169a4733df3aa9cbd337dc8787`, base is its declared review base, and the range contains only the fourteen listed paths. | Verify object existence/type/parentage, exact range path inventory, worktree independence, and diff-check. Treat any accepted ADR/reset queue/legacy/runtime/store/adapter/API/UI/CI change as blocking. |

### Hostile perspective assignments

- **Production saboteur:** AP-02, AP-04 through AP-14, and AP-16; seek partial mutation,
  replay/policy-drift disagreement, budget leakage, false release, and authority escalation.
- **Context-free maintainer:** AP-01, AP-03, AP-08, AP-14, AP-15, and AP-17; seek hidden callable
  seams, non-total vocabulary, cache contracts that cannot be reconstructed, and misleading tests.
- **Safety/data-integrity reviewer:** AP-01 through AP-17; seek any human-gate bypass, position or
  dispatch authority leakage, caller-minted provenance, ambiguity release, and prohibited scope.

## Independent evidence and attack outcomes

Frozen-object checks established that `1d294e0ac29dcd169a4733df3aa9cbd337dc8787` is a commit whose direct parent is the packet's stated base, and that the base-to-target path set is exactly the 14 paths declared in `request.md`. The review checkout is the request-only child commit; every reviewed source and test path was byte-identical to the frozen target. Existing untracked coverage artifacts were left untouched.

| Attack property | Outcome | Evidence level |
|---|---|---|
| AP-01, AP-02, AP-03, AP-04, AP-05, AP-06 | No additional defect promoted beyond the findings below. Reducer dispatch is exact-type, genesis is deny-only, identity conflicts are checked, and create/final checks are separate. | static trace plus focused suite |
| AP-07, AP-08, AP-09 | The four venue-derived safety projections are rebuilt and validated, but their truth can be changed by the caller-authored acceptance-proof path in Finding 1. | reproduced-live plus static trace |
| AP-10 | Kill engagement is monotonic in the authority reducer. | static trace plus focused suite |
| AP-11 | The final manual-flatten claim re-reads residual quantity, but a late-change refusal leaves no ordinary retry transition; see Finding 2. | reasoned-only |
| AP-12, AP-13, AP-14, AP-15, AP-16 | Budget/grant/cancel classification and reducer totality had no additional promoted defect in the inspected boundary. | static trace plus focused suite |
| AP-17 | Frozen target and declared path set matched. | reproduced-live |

## Findings

### P0 — Caller-authored “contract complete” metadata can erase venue uncertainty and authorize final dispatch

**Anchors:** `app/execution_core/venue.py:755`, `app/execution_core/venue.py:762`, `app/execution_core/venue.py:7230`, `app/execution_core/venue.py:7239`, `app/execution_core/venue.py:7240`, `app/execution_core/venue.py:7255`, `app/execution_core/__init__.py:75`, `app/execution_core/__init__.py:81`, `app/execution_core/__init__.py:130`, `app/execution_core/__init__.py:156`.

`AcceptanceProof` is a public, directly constructible value whose claimed kind, evidence reference, and digest are entirely caller-selected. `CloseAcceptanceSet` is also public, and `_close_acceptance_set` verifies scope/claim correlation and the absence of registered active legs but does not establish the semantics promised by `CONTRACT_COMPLETE_RESPONSE` (nor bind that proof to an adapter-certified complete response or an exhaustive exact-occurrence query). The package root then exposes both the proof/close inputs and `apply_venue_recovery_input`, so the check is not merely an inaccessible private seam.

The pure reproduction created and claimed an unresolved BUY effect with no known legs. A control SELL was refused with `VENUE_UNCERTAIN`. It then supplied `CONTRACT_COMPLETE_RESPONSE` with the effect's public scope/claim ID, the arbitrary reference `caller-self-attested-complete`, and `b"P" * 32`. The public recovery reducer returned `APPLIED` and marked the BUY parent `CLOSED`. Repeating the SELL path after that forged closure returned `APPLIED` at create and `APPLIED` at final claim, with a fresh claim issued and budget consumed. A separate control/exploit run produced the same closure and release sequence.

This bypasses the venue-uncertainty predicate at the human-gated final dispatch-claim boundary. ADR-020/ADR-021 allow closure only from authoritative, occurrence-complete evidence; arbitrary well-shaped metadata cannot supply that authority. The defect is reachable through the package's public pure API and changes whether a potentially conflicting order may be dispatched.

**What resolves it:** remove generic caller-authored acceptance proofs from the public authority-changing surface, or make closure a reducer-owned result derived from concrete, coverage-validating adapter facts. For every proof kind, validate the authoritative producer and the evidence semantics, not only identifiers and a digest-shaped byte string. Add a negative end-to-end reducer test showing that caller-selected metadata cannot close an unresolved parent or release a final dispatch claim.

### P1 — A legitimate late residual change can strand manual flatten with no retry transition

**Anchors:** `app/execution_core/authority.py:731`, `app/execution_core/authority.py:746`, `app/execution_core/authority.py:783`, `app/execution_core/authority.py:796`, `app/execution_core/authority.py:879`, `app/execution_core/authority.py:887`.

Creating the manual-flatten SELL irreversibly moves the workflow from `READY` to `SELL_CREATED`. The final claim correctly re-reads residual quantity and refuses if a late canonical fill changes it. That refusal returns the unchanged predecessor: the stale SELL remains requested and the workflow remains `SELL_CREATED`. A replacement create using the same flatten ID is rejected because create accepts only `READY`; a new flatten workflow is also not an ordinary recovery path while the prior requested SELL still contributes venue uncertainty. No non-kill transition cancels/re-sizes the stale request and returns the flatten workflow to a retryable state.

This is fail-closed at the immediate claim, but it can permanently remove the manual-flatten safety control precisely under the late mutable-state condition the final check is intended to handle. The inspected tests cover refusal, but not a complete recovery/retry after that refusal.

**What resolves it:** define an explicit all-or-none retry transition for a residual mismatch: atomically retire the stale unclaimed SELL, recompute the exact residual, and return to a retryable phase (or create the replacement under the same workflow) without weakening kill/fence/venue checks. Add a pure probe that inserts a late canonical fill between create and claim, observes the refusal, and then proves an exact replacement can be claimed once and only once.

### P1 — Query claims are not phase-gated by the authority state machine

**Anchors:** `app/execution_core/authority.py:956`, `app/execution_core/authority.py:964`, `app/execution_core/authority.py:973`, `app/execution_core/authority.py:979`, `app/execution_core/authority.py:997`.

`_claim_query` checks the reconciliation fence, scope, and budget, but never checks `AuthorityPhase`. Consequently, any hydrated/forged predecessor with positive query capacity and the reconciliation fence can mint a fresh broker-query claim even while still `BOOTSTRAPPING`. ADR-020 places `BOOTSTRAPPING` before the dispatcher/command-serving task and makes phase part of the semantic authority center; capacity plus fence must not silently make that phase command-capable. The focused tests exercise positive query claims in `RECONCILING` but do not pin a `BOOTSTRAPPING` refusal.

**What resolves it:** add an explicit total phase classifier for query claims and permit only the phases the ADR names as command-capable. Add negative tests for `BOOTSTRAPPING` and every other non-permitted phase using an otherwise-valid positive predecessor.

## Novel pure probes

| Probe | Setup and oracle | Observed outcome |
|---|---|---|
| Public construction/provenance | Claimed unresolved BUY; no known legs; control SELL; caller-constructed `CONTRACT_COMPLETE_RESPONSE`; retry SELL through final claim. | Control `REFUSED / VENUE_UNCERTAIN`; forged close `APPLIED`; post-close create `APPLIED`; final claim `APPLIED`, fresh claim present. Finding 1. |
| Late mutable drift | Traced the manual workflow across create, final residual re-read, unchanged-state refusal, and retry classifier. | Immediate mismatch is denied, but the retained `SELL_CREATED` state has no ordinary retry transition. Finding 2 is reasoned-only; a dedicated executable recovery probe is still missing. |
| Cross-scope / account-epoch / cancel-parent | Traced cache keys, hydration rebuild/validation, all-effect contribution, exact-target exemption, retained cancel-parent closure, and account-level reconciliation contribution across the full claimed venue boundary. | No separate defect promoted. The required additional novel executable cross-scope probe was not completed; this result does not treat existing tests as independent proof. |

## Failure-capability evidence

The provenance reproduction is itself failure-capable: the same state and SELL input refuse while the unresolved BUY is open, then pass only after the caller-authored proof changes the venue state to closed. This control/exploit pair demonstrates that the challenged acceptance check is decisive rather than incidental. No source or test mutation was made.

## Mechanical gates

| Gate | Fresh result |
|---|---|
| Exact focused eight-file pytest command from the packet | PASS (100%) |
| `tests/execution_core --maxfail=1` | PASS (100%) |
| Ruff check | PASS — `All checks passed!` |
| Ruff format check | PASS — `20 files already formatted` |
| Mypy over `app/execution_core` | PASS — 8 source files |
| Import-linter | PASS — 6 kept, 0 broken |
| Frozen range whitespace check | PASS |

## Not verified

- No SQL, database, broker, network, runtime-adapter, coverage, full-repository, or cleanup action was performed, per the packet exclusions.
- External Python 3.11/3.12 CI was not independently observed.
- Because the required late-drift and cross-scope probes were not both completed as executable probes before review close, they are reported at their actual evidence level rather than treated as passing evidence. This does not affect the blocking public-provenance reproduction.

## Verdict

BLOCK
