# Work Retention Policy

Default dispositions:

- Major feature: PKL_UPDATED + RESULT_SUMMARY_KEPT
- Architecture decision: ADR_CREATED; delete raw prompt after ADR
- Important bug: PKL_UPDATED or error/drift log + RESULT_SUMMARY_KEPT
- Sensitive change: RESULT_SUMMARY_KEPT
- Routine typo/import/formatting: DELETED
- Placeholder: DELETED
- Duplicate: DELETED or SUPERSEDED
- Superseded raw plan: SUPERSEDED, then DELETED after successor is linked

Do not keep raw prompts unless they contain durable knowledge not captured elsewhere.

## Close-out timing (standing rule, adopted 2026-07-11)

Close-out ships with the work: the commit/PR that finishes a work order also
- flips the WO's `status` to its terminal value,
- records `disposition` in the frontmatter AND appends the `work/ledger.jsonl` entry,
- moves the file out of `work/queue|active|review` (to `completed/keep/`, archive, or deletion per the table above),
- refreshes any doc / PKL / ADR / FINDING claim the work just invalidated (stale "still open" notes are defects).

Rationale: in the repo's first three days, four "open items" (WO-0001's terminality caveat, WO-0012,
the WO-0013/14/15 queue strays, the INV-034 finding header) turned out to be finished work with stale
bookkeeping — the work discipline held, the close-out step kept getting dropped. Enforcement: CI runs
the AI-OS hygiene checks on every push; a completed work order parked in a live folder fails the build
(the OS script's warning is promoted to an error in `.github/workflows/ci.yml`, kept unforked).
