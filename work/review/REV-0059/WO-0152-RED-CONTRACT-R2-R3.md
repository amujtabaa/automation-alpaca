# WO-0152 E3 RED contract R2-R3 - static-exception consistency correction

Status: REPLACEMENT CANDIDATE - DRAFT ONLY - NOT ACTIVE  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059  
Controlling composite: `WO-0152-RED-CONTRACT-R1.md`,
`WO-0152-RED-CONTRACT-R1-R1.md`, `WO-0152-RED-CONTRACT-R2.md`,
`WO-0152-RED-CONTRACT-R2-R1.md`, `WO-0152-RED-CONTRACT-R2-R2.md`,
and this R2-R3

## 1. Retained R2-R2 candidate and replacement rule

The R2-R2 candidate remains retained unaccepted evidence. It was stopped
before an independent verdict because its new broad static prohibition
contradicted the inherited exact fixture exceptions, and it treated the public
keyed `SeenFactIndex.observation_at` method as a property. `result-r2-r2.md`
remains absent.

R2-R3 replaces only those internal exception-table contradictions and the
current R2-R2 activation references. Every R2/R2-R1 semantic constraint
remains verbatim controlling: the existing environment fixture, fixed six-step
public same-account OTHER-symbol lifecycle, pre-install guards, one copied
literal venue installation, post-install target-bootstrap assertion,
terminal-fixture limits, retained evidence, and every safety exclusion.

The sole activation condition is all of the following:

1. accepted WO-0151 E2 implementation plus retained exact-head #741
   functional/static success with its 91.34% coverage-only failure;
2. this exact R2-R3 composite frozen in an immutable manifest; and
3. a fresh independent review of that exact manifest returning `ACCEPT` with
   P0=0/P1=0.

No R0, R1, R1 remediation 01, R2, R2-R1, or R2-R2 result can substitute for
item 3. WO-0152 remains DRAFT and `NOT_GRANTED` until this exact R2-R3 rule is
satisfied.

## 2. Coherent exact static exception table

The inherited R2 table and lexical limits remain controlling. The E3 source
must reject private access, mutation, patching, dynamic lookup, and test
imports except only for the exact operations in this complete table. No
broader alias, wrapper, helper, loop, dynamic target, or caller-supplied
operation is permitted to exercise a table exception.

| Helper | Exact allowed operation | Exact limit |
| --- | --- | --- |
| `_serving_environment_predecessor_fixture` | `copy.copy`; `object.__setattr__` | exactly two copies and exactly seven literal setters: six fixed pre-genesis environment fields plus one copied-authority `venue` write from `final_transition.book` |
| `_approved_acquisition_mandates_fixture` | `app.execution_core.acquisition._mint_dual_mandate_binding` | exactly one lexical AST call site, fixed immutable A/B/C configuration before genesis only |
| `_certified_terminal_parent_fixture` | `AcceptanceProof`, `AcceptanceProofKind`, `CloseAcceptanceSet`, `app.execution_core.venue._apply_venue_input`, one temporary `patch.object` of `_external_acceptance_closure_is_certified`, `copy.copy`, `object.__setattr__` | one lexical private reducer site, one literal private hook target, one fixed digest, one copied-authority literal `venue` write, and its locally owned APPLIED-only public suffix |
| `_build_rooted_parent_public_suffix` | no private production access | fixed straight-line public suffix only; no supplied transition/book/execution parameter or dynamic command |
| `_forbid_live_acquisition_history_materialization` | `unittest.mock.patch.object` only | one `ExitStack`-scoped series of exactly sixteen explicit public class-member patches defined in section 3; no instance target, private target, alias, loop, dynamic target/name, returned/started patcher, or production-object mutation |

Outside this table, the E3 module must reject `patch`, `patch.object`,
`monkeypatch`, `setattr`, `object.__setattr__`, `copy.copy`, dynamic attribute
lookup, private production access, and imports from `tests.*`. The source
control must prove each lexical exception remains inside its named helper and
within its exact count/shape limit.

## 3. Exact public boundedness tripwire

`_forbid_live_acquisition_history_materialization` is the sole boundedness
patch helper. It exists only in the future
`tests/execution_core/test_acquisition_stateful.py`. After deterministic
long-state construction but before live decisions, it may patch exactly these
sixteen public `(class, member)` pairs:

| Class | Member | Replacement shape |
| --- | --- | --- |
| `VenueRecoveryBook` | `effects` | raising property |
| `VenueRecoveryBook` | `claims` | raising property |
| `VenueRecoveryBook` | `owners` | raising property |
| `VenueRecoveryBook` | `active_attempts` | raising property |
| `VenueRecoveryBook` | `closure_heads` | raising property |
| `VenueRecoveryBook` | `execution_bindings` | raising property |
| `VenueRecoveryBook` | `input_records` | raising property |
| `VenueRecoveryBook` | `closure_history` | raising property |
| `VenueRecoveryBook` | `human_coverages` | raising property |
| `VenueRecoveryBook` | `broker_coverages` | raising property |
| `VenueRecoveryBook` | `reconciliations` | raising property |
| `VenueRecoveryBook` | `execution_reconciliations` | raising property |
| `VenueRecoveryBook` | `effect` | raising method `(self, effect_id)` |
| `SeenFactIndex` | `entries` | raising property |
| `SeenFactIndex` | `observation_at` | raising method `(self, index)` |
| `RootHeadIndex` | `entries` | raising property |

Each replacement must raise `AssertionError` and restore on both normal and
exceptional exit. The helper must run while the same target scope exercises
and asserts expected public results for:

1. `refresh_acquisition_context`;
2. `project_acquisition_admission`; and
3. `reduce_acquisition_controller` on an authenticated current or
   retired-generation canonical transition.

Setup, long-history construction, and postcondition inspection remain outside
the context. The test must separately prove direct earliest/current routing
after the context exits through the unpatched bounded readers listed below.

The helper must not patch `VenueRecoveryBook.acquisition_correlation`,
`execution_binding`, `owner`, `active_attempt`, or `closure_head`,
`GenerationRegistry.record`, `AcquisitionLineageIndex.route_request`,
`route_effect`, `route_owner`, `route_root`, or `route_fact`,
`SeenFactIndex.get`, or `RootHeadIndex.get`. It must not patch private
`_current_effect`; public `VenueRecoveryBook.effect` is intentionally trapped
because it materializes retained per-effect contradiction history.

The source control must require the exact sixteen-pair set and shapes with no
missing, extra, aliased, dynamic, direct-reader, or private target. Named
test-local negative source specimens must independently demonstrate rejection
for a changed allowed pair, an out-of-scope target, a private target, a dynamic
target/name, a missing required target, and a trap context placed around setup
or postcondition inspection instead of the live decisions. External
scope/diff/hash gates, not this source control, remain responsible for any
production-file change.

## 4. Acceptance and stop rule

The independent reviewer must re-derive this R2-R3 composite against the user
authorization, retained R0/R1/R1-R1/R2/R2-R1/R2-R2 material, accepted ADRs,
current work order, ratification/provenance, and frozen source. It must verify
that `result-r2.md` and `result-r2-r2.md` remain absent, the future E3 test
file remains absent, and no source/test implementation occurred.

Only exact independent `ACCEPT` with P0=0/P1=0 permits the already authorized
test-only WO-0152 activation and implementation. Any P0/P1 keeps WO-0152
DRAFT and requires the smallest root correction or a new human boundary.
R2-R3 does not satisfy, alter, or waive paired E2/E3 93% exact-head closeout.
