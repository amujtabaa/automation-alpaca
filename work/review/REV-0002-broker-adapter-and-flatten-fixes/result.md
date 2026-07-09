---
type: Review Result
rev_id: REV-0002
reviewer_model: <your model, e.g. gpt-5 / o3 / codex>
verdict: <ACCEPT | ACCEPT-WITH-CHANGES | BLOCK>
date: <YYYY-MM-DD>
---

# Review Result REV-0002 — broker-adapter fix + flatten reconciliation

> Reviewer: fill the front-matter (`reviewer_model`, `verdict`, `date`) and the
> sections below. A filled-in `verdict` (one of the three values, not the
> placeholder) is what signals the review is delivered. Do NOT edit `request.md`.

## Verdict
- **Overall:** `<ACCEPT | ACCEPT-WITH-CHANGES | BLOCK>`
- **Per target:**
  - `FINDING-alpaca-adapter-wrong-sdk-method` — `<verdict>` — gate may clear: `<yes|no>`
  - `FINDING-flatten-inv034-live-protection` — `<verdict>` — gate may clear: `<yes|no>`

## Findings
Severity: **P0** = blocking; **P1** = important (see `AGENTS.md`).

| ID | Severity | File:line | Evidence | Why it matters | Required action |
|----|----------|-----------|----------|----------------|-----------------|
| F1 | P0/P1 | `path:line` | <observed> | <impact> | <fix> |

## Could not verify
- <e.g. real-Alpaca-paper-API behavior of get_order_by_client_id, if you can't run the integration tests>

## Notes
<risks to watch, non-blocking suggestions>
