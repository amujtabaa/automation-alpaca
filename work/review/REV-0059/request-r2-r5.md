# Independent preflight request - WO-0152 E3 R2-R5 duplicate-stream probe correction

Review only the exact R2-R5 composite named by
`WO-0152-RED-CANDIDATE-R2-R5-MANIFEST.md` on branch
`codex/arch-reset-2026-07-r1`. Treat that manifest, accepted ADRs, active
WO-0152, retained R0 through R2-R4 packet chain, ratification/provenance, and
the frozen source files named by the manifest as authority. Conversation
history and author notes are orientation only.

## Review boundary

This is a documentation-only re-gate of an already active test-only work
order. The existing untracked partial E3 module is an isolated baseline, not a
candidate implementation or acceptance input; it must remain byte-identical.
Do not edit production code, test code, work orders, PKL, ledger, candidate
records, this request, or the manifest. Do not run tests, database-capable
fixtures, SQL/DDL, network, broker, credential, runtime, CI, or coverage
commands. Static code, file-level, hash, source, and diff inspection are
permitted.

Create only `work/review/REV-0059/result-r2-r5.md`. It must state exact
manifest and candidate hashes, review base, isolated partial-test hash,
evidence limits, findings, and final verdict. Preserve every prior request,
manifest, disposition, and result unchanged.

## Required independent questions

1. Does R2-R5 replace only the R2-R4 duplicate-stream probe construction gap
   while retaining the positive 32-entry schedule and every R2-R3/R2-R4
   fixture, boundedness, provenance, and safety boundary?
2. Is the separate zero-argument probe fixture the smallest authentic way to
   construct a fresh-ID, fresh-binding, A-stream-reuse mandate without making
   the schedule ambiguous, caller-shaped, or a general private seam?
3. Do the exact source controls prove exactly two and only two private minter
   sites, their distinct lexical shapes, fixed probe identity/stream relation,
   no post-genesis invocation, and all named bypass refusals?
4. Does the public A -> B -> duplicate-A-stream control isolate stream reuse
   from duplicate mandate/binding, scope, session, compatibility, stale-head,
   and other refusal paths? Is its E2-stop boundary honest if current behavior
   admits the probe?
5. Are the R2-R4 independent result, partial baseline isolation, current
   records, append-only provenance, scope, and paired 93% closeout reconciled
   exactly?

Perform a bottom-up disproof pass before finalizing. Do not force a finding.

For each concrete finding, provide location, requirement, static evidence,
impact, and smallest complete resolution. End with:

Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT  
P0: n  
P1: n  
P2: n  
Unverified: list or none
