# WO-0152 E3 RED contract — generated acquisition-generation conformance

Status: CANDIDATE — DRAFT ONLY — NOT ACTIVE  
Date: 2026-08-07  
Work order: WO-0152  
Review packet: REV-0059

[FABLE - FULL - verification: DIRECT plus independent review - task: test-only
generated, stateful, replay-model, boundedness, and mutation conformance]

## Decision and authority boundary

This is the exact candidate contract for the user-authorized coverage-gate
ordering amendment. It does not change the accepted E1/E2 implementation,
coverage threshold, runtime, or architecture.

- E2 implementation predecessor: a2b84abc1914517cf591f27fb88f0b20b2a47ef7.
- GitHub Actions run #741 / ID 31185454392: both unchanged Python 3.11 and
  3.12 jobs passed all 5,934 tests and their functional/static checks. The
  run is negative evidence for the unchanged 93% coverage gate only: it
  reported 91.34%, so it is not overall CI success.
- WO-0151 remains effectively REVIEW. Neither WO-0151 nor WO-0152 may become
  effectively closed, and M1 may not be claimed complete, until a later exact
  paired E2/E3 candidate passes unchanged Python 3.11 and 3.12 CI at 93%.
- Accepted ADR-020 R2, ADR-021 R2, ADR-023 R1, ratification, and the retained
  WO-0151 R11/R11-R1 evidence remain controlling.

This contract authorizes no action by itself. It becomes eligible for
activation only after its exact manifest receives an independent ACCEPT with
P0=0 and P1=0. Until then, no E3 test file is created or run.

## Fable gate

fable_gate:
  goal: "Add one bounded, behavior-first E3 proof layer for the accepted E1/E2 serial acquisition-generation contracts without production changes."
  assumptions:
    - "Run #741 is functional/static success and coverage-only negative evidence, as recorded above."
    - "The listed public E1/E2 interfaces and the one named environmental predecessor fixture are sufficient to construct every positive E3 trace."
    - "A finite trace codec and public-observer replay model prove test-model consistency only, not production persistence or hydration."
  approach: "Freeze a one-file test plan, prove it statically constructible, then use deterministic public-contract traces, independent observers, bounded generated cases, and test-owned oracle mutations."
  out_of_scope:
    - "Production-code, public-API, runtime, persistence, database, SQL/DDL, broker, network, credential, CI-workflow, coverage-config, M2, master, PR, deletion, and cleanup changes."
    - "Production snapshot hydration, storage decoding, crash recovery, adapter recovery, and broker recovery."
    - "A third test batch or any coverage-only test expansion after the two bounded batches."
  done_when:
    - "Every E3 control below has fresh, failure-capable evidence."
    - "No production discrepancy is found; any such discrepancy is returned to E1/E2."
    - "The exact paired E2/E3 candidate passes unchanged Python 3.11 and 3.12 CI at 93%."
  blast_radius: "One new pure execution-core test module plus explicitly listed lifecycle/evidence records."

## Exact test boundary

### Permitted production-facing contracts

E3 may use only declared public E1/E2 values, constructors, reducers,
transition outputs, and bounded readers:

- package exports from app.execution_core, including initial_execution_authority_state,
  apply_execution_authority_input, AcquisitionMandate, DualMandateBinding,
  initialize_acquisition_controller, reduce_acquisition_controller,
  begin_acquisition_generation, create_acquisition_effect,
  claim_acquisition_effect, project_acquisition_controller,
  GenerationRegistry, AcquisitionLineageIndex, PositionProtectionState,
  the canonical FILL/CORRECT/BUST fact values, and public value/identity
  types;
- declared public authority-module functions refresh_acquisition_context and
  project_acquisition_admission;
- declared public VenueRecoveryBook acquisition-bootstrap projection and
  direct public registry/lineage readers; and
- immutable public transition/status/projection values returned by those
  operations.

E3 MUST NOT import or call a production name beginning with an underscore,
read a private attribute, construct an opaque/sealed production value, patch
production state, add a production seam, scan retained history, or use an
existing test helper or fixture. Direct readers must be called only for a
known generation/root/effect identifier; they are never enumerated.

