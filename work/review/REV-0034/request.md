---
type: Review Request
rev_id: REV-0034
title: ADR-009 Signal Seat remediation + current-tree spec reconciliation
status: STAGED
reviewer_seat: Claude
targets: [ADR-009, signal-seat-spec, ADR-013-draft, WO-0102..0104-rescope]
human_gated_surfaces: [ADR-text, order-submission-design, auth-transport-design, event-log-design, schema-design]
commit_range: d32dfb1..SET-ON-DISPATCH
created: 2026-07-20
---

# Review Request REV-0034 — ADR-009 remediation and Signal Seat specification

## Reviewer role and output contract

You are the independent Claude review seat, a different model from the Codex implementer. Read
`AGENTS.md`, `CLAUDE.md`, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, and
`pkl/process/review-hardening.md`. Re-derive the design from the current tree; archive records are
provenance, not authority. Produce findings only in `work/review/REV-0034/result.md`; do not edit
this request or implementation/spec files.

Return one verdict: `ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`. Each finding must identify
file:line, why it matters, and what resolves it. Treat every preservation statement as a claim.

## Gate state

ADR-009 remains **Proposed**. This packet does not ask you to implement or accept it. Ameen will
review your result and approve/disposition the final text separately. WO-0102..0104 remain gated
drafts; the fresh `signal_records` DDL approval is deliberately deferred to R4.

Review the final committed state of this branch. On dispatch, replace `SET-ON-DISPATCH` with the
exact tip/range or record it in the result. The archive source
`origin/archive/claude-wo-0001-install-checks-2x5ys8` is optional provenance only; archive
REV-0024..0027 ids never port and clear no master gate.

## What changed

- ADR-009 ports archive-hardened A-1..A-4 while remaining Proposed.
- Transport is narrowed to `loopback` default + `tailnet_serve`; Tailscale Funnel and every
  other public exposure are forbidden with a spec-level negative test.
- The construction-time one-shot bind capability and `python -m app` launcher contract are
  restored regardless of topology.
- Flag-on auth covers every sensitive read/command; cockpit operator-key plumbing is same-change;
  interim keys are env-injected static secrets with overlap rotation.
- A-2 remains a dual-store atomic approval→ordinary-intent command.
- A-3 replaces the archive's local-row exposure sum with shared
  `project_committed_sell_exposure`, consuming INV-090 obligation projection,
  `RECOVERY_OPEN_STATUSES`, and INV-091 accepted-submit facts, with immutable coalescing,
  ambiguity refusal, contribution breakdown, cockpit reuse, and cross-consistency pins.
- D-SIG-7 **declines** the archive multi-exit relaxation: existing sell-intent single-flight and
  INV-087 one-ACTIVE-envelope-per-symbol remain unchanged.
- D-SIG-8 makes conversion mint the same Candidate/SellIntent objects as cockpit/manual flow;
  downstream envelope/order/claim/adapter/reconciliation behavior is identical, with no new lane.
- A-4 retains the final durable non-refilling invalid-budget/quarantine-epoch design and permanent
  real-rails construction guard.
- Specs 00-06, PKL, and WO-0102/0103/0104 are reconciled and kept draft/gated.
- Proposed ADR-013 seeds a thin public HMAC/secret-authenticating Receiver that forwards privately
  as a keyed producer; the trading API is never public. D-HOST-1 deployment/auth acceptance and a
  later independent review are prerequisites.
- `docs/INVARIANTS.md` receives one explicitly non-normative cross-reference; no invariant is
  added, deleted, relaxed, or amended.

## Never-reviewed / explicitly high-risk clauses

Review these directly; prior in-process or archive review does not clear them:

1. **A-1 clause 6 / D-1a construction capability.** Bare
   `uvicorn app.main:app --host 0.0.0.0` (lifespan on or off) must open no listener when flag-on;
   only the sanctioned launcher can mint the opaque one-shot capability.
2. **Final A-4.** Rate bucket + durable non-refilling invalid budget; final debit atomically
   co-opens one epoch; restart cannot refill; post-quarantine writes are zero; release resets both;
   production construction must wire real rails, not a permissive fake.
3. **A-3 locked-clause replacement — quantity truth.** The new shared exposure projection,
   envelope-child no-double-count rule, recovery/acceptance coalescing, full `needs_review`
   contribution, ambiguity refusal, and boolean/quantity cross-consistency are new current-tree
   semantics.
4. **D-SIG-7 outcome — single mandate.** The archive multi-exit relaxation is removed. Verify that
   the draft consistently preserves INV-087 and existing sell-intent single-flight and does not
   accidentally reuse another signal's approval.
