---
type: Review Request
rev_id: REV-XXXX
title: <Short descriptive title>
status: AWAITING_REVIEW
targets: [e.g. WO-0007b, ADR-008]
human_gated_surfaces: []
commit_range: <start>..<end>
created: YYYY-MM-DD
---

## Your Role
You are the **independent review seat** (different model from the author on purpose). 
Follow the rules in `AGENTS.md` and `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`.
Produce findings only. Do not rubber-stamp.

## What You're Reviewing
<One paragraph summary>
Run this command for context: `git diff <commit_range>`

## Where to Look (Start Here)
- Specific file:line anchors
- Relevant tests and invariants

## Review Lenses (Optional)
Consider these perspectives if relevant:
- Correctness & Edge Cases
- Security / Data Integrity
- Performance & Scalability
- Maintainability
- ADR / PKL Consistency

## Threat Model and Stop Rule (Required — doc 20, adopted 2026-08-26)
- In scope: <who/what this change must withstand, e.g. accidents and non-evasive agent mistakes>
- Out of scope: <threat classes that become proposals for the human, never blocks>
- A P0/P1 requires a reproducible counterexample inside the threat model above, or proof that a
  named control cannot fail. Out-of-model concerns: record as threat-class proposals.
- Round cap: two per packet; round two re-examines round-one remediations only. Safety-invariant
  findings in product code are never capped.

## How to Respond
Create `result.md` in this folder using the result template.
Use verdicts: ACCEPT | ACCEPT-WITH-CHANGES | BLOCK
State everything you could not verify.
