---
type: Work Order
title: M2-I3.5 owner-state wire and sealed-proof closure
status: ACTIVE
work_order_id: WO-0168h
wave: M2-I3.5-R13-H
model_tier: strong
risk: critical
disposition: []
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

**Author:** Codex orchestrator seat
**Date:** 2026-08-23
**Status:** Active, documentation-only preflight

`[FABLE • FULL • spec-first/TDD • owner-local hydration • no external I/O]`

## Outcome

Freeze and then implement the smallest complete typed current-state representation for
`VenueRecoveryBook`, `ExecutionAuthorityState`, and `AcquisitionControllerState`, plus exact sealed
proof encodings for the existing execution and protection components. The result must let each
owner reconstruct an authentic current object without replaying audit history, reflecting generic
objects, trusting a digest without bytes, or creating a second reducer/state engine.

R13-H does not create the public checkpoint envelope, payload record/store/load API, or restart
head eligibility. Those remain R13-C after this work receives terminal `REV-0077` acceptance.

## Root design decision

Accepted SQL rows corroborate application/profile/scope/currentness and immutable direct facts but
do not contain every semantic member of the three opaque owners. The future complete checkpoint
payload therefore owns explicit typed current/active/unresolved state rows. Repository-issued
proofs bind those bytes to exact selected direct rows, counts, predicates, application generation,
profiles, currentness head, and checkpoint version. Owner-local constructors decode the typed rows,
rebuild all derived indexes and commitments, and reject any missing, extra, stale, cross-owner, or
noncanonical member.

This is not a new table family and not a history replay. Audit/order ledgers remain omitted; direct
repository lookup remains authoritative for targeted historical inputs and immutable facts.

## Preflight deliverable

Create
`work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`
as one indivisible contract containing:

1. all 57 venue, 20 authority, and 13 acquisition fields classified as payload scalar, bounded
   semantic row, derived index, or omitted history;
2. exact literal tags, fixed-array lengths, member order, null representation, enum spellings,
   digest/byte forms, and count-bearing collection wrappers;
3. canonical identity bytes, family order, strict within-family order, uniqueness, completeness
   predicates, and explicit finite limits;
4. exact venue current rows for effects, claims, owners/attempts, correlations, closures,
   coverage, reconciliations, execution bindings, bootstrap targets, and protection cursors;
5. exact authority rows for effects/claims, manual flatten state, acquisition slots, budget,
   emergency grant, and the sealed venue reference;
6. exact acquisition controller/mandate, LIVE plus optional targeted-retired generation, active
   stream route, and bounded lineage rows;
7. complete fixed-array encodings for `_M2ExecutionObservationProof` and
   `_M2ProtectionAuthorityProof`;
8. owner constructor equivalence, derived-index rebuild order, full authenticity checks, and
   commitment domains;
9. genesis, empty, optional, unresolved predecessor-generation, and targeted late-fact behavior;
10. failure-capable tests for missing/extra/reordered/duplicate/substituted/stale/header-only rows,
    forged proofs, commitment-only substitution, history inclusion, and unbounded selection.

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

- RED must show the named owner state/proof types or constructors are absent or refuse the frozen
  canonical rows.
- GREEN must prove canonical round-trip through owner-owned project/decode constructors and
  equality with authentic reducer-produced objects for genesis and nontrivial current state.
- Derived indexes must be omitted from bytes, rebuilt in fixed order, and independently mutated.
- Every collection must be count-bound, strictly ordered, duplicate-free, and semantically
  complete for the declared current/active/unresolved predicate.
- Execution/protection proof members must be re-derived and byte-round-tripped; detached or
  caller-forged proof tuples fail.
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
