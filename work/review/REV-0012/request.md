---
type: Review Request
rev_id: REV-0012
campaign_id: CAMPAIGN-0001
packet: MARKETDATA
container_group: G-H (market-data)
packet_lens: adversarial red-team — market-data validity gating (staleness / NaN / negative / zero / out-of-range)
status: AWAITING_REVIEW
targets: [G-H-marketdata]
# Market data is NOT itself a human-gated surface. But it FEEDS the gated ones —
# it prices a candidate (order-submission), decides a protective exit
# (order-submission), and supplies a MARKET fill-price fallback. The linkage IS
# the review: a bad datum here becomes a bad sizing/submission decision downstream.
human_gated_surfaces: []   # not itself gated — feeds order-submission / sizing (see "Linkage")
commit_range: b600101      # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12           # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
# There is NO dedicated INV-0xx in docs/INVARIANTS.md for market-data validity /
# staleness — the oracle is the CLAUDE.md safety rail + the Spine §5 principles.
# That registry gap is itself in scope (INVARIANTS.md preamble, X-003).
invariants_in_scope: [safety-core "invalid market data must halt/quarantine — never drive sizing/submission", INV-070, INV-072, INV-001, safety-core #9, "spine §5 fail-fast-on-bad-data", "spine §5 component-health-FSM (DEGRADED on stale data)", "spine §12 fail-fast on NaN/stale/halted"]
adr_in_scope: [ADR-006, ADR-002]   # ADR-006 = SDK-confinement (2nd site); ADR-002 = the withhold-not-guess pattern the fill fallback mirrors
created: 2026-07-10
---

# Review Request REV-0012 — Market data, adversarial red-team (validity gating)

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes no correctness claims — code beats the atlas, and if they disagree
that is itself a finding). You have the full repo at the frozen SHA `b600101`.

## Scope boundary — follow the bug anywhere
**This defines your deep-coverage responsibility, not a fence.** Your container is the market-data
service. But market data is not consumed *inside* the container — its whole reason to exist is to
feed the **Feature / Strategy / Protection / submission** layers, which live in other packets. You
**must** follow every datum across that boundary to the point where it sizes a candidate, decides a
protective exit, or prices an order: a defect you find in `app/strategy.py`, `app/protection.py`,
`app/features.py`, `app/policy.py`, or `app/monitoring.py` while chasing a market-data value is
**your finding**, reported at its true location (Atlas "Your scope — follow the bug anywhere"). The
only thing your container fences *in* is responsibility: you cannot mark market-data validity
"reviewed" by punting the consumer gates to REV-0010/0012/0014 — the gate is only real if it holds
at **every** consumer, so proving that is your job.

**Your container (probe exhaustively; your verdict covers these — ~710 LOC):**
- `app/marketdata/service.py` (92) — the `MarketDataService` ABC and the `MarketSnapshot` model
  (the datum whose validity is the whole subject).
- `app/marketdata/alpaca_stream.py` (435) — the real Alpaca feed and **the 2nd of the two SDK sites**
  (`import alpaca`, INV-070). Ingestion, seeding, the staleness clock, the day-boundary reseed.
- `app/marketdata/fake.py` (118) — the IO-free feed; **your repro instrument** (`set_snapshot(...)`
  builds an arbitrary — stale / NaN / negative / crossed — snapshot in one call).
- `app/marketdata/factory.py` (65) — credential-safe, lazy-import composition helper.

**Owned by other packets, but on the critical path — do not assume their gate holds (re-derive it):**
- Feature/Strategy/Protection gates → `app/features.py`, `app/strategy.py`, `app/protection.py`,
  `app/policy.py` (REV-0010 KERNEL / REV-0014 STRATEGY).
- Submission / fill-fallback consumers → `app/monitoring.py` (REV-0005 ENGINE, already dispositioned —
  but its *market-data* reads are yours to probe).
- The facade read surface → `app/facade/store_backed.py` (REV-0013 FACADE-API).

## The invariant you are probing (the oracle — check the CODE against THIS)
> **Invalid market data (stale / NaN / negative / out-of-range) must HALT or QUARANTINE the flow —
> never drive sizing or submission.** (`CLAUDE.md` safety rails.)

