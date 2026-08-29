# REV-0114 — WO-0168 consolidated changed-DDL static review

Reviewed exact source candidate `b7bf7d2d4f5356a3977fd68cc1dc6cfcdf0dbaae` (tree `3c1eab6ad18c6865e9cbf4e5b33dd343bd3b036`) against parent `bedb1105fc7165da799c3fd025f3291af8bb69cd`. The candidate parent, four changed paths, supplied blobs, and SHA-256 identity pins match the review packet.

No SQLite/database/DDL installation or execution occurred. No `tests_gated/**` suite was collected or executed; held-test source was inspected and syntax-compiled only.

## Findings

No concrete P0, P1, or P2 findings.

Static contract trace and disproof pass found that:

- `acquisition_root_route` references the root-independent exact owner key, retains the exact root foreign key, and guards both one-route-per-owner and rootless/prebound-root behavior in `app/execution_core/persistence/schema.py:710`, `:765`, and `:1252`.
- Both NORMAL admission triggers preserve the active path and add only the flat, `CONSISTENT`, exact-head/version, six-null-coordinate branch at `schema.py:2842` and `:3252`.
- The positive first-activation exception remains constrained to dormant-to-fully-active NORMAL protection, positive `CONSISTENT` controller state, exact live generation, and exact head at `schema.py:3631`; positive transfer/release and quarantined activation remain closed.
- Late-owner insertion advances the controller immediately at `schema.py:3160`; invalidation skips that advance only for the exact retained late owner at `schema.py:3408`.
- Quarantine catch-up is UPDATE-only, requires the exact current head, unchanged coordinates/class, matching invalidation evidence, and no outstanding late owner at `schema.py:3735`.
- The staged held controls are failure-capable for the relevant predicates, including second-route rejection, nonflat/stale dormant admission, transfer/release rejection, ordinary invalidation advance, per-late-owner advance, outstanding-owner catch-up refusal, and stale-head refusal.
- In-memory AST/literal inspection confirms Python syntax, `SCHEMA_DDL` size `190705`, digest `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, flag `False`, 210 complete statements, and inventory `28 tables / 30 indexes / 152 triggers / 0 views`.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: SQLite/database/DDL installation and execution, plus all held-suite execution, were prohibited and did not occur; executable SQLite semantics therefore remain unverified.
