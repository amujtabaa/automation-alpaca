# REV-0077 R4 request — WO-0168c non-serving checkpoint preflight

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Candidate commit: `8d70951d69f034da98bf6f13ce0dd42eff336b48`
- Candidate tree: `67fc56138dfc1104d8ca42a2e4e8aa703e0f547c`
- R4 contract SHA-256: `5366ef50830b2bd83b9948e9dd75c85003aa971084fc7daaaa18728df81b7f43`
- R4 SQL manifest SHA-256: `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
- R3 disposition base: `05e5204d4b90f3ed67345f62f59438485921c137`
- Review diff: `05e5204d4b90f3ed67345f62f59438485921c137..8d70951d69f034da98bf6f13ce0dd42eff336b48`

Verify every identity independently.

## Exact target

- `work/queue/M2-EXECUTION-2026-08-21/13-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R4.md`
- `work/queue/M2-EXECUTION-2026-08-21/14-WO-0168C-R4-SQL-MANIFEST.md`
- the four exact hash-bound predecessor imports named by R4 section 1;
- current source/schema only to verify that imported rows, flattened vectors, indexes, types, and
  proposed implementation surfaces are truthful.

R4 is intended to resolve every reconciled R3 finding in `result-r3.md`. It is documentation-only
and remains non-serving.

## Required independent lenses

1. Authority closure: prove no imported clause relies on an unnamed/transitive/superseded field,
   API, selection rule, or serving claim; verify hashes and precedence.
2. Wire and API completeness: verify exact outer/component rows, public/private record fields,
   signatures, exports, outcomes, exceptions, CAS SQL, and successor ownership.
3. Authenticity: verify weak identity registration cannot be copied/recomputed/reused; verify
   every binding domain, scalar/optional/list/record framing, field order, and known-answer/mutant
   obligation is implementation-deterministic.
4. Selection integrity: verify Q2 cannot omit incomplete scopes; Q3a/Q3b reject over-cap before a
   combined CTE; the required caller-owned transaction closes cross-query races; all later
   completeness/absence/counter rules remain sound.
5. SQL/directness: verify each exact query and storage vector against current schema/repository;
   verify Q4a's bounded temporary sort and reachable `NOT INDEXED` negative control; identify any
   impossible `INDEXED BY`, plan assertion, count, null vector, or parameter claim.
6. Test critic: each important contract clause must have a stable named test and a reachable
   source mutant. Reject broad exception assertions or tests that can pass without exercising the
   decisive path.
7. Scope/safety: no source authority, changed-DDL execution, SQLite test, serving constructor,
   second engine, runtime composition, configured/in-memory database, migration, credentials,
   network/broker/order action, promotion, or merge is authorized.

Return P0/P1/P2 findings with exact file:line, impact, root resolution, evidence level, verdict,
and anything unverified. Do not infer missing details. **READ ONLY:** do not edit any file, do not
write `result.md`, and do not open SQLite or run a SQLite-bearing test.

