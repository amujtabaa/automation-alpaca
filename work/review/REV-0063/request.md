# REV-0063 — independent clean-room review request

Reviewer role: independent architecture/safety review seat. You did not author
the candidate and must re-derive conclusions from the listed current-master
authority and exact candidate files. Produce findings only; do not edit any
candidate file, do not change `request.md`, and do not implement a fix.

## Review target

- Branch and exact candidate commit are supplied by the review launcher.
- Base master: `5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`.
- Semantic candidate manifest:
  `work/queue/M1-5-BROKER-ALIGNMENT/AUTHORITY-MANIFEST.sha256`.
- Proposed ADR body:
  `work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md`.
- Review output you own: `work/review/REV-0063/result.md`.

Read first: `AGENTS.md`, `CLAUDE.md`, ADR-020 through ADR-023, the ratification
index, the M1 handoff, current `pkl/project/goals.md` and architecture map,
`04-persistence-and-cutover.md`, `06-roadmap.md`, and the manifest-covered
candidate. Do not consult or adopt the abandoned Cloud PR #12 candidate.

## Required lenses

1. Alpaca Paper M2–M8 remains exact and live trading/Webull authority is not
   accidentally introduced.
2. M1 stays unchanged; M2/DDL/database/runtime/credential/broker activities
   remain inactive and unclaimed.
3. Exactly one immutable selected profile per generation and exactly one
   mutation-eligible profile are unambiguous; no hot swap, simultaneous profile,
   routing, failover, or cross-broker inventory leaks in.
4. Every capital-relevant durable authority is bound, external identifiers are
   profile-scoped, historical binding is retained, and recutover is the only
   material change route.
5. Execution profile and market-data source profile are separate; ADR-023
   source/stream safeguards remain intact.
6. Capability profiles are evidence-gated; no secret/public-repository leak is
   introduced.
7. Supersession is narrow: selected Paper values and fail-closed checks survive,
   while provider-literal permanent-DDL inference is resolved.
8. M2/M9 obligations can fail and refuse rather than merely describe intent;
   manifest covers every file that changes ratified meaning; hash/ratification
   flow prevents drift.

## Findings and verdict contract

For every finding, give severity (`P0`, `P1`, or `P2`), exact file and line,
why it matters, and the smallest resolution. Separate findings from unverified
checks. End with exactly one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or
`ACCEPT`, followed by P0/P1/P2 totals. `ACCEPT` requires P0=0 and P1=0.

Record SHA-256 values actually reviewed for the manifest and proposed ADR in
your result. If a requested check cannot be run, say so; do not invent
independence or acceptance.
