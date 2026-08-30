---
type: Work Order
title: M2-I6 crash, restore, fault, and boundedness closeout
status: CLOSED
work_order_id: WO-0170
wave: M2-I6
model_tier: strong
risk: critical
disposition: [RESULT_SUMMARY_KEPT, ARCHIVED]
owner: Codex implementation seat; fresh-context review seats REV-0118 and REV-0119
created: 2026-08-21
predecessor: WO-0169 closeout 0e9c5aadf003aae7dc66cf6df497b1a1d1d6d130 / tree b5f1042247804ad9fde4347c8729d5bde29a172d
branch: codex/m2-wo0170-crash-restore-closeout-r1
review_id: REV-0118; terminal M2/M3-preparation review REV-0119
execution_authority: >
  Ameen Mujtabaa's recorded serial-M2 authority, his instruction "You may proceed with the
  remaining sequence", and his current instruction to complete WO-0170 and all necessary work
  self-directedly authorize ordinary reversible implementation, exact fresh pytest-owned file-
  database fault/restore/boundedness tests, deterministic short soak smoke, governance, commits,
  pushes, bounded fresh review, root correction, WO-0170 closeout, terminal M2 evidence assembly,
  and documentation-only M3 entry preparation. The mandatory 24-hour soak remains NOT_RUN unless
  it actually completes uninterrupted. No DDL-byte change, configured or in-memory database,
  migration, runtime composition, credential, broker/network call, order, promotion, master merge,
  history rewrite, or M3 implementation is authorized.
