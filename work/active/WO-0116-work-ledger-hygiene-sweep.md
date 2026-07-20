---
type: Work Order
title: "Work-order / ledger hygiene sweep: flip, disposition, move, ledger — evidence-backed only"
status: ACTIVE
work_order_id: WO-0116
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: []
owner: Ameen / planning seat drafted 2026-07-20 / implementer: Codex session
created: 2026-07-20
gated_surface: none (bookkeeping only; ALL file deletions excluded — operator-gated)
---

# Work Order: make the work/ tree and ledger truthful

> Bookkeeping only. This WO flips statuses, records dispositions, moves files out of live
> folders, and appends ledger rows — **only where evidence proves the work is finished.**
> It fixes zero code, rewrites zero historical prose, deletes zero files. Any correctness
> doubt discovered while gathering evidence is handed to WO-0117 (audit) as a target, never
> fixed here. Anything ambiguous lands in a batched NEEDS-INPUT list for Ameen.

## Goal

Every finished work order carries its true status, disposition, folder, and ledger row —
closing the "done but not dispositioned" drift the CLAUDE.md close-out rule exists to prevent
(the drift currently evades CI because unflipped `status:` fields never trigger the ratchet).

## Context packet

Read only these first:

- `CLAUDE.md` (close-out rule) + `AGENTS.md`
- `.ai-os/rules/ai-os-rules.yaml` (valid statuses/dispositions) + `.ai-os/templates/work-order.md`
- `.ai-os/scripts/check_work_order_disposition.py` + `check_ledger.py` (what CI enforces)
- `work/ledger.jsonl` (append-only; existing row shapes are the format authority)
- `work/review/CAMPAIGN-0002-claude/DOWNSTREAM-STATUS.md` + `PARTB-COMPLETION-PLAN.md` (close evidence)
- `work/review/REV-0029/disposition.md` (WO-0107/0108 closure evidence) + `work/review/REV-0033/disposition.md`
- `docs/adr/ADR-010-execution-envelope.md` (header + §3/§4 records of landed WOs)
- The target files listed below (front matter + close-out sections only)

## Allowed paths

```yaml
allowed_paths:
  - work/**          # front matter, close-out/disposition sections, file moves, ledger append
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - docs/**
  - pkl/**
  - cockpit/**
  - .github/**
  - .ai-os/**        # the OS itself is not edited by a hygiene pass
```

## Target table (planning-time evidence, 2026-07-20, anchor `88833e3d`)

Verify each row independently before flipping — the evidence column is a starting point, not
a conclusion. "Ledger mentions" = substring hits in `work/ledger.jsonl`, not confirmed rows.

| Target | Observed state | Planning evidence | Expected action (if verified) |
|---|---|---|---|
| `work/active/WO-0032` | `status: DRAFT — HUMAN APPROVAL REQUIRED` | ADR-010 header: findings "remediated WO-0024..0034"; 0 ledger mentions | verify vs code/tests → CLOSED + disposition + move + ledger, or NEEDS-INPUT |
| `work/active/WO-0033` | `status: DRAFT` | same ADR claim; 0 ledger mentions | same |
| `work/active/WO-0034` | `status: DRAFT — HUMAN APPROVAL REQUIRED` | same ADR claim; 0 ledger mentions | same |
| `work/active/WO-0035` | non-canonical `status: EXECUTED (…)` | body records Ameen 2026-07-15 directive; 0 ledger mentions | canonical status + disposition + move + ledger |
| `work/active/WO-0105` | `status: REVIEW` | 0 ledger mentions; Part A consolidation — check vs `work/review/CONSOLIDATION-R2-PARTA-CODEX` + WO-0106 CLOSED row | likely SUPERSEDED/CLOSED by consolidation |
| `work/active/WO-0107` | `status: REVIEW` | ADR-010 §4 records Option B landed; REV-0024 subsumed by REV-0029 (ledger WO-0036 row); merged in PR #9 | CLOSED + disposition + move + ledger |
| `work/active/WO-0108` | `status: ACTIVE` | REV-0029 disposition round-2 table: all steps landed; merged in PR #9 | CLOSED + disposition + move + ledger |
| `work/active/W3-STATE.md` | wave-state note in a live folder | W3 concluded | archive note or NEEDS-INPUT |
| `work/completed/keep/WO-0109` | `status: REVIEW` inside completed/ | ledger last state REVIEW; `work/review/REV-0030/` has `result.md` but **no `disposition.md`** | reconcile: was REV-0030 dispositioned/superseded by the REV-0031..0033 chain? record it, flip WO-0109, ledger; else NEEDS-INPUT |
| `work/completed/WO-0110/0111/0112` | front matter unverified | ledger rows say CLOSED (0110/0111); 0112 unchecked | verify front matter matches ledger; align |
| `work/queue/WO-0022` | `status: DRAFT` (W3 adversarial review) | multiple review rounds since executed | SUPERSEDED w/ evidence, or NEEDS-INPUT |
| `work/queue/WO-0029` | self-described "grouped placeholder… re-cut" | WO-0036 marked SPEC-08/10 DONE, CC-05 PARTIAL | flag for planning-seat re-cut (NEEDS-INPUT); do NOT re-cut here |
| `work/queue/W3-KICKOFF-PROMPT/W3-README/W4-SEED-NOTES` | prompts/notes in live queue | retention rules favor deleting routine prompts — but deletion is operator-gated | list for Ameen (NEEDS-INPUT); no deletion in this WO |
| `work/queue/WO-0102/0103/0104` | DRAFT, re-gated on REV-0022 remediation | gate-state currency is an AUDIT question | do not touch; hand to WO-0117 Tier 3 |

