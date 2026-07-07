# Spine v2 — Wave 3c Plan: timeout/504 `TIMEOUT_QUARANTINE` (ADR-002)

This is the accepted design for Phase 3 wave 3c. It records the Phase-3/Phase-4
boundary and the spec/code conflicts that the CLAUDE.md conflict rule requires be
written down *before* coding (they touch order submission and broker facts). It
also exists so the wave is resumable after a usage-budget refresh.

Migrates `docs/MIGRATION_MATRIX.md` "Timeout/504 submit ambiguity"
`legacy_truth → event_truth`. Replaces the blind-redrive behavior pinned by
`tests/test_spine_v2_characterization.py::TestCharacterizeStaleSubmittingRetry`
(Flow 2).

## Problem (current behavior)

A submit that times out / returns 504 / fails in transport *after the request
may have reached Alpaca* is **ambiguous** — the order may be live, filled,
rejected, or never-arrived. Today the adapter collapses 504/5xx/network/timeout/
parse failures to a plain transient `BrokerError`
(`app/broker/alpaca_paper.py` final `except`), and the monitoring loop either
releases `SUBMITTING → CREATED` (`app/monitoring.py::_submit_pending_orders`) or
blind-redrives via `submit_order` again (`_redrive_stale_submitting`), trusting
the idempotent `client_order_id`. ADR-002: blind redrive is too permissive for an
ambiguous outcome — it must instead **quarantine and reconcile by a read-only
targeted query**, never resubmit-and-hope.

## Design

### Representation — `OrderStatus.TIMEOUT_QUARANTINE`, event-log-authoritative

A new **non-terminal** `OrderStatus.TIMEOUT_QUARANTINE`. Its **first durable write
is a `TIMEOUT_QUARANTINE` `ExecutionEvent`** (that type already exists, reserved in
Phase 2); the order-row status is a co-written read-model in the SAME atomic block
— exactly the wave-3a fill-row + `FILL`-event co-write pattern. This is what makes
the fact `event_truth` (first write = event; replay-derivable via a new
`timeout_quarantined_order_ids(events)` projector; dual-store parity by
construction).

Why an OrderStatus (wave 3b added none): 3b quarantine is a *symbol* property with
no owning entity, so it must be log-derived; 3c quarantine is an *order* property
and the `Order` already has a status column + state machine, and §4 models
`TIMEOUT_QUARANTINE` as an order/spawn status by value. The D-017 recovery ledger
does NOT fit — it is keyed on a known `broker_order_id`, and a timeout has none.

Transitions added to `ORDER_TRANSITIONS`:
`SUBMITTING → TIMEOUT_QUARANTINE`; `TIMEOUT_QUARANTINE → {SUBMITTED, REJECTED,
CANCELED}`. Non-terminal (counts toward CAPI exposure — correct, it may be live),
carries no `broker_order_id` so the open-order reconcile skips it.

### Classification — `AmbiguousBrokerError(BrokerError)`

A new adapter exception sibling to `TerminalBrokerError`. The adapter classifies
(§6): 504 / other 5xx / network-timeout / transport / parse-after-send →
`AmbiguousBrokerError`; definitive 400/401/403/422 → `TerminalBrokerError`
(unchanged); genuinely-safe retryable (429 rate-limit) → plain `BrokerError`
(unchanged). Explicit subclass, not a remap — the monitoring loop routes on type,
not guesswork. `except BrokerError` still catches it. The mock/sim need no new
injection hook (`fail_next_submit(AmbiguousBrokerError(...))` already works).

### Targeted resolution — read-only `get_order_by_client_order_id`

New **read-only** adapter method `get_order_by_client_order_id(client_order_id) ->
Optional[BrokerOrderUpdate]`. Required: a timeout leaves no `broker_order_id`, so
`get_order_status` (keyed on venue id) can't be reused. The Alpaca SDK capability
already exists (used internally for duplicate-`client_order_id` recovery); wave 3c
promotes it to a first-class read-only method. Returns `None` on confirmed 404,
the mapped `BrokerOrderUpdate` when present, raises `BrokerError` on a query
failure (never treat a failed query as "absent" — §7 safeguard). Mock/sim gain
`seed_venue_order(client_order_id, update)` so a test can simulate "the ambiguous
submit *did* reach the venue" independently of a raising `submit_order`.

New monitoring step `_resolve_timeout_quarantine` (after `_redrive_stale_submitting`)
queries each `TIMEOUT_QUARANTINE` order by `client_order_id`:
- **working** (SUBMITTED/ACCEPTED/PARTIALLY_FILLED) → resolve to `SUBMITTED` +
  broker id; the existing reconcile poll then tracks/ingests fills normally;
