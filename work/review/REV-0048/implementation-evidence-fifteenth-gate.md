---
type: Implementation Evidence Transcript
work_order_id: WO-0146
review_id: REV-0048
gate: fifteenth
evidence_owner: Codex implementation seat
base_sha: dfb8ed30ebed788f1158d7f8be49b44d505c355b
invalidated_checkpoint: 1de7173bd01dfa35a39da4c8683eaff338c5f2e0
status: READY_FOR_INDEPENDENT_REVIEW
date: 2026-08-02
---

# WO-0146 fifteenth-gate implementation evidence transcript

This is an implementation-seat evidence record, not a reviewer verdict. It preserves exact
commands, outcomes, hashes, mutation results, and invalidated artifact identities needed for
independent review. Reviewer-owned `result.md` and `result-addendum-01.md` remain unchanged. The
containing Git commit and this file's detached SHA-256 are recorded by the active work order and
must be rechecked by the independent reviewer.

## Evidence classes

- **IMPLEMENTATION-SEAT EXECUTED:** run or reproduced by the implementation seat. It requires
  independent review before acceptance.
- **INDEPENDENTLY REPRODUCED:** reproduced by a separate read-only/review seat. This does not imply
  acceptance of a later changed object.
- **EXTERNALLY PENDING:** requires exact-head GitHub or other external evidence not yet available.
- **INVALIDATED:** accurate for the named object, but inadmissible for the final fifteenth-gate
  object.

Causal statements about absence of credentials, broker/network activity, persistent database
effects, runtime wiring, and reliance on the prohibited R1 DDL result are implementation-seat
attestations unless an independent artifact expressly says otherwise.

## Object and evidence lineage

| Object | Status | Meaning |
|---|---|---|
| `dfb8ed30ebed788f1158d7f8be49b44d505c355b` | Base | Accepted WO-0145 closeout and WO-0146 diff base. |
| `bd5943768ab41592c6445892248ade86f1a79bbf` | Superseded checkpoint | Fourteenth-gate retained-state production correction; production object exercised by mutation groups M1-M8. |
| `1de7173bd01dfa35a39da4c8683eaff338c5f2e0` | **INVALIDATED** | Test-only coverage remediation over unchanged `bd594376` production. `_15` passed 93%, but the later public-command production fix invalidated it for acceptance. |
| Containing commit | Fifteenth-gate freeze | Must contain the exact public-command fix, its pin, this transcript, and no unexplained source change. |
| `result-addendum-01.md` SHA-256 `f7cff72992ab831b8be2839d3741c6a02cd1ff9a5a32b0ae32f6124a097a012a` | Preserved independent BLOCK | Result against `9ce0f442db4b9a261fbed4003da377bfb497ec9e`; not acceptance evidence for the current object. |

A separate read-only evidence-integrity pass found no numerical, hash, scope, artifact-identity, or
restoration contradiction in the recorded fourteenth-gate evidence. It identified the missing
durable command provenance now recorded here and a date-span error corrected in the work order.
That pass was an evidence audit, not the final independent implementation review.

## Fifteenth-gate public-command finding and fix

**INDEPENDENTLY REPRODUCED FINDING; FINAL REVIEW STILL PENDING:** review of `1de7173` found that
public `apply_venue_recovery_input` read `item.input_id` and dispatched through `isinstance` before
proving that `item` was one exact admitted command type. A `RequestedEffect` subclass with an armed
getter therefore executed subclass behavior before rejection. No unsafe state acceptance or
quantity change was reproduced, but this was a P1 exact-boundary/read-order defect.

### Failure-first reproduction

**IMPLEMENTATION-SEAT EXECUTED**

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp_wo0146_command_boundary_red_16 tests/execution_core/test_venue_checkpoint_hardening.py::test_public_reducer_rejects_command_subclasses_before_property_access
```

- Exit: `1`
- Result: `AssertionError: input_id read before exact command type check`
- Trace location during this run: `venue.py:7293`
- Interpretation: the new pin was failure-capable before the fix.

The bounded correction centralizes the exact admitted-command set in
`_require_exact_venue_recovery_input` and calls that guard immediately after exact book/execution
validation, before any item property, replay, equality, commitment, dispatch, or economic access.

### Focused green result

**IMPLEMENTATION-SEAT EXECUTED**

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp_wo0146_command_boundary_green_16b tests/execution_core/test_venue_checkpoint_hardening.py::test_public_reducer_rejects_command_subclasses_before_property_access tests/execution_core/test_venue_checkpoint_hardening.py::test_venue_canonical_helpers_cover_every_admitted_shape_and_reject_others
```

