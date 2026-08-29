---
type: Work Order
title: M2-I4 atomic unit of work and post-commit effect eligibility
status: ACTIVE
work_order_id: WO-0168
wave: M2-I4
model_tier: strong
risk: critical
disposition: []
owner: Codex implementation seat; fresh-context review seats REV-0113 and REV-0114
created: 2026-08-28
predecessor: WO-0168d canonical flag-false closeout 25aca36956d68db014df3769678699597e9be56a
branch: codex/m2-wo0168-atomic-uow-r1
preflight_review_id: REV-0113
implementation_review_id: REV-0114
execution_authority: >
  Ameen Mujtabaa's recorded serial-M2 authority in
  work/queue/M2-EXECUTION-2026-08-21/34-M2-COMPLETION-DRIVE.md and his 2026-08-28
  instruction "You may proceed with the remaining sequence" authorize ordinary reversible
  implementation, fresh-file verification against the already-approved unchanged DDL, governance,
  commits, pushes, bounded fresh review, root-cause fixes, and successor preparation through M2
  closeout. This order does not authorize DDL-byte changes, configured or in-memory databases,
  migration, runtime composition, credentials, broker/network calls, orders, promotion, master
  merge, history rewrite, M2-I5+, or M3 implementation.
allowed_paths:
  - app/execution_core/position.py
  - app/execution_core/venue.py
  - app/execution_core/authority.py
  - app/execution_core/acquisition.py
  - app/execution_core/protection.py
  - app/execution_core/persistence/__init__.py
  - app/execution_core/persistence/operations.py
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/persistence/records.py
  - app/execution_core/persistence/repository.py
  - app/execution_core/persistence/unit_of_work.py
  - app/execution_core/persistence/outbox.py
  - tests/execution_core/test_persistence_operations.py
  - tests/execution_core/test_persistence_write_capability.py
  - tests/execution_core/test_persistence_unit_of_work.py
  - tests/execution_core/test_persistence_crash_atomicity.py
  - tests/execution_core/test_import_boundary.py
  - tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py
  - work/active/WO-0168-m2-i4-atomic-unit-of-work-effects.md
  - work/completed/keep/WO-0168-m2-i4-atomic-unit-of-work-effects.md
  - work/review/REV-0113/**
  - work/review/REV-0114/**
  - work/queue/M2-EXECUTION-2026-08-21/05-POST-I3-PREFLIGHT-AND-M2-COMPLETION-MAP.md
  - work/ledger.jsonl
forbidden_paths:
  - app/execution_core/persistence/schema.py
---

# WO-0168 — atomic unit of work and effect eligibility

`[FABLE • FULL • spec-first/TDD • one writer • no external I/O]`

## Outcome

Compose the accepted eight-operation union, authenticated in-memory owners, direct SQLite proof,
owner reducers, relational writes, canonical checkpoint, mandatory receipt/outcome, and optional
immutable outbox row in one `BEGIN IMMEDIATE` transaction. Return effect eligibility only after a
normal commit return. The UOW performs no external publication.

The historical queue packet remains planning evidence. This active successor reconciles it with
the accepted WO-0168a/h/c/d interfaces and unchanged DDL at predecessor head.

## Frozen public boundary

`unit_of_work.py.__all__` is exactly:

- `UnitOfWorkContext`
- `UnitOfWorkDisposition`
- `UnitOfWorkResult`
- `PostCommitEffectEligibility`
- `execute_unit_of_work`

`UnitOfWorkContext` is one exact frozen value containing: expected `KernelCheckpointRecord`, exact
`VenueRecoveryBook`, exact `ExecutionAuthorityState`, and a strictly scope-ID-ordered tuple of
scope-owner rows `(scope_id, AcquisitionControllerState | None, ExecutionSnapshot,
PositionProtectionState | None)`. It contains no connection, callback, write plan, digest-only
owner surrogate, path, credential, or external service.

`execute_unit_of_work(connection, operation, context)` accepts an exact `M2Operation`. Before a
transaction it performs only exact type/canonical operation validation. After `BEGIN IMMEDIATE`,
it verifies the accepted schema and operation coordinates, selects direct current proof against
`context.expected_checkpoint`, and projects every context owner through the accepted checkpoint
projector. A projection mismatch is a technical refusal; caller-owned state is never trusted by
identity or digest alone.

### Operation-keyed owner proof correction (REV-0113 F1)

Projection equality authenticates only the bounded checkpoint members. Before an owner reducer can
read a member deliberately omitted from that checkpoint, the owner module must mint one exact,
sealed, operation-keyed observation proof. The UOW derives that proof only from the selected current
row plus retained durable-input/semantic-key evidence; it never supplies a mapping, callback, or
caller assertion. The public owner API derives the same proof from its reference owner and delegates
to the same shared kernel, so there is one decision engine.

For `BeginManualFlatten` and `AdvanceManualFlatten`, the authority proof has exactly three cases:
`ACTIVE_CURRENT` binds the current scope index to its exact manual row represented by the checkpoint;
`RETAINED_TERMINAL` binds the manual semantic key to its retained input and terminal outcome while
proving no active scope row; and `ABSENT` proves both current and retained evidence absent. The
shared authority kernel may consult only that proof for the targeted flatten ID. An unbound
`_manual_by_id` entry is non-authoritative noise: adding, removing, or changing it cannot alter the
disposition, reason, writes, or successor context. This is an operation-keyed correction, not
authorization to serialize a historical map. Apply the same rule if another admitted route is
shown to read an omitted owner member during implementation.

`UnitOfWorkDisposition` is exactly `COMMITTED`, `REFUSED`, `EXACT_REPLAY`, `CONFLICT`, and
`RECONCILIATION_ONLY`. `COMMITTED` carries the exact owner domain/disposition and successor context;
an owner-level `REFUSED`, `STALE`, or `EXACT_REPLAY` may therefore be a committed durable decision
without economic writes. Technical validation/refusal rolls back and returns `REFUSED`. Primary
identity conflict rolls back and returns `CONFLICT`. A retained primary replay performs no reducer
or write and returns `EXACT_REPLAY` with no effect eligibility.

`PostCommitEffectEligibility` carries only immutable outbox sequence/effect/claim/payload identity.
It is minted after normal commit return and is absent for replay, refusal, conflict, owner results
without a fresh claim, and commit ambiguity. It is not delivery authority or external success.

## Transaction protocol

The one exact sequence is:

1. C0 canonicalize/decode the exact operation; reject unknown/proxy/subclass before SQL.
2. C1 execute literal `BEGIN IMMEDIATE`; no savepoint, retry, or hidden transaction.
3. C2 verify schema plus application/profile/source/scope/session/acquisition/stream coordinates;
   select and project current owners against direct proof, then mint any required exact
   operation-keyed owner observation proof.
4. C3 activate one runtime write lease, claim the canonical durable input, and classify primary
   replay/conflict. Derive and load required semantic keys; callers cannot supply them.
5. C4 derive the exact owner inputs and invoke exactly one existing public reducer pipeline or its
   owner-equivalent shared kernel from the frozen eight-row matrix. A public reducer and the UOW
   route must delegate to that same kernel; no generic callback/registry/`Any` dispatch.
6. C5 validate the exact transition and derive a closed pure write plan from predecessor/result.
7. C6 issue only owner-proven semantic keys and relational rows in dependency order using the
   existing capability-bound repository methods.
8. C7 reselect direct current proof, project successor owners, and store payload then CAS head.
   No-change owner decisions use a null checkpoint reference and do not advance the head.
9. C8 store receipt, outcome, optional outbox, then finalize the durable input. Receipt is never
   reducer/currentness/claim/closure/recovery authority.
10. C9 retire the lease immediately before one COMMIT attempt. A normal return publishes the
    successor context and optional eligibility. A commit exception is never rolled back or retried;
    the connection is retired/closed where supported and returns `RECONCILIATION_ONLY` only.

Every rollback path retires an active lease immediately before one ROLLBACK attempt. The exact R7
L00-L08 lease matrix is binding. Old capabilities fail after commit and rollback on the same
connection; copy/deepcopy/reduction/field-copy and alternate issuer routes fail.

## Closed reducer matrix

The eight operation types, owners, legal owner dispositions, semantic-key rules, and row-family
order are exactly companion contract 06 sections 2.3-3. The UOW may compose existing owner-owned
projection functions needed by acquisition/protection, but it may not recreate owner decisions.
If an existing reducer result does not expose enough authenticated evidence to derive one required
row, the root fix belongs in that owner module with public-to-shared-kernel parity tests; a generic
write plan or caller-provided derivative is forbidden.

Relational technical IDs and global ordinals are allocated deterministically from the accepted
single-writer database state inside `BEGIN IMMEDIATE`, using explicit fixed SQL and exact next-value
checks. No wall clock, randomness, retry allocator, generic SQL builder, or caller-provided ID map.

## Functional requirements

- FR-1: authenticate exact coordinates, bounded owner state, and every operation-keyed omitted
  member the selected reducer can read against direct proof before reduction.
- FR-2: one admitted input yields old-complete or new-complete durable state; no partial authority.
- FR-3: primary replay/conflict short-circuit exactly; semantic matches reach the owning reducer.
- FR-4: a concrete immutable claim and outbox snapshot precede post-commit eligibility.
- FR-5: every new terminal input has one coherent mandatory receipt/outcome before finalization.
- FR-6: commit ambiguity performs no rollback/retry/eligibility and requires reconciliation.
- FR-7: runtime mutators require the exact active lease; setup authority remains test-only.
- FR-8: imports are inert; no DB path discovery, broker/network, credentials, orders, or dispatcher.

## TDD and evidence

Implement coherent slices: lease lifecycle; technical claim/replay/conflict; owner authentication;
one row of the eight-operation matrix at a time; checkpoint/receipt; outbox; fault matrix. Each
slice starts with a failure-capable RED test and ends with focused pure/static evidence. SQLite
tests use only fresh pytest-owned file databases through the accepted gate helper and unchanged
DDL; never `:memory:` or configured paths.

Decisive controls include every R7 L00-L08 exit, fault before/after every composite write,
receipt/outcome/outbox serialization failure, commit-return ambiguity, direct-mutator bypass,
unknown/subclassed input, stale/cross-coordinate context, primary and semantic collisions, owner
disposition parity, and restart inspection proving old-complete/new-complete. Mutants must fail if
lease retirement is skipped/reordered, a reducer is bypassed, a write family is omitted, receipt
becomes optional, eligibility appears pre-commit, or ambiguity retries.

The authority proof slice starts with the two REV-0113 payload-equal counterexamples. For fresh
manual identities, an added omitted `_manual_by_id` row must not change `BeginManualFlatten` from
its clean-context result or make `AdvanceManualFlatten` apply. Mutants fail if the shared kernel
reads the raw target-key map, accepts a semantic digest without retained bytes/outcome, or treats a
terminal manual as active.

## Review and stop rules

REV-0113 is one fresh preflight review of this executable contract. Confirmed P0/P1 findings get
one root remediation and one exact-head re-review maximum. REV-0114 is one fresh implementation
review plus at most one remediation re-review. Taste findings are nonblocking P3; a finding blocks
only when tied to a contract clause or demonstrated failure.

Any DDL-byte change is an explicit stop requiring a new digest/byte-count/schema-blob/test packet
and separate human approval. No successor activation until WO-0168 is independently accepted,
closed, clean, pushed, and local equals origin.

## Done

Focused pure and fresh-file fault suites, full `tests/execution_core`, Ruff check/format, mypy,
import boundaries, governance/scope checks, and `git diff --check` pass. REV-0114 returns zero open
P0/P1. Closeout records exact commit/tree, unchanged DDL identity, test evidence, residuals, and
the WO-0169 activation handoff.
