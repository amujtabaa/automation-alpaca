# Phase 7 — Sell-Side Protection Engine

**Sell-Intent Lifecycle ADR + Implementation Plan (v2, post design-review).** The
mandated first artifact for Phase 7 (`docs/00_START_HERE.md` D-021: "the Phase-7
sell-side ADR — its own sell-intent lifecycle and risk model, never sells bolted
onto the buy-candidate path"). Read `01_ARCHITECTURE.md` (Future Architecture,
Rules 7/8/12), `02_DATA_AND_PERSISTENCE.md` (folding formula, lifecycles), and
`04_IMPLEMENTATION_PLAN.md` (Phase 7 line) first.

> **v2 note.** A fresh-context adversarial design review (5 lenses over the real
> code) found 4 blockers + 16 majors in v1. Every one is resolved below; the
> `## Appendix — Design-Review Resolutions` maps each finding to its fix for
> traceability. Read the appendix alongside the section it amends.

---

## 0. Scope

**Phase 7 builds the always-on Sell-Side Protection Engine + manual flatten.**

In scope: position monitoring against a **hard price floor** (stop-loss);
**controlled exit** via an automatic protective SELL using the session-conditional
order type (Rule 12); **manual flatten** (`POST /api/positions/{symbol}/flatten`);
**residual tracking**; a **first-class sell-intent lifecycle** (`SellIntent`)
mirroring `Candidate`.

Explicitly **NOT** Phase 7 (do not build): Auto-Sell profit-taking (Phase 8),
order cancel/replace/**reprice** to complete an exit (Phase 8; `replaces_order_id`
stays unpopulated), Auto-Buy (Phase 9), realized-P/L accounting (deferred; a sell
folds the position down, no realized P/L), short selling, trailing/high-water
floors. **Paper only. No live trading. No new credentials.**

**Known beta limitations, surfaced not hidden** (each has an operator-visible
signal, per "nothing fails silently"):
- **Detection latency ≈ the order-poll cadence** (`poll_cadence_seconds`, default
  15s) — protection evaluates inside the monitoring tick. A tighter dedicated
  protection cadence is a config knob (§9); sub-tick reaction is Phase 8.
- **Pre/after-hours exit is best-effort single-shot** — Rule 12 forbids a market
  order there, so a fast gap can leave an aggressive protective LIMIT unfilled.
  Beta does **not** reprice it (Phase 8's cancel/replace seam); it surfaces a
  loud, deduped `protection_stalled` signal so the operator can act. See §3.
- **Protection is coupled to `ENABLE_MONITORING`** — it runs in the monitoring
  loop, so disabling monitoring disables protection. `GET /api/protection`
  surfaces `protection_active` truthfully; the cockpit shows it (§8).

---

## 1. The three locked safety decisions (operator, this session)

- **D-P1 — Automatic protection.** A hard-floor breach **auto-creates and submits
  a protective sell** (paper). Built behind the Approval-Gate seam so a future
  human-confirm mode drops in with no state-machine change.
- **D-P2 — Kill-switch: exits exempt; autonomous protection pauses.** **Manual
  flatten always works** (bypasses kill switch / pause-buys / closed session —
  it is risk-reducing and operator-initiated). **Autonomous floor-breach selling
  pauses** while the kill switch is engaged — and it stays blocked **at claim
  time**, not only at intent creation, so a lingering CREATED protective order
  cannot slip through if the switch engages after creation. New BUY intent stays
  blocked as today. Pause-buys never blocks any sell.
- **D-P3 — Exit order type.** **Regular hours → MARKET** (guarantees the exit;
  first real use of `OrderType.MARKET`). **Pre-market / after-hours → aggressive
  protective LIMIT** (Rule 12: limit-only there). **The order type is (re)decided
  at SUBMISSION time**, not frozen at creation (§5.4) — Rule-12 legality is a
  property of when the order reaches the exchange (D-015).

Rule 8 gets a documented carve-out (§12 / `01_ARCHITECTURE.md`): the kill switch
blocks all new **BUY** order intent **and autonomous protection**; **risk-reducing
manual/flatten exits are exempt** (D-P2).

---

## 2. Core principle + the schema change

Buy side: `Candidate → Order → Fill → Position`. Sell side mirrors it:
`SellIntent → Order → Fill → Position`. **Every `Order` originates from exactly
one of `Candidate` (buy) or `SellIntent` (sell):**
- `Order.candidate_id` becomes **`Optional[str]`**; `Order` gains
  `sell_intent_id: Optional[str]`.
- **XOR invariant** (checked in the `Order` model validator AND at both stores'
  order-creation boundary): exactly one of `candidate_id` / `sell_intent_id` is
  set. A `BUY` carries `candidate_id`; a `SELL` carries `sell_intent_id`.

**SQLite schema is a TABLE REBUILD, not an additive column (blocker).**
`orders.candidate_id` is `TEXT NOT NULL` (`app/store/sqlite.py:127`) and
`CREATE TABLE IF NOT EXISTS` never relaxes it on an existing DB, and SQLite has no
`ALTER COLUMN`. Add an idempotent `_migrate` step that rebuilds `orders`:
`ALTER TABLE orders RENAME TO orders_old` → `CREATE TABLE orders (... candidate_id
TEXT /* nullable */, sell_intent_id TEXT, ...)` → `INSERT INTO orders SELECT
..., NULL FROM orders_old` → `DROP TABLE orders_old` → recreate indexes — mirroring
the existing `fills` UNIQUE rebuild (`sqlite.py:339-366`), guarded so it runs once
(detect `NOT NULL`/missing `sell_intent_id` via `PRAGMA table_info`). New
`sell_intents` table added via `CREATE TABLE IF NOT EXISTS`. Both stores parity;
fresh test DBs and migrated prod DBs must end identical.

---

## 3. `SellIntent` entity and lifecycle

```python
class SellReason(str, Enum):
    MANUAL_FLATTEN = "manual_flatten"
    PROTECTION_FLOOR = "protection_floor"
    # future Phase 8: AUTO_SELL = "auto_sell"

