# REV-0048 — Independent Review Result

## Pre-registered attack properties

Recorded before implementation inspection from WO-0146, ADR-020, ADR-021, ADR-012, and roadmap M1 item 2:

1. Only first-occurrence canonical broker execution facts and capacity-capped human-attested fills may mutate position quantity; acknowledgements, statuses, releases, closure, and reconciliation remain quantity-neutral.
2. An effect retains independent, immutable ownership for every concrete broker acceptance. One sibling's terminal/released state cannot close or erase another, and an `OPEN` acceptance set remains potentially live.
3. Closure moves only `OPEN → CLOSED → INVALIDATED`; late acceptance after closure preserves proof and permanently blocks release. A no-leg or non-dispatched occurrence must not self-finalize absent the required local cancellation/no-claim proof.
4. Human authority requires exact active `NEEDS_REVIEW` effect/leg/claim binding, full immutable provenance, exact cumulative/capacity/long-only checks, and cannot be forged, replayed with changed payload, or retained through contradictory evidence.
5. Checkpoint hydration/evolution must preserve exact scope, ownership, execution roots, closure/reconciliation/provenance bindings, account registry, and indexed/history-bounded validation. Cross-symbol registry progress may not hide conflict or strand valid truth.
6. Corrections, busts, and later broker evidence must observe exact occurrence/root/lineage/tail mapping and preserve first-occurrence dedupe; partial/changed/unprovable human overlap requires reconciliation without guessed economics.
7. All public/constructible paths, including replacement and import aliases, must pass the one atomic pure transition seam and must not import persistence, broker, runtime, API, UI, or legacy-state modules.

## Review scope and reproduction

- **Reviewed object:** `dfb8ed30ebed788f1158d7f8be49b44d505c355b..ba9e1268e4645ec36f620f14d361f709916aa690`. The latter is the amended exact head; `ba9e1268` is the canonical-Ruff-only successor of `7f4f428`.
- The checkout was `e74d123`, a descendant of `ba9e1268`, with no `app/execution_core` or `tests/execution_core` diff from the reviewed target.
- Fresh reproduction, exact reviewed code:
  - focused fill/import/ownership/recovery/binding/checkpoint/provenance suites: passed (318 cases);
  - `test_fill_position_stateful.py`: 7 passed; `test_venue_stateful.py`: 2 passed;
  - `ruff check app/execution_core tests/execution_core`: passed; `mypy app/execution_core`: 7 source files, no issues;
  - `git diff --check` passed for both base-to-target and formatter-successor ranges.
- The two stateful runs emitted only an environment-local pytest-cache write warning (`.pytest_cache` access denied); their test results were green. No network, broker, credentials, SQL/DDL, database engine, runtime wiring, or external state was used.

## Fresh counterexample probes

| Probe | Exact outcome | Property attacked |
|---|---|---|
| Construction/provenance forgery | Imported `app.execution_core.venue._BOOK_CONSTRUCTION_TOKEN`, then used `dataclasses.replace` to add a new `IngestHumanAttestedFill`, matching `HumanCoverage`, and a leg cumulative quantity of 4 to a valid review-gated book. `VenueRecoveryBook` construction succeeded while its paired execution snapshot still had raw quantity 0. A later public reducer call returned `RECONCILIATION_REQUIRED` without changing quantity, but the constructor had already minted a standalone checkpoint carrying false human authority. | Constructor/evolution paths must preserve exact position/root/provenance binding. |
| Late acceptance after a finalized parent | Closed an operator-reconciled parent, discovered a fresh second leg, then recorded its terminal status. Outcomes were `APPLIED → RECONCILIATION_REQUIRED → APPLIED`; the effect became `NEEDS_REVIEW`, acceptance became `INVALIDATED`, quantity stayed 0, and the two legs ended as closure heads. | Late evidence must not retain operator-final authority or reopen a closed acceptance set. |
| Sibling broker capacity | On one effect with capacity 4 and two legs, admitted independent broker fills of 3 then 2. Both canonical broker facts applied exactly (raw quantity 5) and the second transition latched `OVERFILL_QUARANTINE`; both coverages remained independently owned. | Sibling acceptance must not silently evade effect-wide capacity. Broker-authoritative overfill remains visible, not suppressed. |
| Failure-capability check: effect-wide human capacity | With the same two-leg/capacity-4 setup, a human 3-fill was applied and the next human 2-fill was correctly refused, leaving raw quantity 3. A reversible runtime monkeypatch of `_effect_canonical_total` to `0` made the same second command apply, producing raw quantity 5 and two human coverages. The original function was restored in `finally`. | The new effect-wide human-capacity rail is failure-capable; its guard is necessary rather than inert. |

## Negative-space closure ledger

