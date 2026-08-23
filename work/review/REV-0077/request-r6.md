# REV-0077 R6 request — WO-0168c closure preflight

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Candidate commit: `2c6c680742aec2ed04465d1818887d591836e797`
- Candidate tree: `6cb65e08516b7e9749a260579925fad4bded97b7`
- R6 SHA-256: `3dd93f8376516003bcb169195f2457395435741aa7a2f628ab644d128736ce0e`
- R5 disposition base: `ef10b6b5ffc13797b0334c87c3c9f742a29ce017`
- Diff: `ef10b6b5ffc13797b0334c87c3c9f742a29ce017..2c6c680742aec2ed04465d1818887d591836e797`

Verify the candidate and every recursively named full commit:path/hash independently.

## Target and lenses

Read R6, its exact R5/R4 clauses, R5's six exact imports, and only current source needed to verify
feasibility. R6 claims to close all eight R5 findings.

1. Prove the authority graph and authority-wire children are recursively closed with unambiguous
   precedence.
2. Prove projected/loaded formulas bind every public/private field with exact row/container framing
   and canonical-payload coherence.
3. Verify the 22-vector inventory and every BLOB classification.
4. Verify the held runtime lease actually prevents T1 tokens in T2 and has complete issuance,
   invalidation, exception, static-import, and future WO-0168b tests without falsely claiming
   current production use.
5. Verify W00a-c and F00-F11 have reachable decisive controls, exact outcome/call/reopen evidence,
   and no observationally equivalent mutant.
6. Recheck that retained R5 SQL/API/binding/CAS/test surfaces remain exact and safe.
7. Enforce scope: documentation only; no SQLite, DDL execution, source/test edit, serving authority,
   runtime composition, configured/in-memory DB, migration, credentials, network/broker/orders,
   promotion, or merge.

Return P0/P1/P2 findings with exact file:line, impact, root resolution, evidence level, verdict,
and unverified items. **READ ONLY:** do not edit, do not write result.md, do not open SQLite, and do
not run SQLite-bearing tests.
