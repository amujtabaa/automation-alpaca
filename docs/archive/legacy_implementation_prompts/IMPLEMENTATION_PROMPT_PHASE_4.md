# Implementation Prompt — Phase 4: Alpaca Paper Adapter
## Alpaca Clean-Sheet CAPI Option 2.5

Build Phase 4: the Alpaca Paper Adapter, background monitoring loop, fill
reconciliation, and position updates. This is the first phase that makes real
network calls. Everything built previously (candidate flow, order records, fill
machinery, position folding) stays intact — Phase 4 wires the Alpaca paper API
into that existing machinery and starts making order records real.

Canonical rules are in `docs/01_ARCHITECTURE.md` and
`docs/02_DATA_AND_PERSISTENCE.md` (auto-loaded). Decisions D-006 through D-011
are all load-bearing here — read `docs/00_START_HERE.md` before starting.

**The overriding safety constraint: paper only, always.** No live trading path
is introduced in this phase or ever. No `ALPACA_LIVE_*` keys, no live endpoint
URLs, no flag that switches from paper to live. If you find yourself writing
anything that could route to a live Alpaca account, stop.

---

## Agent / Compute Efficiency (Ultracode housekeeping — read first)

- **Haiku** for mechanical work: running tests, grepping, reading files to
  report contents, simple boilerplate with an exact spec, formatting.
- **Sonnet** for the bulk of implementation: the adapter interface and mock,
  the paper implementation, the monitoring loop, routes, cockpit wiring, most
  test-writing. Default working tier for this phase.
- **Opus** only for genuine hard reasoning: a subtle concurrency issue in the
  monitoring loop, a reconciliation edge case that requires real depth. If a
  task can be precisely specified, it does not need Opus.
- Parallelize only independent work. The adapter interface must exist before
  the paper implementation, and both before the monitoring loop that calls them.
  Reading/grepping/test-running across unrelated files can be parallelised on
  cheaper tiers.
- State tier choice briefly when spawning a sub-agent.

---

## Scope: What Phase 4 Builds

### 1. BrokerAdapter Interface (app/broker/)

Create `app/broker/adapter.py` with an abstract `BrokerAdapter` interface —
same ABC pattern as `ApprovalGate`. Route handlers and the monitoring loop
depend on this interface, never on `AlpacaPaperAdapter` directly.

