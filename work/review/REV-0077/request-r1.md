# REV-0077 R1 request — WO-0168c non-serving checkpoint preflight

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Supersession base: `0efd9be94d6ecc1238094515fba5accd0e892606`
- R0 disposition parent: `341a8815049422684562c8cb99ba1ca9bfdf6da0`
- R1 candidate: `6faf61aa9419234ee953ab881d1bef550699400c`
- R1 tree: `0f27c7cf77b7f5f437fb6bd7a5db9f3cbc37e90a`
- R1 contract SHA-256: `175c873cd9300d875319da16bafc8a3ba90aae80ec5101bd972aa45c74fe57fd`
- Review diff: `341a8815049422684562c8cb99ba1ca9bfdf6da0..6faf61aa9419234ee953ab881d1bef550699400c`

Verify all identities independently.

## Review target and authority

Review the exact documentation-only contract and active work order:

- `work/queue/M2-EXECUTION-2026-08-21/09-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R1.md`
- `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`

Contract 08 and WO-0168h are superseded evidence only. Read `result-r0.md` and
`disposition-r0.md`, accepted ADR-020/021/022/023 authority, current persistence
records/repository/checkpoint codec/schema, and the closed row definitions in contract 07 only as
needed to re-derive this boundary. Current code wins over prose about existing members.

## Required adversarial lenses

1. Does any byte string, proof object, repository return, or public constructor mint an existing
   serving owner/proof, or is every WO-0168c result structurally inert?
2. Are pre-persistence selection, payload insertion, kernel-head advance, post-persistence load,
   and final head recheck acyclic, transactionally coherent, and free of stale-proof acceptance?
3. Is the database-discoverable versus payload-owned provenance split complete and honest? Can
   owner-only semantics be authenticated at issuance without falsely claiming database set
   completeness on load?
4. Are all outer, venue, authority, acquisition, execution, protection, bootstrap, and cursor
   arrays exact enough for one implementation? Flag any imported row range that remains
   contradictory, ambiguous, or unable to preserve accepted bytes.
5. Do Q1-Q7 have exact predicates, join roots, count bounds, and realistic indexes? Re-derive the
   two proposed static indexes from the current schema without running SQLite.
6. Does the contract avoid claiming that bounded payload commitments reproduce existing
   history-shaped serving commitments? Are all new domains and dependency directions unambiguous?
7. Are APIs, construction rights, transaction ownership, exports, allowed paths, DDL gate, and
   test/mutation obligations exact and proportionate?
8. Are WO-0169's held serving obligations sufficient to prevent this candidate from being used as
   a disguised runtime restore path or from bypassing omitted-history replay/nonmembership?

Treat the R1 contract as an indivisible preflight. Do not infer missing fields, predicates, query
semantics, or constructor inputs. Findings must identify file:line, impact, root resolution, and
evidence level. End with P0/P1/P2 counts, verdict, and anything unverified.

READ ONLY. Do not edit files. Do not run SQLite or any SQLite-bearing test. Do not write or amend
any `result*.md` in this parallel round; return findings to the orchestrator for reconciliation.