- Exit: `0`
- Result: two passing tests.

### Public-command guard mutant

**IMPLEMENTATION-SEAT EXECUTED**

The mutant removed only the entrypoint call to `_require_exact_venue_recovery_input(item)`, leaving
the identity helper's later guard intact.

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp_wo0146_command_boundary_mutant_16 tests/execution_core/test_venue_checkpoint_hardening.py::test_public_reducer_rejects_command_subclasses_before_property_access
```

- Exit: `1`
- Result: the same armed-getter `AssertionError` at `venue.py:7297`.
- Interpretation: the pin specifically requires the early public-boundary guard; the later identity
  guard is insufficient.

After restoring the guard:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp_wo0146_command_boundary_restore_16 tests/execution_core/test_venue_checkpoint_hardening.py::test_public_reducer_rejects_command_subclasses_before_property_access
```

- Exit: `0`
- Result: one passing test.

## Current pure and static gates

All commands in this section are **IMPLEMENTATION-SEAT EXECUTED** against the restored
fifteenth-gate source.

### Pure execution-core suite

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp_wo0146_execution_core_16 tests/execution_core
```

- Exit: `0`
- Result: 521 collected, 521 passed.
- Duration: 130.0 seconds.

### Ruff, mypy, imports, and diff

```powershell
.\.venv\Scripts\python.exe -m ruff check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m ruff format --check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app/execution_core/__init__.py app/execution_core/identity.py app/execution_core/values.py app/execution_core/fills.py app/execution_core/position.py app/execution_core/venue.py app/execution_core/recovery.py
.\.venv\Scripts\lint-imports.exe
git diff --check
```

- Exit: `0` for every command.
- Ruff: all checks passed; all 17 inspected files format-clean.
- Mypy: no issues in seven execution-core source files.
- Import Linter: six contracts kept, zero broken.
- Final exact-scope reconciliation is recorded after the containing commit is frozen.

## R2 conformance

**IMPLEMENTATION-SEAT EXECUTED**

```powershell
$env:BROKER_ADAPTER='mock'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp_wo0146_r2_16 tests/r2_conformance_oracle.py
```

- Exit: `0`
- Result: 61 passed.
- Existing database-bearing cases used only their previously authorized disposable test-only SQLite
  fixtures.

## Live mutation ledger

For M1-M8, each listed invocation expands exactly to:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp <BaseTemp> <Nodes>
```

Every killed mutant was restored before the next mutation. A passing survivor is classified as safe
only where an independent remaining guard still enforced the property.

