---
type: Review Result
rev_id: REV-0072
status: BLOCK
candidate_commit: 6b65c982e87a521e1a3c86cbc6c67049508bf8e6
candidate_tree: 5e22c19a5cec193202e5d57b4e8005cee526d332
base_commit: 0a7b5ae324c34be488da24478f95e2658a1bb894
date: 2026-08-22
review_mode: independent Codex exact-head adversarial review
---

# REV-0072 — WO-0167 independent review result

## Findings

### P0 — The inert-import completion test cannot observe import-time side effects

- Location: `tests/execution_core/test_persistence_repository.py:107`
- Requirement: `AGENTS.md` makes a test that cannot fail for its claimed defect P0; WO-0167 requires inert imports and forbids filesystem/configuration/runtime side effects.
- Evidence (`reproduced-live`): `repository_module` is imported at module-collection line 9, before the test captures `before = set(sys.modules)`. Nothing is imported between `before` and `after`. A probe created a filesystem sentinel representing an already-completed import side effect and then called the exact test; it passed (`prior_import_side_effect_inert_test SURVIVED`). The assertion can detect only unrelated concurrent imports after collection, not behavior caused by importing the repository.
- Impact: the submitted green evidence cannot establish the inert-import safety claim. Import-time filesystem, configuration, credential, database, or runtime work could execute before this test starts and remain invisible.
- Resolution: run the repository import in a clean subprocess after establishing the baseline, assert the exact allowed module/file/environment effects, and prove the test fails with an isolated import-side-effect mutant.

### P1 — The candidate implements only a fraction of the activated WO-0167 contract

- Location: `app/execution_core/persistence/repository.py:355`; `work/review/REV-0072/request.md:20`
- Requirement: WO-0167 FR-2 and AC-1 require bounded hydration and typed round trips for every accepted repository family: profiles, controller, direct routes, fact/revision heads, effects, claims, owners, acceptance/closure, protection, and market cursor.
- Evidence (`static-reasoning`): the public surface covers application generation, scope, acquisition generation/current, kernel checkpoint, fact head, dispatch claim, and acceptance set only. It has no execution/market profile hydration, symbol-controller record, root-fill/fact record, venue effect/owner, acquisition-root route, acceptance evidence, closure head, market stream/cursor, protection authority, or total current-proof slice. The request itself declares most of these omissions and labels the submission an increment, but no separately authorized split narrows WO-0167.
- Impact: M2-I3 is not complete and cannot provide the total direct proof M2-I4 is meant to compose. Accepting this candidate would silently convert one bounded work order into an untracked sequence of partial implementations.
- Resolution: either complete the activated WO-0167 surface and tests on this branch or formally split/re-authorize exact successor increments with explicit entry/exit criteria. Do not close WO-0167 or activate M2-I4 from this head.

### P1 — Records bypass the accepted M2-I1 codec and profile contracts

- Location: `app/execution_core/persistence/records.py:23`; `app/execution_core/persistence/repository.py:14`
- Requirement: WO-0167 FR-3, EC-2, and AC-1 require decoding only through the accepted M2-I1 codecs and rejection of type/version/profile mismatch before domain use.
- Evidence (`static-reasoning`): all records are unvalidated raw `str`/`int` dataclasses, `RepositoryOutcome.record` is `Any`, and neither new module imports or calls `DurableAtom`, `encode_m1_value`, `decode_m1_value`, `ExecutionConnectionProfile`, or `MarketDataSourceProfile`. There is no codec version/type tag to validate and no cross-type or profile-decoding path. The focused tests contain no malformed atom, unknown version, cross-type substitution, or profile round trip.
- Impact: rows are returned as loosely typed storage DTOs rather than accepted M1 values/profiles. The repository cannot satisfy exact value/profile equality or fail closed at the durable decoding boundary.
- Resolution: derive typed records from the accepted M2-I1 values/profiles, route all durable value conversion through the accepted codec, validate exact type/version/profile coordinates, and add independently constructed positive and refusal tests.

### P1 — Public write APIs claim ownership of trigger-derived rows and omit required current-row advances

- Location: `app/execution_core/persistence/repository.py:204`; `app/execution_core/persistence/repository.py:269`; `app/execution_core/persistence/repository.py:237`
- Requirement: WO-0167 FR-4 and FR-6 require a thin repository that stores owner-produced outcomes without re-deciding currentness; direct primitives must match the accepted schema's actual ownership model.
- Evidence (`reproduced-live` and `static-reasoning`): `trg_acquisition_generation_initializes_current` creates `acquisition_generation_current` automatically (`schema.py:1742`), so a normal `store_acquisition_generation` returned COMMITTED, `load_acquisition_generation_current` immediately returned FOUND, and the separate `store_acquisition_generation_current` returned CONFLICT. Likewise, `trg_execution_fact_maintains_direct_head` owns insert/update of `execution_fact_head` (`schema.py:2425`), making `record_execution_fact_head` an invalid independent owner. Conversely, `record_kernel_checkpoint` supports only initial INSERT even though the schema explicitly supports monotonic versioned UPDATE (`schema.py:1834`).
- Impact: two exported operations cannot legitimately commit in the accepted normal flow, while mutable current proof cannot advance. This creates misleading APIs and leaves the repository unable to persist ordinary accepted successor state.
- Resolution: build and record a table/trigger ownership matrix. Expose trigger-derived rows as verified loads, persist their owning facts/routes instead, and add explicit expected-version/head update operations for repository-owned mutable-current rows with positive, stale, rollback, and conflict tests.

