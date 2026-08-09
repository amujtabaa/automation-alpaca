# REV-0063 - focused independent remediation-03 re-review request

Reviewer role: a fresh independent review context. Preserve `result.md`,
`result-remediation-01.md`, and `result-remediation-02.md` unchanged. Review
the exact current head supplied by the launch message and write findings only
to `work/review/REV-0063/result-remediation-03.md`. Do not edit the candidate,
the manifest, the active work order, a prior result, or the disposition.

## Exact review target

Verify the current branch and supplied base/commit before review. Rehash every
manifest-covered path from the exact file bytes; independently hash the
self-excluded manifest and proposed ADR. Report all actual identities and
hashes. Treat `result.md`, `result-remediation-01.md`, and
`result-remediation-02.md` as immutable negative provenance, never as an
acceptance verdict.

## Required disproof pass

1. Re-derive the `*_origin` grammar without a URL library. Attempt the
   prior boundary spellings (`https://127.1`, `https://[0:0:0:0:0:0:0:1]`, and
   `https://%65xample.com`), malformed labels, an explicit `:443`, invalid
   retained ports, and valid lower-ASCII DNS names. Confirm that the rule
   supplies a single accept/reject answer and literal bytes for every allowed
   value, with no parser-selected normalization.
2. Reconstruct both commitment payloads independently from the ADR's field
   order, framing, text/identity/digest/origin rules. Confirm output exclusion,
   opaque-ID behavior, known answers, and mutation controls remain exact.
3. Verify the ratification contract routes only through the named terminal
   `work/review/REV-0063/result-remediation-03.md`. Confirm all earlier
   reviewer results remain audit provenance, are not silently removed or
   treated as `ACCEPT`, and cannot be substituted for the terminal accepting
   verdict/hash.
4. Re-check Alpaca Paper M2--M8 preservation, M1 closure/M2 inactivity,
   single mutation-eligible profile, market-source separation,
   capability-evidence sequencing, no secret/public-repository leak, and the
   prohibitions on runtime work, credentials, live trading, routing/failover,
   and Webull/FIX/IBKR/Robinhood/Tradier implementation.

Use the original request's severity/result format. State unverified gates. An
`ACCEPT` is permitted only if P0=0 and P1=0. This is an independent
findings-only review, not an invitation to revise the candidate.
