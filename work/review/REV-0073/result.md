---
type: Review Result
rev_id: REV-0073
status: BLOCK
candidate_commit: 356297b042fc3b5ba00ccb36526717ffc5aa6dde
candidate_tree: d5576b711150b1c41902ba921a188638c7a7e70c
base_commit: 0a7b5ae324c34be488da24478f95e2658a1bb894
date: 2026-08-22
review_mode: independent exact-tree adversarial review
---

# REV-0073 — WO-0167 independent review result

## Findings

### P0 — The focused completion gate cannot fail for three required M2-I3 controls

- Location: `tests/execution_core/test_persistence_repository.py:357`; `tests/execution_core/test_persistence_repository.py:746`; `tests/execution_core/test_persistence_directness.py:493`; `tests/execution_core/test_persistence_directness.py:543`
- Requirement: `AGENTS.md` classifies a test that cannot fail for its claimed defect as P0. WO-0167 AC-1/AC-3 and the REV-0073 request require failure-capable codec-decoding, direct-key, and total-current-proof controls.
- Evidence level: `reproduced-live`
- Evidence:
  - The unmodified focused gate passed: `23 passed`.
  - Replacing repository identity decoding with direct constructors that bypass `_decode_m1_value` still produced `23 passed`.
  - Replacing the required checkpoint lookup inside `load_current_proof` with a fabricated `KernelCheckpointRecord` still produced `23 passed`.
  - Replacing the checkpoint key predicate inside `load_current_proof` with unfiltered `WHERE (? IS NOT NULL)` still produced `23 passed`.
  - Control mutations were effective elsewhere: removing a schema guard and removing the second-row cardinality check both failed their named tests for the intended reasons.
- Impact: The green focused evidence does not establish that repository reads use the accepted codec, that every required proof member comes from SQLite, or that composite hydration remains direct-key bounded. Those exact regressions can ship while the completion gate remains green.
- Resolution: Add repository-level codec-bypass mutants, independently omit each proof member after all other members exist, and capture the actual `load_current_proof` SQL and `EXPLAIN QUERY PLAN` under same-family stress. Each mutant must make a non-empty focused selection fail for its intended reason.

### P1 — Expected-state advance APIs accept records with contradictory immutable authority

- Location: `app/execution_core/persistence/repository.py:864`; `app/execution_core/persistence/repository.py:1256`; `app/execution_core/persistence/repository.py:1768`
- Requirement: WO-0167 FR-3/FR-6 and AC-1 require typed, exact profile/scope binding and refusal of mismatched records.
- Evidence level: `reproduced-live`
- Evidence:
  - `advance_symbol_controller` returned `APPLIED` for a record containing a different application generation and execution profile; reloading retained the original bindings.
  - `advance_market_cursor` returned `APPLIED` despite contradictory scope, application, acquisition generation, mandate, source profile, session, and sequence mode.
  - `advance_venue_effect` returned `APPLIED` despite contradictory effect identity, scope, application/profile/generation authority, quantity, and economic scope.
  - In each case, the method updates only mutable columns and silently discards contradictory fields from the supplied full record.
- Impact: A caller can receive `APPLIED` even though the supplied typed reducer projection was not the record persisted. M2-I4 could treat a stale or cross-authority outcome as successfully stored.
- Resolution: Either validate every immutable field against the retained row within the caller’s transaction or replace the full-record parameter with an explicitly narrow mutable-update type. Existing identity with contradictory binding must produce `INTEGRITY_FAILURE`, with stale expected state remaining `CONFLICT`.

### P1 — Current-proof hydration accepts a checkpoint behind the loaded controller and fact state

- Location: `app/execution_core/persistence/repository.py:2171`; `tests/execution_core/test_persistence_repository.py:416`; `tests/execution_core/test_persistence_repository.py:499`
- Requirement: WO-0167 FR-3 requires inconsistent heads to be rejected; `CurrentProofSlice` must be total and internally consistent.
- Evidence level: `reproduced-live`
- Evidence: The accepted-schema fixture inserts the first execution fact, confirms that the symbol-controller currentness head advanced to `1`, leaves the kernel checkpoint at `0`, and then receives `FOUND` from `load_current_proof`. The isolated counterexample reported `found ... checkpoint=0 controller=1`.
- Impact: A partially advanced durable state can be labeled a complete current proof instead of failing closed. The outcome itself does not authorize serving, but it supplies inconsistent input to the future M2-I4 composition boundary.
- Resolution: Enforce the accepted checkpoint/controller/fact currentness relationship during composite hydration, including refusal when the checkpoint remains behind the loaded current heads. Add a test that advances the fact/controller while deliberately retaining the old checkpoint.

## Fresh evidence

- Exact base, commit, tree, ancestry, and documentation-only later HEAD were verified.
- Focused repository/directness gate: 23 passed.
- Remaining codec/profile/value/schema/import tests: 373 passed; combined relevant gate: 396 passed.
- Actual unmutated composite proof executed 21 indexed production queries with 500 unrelated roots; no domain-table scan or temporary sort was observed.
- Ruff check and format passed.
- Mypy passed over 93 application files.
- Import Linter kept 6 contracts with 0 broken.
- Ledger, install, version, PKL, disposition, exact-target scope, later-documentation scope, and `git diff --check` passed.
- The import-side-effect, schema-guard, and duplicate-cardinality controls killed their selected mutants.
- No configured/existing database, in-memory SQLite database, network, credentials, broker call, order, runtime composition, or M2-I4 work was performed.

## Unverified

- The claimed full `tests/execution_core` result of 1,713 passed was not rerun.
- The 61-case R2 oracle was not rerun; its fixture parameterizes legacy memory and SQLite stores, and verification stopped under the stated boundary.
- Broader repository tests, coverage ratchets, and Python 3.11 execution were not run.
- GitHub Actions and any external independent-review result were not verified.

## Verdict

`BLOCK`

- P0: 1
- P1: 2
- P2: 0

No files were edited or created in the worktree.
