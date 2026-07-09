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
