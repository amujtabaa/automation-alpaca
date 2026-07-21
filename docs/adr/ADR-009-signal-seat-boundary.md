# ADR-009: Signal Seat — External Agentic Signal Producers as Bounded Intent Sources

**Status:** **Proposed — remediation drafted 2026-07-21; REV-0034 pending.** The 2026-07-12
acceptance was rescinded after REV-0022 returned BLOCK. Archive remediation rounds hardened
A-1..A-4, but no archive packet carried an ACCEPT / ACCEPT-WITH-CHANGES verdict on the final
master-side specification. WO-0127 reconciles that text to today's tree and ratified D-SIG-1..9
without accepting it. G1 clears only after the Claude-seat REV-0034 review returns
ACCEPT / ACCEPT-WITH-CHANGES and Ameen approves the final text.
**Date:** 2026-07-11 (drafted); 2026-07-21 (master-side remediation draft)
**Deciders:** Ameen (human gate). Implementer: Codex. Reviewer: Claude seat via REV-0034.
**Number:** ADR-009.
**Implementation gate:** WO-0102..0104 remain gated drafts. The fresh `signal_records` schema
approval is deliberately deferred until R4 presents current DDL.

> **Archive provenance only.** The amendment basis is
> `origin/archive/claude-wo-0001-install-checks-2x5ys8`. References below to archive
> archive REV-0024/0025 describe evidence at that ref; those packet ids are not ported, do not occupy a
> master review slot, and do not clear REV-0034.
>
> **Ratified topology for this draft.** V1 producers are localhost-only (`loopback`). A future
> tailnet producer is a configuration change through `tailnet_serve`, while the backend remains
> loopback-bound. Tailscale Funnel and every other public exposure are forbidden. External
> TradingView/webhook producers are addressed only by Proposed ADR-013 and remain gated on
> D-HOST-1 deployment/auth ADR acceptance plus independent review.

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
   - Per-producer rate limits; breach → producer-level quarantine (all further signals quarantined until human release). **Rails ship no later than exposure, now enforced structurally (Codex round 6; superseded by Amendment A-4 after archive REV-0024):** the earlier "conservative interim ingest ceiling from the first commit" is **withdrawn** — it was rate-bounded, not storage-bounded (archive REV-0024-F-004). Instead, `signal_seat_enabled` is **gated on full rails by a rails-presence startup guard**: an enabled endpoint structurally cannot run without the refilling rate bucket, the non-refilling invalid/conflict budget, the producer-quarantine epoch, and the human release path — so there is no window in which an enabled endpoint lacks finite-audit flood protection. The human **release** action has a browser path (cockpit control), not raw-API-only — invariant 11. **Post-quarantine backpressure and finite audit:** per **Amendment A-4** — one `PRODUCER_QUARANTINED` event per epoch (opened by rate-bucket breach or invalid/conflict-budget exhaustion), saturating out-of-log counter, one summary on release; nothing periodic (the earlier "periodic rejected-count record" was unbounded over indefinite hostility — REV-0022 F-004; the refilling-bucket-only bound was likewise unbounded under paced hostility — archive REV-0024-F-002).
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

*INV-1..9 rows were re-reconciled to the current invariant registry in `docs/spec/signal-seat/06-invariants.md`; REV-0034 must review those claims as claims, not proof.*

## Options Considered

**A. HTTP boundary contract, advisory-only (chosen).** Complexity low-medium; zero new spine dependencies; producer fully swappable; failure modes contained by quarantine rails. Con: integration is shallow — no shared backtesting, no deep data reuse.

**B. Vendor Vibe-Trading code into the repo.** Rejected: violates pinned-stack/new-dependency rule at scale, imports an LLM-agent framework's whole surface into a safety-critical codebase, license and upstream-churn burden, and the audit wave would balloon.

**C. Embed an LLM agent as a backend module.** Rejected: puts nondeterminism inside the single-writer engine's process; blurs the seam the whole architecture is built on.