Reinforced by the Spine spec, which is the numbered oracle here because **no `INV-0xx` in
`docs/INVARIANTS.md` pins market-data validity** (the registry has INV-070/072 for the SDK/venue
boundary, nothing for staleness or finiteness — flag that gap, see X-003):
- `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` §5, "Fail-fast on bad data" (lines 43-44): *"NaN/negative/
  out-of-range price/qty/timestamp halts or quarantines — never flows into a sizing or submission
  decision."*
- §5, "Component health FSM" (lines 47-48): *"DEGRADED (stream flap, stale data) drives the kill
  switch to `Reducing`."*
- §12 (line 329): *"fail-fast on NaN/**stale/halted** data."*

**Linkage (why a market-data bug is a submission bug):** a snapshot feeds three
human-gated-surface-adjacent decisions — (a) `strategy.evaluate` sets a candidate's
`suggested_limit_price` (`app/strategy.py:126`); (b) `protection.floor_breach_reason` decides
*whether* to fire a `PROTECTION_FLOOR` exit and `protective_limit_price` sets its limit
(`app/protection.py:126`, `:175`); (c) `_snapshot_fill_fallback` supplies a MARKET order's audit
fill price (`app/monitoring.py:1416`). Position **quantity** is firewalled from market data (it derives
only from fills — INV-001 / safety-core #9; a protective exit's quantity is `position.quantity`,
`app/protection.py:79`), so trace whether market data can corrupt a **price / a go-no-go decision**,
not a quantity.

## The design under test (know it before you probe it)
The feed does **no validation at ingest.** `alpaca_stream.py` stores whatever the SDK hands it —
`_seed_from_snapshot` (`:111`) copies raw `latest_trade.price` / `daily_bar.volume` / etc., and
`_on_trade` (`:389`) / `_on_quote` (`:424`) write raw `trade.price` / `quote.bid_price` — **no
`finite`/`>0`/range check anywhere in the module** (confirmed: `grep -n 'finite\|isfinite\|<= 0'
app/marketdata/alpaca_stream.py` matches only a docstring). The entire safety contract therefore
rests on **every consumer re-gating** through the single shared guard
`app.policy.finite_number_reason` (`app/policy.py:186`, rejects bool / non-numeric / NaN / ±Inf),
surfaced to the market-data layer as `market_data_field_reason` (`:159`) and `_finite`
(`app/features.py:22`). Your verdict is essentially: **is that consumer-side gate complete and
correct at every site, for every failure mode (stale / None / NaN / ±Inf / negative / zero /
crossed)?**

Staleness is a **separate, feed-wide** signal, not part of the numeric gate: `_is_stale_locked`
(`app/marketdata/alpaca_stream.py:311`) computes `reference = self._last_message_at or
self._run_started_at` (`:314`) and `get_snapshot`/`list_snapshots` stamp that one bool onto every
snapshot (`:234`, `:238-239`). `_last_message_at` is advanced by **any** trade or quote for **any**
symbol (`_on_trade:392`, `_on_quote:426`; declared feed-wide at `:158`).

## Where to look (neutral anchors — where to start, not what to conclude)
- **The feed-wide staleness clock vs the per-symbol price.** `_last_message_at` (`:158`, `:392`,
  `:426`) and `_is_stale_locked` (`:311-315`). Map what `snapshot.stale == False` actually
  *guarantees* about a *given* symbol's `last_price`. Then note that **no consumer reads
  `snapshot.updated_at`** to check a per-symbol age (verified: `grep -n updated_at` over the
  consumers finds only display passthrough at `store_backed.py:251` and the stale-event payload at
  `strategy_loop.py:281`).
- **The consumer gates** (the coverage set — prove each, or breach one):
  `features.pct_move/spread/spread_pct` (`app/features.py:52/65/73`),
  `strategy.evaluate` (stale `:89`; the non-finite sweep over *present* fields `:101-109`; the
  numeric gates `:111-119`; `suggested_limit_price` `:126`),
  `protection.floor_breach_reason` (`:103-125`) and `protective_limit_price` (`:157-178`),
  `monitoring._effective_submit_order` (`:158-182`, stale→un-priceable `:174`) and
  `monitoring._snapshot_fill_fallback` (`:193-206`),
  `facade.store_backed.get_protection_view` (`:475-489`).