### Sole environmental predecessor exception

The new test module may define exactly one local helper named
_serving_environment_predecessor_fixture. It starts from the public
initial_execution_authority_state result and may make one test-only,
pre-bootstrap environmental setup with only these public coordinates:

1. phase = SERVING;
2. mode = ACTIVE;
3. supervisor_fence = PAPER_MUTATION_ELIGIBLE;
4. kill_engaged = False;
5. one fixed SessionId; and
6. one fixed RequestBudget.

It represents deferred runtime/configuration setup, grants no acquisition
authority, and is not production behavior, a hydration mechanism, or a new
test seam. No object mutation is permitted after this setup boundary. Every
subsequent bootstrap, admission, controller, fact, protection, effect, and
claim action must use only the permitted public contracts above.

The suite MUST prove all three boundary controls:

- the unmodified initial authority remains non-serving and cannot create a
  positive acquisition trace;
- a generic CreateBrokerEffect(BUY) remains refused; and
- a static import/source control rejects an E3 module that imports a private
  execution-core name, reads a private production attribute, or performs a
  post-bootstrap production-object mutation.

## Functional requirements and named controls

### FR-01 — Serial generation behavior

E3-01 MUST run a deterministic A -> B -> C history, with a target-symbol
genesis created while an unrelated symbol already has account-level venue
history. It MUST assert strictly increasing successor ordinal, immutable
direct A/B/C identity/lineage, at most one LIVE generation, one active normal
protection/broker authority, and direct known-ID reads for the earliest and
current generation.

### FR-02 — Late canonical facts and exactness

E3-02 MUST interleave valid late A FILL, TRADE_CORRECT, and TRADE_BUST facts:
before successor creation, around B's first fill, and before final claim.
For each accepted canonical fact it MUST independently observe exactly one
generation-local economic update and exactly one aggregate economic delta.
It MUST verify controller-currentness advance and final-claim refusal when a
retired-generation economic change invalidates the claim.

E3-03 MUST use one compact parameter matrix for duplicate, reordered, exact
replay, changed-payload, fork, stale-head, stale-ordinal, cross-scope,
incompatible emergency-compatibility, unsafe-genesis, and unsafe-successor
variants. Every invalid variant MUST preserve the previously serving BUY
authority and must not create another live generation, claim, or effect.

### FR-03 — Generated and stateful behavior

E3-04 MUST supply a deterministic, shrinkable stateful rule machine with:

- a documented fixed seed;
- at most 25 commands per example;
- 30 to 50 examples in the first complete batch; and
- commands constrained to the frozen public operations and known identifiers.

Its independent observer is observational only. It records public
dispositions, controller status, known direct routes/records, known effect and
claim identifiers, protection projection, and aggregate economics; it is not
a second production reducer. A minimized failing public trace is retained as
evidence and stops E3 for bounded E1/E2 remediation.

### FR-04 — Checkpoint-replay model

E3-05 MUST encode a finite public input trace and named public observer fields
into a test-owned, schema-neutral representation. It MUST validate and decode
that representation before replaying from the same environmental predecessor
through public reducers. The replayed observer record MUST equal the
uninterrupted observer record.

Malformed, missing, duplicate, forked, stale, inconsistent, or cross-scope
codec mappings MUST be rejected before reducer invocation. This is a finite
trace/checkpoint-replay model only. It MUST NOT claim production hydration,
database decoding, persistence, crash recovery, adapter recovery, or broker
recovery; those remain deferred to M2 or later authorized work.

### FR-05 — Bounded live work

E3-06 MUST run a moderate 32-generation serial history. It MUST retain direct
known-ID lookup for generation zero and the current generation while proving
that a live transition does not materialize or traverse audit/history
collections, effects, owners, closure collections, predecessor chains, or
unbounded hydration input. The proof MUST use a structural public-reader
sentinel, not elapsed-time timing or a coverage count.

### FR-06 — Failure-capable proof controls

E3-07 MUST consume the accepted E1/E2 requirement-to-control and named
production-mutation inventory; it does not duplicate unit-level source
mutations. E3 adds only test-owned oracle/trace sensitivity controls. Each
control MUST fail when its own observer omits one decisive comparison:

