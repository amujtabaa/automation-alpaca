# REV-0076 R1 request — WO-0168h owner-state contract remediation

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact candidate

- Base: `58f23ff9ea6d446379f7339075e1203c42a33e96`
- Superseded candidate: `9f8cf21fe61c4746fad129d9ce374d82d3892f2a`
- R1 candidate: `1303ca9a23b5092f8a25804707d69b6e4a6a559d`
- R1 tree: `fd833ff641459e34c654b73736eff29d2a16e9dd`
- Diff: `58f23ff9ea6d446379f7339075e1203c42a33e96..1303ca9a23b5092f8a25804707d69b6e4a6a559d`
- Primary artifact:
  `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`

Verify all identities independently. The original request remains historical; this file supersedes
its candidate for the next review round.

## Reproduced findings corrected

R1 changes the contract at the root level:

1. acquisition claims now carry complete permit semantics; retained per-effect descriptors survive
   inactive successor slots;
2. LIVE and targeted-retired generations each require their matching stream route and complete
   prerequisite REQUEST/EFFECT/OWNER/ROOT/FACT lineage;
3. execution `SeenFact` admits the exact canonical human/broker union; root-head empty prefixes
   use exact bytes; fact-specific proofs are no longer mandatory current-scope members;
4. bootstrap and venue-transition arrays are literal and use a new bounded semantic proof without
   the legacy history-bound whole-book digest;
5. venue selection is explicitly account-wide, and bounded source ordinals preserve
   behavior-significant effect/owner discovery order;
6. pending-operation absence is null and enum `NONE` is rejected for that field;
7. closed enums, numeric lower bounds, literal wrappers, family order, direct-row union, absence
   keys, commitment domains/preimages, and acyclic derivation order are explicit; and
8. the work order now has machine-checkable allowed/forbidden paths.

Do not assume these corrections are complete. Re-run all request.md lenses and try to disprove each
claimed fix with a current-source counterexample.

## Boundary

Documentation-only review. No source authorization exists unless R1 receives `ACCEPT` with
`P0=0/P1=0`. Do not run SQLite or install changed DDL. No configured/in-memory database, runtime,
credentials, network, broker, orders, R13-C serving payload, promotion, or master merge.

Return exact P0/P1/P2 findings and verdict. The authoritative accepted result, if any, belongs in
`work/review/REV-0076/result.md`; do not edit either request.