5. **D-SIG-8 ordinary downstream.** Verify the design truly creates no signal-only execution or
   bypass, including direct SELL vs delegated-envelope behavior.
6. **A-4/A-2 joint enablement.** Verify the three implementation WOs cannot authorize a
   half-railed, unauthenticated, cockpit-locking, or conversion-less flag-on deployment.
7. **ADR-013 boundary.** Verify the proposed Receiver—not FastAPI—is the only public component and
   has zero execution/human-command authority.

## Questions to answer

1. Does A-1 close REV-0022 F-001 without contradicting the D-HOST-1 interim, and is
   `tailnet_serve`/Funnel-negative language complete and testable?
2. Is construction-time no-listener enforcement possible under the stated seams without an
   importable pre-authorized app or environment bypass?
3. Does A-2 structurally eliminate approved-without-intent and intent-without-approval across
   cancellation, crash, expiry, quarantine/release, TradingState, and duplicate races?
4. Does `project_committed_sell_exposure` consume every current SELL-exposure ingress exactly
   once: envelope mandate, direct order, open recovery, UNKNOWN/fallback acceptance, and malformed
   ambiguity? Can it ever contradict `_same_symbol_exit_may_execute` or INV-090/091?
5. Does preserving INV-087/single-flight create any orphaned approval, silent reuse, or inability
   to perform a genuine protective exit? Are refusal semantics operator-visible and retry-safe?
6. Are Candidate/SellIntent/envelope semantics exactly ordinary manual flow, or does any prose
   imply a new submit, bypass, reason, or authority lane?
7. Is A-4's event/storage bound honest under paced hostility, concurrent final-slot requests,
   slow bodies, config changes, crash, replay, release, and accepted (legitimate) traffic?
8. Does the mounted-route matrix cover current routes, specifically
   `POST /api/session/close` and the three envelope routes, while preserving public health only?
9. Are schema/event additions still gated rather than silently approved by this docs change?
10. Does Proposed ADR-013 preserve a private trading API and name sufficient prerequisites, or
    does it smuggle in a public deployment decision?

## Required fresh probes / disproof attempts

No `INV-*` statement was added or amended, so the protocol's new-invariant list is **none**.
Nevertheless, include fresh reasoning/probe results for these mapped claims:

- **INV-087:** attempt two same-symbol signal approvals across different SellIntents/envelopes;
  show the spec requires exactly one mandate and a visible refusal.
- **INV-090/091:** construct one envelope child represented simultaneously by order, recovery,
  and fallback plus a distinct accepted broker identity; show coalescing is one-plus-one, not
  zero/one/three, and malformed identity refuses.
- **INV-034/094:** attempt to label a signal SELL as manual flatten or bypass opposite-side
  Candidate/BUY exposure; show the spec forbids both.
- **A-1 negative:** try bare Uvicorn with lifespan disabled and a public bind; the required future
  test outcome is connection refused/no listener, not HTTP 503.
- **A-4 negative:** pace invalid/expired/conflicting inputs below token refill across many windows,
  restart at limit−1, race the final slot, then release; identify any prose that permits >limit
  terminal events, duplicate epoch opens, silent refill, or inert release.
- **Public-ingress negative:** try to route TradingView directly to FastAPI/Funnel or give the
  Receiver an operator key; the proposed contracts must reject those architectures.

This is a design review; where implementation does not yet exist, provide a file/line-keyed
unreachability/design argument and mark runtime proof UNVERIFIED rather than inventing evidence.

## Curated targets

- `docs/adr/ADR-009-signal-seat-boundary.md`
- `docs/spec/signal-seat/00-overview.md` through `06-invariants.md`
- `pkl/architecture/signal-seat.md`
- `docs/INVARIANTS.md` (INV-034, 085, 087, 090, 091, 094 + WO-0127 annotation)
- `docs/adr/ADR-010-execution-envelope.md`
- `docs/adr/ADR-013-external-ingress.md`
- `work/queue/WO-0102-signal-ingestion-endpoint.md`
- `work/queue/WO-0103-signal-approval-surface.md`
- `work/queue/WO-0104-signal-rails.md`
- `work/review/DISPATCH.md`
- `work/review/REV-0022/{result.md,disposition.md}`
- current anchors: `app/facade/store_backed.py:786-789`,
  `app/store/core.py:887,981-998,1401`, `app/models.py:893`,
  `app/api/routes_system.py:48`, `app/api/routes_trading.py:289,299,318`

## Out of scope

Implementation quality (none is authorized here); acceptance/disposition; fresh schema DDL;
Signal Seat R4-R7 code; Entry Envelope; L1/L2 autonomy; public deployment; changing any test,
application, invariant semantics, or accepted ADR outside the Proposed ADR-009/013 draft surface.