class SellIntentStatus(str, Enum):   # parallel shape to CandidateStatus
    PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"
    EXPIRED = "expired"; ORDERED = "ordered"
```
Fields: `id, symbol, reason, status=PENDING, target_quantity:int, floor_price:
Optional[float], observed_price: Optional[float], session_id, order_id:
Optional[str], created_at, updated_at, approved_at, rejected_at, expired_at,
ordered_at`. `floor_price`/`observed_price` set for `PROTECTION_FLOOR`, `None`
for `MANUAL_FLATTEN`.

**A parallel `SELL_INTENT_TRANSITIONS` table** in `transitions.py` (NOT literal
reuse of `CANDIDATE_TRANSITIONS` — it is typed on `CandidateStatus`), identical
shape:
```
pending ──approve──▶ approved ──order──▶ ordered   (terminal)
   ├──reject──▶ rejected   (terminal)
   └──expire──▶ expired    (terminal)
```
- Idempotent approve/reject/order (audited no-op on same status);
  `transition_sell_intent` uses `require_status_enum(value, SellIntentStatus)`
  (AIR-009). Every genuine transition writes an audit row.
- **APPROVED is the Approval-Gate seam.** Beta automatic mode drives
  `pending→approved→ordered` atomically; a future human-confirm mode stops at
  `approved`. Manual flatten: the click is the approval.
- **`expired`**: the intent is no longer valid before ordering — position went
  flat by another path, session closed with it un-ordered, price recovered above
  floor, or the intent→order handoff was rejected (self-heal, below).

**SellIntent → Order is 1:1** (mirrors Candidate → Order). **Residual** after a
partial fill is handled by re-evaluation: once the protective Order terminates
(canceled/rejected/filled) with the position still breaching, the next protection
tick creates a NEW intent (subject to dedup).

**Dedup — one active sell-intent per symbol, enforced ATOMICALLY (blocker/TOCTOU).**
"Active" = a `pending`/`approved` intent, OR an `ordered` intent whose Order is
still non-terminal **and not stranded in `needs_review`**. The check-and-insert is
done under **one store-lock hold inside `create_sell_intent`** (both stores) — a
concurrent flatten POST and protection tick cannot both win; the second gets the
existing active intent. The flatten route is idempotent against this.

**Stranded-order eligibility (blocker).** If a protective Order gets stuck in a
`needs_review` reconciliation state (AIR-002, e.g. a transiently un-priceable
fill), the symbol is **still eligible** for a fresh protective intent — a spurious
escalation must never permanently disable protection for a still-breaching symbol.

**Stuck pre/after-hours LIMIT (major).** A protective LIMIT that never crosses
sits `SUBMITTED` (non-terminal); beta has no auto-cancel/reprice (Phase 8). While
it sits, dedup blocks a fresh intent. This is **explicitly best-effort
single-shot**: emit a loud, deduped **`protection_stalled`** audit event +
`GET /api/protection` flag whenever a breaching symbol has a non-terminal
protective order that has not progressed, so the operator can manually flatten
(which cancels the stuck order first — §8). No silent indefinite wait.

**Self-heal (blocker).** On ANY `create_order_for_sell_intent` rejection (position
vanished, oversell, etc.), the intent is atomically transitioned
`approved→expired` (a new `expire` path + a `no_sell_intent_stranded_approved`
Hypothesis invariant, mirroring `no_candidate_stranded_approved`). No intent is
ever left `APPROVED` with no order.

---

## 4. Protection decision engine (`app/protection.py`, pure)

Pure, IO-free (like `app/strategy.py`). All numeric guards reuse
`app/policy.py`'s `finite_number_reason` family — do not re-implement.

```python
def floor_price(average_price, stop_loss_pct) -> float:
    return average_price * (1.0 - stop_loss_pct)

