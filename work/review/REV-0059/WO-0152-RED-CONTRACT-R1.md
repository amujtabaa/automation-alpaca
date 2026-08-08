# WO-0152 E3 RED contract R1 — constructible test-only setup and behavior-first conformance

Status: CANDIDATE — DRAFT ONLY — NOT ACTIVE  
Date: 2026-08-07  
Work order: WO-0152  
Review packet: REV-0059  
Supersedes for preflight only: WO-0152-RED-CONTRACT.md  
Retained predecessor: WO-0152-RED-CONTRACT.md and its independent result.md

[FABLE - FULL - verification: DIRECT plus independent review - task: one bounded
test-only generated/stateful/replay/boundedness proof layer]

## 1. Decision, retained evidence, and authority

This is a replacement RED candidate under the user-authorized WO-0152 R1
clarification. It changes no accepted E1/E2 implementation, public interface,
architecture decision, coverage threshold, runtime, persistence behavior, or
production authority.

The initial candidate remains immutable negative preflight evidence:

- R0 contract SHA-256: ce27017d419b2b537d88b618dfc0bdecdc1b01a0a7df3db5f0b5c69b6adf9ce4;
- R0 manifest SHA-256: ba9428c2db4bbb9fc0327f9fae9b3de51c16b1fe93c0d98ea4c59bc008116cfe;
- R0 independent result SHA-256:
  ae398751c5c64478748c4fd15a9a9a4124858c449a604d9052b2034f1e592b57;
- R0 verdict: ACCEPT-WITH-CHANGES, P0=0/P1=1/P2=0.

R0 correctly found that no public M1 configuration producer can mint the
opaque DualMandateBinding required by AcquisitionMandate. A focused
constructibility follow-up found a second, separate gap: a root-owning retired
generation cannot reach the parent acceptance closure needed for successor
admission through public M1 inputs alone. Public terminal-leg observations
remain sufficient for the lifecycle evidence but intentionally cannot certify
the parent set; that adapter certification is deferred to M2.

R1 supplies only two test-only setup capabilities to model those two deferred
external sources. They are neither production authority nor a claim that M1
implements configuration or adapter certification.

The accepted E2 implementation predecessor is
a2b84abc1914517cf591f27fb88f0b20b2a47ef7. GitHub Actions run #741 / ID
31185454392 remains functional/static positive evidence and coverage-only
negative evidence: its unchanged Python 3.11 and 3.12 jobs each reported 5,934
passed tests but failed the unchanged 93% coverage gate at 91.34%. WO-0151
therefore remains REVIEW. Neither WO may become effectively CLOSED, and M1 may
not be claimed complete, until a later paired E2/E3 exact candidate passes
unchanged Python 3.11 and 3.12 CI at 93%.

This document grants no execution authority. Before the only permitted E3 test
module is created or run, the exact R1 manifest must receive an independent
ACCEPT with P0=0/P1=0.

## 2. Fable gate

fable_gate:
  goal: "Add a constructible, behavior-first E3 proof layer for accepted serial acquisition-generation behavior without production changes."
  assumptions:
    - "Run #741 is functional/static success and coverage-only negative evidence."
    - "The three setup fixtures below are sufficient and no fourth setup seam is required."
    - "A finite trace codec and public-observer replay prove a test model only, never production hydration."
  approach: "Freeze one exact test module and its two narrowly sourced test-only setup exceptions, then use deterministic public-contract traces, independent observers, bounded generated cases, and test-owned sensitivity controls."
  out_of_scope:
    - "Production code, public API, runtime, persistence, database, SQL/DDL, broker, network, credential, CI workflow, coverage configuration, M2, master, PR, deletion, cleanup, force-push, and rebase."
    - "Production snapshot hydration, storage decoding, crash recovery, adapter recovery, broker recovery, or a new configuration/certification boundary."
    - "A third E3 batch or coverage-only test growth after the two named batches."
  done_when:
    - "Every R1-defined E3 control has fresh, failure-capable evidence."
    - "A real public behavior/model disagreement is frozen and returned to E1/E2 rather than hidden in E3."
    - "One later paired E2/E3 candidate passes unchanged Python 3.11 and 3.12 CI at 93%."
  blast_radius: "One new pure execution-core test module plus exactly enumerated work-order, PKL, ledger, provenance, and REV-0059 evidence records."

## 3. Exact boundary and three setup fixtures

### 3.1 Public operational contract

