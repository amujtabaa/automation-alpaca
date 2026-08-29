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
  - tests/execution_core/test_persistence_write_capability.py
  - tests/execution_core/test_import_boundary.py
  - tests/execution_core/test_position.py
  - tests/execution_core/test_sqlite_boundary.py
  - tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
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

**Status:** Active from exact accepted WO-0168 closeout; REV-0116 R1 accepted P0=0/P1=0/P2=0

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
3. decode each canonical owner component into private non-serving checkpoint candidates;
4. invoke owner-module-private compact restore constructors for venue, authority, acquisition,
   execution, and protection, each requiring both its exact candidate and the relevant sealed
   repository proof/current rows;
5. require exact semantic agreement for every payload-owned scalar and bounded current/active/
   unresolved row, direct-proof coordinate, scope order, current head, and dormant/active shape;
   and
6. atomically persist one normalized compact-owner successor checkpoint together with cold market
   invalidation before forming the private serving-eligible `UnitOfWorkContext`.

The loaded payload remains byte-identical and hash-authenticated but explicitly inert. Inherited
history-shaped behavior commitments are integrity evidence, not reproducible serving authority:
the accepted predecessor deliberately omitted the history needed to rebuild them. Compact restore
constructors therefore rebuild only complete bounded current/active/unresolved semantic state,
leave omitted audit history omitted, and cut over to newly derived compact commitments in the
successor. Future operations that address omitted history remain governed by the accepted
operation-keyed direct-proof boundary; no default-empty answer may decide them.

The new restore constructors are private, add no `__all__` member, cannot operate from bytes or a
digest alone, and must reject stale/spliced proof, omitted current rows, forged candidate types,
and cross-scope/profile/application substitution. Dormant scope rows restore only dormant `None`
owners. No restored candidate is serving authority before the compact cutover commits and is
reread exactly. The context remains private until the final `SERVING` result. A cutover-commit/
source-refusal/retry test proves the second call reloads committed C1 rather than requiring
caller-retained C0.

### Private startup invalidation bridge

The accepted eight-member public `M2Operation` union and all public UOW exports remain unchanged.
One private unit-of-work entry point may persist the system-owned cold compact cutover and market
invalidation as one transition. It:

1. begins one explicit `BEGIN IMMEDIATE` transaction after owner-lock acquisition;
2. authenticates the loaded inert checkpoint, compact owner candidates, and direct current proof;
3. applies only the history-independent compact-owner cutover plus
   `invalidate_position_protection_market` to exact current projections;
4. persists any changed protection/controller/cursor rows and exactly one canonical compact
   successor checkpoint under the existing runtime write lease;
5. authenticates its sealed capability-bound decision before commit; and
6. returns either the exact successor context, exact replay, or fail-closed refusal.

The compact cutover is idempotent: an already normalized and invalidated current checkpoint is an
exact replay and does not advance again. Startup invokes this transition once before any
reconciliation mutation to establish the first admissible compact context, and once against the
latest post-reconciliation context as the final pre-source invalidation barrier. The second call is
exact replay when reconciliation preserved invalidation; otherwise it commits and rereads exactly
one new invalidated successor. This private lifecycle transition is not a ninth external
durable-input domain and creates no
caller-shaped operation, DDL, receipt bypass for an external input, effect, or dispatch authority.
Its idempotence and checkpoint successor are the durable recovery evidence. No adapter/query task
may start until the first committed invalidation result has returned normally, and no source task
may start until the final invalidation barrier has returned normally.

### Exact startup sequence

1. Validate exact request shape without touching the connection.
2. Acquire and validate process owner evidence.
3. Verify schema/application/profile identity, load the exact inert runtime checkpoint/current
   proof by direct keys, and construct only non-serving compact owners through proof-bound private
   constructors. Require complete semantic agreement; hydrate no authority from explanatory
   history and do not claim inherited history-shaped commitments are reproducible.
4. Persist the atomic compact-owner cutover and cold market invalidation through the private UOW
   bridge, reread its exact successor checkpoint C1, and only then form the private context used by
   M2-I4. A rollback returns no context; ambiguous commit returns non-serving and retry reloads the
   latest committed checkpoint.
5. Enter `RECONCILING`; enumerate the complete authenticated current-unresolved effect union from
   the checkpoint selection proof: OPEN, qualifying INVALIDATED, and qualifying closed-late-owner
   rows. Query every exact claimed unresolved identity through the injected effect-query port and
   apply returned existing venue-recovery items through M2-I4. Never submit or resend an effect;
   unclaimed rows are not queried or treated as evidence of prior dispatch. Each applied operation
   consumes and returns the latest admitted successor context.