def floor_breach_reason(position, snapshot, config) -> Optional[FloorBreach]:
    """Breach iff a TRUSTWORTHY last_price <= floor. Returns None (no action) when:
    protection disabled; position flat; average_price None/non-finite/<=0;
    snapshot None / last_price None/non-finite/<=0 / snapshot.stale; or no breach."""

def exit_quantity(position) -> int:      # full exit, capped at position.quantity
    return position.quantity

def protective_limit_price(snapshot, config) -> Optional[float]:
    """Aggressive marketable sell limit for pre/after-hours. bid is Optional and
    may be None/NaN/<=0 — route it through finite_number_reason FIRST; treat an
    absent/invalid/crossed bid as missing and fall back to last_price. Never
    evaluate min() over a possibly-None bid. Price = min(valid_bid, last_price) *
    (1 - limit_buffer_pct); round to tick (penny for >=$1, $0.0001 for <$1);
    clamp strictly > 0 (>= one tick). Returns None only if last_price itself is
    untrustworthy (caller then cannot price a limit -> no action, surfaced)."""
```

**Order type is chosen at SUBMISSION, not here** (§5.4). `exit_quantity` /
`floor_breach_reason` are creation-time; the concrete MARKET-vs-LIMIT + limit
price is (re)computed when the order is actually submitted, from the live session
+ snapshot. A sell limit priced too low simply fills at the NBBO (harmless);
priced None/0 would reject — hence the strict clamp + fallbacks above, all
unit-tested (bid-None fallback, sub-dollar rounding, >0 clamp).

---

## 5. Monitoring integration

`_run_protection` is added as the **first phase** of `run_monitoring_tick`, so a
protective order it creates is claimed + submitted the same tick.
**`run_monitoring_tick(store, adapter, settings, *, market_data=None)`** — a
**keyword-only, default-`None`** market-data handle (minor): the ~30 existing
positional callers (tests, the Hypothesis machine) are untouched; `_run_protection`
is a no-op when `market_data is None`. `main.py` passes `app.state.market_data`.

`_run_protection(store, adapter, market_data, settings)`:
1. `positions = [p for p in await store.list_positions() if p.quantity > 0]`;
   return early if none.
2. **Ensure held symbols have market data** — `await market_data.subscribe(held)`
   (idempotent). This makes the monitoring loop the authority guaranteeing held
   coverage even when `enable_strategy_engine=False`. See §5.1.
3. For each held symbol with a breach (`floor_breach_reason`), **cancel any open
   BUY first** (§5.3), then, if **not kill-switched** (D-P2 pause) and **no active
   sell-intent** (dedup), create a `PROTECTION_FLOOR` intent → auto-approve →
   `create_order_for_sell_intent(order_type=MARKET placeholder)` (the real type is
   set at submission, §5.4) → write `protection_triggered`.
4. **Kill-switch pause** — if engaged and any held position breaches, manage a
   per-symbol `protection_paused` ↔ `protection_resumed` **transition** (not an
   unpaired once-ever flag): emit `protection_paused` when a symbol enters the
   paused-and-breaching set, `protection_resumed` when it leaves. Names which
   positions are frozen (major).
5. Never raises out of the tick (per-symbol try/except; the loop's never-crash
   contract).

The created `CREATED` sell order flows through the **existing, side-agnostic**
submit → reconcile pipeline. `session_id` for a `PROTECTION_FLOOR` intent = the
current session, **auto-minting today's session only when it actually creates an
intent** (never on an idle tick — preserves the strategy loop's no-idle-mint
discipline).

### 5.1 Market-data subscription union (armed ∪ held)

Desired subscription set = **armed watchlist ∪ open-position symbols**; a symbol
is never unsubscribed while a position is open. A shared helper computes the union
so the strategy loop's unsubscribe sync and `_run_protection`'s additive subscribe
cannot disagree. Strategy-disabled ⇒ `_run_protection` still subscribes held
symbols. A flat+unarmed once-held symbol may linger subscribed if strategy is off
— bounded, benign, documented.

### 5.2 The side/reason-aware submission gate (HIGHEST RISK)

**All the logic lives inside `plan_claim_order_for_submission`
(`app/store/core.py`), branching on the order — the shared pure predicates
`order_intent_block_reason` / `session_submission_block_reason` are UNCHANGED**, so
every BUY caller and its tests are provably byte-for-byte untouched (major).

For a `SELL` order the claim **short-circuits the control re-check** based on the
owning `SellIntent.reason` (fetched under the same lock; gate on
`order.side is SELL AND order.sell_intent_id is not None AND order.candidate_id is
None` so a mislabeled order cannot slip through — minor):
- **`MANUAL_FLATTEN`** → claim (`CLAIM_CLAIMED`) without consulting **any** of
  `{session_submission_block_reason(own_session): session_closed/unknown_session,
  order_intent_block_reason(current_session): kill_switch/buys_paused}` — flatten
  always exits (D-P2).
- **`PROTECTION_FLOOR`** → bypass `buys_paused`, `session_closed`,
  `unknown_session` (a lingering position must be exitable post-close) **but STAY
  BLOCKED by the kill switch at claim time** (both own- and current-session kill
  switch). So an autonomous protective order created just before the switch
  engages is **held** (not submitted) — and `_run_protection`/the pause path
  transitions such a lingering held protective order to `expired` while the switch
  is engaged, so it is not held forever.
- A `BUY` order: unchanged (every existing control/session test holds).

### 5.3 Cancel open BUYs before exiting (major)

Position derives only from filled shares, so an open unfilled BUY is invisible to
`exit_quantity`. Before creating a sell intent (flatten OR floor breach) for a
symbol, **cancel every non-terminal BUY order for that symbol** (a `CREATED` buy →
`CANCELED` locally; a live buy → `cancel_order` at the broker + `CANCEL_PENDING`),
so the exit actually reaches and stays flat and a live BUY never coexists with a
protective SELL (self-cross). Idempotent; audited.

### 5.4 Order type (re)decided at SUBMISSION (blocker — Rule 12 / D-015)

The protective order is created as `MARKET` (the "full exit" intent). **At
submission** (the single choke point all paths funnel through — first submit,
release-retry, stale re-drive), for a `SELL` order the submit path re-derives the
type against `session_type_for(utcnow())` + the live snapshot:
- session `REGULAR` → submit `MARKET`.
- session `PRE_MARKET`/`AFTER_HOURS` → **downgrade to `LIMIT`** with
  `protective_limit_price(snapshot)` (recomputed live) before the broker call.
This gives the monitoring submit path market-data access for sells and guarantees
a MARKET order can never reach the adapter in a limit-only session — the D-015
"decide session-conditional behavior at submission time" pattern, applied to
`order_type` as well as `extended_hours`. Covered by an IO-free test whose mock is
made session/type-aware for the create-regular / submit-after-hours boundary.

### 5.5 Transient-submit release is side-aware (blocker)

The post-submit-failure release (`app/monitoring.py`) sets `CANCELED` for a
closed-session order today (BUY no-zombie, D-013a). **A SELL must ALWAYS release
`SUBMITTING→CREATED` (retry next tick), never `CANCELED`** — a sell is legitimately
submittable in a closed session (§5.2) and reconciles post-close (D-011). Only a
BUY keeps the no-zombie `CANCELED`. Tested both ways.

---

## 6. Store methods (both stores, atomic, parity)

Shared planners in `app/store/core.py`; `any_store` parity.
- `create_sell_intent(*, symbol, reason, target_quantity, floor_price=None,
  observed_price=None, session_id) -> SellIntent` — **atomic single-flight**:
  active-intent check + insert + `sell_intent_created` event under one lock; returns
  the existing active intent if one exists. Validates positive whole
  `target_quantity`, real `SellReason`, normalized symbol.
- `transition_sell_intent(id, new_status, *, order_id=None)` — mirrors
  `transition_candidate` (enum guard, idempotent no-op, audited).
- `revert_sell_intent_approval(id)` / an `approved→expired` self-heal used on
  handoff failure.
- `create_order_for_sell_intent(intent_id, *, order_type, limit_price) -> Order` —
  atomic APPROVED→ORDERED handoff: sell `Order` (`side=SELL`, `sell_intent_id`
  set, `candidate_id=None`, XOR-checked); intent→`ordered`; both events. **NO CAPI
  risk gate.** Re-reads the live position under the lock and **caps/rejects an
  oversell** (never short). **Limit-vs-market validation (major):** run
  `limit_price_reason` **only when `order_type == LIMIT`**; for `MARKET` require
  `limit_price is None` (defensive) and skip the limit predicate; always run the
  whole-count/positive-quantity check.
- `get_sell_intent`, `list_sell_intents(*, session_id, status, symbol)`,
  `active_sell_intent_for(symbol)`.

**`correlation_id` for the sell lifecycle (major).** `EventSpec` gains a
`correlation_id` field (included in `as_kwargs()`); sell-side planners set it to
the owning `sell_intent_id`; both event writers default
`correlation_id = correlation_id or candidate_id`. So `GET /api/events?correlation_id=
<sell_intent_id>` reconstructs a full protective-sell lifecycle, symmetric to the
buy side (D-020).

**`existing_exposure` excludes SELL orders (major).** A pending/in-flight
protective SELL reduces risk; it must not count as positive CAPI exposure (else it
can push a concurrent BUY over `max_total_exposure`). Exclude `side==SELL` from the
order-notional sum in `app/policy.py::existing_exposure`.

**Session close (blocker/minor).** `plan_close_session` + `SessionClosePlan` +
both store bodies gain a `sell_intent_events` slot and an `expired_sell_intents`
count: open (`pending`/`approved`) sell-intents **expire** at close (like
candidates). **CREATED SELL orders are EXCLUDED from close's D-013a CREATED-cancel
sweep** (a sell must remain submittable post-close); only CREATED **BUY** orders
are canceled. `any_store` parity tests.

---

## 7. Broker adapter — market + sell + fill pricing

- `AlpacaPaperAdapter.submit_order` becomes side/type-aware: reads `order.side` +
  `order.order_type`; `MARKET` → `MarketOrderRequest` (no `limit_price`); `LIMIT`
  → existing `LimitOrderRequest`. `extended_hours` logic unchanged (MARKET only
  ever chosen in regular hours by §5.4). Defensive assert: never build a MARKET
  request when `session_type_for(utcnow())` is not REGULAR.
- **Market-sell fill pricing (major).** `_resolve_fill_price` returns `None` (fill
  withheld → AIR-002 escalation) when neither `filled_avg_price` nor `limit_price`
  is trustworthy — but a MARKET order has no `limit_price`. So a transiently
  absent `filled_avg_price` on a MARKET-sell poll would withhold a
  position-critical fill and (with dedup) strand protection. Fix: for a MARKET
  order, fall back to the reconcile-time snapshot `last_price` for the fill's audit
  price (the position fold is quantity-driven; a sell's exact price does not affect
  the long-only quantity/cost-basis fold — the price is for the record). Combined
  with §3's "needs_review-stranded sell stays re-protectable," a transient pricing
  gap can never disable protection.
- `MockBrokerAdapter`/`SimBrokerAdapter` are side-agnostic; add a MARKET-sell path
  in tests (and make the mock session/type-aware enough to exercise §5.4).

---

## 8. HTTP routes + schemas

- **`POST /api/positions/{symbol}/flatten`** (new). Cancels open BUYs for the
  symbol (§5.3), creates a `MANUAL_FLATTEN` intent for the full current position,
  drives `pending→approved→ordered` (click = approval), returns the intent/order
  view. No position → `409`; active intent in flight → **idempotent** (returns it);
  works under kill switch / pause / closed session (§5.2). If a stuck protective
  LIMIT exists for the symbol, flatten cancels it first, then issues the flatten.
- **`GET /api/protection`** (new, read-only): effective config (enabled, stop-loss
  %, limit-buffer %, **`protection_active`** = monitoring-running ∧ enabled) + per
  open position: `floor_price`, `observed_price`, `breaching`,
  `paused_by_kill_switch`, `stalled`, and any active sell-intent — server-side
  classified (cockpit renders, never re-derives; D-020). Feeds the Position
  Monitor "protection mode."
- `GET /api/sell-intents` (read-only); `/api/review` gains `sell_intents` for the
  queried session (`ReviewResponse.sell_intents`, additive).
- Domain errors → HTTP as the existing trading routes do; no raw leaks.

---

## 9. Config (`app/config.py`)

`_env_float`/`_env_int` pattern, reject non-finite/out-of-range at load:
- `protection_enabled: bool = True`.
- `protection_stop_loss_pct: float` (default `0.08`); must be `>0` and `<1`.
- `protection_limit_buffer_pct: float` (default `0.005`); `>=0` and `<1`.
- `protection_cadence_seconds: Optional[float]` (default `None` = use the
  monitoring poll cadence). If set (`>0`), protection can be documented to run on
  its own cadence; beta default keeps it in the monitoring tick and **documents the
  ~15s detection latency**. (Beta keeps it simple; a dedicated fast loop is a
  later knob.)

---

## 10. Safety invariants (the review checklist gets these)

1. Rule 7 preserved — position derives only from appended fills; `_run_protection`
   never touches position.
2. No short — `exit_quantity` caps at live position; `create_order_for_sell_intent`
   re-checks under lock; `NegativePositionError` backstop.
3. Kill switch (D-P2) — manual flatten always exits; autonomous protection is
   blocked at claim time while engaged and surfaced (`protection_paused`/
   `_resumed`); BUY control behavior byte-for-byte unchanged.
4. No action on `None`/stale/non-finite market data.
5. Rule 12 — MARKET only in regular hours, decided at submission (§5.4).
6. Single active sell-intent per symbol, enforced atomically; flatten idempotent;
   a `needs_review`-stranded order never permanently disables protection.
7. Order origin XOR — every order has `candidate_id` XOR `sell_intent_id` (model
   validator + store boundary + Hypothesis invariant).
8. No stranded APPROVED sell-intent (self-heal + Hypothesis invariant).
9. Flatten/breach cancel open BUYs first — an exit truly reaches flat; no
   simultaneous live BUY + protective SELL.
10. Parity — both stores identical (`any_store`).
11. Realized P/L still deferred; exposure excludes pending sells.
12. Protection ≠ Auto-Sell — safety-only (fixed floor, full exit, no reprice).

---

## 11. Test plan (IO-free; both stores where store-facing)

- **`app/protection.py` pure**: floor math + exact boundary; None/stale/non-finite
  snapshot, disabled, flat → no action; full-exit sizing; `protective_limit_price`
  bid-None fallback, sub-dollar tick, >0 clamp.
- **Store (`any_store`)**: create/transition/revert/expire sell-intent; handoff
  sets `side=SELL`/`sell_intent_id`/`candidate_id=None`, XOR enforced; oversell
  rejected; MARKET handoff skips `limit_price_reason`, LIMIT applies it; atomic
  single-flight (two concurrent creates → one active intent); dedup incl.
  needs_review-eligibility; correlation_id = sell_intent_id; session-close expiry +
  CREATED-SELL survives close; parity of events/persistence/readback.
- **Submission gate (`any_store`)**: MANUAL_FLATTEN sell submits under kill
  switch / pause / closed / date-rolled session; PROTECTION_FLOOR sell submits
  under pause/closed but is HELD under kill switch (and the lingering held order is
  expired); BUY still held under each (regression); side+origin cross-check.
- **Release/close**: transient submit failure of a SELL in a closed session
  releases to CREATED and re-drives to SUBMITTED (never CANCELED); flatten →
  close-before-tick → the sell still submits.
- **Order-type at submission**: MARKET created regular / submitted after-hours →
  downgraded to LIMIT (mock made session/type-aware); never a MARKET request in
  pre/after-hours.
- **Monitoring**: breach → auto protective sell → fill → flat; residual
  re-protection after partial; kill switch pauses autonomous (with paused/resumed
  events) but not flatten; stale/absent data → no action; held-but-disarmed symbol
  stays subscribed + protected; open BUY canceled before exit; exposure unchanged
  by a pending sell; `protection_stalled` on a stuck limit.
- **Broker**: MARKET-sell + LIMIT-sell request construction; MARKET fill-price
  fallback.
- **Routes**: flatten happy/no-position(409)/idempotent/under-kill-switch/cancels
  open BUY; `GET /api/protection` classification incl. `protection_active`.
- **Hypothesis machine**: extend `run_monitoring_tick` calls for the new
  `market_data` kwarg (inject a fake feed); add rules hold→breach→protect→flat and
  manual-flatten; add invariants `order_has_exactly_one_origin` (XOR) and
  `no_sell_intent_stranded_approved`; existing safety invariants must hold across
  sell interleavings.
- Coverage floor 93% (`--cov-branch`) holds; repo-local temp root.

---

## 12. Build sequence — each increment gated by a sub-agent review

1. **ADR (this doc)** — design-reviewed (done); v2 resolves all findings.
2. **Data model + schema** — `SellIntent`/`SellReason`/`SellIntentStatus`,
   `SELL_INTENT_TRANSITIONS`, new `EventType` members (`sell_intent_created`,
   `sell_intent_transition`, `protection_triggered`, `protection_paused`,
   `protection_resumed`, `protection_stalled`); `Order.candidate_id` Optional +
   `sell_intent_id` + XOR validator; SQLite `_migrate` **table rebuild** + new
   `sell_intents` table; both stores. → review.
3. **Store methods** — atomic single-flight `create_sell_intent`, transitions,
   revert/expire, `create_order_for_sell_intent` (limit-vs-market, oversell cap,
   XOR, correlation_id), close-session sell handling, `existing_exposure` sell
   exclusion; both stores + parity. → review.
4. **Protection engine** — `app/protection.py` pure + exhaustive tests. → review.
5. **Monitoring** — `_run_protection`, subscription union, kill-switch pause
   (paused/resumed), open-BUY cancel, side/reason-aware claim gate, side-aware
   release, submission-time order-type re-derivation; wire `market_data` (kw-only)
   into the loop + `main.py`. → review.
6. **Broker** — side/type-aware `submit_order` + MARKET fill-price fallback;
   adapter tests. → review.
7. **Routes + schemas** — flatten, `GET /api/protection`, sell-intent list,
   `/api/review` inclusion. → review.
8. **Cockpit** — Position Monitor protection column (`protection_active`, floor,
   breaching/paused/stalled) + working flatten button; thin client. → review.
9. **Gate** — full suite + coverage + parity; **independent adversarial review by
   a fresh context** of the whole Phase 7 diff; fix confirmed findings; **amend
   Rule 8** in `01_ARCHITECTURE.md` + `05_REVIEW_CHECKLIST.md` for the D-P2
   carve-out; write **D-025** in `00_START_HERE.md`; update README/`03_UI_WORKFLOW`;
   commit + push on `claude/confident-babbage-ti5cm8`.

Red-then-green per increment; both-store parity where store-facing; domain errors
never leak raw; no BUY-side behavior changes.

---

## Appendix — Design-Review Resolutions (v1 → v2 traceability)

**Blockers:** (1) SQLite `candidate_id NOT NULL` → §2 table-rebuild migration.
(2) Transient release cancels a SELL in a closed session → §5.5 side-aware release.
(3) Order type frozen at creation vs Rule-12-at-submission → §5.4 re-derive at
submission. (4) Stranded APPROVED intent poisons dedup → §3 self-heal
approved→expired + invariant.

**Majors:** correlation_id sell analogue → §6 (EventSpec field). Session close
cancels CREATED sells → §6 exclude SELL from close sweep. Dedup blocks stuck-limit
residual → §3 best-effort single-shot + `protection_stalled`. Side-awareness on
pure predicates widens blast radius → §5.2 logic inside `plan_claim` only.
`existing_exposure` counts sells → §6 exclude sells. Kill switch bypass fires
autonomous sell after engage → §5.2 reason-aware, kill-switch-blocked at claim +
expire lingering. `protection_paused` no reset → §5 paused/resumed transition.
`limit_price_reason` rejects MARKET → §6 gate on order_type. Un-priceable MARKET
fill strands → §7 fallback + §3 eligibility. Aggressive-limit bid-None crash / tick
→ §4 guards + rounding. Side-aware claim under-specified for closed/date-rolled →
§5.2 names both predicates. Protection inert when `ENABLE_MONITORING=false` → §0/§8
`protection_active` surfaced. Flatten/breach ignore open BUYs → §5.3 cancel first.
Order-type creation-vs-submission (dup #3) → §5.4. Dedup TOCTOU → §3/§6 atomic
single-flight. Stuck LIMIT blocks re-protection → §3 `protection_stalled` (reprice
is Phase 8).

**Minors:** close-session restructure scoped → §6/§12.3. Side+origin cross-check →
§5.2. Dedup atomicity → §3/§6. PROTECTION_FLOOR session_id / no idle-mint → §5.
15s cadence surfaced → §0/§9. `run_monitoring_tick` signature kw-only default →
§5. Rule 8 doc carve-out → §1/§12.9. Test-plan/Hypothesis invariants → §11.
EventType members + parallel `SELL_INTENT_TRANSITIONS` + `ReviewResponse.sell_intents`
→ §12.2.
