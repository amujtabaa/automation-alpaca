---
type: Review Result
rev_id: REV-0109
work_order_id: WO-0168d
reviewer_model: OpenAI Codex independent review seat
verdict: BLOCK
date: 2026-08-28
---

# REV-0109 — independent findings-only result

## Findings

### [P1] `MARKET_OCCURRENCE` durable inputs can splice in a stream from another route

- Location: `app/execution_core/persistence/schema.py:3899`
- Governing requirement: REV-0109 question 3 requires durable-input identity to match the frozen
  checkpoint/unit-of-work substrate (`work/review/REV-0109/request.md:81`), and WO-0166 FR-6/FR-7
  require exact application/profile/scope binding through failure-capable database constraints
  (`work/completed/keep/WO-0166-m2-i2-schema-direct-proof-foundation.md:316`).
- Evidence level: `reproduced-live` for static Git/source searches and extraction;
  `static-reasoning` for the accepted-row counterexample.
- Evidence: For `MARKET_OCCURRENCE`, the row must carry session, acquisition-generation,
  market-source-profile, and stream-generation coordinates (`schema.py:3850`). The application,
  scope, acquisition generation, and source profile are each constrained (`schema.py:3885`), but
  the final foreign key checks only `stream_generation_id` (`schema.py:3899`). Therefore all route-A
  coordinates can be valid while `stream_generation_id` names an existing route-B stream; every
  declared check and foreign key is independently satisfied. Static inspection of every I4 trigger
  found no insert-time exact-stream binding: the only durable-input stream reference after the table
  definition is the immutability comparison at `schema.py:4320`.
- Concrete impact: A retained market occurrence can claim scope/application/acquisition/source/session
  A while naming stream B. Decision receipts and outcomes can then terminalize that contradictory
  durable identity, corrupting protection/audit attribution in the future unit-of-work substrate.
  The held-suite source contains no `MARKET_OCCURRENCE` case, so the proposed command is not
  failure-capable for this bypass.
- Disproof pass: The stronger parent key was inspected at `schema.py:909`; although
  `market_stream_authority` has exact composite route uniqueness, `durable_input` neither references
  that composite nor reproduces it in a trigger. Searches across the complete DDL and all four held
  suites found no alternate binding or negative control, so the counterexample survives.
- Smallest complete resolution: Add a database-native exact-route foreign key or fail-closed insert
  trigger binding stream ID, scope, application generation, acquisition generation, source profile,
  and session; add held positive and one-coordinate-at-a-time cross-route rejection tests. Because
  that changes DDL/catalog identities, stop this gate, refresh the frozen identities/manifests, and
  obtain a new independent review before any unlock.

### [P1] A broker-outbox row can borrow an unrelated durable input from another scope

- Location: `app/execution_core/persistence/schema.py:4213`
- Governing requirement: REV-0109 question 3 requires broker-outbox rows to match durable input
  identity without creating broker authority (`work/review/REV-0109/request.md:81`), while WO-0166
  FR-6 requires capital-relevant rows to bind exact application/profile/scope coordinates
  (`work/completed/keep/WO-0166-m2-i2-schema-direct-proof-foundation.md:316`).
- Evidence level: `reproduced-live` for static Git/source searches and extraction;
  `static-reasoning` for the accepted-row counterexample.
- Evidence: The outbox-to-input foreign key contains only application generation, input domain, and
  input hash (`schema.py:4213`). Scope and, for `CLAIM_ACQUISITION_EFFECT`, acquisition generation
  are checked only by the separate outbox-to-effect foreign key (`schema.py:4218`). In one
  application generation with scopes A and B, an `AUTHORITY` durable input for scope A can therefore
  back an otherwise valid effect/claim/outbox row for scope B. The same splice works for a
  `CLAIM_ACQUISITION_EFFECT` input by choosing a different valid scope/acquisition route. Both
  independent foreign keys succeed.
- Concrete impact: The immutable post-commit broker payload can be durably attributed to a decision
  input that did not authorize its scope or acquisition route. That breaks the substrate's causal
  authority boundary before broker dispatch is ever wired. The held evidence only lists
  `store_broker_outbox` in the directness operation map (`tests_gated/execution_core/test_persistence_directness.py:392`)
  and export inventory; it contains no cross-scope or cross-acquisition outbox rejection.
- Disproof pass: All broker-outbox triggers were inspected (`schema.py:4588` through
  `schema.py:4623`); they enforce sequence, conflict retention, immutability, and no-delete only.
  Static searches across the full DDL and all four held suites found no trigger, composite input FK,
  or negative test that closes the split binding, so the counterexample survives.
- Smallest complete resolution: Add a fail-closed database binding from each outbox row to the same
  durable input scope and, when the domain is `CLAIM_ACQUISITION_EFFECT`, the same acquisition
  generation; add held cross-scope and cross-acquisition rejection tests. Then refresh every changed
  DDL/catalog identity and repeat independent review before a new human unlock.

### [P1] Attempt 2 may execute DDL from an unreviewed, dirty test revision

- Location: `work/review/REV-0109/request.md:115`
- Governing requirement: ADR-026 requires an unlock whose only change is the authorization flag and
  a clean published checkout with all identities reverified before execution
  (`docs/adr/ADR-026-interim-ddl-gate-threat-model.md:67`). WO-0168d repeats the exact-parent,
  flag-only, recorded-commit/tree, clean-worktree, and local-equals-origin lifecycle
  (`work/completed/keep/WO-0168d-m2-i3-5-hybrid-gate-simplification.md:131`).
- Evidence level: `reproduced-live` for static source extraction; `static-reasoning` for the
  lifecycle contradiction.
- Evidence: The plan performs publish/clean/local-equals-origin verification only before attempt 1
  (`request.md:102` through `request.md:108`). It then expressly permits a tracked test-fixture or
  expectation correction before attempt 2 and requires only a static diff check (`request.md:118`
  through `request.md:121`). As written, attempt 2 can therefore run after tracked files change,
  without a commit, publication, independent review, clean-worktree check, local/origin equality,
  or renewed identity verification.
- Concrete impact: A held-suite result could be produced from test code that is not the published,
  reviewer-bound Git identity. That weakens the exact human gate and permits a fixture edit to alter
  failure attribution after the sole independent review, even though the DDL remains frozen.
- Disproof pass: No later plan step restores the lifecycle. Committing the correction would not cure
  the written authorization: it would introduce an additional unreviewed tracked revision beyond
  the recorded flag-only unlock, while leaving the required clean/published re-verification and
  review unspecified. The stop clause does not resolve the contradiction because the preceding
  bullet explicitly authorizes these test changes.
- Smallest complete resolution: Keep attempt 2 only for an environmental/interruption retry with
  zero tracked changes. Any fixture or expectation correction must stop this authorization, enter a
  separately reviewed candidate, and restart the exact unlock lifecycle with newly recorded Git
  identities.

No `schema.py` import, held-suite collection or execution, SQLite connection, database creation,
DDL/schema installation, network/broker activity, or source/test/request edit occurred during this
review. Only this reviewer-owned `result.md` was created.

Verdict: BLOCK

P0: 0

P1: 3

P2: 0

Unverified: SQLite syntax/catalog/runtime constraint behavior and all held-suite outcomes, which the
packet expressly forbids this review from executing.
