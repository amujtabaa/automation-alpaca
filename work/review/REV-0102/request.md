# REV-0102 request — WO-0168c conditional/callable provenance review

Date: 2026-08-25
Author: Codex implementation seat
Verdict requested: findings only — `BLOCK | ACCEPT-WITH-CHANGES | ACCEPT`.

Perform a fresh-context, failure-capable source review. Re-derive the boundary
from code; do not inherit the author's reasoning, treat listed mutants as a
closed enumeration, repair findings in the review seat, or credit stale test
evidence.

## Frozen source target — verify every identity

- Branch: `codex/m2-wo0168c-remediation-r1`
- Candidate source commit: `501a86425c32ab8b099f897f23334cbbc0df5b36`
- Candidate source tree: `df69b207a0b4c060187deaf7e270ef334c0984aa`
- Direct parent: `84afe6eac1ca711a37fdef329c94ac86d60b2388`
- Direct-parent tree: `cd8e21aa85303c4974b8327ab57262c9f3058c02`
- Exact replacement range: `84afe6ea..501a8642`
- Prior blocked source: `2189d0fe6cf5428188b83255a5ef7725fac61174`
- Prior blocked tree: `a068104c1f9363b6557f8f41b69c980dcb605976`
- Complete static-boundary baseline: `b8709110d7e634b92d1af6262c28332fc25b5b93`
- Complete path-limited range: `b8709110..501a8642`

The source commit changes exactly one path:

- `tests/execution_core/test_persistence_write_capability.py`
  - blob `5a854eec267712e77bb31ce58e3f18dcf6157757`

Relevant inherited frozen blobs at the source target:

- `tests/execution_core/test_protection.py`
  - blob `97d9a42e433b0972dbb4d148a8fd369d3d566e14`
- `app/execution_core/persistence/checkpoint_codec.py`
  - blob `966649dbfc70f496c815b4737453fdd5557c4523`
- `app/execution_core/persistence/schema.py`
  - blob `074cd47b49747b4fad740d736f7a0becebcfc682`
- `tests/execution_core/approved_schema_digest.py`
  - blob `8306ea294075fe76b314724ad6c49e514621f7b1`
- `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
  - blob at source target `71e4fa07e9fe859da29785f21ba56ce1bee25f5d`
- `work/review/REV-0101/result.md`
  - blob `af56de14b842044e67586f158fd6edbd812706df`

The later documentation commit containing this request is outside the frozen
source target. The source commit and tree above are authoritative.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0101/request.md` and `work/review/REV-0101/result.md`
5. `work/review/REV-0100/result.md`
6. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
7. The complete current implementations and controls for
   `_schema_installer_gate_violations`,
   `_repository_sensitive_reexport_violations`, and their scope, binding,
   static-text, callable-observation, capability, and diagnostic helpers.

## Root corrections to disprove

1. Expression execution: skipped Boolean/conditional operands, statement
   branches, context-managed bodies, comprehensions, match cases, and exception
   paths must retain prior protected alternatives. Definitely evaluated tests,
   iterable expressions, subjects, and first Boolean operands must not become
   false conditional unions. Comprehension walrus targets must bind their real
   enclosing Python scope.
2. Callable time: named functions, lambdas, and simple aliases must read parent
   state at every proven direct call. Passive bare/identity observation must not
   create an escape; equality, membership, argument/return/container or
   attribute/subscript flow, outward walrus flow, decorators, and other real
   escapes must conservatively retain every state observable from the escape
   onward. A later definite ordinary state may replace a protected one only
   before every observable call or escape.
3. Package identity: `ImportFrom` submodule aliases must retain exact or package-
   prefix identity for namespace packages and protected helper relays.
4. Standard modules: mutable/import-affecting members such as `sys.path` must
   never be ordinary. Only the exact current read operations may pass; unknown
   governed members fail closed.
5. Controls: removing conditional-alternative propagation must fail the
   approval-module-specific control, not merely produce an unrelated connection
   diagnostic. Adjacent spellings from each semantic family must be assessed.

For any finding, supply a minimal source mutant and the exact resolution path.
Separate a true bypass from a conservative false positive and explain its
material impact.

## Exact locked identities and authority

Source-only AST/literal evaluation, with no project or SQLite import:

- `SCHEMA_DDL` SHA-256:
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `SCHEMA_DDL` UTF-8 bytes: `178755`
- `_SCHEMA_CATALOG_SHA256`:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- R4 SQL-manifest SHA-256:
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
- `APPROVED_EXECUTION_DDL_SHA256 = None`

The changed-DDL HUMAN-GATE is closed. Do not import SQLite, open a connection,
install DDL, run a held suite, or mutate source during this review.

## Author evidence and limits

- Ruff check/format and AST parse — clean
- `mypy app --no-incremental` — success, 95 files
- `lint-imports --no-cache` — 6 kept, 0 broken
- AI Project OS install/version/ledger/PKL/disposition and cumulative scope — pass
- `git diff --check` — clean
- source-only locked identity recomputation — unchanged as above

`pytest` is **NOT_RUN** at this source target. The execution guard could not
prove the import graph SQLite-free; the implementation seat did not route
around it. Earlier pytest evidence belongs to prior source identities.

Held — never run in this review:

- `tests/execution_core/test_persistence_schema.py`
- `tests/execution_core/test_persistence_repository.py`
- `tests/execution_core/test_persistence_directness.py`
- `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`

Also forbidden: any SQLite import/connection, configured or in-memory database,
DDL install/migration, runtime composition, credentials, network/broker call,
order, promotion, history rewrite, or merge to `master`.

## Required result

Return findings only. Each finding must name severity, exact file/line, impact,
minimal reproducer, and root resolution. End with P0/P1/P2 counts and one
verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. State every command not
verified. The DDL HUMAN-GATE may open only after a fresh exact-source result
records `P0=0` and `P1=0`.
