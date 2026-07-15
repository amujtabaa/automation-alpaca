---
type: Review Result
rev_id: REV-0027
reviewer_model: Claude Opus (fresh-context in-session subagent) + Codex GPT-5 (GitHub-app, 11 rounds)
reviewed_commit: 5a93f73
verdict: ACCEPT-WITH-CHANGES
date: 2026-07-15
---

# Review Result — REV-0027 (WO-0102 code)

**Verdict: ACCEPT-WITH-CHANGES.** No P0/P1 defect in the WO-0102 surface. One P2
(shared-infrastructure trap for WO-0103) and two P3s, all folded (see disposition).

## Opus deep-dive findings

### F-1 (P2, CONFIRMED) — operator-enforcement middleware prefix-skips the whole `/api/signals*` subtree
`app/main.py` skipped operator enforcement on `path.startswith("/api/signals")`. Correct
for the producer POST, but it also (a) would leave WO-0103's operator-only
`POST /api/signals/{producer}/{signal}/approve|reject` unauthenticated by the middleware
and (b) never stamp `request.state.authenticated_actor`, so `get_actor` would fall back to
the caller-controlled `X-Actor` — making the approval audit (who authorized a real order)
spoofable. This structurally reintroduces the round-5 actor-spoofing hole for the signal
approval audit before approve/reject are even mounted.
**Fix:** narrow the skip to the exact producer ingest (`POST /api/signals`); all other
`/api/signals*` routes now pass through the operator branch and get the principal stamped.

### F-2 (P3, CONFIRMED) — quarantine records store a non-normalized `symbol`
The validation-quarantine path stored `symbol` verbatim (e.g. `"aapl"`) while the store's
`?symbol=` filter normalizes to upper-case, so a quarantined record was unfindable by symbol.
**Fix:** normalize (strip+upper) on the quarantine path.

### F-3 (P3, PLAUSIBLE) — synthetic `malformed-<hash>` identity shares the wire `signal_id` namespace
`malformed-<sha256>` matches the wire pattern `^[A-Za-z0-9_-]+$`, so a producer could (in
principle) forge a colliding well-formed `signal_id`. Self-namespaced (same producer) and
requires predicting one's own body hash — low risk.
**Fix:** use a `:` separator (`malformed:<hash>`) that the wire pattern cannot express, making
collision structurally impossible.

## Areas traced and found sound (no defect)

UTF-8/surrogate poisoning (round-10 fix holds on both paths); dual-store parity (both delegate
to identical `plan_signal_ingest`); dedupe/replay (netstring key injective, raw_fields folded
into hash, idempotent-replay emits no event, conflict audit-only); projector terminal latching
(round-8 guard correct); lazy expiry on every echo path; auth matrix (401 vs 403, constant-time,
byte-safe, injected-Settings overlap re-checked); A-1 launch/bind (module `app` undefined under
flag; mint bind-bound; honest-scope documented); freshness/TTL (A-3 server-capped `expires_at`,
restart-stable, `cycle_budget_limit` stamped on exactly the attributable rejections).

## Codex GitHub-app stream

11 commit rounds (cc346b1..5a93f73). Findings folded round-by-round: auth bypasses + bind
guarantee (r1-2), dedup integrity + input strictness (r3), malformed→quarantine-as-a-class (r3),
whitespace/wrong-role/default-status (r4), X-Actor principal binding + non-ASCII creds (r5),
dual-store parity + rails-async + advisory nulling + bind-bound capability (r6), projector
terminal-state + freshness preservation + non-ASCII overlap (r8), invalid-Unicode read-path +
out-of-range TTL + injected-overlap (r10). Final rounds (7, 9, 11): no findings.
