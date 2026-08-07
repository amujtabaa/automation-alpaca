# Independent preflight request - WO-0152 E3 R2-R3 correction

Review only the exact R2-R3 composite named by
`WO-0152-RED-CANDIDATE-R2-R3-MANIFEST.md` on branch
`codex/arch-reset-2026-07-r1`. Treat that manifest, accepted ADRs, the current
WO-0152 draft, retained R0/R1/R1-R1/R2/R2-R1/R2-R2 material,
ratification/provenance, and the frozen source files named by the manifest as
authority. Conversation history and author notes are orientation only.

## Review boundary

This is a documentation-only pre-activation review. The future E3 test module
must remain absent. Do not edit production code, test code, work orders, PKL,
ledger, candidate records, this request, or the manifest. Do not run tests,
database-capable fixtures, SQL/DDL, network, broker, credential, runtime, CI,
or coverage commands. Static code, file-level, hash, source, and diff
inspection are permitted.

Create only `work/review/REV-0059/result-r2-r3.md`. It must state exact
manifest and candidate hashes, review base, evidence limits, findings, and
final verdict. Preserve every prior request, manifest, disposition, and result;
in particular, `result-r2.md` and `result-r2-r2.md` must remain absent.

## Required independent questions

1. Does R2-R3 preserve every prior candidate/result as correct retained
   unaccepted or negative evidence, without inventing an R2/R2-R2 verdict?
2. Does it replace every active/nonhistorical activation predicate with exact
   R2-R3 independent `ACCEPT` P0=0/P1=0 while preserving dated history?
3. Does its one coherent static table permit every inherited exact fixture
   operation but reject every broader private/mutation/patch path?
4. Is the boundedness helper exact and constructible: precisely sixteen public
   target pairs, fourteen property shapes, two method shapes, `effect` and
   `observation_at` correctly trapped, no bounded direct reader overblocked,
   restoration on every exit, and meaningful trapped execution of the three
   named live public decisions?
5. Does it preserve all R2/R2-R1 sibling-history, setup-fixture, terminal
   certification, public-API, and paired E2/E3 93% closeout constraints?
6. Does any replacement clause conflict with the safety core, accepted ADRs,
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
