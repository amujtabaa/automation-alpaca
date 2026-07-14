# ADR-009: Signal Seat — External Agentic Signal Producers as Bounded Intent Sources

**Status:** **Proposed** — acceptance of 2026-07-12 **RESCINDED 2026-07-14**: the formal REV-0022
packet (frozen `25590a7`) returned **BLOCK** with four P1 findings (credential/transport boundary,
non-atomic approval→intent conversion, unbounded/underspecified TTL + classification semantics,
unbounded audit growth). Not acceptable until F-001..F-004 are remediated in this document and the
re-review clears. Full record: `work/review/REV-0022/`.
**Date:** 2026-07-11 (drafted); accepted 2026-07-12; rescinded 2026-07-14
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
> 3. **Acceptance** — OPEN (rescinded 2026-07-14): REV-0022's formal run returned BLOCK; this
>    document remains Proposed until F-001..F-004 are remediated and the re-review is
>    dispositioned ACCEPT / ACCEPT-WITH-CHANGES.

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
   **Role separation (Codex PR #5 P1, incorporated pre-acceptance):** per-producer API keys are **ingestion-scoped** — valid for `POST /signals` and nothing else. **Identity binding (Codex round 3):** `producer_id` is never trusted from the request body — the server derives it from the authenticated API key; a body-supplied `producer_id` that mismatches the credential is rejected at the boundary. Producer A therefore cannot consume producer B's dedupe/rate-limit/quarantine namespace or forge provenance under B's identity (mismatch tests required for dedupe and rate-limit/quarantine accounting). Approval, rejection, and producer-release are **operator-only** routes authenticated by a distinct operator credential; a producer credential structurally cannot invoke them, proven by negative tests. This is a deliberate departure from the beta as-built posture (`app/api/deps.py` `get_actor` is an audit label, not authentication — accepted while the backend was single-user localhost): admitting authenticated external producers ends that assumption, so the credential split lands **with** the first signal endpoint (WO-0102/0103), not after. **And it cuts both ways (Codex round 4):** scoping the producer key is worthless while the existing command routes accept unauthenticated requests (`get_actor` defaults to `operator` when no header is sent) — a producer could simply omit its key. From the moment a producer can reach FastAPI, **every sensitive route — reads included — requires a valid operator credential** per the route-authorization matrix, transport policy, and key-lifecycle rules of **Amendment A-1** (REV-0022 F-001 extended the earlier mutating-routes-only requirement: a producer must learn nothing about positions, orders, sessions, or other producers). **Sequencing (Codex round 5): the cockpit's credential plumbing ships in the same change as the enforcement flip** — the browser client currently sends no auth header, and a window in which the operator's kill switch or manual flatten answers 401 is an unacceptable safety regression (invariant 11).
2. **Schema.** `SignalProposal`: `producer_id`, deterministic `signal_id` (producer-generated, ULID or equivalent — enables idempotent dedupe, mirroring `client_order_id` practice), `issued_at`, `ttl_seconds`, instrument, direction, *suggested* sizing (advisory field, never binding), thesis text, provenance blob (model, prompt/version identifiers, source citations). Pydantic-validated at the boundary; validation failure → quarantine, not rejection-and-forget. **The idempotency/dedupe key is `(producer_id, signal_id)` — server-namespaced per producer, never the bare `signal_id`**: producers are untrusted, so one producer reusing (accidentally or deliberately) another's id must not quarantine or provenance-collide the other's legitimate signal (Codex review on PR #5, incorporated pre-acceptance).
3. **Event-log provenance.** Every signal's lifecycle is appended to the event log as first-class events: `SIGNAL_RECEIVED` → one of `SIGNAL_QUARANTINED` | `SIGNAL_EXPIRED` | `SIGNAL_REJECTED` (human) | `SIGNAL_APPROVED` (human). Approval emits a normal order intent into the existing path via the **atomic conversion command of Amendment A-2** (one lock/transaction: re-checks, one approval consumed, `SIGNAL_APPROVED`, one intent — all or nothing) — from that point the signal has no special *authority* whatsoever, but the *correlation* survives (Codex round-5 P2): `SIGNAL_APPROVED` carries the id of the candidate/sell-intent it created, and the created intent's origin/audit payload carries `(producer_id, signal_id)` back-reference. With multiple approved signals on one symbol, the event trace of any order must be filterable back to exactly the signal that influenced it — otherwise the "audit exactly what influenced trading" benefit in §Consequences is an empty claim. Test-proven in WO-0103.
   **Operator-derived sizing and pricing (Codex round 4):** "advisory, never binding" must survive conversion mechanics. The as-built candidate path builds the LIMIT order from `candidate.suggested_quantity` / `suggested_limit_price` (`app/store/core.py:641+`) — whoever populates those fields controls the order. Therefore the approval action itself carries the **operator-confirmed quantity and limit price** (entered or explicitly confirmed by the human in the approval UI, validated server-side); producer-suggested sizing is display-only context and never flows into any order field. WO-0101 specs the approval payload; WO-0103 proves by test that the dispatched order's qty/price come from the approval payload, not the `SignalProposal`.
   **Direction-aware conversion (Codex PR #5 round-3 P1):** the as-built intent origins are direction-specific — candidate approval creates BUY orders; SELLs originate only as `SellIntent` with reason `manual_flatten` or `protection_floor`. A sell-direction signal therefore needs a defined origin: WO-0101's spec must specify the signal sell path (e.g. a new `SellReason.SIGNAL` on the existing `SellIntent` machinery, routing through the same session-control/risk/kill-switch gates as manual flatten) rather than misrouting signal sells through the buy or manual-flatten paths. This is load-bearing for the INV-7 asymmetry decision above — the protective-sell-in-`Reducing` test needs a real sell route to exercise.
4. **Trust ladder.** L0 — advisory: every signal requires per-signal human approval before becoming an order intent (beta scope, this ADR). L1 — batch approval queues; L2 — bounded autonomy within pre-approved risk envelopes. **L1 and L2 are explicitly out of scope and each requires its own superseding ADR plus independent review**, since they move the human gate.
5. **Rails (quarantine semantics extended to signals).**
   - TTL/staleness: server-owned semantics per **Amendment A-3** — `expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)`, explicit skew bounds, durable deadline, atomic re-check at conversion. A stale signal can never be approved.
   - Malformed, duplicate-conflicting, or self-contradictory signals → `SIGNAL_QUARANTINED`, recorded never hidden.
   - Per-producer rate limits; breach → producer-level quarantine (all further signals quarantined until human release). **Rails ship no later than exposure (Codex round 6):** the ingestion endpoint carries a conservative hard ingest ceiling from its first commit, superseded (never just removed) by the full rate-limit/quarantine rails — there is no window in which an enabled endpoint lacks flood protection. The human **release** action has a browser path (cockpit control), not raw-API-only — invariant 11. **Post-quarantine backpressure:** superseded by **Amendment A-4** — one `PRODUCER_QUARANTINED` event per epoch, saturating out-of-log counter, one summary on release; nothing periodic (the earlier "periodic rejected-count record" was unbounded over indefinite hostility — REV-0022 F-004).
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


## Amendments — REV-0022 remediation (2026-07-14, PROPOSED, pending human acceptance + re-review)

Each amendment below remediates one BLOCK finding and is **binding ADR text** once this document
is accepted — implementation WOs tune numbers only, never semantics. Drafted by the implementer
seat; nothing here is in force until Ameen accepts and the re-review clears.

### A-1 (remediates F-001) — Transport and credential-lifecycle boundary

1. **Transport policy** (`Settings.signal_transport_policy`, mandatory when `signal_seat_enabled`):
   - `loopback` (beta default): the backend binds `127.0.0.1` only; producers and cockpit run on
     the same host. Startup **fails fast** if the bind address is non-loopback under this policy.
   - `tls_proxy`: external exposure happens ONLY through a TLS-terminating reverse proxy — and
     the backend listener itself stays **proxy-private**: it binds loopback (or a Unix socket)
     with the proxy forwarding to it on the same host. The startup guard verifies the **bind**,
     not just the flag: with `signal_seat_enabled`, a non-loopback/non-socket backend bind fails
     fast under BOTH policies — a same-network client must never be able to bypass the proxy and
     hit the plain-HTTP backend port directly (Codex rev-2 finding). Plain HTTP across a network
     boundary is never a supported configuration.
2. **Key lifecycle**: keys are env-injected secrets (never committed, never logged, redacted in
   error paths); comparison is constant-time (`secrets.compare_digest`); rotation = deploy a new
   key map (producer map supports N keys per producer to allow overlap-rotation); revocation =
   remove the key from the map (effective on config reload/restart). Actor identity on every
   authenticated request derives from the **authenticated principal**, with `X-Actor` demoted to
   an optional sub-label recorded alongside it — never a substitute.
3. **Route authorization matrix** (normative; tested at the real mounted app in WO-0102):
   when `signal_seat_enabled` is on, **every sensitive route — reads included — requires the
   operator credential**: positions, orders, sessions, watchlist, candidates, review queues,
   signal list, producer states, and all mutating commands. Producer keys authorize exactly one
   route: `POST /api/signals`. The matrix {none, invalid, producer-key, operator-key} × {every
   mounted route} is enumerated in the spec (`04-auth-and-api.md` §1a — an explicit
   classification table covering every router `create_app` mounts: system/health, session,
   watchlist, candidates, trading, controls, review, marketdata, dev, signals, producers) and
   enforced **fail-closed**: a parameterized test introspects the mounted app's actual routes at
   runtime and FAILS if any route is absent from the classification table — a new or forgotten
   route cannot silently ship unclassified (Codex rev-2 finding). Unauthenticated or
   producer-credentialed access to any sensitive route, reads included, is 401/403. Rationale: an untrusted producer with network reach must learn nothing about
   positions, orders, sessions, or other producers' theses.

### A-2 (remediates F-002) — Atomic conversion contract

Approval→intent conversion is **one atomic store command** in both stores:

- The conversion is a **dedicated atomic store command** (both stores). The existing facade
  composition — `await gate.approve(candidate_id)` then `await create_order_for_candidate(...)`
  (`app/facade/store_backed.py`) — is **explicitly forbidden** inside signal conversion: its
  inter-await window is precisely the F-002 crash window (Codex rev-2 re-confirmed it in the
  as-built code). The store command performs the candidate/sell-intent mint, approval, and order
  creation as one plan-and-apply inside the lock.
- Under a single lock hold (memory) / one transaction (SQLite), the command: re-reads the
  signal's status and server deadline (A-3), the producer-quarantine epoch, the current
  `TradingState`/kill-switch, and the fresh derived position **plus outstanding sell-intent
  exposure**; evaluates the risk decision; consumes exactly one operator approval; appends
  `SIGNAL_APPROVED`; and creates + links exactly one direction-correct intent — **all or
  nothing**. No `await` between the checks and the durable writes (the ENG-001 exit-open
  pattern). The memory store's `_atomic` snapshot MUST include signal state (the envelope
  branch's REV-0023 F7 showed what omission costs).
- Failure anywhere → nothing persisted: no `SIGNAL_APPROVED`, no intent, signal stays RECEIVED,
  structured operator-visible refusal. Crash/interruption at any point leaves either the
  complete result or none of it — proven by crash-injection tests at every interleaving point,
  plus races against expiry, producer quarantine/release, TradingState flips, and duplicate
  approval, in both stores (WO-0103 required tests).
- **Option E, considered and recorded** (reviewer's ask): a separate bounded signal-inbox store
  + idempotent conversion-outbox would decouple untrusted-volume lifecycle traffic from
  execution replay entirely. **Recommended: not for beta.** With A-4's hard bounds the signal
  event volume is finite and small; one log + one atomic command preserves the single-writer,
  one-truth property that the whole spine is built on, at beta's volume. Option E is the
  designated evolution IF L1 (batch approval) ever raises signal volume by orders of magnitude —
  that superseding ADR must re-evaluate it. This paragraph exists so the choice is a decision,
  not an omission.

### A-3 (remediates F-003) — Server-owned freshness and classification semantics

- **Expiry is server-computed at ingest and durable:**
  `expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)` with
  `received_at` = injected server clock at ingest; `server_max_ttl` default **3600 s**
  (Settings-tunable, hard architectural cap **86400 s** — no config can exceed it);
  `ttl_seconds` accepted range `[30, 86400]` (outside → quarantine). A producer can therefore
  never keep a thesis approvable longer than `server_max_ttl` regardless of its own TTL.
- **Skew bounds:** `issued_at > received_at + 30 s` → quarantine (`issued_at_future`);
  `issued_at < received_at − 24 h` → quarantine (`issued_at_stale`). All comparisons use the
  injected clock; naive datetimes are rejected at validation.
- **Restart behavior:** `expires_at` is persisted at ingest and never re-derived — a restart
  changes nothing; replay reconstructs the identical deadline from `SIGNAL_RECEIVED`'s payload.
- **Conversion re-checks the deadline atomically** inside the A-2 command (same lock, same
  injected clock read).
- **Risk-reducing classification (executable form; supersedes the position-only draft):** a
  signal is risk-reducing iff `direction == sell` AND
  `operator_qty ≤ (live derived position − outstanding committed sell exposure)`, both terms
  read under the A-2 lock; `outstanding committed sell exposure` = Σ target quantities of
  non-terminal sell intents + open SELL order remaining quantities for the symbol. Two signal
  sells can therefore never jointly oversell via classification. Refusals carry stable reason
  codes (`TRADING_STATE_REDUCING`, `POSITION_CHANGED`, `TRADING_HALTED`, `KILL_SWITCH`),
  operator-visible, never silent — the recorded INV-7 asymmetry decision stands (conservative
  toward convertibility; the quantity-aware risk gate remains the binding check).

### A-4 (remediates F-004) — Finite ingest and audit bounds

Ingest processing order is normative: **(1) authenticate** (constant-time key lookup, before any
body read) → **(2) rails check** (quarantine epoch, rate limit / interim ceiling) → **(3) bounded
body read** (`Content-Length` capped at **64 KiB**, streamed reject beyond) → **(4) parse +
field-validate** (thesis ≤ 4000 chars, provenance ≤ 20 keys × 500 chars). Steps 1–2 reject with
zero store writes and zero body processing — with **exactly one carve-out**: the single request
that first breaches the rate limit performs the epoch-opening `PRODUCER_QUARANTINED` append (once
per epoch, by definition); every subsequent step-1/step-2 reject in that epoch is write-free
(Codex rev-2 finding: without the carve-out the breach path is unimplementable as written).

Audit bounds (replacing the draft's "periodic rejected-count record", which the reviewer
correctly showed is unbounded over indefinite hostility):

- **The rate limit debits EVERY authenticated ingest** — valid, invalid, or duplicate — not
  merely accepted proposals (Codex rev-2 finding: otherwise endless unique parseable-but-invalid
  bodies each record `SIGNAL_QUARANTINED` without ever consuming the bucket, growing the log
  unbounded once the interim ceiling retires). Validation-quarantine events are therefore
  bucket-bounded by construction.
- **At most ONE `PRODUCER_QUARANTINED` event per quarantine epoch** (epoch = quarantine →
  release). Post-quarantine ingress appends **nothing**.
- Rejected-request counting is a **saturating in-memory counter outside the event log**
  (diagnostic, best-effort across restarts by design).
- **One summary on epoch close:** `PRODUCER_RELEASED` carries the saturated rejected-count and
  epoch window. Total signal-rail event volume per producer per epoch is therefore a constant
  (≤ 2 events + the pre-quarantine accepted signals, themselves rate-limited).
- Test contract (WO-0102/0104): model-based/long-duration tests assert **constant event-row
  count** and bounded storage under sustained hostile flood — not merely "fewer than requests".

## Action Items

1. [x] Renumber on install (ADR-010 draft → ADR-009) and clear install-verification + WO-0001-disposition gates — done 2026-07-11, evidence in the install note above.
2. [x] Human review — INV-7 asymmetry decision (2026-07-11); the 2026-07-12 acceptance was rescinded (see Status).
3. [ ] Independent cross-model review — **REV-0022 returned BLOCK** (formal packet, frozen `25590a7`); remediate F-001..F-004 here, then re-review. The PR #5 sixteen-finding record remains applied but does not clear the gate.
4. [ ] WO-0101..0104: RE-GATED 2026-07-14 pending F-001..F-004 remediation + re-review. WO-0101's spec output stands as draft input to the remediation.
