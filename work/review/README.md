# work/review/ — findings + cross-model review packets

Two kinds of artifact live here:

- **`FINDING-*.md`** — issues / decision-gaps the author (Claude) flagged during
  development. Raw evidence, some marked "queues for independent review."
- **`REV-NNNN/`** — a **review packet**: a tracked unit that carries a change through
  independent cross-model review. Protocol: `.ai-os/core/15_CROSS_MODEL_REVIEW.md`.

## Packet shape

```
REV-NNNN/
  request.md       # OUTBOUND — author writes it (from .ai-os/templates/review-request.md)
  result.md        # INBOUND  — the independent reviewer (Codex/other model) writes it
  disposition.md   # CLOSE    — author records what was accepted / fixed / disputed
```

## Flow

1. Author fills `request.md`: commit range, curated `file:line` pointers, the invariants /
   ADR to check, and (optionally) the review lenses to apply — Correctness & Edge Cases,
   Security / Data Integrity, Performance & Scalability, Maintainability, ADR / PKL
   Consistency. The reviewer is linked to the live repo.
2. A **different** model from the author writes `result.md`: a findings table + verdict
   `ACCEPT | ACCEPT-WITH-CHANGES | BLOCK` (reviewer role: `AGENTS.md`,
   `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`).
3. Author writes `disposition.md`: each finding fixed following Fable discipline / disputed
   with evidence, then updates `work/ledger.jsonl`. The independent-review gate is now
   cleared for that item.

If a result feels weak, the author may run **one** optional critique round.

## Current packets

- `REV-0001/` — WO-0007b order-status read-flip to event_truth + ADR-008 acceptance.
- `REV-0002/` — broker-adapter SDK method-name fix + flatten INV-034/INV-036 reconciliation.

Both are `AWAITING_REVIEW` — hand `request.md` to an independent model; it deposits `result.md`.