6. Reload direct proof and require complete resolution/coverage. Apply the same private cold
   invalidation transition against the latest context and require its committed-and-reread result,
   or exact replay when invalidation remained current. Only then call the market port.
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
- CR-08: owner-locked hydration uses proof-bound compact owner construction, refuses any missing or
  substituted bounded semantic row, and atomically cuts over to a normalized, cold-invalidated
  successor before reconciliation without replaying omitted history; non-serving retry reloads the
  latest committed context.
- CR-09: stranded claims are found from the complete authenticated current-unresolved union without
  history scans, including qualifying invalidated and closed-late-owner rows.
- CR-10: every exact claimed member of that union receives one targeted query and complete coverage.
- CR-11: phases are monotonic; successful open or reconciliation entry is never serving.
- CR-12: market invalidation commits with the initial compact cutover before reconciliation and is
  re-established idempotently against the latest context before the first source/adapter call.
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

Normal startup may traverse the exact scope tuple and the authenticated current-unresolved effect
tuple, but its query count is bounded by those current rows and is invariant under unrelated retired/fact/
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
  - tests/execution_core/test_persistence_write_capability.py
  - tests/execution_core/test_import_boundary.py
  - tests/execution_core/test_position.py
  - tests/execution_core/test_sqlite_boundary.py
  - tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
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

The CR-08/CR-12 controls include a C0-plus-unresolved claimed effect whose returned
venue-recovery operation changes the checkpoint, and prove initial-cutover rollback,
commit-ambiguity, final-invalidation exact replay or advance, source-refusal/retry reload, and no
extra checkpoint advance.

Completion requires RED, CR-01..19 and failure-capable mutants, focused/static/full-governance
evidence, independent P0=0/P1=0 acceptance, exact publication, and an M2-I6 handoff.

## REV-0116 preflight disposition