Minimum interface surface (keep it small — don't over-engineer for future
needs we haven't designed):

```python
class BrokerFill:
    """A single execution report from the broker."""
    source_fill_id: str       # Alpaca's execution/fill ID (for dedup)
    quantity: float
    price: float
    filled_at: datetime

class BrokerOrderUpdate:
    """Current broker-side state of an order."""
    status: OrderStatus       # map to our OrderStatus enum
    filled_quantity: float
    fills: list[BrokerFill]   # new fills since last poll (may be empty)

class BrokerAdapter(ABC):
    @abstractmethod
    async def submit_order(self, order: Order) -> str:
        """Submit to broker. Returns broker_order_id (Alpaca's order UUID)."""

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> BrokerOrderUpdate:
        """Poll current state. Called on the monitoring cadence."""

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel an open order. Raises if already terminal."""
```

Also create `app/broker/__init__.py` exporting the public types, and
`app/broker/mock.py` with `MockBrokerAdapter` — a fully controllable test
double that records calls and lets tests set per-order responses. Unit tests
only ever use `MockBrokerAdapter`; they make no network calls (Rule 9).

### 2. AlpacaPaperAdapter (app/broker/alpaca_paper.py)

Concrete implementation. **`alpaca-py` is the only permitted SDK.** Add
`alpaca-py>=0.x` to `requirements.txt`. Nothing outside `app/broker/` may
import from `alpaca`. The adapter:

- Initialises from env vars `ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_API_SECRET`
  only (never live keys). Use `alpaca.trading.client.TradingClient(paper=True)`.
- `submit_order`: maps our `Order` (LIMIT, long-only buy for beta) to an
  Alpaca `LimitOrderRequest` and returns the Alpaca order UUID as
  `broker_order_id`. Enforces Rule 12: pre-market/after-hours → limit order
  (this is already true since we only create LIMIT orders, but confirm it here).
- `get_order_status`: fetches the Alpaca order by UUID, maps status and fills
  to `BrokerOrderUpdate`. Map Alpaca statuses to our `OrderStatus` carefully —
  Alpaca uses strings like `"partially_filled"`, `"filled"`, `"canceled"`,
  `"rejected"`, `"accepted"` (≈ submitted). Log unmapped statuses as warnings
  rather than raising; treat them as SUBMITTED (open) until they resolve.
- `cancel_order`: calls Alpaca cancel endpoint. If Alpaca returns "already
  terminal" (404 or status already terminal), treat as a no-op success
  (idempotent cancel — the order is gone either way).
- All Alpaca SDK calls are async-wrapped (use `asyncio.to_thread` if the SDK
  is sync). Network errors are logged and re-raised — the caller (monitoring
  loop) handles retry/backoff.

**Credentials never appear in code, logs, or committed files.** The `.env`
file (gitignored) holds them. Add a clear comment near the credential loading
code pointing to `.env.example` (a committed example with placeholder values).
Create `.env.example` at the repo root with the two variable names and a
comment that these are paper-only keys.

### 3. Order Model — broker_order_id field

Confirm whether `Order.broker_order_id` already exists in `app/models.py`. If
not, add it as `Optional[str] = None`. This is the Alpaca order UUID stored
after submission; it is the key used to poll and cancel. Also confirm
`transition_order` accepts and persists `broker_order_id` — if not, add it.
Migration: `SqliteStateStore._migrate` should add the column if absent (same
idempotent migration pattern already in use for `fills.session_id`).

### 4. Background Monitoring Loop

Create `app/monitoring.py` with the async monitoring loop. The lifespan in
`app/main.py` already starts a background task — this loop replaces the
current no-op placeholder (if one exists) or is wired in now.

**Loop structure:**

```python
async def monitoring_loop(store: StateStore, adapter: BrokerAdapter,
                          config: Config) -> None:
    while True:
        await asyncio.sleep(config.poll_cadence_seconds)   # default 15
        try:
            await _submit_pending_orders(store, adapter)
            await _reconcile_open_orders(store, adapter, config)
        except asyncio.CancelledError:
            raise   # clean shutdown
        except Exception:
            # Log but never crash the loop — a transient Alpaca error
            # should not stop monitoring.
            pass
```

**`_submit_pending_orders`:** finds all orders with status `ORDERED` (created
but not yet submitted to Alpaca), calls `adapter.submit_order`, stores the
returned `broker_order_id` on the order, and transitions to `SUBMITTED`. If
submission fails (network error, Alpaca rejects), log the error and leave the
order at `ORDERED` to retry on the next loop iteration.

**`_reconcile_open_orders`:** finds all orders with status `SUBMITTED` or
`PARTIALLY_FILLED`, regardless of their session's status (D-011 — keep polling
until terminal state). For each:

1. Call `adapter.get_order_status(order.broker_order_id)`.
2. For each new fill in the response: call
   `store.append_fill(order_id, symbol, side, qty, price, source_fill_id=...,
   session_id=order.session_id)`. The store's dedup logic handles duplicates
   (D-006) — don't pre-check; let the store reject silently and move on.
