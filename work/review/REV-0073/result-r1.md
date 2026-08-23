---
type: Review Result
rev_id: REV-0073-R1
status: BLOCK
candidate_commit: fe23558cee249906af8286e73f77ad498d6c24f1
candidate_tree: 3c5b40988c9a63b0db0631d46e7f53679020b9e9
base_commit: 0a7b5ae324c34be488da24478f95e2658a1bb894
blocked_predecessor: 356297b042fc3b5ba00ccb36526717ffc5aa6dde
date: 2026-08-22
review_mode: independent exact-tree adversarial R1 review
---

# REV-0073 R1 — WO-0167 independent review result

## Findings

### P0 — The composite directness gate still accepts indexed range and history-fold queries

- Location: `tests/execution_core/test_persistence_directness.py:567`; `tests/execution_core/test_persistence_directness.py:579`
- Requirement: `AGENTS.md` classifies a test that cannot fail for its claimed defect as P0. WO-0167 FR-5/AC-3 and the R1 request require exact direct-key predicates, fixed query shapes/counts, and failure-capable history-fold controls.
- Evidence level: `reproduced-live`
- Evidence:
  - The unmodified focused gate passed: `53 passed`.
  - Replacing the composite checkpoint equality predicate with indexed range predicate `application_generation_id >= ?` still passed `test_total_proof_uses_only_fixed_direct_key_queries_under_history_stress`.
  - Replacing the exact current-fact lookup with a per-root query that reads the full fact history, orders it by ordinal, and constructs the current record from the final row also passed that test.
  - Both mutants survive because `_capture_proof_queries` requires only some `WHERE`, an indexed `SEARCH`, and no scan/temp sort. It does not pin the exact allowed predicates, query count, or direct-current query shapes.
- Impact: The acceptance gate can remain green after an exact-key lookup is widened into a history-length-dependent indexed range or fact fold. The current implementation is statically direct, but the mandatory completion evidence cannot prevent that regression from shipping.
- Resolution: Pin the exact ordered composite query count, tables, predicates, and key coordinates for each proof mode. Seed multiple application/checkpoint keys and multiple facts for the requested root, then require indexed-range and keyed-history-fold mutants to fail for their intended reasons.

### P1 — Optional-claim handling converts an authenticated SQLite read failure into a successful proof

- Location: `app/execution_core/persistence/repository.py:2481`; `app/execution_core/persistence/repository.py:2487`
- Requirement: WO-0167 FR-3, EC-1, and EC-3 require integrity/query failures to fail closed with no partially trusted proof. Only a confirmed absence may establish that an early-lifecycle effect has no claim.
- Evidence level: `reproduced-live`
- Evidence:
  - A normal `REQUESTED` effect with no claim returned `FOUND`, as expected.
  - An exact `sqlite3.DatabaseError` injected at `SELECT ... FROM dispatch_claim WHERE effect_id = ?` caused `_select_one_unchecked` to return `INTEGRITY_FAILURE`.
  - The early-lifecycle branch checks only whether the outcome is `FOUND`; it ignores `INTEGRITY_FAILURE` and returned `FOUND` with a non-null proof and `dispatch_claim=None`.
  - Probe output: `baseline=found injected=found record=True`.
- Impact: Database corruption, a failed claim read, or malformed claim decoding can be represented as authoritative claim absence. A future M2-I4 consumer could receive a supposedly total proof even though one required integrity check failed.
- Resolution: For `REQUESTED` and `CANCELED_BEFORE_DISPATCH`, accept only `ABSENT`. Reject `FOUND`, and propagate every integrity/error outcome as `INTEGRITY_FAILURE` with `record=None`.

### P1 — Integral floats alias integer repository keys instead of failing exact-type validation

- Location: `app/execution_core/persistence/repository.py:216`; `app/execution_core/persistence/repository.py:219`
- Requirement: WO-0167 FR-3/FR-6 and AC-1 require explicit typed operations and refusal of type-mismatched coordinates.
- Evidence level: `reproduced-live`
- Evidence:
  - `_query_parameters` explicitly accepts `float`.
  - With scope key `1` retained, `load_scope(connection, True)` correctly returned `INTEGRITY_FAILURE`, but `load_scope(connection, 1.0)` returned `FOUND` for scope `1`.
  - Probe output: `bool=integrity-failure float=found scope=1`.
  - The accepted schema families use integer, text, and blob query coordinates; no repository loader requires a real-valued key.
- Impact: A caller can cross the typed repository boundary with the wrong runtime type and hydrate a real row because SQLite aliases integral floats to integer keys. Other numeric loaders using the shared helper have the same exposure.
- Resolution: Remove `float` from accepted query-coordinate types, or validate each integer loader coordinate with `_exact_int` before domain SQL. Add integral-float aliases to the all-numeric-loader refusal matrix.

