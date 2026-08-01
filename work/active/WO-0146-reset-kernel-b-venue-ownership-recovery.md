---
type: Work Order
title: "Reset kernel B: venue ownership and recovery lifecycle"
status: ACTIVE
work_order_id: WO-0146
wave: RESET-M1B
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-08-01
branch: codex/arch-reset-2026-07-r1
base_sha: dfb8ed30ebed788f1158d7f8be49b44d505c355b
staged_source: work/queue/ARCH-RESET-2026-07/06-roadmap.md#M1--Pure-reference-kernel
predecessor: WO-0145
activation_ci: "GitHub Actions run 30706138534 (#677): Python 3.11 job 91385483099 SUCCESS; Python 3.12 job 91385483131 SUCCESS"
---

# WO-0146 — Reset kernel B: venue ownership and recovery lifecycle

`[FABLE • FULL • verification: DIRECT + independent review • task: pure venue-recovery kernel]`

## Activation and authority

Ameen explicitly approved all four proposed next actions on 2026-08-01: activate RESET-WO-02,
produce a read-only branch/worktree retirement manifest, land the five M1 slices as one independently
reviewed non-squashed master milestone, and begin only manifest-approved retirement after exact
merged-master CI. This activates only RESET-WO-02 as canonical `WO-0146`; later M1 slices remain
sequentially gated. The accepted ADRs, preserved safety core, and staged roadmap remain controlling.

The exact predecessor closeout `dfb8ed30ebed788f1158d7f8be49b44d505c355b` passed unchanged
Python 3.11/3.12 CI and independent review with no unresolved P0/P1. No credentials are available or
needed. Force `BROKER_ADAPTER=mock`; do not discover or use credentials, call Alpaca Paper, perform
broker/network I/O, execute SQL/DDL, initialize a database, alter persistence, wire runtime code,
open or merge a PR, or delete/clean any branch, worktree, or artifact during this WO. Existing
database-bearing suites may run only under the prior disposable-test-database authorization; their
legacy fixtures are evidence, not a dependency of this pure slice. The prohibited R1 DDL result is
inadmissible and supplies no design or acceptance evidence.

## Fable gate

```yaml
fable_gate:
  goal: "Build the deterministic venue-effect, one-to-many ownership, closure, ambiguity, and ADR-012 recovery semantic center without I/O or persistence."
  assumptions:
    - claim: "ADR-020/021, ADR-012, and M1 item 2 uniquely determine the pure venue-recovery boundary."
      status: VERIFIED
      evidence: "Clause comparison and AR-02/AR-05 counterexamples agree; adapter completeness and persistence remain later typed inputs/gates."
    - claim: "Human-attested intervals can share the canonical fill fold without a second arithmetic lane."
      status: VERIFIED
      evidence: "WO-0145 already carries authority on root heads; WO-0146 admits it only after exact leg/capacity/cumulative/evidence/long-only checks."
    - claim: "Standing human authority covers this slice and in-scope remediation without activating later slices."
      status: VERIFIED
      evidence: "Ameen approved options 1–4; this work order records their sequential gates and exact exclusions."
  approach: "Commit this docs-only gate, write RED examples/state machines and mutation pins, implement one pure atomic transition seam across venue and recovery state, refactor, then independently review."
  alternatives_considered:
    - "Reuse Spine v2 recovery/store code — rejected because it remains read-only evidence and mixes persistence/runtime concerns."
    - "Infer closure from known-leg terminality or not-found — rejected because AR-02 proves latent acceptances."
    - "Apply later broker evidence unconditionally after attestation — rejected because it can double-count one interval."
  out_of_scope:
    - "SQLite, schema, migration, DDL/SQL, stores, event repositories, adapters, SDKs, network, broker, UI/API, clock, or runtime wiring"
    - "Trading modes, kill/manual controls, request budgets, complete symbol_may_execute, and final-claim authority (RESET-WO-03)"
    - "Protection/trailing (RESET-WO-04), acquisition/cross-side integration (RESET-WO-05), RTH/native handoff, and predictive liquidity"
    - "External cutover/credential/origin/rollback proof beyond generation/client/owner identity rejection"
    - "PR, merge, branch/worktree/artifact deletion, or cleanup"
  done_when:
    - behavior: "Named examples and generated histories prove effects versus attempts, AR-02 multi-acceptance/closure, AR-05 compaction/closure chains, restart, and status precedence."
      test: "Focused venue ownership and stateful suites"
      command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_venue_ownership.py tests/execution_core/test_venue_stateful.py"
    - behavior: "ADR-012 human fill/release and matching/mismatching later broker evidence are exact, idempotent, capacity-safe, long-only, and non-global."
      test: "Focused recovery suite"
      command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_venue_recovery.py"
    - behavior: "Every named safety mutant fails live and the restored tree passes focused/static/full gates on Python 3.11/3.12."
      test: "Mutation ledger, import boundary, repository gates, unchanged CI"
      command: "Run documented mutants; Ruff, mypy, import contracts, AI-OS, R2/full coverage, then exact-head dual-version CI."
    - behavior: "Independent exact-head review reports no unresolved P0/P1."
      test: "Reviewer-owned M1B packet"
      command: "Blind spec-first review of exact diff, tests, mutation evidence, and deferred claims."
  blast_radius: "Only the pure app.execution_core package, isolated tests, and WO/PKL closeout records; no incumbent runtime or schema consumer."
  rollback: "Revert only WO-0146 commits while preserving WO-0145, the retirement manifest, all worktrees, and preserved artifacts."
```