**D. Reverse direction — port the spine into Vibe-Trading.** Rejected for this project's goals: forfeits governance, CI gates, and the event-log-as-truth property; equivalent to starting over inside someone else's architecture.

## Consequences

Easier: adding/swapping producers (any agent that can POST JSON); auditing exactly what influenced trading (provenance in the event log); later trust-ladder promotion as a pure policy change behind a stable contract. Harder: the integration is deliberately shallow; every signal costs a human approval in beta (accepted — that *is* the design); one new API surface + event types to test on both storage paths. Revisit: L1 promotion criteria after beta produces approval-volume data.


## Proposed amendments — REV-0022 remediation (REV-0034 pending)

Each amendment below remediates one REV-0022 BLOCK finding. Archive rounds supplied the hardened
basis; WO-0127 narrows and reconciles it to current master. The text remains Proposed and
non-implementable until REV-0034 and Ameen's post-review approval.

### A-1 (remediates F-001) — Transport and credential-lifecycle boundary

1. **Transport policy** (`Settings.signal_transport_policy`, mandatory when `signal_seat_enabled`):
   - `loopback` (beta default): the backend binds `127.0.0.1` only; producers and cockpit run on
     the same host. Startup **fails fast** if the bind address is non-loopback under this policy.
   - `tailnet_serve`: remote access happens only through `tailscale serve`; the backend listener
     remains loopback-bound (or uses a same-host Unix socket). Tailnet identity is transport
     authentication, not a substitute for the producer/operator keys.
   - **Forbidden:** Tailscale Funnel, a public reverse proxy, a public/non-loopback backend bind,
     or any other Internet exposure. A spec-level negative test must reject every such transport
     value/configuration. ADR-013 is the only proposed path toward public webhook ingress and never
     makes the trading API public.
   Under both allowed policies the construction-time launcher guard verifies the actual bind.
   Plain HTTP across a network boundary is unsupported.
2. **Key lifecycle**: keys are env-injected secrets (never committed, never logged, redacted in
   error paths); comparison is constant-time (`secrets.compare_digest`); rotation = deploy a new
   key map (producer map supports N keys per producer to allow overlap-rotation); revocation =
   remove the key from the map (effective on config reload/restart). Actor identity on every
   authenticated request derives from the **authenticated principal**, with `X-Actor` demoted to
   an optional sub-label recorded alongside it — never a substitute.
3. **Route authorization matrix** (normative; tested at the real mounted app in WO-0102):
   when `signal_seat_enabled` is on, **every sensitive route — reads included — requires the
   operator credential**: positions, orders, sessions, watchlist, candidates, review queues,
   signal list, producer states, and all mutating commands. The current matrix explicitly includes
   `POST /api/session/close` (`app/api/routes_system.py:48`) and the post-fork envelope routes
   `GET /api/envelopes`, `POST /api/envelopes/approve`, and
   `POST /api/envelopes/{envelope_id}/cancel`
   (`app/api/routes_trading.py:289,299,318`). Producer keys authorize exactly one
   route: `POST /api/signals`. The matrix {none, invalid, producer-key, operator-key} × {every
   mounted route} is enumerated in the spec (`04-auth-and-api.md` §1a — an explicit
   classification table covering every router `create_app` mounts: system/health, session,
   watchlist, candidates, trading, controls, review, marketdata, dev, signals, producers) and
   enforced **fail-closed**: a parameterized test introspects the mounted app's actual routes at
   runtime and FAILS if any route is absent from the classification table — a new or forgotten
   route cannot silently ship unclassified (Codex rev-2 finding). Unauthenticated or
   producer-credentialed access to any sensitive route, reads included, is 401/403. Rationale: an untrusted producer with network reach must learn nothing about
   positions, orders, sessions, or other producers' theses.