After fixture setup, every bootstrap, acquisition admission, controller,
effect, claim, discovery, terminal observation, canonical fact, protection,
rebase, currentness, and reader action MUST use only declared public production
constructors, reducers, transition outputs, and bounded direct readers:

- package exports from app.execution_core;
- declared public authority functions refresh_acquisition_context and
  project_acquisition_admission;
- declared public VenueRecoveryBook direct readers, including effect,
  owner, active_attempt, closure_head, acquisition_correlation, direct
  registry record, and direct lineage route readers for a known identifier;
- immutable public transition, status, and projection values returned by those
  operations.

The test may never enumerate effects, claims, owners, closure history,
reconciliations, input records, audit collections, or other unbounded retained
history. It may never construct a sealed value with object.__new__, inspect a
private production attribute, use getattr to bypass a direct reader, import an
existing test fixture, or post-setup mutate a production object.

### 3.2 Existing environmental predecessor fixture

_serving_environment_predecessor_fixture is retained from R0. It starts from
public deny-only initial_execution_authority_state and makes exactly one
pre-bootstrap test-only environment setup. It may use a copied state and
object.__setattr__ only for these exact coordinates:

1. phase = SERVING;
2. mode = ACTIVE;
3. supervisor_fence = PAPER_MUTATION_ELIGIBLE;
4. kill_engaged = False;
5. one fixed SessionId; and
6. one fixed positive RequestBudget.

It is deferred runtime/configuration setup, not acquisition authority. The raw
initial state remains non-serving and cannot produce a positive acquisition
trace. The fixture result is used only as a predecessor; it is never mutated
after that boundary.

### 3.3 R1 configuration fixture — fixed approved mandates

_approved_acquisition_mandates_fixture may call exactly
app.execution_core.acquisition._mint_dual_mandate_binding at one statically
whitelisted AST call site. That call site may be evaluated only to make the
three fixed complete immutable operator-approved A, B, and C
AcquisitionMandate inputs before genesis.

The helper MUST:

- use fixed distinct acquisition and protection mandate identities for A, B,
  and C; one fixed PositionScope and SessionId; fixed complete acquisition
  terms; and equal bounded EmergencyRecoveryCompatibility;
- construct each corresponding public ProtectionMandate and then use the
  returned binding only to construct the matching public AcquisitionMandate;
- return only the immutable A/B/C mandates, never a binding, capability,
  controller, authority state, effect, claim, broker object, actor, or runtime
  object;
- run before bootstrap and never be called from a stateful command;
- prove malformed/mismatched scope, session, identity, or compatibility data
  cannot be silently substituted for the fixed fixture data.

The helper grants no execution, controller, currentness, effect, claim,
broker, runtime, persistence, or actor authority. It does not add a
configuration factory to production.

### 3.4 R1 deferred-certification fixture — one exact terminal parent

_certified_terminal_parent_fixture may model only the deferred M2 adapter
certification that pure M1 intentionally lacks. It is callable only after a
fully public lifecycle has already created and claimed the exact acquisition
BUY effect, discovered every named owned leg, and applied public terminal
observations for every named leg.

The helper takes exact known identifiers and must fail closed unless all of the
following are independently checked before the private transition:

1. the supplied authority, execution, PositionScope, EffectId, exact
   DispatchClaim occurrence, and effect scope agree through public direct
   readers;
2. the parent effect exists, is OPEN, names the exact claim, and has no prior
   acceptance proof;
3. the fixed trace has exactly one named owned leg; its matching direct owner
   has the exact effect/scope, no active attempt, and a terminal closure head.
   The private reducer's bounded current-leg summary remains the only
   authority for confirming that no active owned leg remains; the fixture
   never scans an owner or closure history;
4. an active attempt, unresolved reconciliation, inconsistent target
   execution, or a different known leg is never accepted as equivalent
   evidence;
5. the exact target execution is flat and internally consistent;
6. the fixed proof kind, EvidenceReference, and one fixed 32-byte proof digest
   name the same effect scope and exact claim; and
7. the authority input is a copied, otherwise byte-for-byte preserved
   pre-certification authority state.

Only after those checks, the helper may construct the one exact
AcceptanceProof and CloseAcceptanceSet and, within one temporary
unittest.mock.patch.object context, set only
app.execution_core.venue._external_acceptance_closure_is_certified to return
True. Inside that same context it may call exactly one static call site of
app.execution_core.venue._apply_venue_input with the exact prechecked book,
execution, and CloseAcceptanceSet. The context manager MUST restore the hook
before the helper returns or raises.

