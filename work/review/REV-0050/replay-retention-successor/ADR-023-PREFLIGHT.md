# ADR-023 proposal pre-flight and checkpoint

Status: **READY FOR HUMAN RATIFICATION — NOT YET AUTHORITY**

## Exact state

- Branch: `codex/arch-reset-2026-07-r1`
- HEAD: `488ce0e7cb954d7b1d19c2bc0127a925e069ea58`
- Active work order: `WO-0148`
- Tracked/staged diff: empty
- Preserved untracked artifacts: unchanged; no cleanup or deletion performed
- Rejected implementation candidate remains frozen at HEAD

## Proposed decision

- Path: `work/review/REV-0050/replay-retention-successor/PROPOSED-ADR-023-bounded-market-occurrence-authority.md`
- SHA-256: `898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259`
- Size: 33,156 UTF-8 bytes / 481 lines
- Status inside document: `PROPOSED — NOT ACCEPTED AUTHORITY`

The proposal replaces the rejected aggregate-lifetime receipt map with a generation-global strict
source coordinate, constructor-derived canonical occurrence identity, an exact 19-part/480-byte
constant-size cursor commitment, fail-closed invalidation and exact next-epoch baseline, terminal
u64 exhaustion, a source-authoritative M2 restart fence, and structurally separate projection and
market reducers. It retains the accepted bounded in-memory market cache and optional-recorder
failure boundary. It adds no durable market inbox, database/schema work, runtime wiring, broker
activity, or M2 implementation.

## Critical review history

1. The first bounded-authority draft used a mandatory durable ingress. Static review returned
   P0=0/P1=5/P2=1 because generation was incompletely bound, identical sequence-less facts remained
   ambiguous, durable market history contradicted accepted persistence boundaries, invalid inputs
   did not clearly consume their cursor, and projection/market input remained conflated.
2. The strict-coordinate replacement removed the durable ingress and directly resolved all five
   classes. Mechanical reconciliation then found two process P1s: the exact WO/ADR/public-surface
   re-gate was not yet enumerated, and the goal draft still described durable ingress. Both were
   corrected.
3. Independent architecture review found four P1s: cursor reset across epoch recovery; undefined
   higher-sequence/lower-time handling; incomplete baseline halt/evaluation rules; and a boundedness
   test that covered only the ordinary path. All were corrected at the owning rules.
4. A final classification pass found one wording P1 that conflated coordinate-stale/malformed input
   with cursor-consuming contextual rejection. The classes and dispositions were separated.
5. Early exact-file Sol/Terra passes accepted the smaller draft, but a failure-first RED inventory
   then exposed an undefined bounded-work oracle. A separate implementation wargame exposed three
   further P1s: u64 terminal behavior, baseline economics, and incomplete disposition/alert mapping.
6. After those root corrections, exact-file reviews found and closed ambiguous ADR-021 supersession,
   baseline-entry epoch assignment, an open-ended cursor schema, missing independent known-answer
   controls, non-fail-closed call-graph resolution, restart replay across volatile cursor gaps, and
   contradictory epoch-versus-cursor precedence.
7. The next exact-file pass found and closed retained-current-epoch omission from the authenticated
   cursor, halted-latch recovery ambiguity, retained-cursor fence equality, and the initial-baseline
   predecessor exception. The cursor schema became exactly 19 parts / 480 bytes.
8. Three fresh final reviews of exact SHA-256
   `898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259` independently returned
   `ACCEPT`, each with P0=0/P1=0/P2=0. They confirmed exact testability, ADR-020/021/022 and WO-0148
   reconciliation, recovery-fence deferral to M2, all finding closures, HEAD, and empty
   tracked/staged diff.

These reviews were read-only static architecture/scope reviews. No database, SQL/DDL, broker,
Alpaca, network, runtime, or application/test execution was performed or relied upon.

## Goal refresh

- Path: `work/review/REV-0050/replay-retention-successor/GOAL-REFRESH-DRAFT.md`
- SHA-256: `B27146B24EF3B08D1315E1D56984236E1FBDCC8541A4055E8948A98458CE6EC2`
- Exact size: 3,894 characters / 3,900 UTF-8 bytes
- Static analysis: 973 estimated tokens; clarity 95/100; structure 75/100
- Scenario evaluation: `GOAL-REFRESH-EVAL.md`

The existing active goal's historical P1 paragraph is stale. The refreshed prompt remains
repository-driven and automatically advances after ratification, so it need not be replaced again
merely because the current decision gate closes.

## Exact next gate

No production, RED-contract, accepted-ADR, work-order, PKL, ratification-record, or public-surface
edit is authorized by this checkpoint. The next required action is exact human approval of the
proposal and its enumerated re-gate. After approval, the implementation seat must record the
ADR/WO/PKL chain, freeze replacement RED controls, and obtain independent exact-commit `ACCEPT`
before editing production code.

Recommended exact approval text:

> Approve proposed ADR-023 SHA-256 `898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259` and its “Exact WO-0148 re-gate required by ratification” section; authorize only the named ADR-023, ratification, active-WO, matching PKL, RED-contract, allowed application/test, review, evidence, branch-push, and exact-head-CI work needed to close WO-0148 under its existing safety boundaries; authorize no runtime wiring, persistent application-database or direct database work, broker/Alpaca/network activity, M2 implementation, master merge, deletion, or cleanup.
