# Work Order Retention and Disposition

## Purpose

Work orders are execution artifacts, not institutional memory.

A work order exists to help an agent complete a bounded task with the right context, tests, scope, and verification. After the task is merged, closed, or abandoned, the work order should not remain as a growing pile of stale prompt text.

The durable project memory lives in:

- code
- tests
- contracts and schemas
- Architecture Decision Records (ADRs)
- Project Knowledge Layer (PKL) pages
- error book / drift log
- compact ledger records

## Core rule

Preserve project knowledge. Do not preserve every prompt.

After completion, each work order must be assigned a final disposition:

```text
PKL_UPDATED
ADR_CREATED
RESULT_SUMMARY_KEPT
ARCHIVED
DELETED
SUPERSEDED
ABANDONED
```

This vocabulary is defined canonically in `rules/ai-os-rules.yaml` (`valid_work_order_dispositions`).

A work order may have multiple dispositions. Example: a major architectural feature may be both `PKL_UPDATED` and `ADR_CREATED`, while the raw prompt is still `DELETED` after distillation.

## Lifecycle

```text
DRAFT
→ READY
→ ACTIVE
→ REVIEW
→ MERGED | CLOSED | ABANDONED | SUPERSEDED
→ DISTILLED
→ DISPOSED
```

`DISTILLED` means useful knowledge has been moved into its proper canonical home.

`DISPOSED` means the raw work order has been summarized, archived, deleted, or marked as abandoned/superseded.

## Folder model

```text
work/
  queue/               # not started
  active/              # assigned to a worktree/session
  review/              # implementation complete, review pending
  completed/
    keep/              # compact result records worth keeping
    delete-candidates/ # temporary staging only
  archive/             # compressed old records by milestone/quarter
  ledger.jsonl         # durable searchable index
  retention-policy.md
```

`delete-candidates/` is not a landfill. It should be emptied during maintenance.

## Disposition defaults

Default dispositions per work type live in the installed quick reference
`work/retention-policy.md`. The vocabulary itself is defined canonically in
`rules/ai-os-rules.yaml` (`valid_work_order_dispositions`).

## Deletion checklist

Delete the raw work order if all are true:

- [ ] The work is merged, abandoned, closed, or superseded.
- [ ] It contains no unique product requirement.
- [ ] It contains no architecture decision.
- [ ] It contains no reusable implementation pattern.
- [ ] It contains no important failure lesson.
- [ ] It contains no audit, compliance, or sensitive-change value.
- [ ] Any useful outcome has already been captured in code, tests, PKL, ADRs, error logs, or the ledger.

If all boxes are checked, deletion is the correct disposition.

## Compact result record

Use a result record only when the work has future retrieval value.

```markdown
# WO-004 Report Upload — Result

Status: MERGED / DISTILLED
Disposition: PKL_UPDATED, RESULT_SUMMARY_KEPT
Branch: feature/report-upload
Commit: abc123
Date: 2026-07-07

## Outcome

Implemented PDF report upload with type validation, metadata persistence, and audit-log emission.

## Verification

- Unit tests: passed
- Integration tests: passed
- Scope check: passed
- Fable DONE: present

## PKL / ADR updates

- pkl/modules/reports.md
- pkl/log.md

## Deferred

- Virus scanning not implemented; captured as WO-009.
```

## Ledger entry

The ledger preserves traceability without preserving low-value prompts.

The line format is defined by `mcp/schemas/ledger_entry.schema.json` and validated by `scripts/check_ledger.py`; statuses and dispositions are bound to the vocabularies in `rules/ai-os-rules.yaml`.

```json
{"id":"WO-014","title":"Fix typo in report label","status":"MERGED","disposition":["DELETED"],"commit":"abc123","date":"2026-07-07","reason":"Routine low-value change; no durable knowledge."}
```

## Anti-bloat rules

- No completed raw work order should remain in `active/`, `review/`, or `queue/`.
- No raw prompt should be kept only because it existed.
- No work order should become the canonical home for project rules.
- No work order should duplicate PKL pages, ADRs, or source code comments.
- No old work order should be placed into a context packet unless it is explicitly marked `RESULT_SUMMARY_KEPT` and directly relevant.

## Maintenance cadence

Run a work-order disposition pass:

- after each merge
- after each wave
- before starting a new long session
- after context compaction
- before packaging the OS for a new repo

## Operator command

Use this command in Claude Code, Codex, or a generic agent session:

```text
ai-os dispose-work-orders

Review work/queue, work/active, work/review, and work/completed.
For each work order, assign one of: PKL_UPDATED, ADR_CREATED, RESULT_SUMMARY_KEPT, ARCHIVED, DELETED, SUPERSEDED, ABANDONED.
Distill useful information into PKL/ADR/result records before deletion.
Do not delete anything with unresolved human decisions.
Produce a deletion list for human review before removing files.
```
