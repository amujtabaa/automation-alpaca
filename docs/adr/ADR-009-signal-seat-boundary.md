# ADR-009: Signal Seat — External Agentic Signal Producers as Bounded Intent Sources

**Status:** DRAFT / PROPOSED — pending human acceptance + independent cross-model review
**Date:** 2026-07-11
**Deciders:** Ameen (human gate). Queues for independent cross-model review before acceptance (ADR amendment per review policy).
**Number:** ADR-009 (renumbered on install from planning-seat draft "ADR-010"; 009 is the next free slot after ADR-008).

> **Install note (2026-07-11).** Installed from the Fable-5 planning-seat handoff. Two of the
> draft's three acceptance gates are now cleared with evidence:
> 1. **Install verification** — `check_install.py` → `INSTALL CHECK PASSED`;
>    `check_version_consistency.py` → `VERSION CHECK PASSED: v0.9.1`;
>    `check_mcp_spec.py` → `SKIPPED: mcp/ not installed (optional layer)` (all exit 0).
> 2. **WO-0001 disposition** — `work/ledger.jsonl`: WO-0001 CLOSED, disposition
>    `[PKL_UPDATED, RESULT_SUMMARY_KEPT]`, commit `4eccaac`, 2026-07-08. Caveat the planning
>    seat should weigh: WO-0001's verdict was **NOT-TERMINAL (narrow)** — the order-status/spawn
>    state machine remains `legacy_truth` pending WO-0007b. Signal lifecycle events are new
>    event types and do not depend on that flow, but the approval→intent conversion (WO-0103)
>    lands upstream of it.
> 3. **Acceptance** — still open: human review + independent cross-model review packet
>    (`work/review/REV-*`), per the CLAUDE.md review policy. This document remains DRAFT until
>    that packet is dispositioned ACCEPT / ACCEPT-WITH-CHANGES.

## Context

External agentic research systems (exemplar: HKUDS Vibe-Trading — an LLM-driven market-research/trading-agent platform) can generate trade theses and signals at a cadence and breadth a human operator cannot. We want that capability available to this platform **without** compromising the Spine v2 execution architecture, whose value is precisely that it is deterministic, single-writer, event-sourced, and human-gated.

Forces at play:

- Safety core invariants 1–11 and INV-1..9 are non-negotiable; order submission is a human-gated surface.
- Stack is pinned (Python 3.12, FastAPI, Streamlit, SQLite); new dependencies require an ADR; `alpaca-py` lives only in the Broker Adapter.
- Vibe-Trading and similar systems are fast-moving, LLM-dependent, and nondeterministic — architecturally the opposite of the spine. Coupling their internals into the spine imports their surface area and their failure modes.
- The spine already has exactly one correct entry point for external influence: **intent submitted through the API, subject to session control, risk checks, kill switch, and the single-writer engine.**

## Decision

Define a **Signal Seat**: a runtime role (not a development seat) for external signal producers. A signal producer is any out-of-process system that submits *signal proposals* to the FastAPI backend over an authenticated HTTP contract. The spine treats signal producers as untrusted advisors.

### Contract

