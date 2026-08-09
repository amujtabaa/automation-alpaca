# REV-0062 — independent review request for M1.5 Task A

Review type: architecture / human-gated ADR candidate
Candidate base: `5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`
Author seat: Codex Cloud candidate seat
Status: **READY FOR INDEPENDENT REVIEW**

## Reviewer instructions

Start from the exact Task A candidate commit and re-derive the decision from current authority.
Do not edit the candidate documents or `request.md`. Write findings only to `result.md`. For each
finding give `file:line`, why it matters, and what resolves it. End with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`, P0/P1/P2 counts, and anything not verified.

Review especially:

1. whether pure M1 and its public surface remain unchanged;
2. whether Alpaca Paper is unambiguously the sole M2–M8 mutation-eligible broker;
3. whether the overlay accidentally grants M2, DDL, broker, credential, runtime, or live authority;
4. whether every capital-relevant durable authority binds the immutable profile;
5. whether profile changes can bypass new-generation reviewed recutover;
6. whether market-data provenance is truly independent without weakening ADR-023;
7. whether capability evidence is sufficiently scoped and non-authorizing;
8. whether the clause-level preservation/supersession map is accurate and narrow;
9. whether provider-literal DDL is clearly blocked pending reconciliation; and
10. whether public-repository secret/private-material prohibitions are complete.

No new `INV-*` is introduced: this candidate defines prospective ADR obligations and does not amend
the runtime invariant registry. Probe the decision nonetheless with at least these hostile cases:

- a credential fingerprint rotates after a fill exists;
- query origin differs while trade origin matches;
- a Webull profile is presented during M6;
- two profiles both claim mutation eligibility in one generation;
- an Alpaca execution profile is paired with an independently committed market feed;
- a capability profile changes without a new application generation; and
- hydration finds a capital-relevant row with no profile commitment.

Verify the exact SHA-256 values in `candidate-manifest.sha256`. Human approval must later quote the
accepted exact hashes; a general positive reply is insufficient.