## Reconciliation

### REV-0072 findings

- Inert import: remediated. Clean import returned `0`; the outside-scratch write mutant returned `1`.
- Incomplete repository surface: remediated. Accepted schema families, trigger-owned load-only rows, mutable advances, and total proof records are present and export-pinned.
- Codec/profile bypass: remediated. The codec-bypass mutant failed its selected test for missing accepted decoder tags.
- Trigger ownership and advances: remediated for the originally reported mechanisms. All five stale advance families returned `CONFLICT`; contradictory controller/effect/cursor authority returned integrity failure; retirement and rollback controls passed.
- SQLite provenance/classification: exact-class spoofing and broken claim-authority probes passed. The new optional-claim failure above is a separate fail-closed defect after classification.
- Directness and failure-capable evidence: guard, cardinality, omission, fabricated-member, and unindexed/unkeyed controls improved, but the P0 indexed-range/history-fold gap remains.
- Governance identity/scope/ledger: exact identities, allowed scope, ledger, install, version, PKL, disposition, and whitespace checks passed.

### Original REV-0073 findings

- Codec bypass, fabricated checkpoint, and plainly unkeyed composite query mutants now fail for their intended reasons. Stronger indexed-range and history-fold variants still survive, producing the P0 above.
- Controller, effect, and cursor contradictory immutable-authority handling is remediated.
- Checkpoint/controller currentness equality is enforced, and the stale-head counterexample returns integrity failure without a record.

### Disposition and specialist disclosures

- Exact proof-member omission: all 21 declared omission cases passed; the fabricated-current-checkpoint mutant failed at the omission assertion.
- Advance authority: remediated for controller, effect, and cursor; stale state remains conflict.
- SQLite class/MRO spoofing and duplicate-probe authority: the disclosed controls passed.
- Boolean/integer aliasing: boolean aliases are rejected, but the adjacent integral-float alias remains open as P1.
- Exact exports, import auditing, caller-owned transactions, retirement behavior, and decoder provenance: controls passed and their selected mutants failed.
- Composite query plans: production queries used indexed searches, but exact predicate/count and history-fold enforcement remains incomplete as P0.
- Checkpoint/controller head equality: remediated.

### WO-0167 contract

- FR-1: verified for the reviewed source; explicit connections only, with no configured path, hidden connection, or repository-owned transaction.
- FR-2: accepted families and total proof surface are present.
- FR-3: not satisfied because claim-query integrity failure is treated as absence and integral floats bypass exact coordinate typing.
- FR-4: no second reducer or serving decision was found.
- FR-5: current source is statically direct, but AC-3’s required failure-capable exact-key/history-fold gate is incomplete.
- FR-6: no repository commit/begin/rollback survived the controls; exact typing remains incomplete because of float aliases.
- FR-7: no audit/receipt override path was found.
- AC-1: blocked by the exact-coordinate P1.
- AC-2: no contradiction found.
- AC-3: blocked by the P0 directness-control gap.

## Fresh evidence

- Candidate commit/tree, base, blocked predecessor, ancestry, clean worktree, and documentation-only later HEAD were verified.
- Focused repository/directness gate: `53 passed` on CPython 3.12.13.
- Mandated mutants:
  - codec bypass: killed;
  - fabricated current-proof checkpoint: killed at the omission assertion;
  - plainly unkeyed composite checkpoint query: killed by a table-scan plan;
  - repository commit: killed;
  - no-op retirement: killed;
  - export expansion: killed;
  - outside-scratch import write: killed (`actual=0`, `mutant=1`).
- Stronger disproof mutants:
  - indexed range predicate: survived;
  - per-root fact-history fold: survived.
- Ruff check and format passed on all four changed Python paths.
- Accepted schema, durable codec, and profile sources retained their recorded hashes and were unchanged from the accepted base.
- AI-OS install, version v0.9.2, ledger, PKL, disposition, exact work-order scope, and `git diff --check` passed.
- No repository files were edited or created.

## Unverified

- The author’s `426 passed` codec/profile/value/schema/import integration run was not rerun.
- The 61-case R2 oracle was not rerun because the assigned boundary prohibited in-memory database use.
- The 1,743-test, approximately ten-minute full execution-core suite was not rerun, as instructed.
- Mypy, Import Linter, broader repository tests, coverage ratchets, Python 3.11, GitHub Actions, and external review state were not rerun or verified.
- No configured/existing database, in-memory database, network, credentials, broker call, order, DDL/schema change, migration, runtime composition, or M2-I4 work was used.

## Verdict

`BLOCK`

- P0: 1
- P1: 2
- P2: 0
