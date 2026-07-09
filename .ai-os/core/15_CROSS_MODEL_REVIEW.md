# 15 — Cross-Model Review (Review Packets)

Independent cross-model review is a first-class step in this OS: a **different
model** from the author (Codex / ChatGPT / another Claude lineage) re-derives a
change from the code and returns findings. This doc defines how that review is
requested, delivered, and closed so its output is never orphaned again (the prior
failure: "Codex-tagged findings were never checked into this repo, so those ids
weren't tracked" — `docs/00_START_HERE.md`).

The reviewer's ROLE is already defined in `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`. This doc adds the missing
piece: a **tracked, paired request↔result unit** — the *review packet*.

## When review is required vs. discretionary

Per `CLAUDE.md` "## Review":
- **Mandatory** (a packet MUST exist and reach a verdict before the change is
  *relied upon* for a beta milestone): any change to a **human-gated safety
  surface** (order submission, cancel/replace, kill switch, manual flatten,
  live/shadow config, schema/DB migration, event-log-truth changes,
  deletion of tests/docs/ADRs) and any **ADR amendment / acceptance**.
- **Discretionary** (batched at milestones, at the human's discretion): everything
  else.

In-process validation (Fable evidence, the quality-engineer agent, workflow
recon/verify fan-outs) is **never** the independent review — it is same-lineage.

## The packet

One review = one `REV-NNNN` folder under `work/review/`:

```
work/review/REV-NNNN-<slug>/
  request.md       # OUTBOUND — the author writes it (from .ai-os/templates/review-request.md)
  result.md        # INBOUND  — the external reviewer deposits it (from review-result.md)
  disposition.md   # CLOSE    — the author writes it when ingesting the result
```

`request.md` and `result.md` carry YAML front-matter the checker validates
(`rev_id`, `status`, `targets`, `verdict`, …). `targets` lists the WO / ADR /
`FINDING-*.md` ids under review. Raw `work/review/FINDING-*.md` docs remain the
author's staged evidence and are referenced by a packet's `targets`.

## Lifecycle

```
finding/change → request.md → (hand to external model) → result.md → disposition.md → gate cleared
   AWAITING_REVIEW ─────────────────────────────────────► REVIEWED ──────────────► DISPOSED
```

1. **Request.** The author copies `review-request.md`, gives the reviewer the
   smallest useful context: the commit range, the author's own writeup, curated
   `file:line` pointers + the invariants/ADR to check, and the concrete risks to
   probe. The reviewer is linked to the live repo and may follow its own leads.
2. **Result.** The external model fills `result.md`: a findings table
   (`| ID | Severity | File:line | Evidence | Why it matters | Required action |`)
   and a verdict `ACCEPT | ACCEPT-WITH-CHANGES | BLOCK` (per target too). Severity
   is P0 (blocking) / P1 (important) per `AGENTS.md`.
3. **Disposition.** The author ingests the result: for each finding, applies a fix
   **RED→GREEN** (a failing test first), or disputes it with evidence, or defers it
   to a new work order. `disposition.md` records what happened per finding and the
   resulting per-target gate status.

## What clears the gate

A target's "queues for independent review" gate (in its `FINDING-*.md`, WO
`fable-done.md`, ADR Status, and the ledger `reason`) clears only when its packet
is `DISPOSED` with:
- a `result.md` whose verdict is `ACCEPT` or `ACCEPT-WITH-CHANGES` (a `BLOCK`
  never clears a gate — it must be resolved and re-reviewed), AND
- every `result.md` finding addressed in `disposition.md` (fixed / disputed /
  deferred-with-a-WO).

On close, distill per the retention model (doc 12): mark the `FINDING-*.md`
RESOLVED+REVIEWED, record ADR acceptance if that was a target, append a
`work/ledger.jsonl` line, and update the relevant PKL change log.

## Verdict / status vocabulary

Bound in `rules/ai-os-rules.yaml`:
- `valid_review_verdicts`: `ACCEPT`, `ACCEPT-WITH-CHANGES`, `BLOCK` (matches `AGENTS.md`).
- `valid_review_statuses`: `AWAITING_REVIEW`, `REVIEWED`, `DISPOSED`.

## Checker

`.ai-os/scripts/check_review_packet.py` (manifest-rooted, trigger-agnostic; run
manually / from a hook / in CI). It enforces:
- each `REV-*/` has a `request.md` with valid front-matter (required keys; status
  + verdict in-vocab);
- a `result.md` with a real verdict ⇒ `disposition.md` exists and the request is
  `REVIEWED`/`DISPOSED`;
- a `BLOCK`/`ACCEPT-WITH-CHANGES` verdict ⇒ a non-empty `disposition.md`;
- every `work/review/FINDING-*.md` still marked "queues for independent review"
  appears in some packet's `targets` (nothing flagged is left un-packeted);
- (warning) a packet `AWAITING_REVIEW` older than `review_staleness_days`.

## Related

`AGENTS.md` (reviewer role), `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`,
`.ai-os/templates/review-request.md` + `review-result.md`, `CLAUDE.md` "## Review",
doc 12 (retention/disposition), doc 08 (model-tier orchestration).
