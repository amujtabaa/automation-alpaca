---
type: Work Order
title: "Complete the governance record + make the disposition checker folder-aware"
status: ACTIVE
work_order_id: WO-0120
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: []
owner: Ameen / implementer TBD / from AUDIT-0002 F001/F008/F009/F010 + C001/C102
created: 2026-07-20
gated_surface: none for the record flips; Phase 2 changes a CI gate (operator-aware)
---

# Work Order: make every completed record say so, and make the checker enforce it

## Goal

Close the record-truth findings AUDIT-0002 raised — completed work still labelled in-progress,
missing review-closure records — and harden the disposition checker so the "false green" class
cannot recur.

## Context packet

- `CLAUDE.md` (close-out rule) + `.ai-os/rules/ai-os-rules.yaml` (statuses/dispositions)
- `work/queue/AUDIT-0002-REMEDIATION-BATCH.md` (this WO's source; the two F008 DRAFTs)
- `work/review/AUDIT-0002-priorwork/report.md` (F001/F008/F009/F010) + `addendum-claude-seat.md` (C001/C102)
- `.ai-os/scripts/check_work_order_disposition.py` (the checker to harden)
- The target records listed below + `work/ledger.jsonl`

## Allowed paths

```yaml
allowed_paths:
  - work/**                                         # record flips, dispositions, ledger appends, file moves
  - .ai-os/scripts/check_work_order_disposition.py  # Phase 2 only
  - tests/**                                        # Phase 2: a test for the hardened checker if one fits
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - docs/**            # ADR/INV label drift is WO-0121, human-gated — not here
  - .github/**
```

## Required behavior

- [ ] **Phase 1 — records (bookkeeping, evidence-backed, append-only ledger, no body rewrites):**
  - **F001 / C001:** reconcile the ~14 completed W3 records still at DRAFT/gate-awaiting
    (WO-0016..0021, 0024..0028, 0030, 0031) AND WO-0113 (`status: REVIEW`) to a canonical
    completed status + non-empty disposition, each citing its ledger + close-out evidence. Flip
    WO-0113 citing REV-0033 RESOLVED + merge `88833e3d`.
  - **F008:** write the two closure records from the remediation batch — append the round-2/3
    closure section to `REV-0029/disposition.md` (retitle from IN PROGRESS), create
    `REV-0030/disposition.md` (fill the date at write time). Flip WO-0109 `REVIEW` → completed.
  - **F009:** append a resolution/disposition block to each of the nine remediated W3
    `FINDING-*` files (naming the exact WO + pin + review), preserving original finding text.
    Leave the two legitimately-open findings (grouped lifecycle/eventing, structural-hold) OPEN.
  - **F010:** correct REV-0019's disposition front-matter verdict to match its result (retain
    body); add a retained request/provenance marker for REV-0023 recording the actual dispatch.
- [ ] **Phase 2 — checker (changes a CI gate; operator-aware):** make
  `check_work_order_disposition.py` FAIL when a file under `work/completed/**` has a
  non-completed status or an empty required disposition (today it only inspects recognized
  completed statuses, so a REVIEW/DRAFT file in a completed folder is invisible — the exact
  blind spot behind F001/C001). Keep the existing WARNING-on-parked-completed behavior. Add/extend
  a test if the checker has one.
- [ ] Close-out ships with the work; every flip cites pasted evidence; `git diff --stat` limited
  to allowed paths.

## Acceptance criteria

- [ ] All five AI-OS checks green; the hardened checker passes on the now-truthful tree AND
  fails on a deliberately-planted completed-folder DRAFT (prove the new guard bites).
- [ ] Every record flip evidence-backed; ledger append-only; no historical body rewritten.
- [ ] Fable DONE block; VERIFIED only when every listed record is reconciled or explicitly left
  open with a reason (the two genuinely-open F009 findings).

## Stop conditions

Stop and batch NEEDS-INPUT if a record's evidence conflicts (ledger vs file vs review) or a flip
would need deleting/rewriting history. Rollback: revert the commit(s); ledger reverts with them.

## Notes

Phase 2 is the ratchet AUDIT-0002 asked for: it converts these findings from "caught by an audit"
to "caught by CI." Because it changes gate behavior, call it out in the PR/close-out for operator
visibility even though it touches no app code.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]` (+ ledger rows per record).

## Fable gate

```yaml
fable_gate:
  goal: "Make completed governance records truthful and make the disposition checker reject non-completed records parked under work/completed."
  assumptions:
    - "The cited ledger, close-out, and review artifacts agree; any conflict stops the affected record as NEEDS-INPUT."
    - "Record remediation is additive except for frontmatter status/disposition corrections explicitly authorized by this work order."
  approach: "Verify each cited closure chain, reconcile Phase 1 records without rewriting historical bodies, add a failing checker regression, then make the folder-aware guard pass."
  out_of_scope:
    - "app/**"
    - "docs/**"
    - ".github/**"
    - "the two F009 findings the audit says remain legitimately open"
  done_when:
    - "Every required record is reconciled or explicitly left open with evidence."
    - "The checker fails for a completed-folder DRAFT and passes on the truthful repository."
    - "All five AI-OS checks and scoped regression tests pass with fresh output."
    - "Close-out status, disposition, ledger append, file move, scoreboard, and Fable DONE ship together."
  blast_radius: "work/** governance metadata plus the disposition checker and its tests"
```
