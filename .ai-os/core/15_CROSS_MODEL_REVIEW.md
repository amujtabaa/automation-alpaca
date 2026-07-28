# Cross-Model Review Packets (v0.9.1)

> **See also — `pkl/process/review-hardening.md` (accepted 2026-07-18, REV-0029 post-mortem):**
> mechanical review gates (enum-total classification, mutation checks for safety pins,
> producer/consumer tables for new fields, repeated runs for timing-sensitive gate claims) and
> **blind, spec-first** rules for the IN-PROCESS lens layer beneath this packet protocol. Those
> rules exist because six in-process lenses returned SHIP on a change that independent review then
> BLOCKED with three real execution-safety defects — in-process review is a first-pass filter, and
> "in-process validation never counts as independent review" (below) is load-bearing.

## Purpose
Provide a low-friction, tracked way for independent cross-model review (e.g. Claude → Codex or other model) so that reviewer output is never orphaned and the "queues for independent review" gate can be cleared reliably.

## When to Use
- Human-gated safety surfaces and ADR amendments (mandatory before beta reliance).
- Any change the author wants fresh adversarial eyes on (discretionary).

## Packet Structure
Each review lives in its own folder:
`work/review/REV-NNNN/`

Contents:
- `request.md` — Outbound prompt written by the author (Claude).
- `result.md` — Inbound findings written by the independent reviewer.
- `disposition.md` — Author records what was accepted, fixed, or disputed.

## Packet Ownership and PR-Thread Record (P-1/P-2, adopted 2026-07-21)

- **P-1:** A reviewed party never edits a reviewer-owned `result.md` in place. If a correction,
  clarification, or rebuttal is needed, add a separate disclosed addendum in the same packet that
  identifies its author, date, and relationship to the reviewer result. Preserve the original
  result unchanged.
- **P-2:** Every human-gated-surface change receives a tracked `REV-*` packet even when review
  discussion occurs in PR threads. The packet request or disposition records the PR/thread
  verdict and links or identifies the review record; PR discussion alone is not the packet.

## Review Lenses (Optional but Recommended)
When creating `request.md`, consider asking the reviewer to analyze through relevant lenses:
- Correctness & Edge Cases
- Security / Data Integrity
- Performance & Scalability
- Maintainability
- ADR / PKL Consistency

## Disposition Loop (Critical)
1. Reviewer deposits `result.md` with verdict + findings + proposed fixes.
2. Author reviews proposals.
3. Author applies accepted changes following Fable discipline.
4. Author creates `disposition.md` documenting decisions and evidence.
5. Update `work/ledger.jsonl`.
6. The independent review gate is now cleared for that item.

## Optional Critique Round
If the first result feels weak, the author may create a short critique and ask for one additional pass. Limit to one critique round per packet.

## Integration Notes
- Reuses existing `work/review/` lifecycle, `AGENTS.md` independent seat rules, ledger, and verdict vocabulary.
- Does **not** place anything under `pkl/`.
- Works alongside (does not replace) Fable in-flight review.

See `work/review/README.md` and the templates in `.ai-os/templates/` for concrete examples.

## New-invariant probe obligation (PROC-0001 #3, accepted 2026-07-12)

Every review packet lists the `INV-*` entries ADDED or AMENDED since the last review
milestone, and each must have >= 1 fresh-probe line IN THE PACKET — a new scenario tested
against the invariant statement, NOT a rerun of its own pinning test and NOT a bare citation
(the self-citation trap: a document that mentions an ID makes naive coverage scans read
clean). Before any beta-relevant milestone, the gate check is: every defined INV id appears
in `work/review/` with probe evidence; uncovered ids block the gate for those ids
specifically. First application: INV-078/079/080/085 are due in the REV-0023 Phase B
reconciliation packet.

## Round budgets and the treadmill tripwire (P-1/P-4, operator-ratified 2026-07-28)

Adopted from AUDIT-0003 (evidence: the PR #9 chain consumed six remediation work orders and
five packets; the R6a saga took three BLOCK verdicts on one surface; both times the
intervention that worked — a root-cause audit, a seat change — was applied late).

- **Review-round budget (P-4):** after TWO review rounds on one delivery that each produced
  findings, the response to the next round may not be another in-place remediation of the
  same work order. The delivery is re-cut (split per the clean-close profile: one primary
  rail, explicit paths, bounded surface) and/or the implementing seat changes. The packet
  chain records which was chosen and why.
- **Treadmill tripwire (P-1):** after TWO consecutive BLOCK or P0-bearing rounds on one
  SURFACE (even across different work orders), the next artifact on that surface must be a
  root-cause audit in the AUDIT-0001 mold — grade the prior rounds' own fixes symptom-vs-root,
  map which truths on the surface are multiply derived and which lanes bypass the choke
  points, then sweep for the class — before any further remediation work order is drafted.
  Remediating a third time without the audit requires an explicit operator override recorded
  in the packet.

Counting is per-surface and survives file turnover: the count lives in the packet frontmatter
(`round:` in results; a `surface:` tag naming the subsystem), so a fresh work order on the
same surface does not reset it.
