# ADR-023 RED and implementation map

Status: **PLANNING ONLY — NOT A RED CONTRACT OR IMPLEMENTATION AUTHORITY**

## Exact anchor

- Branch: `codex/arch-reset-2026-07-r1`
- Frozen candidate HEAD: `488ce0e7cb954d7b1d19c2bc0127a925e069ea58`
- Proposal: `PROPOSED-ADR-023-bounded-market-occurrence-authority.md`
- Proposal SHA-256: `898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259`
- Final static reviews: three independent `ACCEPT` verdicts; P0=0/P1=0/P2=0
- Human ratification: absent
- Production/test execution or edits during this planning pass: none
- Database, SQL/DDL, network, Alpaca, broker, runtime, merge, deletion, or cleanup activity: none

The current production candidate remains frozen and still contains the rejected aggregate receipt
map. This file does not authorize retaining, editing, or accepting it.

## Mandatory pre-flight sequence

1. Obtain exact human ratification of the proposal hash and its named WO-0148 re-gate.
2. Reconfirm HEAD, tracked/staged status, preserved untracked artifacts, active WO, accepted ADR/PKL,
   and every allowed path before editing.
3. Record only the ratified ADR-023, ratification addendum, active-WO amendment, and matching PKL/log
   reconciliation. Verify hashes and scope before touching tests.
4. Freeze replacement RED controls with production unchanged. Missing public symbols must fail as
   ordinary assertions rather than collection errors.
5. Prove every high-risk RED control fails for the intended absent property, not a shared helper or
   arity accident. Obtain independent exact-commit `ACCEPT` with zero P0/P1.
6. Only then edit production in the dependency order below.

At each boundary, perform a hostile counterexample pass over route/type seals, epoch precedence,
strict coordinates, cursor-before-context ordering, invalidation, recovery, restart, u64 limits,
goal suppression, bounded state/work, hydration, and public-surface exactness.

## Replacement RED contract

Use approximately 15 parametrized groups rather than a large set of duplicated named tests:

1. Exact five-function signatures, exports, provenance, and cross-shaped-call rejection.
2. `MarketStreamGenerationId`, mode, u64, alert, mandate, and immutable value-shape matrix.
3. Constructor-derived identity field sensitivity and caller-supply/overwrite rejection.
4. Independent literal occurrence-preimage/digest known answers and encoding negative controls.
5. Exact 19-part/480-byte cursor known answers, presence pairing, commitment coverage, and hydration.
6. Sequenced replay/stale/conflict/advance and higher-sequence/lower-time behavior.
7. Source-time replay/stale/equal-time conflict/strict-advance behavior.
8. Route and epoch precedence before cursor reservation; context denial after reservation.
9. Initial baseline, projection/market separation, and no-corroboration/no-goal behavior.
10. Invalidation idempotence, exact next epoch, latch retention, and goal suppression.
11. Halt/reopen, valid-baseline latch clearing, favorable-only activation, and sticky restrictions.
12. Retained-cursor versus no-cursor fence cases and terminal u64 exhaustion.
13. Existing formula, flat/late-positive, ratchet, hard-bail, trail, and M1C composition regressions.
14. Constant-cardinality state plus 10-versus-100,000 history/preimage proof.
15. Fail-closed AST/call-graph bounded-work oracle and named mutation fail/restore matrix.

Expected honest RED causes on the frozen candidate are: only three public functions; caller-supplied
occurrence IDs; no generation/mode types; mixed sequence semantics; no invalidation entry point;
epoch-local resets; no exact cursor schema, baseline/exhaustion latches, recovery fence contract, or
bounded-work oracle; and an aggregate receipt map. Legacy tests that remain green are regression
evidence, not proof of the new contract.

## Test migration map

In `tests/execution_core/test_protection.py`:

- Replace `_mandate`, `_reduce`, and `_occurrence` with generation/mode-aware construction plus
  separate projection, market, and invalidation helpers.
- Remove caller IDs and receipt-map expectations. Replace `_assert_recorded_market_inert` with an
  exact cursor-only transition assertion.
- Retain mandate/seal/provenance, venue lineage, economics, flat/late-positive, formula, goal, wait,
  M1C composition, and policy controls after helper migration.
- Replace same-call projection-plus-market tests and the old replay/epoch-reset cluster with the
  split-entry-point, generation-global, recovery, and exhaustion groups above.
- Preserve the independent venue-extractor bounded-map oracle; it is not the rejected market receipt
  map.

In `tests/execution_core/test_protection_stateful.py`, retain the economics machine and rewrite the
market machine into mode-fixed sequenced, source-time, and invalidation/recovery models. Registration
pins must directly exercise the highest-risk rules.

In `tests/execution_core/test_import_boundary.py`, replace the exact-three-function pin with the
exact-five surface; add negative controls for occurrence-shaped projection reduction, advancing or
forked projections in market reduction, variable-cardinality market state, unresolved dynamic
calls, and retained `_PersistentKeyMap` use by protection.

## GREEN dependency order

1. `identity.py`: exact digest/generation identities and fixed-width validators.
2. `protection.py`: mode/alert vocabulary, mandate binding, exact occurrence constructor/preimage.
3. Replace the receipt map and sentinels with the authenticated 19-part bounded cursor; bump and pin
   the state commitment and all authentic constructors/hydration paths.
4. Implement one route/epoch/coordinate classifier with cursor-before-context commitment.
5. Implement the shared baseline-entry rule, invalidation, halt/recovery, latch clearing, and
   terminal exhaustion.