## Split-review stop and bounded re-gate (2026-08-01)

The first-pass green result is superseded. Because `venue.py` crossed the roadmap's approximate
800-line split-review threshold, hostile Saboteur, New-Hire, and Safety/Security passes re-derived
the slice and reproduced four P0 classes plus multiple P1s. Commit `865ebc2` freezes 20 failing
counterexamples; its tests pass Ruff/diff checks but are intentionally RED. Work stopped before any
WO-03 activation, closeout, PR, merge, runtime, database, broker, or retirement action.

The P0s were: unreserved matching broker evidence could later apply a second delta; a forged public
checkpoint could omit claim/provenance and admit human authority; a released leg could accept later
human economics; and an `INVALIDATED` parent did not permanently refuse release.

The user's standing authorization for in-flight findings and options 1-4 re-gates only bounded
WO-0146 remediation; it does not waive the stop, broaden paths, activate WO-03, or authorize any
runtime/schema/broker/credential/merge/deletion action. Remediation must reserve corroborating facts
at zero delta; deeply validate claim/scope/owner/closure/input/coverage checkpoint coherence; require
an active `NEEDS_REVIEW` leg for human fills; block invalidated/released paths; remove forged operator
status ingestion; enforce release cumulative/capacity/terminal parity; finalize only after all legs
and the parent close; preserve replay/conflict integrity and occurrence uniqueness; use one pending
absence representation and valid closure successors; and bind acceptance proof to exact scope,
occurrence, claim, and immutable evidence. Adapter certification remains a later typed input.

No prior green output is admissible. Fresh focused/static/mutation evidence and a new independent
exact-head `REV-0048` result are mandatory.

## Independent checkpoint re-review and second bounded re-gate (2026-08-01)

The remediation green following the split review is also superseded. Three fresh independent
reviewers attacked checkpoint construction, execution binding/restart, and revision/closure
semantics. They reproduced additional P0/P1 failures: late acceptance after closed rejected or
never-dispatched outcomes was refused instead of invalidating; retained operator authority could be
rewritten; checkpoint evolution helpers allowed reconciliation/history stripping; human authority
could survive removal or reordering of its review gates; cross-symbol account-registry advancement
stranded otherwise valid snapshots; human/corroborated truth could not be safely hydrated; sibling
fills bypassed effect-wide capacity; and revision replay, post-closure conflict, bust/status, and
non-tail mapping cases could wedge or falsely preserve finality. The reviewers added failure-first
contracts in the three dedicated hardening suites listed below. No reviewer changed production.

Ameen's standing authorization for all in-flight findings re-gates these directly necessary
WO-0146 corrections only. It does not activate WO-0147, authorize runtime/schema/database/broker
work, or authorize merge, deletion, or cleanup. The accepted remediation boundary is:

- keep public broker hydration strict while adding venue-provenance hydration for exact retained
  human roots and zero-economic corroborations;
- admit only cryptographically monotonic account-registry projection, record every catch-up outcome,
  and quarantine independently advanced owned-symbol truth until attribution is resolved;
- commit indexed prefix and broker-root-count proofs without materializing retained history;
- make the checkpoint object read-only by moving all construction capability to module-private
  verified functions;