- **The 2nd SDK site.** The `import alpaca` block (`alpaca_stream.py:66-71`), the lazy import in the
  factory (`factory.py:57`), paper-cred gating (`factory.py:40`, `:51-55`), and `run`/`stop`
  (`:241`/`:271`). This module owns a live websocket — confirm it never reaches an order/trading API
  and never a non-paper endpoint.
- **The day-boundary reseed** (`_reseed_symbol:340-387`): `volume=volume` is written
  *unconditionally* (`:386`, even when the REST reseed returns `None`), while `prev_close` is kept on
  `None` (`:384`). Trace what a reseed can do to the value the min-volume gate later reads.
- **The WO-0014 fractional-volume fix** (`_on_trade:420`, `(existing.volume or 0) + trade.size`, no
  `int()`): the type is float end-to-end (`MarketSnapshot.volume:46`, `MarketSnapshotView:84`).

## Probe checklist (find the failure, or prove it cannot exist — symmetric challenges)

**RED-TEAM / VALIDITY (primary)**
1. **Feed-wide staleness vs a per-symbol-stale price.** `snapshot.stale` is set from a feed-wide
   clock that any symbol's tick resets. Construct the case where symbol `X` stops updating (a trading
   halt, a delist, or a silently-dropped per-symbol subscription) while symbol `Y` keeps the feed
   alive — so `X`'s snapshot has an arbitrarily old `updated_at` but `stale == False` — and show that
   old `last_price` drives a real decision at a consumer: a `floor_breach_reason` go/no-go
   (`app/protection.py:115` passes because `stale` is False), an `_effective_submit_order`
   limit price (`app/monitoring.py:174`), or a `strategy.evaluate` proposal (`app/strategy.py:89`).
   **OR** prove per-symbol freshness is adequately gated at every consumer (it is not gated by
   `stale`; is it gated another way?). This is the load-bearing probe — the Spine explicitly names
   **"halted data"** as a fail-fast case (§12:329), and no code checks `updated_at`.
2. **Boundary-vs-consumer completeness (the coverage probe you own).** The ingest boundary stores raw
   SDK values unvalidated. Enumerate **every** consumer that reads `last_price / bid / ask / volume /
   prev_close`, and for each prove a `NaN` / `±Inf` / negative / zero / crossed value cannot reach a
   sizing or submission decision — **or** find one site (present, or a plausibly-next one the
   structure invites) that reads a raw field before the gate. Pay attention to fields a given
   consumer *doesn't* run through the finite sweep (e.g. does every path that touches `bid`/`ask`
   go through `finite_number_reason`, or only the ones that call `spread()`?).
3. **Negative / zero / out-of-range at each consumer.** Using `FakeMarketDataFeed.set_snapshot`,
   build snapshots with `last_price = -5`, `prev_close = 0`, `bid = -1`, `volume = inf`, a crossed
   quote (`bid > ask`), and a `0.0` price, and drive each consumer: candidate `suggested_limit_price`,
   `floor_breach_reason`, `protective_limit_price`, and the MARKET `_snapshot_fill_fallback`. Show
   each rejects/holds — **or** find one that emits an order intent, a non-positive/`inf` limit price,
   or a spurious min-volume pass. (Beta is long-only: a large *negative* `pct_move` must never
   propose — `app/strategy.py:112`.)

**SDK-SITE / PAPER-SAFETY (secondary)**
4. **The 2nd SDK site is confined and paper-only.** Prove `import alpaca` is confined to
   `alpaca_stream.py` within this package (INV-070), that the factory imports it lazily so
   `from app.marketdata import MarketDataService` never drags the SDK in (INV-070 transitive /
   ADR-006 Finding 1), that it uses the *paper* credentials and touches **only** market-data
   endpoints (no `TradingClient`, no order submission), and that a missing-credential path degrades
   to the fake, never to an unauthenticated live call. **OR** find a venue-coupling / non-paper leak.
   Check against the INV-070 **statement** and ADR-006, not the pinning import test (X-002).