Fresh preflight returned `ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0. All three findings are accepted
and preserved unchanged in `work/review/REV-0116/result.md`: caller-held live context made cold
retry impossible, literal OPEN-only reconciliation omitted current unresolved variants, and final
service did not revalidate subscription currentness. The reconciled contract now owns those roots
through immutable request coordinates plus owner-locked proof-bound hydration, the complete
authenticated unresolved union, and final-edge subscription-currentness checks. Source was held
until one correction-only `REV-0116/result-r1.md` returned zero open P0/P1.

REV-0116 R1 returned `ACCEPT`, P0=0/P1=0/P2=0, `Unverified: NONE`, against exact corrected
contract candidate `9867e45fe53540c06cd821760f27e2e844be716a`, tree
`8c2e237aca44928ea04ec10cfd122f869535cb97`. The source hold is released. The stale boundedness
shorthand above was normalized from literal open effects to the already-reviewed authenticated
current-unresolved union without changing the accepted contract.

## REV-0116 R2 implementation-discovered root correction

The first hydration RED found that R1's byte-identical serving-owner reconstruction contradicted
the accepted WO-0168c predecessor: bounded checkpoint bytes deliberately do not reproduce
history-shaped behavior commitments. The corrected contract keeps loaded bytes inert, validates
all bounded semantic state against fresh direct proof, constructs compact non-serving owners, and
atomically persists one normalized compact-owner plus market-invalidation successor before any
context becomes serving-eligible. This is the predecessor-required behavioral-commitment cutover,
not a history replay or empty-map bypass. Source work on hydration/cutover is held until one fresh
finite R2 review returns zero open P0/P1; the already-green capability-contract slice does not
implement or prejudge the cutover.

R2 returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. The accepted finding showed that compact owners
could not authenticate against C0 for pre-cutover M2-I4 reconciliation. The corrected sequence
commits and rereads compact cold-invalidated C1 before reconciliation, uses only admitted successor
contexts thereafter, and applies one final idempotent invalidation barrier before source access.
Hydration/cutover source remains held until the same reviewer verifies this correction with zero
open P0/P1.

REV-0116 R3 returned `ACCEPT`, P0=0/P1=0/P2=0, `Unverified: NONE`, against exact corrected
candidate `47306fe81fb9f279e6190f00ae5241eef7f9203a`, tree
`448cc6aabce8674e5e77f9b26521fc1894b222f6`. The hydration/cutover source hold is released.

## REV-0117 round-one implementation review

Fresh whole-work-order review returned `BLOCK`, P0=1/P1=3/P2=0. The exact result is preserved in
`work/review/REV-0117/result.md`; `disposition.md` accepts and bounds all four corrections. The
single remediation round fixes owner fencing around post-baseline reread, source currentness, and
connection close; explicitly reconciles the held test's two frozen boundary inventories; updates
the stale first-layer checkpoint-authenticity oracle without weakening the separate direct-proof
pin; and corrects the complete Python-format inventory. The historical blank EOF in reviewer-owned
`REV-0116/result.md` remains immutable and is disclosed rather than rewritten. One correction-only
exact-head review with zero open P0/P1 is required before any SQLite gate may open.

REV-0117 correction review R1 returned `ACCEPT`, P0=0/P1=0/P2=0, against exact implementation
candidate `112d95115f2997ca613238b63eb161a12fbfc791`, tree
`137f7a7bd8d3bc4838cff905754c3394af07fef1`. Complete ordinary evidence reached 100% with 2,259
tests collected. The accepted flag-false candidate is now held at the separate human SQLite gate
described by `work/review/REV-0117/sqlite-execution-manifest.md`; no held test has executed.

## REV-0117 fresh-file attempt 1 disposition

Ameen approved the exact packet in `execution-request.md`. The published flag-only unlock was
`895715863ffdc49ae71cea33505e3079f875a9c8`, tree
`20c8e6c50a14743d111126571e699ea956e38edf`. Attempt 1 executed once and stopped during honest
setup when `store_acquisition_generation` returned `INTEGRITY_FAILURE`; attempt 2 did not run.
`execution-result-attempt-1.md` preserves the exact evidence and fresh database. Static diagnosis
found a cross-layer ordinal/classification mismatch in the shared proof fixture and checkpoint
boundary while the accepted one-based DDL contract remained correct. The quarantined flag-true
branch is evidence only. Application/test root remediation, fresh static review, and a new human
fresh-file gate are required before rerun.

The bounded root correction is candidate `dee3533099bba6ffeaa3372d33b04c1513cd75b7`, tree
`50861bbcc4d6e1b68490f619132fb16338a30e8e`. It preserves the domain's zero-based generation
identity while applying the already-established one-based durable-row translation at checkpoint
proof boundaries, and aligns the shared proof records with durable `CONSISTENT` / `NORMAL`
vocabulary. The changed hydration file passed 22 tests; all 2,261 ordinary `execution_core` tests
reached 100% with exit code 0; Ruff, mypy, and correction-range whitespace checks passed. DDL,
schema blob, held-test blob, and exact-false human flag remain unchanged. One finite static R2 review
is open under `correction-r2-request.md`; no SQLite rerun is authorized yet.

REV-0117 R2 returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. The result is preserved unchanged in
`result-r2.md`. Its single accepted P1 was a mutation gap: the production unresolved-generation
plus-one comparison had no non-empty unresolved selection test. The test-only correction builds an
authentic successor with a retained retired predecessor and stream route, proves the one-based
durable row encodes, and proves the domain-ordinal mutant raises the existing splice refusal. One
finite correction verification is required; no SQLite rerun is authorized yet.

REV-0117 R3 returned `ACCEPT`, P0=0/P1=0/P2=0, against exact test-only correction
`d1b0b26a55f8d45fa7b6bc7953c99f5a4fb78126`, tree
`142e738b7848f0751ac51d7b66521227aaff4e6e`. The reviewer reproduced all 23 pure hydration tests
and confirmed the unresolved-generation mutant is failure-capable. `sqlite-execution-manifest-r2.md`
now holds the corrected candidate at a new human gate. The first authorization remains consumed;
no new SQLite execution is authorized yet.

The exact flag-false R2 source candidate is `06fb2e2b1c2d9f184c12032ed20ff81676bf9ac0`, tree
`0762b252c803f9331b98e099e5712947955d6a04`, with R2 manifest SHA-256
`83ff7f3a65f6a9f8a69d015a69c278d392dead3db985570f7c9e4a1a661f8c84`.
`execution-request-r2.md` records the new branch, absent scratch path, exact command, stop rules,
and approval text. The human gate remains closed.

## REV-0117 corrected fresh-file R2 attempt 1 disposition

Ameen approved the exact R2 packet. The published flag-only unlock is
`911ae4292b9738bdb5353126fe12d397b8f6cd5f`, tree
`b8564a30d9ec08820d89d94b28eb0834ab1aa183`, with exact parent
`06fb2e2b1c2d9f184c12032ed20ff81676bf9ac0`. Attempt 1 executed once and reached
the real startup/UOW path, then stopped because startup returned fail-closed
`UNRESOLVED_EFFECTS` instead of `SERVING`; attempt 2 did not run.
`execution-result-r2-attempt-1.md` preserves the exact identities, command, output, and untouched
fresh database. The flag-true branch remains quarantined evidence only.

Static source tracing and one fresh-context review agree that the fixture's
`DISPATCH_CLAIMED -> ACKNOWLEDGED` response is admitted and startup's completeness gate is correct.
The bounded defect is in the real-SQLite venue-recovery UOW persistence/reload chain, whose public
result currently erases the exact inner `_TechnicalRefusal`. No DDL change is indicated. No repair
or rerun is authorized under the consumed R2 gate; a separately bounded application/test
diagnostic-remediation lane, fresh exact-head review, and new human execution packet are required.

## REV-0117 R2 root-cause remediation candidate

Ameen authorized one database-free application/test remediation from canonical head
`5bd3473f5d4f34316935369acb5d38e31f1bcee1`. A pure reproducer isolated the exact rollback:
venue recovery correctly derived `DISPATCH_CLAIMED -> ACKNOWLEDGED`, but
`_execute_venue_operation` projected that successor through `_bounded_context_changed` using the
pre-transaction selection proof. The codec correctly rejected the successor lifecycle against that
stale predecessor row, the UOW collapsed the resulting `_TechnicalRefusal` to `REFUSED`, and
startup remained fail-closed with `UNRESOLVED_EFFECTS`.

The root correction removes only that stale-proof precheck from the relational venue route. The
existing shared checkpoint writer already reselects the post-write proof inside the same
transaction; it now also requires the freshly projected canonical payload to differ from the
authenticated predecessor before storage. This preserves the no-op guard at the authoritative
proof boundary instead of weakening it. Two failure-capable pure controls reproduce the old
stale-proof call and reject an unchanged successor before checkpoint storage.

Both controls failed against the predecessor and pass after correction. Six source-confirmed pure
files passed all 550 collected tests with exit code 0. Ruff check/format, mypy over all 99 app
files, install/version/ledger/PKL checks, scope, and whitespace checks pass. No SQLite-bearing test,
held test, database, DDL, authorization-flag change, runtime, credential, broker/network call, or
order occurred. DDL remains 190,705 bytes at
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; the flag remains exact
`False`, and the held-test SHA-256 remains
`f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

