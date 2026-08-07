# WO-0152 E3 RED contract R2-R2 - current-gate and boundedness-tripwire correction

Status: REPLACEMENT CANDIDATE - DRAFT ONLY - NOT ACTIVE  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059  
Controlling composite: `WO-0152-RED-CONTRACT-R1.md`,
`WO-0152-RED-CONTRACT-R1-R1.md`, `WO-0152-RED-CONTRACT-R2.md`,
`WO-0152-RED-CONTRACT-R2-R1.md`, and this R2-R2

## 1. Retained R2/R2-R1 evidence and replacement rule

The first R2 candidate is retained unaccepted evidence: it was stopped before
an independent verdict because the work order then named a superseded R1
activation condition. `result-r2.md` remains absent. R2-R1 corrected that
work-order condition but independently returned `ACCEPT-WITH-CHANGES`,
P0=0/P1=1/P2=0, result SHA-256
`098b2a3791505064406cd1087a654dc89a3a96d9b42906d7ec491cb4bca5bae9`.
Its P1 was a stale current R2 predicate in two PKL clauses.

R2-R2 replaces only that current activation predicate and the omitted exact
test-only boundedness tripwire. Every R2/R2-R1 semantic constraint remains
verbatim controlling: the one existing environment fixture, fixed six-step
public same-account OTHER-symbol lifecycle, pre-install guards, one copied
literal venue installation, post-install public target-bootstrap assertion,
terminal-fixture limits, all retained negative evidence, and every safety
exclusion.

The sole activation condition is all of the following:

1. accepted WO-0151 E2 implementation plus retained exact-head #741
   functional/static success with its 91.34% coverage-only failure;
2. this exact R2-R2 composite frozen in an immutable manifest; and
3. a fresh independent review of that exact manifest returning `ACCEPT` with
   P0=0/P1=0.

No R0, R1, R1 remediation 01, R2, or R2-R1 result can substitute for item 3.
WO-0152 remains DRAFT and `NOT_GRANTED` until this exact R2-R2 rule is
satisfied.

## 2. Exact public boundedness tripwire

`_forbid_live_acquisition_history_materialization` is the sole new test-only
patch helper. It exists only in the future
`tests/execution_core/test_acquisition_stateful.py` and only for the named
long-sequence boundedness control. After a deterministic long state is fully
constructed, but before its live decisions begin, it may create one
`ExitStack`-scoped series of explicit `unittest.mock.patch.object` calls against
exactly these sixteen public `(class, member)` pairs:

| Class | Member |
| --- | --- |
| `VenueRecoveryBook` | `effects` |
| `VenueRecoveryBook` | `claims` |
| `VenueRecoveryBook` | `owners` |
| `VenueRecoveryBook` | `active_attempts` |
| `VenueRecoveryBook` | `closure_heads` |
| `VenueRecoveryBook` | `execution_bindings` |
| `VenueRecoveryBook` | `input_records` |
| `VenueRecoveryBook` | `closure_history` |
| `VenueRecoveryBook` | `human_coverages` |
| `VenueRecoveryBook` | `broker_coverages` |
| `VenueRecoveryBook` | `reconciliations` |
| `VenueRecoveryBook` | `execution_reconciliations` |
| `VenueRecoveryBook` | `effect` |
| `SeenFactIndex` | `entries` |
| `SeenFactIndex` | `observation_at` |
| `RootHeadIndex` | `entries` |

Each listed property receives a test-local raising property replacement;
`VenueRecoveryBook.effect` receives a method-shaped raising replacement.
Every replacement raises `AssertionError` and restores on both normal and
exceptional context exit.

The helper must run while the same target scope exercises all of the following
public live decisions and asserts their expected public result before leaving
the trap:

1. `refresh_acquisition_context`;
2. `project_acquisition_admission`; and
3. `reduce_acquisition_controller` on an authenticated current or
   retired-generation canonical transition.

Setup, long-history construction, and postcondition inspection remain outside
the context. The test must separately prove direct earliest/current routing
through unpatched bounded readers after the context exits.

The helper must not patch `VenueRecoveryBook.acquisition_correlation`,
`execution_binding`, `owner`, `active_attempt`, or `closure_head`,
`GenerationRegistry.record`, `AcquisitionLineageIndex.route_request`,
`route_effect`, `route_owner`, `route_root`, or `route_fact`,
`SeenFactIndex.get`, or `RootHeadIndex.get`. Those are bounded direct readers.
It must not patch private `_current_effect` or any private member.

## 3. Exact static limits and failure controls

The E3 source control must prove all of the following:

1. Outside `_certified_terminal_parent_fixture`'s already approved one private
   certification-hook patch and this helper, the module rejects `patch`,
   `patch.object`, `monkeypatch`, `setattr`, `object.__setattr__`, dynamic
   attribute lookup, private production access, and imports from `tests.*`.
2. The boundedness helper contains one `ExitStack`-scoped series of explicit
   calls whose exact `(class, member)` set equals the sixteen rows above. It
   may not loop over, alias, dynamically derive, return, or `start()` patchers;
   patch an instance; persistently assign a module/class member; or mutate a
   production object.
3. Every trap replacement raises. Source controls must reject a missing,
   extra, aliased, dynamic, direct-reader, or private target, and must reject a
   context moved around setup or postcondition inspection rather than the live
   decisions.
4. Named test-local negative source specimens must independently demonstrate
   rejection for a changed allowed pair, an out-of-scope target, a private
   target, a dynamic target/name, and a misplaced trap context. A
   failure-capable control removing one required target from a local specimen
   must also fail.
5. External scope/diff/hash gates, not the test-local source control, remain
   responsible for detecting any production-file change.

This is a public test trap, not a production seam or authority mechanism. It
does not permit an opaque-value constructor, private reducer, history scan,
caller-shaped authority, post-setup production-object mutation, database,
runtime, broker, credential, or network operation.

## 4. Acceptance and stop rule

The independent reviewer must re-derive this complete R2-R2 composite against
the user authorization, retained R0/R1/R1-R1/R2/R2-R1 material, accepted ADRs,
current work order, ratification/provenance, and frozen source. It must verify
the first R2 candidate has no result, R2-R1 remains retained
`ACCEPT-WITH-CHANGES` evidence, the future E3 test file remains absent, and no
source/test implementation occurred.

Only exact independent `ACCEPT` with P0=0/P1=0 permits the already authorized
test-only WO-0152 activation and implementation. Any P0/P1 keeps WO-0152
DRAFT and requires the smallest root correction or a new human boundary.
R2-R2 does not satisfy, alter, or waive paired E2/E3 93% exact-head closeout.
