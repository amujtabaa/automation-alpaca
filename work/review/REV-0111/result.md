---
type: Review Result
rev_id: REV-0111
work_order_id: WO-0168d
status: COMPLETE
review_mode: fresh-context findings-only static review
date: 2026-08-28
---

# REV-0111 — required-index fresh-prepare proof correction review

## Review boundary and verified identities

- Reviewed only `f1f1ad2dd5287ea3295f72298ef520151dc6ed75..e139a1a1b19ff58c82b189676bc7394b9d4c045e`.
- The candidate parent is the exact base.  Their trees are respectively
  `a76cb8bb1ce8adc9b707d7b2f76f45124075a37f` and
  `70e9fc519b4adc706f5cddcf50383b11180a6c6f`.
- The held test is candidate blob `3482d9162dc793d71e62ca7e1dd401242b406b6f`.
- The range changes exactly one file:
  `tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py`.
  The schema blob remains `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`, the repository blob remains
  `a147805eb486e76ba0069b7bafbac7cc44961a96`, and the DDL authorization flag is
  statically `False`.
- `git diff --check` produced no errors.

## Findings

No P0, P1, or P2 findings.

## Static re-derivation and disproof pass

- `_explain_details` constructs the prepared statement as `EXPLAIN QUERY PLAN {sql}`. The
  preceding direct-plan loop prepares that exact text for every selection query before
  `_assert_required_indexes_are_hard_requirements` returns the same manifest `sql` for its
  per-index drop probe. Thus, removing `fresh_sql` and passing `sql` again recreates the
  same-text survivor reported by REV-0110: a cached prepared plan can be returned after the
  savepoint-local `DROP INDEX` instead of establishing a post-drop prepare.
- Candidate lines 2025-2029 append a newline plus a block comment containing the dropped index
  only to the post-drop probe. The comment is inert SQL whitespace, while it changes the complete
  `EXPLAIN QUERY PLAN` text. Its index-specific value ensures that no earlier manifest probe has
  prepared the replacement text. The correction therefore forces the required fresh preparation
  at the owning negative-control boundary without mutating the repository tuple, DDL, indexes,
  runtime behavior, or public API.
- Candidate lines 2030-2034 require `sqlite3.OperationalError` with
  `no such index: <dropped-index>`. This rules out the former bare-error control accepting an
  unrelated operational failure: the post-drop statement itself carries the named index through
  the unchanged `INDEXED BY` manifest clause, and the expected missing-index identifier is bound
  to the index dropped in that iteration.
- Disproof pass: the no-comment mutant reuses the earlier full `EXPLAIN QUERY PLAN` text and is
  therefore the documented cache-surviving mutant. A comment shared across indexes would be a
  weaker counterexample, but the candidate comment includes the per-index name. A comment applied
  to the manifest tuple or connection configuration would exceed the owning test boundary; neither
  is present. No static counterexample remained that defeats both fresh-text preparation and
  dropped-index attribution.

No SQLite/database connection or database access/creation occurred. No DDL was installed, no
`tests_gated` tests were collected or executed, and no implementation, request, ledger, commit, or
push was changed by this review.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: Dynamic confirmation is intentionally absent: this static seat did not run the held suite or any SQLite operation.