| ID | Mutation and focused nodes | Base-temp / exit / result |
|---|---|---|
| M1 | Narrow removal of leg-local unresolved reconciliation, then complete removal of the unresolved-release policy. Node: `test_venue_recovery.py::test_unresolved_broker_contradiction_blocks_release_and_parent_finalization`. | Narrow `_m1`: exit `0`, safe survivor because execution/scope guards still blocked release. Complete `_m1b`: exit `1`, observed `APPLIED` instead of `RECONCILIATION_REQUIRED`; restore exit `0`. |
| M2 | Remove ordered effect review alone, then both effect and leg review gates. Nodes: checkpoint-hardening `::test_rebuild_rejects_first_human_source_before_effect_needs_review` and `::test_rebuild_rejects_first_human_source_before_leg_needs_review`. | Effect-only `_m2`: exit `1`, `F.`; restore `0`. Combined `_m2b`: exit `1`, `FF`; restore `0`. |
| M3 | Remove provenance checks individually, then coordinate missing-source, direct-source, and backward-alias removals. Node: provenance-hardening `::test_checkpoint_rejects_semantic_alias_retargeted_as_direct_provenance`. | Partial `_m3`/`_m3b`: exit `0`, safe survivors. Coordinated `_m3c`: exit `1`, `DID NOT RAISE`; restore `0`. |
| M4 | Remove effect-wide sibling overfill latch. Node: recovery `::test_wo0146_red_sibling_broker_fills_latch_effect_wide_overfill`. | `_m4`: exit `1`, missing `OVERFILL_QUARANTINE`; restore `0`. |
| M5 | Permit operator-final state with unresolved execution-integrity bits. Node: provenance-hardening `::test_constructor_rejects_operator_state_with_unresolved_binding_bits`. | `_m5`: exit `1`; both rows reached the later stale-binding failure, proving the intended earlier guard absent. Restore `0`. |
| M6 | Weaken common exact fill-component guard to `isinstance`. Nodes: four delayed quantity/scope/identity/price tests in `test_fill_position.py`. | `_m6`: exit `1`, `FF.F`; identity remained protected by a separate exact guard. Restore `0`. |
| M7 | Remove pre-read exact `VenueExecutionBinding` guard. Node: checkpoint-hardening `::test_hydration_rejects_binding_subclasses_before_property_access`. | `_m7`: exit `1`, armed getter reached; restore `0`. |
| M8 | Remove pre-index exact `VenueInputRecord` shape guard. Node: checkpoint-hardening `::test_hydration_validates_input_identity_before_hashing_or_value_access`. | `_m8`: exit `1`, armed getter reached; restore `0`. |
| M9 | Remove four price-scalar, four `_SnapshotBinding` metadata, and retained `PositionState` binding guards. Nodes: the three new test groups in `test_fill_position.py`. | `.pytest_tmp_wo0146_coverage_remediation_14_mutant`: exit `1`, `FFFFFFFFF`; restored path `_restored`: exit `0`, nine passes. |
| M10 | Remove only the early public-command exact-type guard. Node: checkpoint-hardening `::test_public_reducer_rejects_command_subclasses_before_property_access`. | `_mutant_16`: exit `1`, armed getter reached; restored `_restore_16`: exit `0`. |

The pre-mutation M1-M8 aggregate pin group used
`.pytest_tmp_wo0146_mutation_14_baseline`, exited `0`, and produced 11 passes.

## Restored source identities

These SHA-256 values were reproduced after restoring M10:

| Source | SHA-256 |
|---|---|
| `app/execution_core/fills.py` | `50832e3849aa3d3be888dd400a646dca04180dcf885aecabdecac0b3dbab6666` |
| `app/execution_core/identity.py` | `b7fbf9556031e00ca93fcd49c54deeaec2d0f56f614d6c396d92108c4960fcc2` |
| `app/execution_core/position.py` | `b59971afddcc52c725a8ed5de3ab84c5e49ab58b8621250e39fcd169e8a2e767` |
| `app/execution_core/recovery.py` | `684003e1ca480e1c6cd7bf2e2e8c864732bb2e0f67809acb3a550a814fddd40c` |
| `app/execution_core/venue.py` | `eb16bb8a24ff47c0de66af884ba778a63bae60fd3fbdedd1bfbb2236c1a671db` |

The first four files are unchanged from the fourteenth-gate production checkpoint. `venue.py`
changed from SHA-256 `b6f288a5b36878b017268934ae170f577c8c85faf63a84fc71c89809151edc98`
solely for the public-command boundary correction.

## Invalidated repository-coverage artifacts

Both historical runs used this exact command shape with the named absolute paths:

```powershell
$env:BROKER_ADAPTER='mock'
$env:COVERAGE_FILE='<absolute coverage-file path>'
.\.venv\Scripts\python.exe -m pytest -q --cov=app --cov-branch --cov-report=term-missing -p no:cacheprovider --basetemp <absolute base-temp path> --tb=line
.\.venv\Scripts\python.exe -m coverage report --precision=8 --fail-under=93
```

### `_14` -- INVALIDATED diagnostic failure

- Base-temp: `.pytest_tmp_wo0146_full_14`
- Pytest exit/duration: `0`; 1,127.6 seconds.
- Result: 5,099 collected; 5,087 passed; 11 skipped; one expected failure.
- Explicit coverage: `92.93816463%`, exit `2`; 17,525/18,500 lines and 6,072/6,890
  branches.
