# REV-0079 request — WO-0168c static remediation candidate

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**.
A result of `P0=0` and `P1=0` is necessary but not sufficient to execute SQLite:
Ameen must separately approve the exact candidate identity and fresh-file plan.

## Frozen review target

```text
Candidate commit: 2f16f52763add275892836b396f1f8b9decfd1f7
Candidate tree:   5adb2e2c266f9cb93145e670e993fb03156f9d83
Remediation base: 3b26c1cd636615cf0d85c13951eaebf099b88bdc
Base tree:        fb42ee7a3b689a399ea2e43b6e607d004497075d
Review range:     3b26c1cd636615cf0d85c13951eaebf099b88bdc..2f16f52763add275892836b396f1f8b9decfd1f7
Branch:           codex/m2-wo0168c-remediation-r1
```

`3b26c1c` was a Claude handoff, not an accepted result. Review the full semantic
center at the candidate, not merely this remediation diff. The broader unaccepted
WO-0168c lineage begins at `344c32b`; use its changed-path inventory and
`work/review/REV-0078/result.md` for the prior finding baseline.

## Authority and read order

1. `AGENTS.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/review/REV-0078/result.md`
4. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
5. `checkpoint_codec.py`, `repository.py`, `schema.py`, and directly relevant tests.

The work order permits only its listed paths and prohibits configured/in-memory
databases, migrations, runtime composition, credentials, network/broker calls, orders,
promotion, and merge to `master`. Changed DDL remains **static-only**.

## DDL identity and locked execution gate

```text
SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
SCHEMA_DDL UTF-8:   178755 bytes
Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
schema.py blob:     074cd47b49747b4fad740d736f7a0becebcfc682
checkpoint blob:    66ab8127c8d3052c1cb49e6103ad238e69a58a55
repository blob:    255e3f6f65aff347fee16dff69cf803f0a600ec0
Approval state:     APPROVED_EXECUTION_DDL_SHA256 is deliberately None
```

`tests/execution_core/approved_schema_digest.py` is the sole approval accessor.
Every installer must call it before `sqlite3.connect` and pass that direct call to
`install_schema`. The source audit in `test_persistence_write_capability.py` has
negative controls for helper, alias, local-value, literal, self-derived, and dynamic
bypasses. The historical gate record's controlling state is in
`35-WO-0168C-HUMAN-GATE-DDL.md`.

The thirteen-query manifest is pinned by per-query SHA-256 in
`test_persistence_runtime_checkpoint_directness.py`. The held EXPLAIN proof uses
explicit repository metadata and rejects unlisted, missing, automatic, or scanning access.

## Required review lenses

1. Re-derive every unresolved REV-0078 P0/P1 obligation at the owning boundary.
2. Trace scope/effect/owner/route/root/coverage/reconciliation bindings and try splice,
   duplicate, stale, absent, and unknown-root counterexamples.
3. Check the acceptance-proof boundary for private reach-through and weakened bindings.
4. Verify a fail-closed human gate, including a future literal without permanent red tests.
5. Assess the 10,000-row planner proof's ability to expose omitted or scanning sources.
6. Check scope, governance accuracy, and any claim that implies DDL execution authority.

## Reproduced author evidence at the exact candidate

```text
CPython: C:\Python314\python.exe (3.14.5)

pytest -q test_persistence_runtime_checkpoint_pure.py
          test_persistence_runtime_checkpoint_directness.py
          test_persistence_write_capability.py
          test_persistence_checkpoint_codec.py
          test_venue_checkpoint_hardening.py
  exit 0 (pytest-cache ACL warning only)

pytest -q test_import_boundary.py
          -k "not grimp_graph_has_no_incumbent_or_external_dependency"
  31 passed (pytest-cache ACL warning only)

The omitted Grimp assertion was invoked directly with cache_dir=None: passed.
ruff check/format --check on all 10 changed Python paths: clean
git diff --check: clean
scope check against active WO: passed
```

`mypy 2.2.0` aborts internally under the only available CPython 3.14 interpreter
before project diagnostics, so typing is **unverified**, not green.

## Deliberately NOT_RUN

No database was opened by this remediation. Do not run these modules before Ameen's
separate approval following an `ACCEPT` result:

```text
tests/execution_core/test_persistence_schema.py
tests/execution_core/test_persistence_repository.py
tests/execution_core/test_persistence_directness.py
tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

The eventual plan is those four modules only, using pytest `tmp_path` file databases
with `-p no:randomly`; no `:memory:` or configured database. This request does not
authorize them.

## Reviewer protocol

Review-only: do not edit implementation files, alter this request, execute SQLite-bearing
tests, create a database, or push. Reproduce only safe pure/static checks. Deposit a
findings-only `result.md` beside this request, bound to the exact candidate commit/tree,
with evidence tagged `reproduced-live`, `static-reasoning`, or `unverified`.
