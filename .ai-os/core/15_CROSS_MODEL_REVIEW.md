# Cross-Model Review Packets (v0.9.1)

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
