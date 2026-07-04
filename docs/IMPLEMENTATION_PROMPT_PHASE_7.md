# Phase 7 — Sell-Side Protection Engine

**Sell-Intent Lifecycle ADR + Implementation Plan.** This is the mandated
first artifact for Phase 7 (`docs/00_START_HERE.md` D-021: "the Phase-7 sell-side
ADR — its own sell-intent lifecycle and risk model, never sells bolted onto the
buy-candidate path"). Read `01_ARCHITECTURE.md` (Future Architecture),
`02_DATA_AND_PERSISTENCE.md` (folding formula, lifecycles), and `04_IMPLEMENTATION_
PLAN.md` (Phase 7 line) first — this doc references them rather than restating.

---

## 0. Scope

**Phase 7 builds the always-on Sell-Side Protection Engine + manual flatten.**

In scope:
- **Position monitoring** against a **hard price floor** (stop-loss).
- **Controlled exit**: on a floor breach, an automatic protective SELL that
  exits the position, using the session-conditional order type (Rule 12).
- **Manual flatten**: `POST /api/positions/{symbol}/flatten` — operator-triggered
  immediate exit of a symbol's entire open position.
- **Residual position tracking**: after a partial exit the remaining position is
  still monitored and re-protected next tick.
- **A first-class sell-intent lifecycle** (`SellIntent`), mirroring the buy
  side's `Candidate` — not a sell bolted onto the candidate path.

Explicitly **NOT** in Phase 7 (later phases — do not build):
- Auto-Sell profit-taking / momentum-reversal exits (Phase 8; strategy-driven,
  distinct from safety protection — `01_ARCHITECTURE.md`).
- Order cancel/replace/resize to complete an exit (Phase 8; `replaces_order_id`
  stays unpopulated).
- Auto-Buy (Phase 9).
- Realized-P/L accounting (`02_DATA_AND_PERSISTENCE.md`: deferred; beta shows
  unrealized only — a protective sell folds the position down, no realized P/L).
- Short selling (long-only; a sell can never drive quantity below zero).
- Trailing / high-water-mark floors (that is Auto-Sell-shaped; beta protection is
  a **fixed** floor below average cost).

**Paper only. No live trading. No new credentials.** All non-negotiables in
`01_ARCHITECTURE.md` remain in force.

---

## 1. The three locked safety decisions (operator, this session)

These were decided by the operator up front because the docs do not settle them
and each materially shapes the build:

- **D-P1 — Automatic protection.** A hard-floor breach **auto-creates and submits
  a protective sell** (on paper). "Always-on safety" means the stop cannot wait
  for a human click. Built behind the Approval-Gate seam so a future/config
  human-confirm protection mode drops in without restructuring the state machine.
- **D-P2 — Kill-switch: exits exempt; autonomous protection pauses.** Manual
  flatten **always** works (risk-reducing). Autonomous floor-breach selling
  **pauses** while the kill switch is engaged (the operator asked to freeze
  autonomous action) but the paused/breaching state is surfaced loudly. New BUY
  order intent stays blocked by the kill switch as today. Pause-buys never blocks
  a sell.
- **D-P3 — Exit order type.** During **regular market hours** a protective exit
  is a **MARKET** order (guarantees the exit — protection's priority is getting
  out; this is the first real use of `OrderType.MARKET`). During
  **pre-market / after-hours** it is an **aggressive protective LIMIT** priced to
  cross the spread (Rule 12: limit-only in those sessions, no exception).

---

## 2. Core principle — sell-intent is a first-class lifecycle

The buy side is `Candidate → Order → Fill → Position`. The sell side mirrors it:
`SellIntent → Order → Fill → Position`. A **`SellIntent`** is a durable record of
a *decision that an open position should be reduced/exited*. It is the sell-side
analogue of `Candidate` and reuses the same machinery (a lifecycle state machine,
an atomic "intent → order" handoff, the shared order lifecycle, the append-only
fill fold). This satisfies the mandate: the exit decision is its own entity with
its own lifecycle, not a flag on a candidate or an order created out of nowhere.

**Every `Order` originates from exactly one of two things:** a `Candidate` (buy)
or a `SellIntent` (sell). Concretely:
- `Order.candidate_id` becomes **nullable**.
- `Order` gains a nullable **`sell_intent_id`**.
- **Invariant (enforced at the store boundary, both stores):** an order has
  `candidate_id` XOR `sell_intent_id` set — never both, never neither. A `BUY`
  order carries `candidate_id`; a `SELL` order carries `sell_intent_id`.

---

## 3. `SellIntent` entity and lifecycle

```python
class SellReason(str, Enum):
    MANUAL_FLATTEN = "manual_flatten"     # operator clicked flatten
    PROTECTION_FLOOR = "protection_floor" # hard-floor breach (auto)
    # future: AUTO_SELL = "auto_sell"     # Phase 8 profit-taking

class SellIntentStatus(str, Enum):        # mirrors CandidateStatus
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ORDERED = "ordered"                    # terminal — an Order now exists
```

`SellIntent` fields (mirrors `Candidate` where it can):
```
id, symbol, reason: SellReason, status: SellIntentStatus = PENDING,
target_quantity: int,                 # shares to exit (capped at position qty)
floor_price: Optional[float],         # the breached floor (protection only)
observed_price: Optional[float],      # last price that triggered it (protection only)
session_id, order_id: Optional[str],  # linked Order when ORDERED
created_at, updated_at, approved_at, rejected_at, expired_at, ordered_at
```

**Lifecycle (identical shape to the candidate machine — reuse `transitions.py`):**
```
pending ──approve──▶ approved ──order──▶ ordered   (terminal; an Order exists)
   │
   ├──reject──▶ rejected   (terminal)
   └──expire──▶ expired    (terminal)
```
- **Approve/reject/order are idempotent** (same-status = audited no-op), like the
  candidate machine.
- **The APPROVED state is the Approval-Gate seam.** In beta's automatic mode the
  protection loop (and the flatten route) drive `pending → approved → ordered`
  in one atomic step — the "approval" is the automatic policy decision (D-P1). The
  state exists so a future human-confirm protection mode simply *stops* at
  `approved` and waits for an operator, with **zero** state-machine change.
- **`expired`** is used when the intent is no longer valid before it ordered:
  the position went flat by another path, the session closed with the intent
  un-ordered, or (for a protection intent) the price recovered above the floor
  before ordering. Mirrors candidate expiry at session close.
- Every transition writes an audit/event row (`sell_intent_created`,
  `sell_intent_transition`).

**SellIntent → Order is 1:1**, exactly like Candidate → Order. Residual after a
partial fill is handled by *re-evaluation*, not by one intent spawning many
orders: if a protective order partial-fills and then terminates (canceled/
rejected) while the residual position still breaches the floor, the **next
protection tick** creates a **new** SellIntent for the residual (subject to the
single-active-intent dedup below). This keeps the entity graph a clean tree and
reuses the candidate→order handoff verbatim.

**Dedup — one active sell-intent per symbol.** A symbol with an *open*
(`pending`/`approved`) SellIntent, or an `ordered` one whose Order is still
non-terminal, does not get a second intent. Mirrors candidate dedup (D-014c). The
flatten route is idempotent against this (a second flatten while one is in flight
returns the in-flight intent).

---

## 4. The protection decision engine (`app/protection.py`, pure)

Pure functions, no IO/async, unit-testable in isolation — same pattern as
`app/strategy.py` / `app/policy.py`. The monitoring integration (§5) owns all
store/market-data calls; this module only decides.

```python
def floor_price(average_price: float, stop_loss_pct: float) -> float:
    # the hard floor = average cost reduced by the stop-loss fraction
    return average_price * (1.0 - stop_loss_pct)

def floor_breach_reason(position, snapshot, config) -> Optional[FloorBreach]:
    """Return a FloorBreach (floor_price, observed_price) if this position must be
    protected, else None. Returns None (does NOT act) when:
      - protection disabled, or position flat (quantity <= 0), or
      - average_price is None/non-finite/<=0, or
      - snapshot is None / last_price is None/non-finite/<=0 / snapshot.stale
        (never act on absent or stale market data — a bad price must not trigger
        a spurious liquidation), or
      - last_price > floor (no breach).
    Breach iff a trustworthy last_price <= floor_price(average_price, stop_loss_pct)."""

def exit_quantity(position) -> int:
    # protection exits the ENTIRE position (get out); capped at position.quantity
    return position.quantity

def exit_order_spec(session_type, snapshot, config) -> ExitOrderSpec:
    """(order_type, limit_price) for the protective sell (D-P3):
      - REGULAR hours  -> MARKET, limit_price=None
      - PRE/AFTER hours -> LIMIT at an aggressive protective price that crosses
        the spread: min(bid, last_price) * (1 - limit_buffer_pct), floored > 0,
        rounded to a sane tick. Uses the bid when present (a marketable sell
        limit sits at/below the bid), else last_price, so the limit is as likely
        to fill as limit-only allows."""
```

All numeric guards go through `app/policy.py`'s existing
`finite_number_reason` family (reuse, do not re-implement) so a `NaN`/`Inf`/None
price can never produce a bogus floor or a bogus limit.

**Note on limit-only fill risk (pre/after-hours):** an aggressive protective
limit can still miss in a fast market — that residual risk is inherent to Rule 12
(limit-only there) and is documented, not "solved" by a market order that Rule 12
forbids. The next tick re-drives the residual.

---

## 5. Monitoring integration — protection runs *inside* the monitoring tick

Protection is added as the **first phase** of `run_monitoring_tick` (before
`_submit_pending_orders`), so a protective sell order it creates is claimed +
submitted in the **same tick** (lowest latency, one cadence, one authority). The
monitoring loop gains a `MarketDataService` handle (wired from `app.state.
market_data` in `main.py`, exactly as the strategy loop already receives it).

`run_monitoring_tick(store, adapter, market_data, settings)` becomes:
```
_run_protection(...)          # NEW — evaluate positions, create protective sells
_submit_pending_orders(...)   # existing — submits the created sell orders too
_redrive_stale_submitting(...)
_reconcile_open_orders(...)   # existing — reconciles sell fills -> position folds
_recover_unpersisted_submits(...)
```

`_run_protection`:
1. `positions = [p for p in store.list_positions() if p.quantity > 0]`.
2. **Ensure held symbols have market data** (see §5.1) — `market_data.subscribe`
   for held symbols is idempotent.
3. For each held symbol, if the **kill switch is NOT engaged** (D-P2: autonomous
   protection pauses under the kill switch — surface a `protection_paused` event
   once, do not create intents), and there is **no active SellIntent** for the
   symbol (dedup), and `floor_breach_reason(...)` returns a breach:
   - `create_sell_intent(symbol, reason=PROTECTION_FLOOR, target_quantity=
     exit_quantity(pos), floor_price, observed_price, session_id)` → `pending`.
   - Auto-approve (Approval-Gate seam) → `approved`.
   - `create_order_for_sell_intent(intent_id, order_type, limit_price)` (from
     `exit_order_spec`) → creates the `CREATED` sell Order and transitions the
     intent to `ordered`, atomically.
   - Write a `protection_triggered` audit event (symbol, floor, observed price,
     quantity, session).
4. If the kill switch IS engaged and any held position is breaching, emit a
   single `protection_paused` event (deduped via the event log, like the stale
   flag) so the operator sees "protection would fire but is paused."
5. Never raises out of the tick (the loop's never-crash contract): a per-symbol
   error is logged and skipped.

The created `CREATED` sell order then flows through the **existing** submit
(`_submit_pending_orders` → claim → `submit_order` → `SUBMITTED`) and reconcile
(`_reconcile_open_orders` → fills → position folds down) pipeline **unchanged and
side-agnostic** — the whole point of reusing `Order`.

### 5.1 Market-data subscription for held symbols (the sharp edge)

`MarketDataService` subscriptions are today driven **only by the armed
watchlist** (the strategy loop). A symbol you *hold* but have since **disarmed**
would be **unsubscribed → `get_snapshot` returns `None` → protection is blind**.
That is unacceptable for a safety system. Decision:

- **The desired subscription set is `armed watchlist symbols ∪ symbols with an
  open position`.** A symbol is never unsubscribed while a position is open in it.
- `_run_protection` **subscribes** held symbols (idempotent, additive) every
  tick — this makes the monitoring loop the authority that guarantees held
  coverage **even if the strategy engine is disabled**.
- The strategy loop's existing unsubscribe sync is changed to compute removals
  against `armed ∪ held` (it must **not** unsubscribe a held symbol). A shared
  helper computes the union so the two loops cannot disagree.
- A symbol that is flat **and** unarmed is eligible for unsubscribe (the strategy
  loop's normal path). If the strategy engine is disabled, a flat-but-once-held
  symbol stays subscribed — a bounded, benign leak, documented; a periodic
  reconcile is a later cleanup, not a beta blocker.

### 5.2 Sell orders bypass the buy-side submission gate

The submission claim (`claim_order_for_submission`) consults
`app.policy.order_intent_block_reason` (kill switch / pause-buys / session
closed). A **protective/flatten SELL is risk-reducing and must not be blocked by
buy-side controls** (D-P2: manual flatten always works; a position must be
exitable even after session close). Therefore:

- `order_intent_block_reason` / the claim planner becomes **side-aware**: for a
  `SELL` order it returns **no block** for kill switch, pause-buys, or session
  closed. (Autonomous protection is gated *upstream* by the kill-switch check in
  `_run_protection`; the claim never re-blocks an exit.)
- For a `BUY` order, behavior is **exactly unchanged** — every existing test and
  invariant (D-013/D-013a, F-001/F-002) holds byte-for-byte.
- This is the single highest-scrutiny change in Phase 7; it is covered by
  explicit both-store tests (a SELL order submits under kill switch / paused /
  closed session; a BUY order still does not) and gets the independent review.

---

## 6. Store methods (both stores, atomic, parity)

New `StateStore` methods (shared planner logic in `app/store/core.py`; both
`InMemoryStateStore` and `SqliteStateStore` behave identically — the `any_store`
contract):
- `create_sell_intent(*, symbol, reason, target_quantity, floor_price=None,
  observed_price=None, session_id) -> SellIntent` — atomic (intent row +
  `sell_intent_created` audit event). Validates: `target_quantity` a positive
  whole count; symbol normalized; reason a real `SellReason`; session open (a
  manual flatten may target a **closed** session's lingering position — see
  below).
- `transition_sell_intent(intent_id, new_status, *, order_id=None) -> SellIntent`
  — mirrors `transition_candidate` (real-enum guard AIR-009, idempotent no-op,
  audited genuine transitions).
- `create_order_for_sell_intent(intent_id, *, order_type, limit_price) -> Order`
  — atomic APPROVED→ORDERED handoff (sell Order row with `sell_intent_id` set,
  `candidate_id=None`, `side=SELL`; intent → `ordered`; both audit events). NO
  CAPI risk-limit gate (protection is not risk-limited — it *reduces* risk).
  Rejects if `target_quantity` exceeds the **current** derived position quantity
  (never oversell → never short: caps at live position, re-reads it inside the
  lock).
- `get_sell_intent(id)`, `list_sell_intents(*, session_id=None, status=None,
  symbol=None)`, and an `active_sell_intent_for(symbol)` helper for dedup.

**Session-scoped review:** `SellIntent` and sell `Order`/`Fill` rows carry
`session_id` and are folded into `/api/review` and session-close expiry exactly
like candidates (open sell-intents expire at session close; sell orders already
reconcile past close via D-011).

**Order-creation validation reuse:** the sell-order limit/quantity go through the
same `app/policy.py` guards as buy orders (`limit_price_reason`, whole-count),
and `create_order_for_sell_intent` re-checks the live position so a race that
reduced the position cannot produce an oversell.

---

## 7. Broker adapter — market + sell support

- `AlpacaPaperAdapter.submit_order` today always builds a `LimitOrderRequest` and
  is BUY-shaped. It becomes **side- and type-aware**: reads `order.side`
  (BUY/SELL) and `order.order_type` (LIMIT/MARKET). A `MARKET` order builds a
  `MarketOrderRequest` (no `limit_price`); a `LIMIT` builds the existing
  `LimitOrderRequest`. `extended_hours` logic is unchanged (a MARKET order is
  only ever chosen in regular hours, where extended_hours is irrelevant).
- `MockBrokerAdapter` / `SimBrokerAdapter` are already side-agnostic (they mint a
  broker id and reconcile whatever fills a test scripts); confirm + add a market
  sell path in tests. The reconcile/fill path is unchanged.
- **Rule 12 enforced at the decision layer**, not the adapter: `exit_order_spec`
  only ever returns `MARKET` in regular hours, so the adapter never has to reject
  a market order in pre/after-hours. A defensive assertion documents the
  invariant.

---

## 8. HTTP routes + schemas

- **`POST /api/positions/{symbol}/flatten`** (new; the contract lists it,
  Phase 4 shipped a disabled cockpit placeholder, no route existed). Creates a
  `MANUAL_FLATTEN` SellIntent for the **full current position**, drives it
  `pending → approved → ordered` (the click is the approval), and returns the
  created intent/order view. Behavior:
  - No open position → `409` (nothing to flatten), clean domain error, no state
    change.
  - An active flatten/protection intent already in flight → **idempotent**:
    returns the in-flight intent (no second order).
  - Works under kill switch / pause-buys / closed session (D-P2 / §5.2).
- **`GET /api/protection`** (new; read-only): the effective protection config
  (enabled, stop-loss %, limit buffer %) plus, per open position, its protection
  status — `floor_price`, `observed_price`, `breaching: bool`, `paused_by_kill_
  switch: bool`, and any active sell-intent. This feeds the cockpit's per-position
  "protection mode" (03_UI_WORKFLOW §4). Server-side classification (the cockpit
  renders, never re-derives — D-020 pattern).
- `GET /api/sell-intents` (read-only list) for the review/operator surface;
  `/api/review` includes sell-intents for the queried session.
- Domain errors map to HTTP the same way the existing trading routes do (404/409/
  422); no raw exception leaks.

---

## 9. Config (`app/config.py`, `Settings`)

New settings, following the existing `_env_float`/`_env_int` + validation pattern
(reject non-finite/out-of-range at load):
- `protection_enabled: bool = True` (env `PROTECTION_ENABLED`).
- `protection_stop_loss_pct: float` (env `PROTECTION_STOP_LOSS_PCT`, default e.g.
  `0.08` = exit 8% below average cost). Must be `> 0` and `< 1`.
- `protection_limit_buffer_pct: float` (env `PROTECTION_LIMIT_BUFFER_PCT`,
  default e.g. `0.005`). Must be `>= 0` and `< 1` — how far through the
  bid/last a pre/after-hours protective limit is priced.

Defaults chosen conservatively; all overridable by env. `0`/negative/`>=1`
stop-loss is rejected at load (a `0` floor would liquidate on any tick; a `>=1`
floor is nonsensical) — same footgun-rejection discipline as
`MARKET_DATA_STALE_MINUTES`.

---

## 10. Safety invariants (must all hold; the review checklist gets these)

1. **Rule 7 preserved** — position still derives *only* from appended fills; a
   protective sell mutates position only by appending a SELL fill that folds it
   down. `_run_protection` never touches position.
2. **No short** — `exit_quantity` caps at the live position; `create_order_for_
   sell_intent` re-checks live quantity under the lock; `append_fill`'s existing
   `NegativePositionError` guard is the backstop.
3. **Kill switch (D-P2)** — autonomous protection pauses (no new protective
   intents) while engaged and is surfaced; manual flatten and the submission of
   an already-created sell order are never blocked by kill switch / pause-buys /
   closed session. BUY-side control behavior is byte-for-byte unchanged.
4. **No action on bad data** — protection never triggers on `None`/stale/
   non-finite market data.
5. **Rule 12** — MARKET only in regular hours; LIMIT-only in pre/after-hours,
   enforced at the decision layer.
6. **Single-flight** — one active sell-intent per symbol; flatten is idempotent.
7. **Order origin invariant** — every order has `candidate_id` XOR
   `sell_intent_id`.
8. **Parity** — both stores identical for every new method (`any_store`).
9. **Realized P/L still deferred**; unrealized-only display unchanged.
10. **Protection ≠ Auto-Sell** — this engine is safety-only (fixed floor, full
    exit); no profit-taking, no cancel/replace/resize (Phase 8 seam untouched).

---

## 11. Test plan (IO-free, both stores where store-facing)

- **`app/protection.py` pure tests**: floor math; breach/no-breach at exact
  boundary; None/stale/non-finite snapshot → no action; disabled → no action;
  flat position → no action; exit sizing = full quantity; order-spec MARKET in
  regular hours, aggressive LIMIT in pre/after-hours (bid vs last fallback,
  buffer, tick rounding, `>0` floor).
- **Store tests (`any_store`)**: create/transition sell-intent; the intent→order
  handoff sets `side=SELL`, `sell_intent_id`, `candidate_id=None`; oversell
  rejected (caps at live position); dedup; XOR origin invariant; parity of
  events/persistence/readback; session-close expiry of open sell-intents.
- **Submission-gate tests (`any_store`)**: a SELL order submits under kill switch
  / pause-buys / closed session; a BUY order still does **not** (regression).
- **Monitoring integration tests** (Mock/Sim adapter, fake market data): breach →
  auto protective sell → fill → position flat; residual re-protection after a
  partial; kill switch pauses autonomous protection but not a manual flatten;
  stale/absent data → no action; held-but-disarmed symbol stays subscribed and is
  protected; dedup (no second intent per tick).
- **Broker tests**: MARKET sell request construction (regular hours) and LIMIT
  sell (pre/after-hours), side read from the order.
- **Route tests**: flatten happy path; no-position → 409; idempotent second
  flatten; flatten works under kill switch; `GET /api/protection` classification.
- **Property/state-machine**: extend `tests/test_lifecycle_state_machine.py` with
  a hold→breach→protect→flat rule and a manual-flatten rule; the existing safety
  invariants (position never negative, filled==recorded, no untracked broker
  order) must hold across sell interleavings too.
- **Coverage floor 93% (`--cov-branch`) holds; repo-local temp root.**

---

## 12. Build sequence — each increment gated by a sub-agent review

Per the operator's directive (sub-agents check work *as it is written*, to catch
defects before an after-the-fact code review):

1. **ADR (this doc)** → adversarial **design review** by a fresh sub-agent →
   revise. *(gate: design signed off)*
2. **Data model + schema** — `SellIntent`, `SellReason`, `SellIntentStatus`,
   `SELL_INTENT_TRANSITIONS`; `Order.candidate_id` nullable + `sell_intent_id`;
   both-store schema (SQLite `sell_intents` table + `orders.sell_intent_id`
   column; `orders.candidate_id` NULL-able); idempotent `CREATE TABLE`/additive
   column. → review.
3. **Store methods** — create/transition sell-intent, `create_order_for_sell_
   intent`, dedup/active helper, session-close expiry, XOR invariant; shared
   `core.py` planners; both stores; parity tests. → review.
4. **Protection decision engine** — `app/protection.py` pure + exhaustive tests.
   → review.
5. **Monitoring integration** — `_run_protection`, held-symbol subscription
   union, kill-switch pause, side-aware submission gate; wire `market_data` into
   the loop + `main.py`. → review.
6. **Broker market-order support** — side/type-aware `submit_order`; adapter
   tests. → review.
7. **Routes + schemas** — flatten, `GET /api/protection`, sell-intent list;
   `/api/review` inclusion. → review.
8. **Cockpit** — Position Monitor protection column + working flatten button
   (thin client; all logic server-side). → review.
9. **Gate** — full suite + coverage + parity; **independent adversarial review by
   a fresh context** of the whole Phase 7 diff (per the project's Gate discipline);
   fix confirmed findings; write **D-025** (summary) into `00_START_HERE.md` and
   the Phase-7 section of `05_REVIEW_CHECKLIST.md`; update README/`03_UI_WORKFLOW`;
   commit + push on `claude/confident-babbage-ti5cm8`.

Red-then-green per increment; both-store parity where store-facing; domain errors
never leak raw; no production behavior beyond the phase's scope changes.
