---
type: Work Order
title: M2-I5 startup, reconciliation, and cold market recovery
status: ACTIVE
work_order_id: WO-0169
wave: M2-I5
model_tier: strong
risk: critical
disposition: []
owner: Codex implementation seat; fresh-context review seats REV-0116 and REV-0117
created: 2026-08-21
predecessor: WO-0168 closeout c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51 / tree de844054db45d03c73889d986185cab651cbc386
branch: codex/m2-wo0169-startup-cold-recovery-r1
preflight_review_id: REV-0116
implementation_review_id: REV-0117
execution_authority: >
  Ameen Mujtabaa's recorded serial-M2 authority in
  work/queue/M2-EXECUTION-2026-08-21/34-M2-COMPLETION-DRIVE.md, his instruction
  "You may proceed with the remaining sequence", and his current instruction to continue the best
  of M2 authorize ordinary reversible WO-0169 implementation, exact fake-capability and fresh
  pytest-owned file-database tests, governance, commits, pushes, bounded fresh review, root
  correction, closeout, and WO-0170 preparation. No DDL-byte change, configured or in-memory
  database, migration, runtime composition, credential, broker/network call, order, promotion,
  master merge, history rewrite, M3 implementation, or real process-lock/adapter implementation is
  authorized.
allowed_paths:
  - app/execution_core/persistence/startup.py
  - app/execution_core/persistence/owner_lock.py
  - app/execution_core/persistence/market_recovery.py
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/persistence/unit_of_work.py
  - app/execution_core/venue.py
  - app/execution_core/authority.py
  - app/execution_core/acquisition.py
  - app/execution_core/position.py
  - app/execution_core/protection.py
  - tests/execution_core/test_persistence_startup.py
  - tests/execution_core/test_persistence_cold_recovery.py
  - tests/execution_core/test_persistence_startup_hydration.py
  - tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  - tests/execution_core/test_persistence_unit_of_work.py
  - tests/execution_core/test_import_boundary.py
  - work/queue/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/completed/keep/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/review/REV-0116/**
  - work/review/REV-0117/**
  - work/ledger.jsonl
forbidden_paths: []
---

# Work Order: M2-I5 startup and cold recovery

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Active from exact accepted WO-0168 closeout; preflight required before source edits

`[FABLE • FULL • spec-first/TDD • fake capabilities only, no broker network]`

## Context and goal

Implement fail-closed process ownership, startup integrity, unknown-effect reconciliation, and the
accepted ADR-023 cold market restart sequence. The exact build may enter `SERVING` only after every
direct proof and capability gate passes. Tests use injected/fake capabilities; no broker call or
credential is authorized.

## Functional requirements

- FR-1: Startup MUST acquire one process-lifetime owner lock before database or adapter work; a second process
  cannot write or dispatch, and uncertain takeover remains non-serving.
- FR-2: Startup MUST verify immutable datastore/application/profile identity, schema/version, checkpoint,
  direct-route totality, one-LIVE/controller uniqueness, current heads, claim/owner/closure
  consistency, and supervisor-fence coordinates.
- FR-3: Startup MUST enforce `BOOTSTRAPPING -> RECONCILING -> SERVING`; a successful open is never enough.
- FR-4: Startup MUST convert stranded/in-flight/unknown claims to deterministic reconciliation without blind
  retry; require complete targeted query/stream coverage before release.
- FR-5: Startup MAY classify ADR-023 warm-exact only with quiescence, atomic last-cursor publication, and
  proof of no later publication.
- FR-6: Otherwise startup MUST invalidate volatile market authority before adapter work, obtain a
  source-authoritative post-ack fence, require strict `F > cursor` or the exact initial no-cursor
  exception, exclude buffered `<=F`, deliver one baseline at `F`, then permit `>F` work.
- FR-7: Unsupported or incomplete source capability MUST remain reconciliation-only/non-serving.
- FR-8: Startup MUST use direct current proof; no full facts/receipts/retired-generation/owner/
  closure/tape scan may manufacture serving authority.

## Non-functional requirements

- Fake/injected adapter, query, stream, filesystem, and lock capabilities only.
- Deterministic virtual time and bounded startup/query counts.
- No configured database, credentials, outbound network, orders, or real broker/market source.
- Every refusal retains exact reason/evidence coordinates without secret or raw account material.

## API Contracts

One startup coordinator owns explicit phases and returns a typed serving or non-serving result.
Owner lock, effect reconciliation, and market recovery remain separate injected capabilities; none
may directly mutate reducer state or bypass M2-I4.

N/A — no HTTP or real external service API exists. The Python coordinator consumes injected lock,
repository, query, and stream capabilities and returns one typed phase/serving/refusal result.

## Activated contract reconciliation

The controlling ADR-023 R1 body is the unchanged file whose embedded proposed wording is immutable
provenance. Acceptance is recorded separately in
`docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`; its exact controlling SHA-256 is
`9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf`.

WO-0169 deliberately implements **cold startup only**. It does not implement or infer ADR-023
warm-exact service. Cold-only denial is simpler and safer; a future warm path would need its own
proof of quiescence, atomic last-cursor publication, and no later publication.

### Exact public surface

`startup.py.__all__` is exactly:

- `StartupDisposition`
- `StartupPhase`
- `StartupRefusalCode`
- `StartupRequest`
- `StartupResult`
- `start_startup`

`StartupPhase` is exactly `BOOTSTRAPPING`, `RECONCILING`, `SERVING`, `NON_SERVING`.
`StartupDisposition` is exactly `SERVING`, `NON_SERVING`. Refusal codes distinguish owner denial or
loss, datastore/current-proof failure, unresolved effects, invalidation failure, unsupported source,
fence failure, baseline failure, and internal integrity failure without retaining secrets.

`StartupRequest` contains only exact immutable selection coordinates: application-generation ID,
expected execution-profile ID, and expected market-source-profile ID. It contains no owner object,
checkpoint/context, path, connection, callback, credential, adapter, caller fence, or serving
boolean. `StartupResult` is an exact immutable value containing the final phase/disposition,
optional refusal code, optional process-lifetime `OwnerLeaseEvidence`, and optional authenticated
successor context. Only a `SERVING` result may expose a lease and successor context. A non-serving
return deliberately exposes no stale context; a retry reacquires ownership and reloads the latest
committed checkpoint by the same immutable selection coordinates.

`owner_lock.py` exposes only `OwnerLeaseEvidence` and `OwnerLockPort`. The port has exact acquire,
currentness, and release roles. Evidence is factory-issued, immutable, noncopyable, and bound to
one port/owner occurrence. The coordinator acquires it before the first connection or adapter/query
method call and revalidates it before and after every external-capability step and immediately
before returning `SERVING`. Denial, uncertainty, loss, or malformed evidence is non-serving; no
takeover heuristic exists.

`market_recovery.py` owns narrow exact effect-query and market-source ports plus immutable evidence
values. Ports provide observations only: they cannot mutate reducer state, mint serving authority,
or receive a generic callback/registry. Every observation is coordinate-checked and applied only
through the accepted M2-I4 unit-of-work boundary.

### Owner-locked cold hydration boundary

The accepted persisted checkpoint is intentionally inert. Checkpoint bytes alone never mint a
serving owner or proof. Only after acquiring the process owner lease, startup may:

1. load the current inert envelope using the request's immutable application/profile coordinates;
2. derive its exact `KernelCheckpointRecord` and request one current
   `RuntimeCheckpointSelectionProof` by direct keys;
3. decode each canonical owner component into private checkpoint candidates;
4. invoke owner-module-private restore constructors for venue, authority, acquisition, execution,
   and protection, each requiring both its exact candidate and the relevant sealed repository
   proof/current rows; and
5. project the restored owners through the accepted checkpoint projector and require byte-identical
   payload, digest, owner commitments, scope order, and current head before forming a private
   `UnitOfWorkContext`.

The new restore constructors are private, add no `__all__` member, cannot operate from bytes or a
digest alone, and must reject stale/spliced proof, omitted current rows, forged candidate types,
and cross-scope/profile/application substitution. Dormant scope rows restore only dormant `None`
owners. The restored context remains private until the final `SERVING` result. An
invalidation-commit/source-refusal/retry test proves the second call reloads committed C1 rather
than requiring caller-retained C0.

### Private startup invalidation bridge

The accepted eight-member public `M2Operation` union and all public UOW exports remain unchanged.
One private unit-of-work entry point may persist system-owned cold-start market invalidation. It:

1. begins one explicit `BEGIN IMMEDIATE` transaction after owner-lock acquisition;
2. authenticates the supplied owner context against direct retained checkpoint/current proof;
3. applies only `invalidate_position_protection_market` to exact current projections;
4. persists any changed protection/controller/cursor rows and one canonical successor checkpoint
   under the existing runtime write lease;
5. authenticates its sealed capability-bound decision before commit; and
6. returns either the exact successor context, exact replay, or fail-closed refusal.

This private lifecycle transition is not a ninth external durable-input domain and creates no
caller-shaped operation, DDL, receipt bypass for an external input, effect, or dispatch authority.
Its idempotence and checkpoint successor are the durable recovery evidence. No adapter/query task
may start until the committed invalidation result has returned normally.

### Exact startup sequence

1. Validate exact request shape without touching the connection.
2. Acquire and validate process owner evidence.
3. Verify schema/application/profile identity, load the exact inert runtime checkpoint/current
   proof by direct keys, restore owners only through proof-bound private constructors, and require
   a byte-identical reprojection. Hydrate no authority from explanatory history.
4. Enter `RECONCILING`; enumerate the complete authenticated current-unresolved effect union from
   the checkpoint selection proof: OPEN, qualifying INVALIDATED, and qualifying closed-late-owner
   rows. Query every exact claimed unresolved identity through the injected effect-query port and
   apply returned existing venue-recovery items through M2-I4. Never submit or resend an effect;
   unclaimed rows are not queried or treated as evidence of prior dispatch.
5. Reload direct proof and require complete resolution/coverage.
6. Persist cold market invalidation through the private UOW bridge before calling the market port.
7. Subscribe to the exact selected source/profile/generation/mode and retain exact acknowledgement.
8. Obtain a source-authoritative post-ack fence `F` that covers every possibly pre-ack emission.
   With a retained cursor require strict `F > cursor`; equality fails. The exact no-cursor initial
   case omits only that predecessor comparison. Maximum/exhausted coordinates fail.
9. Require proof that buffered observations `<= F` were excluded, obtain one canonical non-halted
   baseline occurrence exactly at `F`, and apply it through the existing market-occurrence UOW.
10. Reload exact current proof, require committed baseline state with no evidence/goal authority,
    require exact subscription currentness still bound to the same acknowledgement, fence, source
    profile, stream generation, and sequence mode, revalidate the owner lease, repeat subscription
    currentness immediately before return, then and only then return `SERVING`. Startup does not
    process later `> F` work.

### Frozen CR-01 through CR-19 matrix

- CR-01: owner lock is acquired before any connection/query/stream capability call.
- CR-02: second owner, stale evidence, uncertain takeover, or malformed lease is non-serving.
- CR-03: lease loss after database access begins fails closed before the next capability step.
- CR-04: schema, application, execution profile, market profile, or selected identity mismatch
  refuses startup.
- CR-05: stale, changed, forged, or noncanonical checkpoint proof refuses startup.
- CR-06: every retained scope has direct-route totality and exactly one LIVE/controller authority.
- CR-07: current heads, claims, owners, acceptance, closure, and supervisor-fence coordinates agree.
- CR-08: owner-locked hydration uses proof-bound private owner construction and byte-identical
  checkpoint round trip; non-serving retry reloads the latest committed context.
- CR-09: stranded claims are found from the complete authenticated current-unresolved union without
  history scans, including qualifying invalidated and closed-late-owner rows.
- CR-10: every exact claimed member of that union receives one targeted query and complete coverage.
- CR-11: phases are monotonic; successful open or reconciliation entry is never serving.
- CR-12: market invalidation commits idempotently before the first source/adapter call.
- CR-13: subscription binds selected source profile, stream generation, sequence mode, and
  retry-stable coordinate.
- CR-14: the post-ack fence proves coverage of every coordinate possibly emitted before ack.
- CR-15: a retained cursor requires strict `F > cursor`; equality and regression fail.
- CR-16: buffered/replayed observations `<= F` never reach the protection reducer.
- CR-17: baseline exactly matches generation/mode/epoch/freshness/non-halt requirements.
- CR-18: the baseline commits before serving, counts as no evidence, and emits no goal.
- CR-19: stream-currentness loss at any point, including after baseline commit and immediately
  before return, plus lease loss, crash, incomplete query coverage, or unsupported capability,
  remains reconciliation-only/non-serving.

### Boundedness and failure evidence

Normal startup may traverse the exact scope tuple and each scope's current open-effect tuple, but
its query count is bounded by those current rows and is invariant under unrelated retired/fact/
receipt/tape history growth. No generic retry loop, background task, plugin registry, callback
graph, new lock table, or configurable recovery framework is admitted. Tests use exact fake lock,
query, and source ports plus explicit fresh pytest-owned file databases only where the existing
SQLite repository/UOW must be integrated.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Startup phase/result | Bootstrapping, reconciling, serving, or non-serving refusal | Monotonic allowed transitions; successful open is insufficient |
| Owner lease/lock evidence | Exact process-lifetime ownership coordinates | One owner; uncertainty/loss fails closed |
| Reconciliation item | Claimed/in-flight/unknown effect plus coverage state | Deterministic identity; no blind retry; complete coverage required |
| Market recovery state | Profile, stream generation/mode, cursor, fence, baseline | ADR-023 exact ordering and source-authoritative proof |

## Acceptance Criteria

### AC-1: Ownership and integrity gate all startup work (FR-1, FR-2, FR-3)

Given two-owner, stale-lock, lock-loss, identity/profile/fence, route/head, and claim/closure mutants
When startup attempts to progress phases
Then adapter work and `SERVING` remain impossible and the exact refusal is retained

### AC-2: Unknown effects reconcile without blind resend (FR-4)

Given stranded, in-flight, and outcome-unknown claims with complete or incomplete coverage
When reconciliation evaluates deterministic identity and coverage
Then only fully resolved occurrences may progress and no uncertain effect is blindly resubmitted

### AC-3: Market restart obeys exact ADR-023 order (FR-5, FR-6, FR-7)

Given warm-exact, no-cursor, equality-fence, buffered, unsupported-source, and crash variants
When the injected market recovery capability runs CR-01 through CR-19
Then only the exact accepted sequence reaches a fresh baseline and every mutant remains non-serving

### AC-4: Startup work is history-bounded (FR-8)

Given target/stress unrelated history growth
When normal startup loads direct current proof
Then query/work shape remains bounded and history-fold mutants fail

## Edge Cases

- EC-1: Owner lock loss after database open but before serving returns non-serving and disables
  mutation/dispatch eligibility.
- EC-2: Fence equal to retained cursor fails strict `F > cursor`; only the exact no-cursor initial
  exception can proceed.
- EC-3: Source cannot prove post-ack coverage or emits unsupported coordinates; baseline is not
  delivered and current market authority remains invalidated.

## Activated allowed paths

```yaml
allowed_paths:
  - app/execution_core/persistence/startup.py
  - app/execution_core/persistence/owner_lock.py
  - app/execution_core/persistence/market_recovery.py
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/venue.py
  - app/execution_core/authority.py
  - app/execution_core/acquisition.py
  - app/execution_core/position.py
  - app/execution_core/protection.py
  - tests/execution_core/test_persistence_startup.py
  - tests/execution_core/test_persistence_cold_recovery.py
  - tests/execution_core/test_persistence_startup_hydration.py
  - tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  - app/execution_core/persistence/unit_of_work.py
  - tests/execution_core/test_persistence_unit_of_work.py
  - tests/execution_core/test_import_boundary.py
  - work/queue/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/completed/keep/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/review/REV-0116/**
  - work/review/REV-0117/**
  - work/ledger.jsonl
```

This list is authoritative together with the frontmatter. Any additional production path requires
an explicit work-order scope amendment and preflight re-review before editing.

## Out of scope and completion

- OS-1: Production adapter/runtime composition and broker/network/credentials/orders — fake injected
  capabilities only.
- OS-2: Configured DB and live/shadow — forbidden; temporary accepted M2 persistence only.
- OS-3: M2-I6 execution, M3, promotion, and `master` merge — later separately authorized work.

Completion requires RED, CR-01..19 and failure-capable mutants, focused/static/full-governance
evidence, independent P0=0/P1=0 acceptance, exact publication, and an M2-I6 handoff.

## REV-0116 preflight disposition

Fresh preflight returned `ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0. All three findings are accepted
and preserved unchanged in `work/review/REV-0116/result.md`: caller-held live context made cold
retry impossible, literal OPEN-only reconciliation omitted current unresolved variants, and final
service did not revalidate subscription currentness. The reconciled contract now owns those roots
through immutable request coordinates plus owner-locked proof-bound hydration, the complete
authenticated unresolved union, and final-edge subscription-currentness checks. Source remains
held until one correction-only `REV-0116/result-r1.md` returns zero open P0/P1.