6. Split projection-only and market-only reducers; preserve projection economics and suppress every
   goal while baseline-required or exhausted.
7. Update `__init__.py` exports, retained deterministic/stateful/import tests, and exact static pins.

Do not change `venue.py` or authority semantics unless a new failure proves a directly necessary
in-scope dependency and the WO is amended first. Do not duplicate generation/mode outside the
mandate. Prefer small pure helpers and one classifier over parallel special-case paths.

## Mutation and acceptance gates

Named mutations must cover occurrence/cursor field omission, domain/order/prefix/endianness,
evaluation-time inclusion, mode/generation mismatch, epoch-versus-cursor ordering, `<` versus `<=`,
cursor-after-context, current-epoch omission, invalidation retention, baseline latch clearing,
fence equality, baseline corroboration/goal bypass, max wrap, alert/disposition drift, cross-shaped
entry points, append/traversal/container introduction, and projection advance losing restrictive
latches. Every mutant must fail for its intended reason and restore cleanly.

After GREEN, run the WO-named focused/stateful/scaling, predecessor, R2, execution-core,
full-repository coverage, static/type/import/grammar/scope/governance, immutable-candidate review,
and unchanged exact-head Python 3.11/3.12 CI gates. Record exact commands, counts, hashes, failures,
and restoration evidence at execution time; this planning file claims none of them.

## Explicit M2 deferral

WO-0148 proves only the pure contract. Adapter normalization, source recovery-fence capability,
post-resubscription ordering/provenance, crash injection around cursor-only publication, mailbox
overflow delivery, persistence, startup sequencing, and broker behavior remain M2/runtime gates.
They must not be simulated into an M1 acceptance claim or used to authorize M2 work.

## Compaction checkpoint rule

After ratification, RED freeze/review, each production wave, mutation campaign, candidate freeze,
CI result, interruption, or compaction, refresh the live checkpoint with authority hash, HEAD,
status/diff, allowed paths, current test/mutation evidence, unresolved findings, preserved artifacts,
and the single next gate. Live repository authority always supersedes this planning map.

## Post-ratification critical pre-flight addendum — 2026-08-04

This append-only addendum supersedes the planning-only status above prospectively while preserving
the original pre-ratification record. Exact human ratification is now recorded, and the six-record
documentation wave is frozen at commit `f528b5dd59a415413e010bb6015364d0094512c4`. Production is
still unchanged and barred. A fresh independent pre-build pass found P0=0/P1=4/P2=2 in the first
replacement-RED map; all six classes are accepted and close only through the controls below.

### RED causality and failure-capability protocol

No interface-only production scaffold is permitted before independent RED acceptance. The frozen
evidence SHALL distinguish two layers without overstating either:

1. Production-facing structural/API controls must fail current production at their own explicit
   missing or superseded ADR-023 property, never at collection, a shared fixture accident, or an
   unrelated arity error.
2. Every high-risk semantic oracle that cannot yet reach production because the structural surface
   is absent must have an executable test-local positive/negative control, table mutation, or
   reference-model counterexample that runs before freeze and proves the oracle distinguishes its
   named defect independently of the missing surface. The evidence must say that the corresponding
   production behavior remains unexecuted RED.
3. After GREEN, each material ADR-023 rule must additionally receive a named production mutation
   fail/restore control. A pre-freeze test-local control cannot substitute for that campaign.

### Mandatory matrix refinements

- Replace the abbreviated coordinate cases with one explicit classifier table spanning serving,
  baseline-required, and exhausted state; exact/wrong route; old/current/expected/future epoch;
  lower/equal/greater strict coordinate; and identical/different identity. The exact-current
  replay/conflict rule is evaluated before ordinary epoch admission while baseline-required. Each
  row pins disposition, one-shot alert, cursor delta, latch delta, evidence clearing, and goal
  suppression.
- Split coordinate exhaustion into three independent causes: accepting the strict coordinate at
  u64 maximum, committing epoch maximum, and needing `committed_epoch + 1` from committed maximum.
  Add non-trigger controls proving evaluation time at maximum, and source time at maximum in
  `SEQUENCED` mode when sequence is not maximum, do not exhaust merely because those secondary
  watermarks are maximal. Pin terminal exact-current replay, lower/old stale, every other market
  refusal, repeated-invalidation replay, and projection-only economics with goal suppression.
- Run Python 3.11 grammar parsing and used-AST-API compatibility over every changed RED Python file
  before the immutable freeze. Actual 3.11 execution remains exact-head CI evidence, but the RED
  contract cannot defer grammar compatibility until GREEN.
- Make the constant-cardinality proof recursive and exact-type aware. It must reject
  `_PersistentKeyMap` or any variable-cardinality collection anywhere reachable from protection
  market state, not merely count fields or measure the 480-byte cursor preimage. Reintroducing the
  rejected receipt map is an executable structural mutant.
- Rename recovery "fence" cases in M1 controls to initial/no-cursor and retained-cursor baseline
  coordinate cases. Add a negative public-surface and call-graph pin forbidding caller-authored
  baseline, recovery-fence, subscription, or restart-provenance flags/capabilities. Actual source-
  authoritative fence provenance, ordering, and crash proof remain M2-only.

The replacement RED candidate is not freezable until these refinements, the original fifteen
groups, and their failure-capability evidence all reconcile with zero unresolved pre-build P0/P1.
