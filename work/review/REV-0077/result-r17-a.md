# REV-0077 R17-A independent preflight review

Reviewed exact commit `85ddd1a3c438d73e3991436a562ae81ff31263cf`, tree
`b8da99dc2ccbea04c03cd8c344606ebcd40c9347`, and R17 SHA-256
`fae546a497033c772b9f8a7ab0a3b496963f54aa7d200f5dd44dd741b435d503`.

R17 root-resolves all six R16 P1 findings: it retains unresolved retired acquisition state in the
dormant branch, defines both dormant source-projection owner slots, closes active/dormant
execution-protection cross-binding, separates all three authority-superset controls, and deletes
the unauthenticated source-rank design. The following new P1 remains.

### [P1] The dormant acquisition collections have no exact payload wire grammar

- Location: `work/queue/M2-EXECUTION-2026-08-21/28-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R17.md:48`
- Requirement: WO-0168c requires the preflight to freeze exact non-serving wire types, arrays,
  tags, ordering, and commitments, and implementation must not invent authority or encoding rules
  absent from the recursively incorporated contract.
- Evidence: `static-reasoning` — R17 introduces `UnresolvedGenerationCurrentRows`,
  `UnresolvedMarketStreamRows`, and `UnresolvedMarketCursorRows`, then commits “canonical
  generation/current/stream/cursor collections,” but never defines their wrapper tags, row tags,
  member order, scalar encoding, or collection commitment preimages. The referenced R1 acquisition
  grammar instead defines owner-derived 12-member `Generation` and three-member
  `MarketStreamRoute` rows; those require semantic owner fields and commitments unavailable by
  construction in the no-owner dormant branch
  (`work/queue/M2-EXECUTION-2026-08-21/09-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R1.md:208`). R5
  defines database-record storage vectors and domain-separated `COMMIT` bindings for the selection
  proof, not canonical payload arrays or wrappers, and supplies no database lineage-record sequence
  (`work/queue/M2-EXECUTION-2026-08-21/15-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R5.md:153`). Current
  source likewise exposes exact selected record dataclasses and binding helpers but no dormant
  payload grammar (`app/execution_core/persistence/records.py:658`, `:665`). Consequently an
  implementation must choose among non-equivalent encodings—raw storage rows, R1 owner rows,
  per-record binding digests, or a newly invented tagged array—to construct the R17 row and its
  three commitments.
- Impact: The dormant candidate is not byte-implementable from current source and incorporated
  authority without inventing a wire contract. Independent implementations can emit different
  canonical bytes while each appears to satisfy R17, and exact known-answer, wrong-tag,
  wrong-member-order, and commitment-preimage controls cannot be authored failure-capably.
- Resolution: Freeze every dormant collection wrapper and child row as an exact tagged array with
  member count/order and scalar encodings; state whether each member is a raw selected database
  record or an owner-derived projection; define exact registry/lineage commitment preimages over
  those wrappers; and add literal known answers plus independent tag/order/field/commitment
  mutants. Preserve the existing proof order and direct selected-key lookup rule.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: No SQLite, database, DDL, schema, runtime-composition, or executable test was run. R17
is documentation-only; the finding and R16 remediation assessment are static derivations from the
exact candidate, its recursive authority, and current source.