**WO-0014 / FRACTIONAL (verify — do NOT re-file F-003)**
5. **Fractional volume, end-to-end and consistently gated.** WO-0014 (commit `a7b012d`) already fixed
   the `int()` truncation (REV-0002 F-003) — **do not re-file it.** Instead verify the *distinct*
   question: with volume now float, is it still correctly gated? Confirm no residual `int()`/`round()`
   of `volume`/`trade.size`, that a fractional volume round-trips the API view, and that a fractional
   / negative / `NaN` volume is still caught at the **min-volume** consumer (`app/strategy.py:115` —
   note it is the numeric-sweep at `:101-109`, not the `< min_volume` compare, that must catch a
   `NaN`). Then probe `_reseed_symbol`'s unconditional `volume=volume` (`:386`) and keep-`prev_close`-
   on-`None` (`:384`): can a day-boundary reseed leave the min-volume gate reading a wrong baseline?

**STALENESS EDGE CASES (secondary)**
6. **`stale == False` before the feed is live.** `_is_feed_stale(None, ...)` returns `False`
   (`:93-95`), and `_run_started_at` is `None` until `run()` executes (`:159`, `:243`). A snapshot
   REST-seeded by `subscribe()` (`:184-201`) before `run()` starts is therefore `stale == False`
   however old it gets. Show whether a consumer can size on such a pre-`run()` seed that has aged past
   the threshold — or prove the window is closed in the real wiring (`app/main.py`). Separately, the
   module docstring (`:36-54`) claims a **bad API key** produces a silent retry storm but still
   surfaces staleness (no message ⇒ `_last_message_at` never advances ⇒ every snapshot `stale`).
   Verify that claim against `_is_stale_locked`; don't take the docstring on faith.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Probe the **code** against the safety-rail statement above and the Spine §5/§12 principles, plus the
INV-070/072 **statements** in `docs/INVARIANTS.md`. **Do not** validate against the pinning tests.
The live X-002 trap in this container: `tests/test_alpaca_marketdata_stream.py::
test_stale_flag_applies_uniformly_to_every_snapshot` (line 244) and its sibling
`test_tick_updates_feed_wide_staleness_clock` (line 363) **assert the feed-wide behavior as
correct** — "applies to every symbol alike, since staleness is feed-wide, not per-symbol" (test
comment, `:254-256`). That is provenance of the *implemented* behavior, **not** proof it satisfies
"stale/halted data must never drive sizing." Re-derive what must hold from the invariant text and
Probe 1 directly; a test that pins the feed-wide flag cannot answer whether a per-symbol-stale price
is safe to trade on. Likewise, the module's own docstring justifications
(`alpaca_stream.py:26-54`, `:154-157`, `:355-374`) are the author's reasoning, not the oracle — a
disclosed "accepted tradeoff" is still a finding if it lets bad data drive a decision.

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro** (a probe script, a `pytest -k`, or a shell
  command) **plus its pasted output**. The pure consumers (`features`/`strategy`/`protection`/
  `policy`) and `FakeMarketDataFeed` make repros cheap and IO-free — a finding with no repro is
  marked **"unverified concern"** and **cannot gate**. Where a finding exercises a store path
  (`monitoring`/`facade`), show it **dual-store** (memory + sqlite); a pure-function finding needs no
  store.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran.** A bare
  "looks fine / LGTM" with no probe log is a **rejected review** for that area — the consumer gates
  look thorough, so show your work proving each *actually* holds (Probe 2 especially).
- If the code contradicts the Atlas, a disclosed known-item, or a module docstring's own claim, that
  disagreement is itself a finding (≥ P1).

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** and fill it: the
findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters | Proposed fix`),
an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and whether **G-H's foundation gate
may clear.** State plainly anything you could not verify (e.g. real Alpaca feed timing / a live
per-symbol halt you can't exercise without an account). Do **not** edit `request.md`; do **not** push
code fixes.
