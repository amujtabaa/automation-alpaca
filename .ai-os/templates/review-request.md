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

## How to Respond
Create `result.md` in this folder using the result template.
Use verdicts: ACCEPT | ACCEPT-WITH-CHANGES | BLOCK
