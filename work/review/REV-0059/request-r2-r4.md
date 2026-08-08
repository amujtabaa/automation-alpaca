# Independent preflight request - WO-0152 E3 R2-R4 mandate schedule correction

Review only the exact R2-R4 composite named by
`WO-0152-RED-CANDIDATE-R2-R4-MANIFEST.md` on branch
`codex/arch-reset-2026-07-r1`.  Treat that manifest, accepted ADRs, active
WO-0152, retained R0 through R2-R3 packet chain, ratification/provenance, and
the frozen source files named by the manifest as authority.  Conversation
history and author notes are orientation only.

## Review boundary

This is a documentation-only re-gate of an already active test-only work
order.  The existing untracked partial E3 module is an isolated baseline, not
a candidate implementation or acceptance input; it must remain byte-identical.
Do not edit production code, test code, work orders, PKL, ledger, candidate
records, this request, or the manifest.  Do not run tests, database-capable
fixtures, SQL/DDL, network, broker, credential, runtime, CI, or coverage
commands.  Static code, file-level, hash, source, and diff inspection are
permitted.

Create only `work/review/REV-0059/result-r2-r4.md`.  It must state exact
manifest and candidate hashes, review base, the isolated partial-test hash,
evidence limits, findings, and final verdict.  Preserve every prior request,
manifest, disposition, and result unchanged.

## Required independent questions

1. Does R2-R4 replace only the nonconstructible mandate-fixture rule while
   retaining all R2-R3 environment, terminal, boundedness, and safety rules?
2. Is the fixed 32-entry pre-genesis schedule exact, closed, genuinely
   distinct, and sufficient for the ADR-required no-stream-reuse proof?
3. Is the one minter-loop exception narrowly bounded enough to construct all
   valid mandates without creating caller-shaped configuration, a production
   capability, or a general private test seam?
4. Do the AST and behavioral controls prove cardinality, identity, direct
   binding, loop shape, no post-genesis minting, and every stated bypass class
   without duplicating fragile integrity checks?
5. Does the public A -> B -> A-stream refusal control properly surface a real
   E2 semantic defect if present rather than silently weakening the ADR rule?
6. Is the partial test file accurately isolated rather than claimed absent or
   used as preflight evidence?  Are all current records/provenance exact and
   append-only where required?

Perform a bottom-up disproof pass before finalizing.  Do not force a finding.

For each concrete finding, provide location, requirement, static evidence,
impact, and smallest complete resolution.  End with:

Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT  
P0: n  
P1: n  
P2: n  
Unverified: list or none
