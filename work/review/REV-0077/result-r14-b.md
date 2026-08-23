# REV-0077 R14-B independent preflight review

Reviewed exact commit `135b5cde9f3b0d363c007251c3cce78298473e81`, tree `d11976d780f72d707cefe9556d16653f79d83529`, and R14 SHA-256 `c839b072f9c5a4e106337834dc0f675458d0453daf8402c5d37d28ae18597d9f` against the recursively frozen contract.

### [P1] Effect-only discovery cannot reach a valid effectless manual flatten

- Location: `work/queue/M2-EXECUTION-2026-08-21/25-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R14.md:33`
- Requirement: R14 lines 14-36 require projection to accept every authentic bounded selected state, retain every required closed-grammar value, and discover authority manual rows only through selected effect authorizations.
- Evidence: `reproduced-live` — from an archive of the exact reviewed commit, the accepted reducer path used by `test_manual_flatten_identity_grant_and_phase_guards` produced `disposition=APPLIED`, `created_effect_ids=0`, `manual_rows=1`, and `effect_authorizations=0`. This follows directly from `app/execution_core/authority.py:9599-9628`: authorization rows are added only inside `for effect_id in cancel_ids`, while `_ManualFlatten(..., cancel_ids)` is inserted unconditionally after a successful begin. No selected effect authorization can yield the retained flatten ID in this valid state. The focused pure baseline passed (`21 passed`) without exercising this reachability obligation.
- Impact: The access rule cannot encode a required authentic authority row without forbidden map enumeration, so a valid bounded checkpoint state must be refused despite R14's root acceptance rule. The generic "one authentic nonempty authority" control at lines 41-43 can pass with an effect-backed authority and is not failure-capable for this counterexample.
- Resolution: Freeze a proof-derived direct route for the current selected-scope manual row (and explicitly define which older manual rows are excluded), then require a pure effectless-manual control and a mutant that removes that route.

### [P1] Whole-owner materializers make unrelated lifetime history a checkpoint denial

- Location: `work/queue/M2-EXECUTION-2026-08-21/25-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R14.md:19`
- Requirement: R14 lines 14 and 25-29 require acceptance of every repository-selected bounded state while excluding unrelated terminal history. The imported source-order rule in `10-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R2.md:204-215` requires authentic `_owner_order` restricted to selected owners and expressly says repository data does not replace that owner-only order.
- Evidence: `static-reasoning` — the named venue materializers are whole-owner views: `VenueRecoveryBook.effects`, `claims`, `owners`, `closure_heads`, and `execution_bindings` iterate the complete retained order sequences (`app/execution_core/venue.py:4286-4368`), while coverage/reconciliation materializers return complete append-only ledgers (`app/execution_core/venue.py:4383-4408`). Effects are permanently appended to `_effect_order` (`app/execution_core/venue.py:9381-9420`) and later transitions retain that sequence (`app/execution_core/venue.py:12686-12699`). The selected OWNER storage vector has no source ordinal (`work/queue/M2-EXECUTION-2026-08-21/12-WO-0168C-R3-SQL-MANIFEST.md:51-52`), so the projector cannot recover selected owner order from the proof. Under R14's mandatory pre-touch retained-count check, 65,536 unrelated historical owners/effects make projection refuse even when the proof-selected family contains one valid row; touching the materializer instead violates the cap rule.
- Impact: Checkpoint availability depends on lifetime unrelated history rather than the bounded selected set. This contradicts completeness and leaves no conforming path for canonical owner-source attribution after the global retained sequence crosses the cap. A cap mutant that merely enforces the global refusal does not test the required property.
- Resolution: Freeze a bounded selected-key order/rank accessor or authenticated rank index whose work is proportional to the proof-selected keys, and add a negative control with an in-cap selected set plus over-cap unrelated terminal history. The control must still project the selected rows and must kill any fallback to whole-history materialization.

Unverified: SQLite-bearing behavior was intentionally not run; R14 changes no SQL/DDL authority. No implementation fix was evaluated.

P0: 0
P1: 2
P2: 0
Verdict: ACCEPT-WITH-CHANGES
