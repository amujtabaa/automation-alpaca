---
type: Work Order
title: M2-I2 schema and direct-current-proof foundation
status: ACTIVE
work_order_id: WO-0166
wave: M2-I2
model_tier: strong
risk: critical
disposition: []
owner: Codex implementation and checkpoint seat; adversarial agents provide in-process review
created: 2026-08-21
predecessor: WO-0165 exact accepted closeout head 2e47702c926515bf587aa71de987a3fb879e4d75
base_sha: 2e47702c926515bf587aa71de987a3fb879e4d75
branch: codex/m2-i2-schema-direct-proof-codex-r1
review_id: REV-0071
execution_authority: On 2026-08-22 Ameen Mujtabaa explicitly directed Codex to take over and resolve the remaining WO-0166 root defects, granted standing pre-approval for the resulting in-scope DDL revisions, and authorized Codex to execute the temporary-file proof without another exact-hash pause. Configured database access, migration, runtime work, broker or network calls, orders, promotion, and merge remain unauthorized.
---

# Work Order: M2-I2 schema and direct-proof foundation

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Active for Codex-owned root remediation, temporary-file proof, and bounded closeout preparation

`[FABLE • FULL • spec-first/TDD • human-gated schema surface]`

## Context and goal

Translate accepted M1/M1.5 semantics and M2-I1 codecs into one exact SQLite schema contract. The
schema enforces immutable identity, direct current proof, one-writer/current-generation uniqueness,
fact/revision lineage, effect/claim/owner/acceptance/closure authority, and profile separation. It
does not yet provide a repository, runtime, or transition unit of work.

## Activation and human gate

This order is active only for a documentation and RED-test/schema candidate. Before any DDL is
executed, any SQLite database is created/opened, or any schema test runs, the coding LLM must return
a `HUMAN-GATE` bundle containing:

- exact proposed DDL bytes and SHA-256;
- entity/constraint/index/trigger inventory;
- temporary destination and proof that no configured database is reachable;
- positive and negative test matrix; and
- layman's summary of what the schema prevents plus impact of approval.

Ameen must approve that exact candidate. Any semantic DDL change after approval requires a new
hash and gate.

## Activation checkpoint

