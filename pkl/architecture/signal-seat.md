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
per-signal human approval (trust level L0). **GATE STATE (2026-07-14): ADR-009 is ACCEPTED.** History:
its 2026-07-12 acceptance was RESCINDED after the formal REV-0022 review returned BLOCK (4 P1s: credential/
transport boundary, non-atomic conversion, TTL/classification bounds, unbounded audit). Amendments
A-1..A-4 drafted; the REV-0024 re-review confirmed A-2/A-3 CLOSED (atomic conversion, server-owned
freshness) but A-1/A-4 NOT — re-remediated 2026-07-14 (A-1 clause 6 backend-owned launch for F-001;
A-4 non-refilling invalid budget + rails-presence enablement gate for F-004). REV-0025 returned BLOCK
(7 P1s, no A-2/A-3 regression); Ameen decided its forks (D-1 construction-time bind refusal; D-2
release/deployment gate) and **LOCKED the spec 2026-07-14** — remaining items are implementation-
semantic WO-time contracts (atomic epoch-open → WO-0104; multi-exit + local-order exposure →
WO-0103). The three staged packets (REV-0022, REV-0024, REV-0025) are the amendment-design review record. **ADR-009 was ACCEPTED
(Ameen, 2026-07-14) and WO-0102..0104 UNFROZEN for implementation — WO-0102 first, then WO-0103 ∥
WO-0104; live enablement is the joint milestone; each WO's implementation gets its own code review.**
ADR-009 (Accepted) is the decision; the
implementation contract is `docs/spec/signal-seat/` (WO-0101 output — LOCKED 2026-07-14, build against it).
Implementation: WO-0102 → WO-0103 ∥ WO-0104, all **UNFROZEN (status: ready)** 2026-07-14 — WO-0102 activatable first; WO-0103 and WO-0104 start after WO-0102 completes and may run in parallel. Each WO's implementation gets its own independent code review.

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
  breach → producer quarantine with operator release (browser control required, resets **both** the
  bucket and the budget; the budget's check-debit is atomic with the terminal append and its consumed
  count is durable across restart — REV-0025-F-003/F-004); post-quarantine ingress is boundary-rejected
  with epoch-bounded coalesced audit. **The constant storage bound is on attributable-rejection traffic
  only** (≤ invalid_budget + 2 rail events per cycle, each cycle needing a human release); legitimately
  *accepted* signals are **rate-bounded, not finite over indefinite time** (REV-0025-F-006 — not a
  globally-finite-storage claim). **No interim ceiling** (withdrawn, REV-0024-F-004): instead
  `signal_seat_enabled` is gated on full rails by a **rails-presence startup guard**, so an enabled
  endpoint structurally cannot run unrailed. Live enablement is the joint WO-0102+WO-0103+WO-0104
  milestone (ingest + atomic conversion + rails; the A-2 conversion is WO-0103's, not WO-0102's).
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
- 2026-07-14 (later): marked draft/medium-authority — REV-0022's formal verdict (BLOCK) rescinded ADR-009's acceptance; page to re-promote when the re-review clears (Codex PR #6 finding).
- 2026-07-14 (latest): **re-promoted to active/high** — ADR-009 re-ACCEPTED post spec-lock, WO-0102..0104 unfrozen (REV-0022/0024/0025 concluded, REV-0026 withdrawn); the re-promotion condition is satisfied.
