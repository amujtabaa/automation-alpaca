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
- Acceptance criteria and invariants: <closed list or exact governing references>
- Permitted evidence: reproducible runtime evidence, source/contract proof, mutation evidence, or
  another failure-capable form appropriate to the claim.
- A P0/P1 may show an acceptance/scope violation, in-model counterexample, non-failing control,
  remediation regression, or product safety/data-integrity defect. Truly out-of-model concerns
  are threat-class proposals.
- Round cap: two per packet; round two examines round-one remediations and regressions they
  introduce. The cap never forces acceptance; `ACCEPT-WITH-CHANGES` requires zero open P0/P1.

## How to Respond
Create `result.md` in this folder using the result template.
Use verdicts: ACCEPT | ACCEPT-WITH-CHANGES | BLOCK
State everything you could not verify.
