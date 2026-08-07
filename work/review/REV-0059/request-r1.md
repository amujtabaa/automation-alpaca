# Independent preflight request — WO-0152 E3 R1 RED contract

Review only the exact R1 candidate named by
WO-0152-RED-CANDIDATE-R1-MANIFEST.md on branch
codex/arch-reset-2026-07-r1. Treat that manifest, accepted ADR-020 R2,
ADR-021 R2, ADR-023 R1, current WO-0152 draft, retained WO-0151 closeout,
ratification/provenance, and the frozen source files named by the manifest as
authority. Conversation history and the author’s notes are orientation only.

## Review boundary

This is a documentation-only, pre-activation review. No E3 test module exists
yet. Do not edit production code, test code, work orders, PKL, ledger, or
candidate records. Do not edit this request or the R1 manifest. Do not run
tests, database-capable fixtures, SQL/DDL, network, broker, credential,
runtime, CI, or coverage commands. Static code, file-level, hash, source, and
diff inspection are permitted.

Create only work/review/REV-0059/result-r1.md. The artifact must state the
exact manifest and candidate hashes, review base, evidence limits, findings,
and final verdict. Do not overwrite the retained R0 result.md.

## Required independent questions

1. Does R1 retain R0 as negative preflight evidence, preserve run #741 as
   functional/static success but coverage-only negative evidence, leave
   WO-0151 in REVIEW, retain the 93% paired closeout, and prevent premature
   M1 closeout?
2. Are the two new R1 exceptions actually necessary, constructible, and
   smallest-complete: one lexical private dual-binding minter call for fixed
   pre-genesis A/B/C mandates, and one prechecked temporary private venue
   closure under a restored certification hook?
3. Does either fixture accidentally manufacture execution, controller,
   currentness, effect, claim, broker, runtime, persistence, actor, or public
   API authority?
4. Is the terminal-parent fixture constrained to the exact public
   claim/discovery/terminal-observation lifecycle, an OPEN target parent,
   exact effect/claim/scope and fixed proof binding, flat consistent
   execution, clear reconciliation, and a copied authority whose only changed
   coordinate is venue?
5. Does the contract avoid prohibited history scans, private production
   attribute reads, opaque forging, dynamic lookup, existing test helpers,
   private access outside the exact exceptions, post-setup mutation, and
   unbounded operations?
6. Is the proposed self-source AST allowlist exact enough to distinguish the
   three setup fixtures, the lone private minter call, the lone private venue
   reducer call, the lone temporary hook patch, and every prohibited
   counterpart?
7. Are the resulting A/B/C, late retired fact, invalid input, currentness,
   claim, stateful, replay-model, boundedness, and test-owned sensitivity
   controls behavior-first and constructible through public contracts after
   setup?
8. Does any R1 requirement conflict with accepted ADRs, the permanent safety
   core, or the coverage-order authorization? Is any unapproved production/API
   expansion needed?

## Finding format

For each concrete finding:

### [P0|P1|P2] concise title

- Location
- Requirement
- Evidence: static reasoning or reproduced-live
- Impact
- Smallest complete resolution

Perform a bottom-up disproof pass before finalizing. Do not force a finding.

End with:

Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT  
P0: n  
P1: n  
P2: n  
Unverified: list or none

