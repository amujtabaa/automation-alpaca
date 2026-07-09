# work/review/ — findings + cross-model review packets

Two kinds of artifact live here:

- **`FINDING-*.md`** — issues/decision-gaps the author (Claude) flagged during
  development. Raw evidence, staged for review. Some are marked "queues for
  independent review."
- **`REV-NNNN-<slug>/`** — a **review packet**: a tracked, paired unit that carries
  a change through independent cross-model review. Full protocol:
  `.ai-os/core/15_CROSS_MODEL_REVIEW.md`.

## Packet shape

```
REV-NNNN-<slug>/
  request.md       # OUTBOUND — author writes it (from .ai-os/templates/review-request.md)
  result.md        # INBOUND  — the external reviewer (Codex/ChatGPT/other) fills it in
  disposition.md   # CLOSE    — author writes it when ingesting the result
```

## Flow

1. Author fills `request.md`: commit range, curated `file:line` pointers, the
   invariants/ADR to check, the concrete risks to probe. Reviewer is linked to the
   live repo.
2. External model (a **different** model from the author) writes `result.md`:
   findings table + verdict `ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`.
3. Author writes `disposition.md`: each finding fixed RED→GREEN / disputed with
   evidence / deferred to a WO; per-target gate status. Marks the covered
   `FINDING-*.md` REVIEWED, records ADR acceptance, appends to `work/ledger.jsonl`.

A human-gated-surface change's "queues for independent review" gate clears only at
a `DISPOSED` packet with an `ACCEPT`/`ACCEPT-WITH-CHANGES` verdict and every finding
addressed.

## Check

```
python .ai-os/scripts/check_review_packet.py
```

Validates packet structure and that every `FINDING-*.md` still "queues for
independent review" is covered by some packet's `targets`.
