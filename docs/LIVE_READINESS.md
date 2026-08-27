# Live-readiness: the two-tier quality standard and promotion checklist

Status: Accepted (ratified by Ameen Mujtabaa in session, 2026-08-26, as part of the WO-0168d
hybrid decision). Codified alongside ADR-026. This document defines WHEN live-grade weight
applies; it grants no execution, mode, or credential authority. Live modes remain disabled by
configuration (CLAUDE.md invariant 1) regardless of this checklist's state.

## The two-tier standard

Quality effort is split by **reversibility**, not applied uniformly:

**Tier 1 — live-grade from day one (irreversible; retrofit ≈ rewrite).** The safety-core
invariants and data model: single-writer engine; submitted ≠ filled; positions derive only from
first-occurrence canonical execution facts; event log as truth; deterministic engine tests
(injected clocks, seeded randomness, deterministic IDs); Decimal money math; idempotent
reconciliation with `TIMEOUT_QUARANTINE` and never blind-resubmit; layer boundaries
(`ui → api → facade → engine → adapter/store`; `alpaca-py` adapter-only); the human-gated
surface list. These hold at full strength in every phase, including paper.

**Tier 2 — paper-grade now, ratcheted later (reversible; bolts on cheaply).** Proof burden on
ordinary changes (tests + CI + one review round, scaled to blast radius per ADR-026's stop
rule); operational hardening (monitoring, alerting, failover, latency); exhaustive broker
edge-case coverage (discovered from paper reality, not enumerated up front); performance and
capacity work; multi-seat review ceremony outside gated surfaces.

Paper trading is itself the primary live-readiness instrument: real code path, real broker API,
fake money. Past the point of safety, delaying paper "for quality" is quality-negative.

## Promotion checklist — every item must pass before any live-mode configuration exists

1. **Paper runtime**: ≥ 4 consecutive weeks of paper operation with zero unexplained
   reconciliation breaks (every divergence root-caused and dispositioned).
2. **Restart drill**: process killed mid-session on a live-like day; state rebuilt exactly from
   the event log; drill logged with evidence.
3. **Kill-switch and manual-flatten drills**: executed against paper, routed through session
   control and the audit log, evidence retained.
4. **Broker-error taxonomy**: timeouts, rejects, partial fills, and cancel races observed in
   paper and each mapped to a tested handling path (no unhandled category outstanding).
5. **Invariant coverage**: every CLAUDE.md invariant and INV-1…9 has failure-capable tests;
   dual-store parity suites green in CI.
6. **Shadow phase**: a `LIVE_SHADOW` period (live data, no live orders) completed after the
   paper criteria pass, with divergence review.
7. **Limits configured and tested**: per-position caps, max daily loss, and order-rate limits
   enforced by the backend with tests proving refusal.
8. **Secrets hygiene**: live keys never present in the repository, worktrees, or agent-readable
   configuration; separate storage decided and documented before keys are created.
9. **Minimum observability**: alerting on quarantine events, kill-switch triggers, and
   reconciliation breaks reaches Ameen off-machine (e.g., phone).
10. **Independent review**: the live/shadow configuration diff receives a cross-model review
    packet (human-gated surface) with ACCEPT, plus Ameen's explicit written go decision.

## Rules

- The checklist may gain items at any time; removing or weakening an item requires Ameen's
  written decision recorded in the ledger.
- Checklist state is evidence-based: each item's pass cites its drill log, test run, or packet.
- No agent may mark item 10 or flip any live-mode configuration; those are Ameen-only acts.
