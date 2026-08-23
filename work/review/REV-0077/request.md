# REV-0077 R5 request — WO-0168c final non-serving checkpoint preflight

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Candidate commit: `2a096f100644191764b9d12403f3eb5fee823e39`
- Candidate tree: `c62085163e03b4206b180ce6da1cb5d346eead71`
- R5 contract SHA-256: `ffa9fe8c794dbee0fc84d5bcf426eb071d03843cee30bffda3b584b05e739d39`
- R5 SQL manifest SHA-256: `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525`
- R4 disposition base: `7ebc50dd34ba77d7de3adfd01806846e5ed1739d`
- Review diff: `7ebc50dd34ba77d7de3adfd01806846e5ed1739d..2a096f100644191764b9d12403f3eb5fee823e39`

Verify every identity and every full commit:path import independently.

## Exact target

- `work/queue/M2-EXECUTION-2026-08-21/15-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R5.md`
- `work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md`
- only the exact immutable imports named by R5 section 1;
- current source/schema only to re-derive feasibility and truthfulness.

R5 claims to resolve all ten reconciled R4 findings. It remains documentation-only and
non-serving.

## Required independent lenses

1. Closed authority: verify every commit:path hash, imported/excluded row, venue/authority winner,
   and absence of hidden transitive authority.
2. Byte/type closure: verify all public/private fields and annotations, source-owner preimage
   re-derivation, registry identity, recursive atom/scalar/record/sequence/absence bindings, exact
   storage-class mapping, and comprehensive literal known-answer/mutant obligations.
3. Capability/transaction boundary: verify production runtime versus fresh-fixture setup authority,
   exact connection identity, stable transaction requirement, outcomes, and substitution tests.
4. SQL semantics: re-derive Q1 absence/profile distinction; Q2 present/missing optional-null rules;
   Q3a/Q3b and later CTE parity; exact partial-index predicate usability; combined cap; Q4-Q9
   selected-parent admission before sort; all vectors, joins, query/load counts, CAS parameters,
   and plan assertions.
5. Fault proof: verify F00-F10 covers every payload/CAS/reread/receipt/commit boundary and that
   close/reopen assertions detect orphan or mixed state.
6. Test critic: every material claim needs a stable named test and reachable source mutant; reject
   broad exception assertions or a test that can pass without the decisive path.
7. Safety/scope: no serving constructor, second engine, source/test authority, SQLite, changed-DDL
   execution, configured/in-memory database, migration, runtime composition, credentials,
   network/broker/order action, promotion, or merge is authorized.

Return P0/P1/P2 findings with exact file:line, impact, root resolution, evidence level, verdict,
and unverified items. Do not infer missing details. **READ ONLY:** do not edit files, do not write
`result.md`, and do not open SQLite or run a SQLite-bearing test.
