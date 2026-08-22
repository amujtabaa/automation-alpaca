---
type: Review Result Addendum
rev_id: REV-0071
status: BLOCK
reviewed_commit: 57d795aa9da0e96638fd89ba9243ae9819cc37cb
reviewed_tree: e9a1dc259c970d3366161fcf2129e251213280f8
date: 2026-08-22
---

# REV-0071 — terminal-candidate adversarial result

Three fresh read-only adversarial seats reviewed the exact terminal candidate. One seat returned
`ACCEPT`, one returned `ACCEPT-WITH-CHANGES`, and one returned `BLOCK`. The combined verdict below
uses the strongest substantiated severity. These were in-process adversarial agents under Ameen
Mujtabaa's explicit review-process authorization, not external cross-model reviewers.

## Findings

### P0-1 — controller quarantine does not centrally stop outbound authority

`venue_effect` and `dispatch_claim` validate controller identity/head but not controller integrity,
and a retained `protection_authority` row may still replace its state commitment while the
controller is quarantined. Reproduced live: current-head effects/claims and protection state
updates could leave a non-serving controller. Resolve at every outbound authority boundary with
one exact current `CONSISTENT` controller requirement, including all protection updates.

### P0-2 — accepted acquisition-root routing is neither total nor generation-exact

A fact/root can advance controller economics without an effect/owner route, and a LIVE successor
effect can bind an owner/root retained under its retired predecessor generation. Reproduced live.
Resolve with one immutable direct acquisition-root route, exact effect-owner-root-generation
foreign keys, and a sticky reconciliation-required controller state when broker truth arrives
without that route. Broker truth must remain retained rather than being rejected or hidden.

### P0-3 — protection authority can name a retired acquisition generation

The stream foreign key authenticates a historical generation route, but protection insertion does
not require that route to equal the controller's exact current LIVE generation. Reproduced live.
Resolve by binding every protection insert/update to the exact current controller head and live
generation while preserving retired stream history as non-serving evidence.

### P0-4 — INVALIDATED authority can be relabeled as ACCEPTANCE_CLOSED

The closure-kind trigger accepts `ACCEPTANCE_CLOSED` when an effect is either CLOSED or
INVALIDATED. Reproduced live. Resolve by allowing that closure kind only for exact CLOSED authority
and by creating a distinct append-only invalidation terminal atomically from exact contradiction
evidence.

### P1-1 — schema verification trusts a spoofable metadata row

`verify_schema_connection` accepts a database containing only a matching `schema_meta` table and
row. Reproduced live. Resolve by fingerprinting and checking the complete application-owned
SQLite catalog, both during installation and on every verified reopen.

## Verdict

`BLOCK` — combined P0=4, P1=1. Commit `57d795aa...` must not close WO-0166.

No seat edited or pushed repository files. No configured database, migration, runtime,
credentials, broker/network call, order, promotion, or merge was exercised.
