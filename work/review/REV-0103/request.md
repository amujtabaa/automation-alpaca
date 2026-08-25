# REV-0103 request — WO-0168c runtime-provenance source review

Date: 2026-08-25
Author: Codex implementation seat
Verdict requested: findings only — `BLOCK | ACCEPT-WITH-CHANGES | ACCEPT`.

Perform a fresh-context, failure-capable source review. Re-derive the boundary
from the current code. Do not inherit the author's reasoning, treat the listed
mutants as a closed enumeration, repair findings in the review seat, or credit
stale evidence.

## Frozen source target — verify every identity

- Branch: `codex/m2-wo0168c-remediation-r1`
- Candidate source commit: `6dd9396093a58f8e6025521146aa99534a74f01c`
- Candidate source tree: `ce749e17c1a31b141a871783136f53e803b2a62c`
- Direct parent: `d4fca13bb68a470dd1b0b34fa151cad487e9e681`
- Direct-parent tree: `a9b43fcaf32e4e5298e34d01fb424fcaeeff6131`
- Exact replacement range: `d4fca13b..6dd93960`
- Prior blocked source: `501a86425c32ab8b099f897f23334cbbc0df5b36`
- Prior blocked tree: `df69b207a0b4c060187deaf7e270ef334c0984aa`
- Complete static-boundary baseline: `b8709110d7e634b92d1af6262c28332fc25b5b93`
- Complete path-limited range: `b8709110..6dd93960`

The source commit changes exactly one path:

- `tests/execution_core/test_persistence_write_capability.py`
  - blob `11fe7ae71318c8da712ae42568a023f72513e036`

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
  - blob at source target `75e9b9d25cd848b5565b76f7f3474d03370d5523`
- `work/review/REV-0102/result.md`
  - blob `91a728eb457bd6a9446917eaf31adea876217409`

The later documentation commit containing this request is outside the frozen
source target. The source commit and tree above are authoritative.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0102/request.md` and `work/review/REV-0102/result.md`
5. `work/review/REV-0101/result.md` and `work/review/REV-0100/result.md`
6. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
7. The complete current implementations and controls for
   `_schema_installer_gate_violations`,
   `_repository_sensitive_reexport_violations`, and every scope, binding,
   runtime-observation, static-text, capability, prefix, trace, and diagnostic
   helper they call.

## Root replacement to disprove

1. **Execution order.** Match captures, chained comparisons, with-item phases,
   comprehensions, `IfExp`, Boolean alternatives, and augmented assignment must
   preserve every protected state that can reach a read. Source order must not
   stand in for test-before-branch, argument-before-body, or read-before-write
   runtime order.
2. **Callable activation.** Only a proven synchronous direct call may narrow a
   parent state, and it must observe post-argument bindings. Global/nonlocal
   writes cannot erase earlier reads. Returned or nested callables, methods,
   generator/coroutine bodies, and generator expressions must not borrow
   factory or creation time. Passive aliases and truly unobserved local bodies
   must remain precise.
3. **Finite import provenance.** Every literal `IfExp`/Boolean import target and
   its completeness state must survive resolution. Incomplete targets must fail
   closed when a SQLite, schema, approval, or protected-topology member is used,
   and the diagnostic must own the protected provenance rather than pass for an
   unrelated reason.
4. **Governed standard modules and tracing.** `ImportFrom` must use the same
   exact ordinary/fail-closed member classification as attribute access. A
   trace setter may not install a callback that imports, calls, mutates frame
   namespaces, returns another callback, or is rebound while installed. The
   existing finite read-only line counter and exact prior-trace restoration must
   remain accepted.
5. **Namespace packages.** Exact and prefix child identity, prefix maps,
   `getattr`/`__getattribute__`, descriptors/loaders, builtin and bound
   mutation, aliases, and value/map escape must retain provenance whenever a
   protected descendant exists. The same operations on a package with no
   protected descendant must not become a blanket false positive.
6. **Control strength.** Remove or mutate each owning rule mentally and verify
   that its adjacent REV-0103 control fails for the intended diagnostic or
   provenance, not because of another violation. Seek one-step adjacent mutants
   rather than assuming the 43 embedded snippets are complete.

For every finding, provide a minimal source mutant and the exact root resolution
path. Separate a true bypass from a conservative precision issue and explain
its material impact. Do not expand the finite grammar into a claim to evaluate
arbitrary Python metaprogramming.

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

- Ruff check and format check — clean
- Import-free AST parse — module clean; 43/43 REV-0103 embedded snippets parse
- `mypy app --no-incremental` — success, 95 files
- `lint-imports --no-cache` — 6 kept, 0 broken
- AI Project OS install/version/ledger/PKL/disposition and cumulative scope — pass
- exact source diff whitespace gate — clean
- source-only locked-identity recomputation — unchanged as above

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
