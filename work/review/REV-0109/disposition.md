# REV-0109 disposition — gate remains closed

Date: 2026-08-28

Disposition owner: Codex implementation/orchestrator seat

Reviewer result SHA-256:
`d34901ef25ae8b25f31e71f7c3c89ebdf6fc9dd5a78d0eb98d69574fb57dc732`

## Result

`BLOCK`, P0=0, P1=3, P2=0. The reviewer-owned `result.md` is preserved unchanged. No SQLite,
database, DDL, held suite, migration, broker, network, credential, order, or later work-order
activity occurred.

## Independent disposition of each finding

1. **P1 market-stream route splice — ACCEPTED, reproduced statically.** `durable_input` separately
   validates its application/scope/acquisition/source coordinates but references
   `market_stream_authority` by `stream_generation_id` alone. A valid route-A input can therefore
   name route B's existing stream. No insert trigger closes the relation and no held negative test
   covers it. Resolution requires a database-native exact-route binding and one-coordinate-at-a-
   time rejection tests. This changes DDL bytes and remains unauthorized.
2. **P1 outbox/input scope splice — ACCEPTED, reproduced statically.** `broker_outbox` binds one
   foreign key to a durable input identity and a separate foreign key to an effect's exact route,
   but does not require the two referenced rows to share execution profile/scope or, for
   `CLAIM_ACQUISITION_EFFECT`, acquisition generation. Repository validation binds the outbox
   snapshot to effect/claim rows but does not load and cross-bind the durable input. Resolution
   requires a fail-closed same-input-route database constraint/trigger plus cross-scope and cross-
   acquisition rejection tests. This changes DDL bytes and remains unauthorized.
3. **P1 attempt-two identity lifecycle — ACCEPTED.** The request permitted a test edit before the
   second run without requiring a new clean, published, independently reviewed identity. The
   successor plan will permit attempt two only after an environmental/interruption failure with
   zero tracked changes. Any test or fixture edit stops and returns through a new reviewed packet.

## Root-level next step requiring human authority

Do not unlock or execute the current candidate. A bounded remediation should:

- add the two exact database-owned route bindings and failure-capable held tests;
- correct the two-attempt lifecycle as described above;
- address the catalog-identity lifecycle created by any DDL change without reviving a self-
  approving or multi-round gate; the preferred small design is to store the post-install catalog
  digest in the immutable `schema_meta` row as integrity evidence while retaining the separately
  human-approved DDL digest and authorization flag as the only execution authority;
- freeze the resulting DDL bytes/digest, schema blob, manifest implications, tests, and command;
- obtain one fresh static exact-head review, with at most one remediation re-review; and
- return the exact candidate to Ameen before any DDL installation or database creation.

Until Ameen authorizes that static remediation, the current DDL remains 178755 UTF-8 bytes at
SHA-256 `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`, the application flag
remains `False`, and REV-0109 grants no execution authority.
