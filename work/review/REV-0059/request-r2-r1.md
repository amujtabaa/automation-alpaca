# Independent preflight request - WO-0152 E3 R2-R1 activation-gate correction

Review only the exact R2-R1 composite named by
`WO-0152-RED-CANDIDATE-R2-R1-MANIFEST.md` on branch
`codex/arch-reset-2026-07-r1`. Treat that manifest, accepted ADRs, the current
WO-0152 draft, retained R0/R1/R1-R1/R2 material, ratification/provenance, and
the frozen source files named by the manifest as authority. Conversation
history and author notes are orientation only.

## Review boundary

This is a documentation-only pre-activation review. No E3 test module exists
yet. Do not edit production code, test code, work orders, PKL, ledger,
candidate records, this request, or the manifest. Do not run tests,
database-capable fixtures, SQL/DDL, network, broker, credential, runtime, CI,
or coverage commands. Static code, file-level, hash, source, and diff
inspection are permitted.

Create only `work/review/REV-0059/result-r2-r1.md`. It must state exact
manifest and candidate hashes, review base, evidence limits, findings, and
final verdict. Preserve every prior request, manifest, disposition, and result;
in particular, `result-r2.md` must remain absent because the first R2 preflight
was stopped before verdict.

## Required independent questions

1. Does R2-R1 preserve all earlier packets and the first R2 candidate as
   appropriately retained unaccepted/negative evidence, without inventing a
   result or acceptance for it?
2. Does it completely replace the stale R1 future activation condition with
   exact R2-R1 independent `ACCEPT` P0=0/P1=0, and prevent any earlier result
   from activating E3?
3. Does R2-R1 preserve every root-correct R2 semantic/static bound: one
   existing environment fixture, fixed six-step public sibling chain,
   pre-install checks, one copied literal venue installation, post-install pure
   bootstrap assertion, and no extra authority/capability?
4. Are the work-order lifecycle names, ratification/provenance, PKL, log, and
   ledger consistent with DRAFT/preflight-only status, no test implementation,
   and the unchanged paired E2/E3 93% exact-head closeout?
5. Does any replacement clause conflict with the safety core, accepted ADRs,
   coverage-order amendment, or current scope? Is a production/API change
   actually required?

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
