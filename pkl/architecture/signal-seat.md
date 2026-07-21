---
type: Module Knowledge
title: Signal Seat — external signal producers (contract summary)
status: draft
authority: medium
owner: Ameen
last_verified: 2026-07-20
tags: [signal-seat, architecture, boundaries, safety]
source_refs: [docs/adr/ADR-009-signal-seat-boundary.md, docs/spec/signal-seat/00-overview.md]
supersedes: []
superseded_by: null
---

# Signal Seat — external signal producers (contract summary)

## Gate state

ADR-009 is **Proposed**. WO-0127 drafted the master-side remediation and staged REV-0034, but the
draft has no implementation authority. WO-0102..0104 remain gated until the Claude-seat review
returns ACCEPT / ACCEPT-WITH-CHANGES and Ameen accepts the final ADR text. Fresh
`signal_records` DDL approval is deferred to R4.

Archive REV-0024/0025 records at
`origin/archive/claude-wo-0001-install-checks-2x5ys8` are provenance only; their ids and
governance state are not ported.

## Rules / facts proposed by ADR-009

- **Topology:** v1 producer is localhost-only. Allowed transport vocabulary is `loopback`
  (default) and `tailnet_serve`; the backend remains loopback-bound. Tailscale Funnel and every
  other public exposure are forbidden and negatively tested.
- **Launcher:** the backend-owned `python -m app` construction-time capability prevents a
  flag-on bare Uvicorn import from opening any listener. A request-time 503 is only defense in
  depth, not the boundary.
- **Identity/auth:** `producer_id` derives from an ingestion-scoped producer key; operator keys
  gate every sensitive route, reads included, when the flag is on. Keys are env-injected static
  secrets with multi-key overlap rotation; cockpit key plumbing lands with enforcement.
- **Lifecycle:** RECEIVED → QUARANTINED | EXPIRED | REJECTED | APPROVED; terminal is terminal.
  Approval and ordinary intent creation are one dual-store atomic command.
- **Freshness:** durable server-owned
  `expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)`, with bounded TTL,
  skew quarantine, injected clock, and atomic conversion-time recheck.
- **Rails:** every authenticated ingest debits the refilling rate bucket. Attributable terminal
  ingest facts debit a durable, non-refilling per-cycle budget; the final debit co-opens one
  quarantine epoch, post-quarantine ingress is write-free, and human release resets both rails.
  Flag-on construction requires the real rails provider.
- **Conversion:** producer suggestions are display-only. BUY mints the same Candidate and SELL the
  same SellIntent as cockpit/manual flow. Downstream candidate/sell-intent, envelope, claim,
  adapter, and reconciliation paths are unchanged; there is no signal execution lane.
- **Exposure:** one shared `project_committed_sell_exposure` consumes the INV-090 obligation
  projection, `RECOVERY_OPEN_STATUSES`, and INV-091 accepted-submit truth. It returns quantity,
  contribution breakdown, and ambiguity; both stores and the cockpit consume it.
- **Single mandate:** D-SIG-7 preserves existing sell-intent single-flight and INV-087's one ACTIVE
  envelope per symbol. The archive multi-exit relaxation is declined.
- **Correlation:** signal provenance remains auditable across Candidate/SellIntent/order events but
  never grants authority.
- **External Internet producers:** Proposed ADR-013 isolates a public HMAC-authenticating Receiver
  that forwards privately as a keyed producer. The trading API is never public; D-HOST-1
  deployment/auth acceptance is prerequisite.

## Rationale

The only safe external influence point is an untrusted proposal entering the private FastAPI
boundary, then ordinary operator approval and the existing single-writer execution spine. The
Signal Seat adds identity, provenance, freshness, and finite hostile-ingest rails without adding a
second executor.

## Applies to

Future WO-0102/0103/0104/R4-R7 implementation after G1 clears; any future producer integration;
any L1/L2 proposal (which requires a superseding ADR and review).

## Related pages

- `pkl/architecture/architecture-map.md`
- `pkl/architecture/testing-model.md`
- `pkl/safety/invariants-rationale.md`
- `docs/adr/ADR-013-external-ingress.md`

## Change log

- 2026-07-14: initial draft distillation.
- 2026-07-20: reconciled to current INV-087/090/091 semantics and D-SIG-1..9; retained
  draft/medium authority pending REV-0034 and human acceptance.