4. **Credential-presence startup guard**: with `signal_seat_enabled`, startup **fails fast** unless
   `OPERATOR_API_KEY` is set non-blank AND the producer key map is loaded. An enabled flag with no

   operator key makes every sensitive route (kill switch, flatten, cockpit reads) permanently 401
   with no credential to supply — recreating the lockout A-1 forbids (Codex rev-3). Tested.
5. **Auto-docs routes**: FastAPI auto-registers `/openapi.json`, `/docs`, `/redoc`,
   `/docs/oauth2-redirect`. With `signal_seat_enabled` these are **disabled** (they disclose the API
   surface to reachable producers); a deployment that needs them puts them behind the operator
   credential. Either way they are classified in the §1a matrix and tested — never public (Codex rev-3).
6. **Backend-owned server launch — the enforceable bind seam** (Ameen decision 2026-07-14,
   remediates archive REV-0024-F-001). Clause 1's proxy-private-bind guarantee is unobservable from inside
   `create_app`: the ASGI lifespan scope never carries the listener address (it appears only on
   per-request HTTP scopes, after startup), and `uvicorn`'s `--host`/`--uds` are set on the CLI,
   outside the app and taking precedence over any application setting. A guard that only compares an
   application setting can therefore be green while the process is actually serving `0.0.0.0`. The
   boundary is closed by moving the guard onto a launch seam the backend owns:
   - **A backend-owned launch entrypoint** (`app/server.py::run()`, invoked as `python -m app` /
     the sole documented start command) reads the validated `signal_transport_policy` + bind from
     `Settings` and starts Uvicorn **programmatically** (`uvicorn.Server`/`uvicorn.run(app, host=…,
     uds=…)`) with the bind derived from — and re-validated against — that setting. With
     `signal_seat_enabled`, the entrypoint **refuses to start** (process exits non-zero, before any
     socket serves) on any non-loopback/non-socket bind, under both transport policies.
   - **Construction-time launch-provenance capability — no listener without the launcher** (Ameen
     decision 2026-07-14 D-1, remediates archive REV-0024-F-001 / archive REV-0025-F-001). A request-time 503 guard
     is **insufficient**: it still lets a bare `uvicorn app.main:app --host 0.0.0.0 --lifespan off`
     **accept TCP connections and serve `HTTP 503` on the forbidden non-loopback port** (Codex
     archive REV-0025 live-reproduced this) — reachable is not proxy-private, and A-1's invariant demands
     failure **before any socket accepts**. So the guarantee is enforced at **app construction /
     import**, before Uvicorn can open a listener: the sanctioned launcher mints an **opaque,
     one-shot, code-owned capability** (an in-process token created in `app/server.py::run()`,
     **not** an env var, config value, or anything an operator/attacker can set) and passes it to a
     construction factory; with `signal_seat_enabled` on, **building the app without that capability
     raises** (`create_app`/the factory refuses). Constraints on the capability: **no environment
     switch, no importable pre-authorized `app` object, and no zero-argument authorized factory** may
     mint it — otherwise the bare-uvicorn path could re-acquire it. Consequently the module-level
     `app = create_app()` import target is **removed (or itself refuses) under the flag**: a bare
     `uvicorn app.main:app` fails at **import**, Uvicorn never receives an app, and **no listener is
     ever opened** — true pre-serve failure, connection refused, nothing on the network port.
   - **A fail-closed ASGI request guard remains as defense-in-depth** (not the primary control): if
     any future path constructs a flag-on app without the capability, every request is refused. But
     the *binding* guarantee is the construction refusal above — the request guard is the backstop,
     not the boundary.
   - **The direct `uvicorn app.main:app` invocation is unsupported when the seat is enabled** (it
     fails at import — no listener); the README documents `python -m app` as the sole sanctioned start
     command for an enabled seat. (Flag off ⇒ construction is unrestricted; beta's current
     `uvicorn app.main:app` dev command works unchanged.)
   - **Proof (WO-0102 subprocess tests, mutation-sensitive — archive REV-0025-F-002):** with `OPERATOR_API_KEY`
     + producer map + rails all present (so no *unrelated* startup guard supplies the failure): (a)
     `uvicorn app.main:app --host 0.0.0.0` with the flag on, **both `--lifespan on` and `--lifespan
     off`**, fails to open an accepting listener — the hostile client gets **connection refused / no
     listener**, asserted at the socket level, not an HTTP 503; (b) a **same-config positive control**
     — the sanctioned `python -m app` launcher on the policy-valid loopback bind — reaches a **ready
     listener** serving `GET /api/health`; (c) the launcher with a non-loopback bind + flag on exits
     non-zero before serving, asserting the **exact A-1 bind-policy failure reason** (not a generic
     pre-serve error). Removing/mutating any single A-1 check must make its own assertion fail; an
     app-setting-only, lifespan-only, or reachable-503 assertion does not satisfy this clause.

