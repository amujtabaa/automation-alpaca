# REV-0077 R2 request — WO-0168c non-serving checkpoint preflight

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- R1 disposition parent: `156639473ee6d0773c765ab1f04d1f1de58dc633`
- R2 candidate: `bdacfb2fcf2f22e202c8220874722e8e71f8ec92`
- R2 tree: `812cce81c1d9259f1446c06968a52b4103b27cba`
- R2 contract SHA-256: `df1d37b92de692909e17ce6f757c4d4187b2a538b5f8a3612996d01dba8e586b`
- Review diff: `156639473ee6d0773c765ab1f04d1f1de58dc633..bdacfb2fcf2f22e202c8220874722e8e71f8ec92`

Verify every identity independently.

## Target

- `work/queue/M2-EXECUTION-2026-08-21/10-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R2.md`
- `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
- `work/review/REV-0077/result-r1.md` and `disposition-r1.md`

Contracts 07-09 are superseded evidence except for the explicitly retained R1 sections. Current
code/schema and accepted ADRs win. Review the whole R2 boundary; do not assume an R1 finding is
closed merely because R2 says so.

## Required lenses

1. Prove or disprove that every projected/loaded value is structurally inert and that
   `object.__new__`/`object.__setattr__`, loaded-envelope replay, or a public payload record cannot
   bypass selection/owner authenticity.
2. Verify every retained/imported row against current source, especially execution/protection,
   bootstrap transition proof/cursor/summary, authority descriptors/slots, and source orders.
3. Re-derive the selected-generation and qualifying-effect CTEs. Look for historical scans,
   omitted CLOSED+late state, incorrect current counters, missing roots/routes/facts/streams,
   duplicate/absence bugs, unbounded joins, or indexes that cannot support the claimed plans.
4. Verify the predecessor-absent/found CAS, payload-first reverse edge, outcome classifications,
   caller rollback requirement, and final load head/profile recheck are non-circular and stale-safe.
5. Determine whether the named query manifest and record vectors are sufficiently exact for one
   implementation without invented columns, joins, predicates, cardinalities, or absence rules.
6. Verify canonical octets/composite frames, all enum owner tags, size boundaries, ordered tuples,
   commitments, exact APIs/exports/bindings, and finite test mutants.
7. Confirm WO-0169—not WO-0168c—owns every serving constructor, omitted-history proof, owner lock,
   bounded behavioral-commitment cutover, and startup eligibility.
8. Check proportionality: flag unnecessary types, indexes, queries, public exports, or duplicated
   authority, as well as any missing essential surface.

READ ONLY. Do not edit files, run SQLite, or run SQLite-bearing tests. Return findings with exact
file:line, P0/P1/P2, impact, root resolution, evidence level, verdict, and unverified items. Do not
write `result*.md`; return the independent report to the orchestrator.
