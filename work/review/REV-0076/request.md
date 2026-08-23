# REV-0076 request — WO-0168h frozen owner-state wire contract

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact candidate

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-owner-state-wire-r1`
- Base: `58f23ff9ea6d446379f7339075e1203c42a33e96`
- Candidate commit: `9f8cf21fe61c4746fad129d9ce374d82d3892f2a`
- Candidate tree: `daadd9124c3be7c475628efaa43de629fbde399c`
- Review diff: `58f23ff9ea6d446379f7339075e1203c42a33e96..9f8cf21fe61c4746fad129d9ce374d82d3892f2a`
- Primary artifact:
  `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`

Verify identities independently. Later commits do not inherit this verdict.

## Review posture

Re-derive from current code and the accepted predecessor contract. Do not trust the author's
inventory or completion claim. This is a documentation-only preflight: do not edit source, run
SQLite, install DDL, or create a result on a different candidate.

Treat as P0 any authorization leak into changed-DDL execution, SQLite-bearing tests, configured or
in-memory databases, runtime composition, credentials/network/broker/orders, R13-C serving
checkpoint authority, promotion, or master merge.

Treat as P1 any missing owner field, non-lossless current-state row, circular digest/proof binding,
unbounded or incomplete selection, history replay, generic/reflected serialization, second reducer,
ambiguous member order/tag/length/null/enum/commitment domain, constructor that cannot reproduce an
authentic owner, or mismatch with current source semantics.

## Required lenses

1. Account for all 57 `VenueRecoveryBook`, 20 `ExecutionAuthorityState`, and 13
   `AcquisitionControllerState` fields against current source.
2. Try to construct a legal current state that the wire cannot represent, and a malformed state the
   wire would accept.
3. Check every literal array length, source-order claim, optional group, enum spelling, row key,
   order, limit, and commitment/proof dependency for contradictions.
4. Verify the venue effect/current-attempt/closure/coverage/reconciliation/bootstrap/protection
   shapes are lossless without history.
5. Verify authority effect/claim/manual/grant/acquisition-slot shapes rebuild every derived map.
6. Verify acquisition controller/mandate/generation/stream/lineage rows handle LIVE, one targeted
   retired generation, unresolved predecessors, and targeted late facts without claiming equality
   with full-history seals.
7. Verify execution and protection proof arrays are complete and non-circular.
8. Check that the boundary to R13-C is implementable and that no proof is said to depend on a future
   digest containing that same proof.

## Evidence and result

Static inspection and pure parsing/count scripts are allowed. No SQLite-bearing test or changed-DDL
installation is authorized. Put the authoritative result only in
`work/review/REV-0076/result.md`, with each finding labeled P0/P1/P2, exact file:line, impact,
smallest complete root correction, and final verdict. If no findings remain, state
`P0=0/P1=0/P2=0` and what was independently verified.