- Binary: 1,765,376 bytes; SHA-256
  `8392639ffa087fb767c690599fcaa52bd299c5c6819d06ff6be632b7ac8d510b`.
- JSON: 1,739,156 bytes; SHA-256
  `77e5759b023161e263c746d4fb4eac16c503ce106447045c037aa07d5f918b63`.
- Inadmissible because it failed the unchanged floor and predates M10.

### `_15` -- INVALIDATED former pass

- Base-temp: `.pytest_tmp_wo0146_full_15`
- Pytest exit/duration: `0`; 1,165.0 seconds.
- Result: 5,108 collected; 5,096 passed; 11 skipped; one expected failure.
- Explicit coverage: `93.00512013%`, exit `0`; 17,534/18,500 lines and 6,080/6,890
  branches.
- Binary: 1,765,376 bytes; SHA-256
  `aba5362c36543ac73a6bac620afbcc7c4574d6edfbfc8c83effc408843a70fe8`.
- JSON: 1,739,084 bytes; SHA-256
  `a97237e1ae1ed4daa7ef1cbb92ef59f1752a118cebf3dddacf2eedba7b5c248a`.
- Inadmissible because `1de7173` was invalidated by M10's production fix.

## Fifteenth-gate `_16` repository coverage

**IMPLEMENTATION-SEAT EXECUTED**

```powershell
$env:BROKER_ADAPTER='mock'
$env:COVERAGE_FILE='C:\Users\amujt\dev\automation-alpaca\.coverage_wo0146_full_authorized_16'
.\.venv\Scripts\python.exe -m pytest -q --cov=app --cov-branch --cov-report=term-missing -p no:cacheprovider --basetemp C:\Users\amujt\dev\automation-alpaca\.pytest_tmp_wo0146_full_16 --tb=line
.\.venv\Scripts\python.exe -m coverage report --precision=8 --fail-under=93
```

- Pytest exit: `0`
- Duration: 1,179.9 seconds.
- Result: 5,109 collected; 5,097 passed; 11 skipped; one expected failure.
- Explicit report: `93.00594652069468%`, exit `0`.
- Coverage obligations: 17,537/18,503 lines and 6,080/6,890 branches.
- `.coverage_wo0146_full_authorized_16`: 1,765,376 bytes; SHA-256
  `a46d40e58612413aa42c10add6a79f96c918313d385fe15a41feb068b574f798`.
- `.coverage_wo0146_full_authorized_16.json`: 1,739,738 bytes; SHA-256
  `9f9b9cbdc78af92a134658299ef125303ee1418137bd61ee3aa1bfc3e5104b9e`.

## Implementation-seat safety and provenance attestation

For the commands recorded here, the implementation seat attests:

- `BROKER_ADAPTER=mock` was forced for R2 and repository-wide coverage.
- No broker credentials were discovered, read, supplied, or used.
- No Alpaca Paper or other broker activity and no broker/network call was intentionally performed.
- No persistent application database was initialized or changed.
- Existing repository/R2 database-bearing tests used only previously authorized disposable
  test-only SQLite fixtures, including their fixture SQL/DDL.
- No runtime wiring, PR, merge, branch/worktree retirement, deletion, or cleanup occurred.
- The prohibited R1 DDL execution result was not cited or relied upon for design, testing, coverage,
  mutation, or acceptance.

These are implementation-seat attestations. Final review must not relabel them as independently
reproduced unless it performs and records an independent verification.

## Remaining acceptance gates

1. Freeze and commit the exact source, test, work-order, and transcript object.
2. Reconcile exact changed paths against WO-0146 scope.
3. Obtain reviewer-owned `result-addendum-02.md` against the exact final commit with no unresolved
   P0/P1.
4. Push only the exact reviewed/closeout head and obtain unchanged Python 3.11/3.12 exact-head CI.
5. Re-run any gate invalidated by a subsequent source/test byte change.

Until all gates complete, WO-0146 remains active, WO-0147 remains inactive, and no merge or
retirement action is authorized.
