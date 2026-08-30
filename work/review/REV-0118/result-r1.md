# REV-0118 finite correction re-review

Exact candidate reviewed: `0587c7069dfcea7b53e37a35b2cad89cf72bd69d`, tree `ec14552d7f73e8c223d7581a8b5d2f99449c744d`.

Final implementation/test source: `c7e394f52782a9b398ed89bfdc55b45bc09499b4`, tree `2d5c662f569ec3ee792216863fe46213551773a8`.

## Retained P1-1 — CLOSED: finite catalog lacked decisive tests

- Severity: Original P1; closed.
- Exact locations: `harness/m2/closeout.py:102`, `:143-145`; `tests/execution_core/test_persistence_fault_matrix.py:74`; `tests_gated/execution_core/test_persistence_fault_matrix.py:110`, `:120`, `:132`.
- Demonstrated failure: The durable-input-claim control asserts the exact before/after fault pair and routes both through the old-complete rollback oracle. Separate gated controls establish a complete baseline and then require integrity refusal for erased dispatch claim, omitted acceptance, and omitted closure. The cursor control independently regresses fixed and published ordinals, requires the exact monotonicity failure, and confirms retained `(4, 5)` state.
- Real-world impact: Each catalog obligation now fails on the defect it names rather than inheriting success from a broad neighboring test.
- Smallest root correction: The finite catalog now maps directly to these dedicated, failure-capable nodeids.
- Evidence level: `reproduced-live` for the pure catalog controls; `source-rederived` plus `supplied-held` for the gated controls.
- Disproof pass: Checked for a missing claim phase, a shared acceptance/closure path that exercised only one omission, and a cursor case that preserved `fixed <= published` while avoiding monotonic enforcement. The exact two claim phases, both omission parameters, and both independent cursor regressions are present. No residual bypass found.

## Retained P1-2 — CLOSED: boundedness omitted real hydration work

- Severity: Original P1; closed.
- Exact locations: `tests_gated/execution_core/test_persistence_boundedness.py:75`, `:97-127`, `:130`, `:155`, `:190`, `:198`, `:243-259`; `tests/performance/m2_persistence_budget.py:22-24`.
- Demonstrated failure: Setup stores a canonical checkpoint and propagates its repository-issued head. The measured path invokes `_m2_load_compact_context`, which loads the envelope, selects current proof, decodes compact components, and restores the runtime context. The test measures target/stress elapsed time, traced read-statement counts, and hydration peak memory against the frozen 12x/2 MiB limits, while checking every selection and load plan on both databases.
- Real-world impact: Unbounded load, decode, or compact restoration can no longer hide behind bounded selector-only evidence.
- Smallest root correction: Extend the existing boundedness test around the actual hydration entry point while retaining the frozen budget contract.
- Evidence level: `source-rederived`; the three pure budget controls were `reproduced-live`; the seven-case SQLite execution is `supplied-held`.
- Disproof pass: Checked for stale pre-checkpoint requests, selector-only timing, target-only plans, omitted load plans, statement counts that excluded hydration, and memory measured outside the hydration call. Each failure mode is now explicitly covered. The transient direct setup-support import was also removed; the frozen-importer static control passed.

## Retained P1-3 — CLOSED: restore ignored orphan destination sidecars

- Severity: Original P1; closed.
- Exact locations: `harness/m2/closeout.py:252-255`, `:296-310`; `tests/execution_core/test_persistence_restore.py:57`, `:93`.
- Demonstrated failure: Snapshot refuses an existing destination database, WAL, or SHM before inspecting source sidecars. Verification refuses an unrecorded destination WAL or SHM created after snapshot.
- Real-world impact: A stale destination sidecar cannot contaminate or alter an otherwise byte-exact restore.
- Smallest root correction: Treat the destination database/WAL/SHM as one collision family and validate the recorded suffix set during verification.
- Evidence level: `reproduced-live`; both WAL and SHM variants passed in the exact 60-test pure control run.
- Disproof pass: Exercised destination WAL and SHM with a source that had neither sidecar, then introduced each sidecar after evidence creation. Both pre-snapshot and post-snapshot routes fail closed. No residual source-dependent collision path found.

## [P0] Exact candidate contradicts its diff-hygiene green claim

- Severity: P0. `AGENTS.md` classifies a completion/green claim that cannot be reproduced as blocking.
- Exact locations: `harness/m2/M2-CLOSEOUT-MANIFEST.md:95`; `work/review/REV-0118/execution-result-r8.md:23`. Violating lines are `execution-packet-r6.md:56`, `execution-packet-r7.md:37`, `execution-packet-r8.md:30`, `execution-result-r6.md:29`, `execution-result-r7.md:30`, and `execution-result-r8.md:29`.
- Demonstrated failure: `git diff --check d801fb1730d9116334b5eee735577217abee7d9f..0587c7069dfcea7b53e37a35b2cad89cf72bd69d` exits 1 and reports a new blank line at EOF in all six files. The source-to-candidate range also exits 1 for the three later artifacts.
- Real-world impact: The authoritative manifest and R8 result assert a passing closeout gate that the exact candidate does not pass, so its green evidence is not independently reproducible.
- Smallest root correction: Remove the extra EOF blank lines, rerun the exact base-to-final-candidate check, and rebind any affected artifact hashes and evidence claims.
- Evidence level: `reproduced-live`, using exact Git objects.
- Disproof pass: Verified the candidate/source trees, confirmed R8 is a flag-only child of the final source, confirmed no tracked working-tree changes, and repeated the check across original-candidate-to-source and source-to-final-candidate ranges. The failures are committed correction artifacts, not checkout dirt or the later publication commit.

No SQLite connection, database, or held-suite execution occurred in this review seat. The live restore controls used ordinary byte files only.

Verdict: BLOCK
P0: 1
P1: 0
P2: 0
Unverified: R8 seven-case held execution; full 2,310-test ordinary suite; 61-case R2 oracle; Ruff, mypy, Import Linter, and AI Project OS gates; 24-hour soak remains NOT_RUN; R16 remains NOT_EVALUATED
