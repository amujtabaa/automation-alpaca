# REV-0077 R7 request — WO-0168c final closure preflight

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Candidate commit: `855b3f26abc8d1cb3a6f83eb2dd718754d18e0df`
- Candidate tree: `ec6b961b435a37a9f01dd880970a985caac9ef3e`
- R7 SHA-256: `086b49103ad3480401ea0450a9d8d309a206bd2dec99d0302e75113332ab1c89`
- R6 disposition base: `7cd8098c30a28f1ee294ecf78ecbad4a47e6d469`
- Diff: `7cd8098c30a28f1ee294ecf78ecbad4a47e6d469..855b3f26abc8d1cb3a6f83eb2dd718754d18e0df`

Verify all identities and the recursively closed R6 graph independently.

## Required lenses

1. Verify the ManualFlattenRows alias, actual provenance binding, exact public/private envelope
   coherence, and all retained wire/API/binding authority.
2. Prove runtime capability copy resistance, exact-object registry identity, transaction-generation
   turnover, every L00-L08 exceptional exit, and AST/reference issuer confinement are
   implementation-deterministic and failure-capable.
3. Prove runtime versus setup transaction-gate exception/outcome behavior is unambiguous and
   zero-SQL before failure.
4. Prove every F00-F11 variant has one reachable seam, exact caller-visible outcome/exception,
   receipt presence, transaction calls, and reopen assertion; F10 must remain setup-only and L05
   future-runtime-only.
5. Recheck all recursively retained R5/R6 SQL, DDL, vectors, CAS, capabilities, tests, safety, and
   successor holds for contradictions or regression.
6. Enforce documentation-only scope and the unchanged exact changed-DDL human gate.

Return P0/P1/P2 findings with exact file:line, impact, root resolution, evidence level, verdict,
and unverified items. **READ ONLY:** do not edit, do not write result.md, do not open SQLite, and do
not run SQLite-bearing tests.
