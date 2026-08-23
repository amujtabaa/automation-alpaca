# REV-0077 R14 independent preflight result A

Candidate: `135b5cde9f3b0d363c007251c3cce78298473e81`

Tree: `d11976d780f72d707cefe9556d16653f79d83529`

Contract SHA-256: `c839b072f9c5a4e106337834dc0f675458d0453daf8402c5d37d28ae18597d9f`

### [P1] Manual-flatten state is not always reachable from a selected effect authorization

- Location: `work/queue/M2-EXECUTION-2026-08-21/25-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R14.md:33`
- Requirement: R14 lines 14-16 require projection to accept every authentic bounded state selected by the repository contract. The incorporated R2 authority grammar includes `ManualFlattenRows`, and R3 classifies authority manual history as payload-owned semantics.
- Evidence (`static-reasoning`): R14 makes selected effect authorizations the only route to manual rows. At the exact candidate, `app/execution_core/authority.py:9553` inserts `_ManualFlatten` after `_authority_begin_symbol_flatten`; that helper at `app/execution_core/venue.py:14478` can validly return an empty `cancel_ids` tuple when there are no cancellable BUY legs. The resulting authentic `WAITING` manual has no effect authorization from which its flatten ID can be discovered. The same loss can occur after all of a manual's cancel effects become terminal and leave the repository's qualifying-effect selection. The selected scope exists, but R14 expressly forbids using its `_manual_flatten_by_scope` current index as the discovery route.
- Impact: A valid, bounded authority state required by the frozen wire grammar is integrity-refused instead of checkpointed. A crash in that state loses the only checkpoint representation of the in-progress manual flatten, so the owner-projection route is incomplete.
- Resolution: Admit one closed selected-scope route through `_manual_flatten_by_scope` to `_manual_by_id` (with exact scope/current-map equality and no-extra-row checks), or provide an equivalent named bounded current-manual materializer. Add authentic zero-cancel `WAITING` and terminal-cancel `READY` controls that project successfully and fail when the row/index is missing, duplicated, or spliced.

### [P1] The pre-filter sequence cap makes unrelated history a checkpoint dependency

- Location: `work/queue/M2-EXECUTION-2026-08-21/25-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R14.md:19`
- Requirement: R14 lines 14 and 29 require every authentic bounded selected state to remain projectable while unrelated terminal history stays out of the checkpoint. Incorporated R2 lines 43-47 cap canonical rows per selected wire family, and lines 206-209 restrict source order to the selected effect/owner sets. ADR-022 lines 160-161 require terminal order history not to grow the operational checkpoint with campaign length.
- Evidence (`static-reasoning`): R14 lines 25-26 require checking the retained count of a named owner sequence before filtering it. The exact source materializers at `app/execution_core/venue.py:4286-4403` walk whole `_effect_order`, `_claim_order`, `_owner_order`, and append-only coverage/reconciliation ledgers. Therefore a book with 65,536 unrelated closed historical entries and one selected unresolved effect has a repository-selected family size of one, but R14 refuses before filtering because the retained audit sequence exceeds 65,535. Below that threshold, projection still walks unrelated history to discover a small selected set. R14's listed controls contain no noise-invariance case proving that unrelated terminal history neither changes bytes nor makes projection fail.
- Impact: Checkpoint availability becomes a function of lifetime campaign history rather than the bounded selected state. An otherwise authentic current state eventually becomes unreachable, and the proposed route cannot satisfy the no-unrelated-history boundary using only the currently allowed persistence files.
- Resolution: Bound projection by the authenticated selected identity set, using exact direct lookups plus a direct selected-order proof/index rather than whole-history materialization. If source order cannot be recovered without scanning `_effect_order`/`_owner_order`, add the required owner-side direct index under separately authorized scope. Add a control that appends unrelated terminal history beyond the family cap while holding the selected set fixed and proves identical bytes and successful projection.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 0
Unverified: No SQLite, DDL, query-plan, database, or executable test activity was performed; findings are from exact-object identity checks and static review of the frozen recursive contract and candidate source.