### P1 — Constraint and exception classification does not preserve conflict versus integrity semantics

- Location: `app/execution_core/persistence/repository.py:35`
- Requirement: WO-0167 EC-1/EC-2 and the API contract require malformed/mismatched/broken authority to return integrity failure, while genuine identity/current-write contention returns conflict; non-SQLite exceptions must propagate.
- Evidence (`reproduced-live`): storing `ScopeRecord(..., symbol_text="")` violated the schema CHECK but returned `CONFLICT`, not `INTEGRITY_FAILURE`. A non-SQLite custom exception whose class was merely named `IntegrityError` was also translated to `CONFLICT`. `_classified_failure` authenticates exceptions only by class-name text and treats every non-FK SQLite integrity failure—including CHECK and authority-trigger failures—as conflict.
- Impact: malformed records and broken authority can be reported as retryable contention, while unrelated libraries can have exceptions laundered into repository outcomes. Callers cannot safely distinguish duplicate identity from corrupted or unauthorized state.
- Resolution: authenticate exact SQLite exception provenance and classify per operation/constraint. Only expected duplicate/current-version contention should map to conflict; malformed CHECK/FK/authority-trigger failures should map to integrity failure, and non-SQLite exceptions must propagate. Add direct tests for each class.

### P1 — Directness, guard, and exported-operation tests are not failure-capable for the claimed boundary

- Location: `tests/execution_core/test_persistence_directness.py:27`; `tests/execution_core/test_persistence_repository.py:128`
- Requirement: WO-0167 AC-1/AC-3 requires every family round trip plus history-fold/type-scan mutants that fail; every operation must execute the schema guard.
- Evidence (`reproduced-live`): the directness test loads an absent checkpoint, grows a different profile table, and asserts only equal result/equal query count. Replacing `load_kernel_checkpoint` with an actual unfiltered full-table `SELECT ... FROM kernel_checkpoint` mutant still passed (`full_table_scan_directness_mutant SURVIVED`). The request also admits that six exported fact-head/claim/acceptance operations are untested and that removing the guard from one path is not killed. Additional exported success paths—including `store_application_generation`, successful `load_scope`, `store_acquisition_generation_current`, and most current-state operations—have no direct behavioral proof.
- Impact: a history/type scan, hard-coded absence, missing guard, or broken exported method can retain a green focused suite. Query boundedness and public API completeness are therefore unproven.
- Resolution: seed populated targets and relevant same-family stress history; assert exact records and outcomes; capture the actual SQL and exact index plan for each load/current-proof composition; and kill full-scan, history-fold, hard-coded-result, missing-totality, and per-operation guard mutants with non-empty test selections.

### P1 — Review identity, scope, and ledger records are not internally valid

- Location: `work/review/REV-0072/request.md:14`; `work/active/WO-0167-m2-i3-sqlite-repository-hydration.md:104`; `work/ledger.jsonl:214`
- Requirement: the review packet must freeze the exact semantic candidate, activation must append the exact review path, and the ledger/governance gates must pass before completion.
- Evidence (`reproduced-live`): the request binds implementation/tests only through `adc8c59` and says later commits touch review docs only, but `6b65c98` changes `repository.py` and its tests. The active work order never appended `work/review/REV-0072/request.md`; the exact scope checker fails on that path. `check_ledger.py` fails line 214 because the appended object lacks required `id`, `title`, `disposition`, `commit`, and `reason` fields. The request still reports 10 focused tests and a full suite at the earlier `ea22a6f`, while the final head has 11 focused tests and no author-recorded final-head full run.
- Impact: a reviewer can be directed to the wrong semantic cutoff, and mandatory governance gates are red. The branch cannot be accepted or closed with this packet state.
- Resolution: repair the append-only ledger with the canonical schema, amend the active work order with the exact review path, re-freeze the final semantic head/tree/diff and changed paths, and rerun/report the required checks at that exact head.

## Fresh evidence at the reviewed head

- Identity: local `HEAD`, upstream, fetched `origin`, and branch all matched `6b65c982e87a521e1a3c86cbc6c67049508bf8e6`; tree `5e22c19a5cec193202e5d57b4e8005cee526d332`; worktree clean before this result.
- Focused repository/directness suite: 11 passed on CPython 3.12.13.
- `tests/execution_core`: 1,699 passed and one Grimp cache-write `PermissionError` under the review sandbox; the exact failed Grimp test passed 1/1 when rerun with normal worktree cache access. No functional candidate failure was observed in that broad run.
- Ruff check/format: passed on all four changed Python paths.
- Mypy: success across 93 source files.
- Import-linter: 6 contracts kept, 0 broken.
- R2 conformance oracle: 61 passed with an explicit temporary base.
- AI-OS install/version/PKL/disposition: passed. Ledger and changed-path scope: failed as described above.
- `git diff --check`: passed.

## Unverified

- Broader non-`execution_core` repository tests and coverage ratchets were not run.
- A single unrestricted final-head run of all 1,700 execution-core tests was not repeated; the one sandbox-only Grimp failure was reproduced separately as passing.
- No external cross-model or GitHub Actions verdict is claimed.

## Verdict

`BLOCK`

- P0: 1
- P1: 6
- P2: 0