### A-2 (remediates F-002) — Atomic conversion contract

Approval→intent conversion is **one atomic store command** in both stores:

- The conversion is a **dedicated atomic store command** (both stores). The existing facade
  composition at `app/facade/store_backed.py:786-787` — `await gate.approve(candidate_id)` then `await create_order_for_candidate(...)`
  (`app/facade/store_backed.py`) — is **explicitly forbidden** inside signal conversion: its
  inter-await window is precisely the F-002 crash window (Codex rev-2 re-confirmed it in the
  as-built code). The store command performs the ordinary Candidate/SellIntent mint, approval, and order creation as one plan-and-apply inside the
  lock, composing the current candidate planner at `app/store/core.py:887`. Per D-SIG-8 these are
  the same objects the cockpit creates; downstream execution is identical to manual flow
  (including ADR-010 envelope delegation when selected), with no signal-only execution lane.
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
  execution replay entirely. **Recommended: not for beta.** A-4 makes the *hostile* signal event
  volume finite (attributable-rejection appends are hard-bounded per epoch by the non-refilling
  budget, and post-quarantine ingress is write-free). **Scope honesty (archive REV-0024-F P1):** *legitimate*
  accepted-signal volume is **rate-bounded, not finite over indefinite time** — a well-behaved
  producer sending valid proposals at the refill rate grows the event log like any other legitimate
  rate-limited activity (each such signal also self-limits via the A-3 TTL, so the operator queue
  stays bounded even though the append-only audit trail does not). That is acceptable at beta's
  single-operator, paper-only volume, and is the normal cost of an event-sourced spine; it is **not**
  a claim of globally finite storage. Option E is the designated evolution IF L1 (batch approval) or
  sustained legitimate volume ever raises signal throughput by orders of magnitude — that superseding
  ADR must re-evaluate it. One log + one atomic command preserves the single-writer, one-truth

  property the whole spine is built on, at beta's volume. This paragraph exists so the choice is a
  decision, not an omission.

### A-3 (remediates F-003) — Server-owned freshness and shared exposure semantics

- **Expiry is server-computed at ingest and durable:**
  `expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)`, with
  `received_at` from the injected server clock; `server_max_ttl` default 3600 s and hard cap
  86400 s; producer TTL range `[30, 86400]`. Out-of-range input quarantines.
- **Skew bounds:** future beyond +30 s quarantines as `issued_at_future`; older than −24 h
  quarantines as `issued_at_stale`. Persisted `expires_at` is replayed, never re-derived.
- **Conversion re-checks deadline/status/quarantine/TradingState atomically** inside A-2.
- **One shared committed-exposure projection, no hand sum.**
  `project_committed_sell_exposure(symbol, orders, envelopes, recoveries, events)` lives beside
  `project_envelope_obligation` (`app/store/core.py:1401`) and returns
  `{quantity, contributions, ambiguity_flags}`. Both stores call it under the A-2 lock/transaction
  and the cockpit exposure display consumes the same result.
