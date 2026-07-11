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
>    `[PKL_UPDATED, RESULT_SUMMARY_KEPT]`, commit `4eccaac`, 2026-07-08. WO-0001's
>    NOT-TERMINAL (narrow) residual has since been **closed**: WO-0007b flipped the
>    order-status/spawn flow to `event_truth` (2026-07-08, human sign-off), WO-0013 remediated
>    the REV-0001 P0s on the write path, ADR-008 was **Accepted** (2026-07-09), and the
>    independent review dispositioned RESOLVED (REV-0003, ACCEPT-WITH-CHANGES). The migration
>    is substantially terminal; the only known deferral is `filled_quantity` event-sourcing
>    (status-only flip; separate follow-up), which the signal WOs do not depend on.
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
   **Role separation (Codex PR #5 P1, incorporated pre-acceptance):** per-producer API keys are **ingestion-scoped** — valid for `POST /signals` and nothing else. **Identity binding (Codex round 3):** `producer_id` is never trusted from the request body — the server derives it from the authenticated API key; a body-supplied `producer_id` that mismatches the credential is rejected at the boundary. Producer A therefore cannot consume producer B's dedupe/rate-limit/quarantine namespace or forge provenance under B's identity (mismatch tests required for dedupe and rate-limit/quarantine accounting). Approval, rejection, and producer-release are **operator-only** routes authenticated by a distinct operator credential; a producer credential structurally cannot invoke them, proven by negative tests. This is a deliberate departure from the beta as-built posture (`app/api/deps.py` `get_actor` is an audit label, not authentication — accepted while the backend was single-user localhost): admitting authenticated external producers ends that assumption, so the credential split lands **with** the first signal endpoint (WO-0102/0103), not after. **And it cuts both ways (Codex round 4):** scoping the producer key is worthless while the existing command routes accept unauthenticated requests (`get_actor` defaults to `operator` when no header is sent) — a producer could simply omit its key. From the moment a producer can reach FastAPI, every mutating/human-gated command route requires a valid operator credential; requests with no credential or an invalid one are denied (negative tests for the *existing* command routes, not just producer-key rejection). **Sequencing (Codex round 5): the cockpit's credential plumbing ships in the same change as the enforcement flip** — the browser client currently sends no auth header, and a window in which the operator's kill switch or manual flatten answers 401 is an unacceptable safety regression (invariant 11).
2. **Schema.** `SignalProposal`: `producer_id`, deterministic `signal_id` (producer-generated, ULID or equivalent — enables idempotent dedupe, mirroring `client_order_id` practice), `issued_at`, `ttl_seconds`, instrument, direction, *suggested* sizing (advisory field, never binding), thesis text, provenance blob (model, prompt/version identifiers, source citations). Pydantic-validated at the boundary; validation failure → quarantine, not rejection-and-forget. **The idempotency/dedupe key is `(producer_id, signal_id)` — server-namespaced per producer, never the bare `signal_id`**: producers are untrusted, so one producer reusing (accidentally or deliberately) another's id must not quarantine or provenance-collide the other's legitimate signal (Codex review on PR #5, incorporated pre-acceptance).
3. **Event-log provenance.** Every signal's lifecycle is appended to the event log as first-class events: `SIGNAL_RECEIVED` → one of `SIGNAL_QUARANTINED` | `SIGNAL_EXPIRED` | `SIGNAL_REJECTED` (human) | `SIGNAL_APPROVED` (human). Approval emits a normal order intent into the existing path — from that point the signal has no special *authority* whatsoever, but the *correlation* survives (Codex round-5 P2): `SIGNAL_APPROVED` carries the id of the candidate/sell-intent it created, and the created intent's origin/audit payload carries `(producer_id, signal_id)` back-reference. With multiple approved signals on one symbol, the event trace of any order must be filterable back to exactly the signal that influenced it — otherwise the "audit exactly what influenced trading" benefit in §Consequences is an empty claim. Test-proven in WO-0103.
   **Operator-derived sizing and pricing (Codex round 4):** "advisory, never binding" must survive conversion mechanics. The as-built candidate path builds the LIMIT order from `candidate.suggested_quantity` / `suggested_limit_price` (`app/store/core.py:641+`) — whoever populates those fields controls the order. Therefore the approval action itself carries the **operator-confirmed quantity and limit price** (entered or explicitly confirmed by the human in the approval UI, validated server-side); producer-suggested sizing is display-only context and never flows into any order field. WO-0101 specs the approval payload; WO-0103 proves by test that the dispatched order's qty/price come from the approval payload, not the `SignalProposal`.
   **Direction-aware conversion (Codex PR #5 round-3 P1):** the as-built intent origins are direction-specific — candidate approval creates BUY orders; SELLs originate only as `SellIntent` with reason `manual_flatten` or `protection_floor`. A sell-direction signal therefore needs a defined origin: WO-0101's spec must specify the signal sell path (e.g. a new `SellReason.SIGNAL` on the existing `SellIntent` machinery, routing through the same session-control/risk/kill-switch gates as manual flatten) rather than misrouting signal sells through the buy or manual-flatten paths. This is load-bearing for the INV-7 asymmetry decision above — the protective-sell-in-`Reducing` test needs a real sell route to exercise.
4. **Trust ladder.** L0 — advisory: every signal requires per-signal human approval before becoming an order intent (beta scope, this ADR). L1 — batch approval queues; L2 — bounded autonomy within pre-approved risk envelopes. **L1 and L2 are explicitly out of scope and each requires its own superseding ADR plus independent review**, since they move the human gate.
5. **Rails (quarantine semantics extended to signals).**
   - TTL/staleness: a signal past `ttl_seconds`, or carrying `issued_at` in the future or implausibly old, is `SIGNAL_EXPIRED`/`SIGNAL_QUARANTINED` — the market-data fail-fast rail applied to signal freshness. A stale signal can never be approved.
   - Malformed, duplicate-conflicting, or self-contradictory signals → `SIGNAL_QUARANTINED`, recorded never hidden.
   - Per-producer rate limits; breach → producer-level quarantine (all further signals quarantined until human release). **Rails ship no later than exposure (Codex round 6):** the ingestion endpoint carries a conservative hard ingest ceiling from its first commit, superseded (never just removed) by the full rate-limit/quarantine rails — there is no window in which an enabled endpoint lacks flood protection. The human **release** action has a browser path (cockpit control), not raw-API-only — invariant 11. **Post-quarantine backpressure (Codex PR #5 P2):** once a producer is quarantined, further ingress from it is rejected at the boundary (HTTP 429/403) and does **not** append per-request events — the audit trail is coalesced (the quarantine event itself plus a bounded/periodic rejected-count record), so a malicious authenticated producer cannot flood the append-only log or grow SQLite without bound. Test-proven: requests after producer quarantine leave the event log bounded.
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
| INV-1 fills only change `remaining_qty` | No signal event type touches spawn/fill accounting; approval emits an order intent *upstream* of primary creation. `SIGNAL_*` events are structurally outside the `remaining_qty` fold. |
| INV-2 single active spawn | Unaffected: signal-originated intents enter before the engine's spawn machinery, which enforces INV-2 identically for every intent origin. |
| INV-3 block on ambiguity | No bypass: a `BLOCKED` primary blocks new/replacement spawns regardless of whether the originating intent came from a signal or an operator. |
| INV-4 no oversell | `SignalProposal.suggested sizing` is advisory-only, never binding; actual sizing passes the same pre-submit risk gate; overfill quarantine semantics unchanged. |
| INV-5 fill dedup | Untouched. `signal_id` dedupe deliberately *mirrors* the `client_order_id`/`trade_id` idempotency practice but lives upstream in its own key space; signal events never key fills. |
| INV-6 monotonic status | Spawn status machinery untouched. The signal lifecycle is its own state machine (RECEIVED→terminal, no regression) — WO-0101 must spec it with the same monotonicity discipline. |
| INV-7 reduce-only, quantity-aware | The conversion gate applies `TradingState` rules: in `Reducing`, only risk-reducing signals are convertible, and the resulting intent is still evaluated by the same quantity-aware risk gate. **Human decision (Ameen, 2026-07-11): classification errors are asymmetric.** A false "risk-reducing" is backstopped by the risk gate; a false "not-risk-reducing" silently blocks a protective exit with **no** downstream backstop. WO-0101 must therefore spec the classification conservatively toward convertibility of genuine exits (with the risk gate as the binding check), WO-0103 must test the positive path (a genuine protective sell IS convertible in `Reducing`), and manual flatten remains the operator's signal-independent fallback either way. |
| INV-8 completion | Signals cannot mark primaries complete; no `SIGNAL_*` event reaches primary/spawn projections. |
| INV-9 position ≠ acks | The Position Service consumes only deduped fill events; the new `SIGNAL_*` event family is structurally invisible to it, exactly as `SUBMITTED`/`ACCEPTED` are. |

*INV-1..9 rows drafted line-by-line against `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5` on install (2026-07-11, implementer seat) — to be confirmed by the human + independent review before acceptance.*

## Options Considered

**A. HTTP boundary contract, advisory-only (chosen).** Complexity low-medium; zero new spine dependencies; producer fully swappable; failure modes contained by quarantine rails. Con: integration is shallow — no shared backtesting, no deep data reuse.

**B. Vendor Vibe-Trading code into the repo.** Rejected: violates pinned-stack/new-dependency rule at scale, imports an LLM-agent framework's whole surface into a safety-critical codebase, license and upstream-churn burden, and the audit wave would balloon.

**C. Embed an LLM agent as a backend module.** Rejected: puts nondeterminism inside the single-writer engine's process; blurs the seam the whole architecture is built on.

**D. Reverse direction — port the spine into Vibe-Trading.** Rejected for this project's goals: forfeits governance, CI gates, and the event-log-as-truth property; equivalent to starting over inside someone else's architecture.

## Consequences

Easier: adding/swapping producers (any agent that can POST JSON); auditing exactly what influenced trading (provenance in the event log); later trust-ladder promotion as a pure policy change behind a stable contract. Harder: the integration is deliberately shallow; every signal costs a human approval in beta (accepted — that *is* the design); one new API surface + event types to test on both storage paths. Revisit: L1 promotion criteria after beta produces approval-volume data.

## Action Items

1. [x] Renumber on install (ADR-010 draft → ADR-009) and clear install-verification + WO-0001-disposition gates — done 2026-07-11, evidence in the install note above.
2. [ ] Human review of this draft. (INV-1..9 mapping drafted from §5 on install, 2026-07-11 — confirm the rows, don't re-derive from scratch.)
3. [ ] Independent cross-model review: packet **REV-0022** queued (`work/review/REV-0022/request.md`) — dispatch at the human's discretion; acceptance blocked until it is dispositioned ACCEPT / ACCEPT-WITH-CHANGES.
4. [ ] WO-0101..0104 (installed to `work/queue/`, status draft) — all remain gated on this ADR's acceptance.