| Attack path | Choke point and independent result |
|---|---|
| 1. Non-fact quantity mutation | `recovery.py:599-710` admits human deltas only after exact active review/ownership/capacity/long-only checks; `recovery.py:842-1090` and `1175-1430` route broker facts/revisions through `position.py:1262-1304`. Status/release transitions have zero delta. No bypass reproduced. |
| 2. Multi-acceptance loss or overwrite | `venue.py:857-873` keys immutable owners by concrete leg; `venue.py:671-673` requires every owner be exactly active or closed; `venue.py:2486-2549` treats a different owner as conflict. No overwrite reproduced. |
| 3. Premature ambiguity release | `venue.py:1925-1955` constrains `OPEN → CLOSED → INVALIDATED`; `venue.py:2626-2675` requires closed acceptance and every owned leg closure before finality. `symbol_may_execute` is explicitly a later WO-03 concern, so this pure slice was checked only for its retained ambiguity state. |
| 4. Forged/aliased/stale checkpoint authority | Direct-construction bypass reproduced; see P1-1. For a reducer/binder consumer, `venue.py:2071-2103` and `recovery.py:1532-1586` reject the forged root/binding mismatch. |
| 5. Catch-up skips or hides same-symbol truth | `venue.py:2765-2908` requires account identity, prefix monotonicity, same-symbol suffix attribution, and emits an unresolved reconciliation record when that symbol independently advanced. Static paths are bounded against the persistent seen-fact index. No alternate public catch-up route found. |
| 6. Sibling capacity, lineage, tail, and first-observation bypass | Human capacity is at `recovery.py:640-668`; broker and revision latches are at `recovery.py:1027-1035` and `1274-1286`; coverage/provenance and interval checks are at `venue.py:1579-1813`. Fresh sibling and monkeypatch probes above exercised the two capacity modes. |
| 7. Finality survives contradiction or unresolved evidence | Late discovery demotes an operator-final effect at `venue.py:2520-2532`; finalization rejects unresolved integrity/reconciliation/mapping/closure state at `venue.py:2626-2675` and `1966-2025`. The late-acceptance probe reproduced that demotion. |
| 8. No-leg / never-dispatched self-finalization | `venue.py:2698-2706` requires local cancellation and absence of a claim for `NEVER_DISPATCHED`; a later discovered acceptance preserves the proof and permanently invalidates the set at `venue.py:2520-2538`. No premature final state reproduced. |
| 9. Status cumulative mistaken for fills | `venue.py:2573-2585` writes a terminal closure using `_covered_cumulative`, while `recovery.py:2362-2379` derives that only from canonical coverage. Status itself does not call a position reducer. No economic status path found. |
| 10. Public/constructible seam bypass | The main public reducer type/binding gate is `venue.py:2911-2979`, but `venue.py:59, 632-638` exposes its supposed private construction capability to any importer. This is the P1-1 bypass. |

## Findings

| ID | Severity | Finding | Evidence and resolution |
|---|---|---|---|
| P0-1 | P0 | **Every accepted venue transition can validate terminal history in time proportional to all retained closures.** This contradicts the accepted ADR's no-history-length live-transition rule and the packet's explicit bounded/indexed-validation gate. A long-lived account's ordinary state update therefore grows with unrelated past terminal legs, eventually turning the sequencer's safety-bounded transition into a latency/availability hazard. | `app/execution_core/venue.py:613-673` invokes `_validated_closures` for every rebuilt book; `app/execution_core/venue.py:919-966` iterates all `closure_history` entries to rebuild and validate per-leg histories; `app/execution_core/venue.py:1434-1499` scans that same retained history for each closure's source; and `app/execution_core/venue.py:2294-2341` performs another linear duplicate-ID scan before appending. The history is a checkpoint tuple at `app/execution_core/venue.py:621-622`, and accepted transitions rebuild it through `app/execution_core/venue.py:2138-2145`. Replace live retained-history scans with bounded per-owner indexed/current-head proof material (keeping audit history outside the serving checkpoint), then add a failure-capable guard that makes iteration/materialization of terminal history fail on ordinary non-history transitions. |
| P1-1 | P1 | **The purportedly verified-only checkpoint constructor is bypassable by importing its capability token.** Any in-process caller can import `_BOOK_CONSTRUCTION_TOKEN` and pass it to the public dataclass initializer or `dataclasses.replace`, constructing a self-consistent-looking book that records an un-applied human root and nonzero leg coverage. The fresh probe produced exactly that object. Although the next reducer/binder use detects the mismatch, the object itself has already minted false human/provenance state for any checkpoint-only consumer. | `app/execution_core/venue.py:59` stores the capability as an importable module global; `app/execution_core/venue.py:632-638` accepts it as an initializer argument; and `app/execution_core/venue.py:821-837` only establishes structural binding presence, not the covered roots' equality to an execution snapshot. Root equality is deferred to `app/execution_core/venue.py:2087-2103` / `app/execution_core/recovery.py:1556-1586`. Do not use underscore visibility as authority: make checkpoint construction an opaque replay-and-bind operation that validates the paired execution snapshot before yielding a usable object, and add an external-import/`replace` regression test. |

## Deferred / not verified

- Full repository/R2 and external Python 3.11/3.12 exact-head CI were not run here; the packet designates them later closeout gates.
- Persistence, startup, adapters, broker calls, UI/API, SQL/DDL, and runtime wiring were intentionally not inspected or exercised because this review's frozen slice prohibits them.

## Verdict

**BLOCK**
