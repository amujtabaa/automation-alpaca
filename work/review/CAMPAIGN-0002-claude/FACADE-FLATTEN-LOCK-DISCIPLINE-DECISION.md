# Decision memo: `create_exit` flatten lock-discipline (surfaced by the I.6 third-party review)

> **STATUS: DECISION FOR THE OPERATOR. No code changed.** The operator asked to "address" this
> finding. Addressing it correctly turned out to mean *not* patching it: two independent deep
> reviews confirmed the obvious fix is a safety **regression**, the finding itself is **non-exposure
> (safe as-is)**, and the two reviews then **disagreed on the right alternative** — so the real fix
> is a behavior/architecture decision on a human-gated flatten surface, which is the operator's to
> make, not the implementer's. This memo lays out the options and a recommendation.

## The finding (recap)

`app/facade/store_backed.py::create_exit` (the sole handler of `POST /positions/{symbol}/flatten`)
reads the position **outside** the store lock and short-circuits on it before calling the store:

```python
position = await self._store.get_position(key)   # read, OUTSIDE the store lock
if position.quantity <= 0:
    raise ConflictError("no open ... position to flatten")   # (A) early return
await cancel_open_buys(...)                        # broker call — by contract NOT under the store lock
result = await self._store.flatten_position(...)   # (B) the atomic, locked decision
if result.outcome == FLATTEN_FLAT:
    raise ConflictError("no open ... position to flatten")
```

The `(A)` pre-check is a check-then-act on a stale read, one lock-acquisition removed from the
store's own authoritative decision. It is **pre-existing base behavior** (zero diff across
`22617f4`, both R2 freeze branches, and current HEAD — this campaign's work did not introduce it).

## What the two independent reviews established

Both reviews read the actual code; the second was briefed to reason from first principles and told
nothing of the first's conclusion.

