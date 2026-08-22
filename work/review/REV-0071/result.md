---
type: Review Result
rev_id: REV-0071
status: BLOCK
reviewed_commit: 28c2c43deaaa5721c58c1a30d17d149486167de0
reviewed_tree: 5420633c47daece2bb789b2fc85b19c76abeac6e
date: 2026-08-22
---

# REV-0071 — first adversarial result

This result records the findings returned independently by three fresh in-process adversarial
seats for the exact candidate above. The orchestration seat transcribed and deduplicated their
findings without changing their verdict. These seats are not represented as an external
cross-model reviewer; Ameen Mujtabaa explicitly authorized this review arrangement for WO-0166.

## Findings

### P0-1 — revisions can rewrite exact root identity and revise human attestations

`app/execution_core/persistence/schema.py:338` and
`app/execution_core/persistence/schema.py:1402` authenticate only the predecessor fact id/root.
A `TRADE_CORRECT` or `TRADE_BUST` can change order or side and can target a `HUMAN_ATTESTED`
root. That violates exact broker-authoritative predecessor lineage and can move position economics
to a different order/side. Reproduced live with order, side, and authority mutants. Resolve by
requiring the new revision and predecessor to match the complete root scope and both to be
`BROKER_AUTHORITATIVE`.

### P0-2 — valid negative broker truth is rolled back instead of retained and quarantined

`app/execution_core/persistence/schema.py:224` constrains controller aggregate quantity to be
nonnegative. A broker-authoritative correction/bust that makes the signed aggregate negative
therefore aborts the entire fact insert. This hides the broker fact rather than retaining it and
placing the controller in a non-serving integrity state. Reproduced live. Resolve with a signed
aggregate plus sticky explicit quarantine state derived in the same transaction.

### P0-3 — late contradiction can commit while canonical effect authority stays CLOSED

`app/execution_core/persistence/schema.py:607` admits `INVALIDATION` evidence, while
`app/execution_core/persistence/schema.py:1799` only exempts it from the late-evidence refusal.
The evidence can commit without atomically advancing the effect to `INVALIDATED`, leaving
contradictory canonical authority. Reproduced live. Resolve with exact contradiction attribution
and an atomic CLOSED-to-INVALIDATED transition.

### P0-4 — broker owner identity can be rebound across symbol scopes in one profile

`app/execution_core/persistence/schema.py:574` keys venue ownership by `(scope_id,
owner_external)`. The same broker/account profile can therefore bind one external venue identity
to separate effects in separate symbol scopes. Reproduced live. Resolve by making external owner
identity unique at execution-profile scope while retaining exact effect/scope/generation
coordinates.

### P0-5 — active protection stream can transfer while the position is nonflat

`app/execution_core/persistence/schema.py:704` and
`app/execution_core/persistence/schema.py:1878` permit a version-incrementing stream-route update
without checking controller economics. A nonflat scope can therefore transfer protection
authority to another stream. Reproduced live. Resolve with an exact stream/generation route and a
nonflat transfer refusal.

### P1-1 — requested effects are not representable before a fill and omit complete scope

`app/execution_core/persistence/schema.py:484` requires every effect to reference a root fill and
stores only an order identity plus lifecycle fields. A submit request necessarily precedes a fill,
and the row omits request occurrence, mandate, effect kind, side, quantity, economic scope, and
exact generation coordinates. Reasoned from accepted M1 types and reproduced with a rootless
request mutant. Resolve by persisting complete immutable `VenueEffectScope` coordinates without a
required root.

### P1-2 — `INSERT OR REPLACE` can bypass retained-authority guarantees

The immutable tables rely primarily on UPDATE/DELETE triggers. On a reopened default SQLite
connection where recursive triggers are off, `INSERT OR REPLACE` can delete and recreate direct
authority rows without firing the intended delete guard. Reproduced live. Resolve with conflict-
detecting BEFORE INSERT guards on every direct/retained authority identity, independent of
recursive-trigger behavior after installation.

### P1-3 — controller aggregate proof uses a corpus scan

The controller aggregate validation query has no index covering scope plus current root economics
at `app/execution_core/persistence/schema.py:245`. `EXPLAIN QUERY PLAN` reports a scan, violating
the direct-current-proof requirement. Reproduced live. Resolve with a purpose-built current-root
economics index and a failure-capable no-scan query-plan control.

## Verdict

`BLOCK` — P0=5, P1=3. The exact candidate must not close WO-0166 or activate M2-I3.

The reviewers did not verify a configured database, migration, runtime composition, credentials,
broker/network calls, orders, promotion, or merge; none was authorized or exercised.
