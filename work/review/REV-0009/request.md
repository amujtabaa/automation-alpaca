---
type: Review Request
rev_id: REV-0009
campaign_id: CAMPAIGN-0001
packet: STORE-IMPL
container_group: G-C (store impls + parity)
packet_lens: SWE (primary) + adversarial red-team + performance (dual-store parity)
status: AWAITING_REVIEW
targets: [G-C-memory-store, G-C-sqlite-store, G-C-dual-store-parity]
human_gated_surfaces: [order-submission, manual-flatten, event-log-truth]
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [safety-core #8, safety-core #9, INV-001, INV-002, INV-003, INV-004, INV-020, INV-021, INV-025, INV-030, INV-031, INV-032, INV-033, INV-034, INV-035, INV-036, INV-037, INV-038, INV-040, INV-041, INV-050, INV-051, INV-052, INV-060, INV-061, INV-075, "spine INV-1..9"]
adr_in_scope: [ADR-001, ADR-002, ADR-003, ADR-004, ADR-008]
created: 2026-07-10
---

# Review Request REV-0009 — Store implementations + dual-store parity (how each store applies the plan), SWE + red-team + perf

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes **no** correctness claims — code beats the atlas, and if they
disagree that is itself a finding, at least P1). You have the full repo at the frozen SHA.

This packet is the **implementation layer** of the store. REV-0006 (STORE-SPEC) owns the ABC
(`base.py`) and the pure planners (`core.py`) — *what* the decision is. You own the two concrete
`StateStore` implementations that drive those planners: *how* each store **fetches** the inputs the
planner decides over, **holds its lock**, **applies the returned plan atomically**, and stays at
**parity** with its sibling. So this packet carries three lenses at once:
- **SWE (primary):** does each store fetch exactly the state the planner needs, apply every field of
  the returned plan, and dispatch on every `outcome` the planner can emit — with the *same* observable
  result in both stores (the `any_store`/replay-parity property)?
- **Adversarial red-team (secondary):** can a store **diverge from its planner's intent** (apply a
  partial plan, drop a co-written event, mutate the wrong row) or **from its sibling** (memory does X,
  sqlite does Y for the same call) in a way that double-submits, double-exits, moves quantity off a
  non-fill, or flips a status column with no lifecycle event?
