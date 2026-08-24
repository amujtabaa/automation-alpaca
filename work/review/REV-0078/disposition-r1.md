# REV-0078 disposition — R1 (author seat, after the BLOCK verdict)

Date: 2026-08-24 · Author: implementing seat (Claude) · Verdict dispositioned: **BLOCK (P0=1, P1=7, P2=3)** at reviewed candidate `5d3df2b`

The reviewer's `result.md` is merged unmodified (commit `5bfec3a`); per P-1 nothing in it is
edited, and this disposition plus the request amendment are the author-side record. Verification
below is **pure/static only** — per the reviewer's gate disposition, no changed-DDL install and no
SQLite-bearing test has run since the verdict.

| Finding | Disposition | What was done |
| --- | --- | --- |
| **P0-1** DDL before the gate | **ACCEPTED** | Gate bundle Amendment 2 marks every prior `tmp_path`/`:memory:` run noncompliant and unusable as gate evidence; their counts stand only as history. Self-derived approval removed at source: all installing fixtures read the one transcribed literal (`approved_schema_digest.py`), and `test_no_installer_approves_itself_with_a_self_derived_digest` (AST) refuses the `schema_ddl_digest()` spelling — probed: reintroducing it fails the control. The literal is statically verified equal to the ratified digest by text hash only. Fresh gate packet = `request.md`; nothing DDL-bearing executes until Ameen approves it. |
| **P1-1** same-key splices | **ACCEPTED, FIXED** | Owner attempts bind observation + effect against the selected owner record (surrogate id resolved through selected effects). Correlations bind effect/owner/generation against the selected root route. Both coverages bind the full `RootFillKey` (broker/environment/account), on the head and corroboration facts too. Reconciliations carry the referencing row's effect where the referencer has one and require equality. Nine splice mutants added; sweep below. |
| **P1-2** descriptor scope bridge | **ACCEPTED, FIXED** | Slot references carry `(effect_id, position_scope)`; descriptor resolution requires `permit.position_scope` to equal the referencing slot's scope and `permit.application_generation_id` to equal the selected generation. Cross-scope and cross-generation negative controls added. |
| **P1-3** `INDEXED BY` parsing | **ACCEPTED, FIXED — and the hole was deeper** | The fix is a negative lookahead in `_SQL_SOURCE_ALIAS`, not a post-hoc guard: a keyword consumed as an alias didn't just misname the source, it swallowed the next bare `JOIN` source from the set entirely. Six-case pure parser control pinned (`test_base_table_plan_names_resolves_indexed_by_and_bare_aliases`). The EXPLAIN-based unbounded-plan negative control is deferred to the approved gate run — it requires an installed schema. |
| **P1-4** four untested branches | **TWO FIXED, TWO DISPUTED-AND-CORRECTED** | The two duplicate-collision guards now have direct tests (two-legs, two-scopes). The two absent-row raises were not tested because they were **wrong**: an applied fill's coverage names its own evidence input and creates no reconciliation (`recovery.py:963` — `root_source_input_id=item.input_id`, no record on that arm), and an initial bootstrap target's `checkpoint_input_id` is the registry input, never a catch-up. Raising refused every applied-fill and every freshly-bootstrapped book — the same unprojectable-ordinary-state class this review cycle removed elsewhere. Both arms revert to omission, pinned by name (`test_rev78_referenced_input_with_no_reconciliation_is_omitted`, `test_rev78_initial_bootstrap_with_no_registry_outcome_is_omitted`). The handoff's overstated mutation claim is corrected in place. |
| **P1-5** out-of-scope paths | **ACCEPTED** | The active work order carries a dated released-paths amendment naming every path with its authorizing decision. |
| **P1-6** R15 §3 / R16 §2 conflict | **RESOLVED BEFORE THE VERDICT LANDED** | Ameen ratified exactly the reviewer's recommended decision on 2026-08-24 (`36-R16-MANUAL-RULE-RATIFICATION.md`, commit `c725dfb` — after the reviewed `5d3df2b`). The previously unpinned duplicate refusal was tested in the same commit. |
| **P1-7** no frozen request | **ACCEPTED** | Canonical `request.md` follows this disposition, freezing the immutable post-remediation head/tree/range, commit list, changed paths, DDL identities, evidence, and limitations. `request-r1.md` is superseded and marked so. |
| **P2-1** wrong citation | **ACCEPTED, FIXED** | Both reconciliation docstrings now cite R15 §2 as governing and explicitly decline R16 §2 as authority for venue indexes. |
| **P2-2** unreproducible commands | **ACCEPTED, FIXED** | `PYTHONPATH=. python tests/r2_conformance_oracle.py`; floor finding names `tests/execution_core/test_import_boundary.py`. |
| **P2-3** whitespace | **ACCEPTED, FIXED** | EOF blank line removed; `git diff --check` clean over the exact range. |

## Mutation sweep (reproducible)

Each guard disabled by rewriting its exact `if` to `if False and …`, then
`pytest tests/execution_core/test_persistence_runtime_checkpoint_pure.py -q -p no:randomly`;
count = tests failing under the mutant, restored after each:

```text
owner observation binding        -> 1   two-legs collision guard    -> 1
owner effect binding             -> 1   two-scopes collision guard  -> 1
correlation route binding        -> 1   descriptor scope binding    -> 1
broker coverage full RootFillKey -> 2   descriptor generation bind  -> 1
reconciliation referencing effect-> 1
```

## Author verification at the remediation head (pure/static only)

```text
pytest tests/execution_core/test_persistence_runtime_checkpoint_pure.py     114 passed
pytest tests/execution_core/test_persistence_write_capability.py              8 passed
pytest tests/test_import_boundaries.py                                        6 passed
pytest ...checkpoint_sqlite.py -k resolves_indexed_by   (string parsing only) 1 passed
ruff check · mypy app/ (95 files) · lint-imports (6 kept)                     clean
git diff --check 344c32b..HEAD                                                clean
NOT run: every SQLite-bearing test, per the reviewer's gate disposition.
```
