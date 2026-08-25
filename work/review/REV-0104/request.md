# REV-0104 request — WO-0168c root-remediation exact-source review

Date: 2026-08-25
Review mode: fresh-context, findings only, source/static only

## Assignment

Independently re-derive whether the replacement finite source gates close every
REV-0103 P0/P1 root without a bypass, false safety claim, route-specific waiver,
or unacceptable precision regression. Do not trust author evidence or prior
review reasoning. Attempt to disprove the candidate with new minimal source
mutants and ordinary controls.

Do not edit source or `request.md`. The independent review result belongs in
`work/review/REV-0104/result.md` only after the review seats reconcile their
findings against the exact frozen source identity below.

## Frozen target — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168c-remediation-r1`
- Candidate source commit: `cdf17715839d7d109dbf555cb4064488ae0beefe`
- Candidate tree: `d6304912ca316552272d6379936cc6a1d661ade8`
- Candidate parent: `e992136333573f2490ab5ac821c16402b8896176`
- REV-0103 source baseline: `6dd9396093a58f8e6025521146aa99534a74f01c`
- Changed source path: `tests/execution_core/test_persistence_write_capability.py`
- Candidate source blob: `5b1367e08e723a9edac5b02f9b7e799b7d68602f`
- Frozen schema blob: `074cd47b49747b4fad740d736f7a0becebcfc682`
- Frozen approval-file blob: `8306ea294075fe76b314724ad6c49e514621f7b1`
- Frozen R4-manifest blob: `1f3bb9dd2cdd13e2f2c7b5439e0c8f98a68eb4da`

The source delta under review is the one-path diff from REV-0103 source baseline
to the candidate source commit. Intervening commits before the candidate are
review/governance records, not source changes.

## Read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`, especially
   the REV-0103 disposition and REV-0104 candidate amendments.
3. `work/review/REV-0103/request.md` and `result.md`.
4. The complete current implementations of
   `_schema_installer_gate_violations` and
   `_repository_sensitive_reexport_violations` in the frozen source blob.
5. Every REV-0104 control plus adjacent REV-0102/REV-0103 controls.
6. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`.

## Required review lenses

1. **Runtime phase order.** Verify RHS-before-target assignment evaluation for
   `Assign` and valued `AnnAssign`, including chained/destructured attribute and
   subscript targets, while preserving correct augmented-assignment behavior.
2. **Callable activation.** Attempt local function/lambda/factory activation
   through `globals()`/`vars()`, direct and aliased subscript/getter forms,
   `dict`/`operator` helpers, static reflection, returns, closures, and deferred
   objects. Discarded generators, generator expressions, and coroutines must
   remain unobserved until finite activation or real escape.
3. **Cross-file carriers.** Verify cycle-safe transitive provenance through
   child modules, package prefixes/maps, governed standard modules, member
   aliases, callable returns, maps, reflection, mutation, and escape. Ordinary
   package metadata and static ordinary members must remain ordinary.
4. **Trace safety.** Verify callback identity cannot self-replace through local,
   global, nonlocal, closure, namespace, or return routes. Require exact direct
   `gettrace` capture, immutable bounded callback, immediate protected `try`, and
   exact restoration in `finally`; independently kill import, call, escape,
   missing/late/conditional/mismatched restoration branches.
5. **Dynamic provenance and mutation.** Verify exact-or-prefix dynamic import
   classification, Boolean/conditional alternative union, incomplete-target
   ownership, and direct/map/alias/getter mutation diagnostics.
6. **Test critic and boundedness.** Confirm controls fail for the intended
   missing rules, accepted controls are semantically plausible, caches/fixpoints
   cannot hide a protected route, and the exact 49-file inventories terminate
   with zero violations without a recursion-limit or filename waiver.

## Locked changed-DDL identities

Computed by AST/literal extraction only, without importing project modules:

- `SCHEMA_DDL` SHA-256:
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `SCHEMA_DDL` UTF-8 bytes: `178755`
- `_SCHEMA_CATALOG_SHA256`:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- R4 SQL-manifest SHA-256:
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
- `APPROVED_EXECUTION_DDL_SHA256 = None`

## Author evidence and limits

- 27 source-only historical/current controls — pass in 0.723 seconds.
- Recursive topology inventory — 49 files, 0 violations, 30.132 seconds.
- Recursive primary inventory — 49 files, 0 violations, 121.581 seconds.
- Ruff check and format check — pass.
- Import-free AST parse — module plus 433 embedded snippets pass.
- `mypy app --no-incremental --no-sqlite-cache` — success, 95 files.
- `lint-imports --no-cache` — 6 kept, 0 broken.
- AI Project OS install/version/ledger/PKL/disposition and cumulative scope — pass.
- `git diff --check` — clean.

An earlier mypy attempt inherited a SQLite cache and failed before opening it;
the successful command disabled that cache. No cache DB was opened or created.

`pytest` is **NOT_RUN** at this source target. Earlier test evidence belongs to
older source identities and must not be credited to this candidate.

## Prohibited during review

Do not run pytest or any held suite. Do not import project modules or SQLite,
open any database or connection, install/execute DDL, migrate data, compose the
runtime, load credentials, use network/broker APIs, place orders, promote,
rewrite history, or merge to `master`. Do not mutate source. Source-only AST
extraction and minimal in-memory strings passed to the two scanner functions are
permitted.

The four held suites are:

- `tests/execution_core/test_persistence_schema.py`
- `tests/execution_core/test_persistence_repository.py`
- `tests/execution_core/test_persistence_directness.py`
- `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`

## Required result

Return findings only. Each finding must include severity, exact file/line,
impact, minimal source reproducer, and root resolution. Distinguish reproduced
source-only findings from reasoned-only concerns. End with P0/P1/P2 counts and
one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. State everything not
verified. The DDL HUMAN-GATE may open only after a fresh exact-source result
records `P0=0` and `P1=0`.