- identity coordinate or direct lineage equality;
- genesis/successor head or ordinal;
- controller-head advance;
- one-LIVE uniqueness;
- aggregate exactly-once economics;
- emergency-recovery compatibility;
- generation-local capacity;
- trace-codec mapping consistency; or
- bounded direct lookup.

The original comparison is then restored. No production file, condition, or
runtime value may be mutated for E3 mutation evidence.

### FR-07 — Evidence and downstream handoff

E3-08 MUST produce a concise M1-to-M2 handoff listing frozen public
interfaces, the schema-neutral durable observer/field map, the single
composite transition boundary, executed traces and test-owned sensitivity
controls, and deferred M2 database/crash-recovery, M4 correlation, and M7/M8
observation obligations. It MUST explicitly state that no runtime/persistence
cutover, master landing, or M1-complete claim occurred.

## RED discipline, batches, and stop rules

Production code is frozen. For E3, RED means each new behavior assertion is
first paired with a failure-capable invalid trace or test-owned observer
omission that demonstrates the assertion can fail for the stated reason.
The suite may then pass only by observing the accepted public implementation;
there is no GREEN production edit in this work order.

Batch 1 is the complete requirements-derived scenario set above. Batch 2 is
permitted only for a named uncovered public behavior or a realistic
counterexample found by Batch 1. Coverage percentage alone cannot justify
Batch 2. If the paired exact-head gate remains below 93% after Batch 2, stop
and return a coverage re-adjudication; do not grow the generator, mutation
set, test surface, threshold, exclusions, or pragmas.

Any real public implementation/model disagreement freezes the minimized trace
and stops for bounded E1/E2 remediation. E3 must not change production code,
weaken the observer, or reinterpret the disagreement as coverage work.

## Exact activation-time file boundary

Application/test implementation may modify only:

- tests/execution_core/test_acquisition_stateful.py; and
- the explicitly listed WO-0152 lifecycle/evidence paths below.

Lifecycle/evidence paths are:

- work/queue/WO-0152-reset-kernel-e3-generation-conformance.md;
- work/active/WO-0152-reset-kernel-e3-generation-conformance.md;
- work/completed/keep/WO-0152-reset-kernel-e3-generation-conformance.md;
- work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md;
- work/ledger.jsonl;
- pkl/project/goals.md;
- pkl/architecture/architecture-map.md;
- pkl/log.md;
- docs/adr/ARCH-RESET-2026-07-RATIFICATION.md; and
- work/review/REV-0059/WO-0152-RED-CONTRACT.md,
  WO-0152-RED-CANDIDATE-MANIFEST.md, request.md, result.md,
  activation-disposition.md, implementation-manifest.md, evidence.md, and
  handoff.md.

The earlier removal of the exact 340-line E2 coverage experiment from
tests/execution_core/test_acquisition.py is retained separately in REV-0058.
It is not an E3 implementation path.

## Verification and closeout requirements

At coherent checkpoints E3 must run only authorized pure/static checks:

- focused E3 tests and the relevant E1/E2 execution-core tests;
- the existing pure execution-core suite;
- Ruff check and format verification on changed paths;
- mypy on changed production paths (none expected) and relevant test/static
  checks;
- import-boundary, scope, ledger, PKL, disposition, hash, and diff checks;
- the full-repository branch-coverage gate and unchanged exact-head Python
  3.11/3.12 CI only after the normal activation/implementation gates permit
  them.

Existing test fixtures may not create a database or execute SQL/DDL under
this contract. No database-capable fixture is part of E3.

evidence:
  command: "Preflight is static only; execution begins only after independent ACCEPT and activation."
  result: NOT_RUN
  decisive_output: "No E3 test exists or has run at this candidate stage."

fable_done:
  task: "WO-0152 RED-contract freeze"
  done_when_results:
    - "Exact manifest hashes every candidate input."
    - "Independent result is ACCEPT with P0=0 and P1=0."
    - "Human-authorized automatic activation condition is then recorded."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence: []
  status: UNVERIFIED

