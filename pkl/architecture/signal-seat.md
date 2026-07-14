---
type: Module Knowledge
title: Signal Seat — external signal producers (contract summary)
status: active
authority: high
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
per-signal human approval (trust level L0). ADR-009 (Accepted 2026-07-12) is the decision; the
full implementable contract is `docs/spec/signal-seat/` (WO-0101 output). Implementation:
WO-0102 (ingestion) → WO-0103 (approval surface) ∥ WO-0104 (rails), queued.

## Rules / facts

- Identity: `producer_id` derives from the API key server-side, never from the request body;
  dedupe/idempotency key is `(producer_id, signal_id)`.
- Role separation: producer keys are ingestion-scoped (`POST /api/signals` only); approve /
  reject / producer-release are operator-credential-only. Operator-auth enforcement on all
  mutating command routes flips on with the `signal_seat_enabled` flag, together with the cockpit
  credential plumbing (no operator lockout window).
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
- Rails: TTL/staleness quarantine at ingest; per-producer rate limit → producer quarantine with
  operator release (browser control required); post-quarantine/over-ceiling ingress is
  boundary-rejected with coalesced audit — the event log stays bounded under flood; WO-0102
  ships an interim hard ceiling so no unrailed enablement window exists.
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
