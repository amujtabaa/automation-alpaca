---
type: Work Order
title: M2-I3.5 owner-state wire and sealed-proof closure
status: SUPERSEDED
work_order_id: WO-0168h
wave: M2-I3.5-R13-H
model_tier: strong
risk: critical
disposition: [SUPERSEDED, RESULT_SUMMARY_KEPT, ARCHIVED]
owner: Codex orchestrator and implementation seat; fresh-context reviewers required
created: 2026-08-23
predecessor: WO-0168a closeout 58f23ff9ea6d446379f7339075e1203c42a33e96
branch: codex/m2-i3-5-owner-state-wire-r1
preflight_review_id: REV-0076
implementation_review_id: REV-0077
execution_authority: Ameen Mujtabaa's serial-M2 authorization permits ordinary reversible work through M2 closeout and M3 preparation. R13-H begins documentation-only. No owner-state source or test change may start until REV-0076 accepts the exact frozen row/proof contract with P0=0/P1=0. No changed-DDL installation, SQLite-bearing test, configured/in-memory database, runtime composition, credentials, network, broker calls, orders, promotion, or merge to master is authorized.
allowed_paths:
  - app/execution_core/venue.py
  - app/execution_core/authority.py
  - app/execution_core/acquisition.py
  - app/execution_core/position.py
  - app/execution_core/protection.py
  - tests/execution_core/test_m2_owner_state_wire.py
  - tests/execution_core/test_venue*.py
  - tests/execution_core/test_authority*.py
  - tests/execution_core/test_acquisition*.py
  - tests/execution_core/test_position*.py
  - tests/execution_core/test_fill_position*.py
  - tests/execution_core/test_protection*.py
  - work/active/WO-0168h-m2-i3-5-owner-state-wire-closure.md
  - work/completed/keep/WO-0168h-m2-i3-5-owner-state-wire-closure.md
  - work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md
  - work/review/REV-0076/**
  - work/review/REV-0077/**
  - work/ledger.jsonl
forbidden_paths:
  - app/execution_core/persistence/**
  - app/execution_core/runtime.py
---

# Work Order: WO-0168h — M2 owner-state wire closure

> **Superseded 2026-08-23.** Five documentation review rounds disproved the premise that a
> complete bounded owner-state snapshot can be implemented independently of repository provenance
> and serving composition. REV-0076 R5 found repository-only selection facts, serving authority
> mintable from proof bytes, and proposed venue-wire behavior changes. No R13-H source, test, DDL,
> or SQLite work occurred. WO-0168c succeeds this work with one indivisible checkpoint boundary.

**Author:** Codex orchestrator seat
**Date:** 2026-08-23
**Status:** Superseded after failed documentation-only preflight

`[FABLE • FULL • spec-first/TDD • owner-local hydration • no external I/O]`

## Outcome

Freeze and then implement the smallest complete typed non-serving snapshot representation produced
and decoded by the venue, authority, and acquisition owners, plus exact byte round-trips for the
existing execution and protection proofs. R13-H must not construct a serving reducer or claim that
omitted history can authorize future operations.

R13-H does not create the public checkpoint envelope, payload record/store/load API, or restart
head eligibility. Those remain R13-C after this work receives terminal `REV-0077` acceptance.

## Root design decision

Accepted SQL rows do not contain every semantic member of the three opaque owners. The future
checkpoint therefore needs explicit typed current/active/unresolved snapshot rows. R13-H only
proves owner-local pure projection, canonical bytes, validation, and non-serving type separation.
Repository corroboration, omitted-history operation authority, behavioral-commitment activation,
and serving composition are a distinct R13-C contract and review problem.

The snapshot wire is not a history replay. Audit/order ledgers remain omitted. R13-H creates no
table, repository operation, operation fact, serving adapter, or reducer seam.

## Preflight deliverable

Create
`work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`
as one indivisible contract containing:

1. all 57 venue, 20 authority, and 13 acquisition fields classified as payload scalar, bounded
   semantic row, derived index, or omitted history;
2. exact literal tags, fixed-array lengths, member order, null representation, enum spellings,
   digest/byte forms, and count-bearing collection wrappers;
3. canonical typed ordering, strict within-collection order, uniqueness, counts, and explicit
   finite limits;
4. exact venue current rows for effects, claims, owners/attempts, correlations, closures,
   coverage, reconciliations, execution bindings, bootstrap targets, and protection cursors;
5. exact authority rows for effects/claims, manual flatten state, acquisition slots, budget,
   emergency grant, and the sealed venue reference;
6. exact acquisition controller/mandate, standing LIVE and unresolved generation/stream rows, and
   bounded active lineage, all as non-serving snapshot state;
7. complete fixed-array encodings for `_M2ExecutionObservationProof` and
   `_M2ProtectionAuthorityProof`;
8. owner-local snapshot projection/decode, fail-closed type separation, full snapshot validation,
   and commitment domains;
9. genesis, empty, optional, unresolved predecessor-generation, and targeted late-fact behavior;
10. failure-capable tests for missing/extra/reordered/duplicate/substituted rows, forged snapshots,
    commitment-only substitution, history inclusion, oversize refusal, and serving-type misuse.

The contract must resolve every identified source gap. `TBD`, generic records, `repr`, pickle,
reflection, caller-shaped tuples, or “implementation-defined” ordering are preflight failures.

## Held implementation surface

After exact REV-0076 `ACCEPT` with P0=0/P1=0, ordinary reversible source/TDD work may use only:

- `app/execution_core/venue.py`
- `app/execution_core/authority.py`
- `app/execution_core/acquisition.py`
- `app/execution_core/position.py`
- `app/execution_core/protection.py`
- `tests/execution_core/test_m2_owner_state_wire.py`
- directly necessary owner-specific existing test files when a failure-capable contract cannot be
  isolated in the new file;
- this work order, the frozen contract, `work/review/REV-0076/**`,
  `work/review/REV-0077/**`, and append-only `work/ledger.jsonl`.

`persistence/checkpoint_codec.py`, records/repository/schema/DDL, unit-of-work, runtime composition,
and R13-C remain out of scope.

## TDD and proof obligations

- RED must show the named owner snapshot types or constructors are absent or refuse the frozen
  canonical rows.
- GREEN must prove canonical round-trip through owner-owned project/decode constructors from
  authentic reducer-produced objects for genesis and nontrivial current state.
- Derived indexes and omitted history must be absent from bytes; snapshot types expose no serving
  reducer capability.
- Every collection must be count-bound, strictly ordered, duplicate-free, and semantically
  complete for the declared current/active/unresolved predicate.
- Execution/protection proof members must be re-derived and byte-round-tripped; detached or
  caller-forged proof tuples fail.
- Passing any snapshot where an existing serving owner is required must fail by exact type.
- Imports stay inert. No SQLite-bearing test belongs to R13-H.

## Required review gates

1. `REV-0076`: fresh documentation review of exact contract candidate; source remains held until
   P0=0/P1=0.
2. `REV-0077`: fresh implementation review with failure-capable mutation evidence; R13-H closes
   only at P0=0/P1=0.
3. R13-C receives fresh work-order/review identities after R13-H closeout.

## Safety and exclusions

- No changed DDL execution or SQLite-bearing test.
- No configured/existing or in-memory database.
- No runtime composition, credentials, network, broker calls, orders, or trading-mode changes.
- No public checkpoint payload record/store/load, restart authority, unit of work, M2-I4+, M3
  implementation, promotion, PR, or merge to `master`.
- No second engine, whole-history snapshot, audit replay, generic serializer, ORM, or alternate
  state store.

## Completion condition

R13-H completes only after the exact frozen contract is accepted, source/tests implement that
contract, fresh pure evidence and mutations pass, `REV-0077` returns P0=0/P1=0, governance is
clean, and the accepted branch is published. Any inability to define a complete bounded row is a
contract finding, not permission to serialize the corresponding private map wholesale.

## Preflight remediation record — 2026-08-23

Fresh REV-0076 review exposed a future-checkpoint digest cycle, incomplete collection and
predicate cardinalities, caller-forgeable authority dedupe evidence, a history-dependent
acquisition transition commitment, and an ambiguous targeted-retired stream route. The contract
was corrected at the root: the new kernel head is now outer-only and payload-first; every variable
collection has one literal wrapper; one committed predicate-coordinate set covers positive and
negative cardinality; authority facts are opaque and request/snapshot-bound; acquisition behavior
uses one history-independent standing commitment; and retired generation/stream/lineage evidence
is sealed operation proof and enters standing state only while unresolved. R3 review then proved
the accepted schema lacks the mutable generation-state row needed to reload resolved-history
targets without replay. The R13-H contract now defines that pure row and holds its future R13-C
persistence/DDL behind Ameen's exact gate. These clarifications do not release the source hold or
authorize SQLite/DDL work.

R4 review then demonstrated that combining snapshot reconstruction with future-operation authority
was itself the recurring complexity source: exact command grammars, historical replay membership,
and repository freshness do not belong inside checkpoint state bytes. R5 therefore narrows R13-H
to owner-local non-serving snapshots and moves all repository observation, operation capability,
behavioral commitment activation, mutable generation state, FACT membership, and DDL to a fresh
R13-C contract/review. This is a fail-closed scope split, not a default-empty or bypass path.

## Terminal disposition — 2026-08-23

`SUPERSEDED`, `RESULT_SUMMARY_KEPT`, and `ARCHIVED`. REV-0076 never accepted the contract and the
source hold was never released. The durable correction carried into WO-0168c is that inert bytes
may preserve integrity, but repository provenance and serving-proof issuance must be reviewed and
implemented with the complete checkpoint boundary, not reconstructed by a standalone owner-local
decoder.