1. **Transport & isolation.** HTTP only, to dedicated FastAPI endpoints. The producer runs as a separate process/repo (Vibe-Trading unmodified, or any other agent). No code from the producer enters this repository; no spine code enters the producer. Zero shared dependencies beyond the OpenAPI contract.
2. **Schema.** `SignalProposal`: `producer_id`, deterministic `signal_id` (producer-generated, ULID or equivalent — enables idempotent dedupe, mirroring `client_order_id` practice), `issued_at`, `ttl_seconds`, instrument, direction, *suggested* sizing (advisory field, never binding), thesis text, provenance blob (model, prompt/version identifiers, source citations). Pydantic-validated at the boundary; validation failure → quarantine, not rejection-and-forget.
3. **Event-log provenance.** Every signal's lifecycle is appended to the event log as first-class events: `SIGNAL_RECEIVED` → one of `SIGNAL_QUARANTINED` | `SIGNAL_EXPIRED` | `SIGNAL_REJECTED` (human) | `SIGNAL_APPROVED` (human). Approval emits a normal order intent into the existing path — from that point the signal has no special status whatsoever.
4. **Trust ladder.** L0 — advisory: every signal requires per-signal human approval before becoming an order intent (beta scope, this ADR). L1 — batch approval queues; L2 — bounded autonomy within pre-approved risk envelopes. **L1 and L2 are explicitly out of scope and each requires its own superseding ADR plus independent review**, since they move the human gate.
5. **Rails (quarantine semantics extended to signals).**
   - TTL/staleness: a signal past `ttl_seconds`, or carrying `issued_at` in the future or implausibly old, is `SIGNAL_EXPIRED`/`SIGNAL_QUARANTINED` — the market-data fail-fast rail applied to signal freshness. A stale signal can never be approved.
   - Malformed, duplicate-conflicting, or self-contradictory signals → `SIGNAL_QUARANTINED`, recorded never hidden.
   - Per-producer rate limits; breach → producer-level quarantine (all further signals quarantined until human release).
   - Kill switch / `Halted` state: signals may still be *recorded* (facts are facts), but signal→intent conversion is blocked exactly as any other new order intent is. In `Reducing`, only risk-reducing signals are convertible.
6. **UI.** Streamlit gains a read/approve panel: renders pending proposals, issues approve/reject *intents* to the API. It remains a thin client — no signal state owned client-side, no direct mutation, and (as always) no Alpaca calls.

### Invariant mapping

| Invariant | Preservation |
|---|---|
| 1–2 Paper-only | Signals carry no execution authority; approved intents flow into the existing paper-only pipeline unchanged. |
| 3, 7 Backend is engine/truth | Signal state lives in backend + event log only. |
| 4, 6 Streamlit thin, owns no state | Approval panel observes and issues intents only. |
| 5 UI never calls Alpaca | Unchanged; producers also never touch Alpaca through us. |
| 8 Submitted ≠ filled | Signal approval produces an intent, not an order, not a fill. |
| 9 Only fills change positions | Signals are upstream of intents; structurally cannot touch positions. |
| 10 Kill switch blocks new intent | Conversion gate sits behind the kill switch. |
| 11 Browser-first | Approval surface is the browser UI. |
| INV-1..9 | To be mapped line-by-line by the planning seat — **UNVERIFIED in this draft**. (Install note: §5 of `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` is available in-repo; mapping remains an open action item before acceptance.) |

## Options Considered

**A. HTTP boundary contract, advisory-only (chosen).** Complexity low-medium; zero new spine dependencies; producer fully swappable; failure modes contained by quarantine rails. Con: integration is shallow — no shared backtesting, no deep data reuse.

**B. Vendor Vibe-Trading code into the repo.** Rejected: violates pinned-stack/new-dependency rule at scale, imports an LLM-agent framework's whole surface into a safety-critical codebase, license and upstream-churn burden, and the audit wave would balloon.

**C. Embed an LLM agent as a backend module.** Rejected: puts nondeterminism inside the single-writer engine's process; blurs the seam the whole architecture is built on.

**D. Reverse direction — port the spine into Vibe-Trading.** Rejected for this project's goals: forfeits governance, CI gates, and the event-log-as-truth property; equivalent to starting over inside someone else's architecture.

## Consequences

Easier: adding/swapping producers (any agent that can POST JSON); auditing exactly what influenced trading (provenance in the event log); later trust-ladder promotion as a pure policy change behind a stable contract. Harder: the integration is deliberately shallow; every signal costs a human approval in beta (accepted — that *is* the design); one new API surface + event types to test on both storage paths. Revisit: L1 promotion criteria after beta produces approval-volume data.

## Action Items

1. [x] Renumber on install (ADR-010 draft → ADR-009) and clear install-verification + WO-0001-disposition gates — done 2026-07-11, evidence in the install note above.
2. [ ] Human review of this draft; resolve the INV-1..9 line-by-line mapping against `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5`.
3. [ ] Queue for independent cross-model review (ADR amendment class) — create a `work/review/REV-*` packet at the human's discretion; acceptance blocked until that packet is dispositioned.
4. [ ] WO-0101..0104 (installed to `work/queue/`, status draft) — all remain gated on this ADR's acceptance.