The helper MUST require an APPLIED transition and prove:

- the post-transition public parent effect is CLOSED and carries the exact
  proof;
- all output execution economics and all authority fields except the copied
  state's venue book are unchanged;
- currentness, session, budget, effect authority, claims, runtime, persistence,
  and actor coordinates are unchanged; and
- the original authority/book remain unchanged while only the copied authority
  receives the resulting venue book.

This fixture is an adapter-certification setup only. It does not grant a
runtime capability, an externally callable closure capability, a generic
private venue reducer, or authority to certify any other effect.

### 3.5 Required static allowlist control

The new module tests/execution_core/test_acquisition_stateful.py MUST contain a
self-source AST control that rejects every private production import,
attribute, call, patch target, object.__setattr__, and dynamic lookup except
these exact, separately owned occurrences:

| Fixture | Exact exception | Static limit |
| --- | --- | --- |
| _serving_environment_predecessor_fixture | copy.copy and object.__setattr__ | only the six environmental fields in section 3.2 |
| _approved_acquisition_mandates_fixture | app.execution_core.acquisition._mint_dual_mandate_binding | one AST call site, pre-genesis, fixed A/B/C configuration only |
| _certified_terminal_parent_fixture | AcceptanceProof, AcceptanceProofKind, CloseAcceptanceSet, app.execution_core.venue._apply_venue_input, and temporary patch.object of _external_acceptance_closure_is_certified | one AST reducer call site, one fixed patch target, one fixed digest, and copied authority.venue only |

The control MUST also reject imports from tests.*, private-value construction,
object.__new__, private production attribute reads, private calls outside the
two named R1 helpers, a post-setup object mutation, a second private reducer
or minter call site, a nonliteral patch target, and any production source
edit. It MUST use an exact expected set, not a broad prefix allowlist. A
separate negative source specimen for each prohibited class must cause this
control to fail for the intended class.

## 4. Functional requirements and failure-capable controls

### FR-01 — Constructible serial A -> B -> C behavior

E3-01 MUST start from the exact environmental fixture and fixed approved
mandates, establish target bootstrap/admission through public contracts, and
run an A -> B -> C history with unrelated-symbol account-level venue history.
It MUST assert strictly increasing successor ordinal, immutable direct A/B/C
identity and lineage, at most one LIVE generation, one active normal
protection/broker authority, and direct known-ID reads for earliest and current
generation.

### FR-02 — Late canonical facts and exact economics

E3-02 MUST interleave valid late A FILL, TRADE_CORRECT, and TRADE_BUST facts
before successor creation, around B first fill, and before final claim. It MUST
prove, using public projections and an independent test model, one
generation-local update and exactly one aggregate delta per accepted canonical
fact; controller-currentness advance; and final-claim refusal after a retired
generation economic change.

E3-03 MUST use one compact invalid-input matrix: duplicate, reorder, exact
replay, changed payload, fork, stale head, stale ordinal, cross scope,
incompatible emergency compatibility, unsafe genesis, and unsafe successor.
Every invalid input MUST retain prior serving BUY authority and create no new
LIVE generation, effect, or claim.

### FR-03 — Parent closure and successor constructibility

E3-04 MUST demonstrate that a positive root-owning predecessor does not
receive parent closure before the fully public claim/discovery/terminal-
observation lifecycle, that invalid fixture preconditions refuse without a
transition, and that the exact deferred-certification fixture installs one
CLOSED parent only after the required public lifecycle. B successor admission
must then use public controllers/readers; the fixture cannot create, register,
or claim B.

### FR-04 — Stateful generated behavior

E3-05 MUST supply a deterministic, shrinkable stateful rule machine using a
documented fixed seed, at most 25 commands per example, and 30 to 50 examples
in batch one. Its independent observer records public dispositions, controller
status, known direct routes and registry records, known effect/claim IDs,
protection projection, and aggregate economics. It is observational only, not
a second reducer. A minimized real disagreement freezes the trace and returns
it to E1/E2.

### FR-05 — Schema-neutral replay model

E3-06 MUST encode a finite public input trace and named public observer fields
into a test-owned schema-neutral representation, validate/decode it before any
reducer call, replay it from the same three setup fixtures plus public
reducers, and compare the replayed public observer record to the uninterrupted
record. Missing, duplicate, forked, stale, inconsistent, or cross-scope
encodings MUST reject before reducer invocation. This proves neither production
hydration nor database, crash, adapter, or broker recovery.

