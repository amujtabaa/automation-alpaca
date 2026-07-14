---
type: Module Knowledge
title: Signal Seat — external signal producers (contract summary)
status: draft
authority: medium
owner: Ameen
last_verified: 2026-07-14
tags: [signal-seat, architecture, boundaries, safety]
source_refs: [docs/adr/ADR-009-signal-seat-boundary.md, docs/spec/signal-seat/00-overview.md]
supersedes: []
superseded_by: null
---

# Signal Seat — external signal producers (contract summary)

## Summary

External agentic producers (untrusted advisors, out-of-process) may POST signal proposals to the
backend over an authenticated HTTP contract; a proposal becomes an order intent **only** through
per-signal human approval (trust level L0). **GATE STATE (2026-07-14): ADR-009 is Proposed — its
acceptance was RESCINDED after the formal REV-0022 review returned BLOCK (4 P1s: credential/
transport boundary, non-atomic conversion, TTL/classification bounds, unbounded audit). Amendments
A-1..A-4 drafted; the REV-0024 re-review confirmed A-2/A-3 CLOSED (atomic conversion, server-owned
freshness) but A-1/A-4 NOT — re-remediated 2026-07-14 (A-1 clause 6 backend-owned launch for F-001;
A-4 non-refilling invalid budget + rails-presence enablement gate for F-004). Nothing below is
implementable until REV-0025 clears the re-remediation; WO-0102..0104 stay re-gated.** ADR-009
(Proposed) is the decision; the
draft contract is `docs/spec/signal-seat/` (WO-0101 output — DRAFT input to the remediation).
Implementation: WO-0102 → WO-0103 ∥ WO-0104, all RE-GATED pending remediation + re-review.

## Rules / facts

- Identity: `producer_id` derives from the API key server-side, never from the request body;
  dedupe/idempotency key is `(producer_id, signal_id)`.
- Role separation: producer keys are ingestion-scoped (`POST /api/signals` only); approve /
  reject / producer-release are operator-credential-only. Operator-auth enforcement on **every
  sensitive route — reads included** (not narrowed to mutating command routes; ADR-009 A-1.3,
  REV-0024-F-003) flips on with the `signal_seat_enabled` flag, together with the cockpit
  credential plumbing (no operator lockout window). The proxy-private bind is enforced through a
  **backend-owned launch path** (`python -m app`) — an in-app setting check can't observe the real
  uvicorn bind (ADR-009 A-1 clause 6, REV-0024-F-001).
- Lifecycle: RECEIVED → QUARANTINED | EXPIRED | REJECTED | APPROVED; terminal is terminal;
  approval is **atomic with conversion** (no approved-but-unconverted state); no event ordering
  can approve an expired/quarantined signal.
- Events: `SIGNAL_*` / `PRODUCER_*` are first-class append-only ExecutionEvents; signal state is
  replay-reconstructable; the position fold consumes only `FILL`, so signal events are
  structurally position-invisible.
- Sizing: producer suggestions are display-only; the dispatched order carries the
  operator-confirmed quantity/limit price from the approval payload.
- Conversion is direction-aware: buys mint a `Candidate` (strategy="signal"), sells a
  `SellIntent` with `SellReason.SIGNAL` (pauses under the kill switch; no manual-flatten-style
  bypass). Kill switch/Halted block conversion; in `Reducing` only risk-reducing signals convert
  (within-position sells; classification conservative toward convertibility, the quantity-aware
  risk gate stays binding; blocked conversions are operator-visible — recorded human decision).
- Rails: TTL/staleness quarantine at ingest; per-producer **refilling rate bucket** (bounds
  throughput) **plus a non-refilling invalid/conflict budget** (bounds storage — the refilling
  bucket alone lets paced-at-refill hostility append forever; ADR-009 A-4, REV-0024-F-002); either
  breach → producer quarantine with operator release (browser control required, resets the budget);
  post-quarantine ingress is boundary-rejected with epoch-bounded coalesced audit — the event log
  stays bounded under indefinite flood. **No interim ceiling** (withdrawn, REV-0024-F-004): instead
  `signal_seat_enabled` is gated on full rails by a **rails-presence startup guard**, so an enabled
  endpoint structurally cannot run unrailed. Live enablement is the joint WO-0102+WO-0104 milestone.
- Correlation: `SIGNAL_APPROVED` ↔ minted intent id; Candidate/SellIntent carry nullable
  `signal_producer_id`/`signal_signal_id` — every signal-originated order's trace resolves to
  exactly its signal.

## Rationale

The spine's one correct entry point for external influence is intent through the API behind
session control, risk checks, the kill switch, and the single-writer engine. The Signal Seat
formalizes that entry point for machine advisors without moving the human gate. See ADR-009
(options analysis + 16-finding adversarial review, REV-0022).

## Applies to

- WO-0102/0103/0104 implementation; any future producer integration; L1/L2 trust-ladder proposals
  (each needs a superseding ADR + independent review).

## Related pages

- `pkl/architecture/architecture-map.md`
- `pkl/architecture/testing-model.md`
- `pkl/safety/invariants-rationale.md`

## Change log

- 2026-07-14: Created as WO-0101's PKL distillation of `docs/spec/signal-seat/`.
- 2026-07-14 (later): marked draft/medium-authority — REV-0022's formal verdict (BLOCK) rescinded ADR-009's acceptance; page re-promotes only when the re-review clears (Codex PR #6 finding).