## REV-0117 R4 review correction

R4 returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. The result is preserved unchanged in
`result-r4.md`. The accepted P1 showed that the original controls did not prove the checkpoint
projector received the distinct post-write proof: they could pass if projection regressed to the
pre-transaction proof.

Replacing that mock boundary with the real completion/checkpoint path exposed an earlier refusal
in the same held scenario. A dormant acquisition owner, before any protection is active, correctly
has no market cursor; the venue-recovery route nevertheless required one before persisting
`DISPATCH_CLAIMED -> ACKNOWLEDGED`. The bounded root correction now permits an absent cursor only
for a dormant owner on this venue route. Active protection still requires exactly one cursor, with
an explicit negative mutant control.

The integrated regression uses authentic predecessor and distinct post-write selection proofs,
drives the venue route through `_complete_claimed_input` and `_store_successor_checkpoint`, and
asserts both projection and storage consume only the fresh proof. The separate no-delta control
also uses a distinct fresh proof and proves an unchanged payload cannot reach storage. One finite
correction-only R5 review by the same independent reviewer must confirm zero open P0/P1 before a
new fresh-file execution packet is prepared. No SQLite or held test ran during this correction.

REV-0117 R5 returned `ACCEPT`, P0=0/P1=0/P2=0, against exact correction candidate
`fe59068d9129d417d0d9c85e4a9b53e0bd97d995`, tree
`a92dc7fb91ceb349323eee92a9e677fc03769279`. The reviewer reproduced all three direct pure controls
and confirmed that the stale-proof mutation is killed, the absent-cursor exception is limited to
dormant venue recovery, and active/default routes retain exact-one cursor enforcement. The
application/test remediation is statically accepted. A new R3 fresh-file packet is the next
separate human gate; neither consumed R2 authority nor its quarantined branch/database may be
reused.

## REV-0117 fresh-file R3 attempt 1 disposition

Ameen approved the exact R3 packet. The published flag-only unlock is
`a854f93eb93a70c324fcb9ae5a5d77ceefe3bed1`, tree
`60317a381b2c6c77487e6cf2b4b046ad30c4d949`, with exact parent
`9bb76c6f05dd7d9b672a6d3ee91e832134d8d544`. Static revalidation reproduced the approved DDL
identity and confirmed the unlock commit changed only the exact boolean flag.

