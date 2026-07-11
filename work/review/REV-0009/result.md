# REV-0009 result — Store implementations + dual-store parity

Reviewed at frozen base `b60010148f3201a9f8c62ee0bda45371d5c964f4` using Python 3.12.3. I treated the packet as findings-only and did not edit production code.

| Finding | Severity | Evidence | Why it matters | Required action |
|---|---:|---|---|---|
| Confirmed known item REV-0006-F-001: sqlite `flatten_position` applies one logical flatten across multiple transactions while memory applies it atomically. | Known P1, not re-filed | Memory wraps supersede/create/approve/dispatch in one `_atomic()` call, while sqlite uses separate `_tx()` blocks for supersede cancel, supersede expire, insert+approve, and dispatch helper. | This is the known dual-store crash-atomicity gap: a hard crash between sqlite transactions can strand an approved/no-order sell intent, violating the dual-store parity/atomicity invariant. | Keep the queued fix: make sqlite apply the whole flatten plan in one transaction and keep parity tests. |

## Additional verification notes

- Apart from the known flatten atomicity item, the sampled fill append, order transition, and claim-order apply paths co-write row changes plus events inside a single store lock/transaction boundary in both stores.
- I did not find a fresh store-implementation finding beyond the known sqlite flatten split-transaction issue during this pass.

## Verdict

ACCEPT-WITH-CHANGES

Could not perform exhaustive crash-injection against sqlite; this review used code inspection plus targeted parity reasoning.