## Required behavior

- [ ] Per target: gather fresh evidence (commits, ADR text, review packets, test presence,
      ledger) BEFORE any edit; paste it in the close-out section written into the file.
- [ ] Evidence-backed targets: in ONE commit per target (or one batched commit) — canonical
      `status:` flip + `disposition:` from `valid_work_order_dispositions` + completed
      close-out section + `git mv` out of the live folder + appended `work/ledger.jsonl` row
      matching existing row shape. Never split flip from move (the CI ratchet fails a
      completed status parked in a live folder).
- [ ] Ledger is append-only: no row edited or reordered; WO-0109's stale REVIEW row is
      superseded by a NEW row, not rewritten.
- [ ] No file deletion of any kind (even where retention rules would allow): deletions are
      batched as recommendations in the NEEDS-INPUT list for Ameen.
- [ ] No historical-body rewrites: front matter, close-out/disposition sections, and file
      location only. The record stays honest — a flip states what happened and when it was
      recorded, never backdates.
- [ ] Unverifiable or contradictory targets → NEEDS-INPUT batch with the exact contradiction
      quoted; correctness doubts (a claim that looks false against current code) → named
      handoff to WO-0117, not investigated here.
- [ ] Final report: table of every target → action taken / NEEDS-INPUT / handed-to-audit,
      each with its evidence citation.

## Required commands

```bash
python .ai-os/scripts/check_install.py && python .ai-os/scripts/check_version_consistency.py
python .ai-os/scripts/check_ledger.py && python .ai-os/scripts/check_pkl.py pkl/
python .ai-os/scripts/check_work_order_disposition.py   # must print zero WARNING lines
ruff check . && pytest -q --collect-only -q | tail -2   # tree untouched proof (no code paths changed)
```

## Acceptance criteria

- [ ] All five AI-OS checks green AND the disposition checker emits zero WARNING lines
      (the CI step promotes WARNING to failure).
- [ ] Every flip cites pasted evidence in the file it flips; zero unevidenced status changes.
- [ ] `git diff --stat` touches `work/**` only.
- [ ] NEEDS-INPUT batch + audit-handoff list delivered in the final report.
- [ ] Fable DONE block; status `VERIFIED` only if every target is dispositioned or explicitly
      batched.

## Stop conditions

Stop and batch (no flip) if: evidence conflicts (ledger vs ADR vs file), a target's "done"
claim would require re-verifying code behavior (that is WO-0117's job), or a flip would
require deleting/rewriting history. Rollback: revert the commit(s); ledger reverts with them.

## Model-tier rationale

`mid` — mechanical edits, but each flip is an evidentiary judgment against governance records;
misfiling one record corrupts the planning plane CI protects.

## Notes

- This WO deliberately precedes WO-0117 (audit) so the auditor reads a truthful tree; it can
  run in the same session, in its own commits.
- Builder-seat note: this is bookkeeping, so the Codex session may execute it even where the
  underlying work was Codex-built — flips record *that* work finished, not that it was correct.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]` (+ ledger rows per target).
