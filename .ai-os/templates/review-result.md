---
type: Review Result
rev_id: REV-0000                 # MUST match the request in this folder
reviewer_model: <your model, e.g. gpt-5 / o3 / codex>
verdict: <ACCEPT | ACCEPT-WITH-CHANGES | BLOCK>
date: <YYYY-MM-DD>
---

# Review Result REV-0000 — <title>

> Reviewer: fill the front-matter (`reviewer_model`, `verdict`, `date`) and the
> sections below. A filled-in `verdict` (one of the three values, not the
> placeholder) is what signals the review is delivered. Do NOT edit `request.md`.
> Deposit this file as `result.md` in the same packet folder.

## Verdict
- **Overall:** `<ACCEPT | ACCEPT-WITH-CHANGES | BLOCK>`
- **Per target:**
  - `<WO/ADR/FINDING id>` — `<ACCEPT | ACCEPT-WITH-CHANGES | BLOCK>` — gate may clear: `<yes|no>`
  - `<...>`

## Findings
Severity: **P0** = blocking (gated-surface without approval, safety-invariant
violation, unreproducible "green"); **P1** = important (untested behavior change,
scope creep, boundary/formatter violation).

| ID | Severity | File:line | Evidence | Why it matters | Required action |
|----|----------|-----------|----------|----------------|-----------------|
| F1 | P0/P1 | `path:line` | <what you observed> | <impact> | <what resolves it> |

## Could not verify
- <anything you couldn't confirm from a clean checkout — e.g. real-broker-API behavior>

## Notes
<free-form: risks to watch, suggestions that are not blocking>
