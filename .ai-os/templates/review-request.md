---
type: Review Request
rev_id: REV-0000
title: <one line — what is under review>
status: AWAITING_REVIEW          # AWAITING_REVIEW | REVIEWED | DISPOSED
targets: []                      # WO / ADR / FINDING ids under review, e.g. [WO-0007b, ADR-008]
human_gated_surfaces: []         # from the CLAUDE.md safety-core list, e.g. [manual-flatten, order-submission]
commit_range: <base>..<tip>      # the exact commits under review (git range or space-separated SHAs)
reviewer_model: null             # filled by the reviewer, e.g. gpt-5 / o3 / codex
verdict: null                    # filled by the reviewer: ACCEPT | ACCEPT-WITH-CHANGES | BLOCK
created: <YYYY-MM-DD>
---

# Review Request REV-0000 — <title>

## Your role
You are the **independent review seat** — a different model from the author, on
purpose. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md` and follow them verbatim:
re-derive from the code in front of you, don't rubber-stamp, **produce findings
only — do not push fixes**. In-process (same-author) validation does not count as
independent review; that is why this exists.

You have the full repository. The pointers below are where to START, not a fence —
follow your own leads.

## What you're reviewing
<1–3 sentences: what changed and why. Name the WO/ADR/finding.>

- Commits: `commit_range` above. See the diff with:
  ```
  git log --oneline <base>..<tip>
  git diff <base>..<tip> -- <paths>
  ```
- The author's own writeup(s): `<work/review/FINDING-*.md and/or work/completed/keep/WO-*/…>`
  (read these to see what the author claims — then verify it independently).

## Where to look (curated pointers)
Read these first, with the specific thing to check for each:
- `<path:line>` — <what to verify here>
- `<docs/adr/ADR-NNN-*.md>` — <the decision to pressure-test; is it sound + consistent?>
- Invariants: `<docs/INVARIANTS.md INV-NNN>` / `<CLAUDE.md safety item>` — quote + check the code honors it.
- Pinning tests: `<tests/…>` — confirm they can actually fail (not tautological) and cover both stores where relevant.

## Specific risks to probe
Concrete questions, one per target/risk (be adversarial — assume the author
rationalized past something):
1. <risk / question>
2. <risk / question>
3. <anything the author flagged as "unverified" / "residual risk" — verify or refute it>

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS packet folder**
and fill it in. Do not edit `request.md`. Use the findings table and end with a
verdict `ACCEPT | ACCEPT-WITH-CHANGES | BLOCK` plus, for each target, whether its
CLAUDE.md "queues for independent review" gate may clear. State anything you could
not verify.