- replay control-plane input order so first human authority exists only after the exact effect and
  leg both reached `NEEDS_REVIEW` and before release;
- bind every coverage, corroboration, revision head/history, reconciliation, closure, and registry
  outcome to its exact source input; semantic aliases must point backward to a retained direct
  source and can never replace it;
- require effect-wide capacity, exact revision lineage/mapping, current closure parity, clean
  execution bindings, and no unresolved evidence for `OPERATOR_RECONCILED`; later contradictions
  demote the effect to `NEEDS_REVIEW` rather than leaving a falsely serving final state.

All earlier green claims remain inadmissible. Fresh focused/stateful/static/mutation/full-suite and
exact-head independent evidence are required after the final production freeze.

## Fresh implementation checkpoint evidence (2026-08-01, pre-review)

The production source was restored after every mutation and then frozen for this checkpoint.
Current-source evidence:

- deterministic execution-core contract: 318 passed across fill, import-boundary, ownership,
  recovery, binding/restart, checkpoint, and provenance suites;
- fill/position state machine: 7 passed; venue state machine: 2 passed;
- Ruff: all execution-core source/tests passed; mypy: 7 source files passed; `git diff --check`:
  passed;
- five live safety mutants were killed by their focused pins: removing unresolved registry release
  blocking; removing the ordered effect review gate; allowing an alias to replace its direct
  provenance source; removing effect-wide sibling overfill latching; and allowing unresolved
  execution-integrity bits in an operator-final checkpoint. The restored source passed all six
  parametrized/targeted mutation pins.

These are implementation-seat results, not acceptance. No SQL/DDL, database engine or fixture,
broker adapter, Alpaca activity, credential, network, runtime wiring, merge, deletion, or cleanup
was used. Full repository/R2 evidence and independent exact-head `REV-0048` remain mandatory.

## Frozen semantic contract

- Add exact generation/effect/occurrence/client/claim/closure/evidence identities and immutable full
  scope binding. `SUBMIT`, `CANCEL`, and `REPLACE` effects start `REQUESTED` with canonical
  `acceptance_set_state=OPEN`; creating client identities are nonblank and generation/account unique.
- Effect edges are `REQUESTED -> CANCELED_BEFORE_DISPATCH | DISPATCH_CLAIMED`, then claimed to
  `ACKNOWLEDGED | REJECTED | OUTCOME_UNKNOWN`, unknown to acknowledged/rejected/needs-review, and
  needs-review to operator-reconciled only after every owned leg is closed/released and the parent
  acceptance set is exactly `CLOSED`. The immutable claim is recorded with the claim edge. A
  stranded claimed effect becomes `OUTCOME_UNKNOWN`; it is never resent.
- Attempt order status and pending submit/cancel/replace operation are orthogonal. Acknowledgement is
  quantity-neutral and cannot terminalize an attempt. A fill during cancel/replace ambiguity updates
  economic truth without clearing that ambiguity. Delayed statuses cannot regress terminal/higher
  state; new canonical economic facts still apply.
- One effect owns zero, one, or many immutable concrete broker-order identities. Same exact owner is
  replay; cross-effect/generation/client/occurrence/symbol/side/economic scope is conflict and cannot
  overwrite. Every owner has exactly one active/unresolved leg or one current terminal-closure head.
- Terminal compaction removes only the active leg and appends the sole ordinal-1 closure root.
  Successors must name the same owner's immediately prior ordinal. Duplicate roots, gaps, stale or
  cross-owner predecessors, and branches fail closed. Later economics append the next closure; stale
  status cannot reactivate a closed leg.
- Acceptance edges are only `OPEN -> CLOSED -> INVALIDATED`. `NEVER_DISPATCHED` requires local
  cancellation and provable absence of an immutable claim. Other closure kinds are typed externally
  established `CONTRACT_COMPLETE_RESPONSE` or `COVERED_RECONCILIATION` facts; M1 never invents
  adapter completeness. Known-leg terminality, not-found, and position parity do not close `OPEN`.
  Late acceptance preserves the closure proof, appends contradiction evidence, and makes the set
  permanently `INVALIDATED`; no reopen/re-close exists.