Attempt 1 ran once and again returned fail-closed `NON_SERVING / UNRESOLVED_EFFECTS` instead of
`SERVING`; one held test failed in 1.64 seconds. This is a substantive result, so attempt 2 did not
run and no repair was made under the consumed gate. `execution-result-r3-attempt-1.md` preserves
the exact command, identities, output, and untouched fresh database path. The flag-true R3 branch
remains quarantined evidence only, and the canonical flag-false branch remains the sole
implementation predecessor. Further diagnosis/remediation requires new bounded authority; no
later work order has started.

## REV-0117 R3 instrumented diagnosis

Ameen authorized instrumented diagnosis after the substantive R3 stop. Wrappers on copies of the
preserved disposable database exposed the erased inner refusal in `_prepare_transaction`:
`runtime owners do not equal the retained checkpoint payload`. All six bounded owner components
were byte-identical. The only difference was intentional successor metadata: the retained current
checkpoint was version 1 while the authentic repository write proof targeted version 2.

`diagnosis-r3-instrumented.md` records the exact values, affected shared boundary, false-positive
fake-byte unit test, risk, and bounded remediation shape. A transient hypothesis probe using the
module's existing exact owner-semantic comparator produced first-start `SERVING` with one committed
`ACKNOWLEDGED` successor at version 2, then second-start `SERVING` with zero queries and no extra
checkpoint write. No second hidden refusal appeared. No tracked source/test, DDL, schema, original
database, or held assertion changed. Remediation remains separately unauthorized, and WO-0170 has
not started.

## REV-0117 R3 retained-checkpoint root remediation

Ameen authorized the instrumented diagnosis and then granted standing authority to finish WO-0169
without repeated routine approval stops. That authority covers ordinary reversible in-scope root
correction, tests, static and governance checks, fresh exact-head review, one fresh pytest-owned
file-database proof with unchanged approved DDL, publication, and closeout. It does not expand the
work order across its existing hard boundaries: changed DDL, configured or real database access,
migration, credentials, broker/network activity, orders, destructive history changes, promotion,
master merge, later-work-order implementation, and M3 implementation remain unauthorized.

The false-positive byte-mock control was replaced with genuine codec-issued projected and loaded
envelopes. The authentic RED reproduced the production relationship: the retained checkpoint at
version N and the repository-selected target projection at N+1 had different whole payload bytes
despite exact owner-semantic equality. A second mutation proved that merely projecting the
predecessor at N is not an acceptable substitute for the required N+1 projection.

The owning guard now performs two separate checks instead of conflating them:

1. the loaded predecessor must be authentic, have `LOADED` provenance, and match the exact expected
   application, currentness ordinal, version ordinal, and payload digest; and
2. the authenticated owner projection must be authentic, have `PROJECTED` provenance, be the
   expected next checkpoint version without currentness regression, and match every retained owner
   component through the existing exact `_m2_checkpoint_semantics_match` comparator.

This is an application/test-only correction. It changes no DDL, schema API, startup contract,
public UOW surface, operation union, held-test assertion, or execution-authority flag. The three
direct authentic controls are green; all 552 tests in the six source-confirmed pure modules and all
2,266 ordinary `tests/execution_core` tests pass at 100% with exit zero. Ruff check/format and mypy
over all 99 application files pass, as do install, version, ledger, PKL, disposition, scope, and
whitespace checks. Protected identities remain DDL
190,705 UTF-8 bytes at
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, schema blob
`164de10ad9fef6ce37324840aff59b5b68c07d2a`, exact-false human flag, and held-test SHA-256
`f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`. One finite fresh
exact-head review with zero open P0/P1 remains required before the new fresh-file proof.

## REV-0117 R6 test-evidence correction

Fresh R6 review returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. The product correction was not
disputed. The accepted P1 showed that the different-owner negative control projected its active
owner fixture at version N, so the earlier N+1 guard refused it before the owner-semantic
comparison. The test therefore did not independently kill removal of the comparator.

The test-only correction now issues the different active owner set under an authentic successor
proof bound to the retained application's exact profile/head coordinates at version N+1. It pins
that version relationship and traces the guard's single semantic-comparator invocation for the
different-owner case; all stale-head, wrong-provenance, and predecessor-at-N cases must refuse
before that comparator. One finite same-seat verification of this exact evidence correction must
return zero open P0/P1 before the fresh-file proof proceeds. Production source, DDL, held test,
human flag, and accepted startup architecture are unchanged.