allowed_paths:
  - app/execution_core/persistence/schema.py
  - tests/execution_core/test_persistence_fault_matrix.py
  - tests/execution_core/test_persistence_restore.py
  - tests/execution_core/test_persistence_boundedness.py
  - tests/execution_core/test_sqlite_boundary.py
  - tests_gated/execution_core/test_persistence_fault_matrix.py
  - tests_gated/execution_core/test_persistence_restore.py
  - tests_gated/execution_core/test_persistence_boundedness.py
  - tests/performance/m2_persistence_budget.py
  - harness/m2/**
  - work/queue/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/active/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/completed/keep/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/queue/WO-0171-m3-p1-deterministic-simulator-tape-clock.md
  - work/queue/WO-0172-m3-p2-semantic-replay-regression-corpus.md
  - work/queue/M2-EXECUTION-2026-08-21/01-M2-M3-EXECUTION-MAP.md
  - work/queue/M2-EXECUTION-2026-08-21/39-M2-TERMINAL-CLOSEOUT-AND-M3-ENTRY.md
  - work/review/REV-0118/**
  - work/review/REV-0119/**
  - work/ledger.jsonl
forbidden_paths: []
---

# Work Order: M2-I6 fault and restore closeout

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Active from exact accepted WO-0169 closeout

`[FABLE • FULL • verification-heavy closeout • no promotion gain]`

## Context and goal

Prove the complete M2 build under crash, restore, corruption, scale, and operator reconstruction.
This order may make only directly necessary M2 corrections found by its tests. It does not wire a
broker, promote the system, or claim M3 readiness without exact evidence.

## Functional requirements

- FR-1: The closeout harness MUST inject failure at every M2 write/commit/publication/claim/lock/cursor edge and verify
  old-complete or new-complete state after independent reopen.
- FR-2: The closeout harness MUST restore copied database/WAL evidence into an independent destination and reproduce exact
  integrity, current-proof, reconciliation, and non-serving classifications.
- FR-3: The closeout harness MUST kill mutants for duplicate/forked lineage, stale/missing routes, two-LIVE controllers,
  profile substitution, claim erasure, acceptance/closure gaps, cursor ordering, and history-fold
  startup.
- FR-4: The closeout harness MUST measure bounded direct hydration/startup and target/stress query plans using the frozen
  testing-model budgets; unexplained regression fails.
- FR-5: The closeout MUST run the required faulted soak for at least 24 hours on one exact build/profile and retain
  incident/operator reconstruction evidence. Interrupted or shortened soak remains `NOT_RUN`.
- FR-6: The closeout MAY evaluate the frozen R16 G0-G7 conjunction only if every named input is current and exact;
  otherwise retain `NOT_EVALUATED` with the missing coordinates.
- FR-7: The closeout MUST produce a self-contained M2 closeout/handoff manifest binding source, tests, schema,
  environment, evidence, limitations, and every `NOT_RUN` item.

## Non-functional requirements

- Fresh temporary or explicitly isolated restore destinations only; never the configured DB.
- No credentials, broker/network calls, orders, production runtime, or live/shadow mode.
- Failure seeds/traces and environment versions are retained and reproducible.
- No waiver converts environmental inability, Paper observation, or documentation into PASS.

## API Contracts

N/A — no HTTP or production runtime API is added. The harness accepts an exact M2 build/profile,
fresh temporary/restore destinations, a named fault schedule, and deterministic evidence sinks.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Fault case/result | Named edge, exact precondition, injected fault, reopened outcome | Reproducible; old/new complete classification only |
| Restore evidence | Source DB/WAL hashes, independent destination, integrity result | Source untouched; destination isolated; exact environment |
| Soak record | Build/profile, start/end, fault schedule, incidents, reconstruction | At least 24 uninterrupted hours or `NOT_RUN` |
| M2 closeout manifest | Source/test/schema/environment/evidence hashes and limitations | Self-contained, exact, no PASS laundering |

## Acceptance Criteria

### AC-1: Complete fault and restore proof (FR-1, FR-2)

Given every named fault edge plus independent restore/corruption variants
When the harness crashes, reopens, and verifies each destination
Then every result is old-complete, new-complete, or exact fail-closed refusal with no blind resend

### AC-2: Mutants and scale cannot bypass M2 authority (FR-3, FR-4)

Given directness, uniqueness, lineage, profile, claim, closure, cursor, and history-fold mutants at target/stress scale
When the decisive mutation and boundedness gates execute
Then every mutant fails and accepted query/work budgets remain within the frozen limits

### AC-3: Soak and R16 state remain evidence-faithful (FR-5, FR-6)

Given one exact build/profile and the current R16 inputs
When the soak and conjunction evaluation are attempted
Then a full 24-hour exact record passes or remains `NOT_RUN`, and R16 passes only with every exact current input

### AC-4: Closeout is independently reproducible (FR-7)

Given the final candidate and closeout manifest
When an independent reviewer rehashes and reruns its named gates
Then the evidence reproduces with P0=0/P1=0 or M2 remains unclosed

## Edge Cases

- EC-1: Interrupted/shortened soak, destination collision, source-file mutation, or missing WAL
  remains failed/`NOT_RUN`; no partial credit.
- EC-2: Environmental inability or unavailable target hardware is recorded exactly and never
  converted to a passing proxy result.
- EC-3: A production correction discovered by closeout stops at an exact scope amendment; the
  harness cannot silently edit an unlisted production path.

## Activated path boundary

```yaml
allowed_paths:
  - app/execution_core/persistence/schema.py
  - tests/execution_core/test_persistence_fault_matrix.py
  - tests/execution_core/test_persistence_restore.py
  - tests/execution_core/test_persistence_boundedness.py
  - tests/execution_core/test_sqlite_boundary.py
  - tests_gated/execution_core/test_persistence_fault_matrix.py
  - tests_gated/execution_core/test_persistence_restore.py
  - tests_gated/execution_core/test_persistence_boundedness.py
  - tests/performance/m2_persistence_budget.py
  - harness/m2/**
  - work/active/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/completed/keep/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/queue/WO-0171-m3-p1-deterministic-simulator-tape-clock.md
  - work/queue/WO-0172-m3-p2-semantic-replay-regression-corpus.md
  - work/queue/M2-EXECUTION-2026-08-21/01-M2-M3-EXECUTION-MAP.md
  - work/queue/M2-EXECUTION-2026-08-21/39-M2-TERMINAL-CLOSEOUT-AND-M3-ENTRY.md
  - work/review/REV-0118/**
  - work/review/REV-0119/**
  - work/ledger.jsonl
```

Any production correction needs an additive exact scope amendment naming the owning M2 file and
demonstrated defect before edit. The two review paths are finite: REV-0118 owns the WO-0170 green
candidate and at most one correction re-review; REV-0119 owns the terminal combined M2 and M3-entry
preparation review.

The ordinary `tests/execution_core/**` files are pure/static controls and remain part of default
discovery. The three exact `tests_gated/execution_core/**` files own SQLite-bearing fresh-file
proof and remain outside default discovery behind the existing application-owned installer gate.
This split prevents a skipped or locally provisioned database from masquerading as ordinary green
evidence.

`app/execution_core/persistence/schema.py` is admitted only on the quarantined WO-0170 proof branch
for one exact authorization-only change from literal boolean `False` to literal boolean `True`.
The canonical branch retains `False`; `SCHEMA_DDL`, its expected digest, and every other source byte
must remain unchanged. A substantive failure ends that execution attempt before remediation.

## Out of scope and completion

- OS-1: Adapter/runtime composition and broker/network/credentials/orders — no operational activity.
- OS-2: Configured DB and promotion — only fresh isolated evidence destinations; no readiness gain
  beyond proven M2 closeout.
- OS-3: M3 implementation and `master` merge — separate future authority.

Completion requires exact independent acceptance, full lifecycle closeout, M2 manifest, honest
soak/R16 state, and a separately reviewed M3 entry handoff. It activates neither M3 order.

## REV-0118 consolidated correction checkpoint — 2026-08-29

The first whole-candidate review returned `ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0. All three
findings are accepted and corrected at their proof-contract roots in canonical source
`a18924131e0e2534bbdf51fb9374dbdd5bac4c9f`, tree
`c9ee080be59a4847e82258c615289da456c2f195`:

1. claim, claim-erasure, acceptance/closure-gap, and cursor-ordering obligations now map to
   dedicated failure-capable tests that isolate the stated invariant;
2. boundedness now measures actual checkpoint load, decode, and compact restoration at target
   and stress, consumes the frozen startup SELECT/elapsed and memory budgets, and checks plans at
   both coordinates; and
3. restore snapshot and verification reject destination database, WAL, and SHM collisions even
   when the corresponding source sidecar is absent.

No application persistence or DDL byte changed. Canonical `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`
remains exact boolean `False`. One correction-only flag-true proof is recorded in
`work/review/REV-0118/execution-packet-r6.md`; after it passes, REV-0118 receives its one finite
correction re-review against the exact final canonical head.

R6 then passed all six fault-matrix cases and failed only the boundedness setup: after setup
stored a real checkpoint, the legacy selection-only probe still requested the pre-checkpoint
`None` head and was correctly refused as a conflict. Canonical test-only correction
`106fa7c4be39adc974af038264ed74d4349f19c7` now propagates the exact repository-issued
checkpoint head into every selector sample. R6 is quarantined; R7 is the one exact corrected
fresh-file execution recorded in `work/review/REV-0118/execution-packet-r7.md`.

R7 PASSED all seven corrected fresh-file cases at flag-only proof commit
`94ca21f2cf0a786ac92e0ef15c8cb3966e0de1a8`, tree
`ac046cc8590aa668e7e324f3d8c06f24d6cc2633`. The canonical source remains exact boolean
`False`; the proof branch and databases are quarantined evidence. Final ordinary/static
regression and the finite REV-0118 correction re-review remain before closeout.

The final ordinary suite then found one frozen import-direction violation: the new boundedness
test imported setup support directly. Canonical `c7e394f52782a9b398ed89bfdc55b45bc09499b4`
removes that extra dependency and reaches the identical approved helper through the already-
authorized checkpoint SQLite test module. Its focused pure boundary test passes. R8 rebinds the
seven-case proof to these final test bytes; no application or DDL behavior changed.

R8 PASSED all seven held cases at proof commit
`b14cbb88061aab09f69ce219e9c1427a01873761`, tree
`f4571503ad5a3b507b0ee33997d3335c317f68b4`. The final canonical ordinary suite passed all
2,310 cases, the R2 oracle passed all 61, and all named static/import/governance gates passed.
The candidate is ready for the finite REV-0118 correction re-review.

REV-0118 finite correction re-review closed all three substantive P1 findings but returned one
P0: six new evidence Markdown files contained an extra blank line at EOF, so the candidate's exact
base-to-head `git diff --check` claim was false. The correction removes only those blank lines,
updates the R7 reference to the changed R6 packet hash, and rebinds every affected manifest and
ledger hash. Exact checks from both the original reviewed candidate and the final implementation
source now pass. One narrow same-seat verification may confirm only this correction and no drift;
it is not another design-review round.

## Terminal acceptance and completion

REV-0118 final correction verification accepted candidate
`2051afe2bbc21918fac6b69875e0a536fe722e49`, tree
`2d3fef0011412ec432fd26f43f526be6946ad00c`, with P0=0/P1=0/P2=0 and
`Unverified: NONE`. All three original substantive findings are closed, and the sole correction-
review P0 was resolved by exact diff-clean evidence plus hash rebindings with zero application,
test, DDL, flag, or outcome drift.

The accepted implementation/test source remains
`c7e394f52782a9b398ed89bfdc55b45bc09499b4`, tree
`2d5c662f569ec3ee792216863fe46213551773a8`. Final evidence is 60 focused pure controls, 2,310
ordinary execution-core tests, 61 R2 cases, R4's 259-case full matrix, R5's 180-case one-cycle
smoke honestly classified `NOT_RUN`, and R8's seven correction cases. Ruff, format, mypy, six
import contracts, install/version/ledger/PKL/disposition/scope, and exact diff hygiene pass.

DDL remains 190,705 UTF-8 bytes at
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, schema blob
`164de10ad9fef6ce37324840aff59b5b68c07d2a`, with canonical flag exact boolean `False`.
Every flag-true branch and generated database remains quarantined evidence and is not an
implementation predecessor.

The 24-hour soak remains `NOT_RUN`; R16 G0-G7 remains `NOT_EVALUATED` for the exact missing
coordinates in the manifest. These honest residuals grant no operational, promotion, or trading
authority. Terminal combined M2/M3-preparation review REV-0119 is documentation/governance only.

## Completion disposition

- [x] `RESULT_SUMMARY_KEPT`
- [x] `ARCHIVED`
- [x] PKL/ADR update not required: the implementation conforms to the accepted M2 architecture;
  no new architecture decision was introduced.

```yaml
fable_done:
  status: VERIFIED
  evidence: "REV-0118 ACCEPT P0=0/P1=0/P2=0; 2310 ordinary, 61 R2, R4 259-case and R8 7-case fresh-file proofs passed; static/governance/diff gates passed; DDL unchanged and canonical flag False."
  command: "See work/review/REV-0118/result-r2.md and harness/m2/M2-CLOSEOUT-MANIFEST.md."
  terminal_state: "WO-0170 CLOSED — M2 implementation complete; REV-0119 terminal M2/M3-preparation review pending"
```

## Distillation decision

Keep this work order, closeout manifest, and REV-0118 chain as durable crash, restore,
boundedness, soak-status, and review-correction evidence. Delete no source, tests, review history,
or preserved pytest evidence. No M3 work order is activated by this closeout.

## Post-closeout R16 label correction — 2026-08-29

The original FR-6/AC-3 and closeout paragraphs retain the historical `R16 G0-G7` wording that was
accepted when no input manifest was available. Subsequent repository and introduction-commit
tracing established that the eight gates were never defined in repository authority. Ameen
Mujtabaa authorized the additive disposition in
`work/queue/M2-EXECUTION-2026-08-21/40-R16-G0-G7-LABEL-DISPOSITION.md`: the orphaned label is
retired and is no longer a current residual or gate. The actual R16 contract, its manual-rule
ratification, all M2 implementation/test evidence, the 24-hour soak `NOT_RUN`, and every
operational prohibition remain unchanged.
