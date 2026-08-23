# REV-0075 R17 — final contextual fixture grammar review

Findings only. Do not edit/create files, commit, push, access SQLite, create a database, or invoke
runtime composition, credentials, network, broker, or order code.

## Exact identities — verify, do not trust

- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Rejected R16 source: `7fe2e9d5d215dea49676337dd1069692564527ae`, tree
  `2c8043bd2cc8eed25421e9d3f49c70b808392ebd`
- Exact R17 correction: `7f927d6a15daea0ff53a5008837fef816fcf90ec`, tree
  `a6e2e3bcb2be9b1823c0906fca3bfd7aa1242392`
- Diff: `7fe2e9d5d215dea49676337dd1069692564527ae..7f927d6a15daea0ff53a5008837fef816fcf90ec`

Read `AGENTS.md`, `CLAUDE.md`, active WO-0168a, R13/R13-R1, this request, and
`result-r16.md`. Re-derive everything.

## Required adversarial checks

1. Reproduce the exact R16 `for...else`, parent-package repository, aliased `sys.modules`, and
   counterfeit optional `_apply_mutator` mutants; all must now fail.
2. Try nearby ordinary variants: parent `app` imports, aliased namespace builtins, nested loops,
   loop stores/uses outside the body, and imported/assigned protected helper names.
3. Confirm canonical fixture forms remain green and every present/called `_apply_mutator` is exact.
4. Assess whether the correction is a bounded contextual whitelist rather than a data-flow engine.
5. Confirm no production code, DDL, schema bytes, SQLite, runtime capability, or safety surface
   changed.

Permitted evidence is the four-file pure command in `request-r16.md`; author result is 79 passed,
with Ruff and `git diff --check` green. No SQLite-bearing test ran.

Return P0/P1/P2 findings with concrete mechanism, impact, smallest complete correction, evidence
tag, final `BLOCK` / `ACCEPT-WITH-CHANGES` / `ACCEPT`, counts, and unverified items. This review
authorizes no implementation, DDL execution, SQLite activity, external I/O, promotion, or merge.
