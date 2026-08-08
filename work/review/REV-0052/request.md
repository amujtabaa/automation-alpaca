# WO-0149 corrected-specification final preflight

Status: **INDEPENDENT PLANNING / ACTIVATION REVIEW**

Candidate: `work/queue/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md`

Candidate SHA-256: `8257907E9DC0772D8E419696FA8A0B7BFB8BA13BCCD4E464814314CF9B275D47`

Activation base: `2462fb557172dd28a7475a763eca0b440c0298e3`

This is a new review of the corrected documentation-only candidate. Application and test
implementation remains explicitly unauthorized. The prior `REV-0051/result.md` is retained
unchanged for its reviewed candidate; a separate fresh Sol rerun found four P1 specification gaps,
which this candidate claims to resolve. Re-derive the answer from current authority and the exact
candidate rather than relying on either earlier verdict.

## Required authority packet

Read only the smallest useful packet:

1. `AGENTS.md`, the permanent safety core in `CLAUDE.md`, and the Fable-v3 required-block grammar;
2. this candidate and `work/review/REV-0051/`;
3. accepted ADR-020 through ADR-023, their ratification index, and the acquisition/cross-side domain
   sections; and
4. the relevant public M1C/M1D interfaces in `authority.py`, `venue.py`, and `protection.py`, plus
   predecessor work-order contracts as necessary.

## Required disproof pass

Attempt to establish that one of these four repaired roots is still incomplete, inconsistent, or
outside accepted authority:

1. An exposure-increasing BUY `SUBMIT` or `REPLACE` can still be created or finally claimed from a
   caller-shaped request, or a valid target-derived BUY `CANCEL` is accidentally blocked despite its
   inherited safety role.
2. The preemption latch fails to become atomic, a cancellation still requires an all-leg sweep, a
   cursor can lose or repeat a current leg, or a SELL can release before every relevant parent is
   exactly `CLOSED`.
3. The path allowlist prevents the promised activation/closeout records, permits a historical rewrite
   of WO-0148 or retained evidence, or lets activation-only records drift into later implementation.
4. The Fable task-start/gate grammar remains incomplete or internally contradicts documentation-only
   activation, RED-first implementation, or the required evidence path.

Also recheck the original core boundaries: distinct immutable acquisition/protection authority,
composite currentness at create/final claim, one-fold first-fill integration, correction/bust and
late-fill recovery, no audit/private/test seam, pure I/O-free scope, no accepted-ADR conflict, and
clear separation of future implementation from this activation.

## Boundaries and output contract

This is a findings-only, static review. Do not edit source, tests, the candidate, work orders,
accepted authority, PKL, ratification, ledger, or this request. Do not run tests or application code;
do not execute SQL/DDL, database tooling, broker/Alpaca/network activity, or Git mutation. Do not
commit, push, merge, delete, or clean.

Write only `work/review/REV-0052/result.md`. Each finding needs priority, exact location,
evidence, concrete effect, and smallest complete resolution. End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

Activation may proceed only if this exact candidate receives `ACCEPT` with P0=0 and P1=0. An
ACCEPT grants no implementation authority.
