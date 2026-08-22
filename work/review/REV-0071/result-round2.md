---
type: Review Result Addendum
rev_id: REV-0071
status: BLOCK
reviewed_commit: dbd2a086fe861047e5df49cdd65a4ded33c7f758
reviewed_tree: c82dc44bae00aa3df5932991ef38a3839b91f85d
date: 2026-08-22
---

# REV-0071 — second adversarial result

Three fresh read-only seats reviewed the exact remediation candidate. One original seat was stopped
by an unrelated automated classifier without returning a technical result and was replaced; the
replacement reviewed the same exact commit. The findings below preserve the returned verdicts in
deduplicated form. The seats were in-process adversarial agents under Ameen Mujtabaa's explicit
review-process authorization, not an external cross-model reviewer.

## Findings

### P0-1 — direct CLOSED-to-INVALIDATED update bypasses contradiction evidence

`app/execution_core/persistence/schema.py:2052` permits a direct disposition update without an
exact immutable invalidation-evidence row. Reproduced live: a closed effect became INVALIDATED
while its acceptance set had zero INVALIDATION rows. Resolve by requiring an already-persisted
exact contradiction in the transition trigger so the evidence insert remains the sole atomic
route.

### P0-2 — dispatch claims do not revalidate controller currentness

`app/execution_core/persistence/schema.py:658` and
`app/execution_core/persistence/schema.py:2233` do not retain or compare the effect's expected
controller head. Reproduced live: an effect created at head 0 was claimed after a FILL advanced the
controller to head 1. Resolve by retaining the immutable expected head, checking exact controller
identity/head at effect creation, and rechecking it atomically before claim insertion.

### P0-3 / P1-1 — a reopened default connection disables relational authority

`app/execution_core/persistence/schema.py:2605` verifies foreign keys and recursive triggers only
at installation. Reproduced live: a default reopen reported both disabled and admitted unbacked
authority, including a root/fact that advanced controller economics. Resolve with a mandatory
per-open/per-operation verifier for both connection-local pragmas and the exact installed schema
identity; the future repository must call it before every durable read/write operation.

### P1-2 — schema approval metadata is replaceable on a default reopen

`app/execution_core/persistence/schema.py:854` protects `schema_meta` with update/delete triggers
but no conflict insert guard. Reproduced live: `INSERT OR REPLACE` changed the approved digest while
recursive triggers were disabled. Resolve with a BEFORE INSERT retained-identity guard that does
not depend on recursive delete-trigger behavior.

### P1-3 — protection versions are accidentally global across scopes

`app/execution_core/persistence/schema.py:828` makes `version_ordinal` globally unique. Reproduced
live: two valid first protection rows in separate scopes could not both use version 1. Resolve by
making version monotonicity scope-local; the current one-row-per-scope table needs no global
uniqueness.

### P1-4 — sticky controller quarantine does not gate protection authority

`app/execution_core/persistence/schema.py:2418` blocks only nonflat route changes and has no
insert-time integrity guard. Reproduced live: after negative broker truth was busted back to flat,
the sticky quarantine remained but protection transfer succeeded; a newly quarantined controller
also accepted a fresh protection row. Resolve by requiring a CONSISTENT controller for insertion
and for any route transfer, even when signed quantity is zero.

## Verdict

`BLOCK` — combined P0=3, P1=4. Commit `dbd2a086...` must not close WO-0166.

No seat edited or pushed repository files. No configured database, migration, runtime,
credentials, broker/network call, order, promotion, or merge was exercised.