3. Update the order's `filled_quantity` and status via `transition_order`.
4. If the order is still open and `(now - order.created_at) > unfilled_timeout`
   (default 60 minutes, `ALPACA_UNFILLED_TIMEOUT_MINUTES`): append an audit
   event of a new type `order_stale` (with the age in the payload). Write this
   event once (check whether a `stale` event already exists for this order
   before appending — don't spam one per loop tick).

**Cadence config:** `poll_cadence_seconds` and `unfilled_timeout_minutes` come
from `app/config.py`, read from env vars, with sensible defaults (15s / 60min).

**Concurrency note:** the monitoring loop runs as a background asyncio task in
the same single-process event loop as FastAPI. The existing `asyncio.Lock`
(already held by `StateStore` mutating operations) serializes concurrent access.
The loop must not hold a lock across the Alpaca network call — acquire lock
only for the store operations, not for the adapter call itself.

### 5. New API Endpoints

**`GET /api/orders/{order_id}`** — single order fetch (confirm it exists or
add it). Returns 404 if not found.

**`POST /api/orders/{order_id}/cancel`** — cancel an open order:
1. Fetch the order; 404 if not found.
2. If already terminal (filled/canceled/rejected), return 409.
3. Call `adapter.cancel_order(order.broker_order_id)`.
4. Transition order to `CANCELED` via `store.transition_order`.
5. Return the updated order.

The cancel route depends on `BrokerAdapter` (the interface), not
`AlpacaPaperAdapter`. Wire it into `deps.py` the same way `get_approval_gate`
is wired.

### 6. Cockpit — Position Monitor + Orders

**Position Monitor** (`cockpit/app.py`): make it functional. Currently shows
empty state; now that fills populate positions, show real data:
- Table: symbol, quantity (from `GET /api/positions`), average price.
- **Do NOT show unrealized P/L** — it requires current price from the market
  data service (Phase 5). Show a "P/L: pending market data" placeholder or
  omit the column entirely. Do not invent a fake price or hard-code a value.
- Flatten button: show it but wire it to a disabled/coming-soon state — the
  sell-side exit logic belongs to Phase 7 (Sell-Side Protection). Do not
  implement sell-order creation here.

**Orders section** (can be part of the Position Monitor screen or a new
sub-section — your call on placement, as long as Streamlit stays thin):
- Table of open orders (status = SUBMITTED or PARTIALLY_FILLED) showing
  symbol, quantity, limit price, status, filled_quantity, age.
- **Stale order alert**: highlight orders that have a `stale` audit event.
- **Cancel button** per open order: calls `POST /api/orders/{id}/cancel`.
  Confirm with a brief "are you sure?" before sending (a second button click
  or simple `st.warning` prompt is fine — no modal needed).

Verify the Position Monitor end-to-end with the `AppTest` pattern where
possible (position appears after a fill is appended through the API).

---

## Out of Scope (Do Not Build)

- Live trading, live Alpaca keys, any live endpoint URL.
- Websocket trade updates (REST polling only — D-011; websocket is Phase 8).
- Auto-cancel on unfilled timeout (surface only — D-011).
- Unrealized P/L calculation (needs market data — Phase 5).
- Position flatten / sell-side order creation (Phase 7).
- Order cancel/replace/resize for strategy-driven exits (Phase 8 / Auto-Sell).
- Market data service / websocket stream (Phase 5).
- Strategy Engine / candidate generation (Phase 5).
- CAPI risk checks (Phase 6).
- Sell-Side Protection (Phase 7).

---

## Credentials and Environment Setup

`.env.example` (committed, safe — no real values):
```
# Alpaca paper trading credentials — PAPER ONLY, never live keys.
# Get these from: https://app.alpaca.markets -> Paper account -> API Keys
ALPACA_PAPER_API_KEY=your-paper-key-here
ALPACA_PAPER_API_SECRET=your-paper-secret-here

# Optional — monitoring cadence and unfilled-order timeout
ALPACA_POLL_CADENCE_SECONDS=15
ALPACA_UNFILLED_TIMEOUT_MINUTES=60
```

`.env` (gitignored, holds real paper values — never committed):
The developer copies `.env.example` to `.env` and fills in real paper keys.

Add `.env.example` to the `README.md` setup section. Confirm `.env` is in
`.gitignore` (it is — verify before adding any credentials).

---

## Tests Required

**Unit tests (IO-free, MockBrokerAdapter, no network):**
- `MockBrokerAdapter` is controllable: set per-order responses (fill it,
  partially fill it, cancel it, reject it).
- Monitoring loop submits `ORDERED` orders and transitions them to `SUBMITTED`
  with the returned `broker_order_id`.
- A fill from the mock drives `append_fill` → position updates (fold correctly
  per D-006 formula).
- Duplicate fill (same `source_fill_id`) is detected by the store and not
  double-appended; position unchanged on the second attempt.
- Order reaches `FILLED` when all fills are received; reaches `PARTIALLY_FILLED`
  on partial fill.
- Unfilled order past timeout appends exactly one `order_stale` event (not
  one per loop tick — idempotent).
- Cancel route transitions order to `CANCELED` and calls adapter once.
- Attempting to cancel a terminal order returns 409.
- `MockBrokerAdapter` records every call (submit, get_status, cancel); tests
  assert specific adapter interactions.

**Integration tests (env-gated):**
```
tests/integration/test_alpaca_paper.py
```
Run only when `ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_API_SECRET` are present:
```python
pytestmark = pytest.mark.skipif(
    not os.getenv("ALPACA_PAPER_API_KEY"),
    reason="Alpaca paper credentials not configured"
)
```
Integration tests: submit a real paper order, poll until it reaches a terminal
state (or times out after a reasonable wait), confirm the fill was appended and
the position updated. These run against Alpaca's paper endpoint — no live
account is ever used.

Integration tests are **not** part of the standard `pytest` run and do not need
to pass in CI without credentials. Document in the README how to run them:
`pytest tests/integration/` with credentials in `.env`.

**Existing suite must still pass:**
The standard `pytest` (184 tests) must pass without any Alpaca credentials
present — no integration tests auto-run, no import errors from missing env vars.

---

## Git & Review

- Branch `phase4-alpaca-paper-adapter` off `master`.
- Incremental commits: adapter interface + mock → paper implementation → Order
  model migration → monitoring loop → routes → cockpit → tests.
- Push to `origin` after each meaningful commit.
- **Never commit credentials.** Run `git diff --staged` before every commit and
  confirm no API keys are present.
- Run `python -m pytest` (standard suite, no credentials needed) before
  declaring done — all 184 original tests plus new unit tests must pass.
- **Independent dual-lens review before merge to `master`** (per `CLAUDE.md`):
  input-boundary pass (hostile inputs to the new cancel endpoint and the
  monitoring loop's error paths) + sequence/lifecycle pass (submit → partial
  fill → full fill → position; submit → timeout → cancel; fill dedup sequence).
  Bring the diff to the planning chat before merging.

---

## Definition of Done

- [ ] `app/broker/adapter.py` — `BrokerAdapter` ABC + `BrokerFill` /
      `BrokerOrderUpdate` types.
- [ ] `app/broker/mock.py` — `MockBrokerAdapter` fully controllable, used by
      all unit tests.
- [ ] `app/broker/alpaca_paper.py` — `AlpacaPaperAdapter` using `alpaca-py`,
      paper=True, no live path.
- [ ] `alpaca-py` added to `requirements.txt`.
- [ ] `.env.example` committed; `.env` confirmed gitignored.
- [ ] `Order.broker_order_id` exists and is persisted; SQLite migration
      is idempotent.
- [ ] `app/monitoring.py` — monitoring loop wired into app lifespan; submits
      `ORDERED` orders; reconciles `SUBMITTED`/`PARTIALLY_FILLED` orders;
      surfaces stale orders (one event per order, not one per tick).
- [ ] `POST /api/orders/{id}/cancel` implemented, wired to `BrokerAdapter`
      interface, 409 on terminal orders.
- [ ] Cockpit Position Monitor shows real positions (quantity + avg price);
      no fake P/L; flatten is placeholder.
- [ ] Open orders visible in cockpit with cancel button; stale orders alerted.
- [ ] Unit tests cover submit, fill (including dedup and partial), cancel,
      stale-event idempotency — all with `MockBrokerAdapter`, IO-free.
- [ ] Integration tests in `tests/integration/` gated behind env vars; not
      in standard pytest run.
- [ ] Standard `pytest` (no credentials) passes with all prior tests green.
- [ ] No credentials in any committed file, log output, or exception message.
- [ ] Branch pushed to `origin`; independent dual-lens review before merge.