- **Contribution identity and coalescing:** (a) a live envelope mandate contributes its
  `remaining_quantity`; its own children are not double-counted; (b) direct/legacy SELL orders
  in the may-execute set contribute unfilled remainder; (c) open SELL recovery rows in
  `RECOVERY_OPEN_STATUSES` (`app/models.py:893`) contribute venue exposure; (d) INV-091
  `UNKNOWN_RECONCILE_REQUIRED` and accepted-submit fallback facts contribute if not otherwise
  represented. An exact order/recovery/fallback `(local_order_id, broker_order_id)` coalesces as
  one leg; distinct broker acceptances remain distinct. `needs_review` contributes full recovery
  quantity.
- **Fail closed:** malformed identity, projection ambiguity, or unbounded quantity refuses
  conversion. Refusals carry the contribution breakdown.
- **Universal ceiling:** in every TradingState,
  `operator_qty <= live_fill_derived_position - committed_exposure.quantity`. Ordinary risk,
  opposite-side, claim, recovery, and envelope rails also remain binding.
- **Cross-consistency pin:** wherever committed exposure is at least the position, the boolean
  `_same_symbol_exit_may_execute` rails and the quantity view must agree. T1.3 AST checks
  enumerate the projection producer and all store/cockpit consumers.
- **D-SIG-7 — no multi-exit relaxation.** Signal SELL conversion preserves the existing
  sell-intent single-flight rule and INV-087 one-ACTIVE-envelope-per-symbol mandate. Occupied
  single flight refuses the signal atomically; it is not reused or widened.
- **D-SIG-8 — ordinary objects/ordinary downstream.** BUY signals mint the same Candidate and SELL
  signals the same SellIntent as cockpit/manual flows. If the operator delegates through an
  execution envelope, the ordinary ADR-010 path is used. Signal correlation is provenance, not
  authority, and creates no execution lane.
- Stable refusal codes include `TRADING_STATE_REDUCING`, `POSITION_CHANGED`,
  `TRADING_HALTED`, `KILL_SWITCH`, `SINGLE_FLIGHT_CONFLICT`, and an ambiguity code carrying
  the breakdown. The INV-7 error-direction asymmetry remains: classification is conservative
  toward legitimate exits, but the ordinary quantity-aware risk gate is binding.

### A-4 (remediates F-004) — Finite ingest and audit bounds

