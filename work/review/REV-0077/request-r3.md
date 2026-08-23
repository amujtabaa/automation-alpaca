# REV-0077 R3 request — WO-0168c non-serving checkpoint preflight

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- R2 disposition parent: `a0e966d`
- R3 candidate: `280a675cedf19dd32aa4f0408749ef258b7d42df`
- R3 tree: `6fe2864bd41ba295d7fab0bd0fd257aa0cf185aa`
- R3 contract SHA-256: `ee31dda649c700438dc55642a91daee42dc6b2eac8634119ae159aea519fa3cb`
- R3 SQL manifest SHA-256: `f1cae0c9af8a6b906497864e03311158ecdfae2ff37a7f7cd23c59c542bbd069`

Verify independently.

## Authoritative target

- `work/queue/M2-EXECUTION-2026-08-21/11-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R3.md`
- `work/queue/M2-EXECUTION-2026-08-21/12-WO-0168C-R3-SQL-MANIFEST.md`
- active WO-0168c and R2 result/disposition

Current source/schema and accepted ADRs win. Earlier contracts are evidence only except the exact
R2 sections retained by R3.

## Required hostile checks

1. Try copied/recomputed binding, weak-registry cleanup/ID reuse, cross-connection proof,
   post-transaction proof, loaded-envelope store, and private-carrier forgery.
2. Verify the exact 10-member outer row, integer scope ID, 21-member execution row, 32-member
   protection row, complete bootstrap/proof/cursor/summary, authority descriptors, and acquisition
   rows against current source.
3. Expand every `V(alias,VECTOR)` mechanically and review all twelve SQL statements. Check tuple
   widths/null vectors, parent/complement rules, effect counters, duplicate late owners, closure
   head, root/fact optionality, stream/cursor optionality, caps, query count, and claimed plans.
4. Verify target head/version are wholly repository-derived and agree with every selected
   controller/protection coordinate; verify global version uniqueness is removed safely.
5. Verify store-time full reselection plus predecessor CAS defeats stale/spliced proofs and that
   the narrowed transaction claim is honest pending WO-0168b.
6. Verify database-complete and payload-owned reference lists are disjoint, complete, and do not
   conceal a serving or omitted-history claim.
7. Verify exact API/export/outcome/binding/test surfaces remain implementable without invention
   and are proportionate.

READ ONLY. Do not edit, run SQLite, run SQLite-bearing tests, commit, or push. Return exact P0/P1/P2
findings with file:line, impact, root resolution, evidence level, verdict, and unverified items. Do
not write a result file.
