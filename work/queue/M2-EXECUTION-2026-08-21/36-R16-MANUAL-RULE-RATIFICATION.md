# WO-0168c decision record — R16 reachable-current manual rule ratified

Date: 2026-08-24 · Ratified by: Ameen Mujtabaa · Recorded by: implementing seat (Claude)

## The ratification, verbatim

> I approve R16's reachable-current manual rule for WO-0168c: checkpoint the current manual
> reached from each selected scope and omit older unreachable `_manual_by_id` history, while
> retaining strict refusal of missing, stale, duplicate, or cross-scope current links. This
> supersedes the conflicting R15 §3 cardinality sentences.

## The conflict this closes

R15 §3 required the discovered manual count to equal "**both** current-index map cardinalities"
and asserted "no older manual row is retained." R16 §2 reclassified `_manual_by_id` as a
directly-reachable current index whose "older unreachable IDs are omitted." R16's preamble
supersedes R15 §§1, 4, 5 — but not §3, so the two accepted documents disagreed on a checkpoint
truth surface. Per CLAUDE.md's conflict rule the gap was recorded (REV-0078 in-process pass, P2)
rather than resolved silently; the implementation had followed R16 with the choice documented in
the encoder's docstring. This ratification supplies the missing human authority: **R16's rule
governs, and R15 §3's cardinality sentences are superseded for WO-0168c.**

The frozen R15/R16 documents are not edited; this record is the additive amendment, following the
same convention as the gate bundle's Amendment 1.

## What the ratified rule requires, and where each clause is enforced

| Clause | Enforcement | Pin |
| --- | --- | --- |
| Checkpoint the current manual reached from each selected scope | `_encode_runtime_checkpoint_manual_rows` walks `_manual_flatten_by_scope` per selected scope, resolves through `_manual_by_id` | `test_r20_manual_flatten_rows_project_exact_wire_from_selected_scope` |
| Omit older unreachable `_manual_by_id` history | no whole-map cardinality check on `_manual_by_id` | `test_r20_unreachable_manual_id_is_omitted_not_refused` + byte-identity noise-invariance control |
| Refuse **missing** | "selected scope names an absent manual flatten" | `test_r20_dangling_manual_slot_entry_is_refused` (+ `_is_still_refused`) |
| Refuse **stale** | "reached manual flatten does not own its index flatten ID" | `test_r20_manual_disagreeing_with_its_index_flatten_id_is_refused` |
| Refuse **duplicate** | "selected scopes retain a duplicate manual flatten" | `test_r20_duplicate_manual_reach_is_refused` — added with this record; the guard previously had no pin because the symbol refusal shadows it for spliced slots. Mutation-checked: disabling the guard fails the test. |
| Refuse **cross-scope** | "does not own its selected scope symbol" + `_manual_flatten_by_scope.size` unselected-scope refusal | `test_r20_manual_disagreeing_with_its_reached_scope_is_refused`, `test_r20_manual_flatten_unreachable_from_selected_scopes_is_refused` |

`_manual_flatten_by_scope` remains an exact current selected-scope map with its whole-map size
check — the ratification changes nothing there; only `_manual_by_id`'s cardinality treatment was
in conflict.

## Effect on open records

- REV-0078 in-process pass: the R15 §3 / R16 §2 P2 decision gap moves to the closed table.
- REV-0078 handoff: the open-question row becomes a ratified decision Codex verifies rather than
  weighs.
- No SQL, DDL, public export, or serving behavior changes. Documentation, one test, and one
  docstring citation only.
