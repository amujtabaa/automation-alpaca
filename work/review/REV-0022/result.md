---
type: Review Result
rev_id: REV-0022
reviewer: GPT-5 (Codex) via the chatgpt-codex-connector GitHub App — automated adversarial PR review
review_venue: PR #5 (amujtabaa/automation-alpaca), commits e50153d..f99fa17
verdict: ACCEPT-WITH-CHANGES (constructed — see "Verdict basis")
findings_total: 16
date: 2026-07-11
ingested: 2026-07-12 (by the implementer session, per Ameen's option-1 decision)
---

# REV-0022 Result — ADR-009 Signal Seat, reviewed adversarially on PR #5

## Verdict basis (read this first)

This packet was never dispatched in the usual paste-the-request form. Instead, the same reviewer
model (GPT-5/Codex) reviewed the ADR and its WO bundle **adversarially and independently on PR #5
itself**, across **seven review passes** tracking every push (reviewed commits `e50153d`, `85443fb`,
`c3bd038`, `8c7c893`, `25590a7`, `0ddabc5`, + trailing findings on the WO-0104 fix), producing
**16 inline findings** — each re-derived from the as-built code (`.importlinter`, `app/api/deps.py`,
`app/main.py`, `app/store/core.py:641+`, `app/models.py::SellReason`, `cockpit/api_client.py`),
not from the author's claims. Every finding was verified against the code by the implementer before
any change, and every change was applied in-flight; the reviewer raised no further findings after
the final fix commit (`f99fa17`) through merge (`c4271d8`).

The reviewer never emitted a formal verdict token, so **ACCEPT-WITH-CHANGES is constructed** from
its observed behavior: 16 change-requests, 16 applied, zero open at merge. Ameen adjudicated that
this record satisfies the independent cross-model review requirement for ADR-009 (decision recorded
2026-07-12, this packet's disposition).

## Findings ledger (all applied)

| # | Sev | Finding (one line) | Fixed in |
|---|-----|--------------------|----------|
| 1 | P1 | `.importlinter` contract 5 enumerates route modules — a new `routes_signals` would silently evade the route→facade gate | `85443fb` |
| 2 | P2 | Global `signal_id` dedupe lets producer A collide/quarantine producer B's signals → key on `(producer_id, signal_id)` | `85443fb` |
| 3 | P1 | Approvals need operator-only auth — `get_actor` is an audit label, not authentication; a producer could convert its own signal | `c3bd038` |
| 4 | P2 | Post-breach signals were still event-appended → a quarantined producer could grow the append-only log unboundedly | `c3bd038` |
| 5 | P1 | `create_app` mounts routers explicitly — WO-0102 couldn't mount `/signals` within scope | `c3bd038` |
| 6 | P1 | Body-supplied `producer_id` lets A forge B's identity/namespace → derive from the API key, reject mismatch | `19ebd50` |
| 7 | P1 | No sell-direction conversion origin exists (`SellReason` = {manual_flatten, protection_floor}) → spec `SellReason.SIGNAL` path | `19ebd50` |
| 8 | P1 | Producer-key scoping is worthless while command routes accept NO credential — require operator credential on all mutating routes | `8c7c893` |
| 9 | P1 | WO-0102 scoped store/events but no facade seam — implementer forced to break contract 5 or use the `get_store` loophole | `8c7c893` |
| 10 | P1 | Candidate path binds `suggested_quantity`/`suggested_limit_price` — producer sizing would become binding → operator-confirmed qty/price at approval | `8c7c893` |
| 11 | P1 | The auth flip would 401 the cockpit's kill-switch/flatten between WO-0102 and WO-0103 → credential plumbing ships with the flip | `25590a7` |
| 12 | P2 | "No special status after approval" severed the signal→order audit chain → correlation survives (`SIGNAL_APPROVED` ↔ intent id ↔ `(producer_id, signal_id)`) | `25590a7` |
| 13 | P2 | Flag enabled between WO-0102 and WO-0104 = unrailed flood window → interim hard ingest ceiling ships with the endpoint | `0ddabc5` |
| 14 | P2 | Producer-quarantine release (required human action) had no browser path → cockpit release control scoped into WO-0104 | `0ddabc5` |
| 15 | P1 | WO-0104 granted the cockpit release control in allowed_paths while forbidding `cockpit/**` — scope deadlock | `f99fa17` |
| 16 | P1 | WO-0104's release route had no facade seam in scope (contract 5 unimplementable) | `f99fa17` |

## Coverage vs. the request's five questions

1. **Invariant preservation** — attacked and hardened (findings 3, 6, 7, 8, 10: L0-gate bypass via
   missing auth, identity forgery, advisory-sizing violation, undefined sell origin). The INV-1..9
   mapping's INV-7 row was strengthened separately by Ameen's recorded asymmetry decision.
2. **Human-gate integrity** — findings 3, 8, 11 directly; the gate survives with credential
   separation and no lockout window.
3. **Rails sufficiency** — findings 2, 4, 6, 13 (id-collision games, log flooding pre- and
   post-quarantine, identity forgery); the INV-7 asymmetry remedy was folded into the ADR text
   during the review window.
4. **Boundary hygiene** — findings 1, 5, 9, 15, 16 (contract-5 enumeration, mount scope, facade
   seams, scope self-consistency).
5. **Options analysis** — no findings raised against Options B–D framing across seven passes.

## Residual notes for the record

- The final fix commit `f99fa17` received no explicit clean pass before merge; it was a 3-line
  scope-consistency fix responding to findings 15/16, and no further reviewer activity occurred in
  the ~18 hours before merge.
- Scope-growth observation (implementer, endorsed for planning): the operator-credential work now
  folded into WO-0102 is a candidate to split into a preceding WO-0102a at activation time.