- **filled** → resolve to `SUBMITTED` + broker id; next reconcile ingests the fill
  via the existing wave-3a path → `FILLED` (routing through `SUBMITTED` preserves
  INV-9 "submitted ≠ filled" and reuses the single fill path — deliberate
  divergence from §4's direct `TIMEOUT_QUARANTINE → FILLED` edge, see C4);
- **not-found (`None`) and query-retries exhausted** (`timeout_quarantine_max_query_attempts`)
  → resolve to `REJECTED`; before exhaustion stay quarantined (bounded, counted via
  a durable audit event, mirroring the redrive backstop);
- **query error / persistent ambiguity past the bound** → escalate to a
  `needs_review` recovery record (delivers ADR-002 "manual review" for free).

### Block-replacement — no new mechanism

The quarantined order stays non-terminal, so its 1:1 `Candidate`/`SellIntent`
stays `ORDERED` with an active order ⇒ no replacement order is generated (INV-2).
Both submit sweeps skip it by status; resolution is read-only ⇒ **no path can
`submit_order` a quarantined order** (double-submit-safe by construction). This is
the concrete stand-in for ADR-002 "block replacement / primary BLOCKED" in a repo
with no primary FSM (see C1).

## Phase-3 / Phase-4 boundary

Wave 3c **does**: classify ambiguity; record the `TIMEOUT_QUARANTINE` event + flip
the order read-model; block replacement via the non-terminal state; resolve ONE
order by a read-only targeted `client_order_id` query; escalate stuck cases to the
existing `needs_review` ledger; prove replay + dual-store parity.

Wave 3c **defers to Phase 4**: startup mass reconcile ("no trading until startup
reconcile succeeds"); runtime open-order/position polls at scale; external/unmanaged
order surfacing; position-parity tolerance gates; query throttling / 200-min token
bucket; reconcile-after-reconnect → `Reducing`; operator "stuck reconciliation"
alerting; a real primary/spawn/TradingState projector. Justification: every ADR-002
required test is satisfiable with a single-order read-only by-client-id query; the
`get_order_by_client_order_id` seam is the shared Phase-4 infrastructure introduced
here in minimal form.

## Recorded conflicts (CLAUDE.md conflict rule — order submission / broker facts)

- **C1 — no primary / TradingState FSM.** ADR-002 + Addendum Decision 2 say "mark
  the primary `BLOCKED`." The repo has no primary/spawn FSM (inert `primary_id`/
  `spawn_id` fields) and no TradingState (wave 3d). Wave 3c maps "block replacement
  / primary BLOCKED" onto *order stays non-terminal + 1:1 intent ⇒ no replacement*.
  The literal primary-`BLOCKED` / INV-3 primary state has no home until the
  primary/TradingState FSM lands (3d/Phase 4).
- **C2 — 429 classification.** §6 lists `400/401/403/422/429` as definitive rejects.
  The adapter treats 429 as transient-retryable, which is correct in practice (a
  rate limit *is* retryable and did not reach the book). Wave 3c keeps 429 transient
  and does not route it to quarantine; disagreement with §6's letter recorded.
- **C3 — 404 in the definitive set.** The adapter maps 404 → `TerminalBrokerError`;
  §6's definitive list omits 404. Minor; left as-is.
- **C4 — `TIMEOUT_QUARANTINE → FILLED` edge.** §4 draws a direct edge; wave 3c routes
  filled-resolution through `SUBMITTED`-then-reconcile to reuse the single fill
  ingestion path and preserve INV-9 (submitted ≠ filled). Deliberate divergence.
- **C5 — `event_truth` scope.** Order *status* is not projected from the log
  anywhere yet (spawn projector deferred to Phase 4). Wave 3c makes the
  `TIMEOUT_QUARANTINE` *fact* `event_truth` (first durable write + replay-derivable
  set) while the status column is a co-written read-model. The matrix flip is scoped
  to the quarantine fact, not a full spawn projection.
- **C6 (risk, flag+defer) — protective-exit self-cross.** `cancel_open_buys`
  excludes `TIMEOUT_QUARANTINE`, and a quarantined BUY *may be live at the venue*
  (unlike a never-sent `SUBMITTING`), so a floor-breach exit could self-cross when
  it later resolves to `FILLED`. Exit sizing derives from filled shares only, so it
  is no worse than today's `SUBMITTING` case, but more likely live. Document + test
  current behavior in 3c; close the hardening (resolve-or-hold before exit) in 3d
  (`Reducing`) / Phase 4.

## Implementation slices (each gated: suite + coverage + parity + harness)

- **Part 1 — inert scaffolding (additive, nothing routes to it yet):**
  `OrderStatus.TIMEOUT_QUARANTINE` + transitions + audit `EventType`s;
  `AmbiguousBrokerError`; read-only `get_order_by_client_order_id` on the interface +
  all three adapters + `seed_venue_order` on mock/sim; store atomic evented
  transition (`transition_order_evented` planner + both stores); projector
  `timeout_quarantined_order_ids` + `list_timeout_quarantined_orders`. Unit +
  dual-store parity + replay tests. Full corpus stays green (nothing wired).
- **Part 2 — wiring (the behavior change):** monitoring routes
  `AmbiguousBrokerError` → quarantine (guard placed BEFORE the generic release —
  safety-critical); `_resolve_timeout_quarantine` step + `config` bound; adapter
  classification split (504/5xx/timeout → ambiguous); Flow-2 characterization
  migration (+ a residual test that a safe 429 still redrives); cockpit read-only
  bucket; docs (matrix row → event_truth, ledger, INVARIANTS INV-2/INV-3 note).
  Then independent adversarial review focused on double-submit/oversell + replay.

## ADR-002 required tests → coverage

| Required test | Satisfied by |
|---|---|
| timeout and HTTP 504 → `TIMEOUT_QUARANTINE` | Part 2: `submit_order` raising `AmbiguousBrokerError` (timeout *and* 504) → status + one execution event, both stores |
| quarantined spawn blocks replacement | Part 2: next tick does not `submit_order` that order; no replacement for its intent (INV-2) |
| targeted query resolves to working/filled/rejected/manual review | Part 2: the four `_resolve_timeout_quarantine` branches |
| duplicate client-order lookup recovers existing venue order without new submit | Part 1/2: `get_order_by_client_order_id` finds the venue order → resolve to SUBMITTED, no `submit_order` call |
| replay reproduces blocked/quarantined state | Part 1: replay → `timeout_quarantined_order_ids` == live `list_timeout_quarantined_orders`; dual-store parity |