**1. The finding is NOT an exposure — the status quo is safe.** In the window it targets ("Repro 2":
position genuinely 0, a stale envelope still lingering), the `(A)` pre-check returns a **correct**
409 (there is nothing to flatten). The only thing skipped is the store-internal ADR-010 envelope-FSM
cleanup (`_cancel_symbol_envelopes_unlocked`, `memory.py:2081-2111`) — which walks the store's own
`_envelopes` records through `ACTIVE→FROZEN→CANCELLED`, **never a broker/venue action** — and it is
reconciled on the next monitoring tick regardless. The genuinely dangerous case (an envelope child
*live at the venue* while flat) is caught by `FlattenBlockedError` ("position is flat but envelope
order may still be live", `memory.py:2581` / `sqlite.py:3855`) in **both** the current and any
proposed path. So Window 1 is bookkeeping latency, not exposure.

**2. The obvious fix is a REGRESSION — do NOT apply it.** The tempting patch — guard the buy-cancel
(`if position.quantity > 0: await cancel_open_buys(...)`) and always call `flatten_position` — was
independently judged a net safety **regression** by both reviews. In a second window (a BUY fill
lands in the gap: the stale read is 0 but the locked position is actually `>0`, with an open BUY
remainder), the guard **skips** `cancel_open_buys`, then `flatten_position` mints a `MANUAL_FLATTEN`
sell with the open BUY still fully live at the venue — the exact **self-cross / re-grow exposure**
`cancel_open_buys`-before-flatten exists to prevent (its own docstring, `monitoring.py:250-258`).
`flatten_position`'s contract (`app/store/base.py:672-679`) explicitly requires the caller to cancel
buys first. Introducing a new (even low-probability) exposure window to fix a non-exposure tidiness
issue is backwards on a "safety outranks velocity" surface.

**3. There is a latent NON-exposure defect in the status quo worth naming.** In that same
buy-fill-in-the-gap window, today's `(A)` pre-check reads 0 and returns a **spurious 409** — the
operator's flatten command is silently dropped while they actually hold shares, and they are told
"no position." That is a false-flat / dropped-exit **correctness** defect (not an exposure; the
position stays protected by the monitoring loop), and it is extremely rare (a fill landing in the
sub-millisecond gap between two lock acquisitions, plus an open buy, plus a human clicking flatten in
that instant). It is a reason the finding is not *zero*-cost to leave, but it is not dangerous.

## Where the two reviews DISAGREE (why this is the operator's call)

They diverge on the "clean" fix:

- **Review 2 (adjudicator)** recommends calling `cancel_open_buys` **unconditionally** (drop both the
  `(A)` early return and the `>0` guard), then always call `flatten_position`. Rationale:
  `cancel_open_buys` does its own fresh `store.list_orders()` (`monitoring.py:260`), is idempotent,
  and no-ops when there are no open buys — so it doesn't need the stale read at all. This closes
  Window 1, closes Window 2 (buy is cancelled first → no self-cross), and fixes the dropped-exit.
  Its only behavior change: on a *genuinely* flat symbol carrying an unrelated pending BUY, that buy
  now gets cancelled — which the adjudicator judges bounded and in-scope for a human "flatten SYMBOL".
- **Review 1 (de-risk)** explicitly warned *against* the unconditional variant: it "would cancel an
  unrelated resting BUY on every genuinely-flat flatten (a more frequent, more surprising,
  automated-cancel-surface mutation) — strictly worse."

Both are defensible, and they contradict each other. Plus a wrinkle neither fully weighed: under the
unconditional variant, a flatten of a genuinely-flat-symbol-with-an-open-buy returns a **409** ("no
position") *while having cancelled the buy* — a side effect not reflected in the error response. This
is a genuine **product/UX + architecture decision** about what "flatten SYMBOL" should do to a
pending BUY on a flat position — on a **human-gated** surface — not a mechanical bug with one right
answer.

## Options

| # | Option | Closes finding? | Cost / risk | Needs |
|---|---|---|---|---|
| 0 | **Leave as-is** | No (but it's safe) | Retains the lock-discipline smell + the rare false-409 dropped-exit. Both non-exposure. | Nothing (record this memo) |
| A | **Unconditional `cancel_open_buys` + always flatten** (Review 2's fix) | Yes (both windows + dropped-exit) | Changes "flatten a flat symbol" to cancel a stray unrelated pending BUY; 409-with-a-side-effect UX wrinkle | Product sign-off (behavior change on a gated surface) + tests |
| B | **Atomic redesign**: fold open-buy detection into `flatten_position` under the store lock (it blocks/signals rather than relying on caller ordering), removing the facade check-then-act entirely | Yes, cleanly and permanently | Larger change; touches the store's flatten decision | Scoped WO + independent cross-model review (human-gated flatten surface, per CLAUDE.md) |

## Recommendation

**Do not apply the naive guarded patch (confirmed regression).** The finding is safe as-is, so there
is no urgency. My recommendation, in priority order:

1. **Preferred: Option B** — the atomic redesign is the only fix with no behavioral trade-off and no
   residual window; it removes the irreducibility at its root (the facade stops trying to make a
   flat/blocked decision on a stale read). Queue it as its own small WO with independent review,
   since it changes the store's human-gated flatten decision.
2. **Acceptable lighter path: Option A** — if the team wants the dropped-exit + lock-discipline
   closed sooner and is comfortable ratifying "flatten SYMBOL cancels a pending BUY on that symbol"
   as intended semantics. This needs an explicit product decision, not an implementer's guess.
3. **Also fine: Option 0** — leave it; it is safe, and the defects it carries are rare and
   non-exposure.

I am not choosing between A / B / 0 unilaterally: it is a behavior decision on a human-gated surface
where two independent expert reviews disagreed. **Tell me which option you want and I'll implement it
(test-first, and for B, routed through independent review).**

## Cross-reference

The finding's discovery and the non-blocking-verdict-still-holds conclusion for the R2/I.6 "Repro 2"
question are recorded in `RATIFICATION-part-a.md` (2026-07-16 addendum, under I.6). This memo is the
follow-through on that addendum's "flagged for the operator's own sequencing decision."