| Item | Exact value |
| --- | --- |
| Human activation | Ameen Mujtabaa: close WO-0165, then move to the next work order promptly (Codex task, 2026-08-21) |
| Accepted predecessor | `WO-0165` closeout `2e47702c926515bf587aa71de987a3fb879e4d75`, tree `e8d2b0d4a8f734934252b8719cb0241574d03654` |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` created from Ox Alpha v4 `6a8477d51d38eb4575d88395e3b57493d03b6812` |
| Review identity | `REV-0071` reserved; independent packet not yet opened |
| Current authority | Codex root remediation plus direct and adversarial verification under the 2026-08-22 amendment |
| DDL execution | `AUTHORIZED` for this bounded remediation proof only |
| SQLite create/open/access | `AUTHORIZED` for fresh pytest `tmp_path` file databases only |
| Schema-test execution | `AUTHORIZED` within WO-0166 scope |

## Authority amendment — Codex takeover and standing DDL approval

**Decision owner:** Ameen Mujtabaa

**Decision date:** 2026-08-22

Ameen directed Codex to take over the remaining WO-0166 remediation after repeated Ox Alpha
attempts. He granted standing pre-approval for Codex's necessary in-scope DDL corrections and
temporary-file execution, stating that another exact-hash approval pause was not needed for this
area. He also authorized Codex to rely on its own direct verification plus adversarial review
agents instead of requiring Ox Alpha or a separate external seat to approve the result.

This amendment authorizes changes only within the existing allowed paths and execution only
against fresh pytest `tmp_path` file databases. It does not authorize a configured database,
migration, repository/hydration/runtime work, credentials, broker/network calls, orders,
promotion, or merge to `master`. The historical 2026-08-21 exact-hash decision below remains
preserved as prior evidence but no longer limits this remediation run.

Operationally, this amendment supersedes the earlier pre-gate stop for the bounded Codex
remediation run. The return bundle must still disclose every executed check and retain all
`NOT_RUN` items; all other scope and safety limits remain in force.

## Fable execution record — Codex remediation

### RED

The inherited Ox Alpha v4 candidate at `6a8477d51d38eb4575d88395e3b57493d03b6812`
was tested with isolated negative controls before production correction. Six controls failed as
intended: fact-lineage branching, missing exact venue-owner authority, retirement-time generation
rebinding, venue-effect rebinding, exact owner/effect closure attribution, and same-version
checkpoint payload substitution. These failures established that the inherited constraints were
not load-bearing for the required invariants.

### FIX

Codex replaced the incomplete mechanisms at their semantic roots: authenticated direct fact heads
and current-head predecessor enforcement; one immutable venue-owner relation used by closure
authority; immutable identity/binding guards; version-coupled payload replacement; canonical
effect state with immutable closure proof; and controller/generation compatibility and liveness
coupling. Tests include both refusal mutants and positive/no-op controls so an over-restrictive
repair cannot pass unnoticed.

### Fresh adversarial RED and root redesign

Three fresh adversarial agents independently reviewed the first Codex checkpoint
`b284beaa627f3a150148f007ea21b3764c651509`. Their combined P0/P1 findings reproduced authority
gaps in root/controller economics, profile/generation ownership, fact shape, effect closure proof,
successor compatibility, market-stream binding, query-plan coverage, installer atomicity, and
`INSERT OR REPLACE` behavior. Seven isolated negative controls were added and all seven failed
against that checkpoint before the redesign.

The remediation replaced those surfaces rather than adding fixture-specific exceptions:

- root and controller economics now derive automatically from the exact immutable current fact
  head; callers cannot supply an unauthenticated economic total;
- scopes select immutable application/execution profile coordinates, complete fact variants retain
  their typed authority fields, and successor generations require the exact retired compatible
  predecessor;
- effect closure requires exact immutable claim/evidence/proof coordinates, a dispatch claim
  automatically advances the effect state, and claimed-or-later states cannot be caller-minted;
- market cursor and protection authority bind to one exact stream/source/session/mode route;
- canonical origin/version triggers, direct-query indexes, and replacement-bypass mutants make the
  constraints failure-capable; and
- installation takes an immediate write lock, checks emptiness under that lock, executes each DDL
  statement atomically, and rolls back completely on an injected interruption. The production
  module remains dependency-neutral and imports no `sqlite3` capability.

### DONE evidence — final pre-review candidate

The final standing-approved DDL is exactly `72,373` UTF-8 bytes with SHA-256
`46d486a01c9c2b93cd39024c7376df39a23e78ccf3f0d17b6239aa00b8423a66`; the test gate contains
that same digest. Fresh checks on CPython 3.12 completed as follows:

- `python -m pytest -q tests/execution_core/test_persistence_schema.py`: 50 passed;
- `python -m pytest -q tests/execution_core/test_import_boundary.py`: 32 passed;
- `python -m pytest -q tests/execution_core`: 1,658 passed;
- `ruff check` and `ruff format --check` on both changed Python paths: clean;
- `mypy app`: success across 91 source files;
- `lint-imports`: six contracts kept, zero broken; and
- `git diff --check`: clean.

Every database opened by the schema tests was a fresh file under pytest `tmp_path`; no in-memory or
configured database, migration, runtime composition, credential, broker/network call, order,
promotion, or merge was performed. Fresh exact-commit review remains the next gate before closeout.

### First review verdict and second RED

Three fresh adversarial seats returned `BLOCK` on exact commit
`28c2c43deaaa5721c58c1a30d17d149486167de0` with five P0 and three P1 findings. The preserved
review result is `work/review/REV-0071/result.md`. Ten isolated second-round controls failed against
that candidate before repair: revision order/side drift, negative broker-truth rollback, root-bound
incomplete effects, non-atomic invalidation, cross-scope owner reuse, nonflat protection transfer,
default-connection `INSERT OR REPLACE`, aggregate query scan, and unaccounted global sequence gaps.

### Second root remediation candidate

Codex corrected those authority surfaces at their relational roots. Revisions now preserve exact
broker-authoritative predecessor scope; signed negative broker truth is retained while a sticky
controller integrity state quarantines serving; requested effects are rootless and carry complete
immutable M1 scope; invalidation names an exact immutable owner/observation and atomically advances
the canonical effect; owner identity is profile-global; stream, cursor, and protection authority
retain exact acquisition-generation/mandate routes; nonflat protection transfer is refused; and
conflicting inserts are blocked even after reopening with default recursive-trigger behavior.

The replacement candidate is commit `dbd2a086fe861047e5df49cdd65a4ded33c7f758`, tree
`c82dc44bae00aa3df5932991ef38a3839b91f85d`, with `SCHEMA_DDL` exactly `93,860` UTF-8 bytes and
SHA-256 `8bfbfaa30302d3c6be3266b02e3bc19bc6b3c72484fbd9a324aba0561e912ed0`. Fresh evidence at that
identity: 60 focused schema tests and all 1,668 collected `tests/execution_core` tests passed on
CPython 3.12.13; Ruff, formatting, mypy over 91 source files, six import contracts, scope, and
whitespace checks passed. `request-addendum.md` opens the required fresh re-review.

### Second review verdict and terminal remediation

The second exact review returned `BLOCK` on `dbd2a086fe861047e5df49cdd65a4ded33c7f758`.
`result-round2.md` preserves three P0 and four P1 findings: evidence-free direct invalidation,
stale-head dispatch claims, connection-local enforcement loss after reopen, replaceable schema
metadata, global protection versions, and non-load-bearing sticky quarantine.

The terminal repair makes invalidation evidence the sole atomic CLOSED-to-INVALIDATED route;
persists the effect's expected controller head and revalidates exact controller identity/head at
creation and claim; adds an explicit per-open/per-operation connection verifier for both SQLite
enforcement pragmas and exact installed schema identity; prevents schema-metadata replacement
independent of recursive-trigger behavior; makes protection versions scope-local; and gates both
protection insertion and transfer on controller integrity.

The replacement candidate is commit `57d795aa9da0e96638fd89ba9243ae9819cc37cb`, tree
`e9a1dc259c970d3366161fcf2129e251213280f8`, with `SCHEMA_DDL` exactly `97,064` UTF-8 bytes and
SHA-256 `cd9ffbd8997ce66c5a332473de4697f5d3ecfbab9b8810866af380d7968ee1cf`. Fresh evidence: 65
schema tests and all 1,673 collected `tests/execution_core` tests passed on CPython 3.12.13; Ruff,
formatting, mypy over 91 source files, six import contracts, scope, and whitespace checks passed.
`request-terminal.md` opens the final fresh review.

### Terminal review verdict and final root remediation

The terminal review of `57d795aa9da0e96638fd89ba9243ae9819cc37cb` remained `BLOCK`.
`result-round3.md` preserves four P0 and one P1 findings: outbound actions remained possible under
controller quarantine; acquisition-root routing was neither total nor generation-exact;
protection could bind retired generation history; INVALIDATED authority could be relabeled as
ACCEPTANCE_CLOSED; and the connection verifier trusted a spoofable metadata row.

Codex resolved these at their shared semantic roots. An immutable `acquisition_root_route` now
seals each accepted root to exact effect, owner, observation, scope, profile, and acquisition
generation coordinates. Broker truth without that route remains durable and advances exact
economics, but drives a sticky unmatched-lineage quarantine that cannot serve. Effect, claim, and
all protection mutation boundaries require the exact current consistent controller; protection
also requires the controller's exact LIVE generation. Exact invalidation evidence atomically
appends a distinct negative-ID `INVALIDATED_TERMINAL`, while ACCEPTANCE_CLOSED requires exact CLOSED
authority. Finally, installation and every verified reopen compare a deterministic fingerprint of
the complete application-owned SQLite catalog, not merely the metadata row.

The final source/test candidate is commit `5c44b2ea517be306b94851199ccb9c15ef407e93`,
tree `4d6e6d3657d278259babb9e104e464efd10febad`, with `SCHEMA_DDL` exactly `104,851`
UTF-8 bytes and SHA-256 `6871d276b2a59b136579c4535dd689f5d85ab73e508d0ad6ec82dc3dd804797f`.
Its installed-catalog fingerprint is
`5dc150333a89ff369956ad16c364b1bcbb7d15e93e71860236ebeaebcbac309f`. Fresh evidence:
70 schema tests and all 1,678 collected `tests/execution_core` tests passed on CPython 3.12.13;
Ruff, formatting, mypy over 91 source files, six import contracts, scope, and whitespace checks
passed. `request-final.md` opens a fresh exact-commit review.

### Final review verdict and retired-lineage remediation

The review of `5c44b2ea517be306b94851199ccb9c15ef407e93` returned `BLOCK`.
`result-round4.md` preserves one P0 and one P1: a late exact retired-generation fact left normal
successor BUY/protection authority serving, and one root could borrow another root's owner/effect
proof inside the same generation.

The remediation introduces sticky `MIXED_GENERATION_RECOVERY` for non-no-op exact retired-root
economics. Normal effects, claims, and protection mutations cannot serve in that state. The schema
retains one explicit `HARD_BAIL` authority class: only a head-bound SELL effect and matching
protection classification may proceed, with at most one HARD_BAIL effect per scope/controller
head. Non-flat or non-consistent controllers cannot unbind/rebind live generations around the
fence. The acquisition route's owner-side foreign key now carries `root_fill_key_id` end-to-end,
making same-generation cross-root proof borrowing structurally impossible.

The replacement source/test candidate is commit `fead0234c4428678c673b9a6e34e632116030281`,
tree `f3e335738020bf5655648193183509ccf5cf2db4`, with `SCHEMA_DDL` exactly `111,149`
UTF-8 bytes and SHA-256 `ef4f4fb3fc6a98705c6f713d3d0e9a330863ad2d975bfb444baa4801aa4ba2cf`.
Its installed-catalog fingerprint is
`88b9dc1cbe4771f689f8d308802c2786b5e283910acfba70b7d341a1973113da`. Fresh evidence:
73 schema tests and all 1,681 collected `tests/execution_core` tests passed on CPython 3.12.13;
the catalog fingerprint also matched on CPython 3.14.5 / SQLite 3.50.4; Ruff, formatting, mypy over
91 source files, six import contracts, scope, and whitespace checks passed. `request-final-02.md`
opens the next exact-commit review.

### Final review 02 verdict and Codex root repair

The review of `fead0234c4428678c673b9a6e34e632116030281` returned combined `BLOCK`, P0=2,
P1=2. `result-round5.md` preserves four live-reproduced defects: negative retired facts could
retain HARD_BAIL SELL authority; HARD_BAIL was not bound to exact protection or bounded by current
long quantity; retired exact no-op revisions staled valid successor work; and valid fact-driven
flat recovery could not release the mixed fence.

Codex corrected the semantic roots. Negative aggregate now outranks mixed recovery. HARD_BAIL
requires exact current protection/live-generation authority and a positive SELL quantity no larger
than the aggregate long position at effect creation and claim. Exact retired no-op revisions still
advance immutable fact/root lineage but not controller currentness. Mixed recovery releases only
at exact flat after a non-no-op fact routed to the current live generation, while retired/no-op
facts cannot relax the fence.

The replacement source/test candidate is commit
`9841bae870c462b36ec92d0dd588701d5c7125f6`, tree
`7e34a0d14e405a75d25befd9af137fb17049f461`, with `SCHEMA_DDL` exactly `122,873`
UTF-8 bytes and SHA-256 `e279eae170bf6ee572c2b67b3e67ce862739a2a4768ede54383e590e86a61609`.
Its installed-catalog fingerprint is
`65dfedd48abfb25faf1ae1e758bccbb2738330370d1acc9df16b480add09c000`. Fresh evidence:
75 schema tests and all 1,683 collected `tests/execution_core` tests passed on CPython 3.12.13;
the catalog identity matched on CPython 3.14.5 / SQLite 3.50.4; Ruff, formatting, mypy over 91
source files, 32 import-boundary tests, six import contracts, scope, ledger, and whitespace checks
passed. `request-final-03.md` opens fresh exact-commit review.

### Final review 03 verdict and direct generation-closure redesign

The review of `9841bae870c462b36ec92d0dd588701d5c7125f6` returned combined `BLOCK`, P0=2,
P1=3. `result-round6.md` preserves the unique findings: unresolved predecessor SELL authority
could coexist with successor BUY authority; mixed recovery could clear around retained unmatched
lineage; initial negative aggregate had the wrong classification priority; normal effects/claims
did not require protection; and multi-acceptance ownership was unrepresentable.

The replacement introduces one exact `acquisition_generation_current` record per generation with
a direct economics head, unresolved-effect count, and active-protection count. Triggers maintain
and verify those values against exact indexed authority. Controller unbinding, retirement, and
successor admission require zero unresolved effects and non-serving predecessor protection. Late
invalidation reopens the predecessor summary, advances controller currentness, and enters sticky
unresolved-venue quarantine. Normal and HARD_BAIL effects bind exact protection, including its
version, at creation and final claim. Negative and global unmatched classifications outrank mixed
release, and distinct concrete owners may coexist under one effect without weakening exact route
or closure keys.

The replacement source/test candidate is commit
`00507efebbb9dcee3f0f2926a718df3a4bd205c3`, tree
`ba7a9f74aab639601bafaa41f543884946de99a5`, with `SCHEMA_DDL` exactly `138,120`
UTF-8 bytes and SHA-256 `a798137e8d9b062abec70317167242a6afd68732654258e912c49e1317f2bd16`.
Its installed-catalog fingerprint is
`c2cbf42b61ec6ca6928dc63e5165584f525356a64878907574ab93c975478d56`. Fresh evidence:
80 schema tests and all 1,688 collected `tests/execution_core` tests passed on CPython 3.12.13;
the catalog identity matched on CPython 3.14.5 / SQLite 3.50.4; Ruff, formatting, mypy over 91
source files, 32 import-boundary tests, six import contracts, scope, ledger, and whitespace checks
passed. `request-final-04.md` opens fresh exact-commit review.

## Functional requirements

- FR-1: The schema MUST bind one immutable application generation to one selected execution profile and a
  distinct market-source profile; retain historical profiles and refuse in-place material change.
- FR-2: The schema MUST represent direct current checkpoint/controller/generation, fact/revision head, root,
  effect, owner, acceptance, closure-head, claim, and market-cursor routes without serving-time
  history fold.
- FR-3: The schema MUST enforce at most one LIVE acquisition generation per exact scope and one selected profile
  per application generation with database-native constraints.
- FR-4: The schema MUST preserve immutable predecessor-linked facts and nonbranching same-owner closure ordinals;
  reject duplicate roots, gaps, branches, cross-owner predecessors, and mutable head substitution.
- FR-5: Canonical effect rows MUST own `OPEN|CLOSED|INVALIDATED`; checkpoint-shaped copies cannot
  override them. A committed immutable claim makes `NEVER_DISPATCHED` impossible.
- FR-6: The schema MUST bind every capital-relevant row and external identity to exact application/profile/scope
  coordinates. No raw credential or provider account identifier may appear.
- FR-7: Foreign keys, checks, uniqueness, immutability guards, and direct-key indexes MUST be
  enabled and failure-capable in fresh temporary databases.
- FR-8: The implementation MUST treat historical proposed SQL as evidence only. Names or constructs are adopted only when
  freshly derived and tested against current accepted authority.

## Non-functional requirements

- Fresh temporary SQLite only; foreign keys explicitly verified; deterministic setup/teardown.
- No migration, configured database, runtime wiring, broker/network, or ORM/new dependency.
- Query-plan controls reject unrelated corpus walks and unindexed current-proof access.
- SQL and tests remain compatible with the repository's supported Python/SQLite environments.

## API Contracts

The only production surface is a schema-definition/version contract and pure schema installer for
an explicitly supplied empty connection. It MUST NOT discover a path, open a configured database,
hydrate domain state, dispatch work, or infer accepted semantics.

N/A — no HTTP endpoint or external API exists. The Python installer accepts only an explicitly
supplied empty SQLite connection and returns an exact schema version or a typed failure.

## Data Models

| Family | Minimum durable role | Primary constraints |
| --- | --- | --- |
| Generation/profile | Application, execution profile, market-source profile | Immutable, exact binding, one selected profile per generation |
| Current proof | Checkpoint, controller, generation registry, direct routes, current heads | One LIVE per scope; direct-key totality; no history-derived currentness |
| Facts/effects | Facts/revisions, effects, claims, owners, acceptance | Immutable lineage; claim-before-I/O; canonical acceptance owner |
| Closure/market | Closure chain/head, protection state, market cursor | Same-owner nonbranching ordinals; one current cursor; profile/source scoped |

## Acceptance Criteria

### AC-1: Integrity constraints reject contradictory authority (FR-1, FR-3, FR-4, FR-7)

Given duplicate, branch, gap, cross-owner, cross-profile, and two-LIVE schema mutants
When each mutant is attempted in a fresh approved temporary database
Then the exact database-native constraint rejects it before commit

### AC-2: Direct current proof remains bounded (FR-2, FR-5)

Given valid current rows plus target/stress unrelated history and checkpoint-shaped impostors
When every serving-current lookup and acceptance lookup is explained and executed
Then exact indexes are used and only canonical effect/current rows can answer

### AC-3: Current authority is freshly derived and secret-free (FR-6, FR-8)

Given the current accepted profiles and historical proposed SQL as non-authoritative evidence
When the final schema inventory is compared to current authority
Then every capital row is profile-scoped, no raw secret/account identifier is stored, and no stale SQL is adopted by inheritance

## Edge Cases

- EC-1: Closing one leg, flatness, not-found, receipt, or local cancel cannot manufacture `CLOSED`.
- EC-2: A late acceptance after `CLOSED` retains prior proof and may only append invalidation evidence.
- EC-3: Disabled foreign keys, unsupported SQLite behavior, non-empty target, or configured-path
  discovery fails before schema execution.
- EC-4: DDL bytes differing from the human-approved digest return to the human gate before execution.

## Allowed paths

```yaml
allowed_paths:
  - app/execution_core/persistence/__init__.py
  - app/execution_core/persistence/schema.py
  - tests/execution_core/test_persistence_schema.py
  - work/queue/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/active/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/completed/keep/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/review/REV-0071/**
  - work/ledger.jsonl
```

Any additional source, test, work, PKL, ADR, dependency, migration, or workflow path requires a
reviewed scope amendment before editing.

## Out of scope and completion

- OS-1: Repository/hydration, transition, and outbox behavior — deferred to M2-I3/I4.
- OS-2: Runtime, owner lock, broker I/O, credentials, orders, configured DB, and migration — no
  authority exists in this schema-only order.
- OS-3: M2-I3+, M3, promotion, and `master` merge — each requires a later accepted checkpoint and
  separate activation.

Completion requires exact human-gated DDL, RED/negative constraints, direct-query plans, focused/
static/full-governance evidence, independent P0=0/P1=0 acceptance, exact publication, and an M2-I3
handoff. It grants no activation of M2-I3.

## HUMAN-GATE decision — exact WO-0165 to WO-0166 schema candidate

**Decision owner:** Ameen Mujtabaa

**Decision date:** 2026-08-21

**Decision:** APPROVED for the bounded proof step below

The approval binds all of these identities together:

| Identity | Approved exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-r1` |
| Candidate commit | `7a91de3d45b9dfc884f35c1eaa1d1b48b0a532de` |
| Candidate tree | `a99d387a6e6a7cd60a511d37ace26797a8bd3731` |
| `SCHEMA_DDL` SHA-256 | `b9565de1dab1dd6388980260ffd5089abe11ce887bbf67ccce2434848e252cbc` |
| `SCHEMA_DDL` UTF-8 length | `22,916` bytes |
| DDL source | `app/execution_core/persistence/schema.py` |

Before recording this decision, Codex independently parsed the `SCHEMA_DDL` string without
importing the module or opening SQLite and reproduced the approved byte length and digest. Codex
also verified the exact branch, commit, tree, clean worktree, matching remote branch, exactly 17
schema tests, only `pytest` `tmp_path` file connections, no in-memory/configured database path, and
the gate check before connection construction.

This decision authorizes only:

1. one unlock commit setting `_GATE_DIGEST` in
   `tests/execution_core/test_persistence_schema.py` to the approved digest above;
2. execution of exactly those 17 schema tests against fresh temporary file databases under
   pytest `tmp_path`, with no configured or in-memory database;
3. collection and return of RED/GREEN evidence, followed by opening independent review `REV-0071`.

It does not authorize configured database access, migration, repository/hydration or runtime work
(`M2-I3+`), credentials, broker/network calls, orders, promotion, merge to `master`, or any semantic
change to the DDL. Any byte-level change to `SCHEMA_DDL` requires a new digest and a new HUMAN-GATE
decision before execution.
