# REV-0078 — in-process adversarial pass (NOT the independent review)

Date: 2026-08-24 · Author: the implementing seat (Claude) · Candidate at time of pass: `2cfbce0`

## Status of this document

**This is not `result.md` and does not clear REV-0078's gate.** CLAUDE.md: "In-process
validation never counts as independent review; no seat's self-review is ever the only review."
Protocol P-1 also bars the reviewed party from authoring the reviewer-owned result. Ameen asked
for a fresh-context adversarial self-review; this records it as a disclosed first-pass filter so
the independent reviewer can see what was already found, fixed, or deliberately deferred.

Three fresh-context agents ran with no shared state, on separate lenses: contract conformance,
refusal/taxonomy logic, and test integrity. Raw totals: **P0=7, P1=14, P2=18** across the three.
They agreed independently on the most severe finding.

## Fixed in `0a5c2c3`

| Sev | Finding | Disposition |
| --- | --- | --- |
| P0 | `_reconciliation_by_input.size != reached` refused every reconciliation-required book. `recovery._reconciliation` appends without touching any closure or coverage row, so the input is legitimately unreferenced. Found independently by two agents. | Check removed. The map is `insert_new`-only beside an append-only ledger — a permitted superset under R16 §2. Test that pinned the refusal now asserts omission. |
| P0 | Same for `_execution_reconciliation_by_input`. A catch-up is appended for every `CatchUpExecutionRegistry` while a bootstrap target is refreshed only where one exists, the unresolved arm never advances `checkpoint_input_id`, and that field is replaced on each refresh. | Check removed; test inverted to assert omission. |
| P0 | Same for `_closure_head_by_leg`. A head persists for every leg that ever terminated; the repository selects only OPEN/INVALIDATED effects plus late owners, so the first closed effect made every later checkpoint refuse. | Check removed; the control retargeted onto the leg-ownership refusal this family actually carries. |
| P0 | A *referenced* reconciliation that is missing was silently skipped. R15 §2 lists "missing" first among rows that must fail, and the size check could never have caught it — deleting a referenced row decrements both sides. | Both families now raise. |
| P0 | `trg_kernel_checkpoint_versioned_replace` had zero coverage repo-wide after my expectation change, and my stated reason ("unreachable through this path") was false — it is reachable and loses SQLite's BEFORE-trigger order race. | Dedicated control added, staging the payload for both versions so only the version trigger can refuse. Mutation-checked: deleting the trigger now fails 2 tests, previously 0. |
| P1 | Bootstrap records reached the wire without `_bootstrap_bound_target_record_is_authentic` / its consumed twin. Contract 07 §3.3 requires retained seals and commitments to be re-derived and compared, never trusted; absence from the wire is not verification. | Both forms now call the venue's own helper. |
| P1 | My "partial index implies bounded" rule was wrong. `ix_venue_owner_checkpoint_late` is partial on `admitted_after_effect_closed = 1`, which never clears, on a table with a no-delete trigger. | The two live-state indexes are named explicitly, with an assertion that they really are partial. Pinned violation set grows 5 → 12. |
| P1 | `test_r20_emergency_grant_refuses_a_member_of_the_wrong_exact_type` used a bare `pytest.raises(ValueError)`; the `TypeError` branch its name promises was untested. | Both branches pinned with `match=`. |
| P1 | The "closure over all families" docstring claimed a "fully populated" book; the fixture populates ten of fifteen venue collections and three of four authority collections. | Docstring corrected to say what it does and does not cover. |

## Closed since this pass was written (Ameen authorized 2026-08-24)

| Sev | Finding | Disposition |
| --- | --- | --- |
| P1 | `_GATE_DIGEST` re-pin not in the approved bundle | Ratified retroactively in gate bundle Amendment 1; the underlying self-approving gate is tracked as `work/review/FINDING-schema-approval-gate-is-self-approving.md`, blocking before `execution_core` goes live. |
| P0 | Reconciliation checked for set membership, not the referencing relation | Both derivations now carry the referencing row's identity (leg for fills, scope for registry outcomes) and require equality. An input named by two different legs or scopes is itself a refusal. Mutation-checked. |
| P0 | `selection.closure_heads` never consulted | Closure heads now bind against their selected record on owner, ordinal, kind, and predecessor presence, in all three directions. Duplicate selected owners refused. Mutation-checked. |
| P1 | Five pre-existing whole-map cardinality checks | Removed, on verified facts rather than argument: `_PersistentKeyMap` has no deletion operation, and the selection is `disposition IN ('OPEN','INVALIDATED')` plus late owners. **The independent reviewer is still asked to rule on this** — it removes refusals on a safety surface. |
| P1 | Packet bound stopped at `2cfbce0` | Extended in `request-r1.md` Amendment 1. |
| P2 | Plan-control alias regex required `AS` | Bare aliases now resolved, with keyword guarding. |
| P2 | Import-direction control detected a bare substring | Now AST-based. Probed: a comment-only mention does not count; a real import does. |

## Still open — recorded for the independent reviewer and for Ameen

| Sev | Finding | Why not acted on |
| --- | --- | --- |
| P2 | Undeclared R15 §3 / R16 §2 conflict on `_manual_by_id`: R16 supersedes §§1, 4, 5 but not §3, and the code follows R16 with the choice recorded only in a docstring. | CLAUDE.md conflict rule says record the decision gap. Recorded here. |
| P2 | Pre-existing tautologies in `test_persistence_runtime_checkpoint_pure.py` (`:1554`, `:1551`, `:2258`) compute the expectation with the same production helper under test. Not from this diff. | Out of scope; recorded. |
| P2 | Plans are measured on a ~9-row database with no `ANALYZE`; planner choices there are weak evidence about production shapes. | Real limitation of the control. |

## What this pass does not establish

It is in-process. Two of the three agents were given lenses I chose, on a diff I wrote, with
contracts I selected as authority. It found real defects — including several in reasoning I had
presented to Ameen as sound — but it cannot substitute for the independent seat, and no verdict
is recorded here.