### FR-06 — Bounded direct live work

E3-07 MUST run a moderate 32-generation serial history. It MUST preserve
direct known-ID routing to generation zero and current generation while a
structural public-reader sentinel proves that a live decision does not
materialize or traverse audit/history collections, effects, owners, closure
collections, predecessor chains, or unbounded hydration input. Timing and
coverage counts are not boundedness evidence.

### FR-07 — Test-owned sensitivity controls

E3-08 MUST consume the frozen E1/E2 requirement-to-control and production
mutation evidence. E3 adds only test-owned trace/model sensitivity controls:
identity/direct-lineage equality, successor head/ordinal, controller-head
advance, one-LIVE uniqueness, aggregate exactly-once economics, emergency
compatibility, generation capacity, codec consistency, bounded direct lookup,
and the R1 allowlist. Each omitted test-model comparison MUST make its assigned
control fail and be restored. E3 MUST NOT mutate or monkeypatch a production
condition to create a mutant.

### FR-08 — Discrepancy stop and handoff

E3-09 MUST preserve an observed public behavior/model discrepancy as a
minimized trace and stop for bounded E1/E2 remediation. It must not change
production code, weaken the model, or classify a defect as coverage work.

E3-10 MUST prepare an M1-to-M2 handoff listing frozen public interfaces, the
schema-neutral durable observer map, composite transition boundary, executed
traces and sensitivity controls, and deferred M2 database/crash recovery, M4
correlation, M7/M8 observation, runtime, master landing, and final M1 gates.

## 5. RED batches, acceptance, and stop rules

Production code is frozen. For E3, RED means every behavior assertion has a
paired invalid trace or test-owned observer omission that can fail for the
stated reason. The only implementation is test code that observes accepted
public behavior.

Batch 1 is the complete R1 requirements-derived test set. Batch 2 is allowed
only for a named uncovered public behavior or a realistic counterexample
discovered in Batch 1; coverage percentage alone cannot justify it. If the
paired exact-head gate is below 93% after Batch 2, stop for human
re-adjudication. Do not add a third batch, grow fixtures, lower coverage,
exclude code, add a pragma, or modify CI.

A real public behavior/model disagreement stops E3 and returns bounded
remediation to E1/E2. No E3 production remediation is authorized.

## 6. Exact future allowed paths and verification

After independent R1 ACCEPT and activation, application/test implementation
may modify only:

- tests/execution_core/test_acquisition_stateful.py; and
- work/queue/WO-0152-reset-kernel-e3-generation-conformance.md;
- work/active/WO-0152-reset-kernel-e3-generation-conformance.md;
- work/completed/keep/WO-0152-reset-kernel-e3-generation-conformance.md;
- work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md;
- work/ledger.jsonl;
- pkl/project/goals.md;
- pkl/architecture/architecture-map.md;
- pkl/log.md;
- docs/adr/ARCH-RESET-2026-07-RATIFICATION.md; and
- the individually named REV-0059 R0/R1, activation, implementation,
  evidence, and handoff artifacts recorded by the work order.

No existing test module is an E3 implementation path. The separately completed
removal of the exact 340-line E2 coverage experiment remains retained in
REV-0058 and is not E3 scope.

At coherent checkpoints E3 may run only authorized pure/static checks:
focused E3 and related pure execution-core tests; existing pure execution-core
suite; Ruff; mypy/relevant static checks; import/scope/ledger/PKL/disposition/
hash/diff checks; and, only at normal closeout, the full repository coverage
gate plus unchanged exact-head Python 3.11/3.12 CI. No database-capable
fixture, SQL/DDL, persistent-database, broker, network, credential, runtime,
or CI-workflow work is in scope.

evidence:
  command: "R1 preflight is static only; no E3 test exists or runs before independent ACCEPT and activation."
  result: NOT_RUN
  decisive_output: "The candidate permits exactly the three named setup fixtures and no production capability."

fable_done:
  task: "WO-0152 R1 RED-contract freeze"
  done_when_results:
    - "The exact R1 manifest hashes every candidate input and retained R0 evidence."
    - "The independent R1 result is ACCEPT with P0=0 and P1=0."
    - "The human-authorized activation condition is then recorded; no activation is claimed beforehand."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence: []
  status: UNVERIFIED