- `IngestHumanAttestedFill` carries exact leg/effect/claim occurrence, stable source/root identity,
  price, incremental and prior/resulting cumulative quantity, actor, reason, and evidence. It may
  call the one canonical root-fill primitive only after exact binding, `NEEDS_REVIEW`, full-payload
  idempotency, order-capacity, cumulative-interval, and long-only checks. Its root authority is
  `HUMAN_ATTESTED`; it has no correction/bust or broker-overfill power.
- Human coverage is the half-open exact leg interval `(prior_cumulative, resulting_cumulative]` with
  committed economics. Later broker evidence matching that interval corroborates with zero second
  delta; an exactly disjoint uncovered interval may enter the broker fact reducer; partial overlap,
  changed economics, or unprovable mapping records reconciliation with zero guessed delta.
- `ReleaseVenueLeg` requires exact ownership, broker-terminal evidence, and equality of cumulative
  venue quantity to canonical fills attributed to that leg. It changes no economics/integrity,
  clears only that leg, releases no sibling or parent set, and creates no successor. Exact retry is
  a no-op; changed actor/reason/evidence/identity/economics conflicts.
- Keep `apply_broker_execution_fact` broker-only and broker-authoritative overfill exact. Broker
  correction/bust cannot revise a human root. Human support must not duplicate position arithmetic.

## Scope

```yaml
allowed_paths:
  - app/execution_core/identity.py
  - app/execution_core/fills.py
  - app/execution_core/position.py
  - app/execution_core/venue.py
  - app/execution_core/recovery.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_fill_position.py
  - tests/execution_core/test_fill_position_stateful.py
  - tests/execution_core/test_import_boundary.py
  - tests/execution_core/test_venue_ownership.py
  - tests/execution_core/test_venue_recovery.py
  - tests/execution_core/test_venue_stateful.py
  - tests/execution_core/test_venue_binding_recovery.py
  - tests/execution_core/test_venue_checkpoint_hardening.py
  - tests/execution_core/test_venue_provenance_hardening.py
  - work/active/WO-0146-reset-kernel-b-venue-ownership-recovery.md
  - work/completed/keep/WO-0146-reset-kernel-b-venue-ownership-recovery.md
  - work/review/REV-0048/**
  - work/ledger.jsonl
  - pkl/log.md
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
activation_only_paths:
  - README.md
  - docs/04_IMPLEMENTATION_PLAN.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
  - work/queue/ARCH-RESET-2026-07-M1-BRANCH-RETIREMENT-MANIFEST.yaml
forbidden_paths:
  - app/store/**
  - app/events/**
  - app/broker/**
  - app/api/**
  - app/monitoring.py
  - app/main.py
  - app/server.py
  - ui/**
  - docs/adr/ADR-020-current-state-execution-kernel.md
  - docs/adr/ADR-021-position-protection-liquidity-execution.md
  - docs/adr/ADR-022-reset-beta-scope-cutover-governance.md
  - work/queue/ARCH-RESET-2026-07/**
  - .github/**
```

`REV-0048` is reserved for the independent M1B review seat; the implementation seat may create
`request.md` and `disposition.md` but never reviewer-owned `result.md`. The manifest-covered packet
and accepted ADR bodies remain byte-immutable. Existing oversized `fills.py`/`position.py` edits are
limited to the verified human-root seam; material restructuring is a stop. `venue.py` and
`recovery.py` expose one atomic transition API rather than competing reducers.

## Required failure-capable evidence and stops

Named deterministic, independent-oracle, and Hypothesis histories must kill: ACK-as-terminal;
status regression; singular broker-ID overwrite; terminal-leg-closes-`OPEN`; false
`NEVER_DISPATCHED`; late-acceptance reopen; owner rebind; closure root/gap/branch/cross-owner bugs;
human over-capacity/negative SELL; release economic/global mutation; changed evidence retry;
attested/broker double count; claimed-effect resend; terminal-history scan/materialization; and
commitment/equality omissions for claim, proof, owner scope, closure head, or human evidence.

Stop if interval mapping needs a second economic lane, persistence, or adapter inference; if attempt
state cannot retain orthogonal cancel/replace ambiguity; if closure must infer completeness; if
WO-03 policy is needed; if PA-03 needs endpoint/credential/legacy rollback work; if broker-only
overfill or revision guards weaken; if runtime/schema/broker/ADR changes become necessary; or if two
P0s or three same-root P1s emerge. Close only after focused/full/static/dual-version gates and blind
review pass, then append one ledger row and reconcile PKL. Do not activate RESET-WO-03 here.
