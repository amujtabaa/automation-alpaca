# REV-0114 correction-only static review — result-r1

## Findings

None.

## Evidence

- Exact branch, commit, tree, and parent verified:
  `codex/m2-wo0168-atomic-uow-r1`,
  `9a79f5821d5c74bf4b8650868e91e36ca18d4f95`,
  `bb0c8c0ce07cc5eeb7c4daf8b50927423f6e5476`,
  parent `26f19230891710224e908cc59ac9b7b26dcbc213`.
- Exact corrected test blobs and SHA-256 values match the request.
- Cross-root assertion now requires the owning guard message and remains failure-capable.
- Serial late-owner setup begins at `(2, 3)`; three late-owner insertions advance once each, while matching invalidations do not advance again. Final `(5, 6)` is consistent.
- Dormant-position fixture uses unused `fact_id=1`, producing the required first global fact ordinal without changing tested semantics.
- Both corrected files compile; Ruff check, format check, and `git diff --check` pass.
- No application/schema file changed. Schema blob remains `164de10ad9fef6ce37324840aff59b5b68c07d2a`; DDL digest and exact `False` execution flag remain unchanged.

No SQLite import or invocation, database connection, DDL installation, or `tests_gated` collection/execution occurred.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: candidate held-suite execution; prohibited by review scope
