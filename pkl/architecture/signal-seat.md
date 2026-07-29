---
type: Module Knowledge
title: Signal Seat — external signal producers (contract summary)
status: active
authority: high
owner: Ameen
last_verified: 2026-07-28
tags: [signal-seat, architecture, boundaries, safety]
source_refs: [docs/adr/ADR-009-signal-seat-boundary.md, docs/spec/signal-seat/00-overview.md]
supersedes: []
superseded_by: null
---

# Signal Seat — external signal producers (contract summary)

## Gate state

ADR-009 is **Accepted**. REV-0034 returned ACCEPT-WITH-CHANGES, WO-0133 resolved C-1/C-2, and
Ameen approved the final text at `385cc7d` on 2026-07-21. G1 is clear. WO-0102..0104 remain draft
and retain their own activation, sequencing, implementation-review, and joint-enablement gates.
Fresh `signal_records` DDL approval remains deferred to R4.

Archive REV-0024/0025 records at
`origin/archive/claude-wo-0001-install-checks-2x5ys8` are provenance only; their ids and
governance state are not ported.

## Rules / facts accepted by ADR-009

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
  Flag-on construction requires the real rails provider. Startup is tolerant per producer: an
  unfoldable history yields a derived, never-persisted invalid-projection marker (ADR-014) that
  refuses the offender write-free while every other producer folds, and release is three-state
  (open-epoch close / no-epoch heal / mid-cycle repair-and-refuse). Derived sequence truth is
  single-sourced through `contributed_epoch_sequence()` and the release-key parser is a total
  inverse of the mint (REV-0045; enforced by `tests/test_derived_truth_single_source.py`).
  **Proof and occupancy are separate facts (ADR-016) — RATIFIED TARGET, NOT DELIVERED BEHAVIOR.**
  The `c20ca47` implementation carries four self-audit P0s, chief among them that the fold and both
  stores disagree about where recovery may land, so the human release does not survive a restart
  (`tests/test_wo0141_known_defect_fold_store_disagreement.py`). The rules below describe the
  intended model, not current code. Intended: the high-water mark advances only
  when the fold ACCEPTS an event, while a well-formed producer-bound `producer_release:` key is
  consumed by the UNIQUE index whether or not the event was valid. Recovery lands at
  `next_mintable` — lowest sequence above the proven high-water and unconsumed — which equals
  `high_water + 1` in any fully valid history. Attribution is one rule: a release's key producer
  and payload producer must agree or it contributes nothing anywhere. Minting is capped at
  `SIGNAL_EPOCH_SEQUENCE_MINT_MAX` while readers keep the full signed domain, so a successor always
  exists. This replaces the withdrawn §2.6 reservation ruling, which produced P0-6.
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

Future WO-0102/0103/0104/R4-R7 implementation now that G1 is clear, subject to each work order's
remaining gates; any future producer integration; any L1/L2 proposal (which requires a superseding
ADR and review).

## Related pages

- `pkl/architecture/architecture-map.md`
- `pkl/architecture/testing-model.md`
- `pkl/safety/invariants-rationale.md`
- `docs/adr/ADR-013-external-ingress.md`

## Change log

- 2026-07-14: initial draft distillation.
- 2026-07-20: reconciled to current INV-087/090/091 semantics and D-SIG-1..9; retained
  draft/medium authority pending REV-0034 and human acceptance.
- 2026-07-21: promoted to active/high authority after REV-0034 ACCEPT-WITH-CHANGES, WO-0133
  remediation, RESOLVED disposition, and Ameen's explicit final-text approval at `385cc7d`.
- 2026-07-22: R4 store layer landed (WO-0134): signal model vocabulary, pure ingest planner
  (A-3 deadline, injective `(producer_id, signal_id)` dedupe, echo/audit-only-conflict), dual-store
  persistence (`signal_records` DDL behind the operator schema gate), `project_signal_records` fold
  + replay-parity registration. Both stores green; INV-1/INV-9 preserved. Independently reviewed
  REV-0039 ACCEPT-WITH-CHANGES → RESOLVED. Endpoint/auth/rails/conversion (R5–R7) remain unbuilt;
  the seat flag stays OFF until the joint D-2a milestone.
- 2026-07-25: R5a construction-time foundation landed (WO-0137): exact-identity one-use launch
  capability, private bind guard, conditional module-level `app`, rails conformance seam, and
  Signal Settings plus validation. REV-0041 returned final ACCEPT after C-1 through C-4 cleared.
  D-2a remains OFF pending R5b + R6 + R7; R5b-N1 and formatter cleanup remain follow-up work.
- 2026-07-25: R5b-1 ingest-only producer surface landed (WO-0138): typed write-only
  `StoreBackedSignalFacade`, producer-key auth with server-bound identity, flag-gated
  `POST /api/signals`, validation quarantine/event attribution, injective replay/conflict behavior,
  and ingest-time dead-on-arrival expiry. REV-0042 returned ACCEPT after the F-1 wire-bound
  remediation and seven reviewer-requested pin classes; disposition RESOLVED. `app/store/`
  remained untouched. At R5b-1 close, facade reads, operator enforcement, and lazy expiry were
  deferred to R5b-2; F-8/F-10/F-11 carried to R5b-2/R7.
- 2026-07-25: R5b-2 closed (WO-0139): deny-by-default operator enforcement, principal-bound actor
  attribution, cockpit credential plumbing, the literal route-authorization matrix, and
  mutation-free effective-expiry projection for reads and existing-record ingest echoes were
  delivered. REV-0043 returned ACCEPT-WITH-CHANGES, then final ACCEPT after F-1/F-2 remediation and
  the operator's F-4 acknowledgement retaining `detected_by:"conversion"`; disposition RESOLVED.
  F-6/F-8 carry to R6. D-2a stays OFF pending R6 + R7 and the joint gate.
- 2026-07-26: R6a rails store surface implemented (WO-0104a): the
  operator-approved nine-column producer-rail table and fail-closed startup
  guards; event-authoritative budget/quarantine/epoch projection registered in
  replay; identity-conditioned atomic budget debit and epoch opener; primary
  durable REAL token bucket with fractional carry; record-free late-body
  rejection; human release resetting both rails; and a snapshot-free signal
  transition-event builder. The seat flag remains OFF: R6b still owns provider,
  route/sweep/cockpit wiring and rate settings, and REV-0044 must disposition
  before R6b or R7a starts.
- 2026-07-27: R6a truth-model remediation implemented (WO-0140, REV-0044 R-1..R-13; implementer
  Claude by operator seat swap, gate-clearing review Codex-owned REV-0045): per-producer tolerant
  startup with derived invalid-projection markers (a pre-R6a log OPENS; exactly the offender is refused; vocabulary per ADR-014 — formerly "poisoned");
  cache-authoritative live gating with the incremental debit (the attributable path folds nothing);
  bounded release-exclusive verification folds with a state-conditional seed, an O(1) dedupe-key
  anchor, and the release-boundary regression rule; the three-state log-classified release (open →
  state-1 from log truth; wedge/unfoldable → zero-width heal consuming the next sequence via the
  dedupe key; zero/interior → repair-and-refuse); ratified caps single-sourced in `app/models.py`.
  **STANDING RULE (WO-0140): the ratified rail caps bind at WRITE time only — the fold and the row
  validator judge logged/durable values structurally, and lowering a ratified cap is a log-truth
  change, not a config change.** Two fresh-context refutation passes ran during implementation;
  their P0s (exception-hierarchy escape; the drift-heal replay divergence) were fixed under
  operator ruling Option A. D-2a remains OFF; R6b starts only after REV-0045 dispositions.