- **Performance (tertiary):** N+1 queries, full-table scans, and unbounded loads on the hot paths of
  the sqlite store specifically (memory folds in RAM; sqlite pays per query).

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/store/memory.py` (2239 LOC) — `InMemoryStateStore` (`memory.py:134`): the IO-free store, one
  `asyncio.Lock`, a **nestable** snapshot/restore atomicity block `_atomic()` (`memory.py:248`), and
  `*_unlocked` composition helpers.
- `app/store/sqlite.py` (3359 LOC) — `SqliteStateStore` (`sqlite.py:349`): the durable store, one
  `asyncio.Lock`, a per-call `BEGIN/COMMIT/ROLLBACK` context manager `_tx()` (`sqlite.py:370`), and
  `*_locked` explicit-cursor composition helpers.
- `app/store/__init__.py` (51 LOC) — `create_state_store` (the settings→impl selector) and the
  public export surface.

**Owned by other packets (follow leads freely into them):** these have a deep-coverage owner
elsewhere, so you need not audit them exhaustively — but **do not assume their contract holds.** If a
store's correctness rests on a behavior a neighbor doesn't actually guarantee, re-derive that behavior
from the neighbor's own code and report the reliance as **your** finding.
- the **pure planners** the stores drive, and the ABC/DTO contract they satisfy
  (`core.py`, `base.py`) → REV-0006 (STORE-SPEC). *You* own whether the store **feeds the planner the
  right inputs and applies its whole plan**; the planner's own logic is REV-0006's.
- the **projectors** each store folds to derive truth — `project_symbol_position`,
  `project_order_status`, `quarantined_symbols`, `timeout_quarantined_order_ids` (`app/events/projectors.py`) →
  REV-0007 (EVENTS). *You* own whether the store calls them over the **right event set** and caches/loads
  that set efficiently; their fold math is REV-0007's.
- the **engine** that sequences these store calls under its single-writer loop (`app/monitoring.py`,
  `reconciliation.py`) → REV-0005 (ENGINE). The store's lock discipline meets the engine here.
- the **facade** that maps `StoreError` subclasses to HTTP and calls the store (`app/facade/*`) →
  REV-0013 (FACADE-API).

## What you're reviewing
Each store is a thin "fetch → plan → apply" sandwich around a shared pure planner: fetch the state
the planner needs (a dict lookup in memory; a `SELECT` in sqlite), call the planner
(`plan_append_fill`, `plan_transition_order`, `plan_flatten_position`, `plan_claim_order_for_submission`,
`plan_close_session`, …), then apply the immutable plan it returns — the order/fill/intent row change
**plus** its co-written audit `Event` **plus** its co-written lifecycle `ExecutionEvent` — inside the
store's atomicity boundary. The decision is single-sourced in `core.py`; the two stores must apply it
**identically**. The parity property is load-bearing: `InMemoryStateStore` runs the tests IO-free,
`SqliteStateStore` is the durable production engine (safety-core #3), and the replay/parity harness
(`any_store` fixture, `conftest.py:28`; the WO-0007a dual-store parity suite) proves they agree. A
defect here is a store that (a) applies its planner's plan wrong, (b) diverges from its sibling, or
(c) breaks an atomicity/lock invariant the pure planner cannot enforce because atomicity lives in the
*apply*, not the *plan*.

Run for context: read `app/store/memory.py` and `app/store/sqlite.py` at `b600101`. **Verified: both
files are byte-identical between the frozen base and the review-branch tip** (`git diff b600101..HEAD --
app/store/memory.py app/store/sqlite.py app/store/__init__.py` is empty) — there is no in-range diff to
read; review the files as they stand at the frozen SHA.

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
Each anchor is a `file:line` **paired with a stable symbol** so it re-locates if lines drift. All were
opened and confirmed at `b600101`. Pointers are given in **memory ↔ sqlite pairs** so you can diff the
two applies of the same plan side by side.

**The two atomicity primitives (INV-050) — read these first:**
- Memory: `_atomic()` (`memory.py:248`) — snapshots every collection on enter, restores all on ANY
  `BaseException`, and is **nestable** (a helper's `_atomic()` inside a caller's `_atomic()` re-snapshots).
- Sqlite: `_tx()` (`sqlite.py:370`) — one `BEGIN`…`COMMIT`, `ROLLBACK` on exception; the connection is
  autocommit (`isolation_level = None`, `sqlite.py:365`) so *only* code inside a `_tx()` is transactional.
  **A method that opens `_tx()` more than once, or calls a helper that opens its own `_tx()`, is
  multiple transactions, not one** — map which methods do that.
- The parity claim: memory's `_atomic()` docstring says it "Mirrors `SqliteStateStore`'s
  BEGIN/COMMIT/ROLLBACK." Where a memory method wraps N writes in ONE `_atomic()` but its sqlite twin
  splits them across several `_tx()`, the two stores have **different crash-atomicity** for the same
  operation.

**Fill → position apply (safety-core #8/#9, INV-001/002/003/004):**
- `append_fill` — memory (`memory.py:1655`) vs sqlite (`sqlite.py:2583`). Compare the three fetches the
  planner decides over: `order`, `prior_filled` (memory sums `self._fills` at `memory.py:1676`; sqlite
  `SELECT COALESCE(SUM(quantity),0)` at `sqlite.py:2607`), and `is_duplicate` (memory checks the
  `_fill_source_ids` set at `memory.py:1679`; sqlite `SELECT 1 ... AND source_fill_id = ?` at
  `sqlite.py:2616`). Then the apply: FILL_REJECT (single event, no wrapper), FILL_DUPLICATE, and
  FILL_APPEND (memory one `_atomic()` at `memory.py:1720`; sqlite one `_tx()` at `sqlite.py:2660`,
  co-writing fill row + audit `Event` + shadow `ExecutionEvent`).
- Position fold: memory `_position_unlocked` (`memory.py:384`, folds `self._execution_events` in RAM) vs
  sqlite `_position_locked` (`sqlite.py:2713`, `SELECT * FROM execution_events WHERE symbol=? AND
  event_type='fill' ORDER BY sequence`). Both hand the events to `project_symbol_position`.

**The double-submit claim apply (INV-020/021/060; the REV-0001 F-001 class):**
- `claim_order_for_submission` — memory (`memory.py:1212`) vs sqlite (`sqlite.py:1975`). The gate reads
  **projected** (event-log) status, not the raw column: memory `_project_order_unlocked`
  (`memory.py:1223`), sqlite `_project_order_locked` (`sqlite.py:1983`). Both carry the same
  defense-in-depth `assert` that a past-CREATED column projecting CREATED is a co-write violation
  (`memory.py:1231`, `sqlite.py:1989`). The apply co-writes a `SUBMIT_PENDING` ExecutionEvent, keyed on
  an `occurrence` count read under the lock (memory counts `self._execution_events` at `memory.py:1278`;
  sqlite `SELECT COUNT(*)` inside the write tx at `sqlite.py:2054`).

**Order-status transition apply + the event co-write (ADR-004/008, INV-025/075):**
- `transition_order` — memory (`memory.py:1496`) vs sqlite (`sqlite.py:2377`): the NOOP short-circuit,
  the `order_transition` vs `order_fill_progress` branch, and the co-written routine ExecutionEvent
  (memory atomic block `memory.py:1566`; sqlite `_tx()` `sqlite.py:2452`).
- The evented-plan apply (timeout-quarantine/reconcile resolve): `_apply_order_evented_plan_unlocked`
  (`memory.py:1578`) vs `_apply_order_evented_plan_locked` (`sqlite.py:2477`) — order row + audit event
  + ExecutionEvent in one boundary.
- Read-flip projection: `get_order`/`_project_order_unlocked` (`memory.py:1471`) vs
  `get_order`/`_project_order_locked` (`sqlite.py:2351`, per-order `SELECT ... WHERE order_id=? ORDER BY
  sequence`).

**Manual flatten apply (ADR-002/003, INV-034/035/036/037/038, INV-060) — the atomicity hot spot:**
- `flatten_position` — memory (`memory.py:928`) vs sqlite (`sqlite.py:1624`). Both compute the plan from
  state read under one continuous lock hold. Compare the APPLY of `FLATTEN_SUPERSEDE_AND_CREATE`:
  memory runs supersede-cancel + supersede-expire + insert + approve + **dispatch** inside ONE
  `_atomic()` (`memory.py:1018`, with the nested dispatch `_dispatch_order_for_sell_intent_unlocked` at
  `memory.py:1066` re-entering `_atomic()`); sqlite uses **separate** `_tx()` blocks — supersede-cancel
  (`sqlite.py:1723`), supersede-expire (`sqlite.py:1755`), insert+approve (`sqlite.py:1765`), then
  `_dispatch_order_for_sell_intent_locked` opens its OWN `_tx()` (`sqlite.py:1582`). The deferral and
  override-consume paths (`memory.py:976`/`988`, `sqlite.py:1685`/`1696`) and the flat short-circuit are
  the other outcomes.
- The shared dispatch helper each flatten inlines: `_dispatch_order_for_sell_intent_unlocked`
  (`memory.py:842`) vs `_dispatch_order_for_sell_intent_locked` (`sqlite.py:1528`) — the X-002 self-heal
  reject branch (`memory.py:871`, `sqlite.py:1558`) and the create branch.

**Session close apply (INV-050) — the contrast case:**
- `close_session` — sqlite (`sqlite.py:3173`) applies the entire candidate-expire + BUY-cancel +
  sell-intent-expire + snapshot + session-close cascade in a **single** `_tx()` (`sqlite.py:3266`).
  Memory `close_session` (`memory.py:2105`) is the counterpart. Diff *why* close_session is one
  transaction while flatten is several.

**Control-flag / correlation apply (INV-061, INV-040/041):**
- Control setters route through `_apply_control_change_unlocked` (`memory.py:1905`) /
  `_apply_control_change_locked` (`sqlite.py:2924`); `set_kill_switch` (`memory.py:1976`,
  `sqlite.py:3020`).
- The single central event-write path that resolves `correlation_id` (INV-041, X-004): memory
  `_append_event_unlocked` (`memory.py:304`, reads `self._orders` at `memory.py:339`) vs sqlite
  `_insert_event` (`sqlite.py:831`, `SELECT sell_intent_id FROM orders` on the **same cursor** at
  `sqlite.py:859`). Note the two resolve over different visibility scopes (live dict vs same-tx cursor).

**Perf surface (sqlite; memory folds in RAM so these are sqlite-specific):**
- `list_orders` (`sqlite.py:2331`) projects each row via `_project_order_locked` (`sqlite.py:2349`) —
  one per-order event `SELECT` each.
- `list_positions` (`sqlite.py:2732`): `SELECT DISTINCT symbol …` then a per-symbol `_position_locked`
  fold (`sqlite.py:2738`).
- `_current_exposure_locked` (`sqlite.py:1850`): the same per-symbol fold **plus** `SELECT * FROM fills
  ORDER BY rowid` (`sqlite.py:1871`).
- `claim_order_for_submission` (`sqlite.py:2019`) and `create_order_for_candidate` (`sqlite.py:1916`)
  each load `SELECT * FROM execution_events WHERE event_type='fill'` to compute `quarantined`.
- `quarantined_symbols` itself (`app/events/projectors.py:141`) is O(symbols × events) over whatever
  event list the store hands it (nested loop `projectors.py:175`).
- `initialize` builds the indexes these reads lean on (`sqlite.py:393`–`424`).

## Probe checklist (find the parity divergence / non-atomic apply / perf cliff, or prove the two stores apply identically — symmetric challenges)
Grouped by named cluster. Every P0/P1 probe is answerable **dual-store**: build the state on a fresh
`InMemoryStateStore()` and a fresh `SqliteStateStore(tmp)` (the `any_store` fixture pattern), run the
same call sequence on each, and compare the observable result — the returned DTO, `get_execution_events()`,
`list_orders()`, `get_position()`. **Parity is the null hypothesis; a divergence is the finding.**

**PARITY (memory vs sqlite apply the same plan to the same state)**
1. **Whole-plan application.** For each of `append_fill`, `transition_order`, `claim_order_for_submission`,
   `flatten_position`, `close_session`, `create_order_for_sell_intent`: does each store apply **every**
   field the plan sets, and **every** co-written event, and dispatch on **every** `outcome` the planner can
   emit? Drive the same input through both stores and assert the two `get_execution_events()` streams are
   identical in **event_type order** AND **dedupe_key order** (normalizing store-local ids, as
   `tests/test_wo0007a_stage4_dual_store_parity.py` does). Find a call where the two stores emit a
   different event set/order or apply a different row change — or prove they apply identically across the
   outcome space.
2. **Fetch fidelity.** The planner is only as correct as the inputs the store feeds it. `prior_filled`,
   `is_duplicate`, `current_quantity`, `own_session`, `sell_reason`, `quarantined`, `trading_state`,
   `override_active` are each fetched **differently** in the two stores (`self._fills` sum vs `SUM(quantity)`;
   an in-RAM set-membership vs `SELECT 1`; a `next(...)` over `self._sessions` vs a `SELECT`). Construct a
   state where one store's fetch returns a value its sibling's fetch does not (e.g. a `source_fill_id`
   duplicate across a different `order_id`; a `prior_filled` that a partial fill left mid-transition;
   sessions that differ in row-order). Find a fetch that feeds the planner a different value in one store —
   or prove each pair computes the identical input for every reachable state.
3. **Read-model vs event-truth per store.** Both stores derive order status (`_project_order_*`) and
   position (`_position_*`) from the event log, but keep a co-written `orders.status`/`filled_quantity`
   column. Probe whether any store method decides on the **raw column** where its sibling decides on the
   **projection** (or vice-versa) — the claim gate reads the projection (`memory.py:1223`,
   `sqlite.py:1983`); does every other status-gated store branch (flatten's `active_order.status`,
   close_session's `WHERE status=…` SQL filters at `sqlite.py:3226`, `list_timeout_quarantined_orders`)?
   A store that gates on the stale column where truth is the log is the REV-0001 F-001 class. Find one, or
   show every safety-gating read is projection-sourced (or that the column is provably in sync at that
   point).

**ATOMICITY & LOCK (INV-050/051/052 — where the pure plan cannot help)**
4. **Multi-transaction apply (INV-050).** Enumerate every sqlite method that opens `_tx()` more than once
   OR calls a helper that opens its own `_tx()` (start from `flatten_position` — supersede/expire/insert/
   dispatch are four separate transactions, `sqlite.py:1723/1755/1765/1582`; the atlas discloses this as
   **REV-0006-F-001, a known item — confirm/expand, do not re-file as a fresh P0/P1**). Then look past it:
   is there a **different** method that splits an all-or-nothing plan across `_tx()` boundaries, or that
   splits it where its memory twin uses ONE `_atomic()`? For any you find, build the half-committed state
   (apply the first write, skip the second) and show a durable inconsistency the memory store cannot reach —
   or prove every *other* method's writes commit in a single transaction. Contrast against `close_session`
   (`sqlite.py:3266`), which does the whole cascade in one `_tx()`.
5. **Nestable `_atomic()` correctness (INV-050, memory).** `_atomic()` (`memory.py:248`) snapshots on enter
   and restores on exception, and nests (flatten's outer block at `memory.py:1018` contains the dispatch's
   inner block at `memory.py:887`). Probe the nesting: if an **inner** block raises and is **caught** above
   the outer block, does the outer restore-on-exit still see a consistent snapshot — or can a caught-inner /
   partial-outer sequence leave a half-applied mutation the sqlite `ROLLBACK` would have fully reverted?
   Find an exception-path divergence, or prove the snapshot/restore is exception-equivalent to a SQL
   transaction for every nesting the code reaches.
6. **Lock reentrancy (INV-051).** `asyncio.Lock` is not reentrant. Find any path where a public
   lock-acquiring store method (`async with self._lock`) reaches — directly or transitively — a second
   public lock-acquiring method on the same store, instead of an `*_unlocked`/`*_locked` helper (probe
   `flatten_position` → dispatch, `create_order_for_sell_intent` → dispatch, `close_session`, the
   emergency-override paths). One real reentrant acquire hangs the whole process. Find it, or prove every
   compositional call goes through the non-acquiring helper variant in both stores.
7. **No broker/network call under the lock (INV-052).** Confirm that no store method performs a broker or
   network call while holding `self._lock` — the stores are supposed to touch only local state, with the
   `cancel_open_buys` broker round-trip pushed to a route-level pre-step (INV-037). Find a store method
   that reaches an `await` to any IO boundary under the lock, or prove every under-lock body is local-only
   in both stores.

**RED-TEAM / SAFETY (a store that diverges from planner intent or from its sibling)**
8. **Flatten supersede-cancel vs a possibly-live order.** In the SUPERSEDE_AND_CREATE apply, the store
   UPDATEs the superseded order to CANCELED and co-writes its CANCELED ExecutionEvent
   (`sqlite.py:1724`/`memory.py:1036`). Confirm the store only ever reaches this apply for an order the
   planner deemed local/never-live (a CREATED `PROTECTION_FLOOR`), and never blind-cancels a possibly-live
   one (ADR-002). Since the planner's deferral gate is REV-0006's, your angle is: does the store feed the
   planner the **true** `active_order` (the projected status, under the lock) so the planner's decision is
   made on truth — and does the store apply the cancel to the row the planner named, not a stale copy?
   Find a store-side mis-feed or mis-apply, or prove the applied cancel always targets the planner's
   never-live order.
9. **Fill quantity single-sourced to `append_fill`.** Safety-core #8/#9 / INV-001. Show that in **both**
   stores, only `append_fill`'s FILL_APPEND branch writes a `fill` row and an `ExecutionEventType.FILL`
   event; no `transition_order`, evented-plan, flatten, or close-session apply path emits a FILL event or
   touches the fills table. Then the sibling check: does either store's `filled_quantity` column write
   (`transition_order`) ever disagree with that store's FILL-event fold (INV-004) in a way the *other*
   store doesn't — e.g. one store lets `transition_order(filled_quantity=…)` set a value the fill sum
   contradicts while the other rejects it? Find a divergence, or prove position-quantity mutation is
   single-sourced and identical across stores.
10. **Duplicate/overfill ordering under each store's fetch (INV-002/003, ADR-001).** The planner
    short-circuits a duplicate before the overfill check, but that only holds if the store's `is_duplicate`
    fetch is correct. Probe the sqlite dedup (`SELECT 1 … order_id=? AND source_fill_id=?`,
    `sqlite.py:2616`, backed by the partial unique index `idx_fills_order_source`, `sqlite.py:407`) vs the
    memory `(order_id, source_fill_id)` set: replay the same overfilling fill twice on both stores and
    confirm the second is recorded as duplicate (not a second short) identically. Find a store where a
    replayed overfill double-records or is silently rejected, or prove both dedup identically.

**PERFORMANCE (sqlite hot paths; memory is RAM-bounded)**
11. **N+1 and unbounded loads.** For `list_orders` (`sqlite.py:2349`), `list_positions` (`sqlite.py:2738`),
    `_current_exposure_locked` (`sqlite.py:1850`), and the per-claim/per-create `quarantined` load
    (`sqlite.py:2019`, `sqlite.py:1916`): quantify the query/row growth as orders, symbols, fills, and
    session length grow. Which run on a hot path (every submit sweep tick calls the claim gate; every
    reconcile computes exposure)? Is `quarantined_symbols` (`projectors.py:141`, O(symbols × events)) re-run
    from a full `execution_events` fill-scan on **each** claim? Build a session with many fills/orders,
    measure (row counts or timing), and report the growth curve — or show each read is index-bounded and
    O(result) at beta's single-user scale. (Perf findings are P2 unless a load is unbounded enough to
    threaten the monitoring-loop budget, in which case argue the severity.) Note the reviewer should weigh
    these against the code's own "negligible at beta's single-user scale" claims — decide whether that
    holds for a *session-length-accumulating* log, not just a small watchlist.

## Independent-oracle hook (check code against the STATEMENT, not the test — X-002)
Check the CODE against the invariant **statements** in `docs/INVARIANTS.md` and the `CLAUDE.md` safety
core, **not** against the pinning tests. Per X-002, a test can assert the very bug it should catch (the
on-the-record case: an ADR required a self-heal, the code didn't do it, and the test pinned the buggy
`APPROVED` result as correct — now guarded by INV-033). **That X-002 defect lives in *this* container's
apply path:** the self-heal is applied by `_dispatch_order_for_sell_intent_unlocked`/`_locked`
(`memory.py:871`, `sqlite.py:1558`). Probe the *store's applied behavior* against INV-033's statement
(intent atomically `approved → expired` **in the same operation that raises**), not against
`tests/test_phase7_sell_intents.py` — and confirm both stores apply that self-heal in one atomicity
boundary (memory `_atomic()` at `memory.py:871`; sqlite `_tx()` at `sqlite.py:1558`).

In scope for this packet (verified present in `docs/INVARIANTS.md` with the meaning cited), framed as the
**store's obligation to apply** what the planner decides:
- **Atomicity/lock:** INV-050 (every multi-row apply is atomic — the store's `_atomic()`/`_tx()` boundary
  must bundle the row change and its co-written events all-or-nothing), INV-051 (the `asyncio.Lock` is
  never reentrant — composition via `*_unlocked`/`*_locked`), INV-052 (no broker/network call under the
  lock).
- **Fill/position apply:** safety-core #8 (submitted ≠ filled), safety-core #9 (only fill events change
  quantity), INV-001 (position derived from the FILL fold), INV-002 (overfill quarantined, never a silent
  short), INV-003 (duplicate fill idempotent), INV-004 (`filled_quantity` == fill sum).
- **Claim/lifecycle apply:** INV-020 (`SUBMITTED` needs a real broker id), INV-021 (`claim_...` is the sole
  CREATED→SUBMITTING apply), INV-025 (same-status transition applies as a true no-op), INV-075 (the store
  reads order status by projecting the append-ordered log, and every status writer co-writes its
  ExecutionEvent in the same boundary).
- **Flatten apply:** INV-034/035/036/037/038 (the store applies the plan's supersede/defer/create outcome —
  never double-exits a live order, never blind-cancels, never returns a stranded intent as "existing").
- **Sell-intent apply:** INV-030/031/032/033 (single-flight dedup and the self-heal are applied under the
  one continuous lock hold).
- **Correlation/control apply:** INV-040/041 (both stores resolve `correlation_id` in the one central
  event-write path), INV-060 (kill-switch carve-out applied only via the claim gate), INV-061 (control
  setters apply only a real `bool`).

ADRs in scope (verified relevant, as the **store applies** them): **ADR-004** (event-log-as-truth — every
status/position read the store returns is a projection of a co-written `ExecutionEvent`; check
`_project_order_*` and `_position_*` and the co-write in every apply), **ADR-008** (order-status provenance
— the store's projection folds by sequence, and the claim-gate `assert` pins the co-write invariant),
**ADR-002** (the store never applies a blind-cancel/blind-resubmit to a possibly-live order — flatten's
supersede path, the evented quarantine-resolve apply), **ADR-003** (the store applies the Halted-deny /
override-consume flatten outcomes), **ADR-001** (the store applies the overfill quarantine via `append_fill`
and holds a quarantined BUY at the claim gate).

Also check the spine `INV-1..9` in `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5` (⚠ a *separate* numbering
from the INV-0xx registry) where the store's fill/position apply cites one (e.g. "only a fill moves
quantity", the position firewall).

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro plus its pasted output**, and — because this is the
  parity packet — driven **dual-store** wherever the claim is about apply/divergence: run the same call
  sequence on a fresh `InMemoryStateStore()` and a fresh `SqliteStateStore(tmp_path/"x.db")` (call
  `await store.initialize()` yourself, as the `any_store` fixture requires) and paste both stores'
  observable results side by side. For an **atomicity** claim, simulate the crash window (apply the first
  write, then raise/skip the second, or kill between `_tx()` commits) and show the durable state the sqlite
  store is left in versus the memory store. A finding with no repro is marked **"unverified concern"** and
  **cannot gate**.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran** (the dual-store
  script and the identical results you got back). A bare "looks fine / LGTM" with no probe log is a
  **rejected review** for that area — show your work on the parity that *holds*, too.
- **Known items — confirm/expand, do NOT re-file as fresh P0/P1** (Atlas "Wave-1 VERIFIED findings"):
  **REV-0006-F-001** (sqlite `flatten_position` splits into 4 transactions; a crash strands an
  approved-no-order intent — memory is atomic) and **ENG-001** (the `monitoring.py` kill-switch-cache race)
  are already dispositioned and in remediation. A genuinely **distinct** store-impl defect — a *different*
  method with a split transaction, a *different* parity divergence, a lock-held broker call, a stale-column
  safety gate — IS wanted; report it.
- If the code contradicts the Atlas, a docstring's own claim (e.g. memory `_atomic()` "Mirrors
  `SqliteStateStore`'s BEGIN/COMMIT/ROLLBACK", or flatten's "never a silently-blocked symbol"), or a
  disclosed known-item, that disagreement is itself a finding (≥ P1) — the map/comment is wrong.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** (`work/review/REV-0009/`)
and fill it: the findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters |
Proposed fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a plain statement of
whether **G-C's gate may clear** (do the two concrete stores apply the planners' plans **atomically** and
at **parity** with each other, such that the durable sqlite engine and the IO-free memory engine are
behaviorally interchangeable?). State plainly anything you could not verify. Do **not** edit `request.md`;
do **not** push code fixes.
