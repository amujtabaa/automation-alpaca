# REV-0114 correction-only re-review r2

Verdict requested: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`.

This is a fresh, static, correction-only review. Re-derive the result from the exact diff and do not
trust the author diagnosis. Do not open SQLite, create a database, install DDL, execute any held
suite, edit files, or propose unrelated design changes.

## Exact review binding

- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- Base: `1cab8d7c7401112a99e399d1a11ecf4cdb85e8ea`.
- Candidate: `7a41daaadbf7d87bbbc095829aef6b7d8b5762a3`.
- Candidate tree: `789ca0016eb9e5a1300285caf0cdf73483180283`.
- Diff: `1cab8d7c7401112a99e399d1a11ecf4cdb85e8ea..7a41daaadbf7d87bbbc095829aef6b7d8b5762a3`.
- Held-test blob: `515b2bc075ca72f2f9eaf525e66e2d9100a2eb4e`;
  file SHA-256 `df3470cbb846271277c1d1d1b4c1e11d4b96c4314daa260f17c488dfca9c9aca`.
- Failure-evidence blob: `a3399a4c652e838a1d02690c142f8eb2fb3de66a`;
  file SHA-256 `704c28bf490108b36ea4ec8714ac69d234310b57c08d61bab239940e5219d220`.
- DDL remains 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob remains `164de10ad9fef6ce37324840aff59b5b68c07d2a`; the source flag is exact
  boolean `False`.

## Narrow questions

1. Does the observed error prove the negative/quarantined activation was refused by a valid,
   directly applicable controller-authority invariant rather than exposing a DDL defect?
2. Is changing only that test's exact message from the overlapping no-transfer guard to the
   observed current-controller guard contract-faithful, while leaving the positive transfer and
   release tests untouched?
3. Does the added row assertion prove the failed statement left all dormant coordinates,
   checkpoint head, commitment, and version unchanged?
4. Did the candidate avoid DDL, expected-digest, flag, application, or unrelated test drift?
5. Is the execution evidence exact and sufficient to justify one new flag-only branch and one
   genuinely fresh file-database path?

Classify only concrete P0/P1/P2 findings with file and line, impact, and required resolution. Do
not turn overlapping-but-correct error wording or style preferences into a blocker. End with exact
counts and verdict. State explicitly that no database or held-suite execution occurred in review.