Ingest processing order is normative: **(1) authenticate** (constant-time key lookup, before any
body read) → **(2) rails check** (quarantine epoch, refilling rate bucket; no parse-validity
qualifier) → **(3) bounded body read** (`Content-Length` capped at **64 KiB**, streamed reject
beyond) → **(4) parse + field-validate** (thesis ≤ 4000 chars, provenance ≤ 20 keys × 500 chars).
The non-refilling invalid/conflict budget is debited at step 4 when an attributable-rejection event
is appended; **the append that consumes the last slot co-appends the `PRODUCER_QUARANTINED`
epoch-opener in the same atomic op** (Ameen decision 2026-07-14, archive REV-0025-F P1 — supersedes the
earlier "epoch opens on the next ingest," which left a zero-budget-but-un-quarantined gap where an
exhausted producer's RECEIVED signals were still approvable). Steps 1–2 reject with zero store writes
and zero body processing — with **exactly one carve-out**: the single request that first crosses
**either** breach threshold — rate-bucket empty (opens on that request) **or** invalid/conflict
budget exhausted (co-opened by the exhausting step-4 append) — performs the epoch-opening
`PRODUCER_QUARANTINED` append (once per epoch, by definition); every subsequent reject in that epoch
is write-free.

Audit bounds (replacing the draft's "periodic rejected-count record", which the reviewer
correctly showed is unbounded over indefinite hostility):

- **The rate limit debits EVERY authenticated ingest** — valid, invalid, or duplicate — not
  merely accepted proposals (Codex rev-2 finding: otherwise endless unique parseable-but-invalid
  bodies each record `SIGNAL_QUARANTINED` without ever consuming the bucket). This bounds
  *throughput*; the non-refilling budget below bounds *storage*.
- **A finite, non-refilling per-producer invalid/conflict budget bounds the *storage*, not just
  the rate** (Ameen decision 2026-07-14, remediates archive REV-0024-F-002 / REV-0022-F-004). The refilling
  rate bucket (60/hour) bounds *throughput* but **not** the append-only log: a producer paced at or
  below the refill rate keeps the bucket non-empty forever, never breaches, and appends one
  `SIGNAL_QUARANTINED` (validation) or one novel-hash `SIGNAL_DUPLICATE_CONFLICT` per request
  indefinitely (Codex probe: 10080 events over 7 days at 1/min, bucket never below 9 tokens). So
  **in addition to** the refilling bucket, each producer holds a **non-refilling** budget
  `signal_invalid_budget_per_epoch` (default **50**, `Settings`-tunable within **`[1, 1000]`**; a
  hard architectural cap of **1000** that no config may exceed — startup **fails fast** on a value
  outside the range, mirroring `server_max_ttl`'s cap so the "finite and small" property cannot be
  configured away, archive REV-0024-F P2). It is debited by **every attributable terminal-at-ingest append**
  — one that authenticates, embeds the proposal, and grows the log: validation/skew `SIGNAL_QUARANTINED` (NOT the `producer_sweep` quarantine — that does not debit),
  each novel-hash `SIGNAL_DUPLICATE_CONFLICT`, **and** each dead-on-arrival `SIGNAL_EXPIRED`
  (`expires_at ≤ received_at`, or a skew-based `issued_at_future`/`issued_at_stale` terminal quarantine)
  — so a producer cannot evade the budget by pacing unique just-expired proposals (archive REV-0024-F P1). It
  does **not** refill while the producer is un-quarantined; on exhaustion the producer is
  **quarantined** (`PRODUCER_QUARANTINED` opens the epoch), after which ingress is write-free per the
  epoch rule; the budget **resets only on human release** (`PRODUCER_RELEASED` — clause below).
  **The check-reserve-debit and the terminal event append are one linearizable store operation**
  (one memory lock / one SQLite transaction — archive REV-0025-F-003): a request that cleared the pre-body
  step-2 rails check re-checks-and-debits atomically at step 4, so with one slot left, concurrent or
  slow-streamed-body requests cannot each append — exactly one consumes the slot, the rest are
  post-exhaustion; a crash leaves either the whole {debit + event} or neither, both stores.
  **Both the pinned per-cycle limit AND the consumed/remaining count are durable producer-rail state**
  restored **before serving** and updated atomically with each terminal append (archive REV-0025-F-004): a
  restart cannot reset consumed slots to zero (which would grant a fresh budget without a human

  release); replay reconstructs both the historical limit and the consumed count in both stores.
  The **constant storage bound is on attributable-rejection traffic only**: per cycle **≤
  `invalid_budget` terminal-at-ingest events + 2 rail events**, and every *further* cycle requires a
  human `PRODUCER_RELEASED` — so indefinitely-paced invalid/conflict/expiry hostility can no longer
  append forever. (Legitimately *accepted* signals are separately **rate-bounded, not part of this
  constant** — see the Option-E scope note in A-2: their volume is finite per window but not over
  indefinite time, by design.)
- **At most ONE `PRODUCER_QUARANTINED` event per quarantine epoch** (epoch = quarantine →
  release), opened by **either** trigger — rate-bucket breach **or** invalid/conflict-budget
  exhaustion. Post-quarantine ingress appends **nothing**.
- Rejected-request counting is a **saturating in-memory counter outside the event log**
  (diagnostic, best-effort across restarts by design).
- **One summary on epoch close:** `PRODUCER_RELEASED` carries the saturated rejected-count and
  epoch window, and **resets BOTH rails — the §1 refilling bucket AND the §1a non-refilling
  invalid/conflict budget** (archive REV-0024-F P1: releasing without resetting the budget re-quarantines the
  producer on its very next ingest, making the human release control inert). The **constant** bound
  covers only attributable-rejection + rail traffic: ≤ 2 rail events + ≤ `invalid_budget`
  attributable-rejection events per cycle. **Legitimately accepted signals are NOT part of this
  constant** — they are rate-bounded only and may continue indefinitely in an epoch that never
  quarantines (the Option-E scope note; archive REV-0025-F P2). Flood/Option-E acceptance tests must assert
  the constant bound over attributable-rejection traffic, never over accepted traffic.
- Test contract: model-based/long-duration tests assert **constant event-row count** and bounded
  storage under sustained hostile flood — paced at or below the refill rate over arbitrarily many
  windows, not merely a burst that eventually exceeds the rate limit — in both stores.

**Enablement is gated on full rails — the audit-free interim ceiling is withdrawn** (Ameen decision
2026-07-14, remediates archive REV-0024-F-004). The earlier design shipped a crude *audit-free interim
ceiling* in WO-0102 ahead of the full rails, on the theory that a counting-only ceiling kept an
enabled endpoint from ever being unrailed. archive REV-0024 showed that ceiling was rate-bounded, not
storage-bounded, so it left exactly the paced-flood hole above. It is **removed**, not tuned.
In its place, `signal_seat_enabled` gains a **permanent rails-presence startup guard**, exactly
parallel to clause A-1.4's credential-presence guard: **with the flag on, startup fails fast unless
the full per-producer rails are wired** — the refilling rate bucket, the non-refilling invalid/conflict
budget, the producer-quarantine epoch machinery, and the human `PRODUCER_RELEASED` path. The guard is
**never removed** — it is a standing invariant that WO-0104 **satisfies** by wiring the real provider,
**not** a scaffold that WO-0104 deletes (archive REV-0025-F-005). A *Protocol-presence* check alone cannot
tell a real rails provider from a permissive no-op fake, so: **the production entrypoint is proven to
construct the real WO-0104 provider, and any fake/permissive provider is confined to a test-only
construction path that production config/environment cannot select** (the sole distinction is
enforced, not merely labelled "never a production default"). There is therefore **no window in which
an enabled endpoint runs without finite-audit flood protection**, and no interim ceiling to reason
about.

Consequence for sequencing: the endpoint's **live enablement is the joint WO-0102 + WO-0103 + WO-0104
milestone** — WO-0102 ships the ingestion endpoint and the A-1 boundary; **WO-0103 owns the A-2
atomic approval→conversion** (the human-gated order-submission surface — NOT WO-0102's); and WO-0104
lands the full rails and satisfies the rails guard. **The WO-0103 half is enforced as a
release/deployment gate + test, not a new runtime startup check** (Ameen decision 2026-07-14 D-2):
the sequencing dependency is binding, and the **joint mounted-app integration suite proves
ingest → operator approval → exactly one atomically-linked intent** against the real rails, alongside
the route-authorization matrix and constant-event-row flood tests. The **route matrix asserts the
required sensitive routes EXIST** (not merely classifies whatever happens to be mounted, archive REV-0025-F-005/
F-007). All three WOs must land before live enablement; the suite runs green at that joint milestone —
never against a half-railed or conversion-less app.

## Action Items

1. [x] Draft master-side A-1..A-4 remediation under the ratified D-SIG decisions (WO-0127).
2. [x] Reconcile specs 00-06, PKL, and WO-0102..0104; seed Proposed ADR-013.
3. [x] Stage one fresh request at `work/review/REV-0034/request.md`.
4. [ ] Claude-seat independent review returns ACCEPT / ACCEPT-WITH-CHANGES.
5. [ ] Ameen dispositions REV-0034 and explicitly approves the final ADR text.
6. [ ] Only then: flip Proposed→Accepted and unfreeze implementation WOs.
7. [ ] At R4: present current `signal_records` DDL for a fresh schema decision.
