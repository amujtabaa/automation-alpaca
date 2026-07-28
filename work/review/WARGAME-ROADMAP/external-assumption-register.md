# External-Assumption Register (XA) — draft

- **Status:** PROPOSAL, unratified. Nothing here binds until the operator ratifies it.
- **Origin:** WARGAME-ROADMAP hazard 2, identified in the kickoff as the highest-novelty artifact.
- **Scope:** every belief this codebase holds about **external reality** — Alpaca REST semantics, order
  state machine, `client_order_id` semantics, market calendar, clock/timezone, data feed, rate limits.
  Beliefs about our own code are invariants (`docs/INVARIANTS.md`), not register rows.
- **Base:** `14ff12f`. Every anchor below was verified against code by the planning seat unless the row
  says otherwise.

## Why this is not a table

A markdown table of Alpaca beliefs is **S-4 by construction** — not machine-consumed, unable to fail,
rots against the surface it guards. This repo already ran the experiment: REV-0011 recorded exactly this
obligation as prose in a closed disposition — *"Beta pre-flight (not a code change): confirm with the
live Alpaca paper venue that a duplicate `client_order_id` is rejected for all order states incl.
post-fill (the one external assumption UC-001's safety rests on)"*
(`work/review/REV-0011/disposition.md:42-45`). It was never run. Eighteen days and a full migration
later the belief is still unprobed, and two fail-open branches now depend on it.

**A second table will do what the first sentence did.** The register earns its place only as a
**keyed artifact the code points at**, joined by a checker:

1. Every row has a stable id `XA-NN` and at least one `file:line` anchor.
2. Every classification branch in `app/broker/` that keys on an external fact — an HTTP status
   comparison, an error-message substring test, a completeness assumption about a venue response —
   carries a `# XA-NN` marker naming the row it depends on.
3. A checker in the `.ai-os/scripts/` family joins the two directions and **fails the build** on either
   half: a branch with no id, or an id whose anchor no longer resolves.
4. The negative fixture is one committed module adding an unregistered `status_code` branch, asserted
   RED. This lives under `tests/` — **not** `.ai-os/scripts/tests/`, which `pyproject.toml:5`
   (`testpaths = ["tests"]`) excludes from every pytest invocation in the repo.

That satisfies meta-law (1) machine-consumed, (3) failure-capable, (4) negative fixture, (5) current —
the join is recomputed against the guarded file on every push.

**What it cannot satisfy is (2), semantic completeness, and this must be stated rather than papered
over.** A register row proves a belief is *named*; nothing in-repo proves it is *true*. The
`verified` column is a data field, not a control, until a credentialed paper-venue probe exists and its
output is committed as a fixture.

## The decision this register forces (operator input required)

**May any credentialed live-paper probe run in this program?**

- **If yes** — the `verified` column becomes real, probes are authored per row, their recorded output is
  committed as fixtures, and the promotion gates in `phase-gate-ADRs.md` can require a verified bit.
- **If no** — the column must be renamed `unverifiable-in-beta` and every `ASSUMED` row stays `ASSUMED`
  permanently. **That is a legitimate answer.** But it must be ratified explicitly, because it changes
  what the beta→shadow gate can honestly claim, and because the seven `CONTRADICTED` rows below are then
  the *only* rows actionable without venue access.

This decision is not defaultable. Defaulting it is how REV-0011's sentence died.

## Register

`class`: **DOC** traceable to Alpaca documentation · **MOCK-ONLY** encoded in our mock/sim, never checked
against the venue · **ASSUMED** nothing anywhere states it · **CONTRADICTED** something in the repo
already disputes it. Ordered by blast radius.

| id | assumption (falsifiable) | relied on at | blast radius if false | class |
|---|---|---|---|---|
| XA-01 | `get_order_by_client_id` returning 404 proves the order **never existed** at the venue, regardless of age or terminal state | `app/broker/alpaca_paper.py:1171-1172` → `app/monitoring.py:2930-2946` | A filled order aged out of the lookup horizon resolves to `REJECTED`; real shares held, no local order, no envelope, no protective sell. **Position quantity** | ASSUMED |
| XA-02 | `get_order_by_client_id` searches **all** order states, not just recent/open | same as XA-01 | XA-01's hidden sub-premise; separately falsifiable | ASSUMED |
| XA-03 | Alpaca rejects a duplicate `client_order_id` in **all** states including post-fill, with no retention window | `app/broker/alpaca_paper.py:630-634` (docstring), `:738-743` | UC-001's never-blind-resubmit guarantee collapses. **Position quantity** | ASSUMED — REV-0011 recorded it unverified (`disposition.md:36-38,42-45`) |
| XA-04 | A duplicate-id rejection always carries 409 or 422 **and** the substring `"duplicate"` or `"client_order_id"` in `str(exc)` | `app/broker/alpaca_paper.py:741-743`; replace mirror `:1065-1066` | A 422 duplicate worded differently falls to XA-05 → treated as never-submitted. **Fail-open. Order submission** | ASSUMED (every test supplies a message built to match: `tests/test_alpaca_paper_submit.py:288,398,427,456,696,767`) |
| XA-05 | 400/401/403/404/**422** is a definitive rejection meaning the order never reached the book | `app/broker/alpaca_paper.py:804-808`; pinned by `tests/test_alpaca_paper_submit.py:299-307` | 422 appears in **both** the duplicate and terminal branches; the only disambiguator is XA-04's substring. **Order submission** | **CONTRADICTED** (by XA-04, same file) |
| XA-06 | Alpaca's cumulative `filled_qty` is **monotone non-decreasing** per order id | `app/broker/alpaca_paper.py:1473-1475` (`delta <= 0 → []`) | A venue bust/correction lowering cumulative qty is silently discarded — no fill, no event, no quarantine. Position permanently overstated; the "never hidden" rail is bypassed. **Position quantity** | ASSUMED |
| XA-07 | `(broker_order_id, cumulative filled_qty)` identifies a fill level reached at most once in an order's life | `app/broker/alpaca_paper.py:1456-1458` | Fill→bust→refill to the same level is deduped away. **Position quantity** | ASSUMED |
| XA-08 | `get_orders(status=OPEN)` returns **every** open order in one unpaginated response | `app/broker/alpaca_paper.py:1250-1255` (no `limit`) | Truncation routes managed orders to XA-01's not-found path, and under-reports external/unmanaged venue exposure (`app/reconciliation.py:1128-1156`). **Position quantity + risk** | **CONTRADICTED** — Alpaca REST `GET /v2/orders` defaults to `limit=50`. *Open: not confirmed against the SDK — see Residual* |
| XA-09 | No fill can arrive after a locally **terminal** `CANCELED` | `app/monitoring.py:3707` (`_OPEN_STATUSES`) + `app/transitions.py:154`; mock at `app/broker/mock.py:138-144` | A fill after venue-confirmed cancel enters through no lane — neither per-order poll nor `status=OPEN`. **Position quantity.** *(The `CANCEL_PENDING` lane IS covered — `tests/test_sim_chaos.py:81`)* | MOCK-ONLY |
| XA-10 | HTTP 429 is a pre-flight reject: the order provably never reached the book, so plain retry is safe | `app/broker/alpaca_paper.py:815-821` | A rate-limited-but-accepted submit is redriven → duplicate order, guarded only by XA-03. **Order submission** | **CONTRADICTED** — the code comment records the conflict itself: *"conflict C2 keeps it transient vs §6's letter"* |
| XA-11 | Session record identity is the **UTC** calendar date while session type is Eastern | `app/store/memory.py:831`, `app/store/sqlite.py:1951`, `app/models.py:1197` | Session rolls at 19:00 ET (EST) / 20:00 ET (EDT) — a DST-dependent 1-hour window where the durable session is "tomorrow" but the Eastern session is live. Restart disagreement; per-session limits reset mid-session. **Kill-switch adjacent** | **CONTRADICTED** — `app/policy.py:437-441` names it a Rule-8 bypass root, hardened on **one** consumer |
| XA-12 | RTH is 09:30–16:00 ET every non-weekend day; no holidays, no half-days | `app/features.py:91-133`, `app/sellside/session.py:44-63`, `app/recorder/models.py:58-70` | Orders into a closed exchange with `extended_hours=False`; envelopes ACTIVE past a real close; strategy evaluates on a holiday. **Order submission** | **CONTRADICTED** — `app/features.py:110-118` states the gap and `tests/test_features.py:148-160` **asserts the wrong answer as correct** |
| XA-13 | Absence of feed messages for `MARKET_DATA_STALE_MINUTES` reliably indicates a dead connection, and proxies for "the exchange is closed" | `app/marketdata/alpaca_stream.py:83-95,324-338` | This is the *only* substitute for a market calendar (XA-12's cited mitigation) and cannot distinguish half-day / holiday / halt / websocket drop / illiquid symbol. **Sizing + submission** | ASSUMED |
| XA-14 | A security-level halt is indistinguishable from a quiet symbol and needs no separate handling | `app/marketdata/alpaca_stream.py:328-334` | Sizing/exit decisions run on a pre-halt print; a protective sell is submitted into a halted book. **Sizing** | ASSUMED |
| XA-15 | The paper account receives the full real-time **SIP** feed by default | `app/marketdata/alpaca_stream.py:137-142` (`feed: DataFeed = DataFeed.SIP`) | Without Algo Trader Plus the stream is IEX-only or refused; a partial-market tape drives sizing while presenting as full-market. **Sizing** | **CONTRADICTED** — the code default is unconditional while its own comment hedges on the subscription |
| XA-16 | `previous_daily_bar.close` is the prior **trading** day's close (venue calendar-aware) | `app/marketdata/alpaca_stream.py:124-126`, reseed `:207,:422,:431` | Gap/momentum features computed against the wrong baseline around holidays and half-days. **Sizing** | ASSUMED |
| XA-17 | 404 or 422 on `cancel_order` means "already terminal", so the cancel is idempotently successful | `app/broker/alpaca_paper.py:966-972` | A 422 meaning "not cancelable **yet**" (pending-new) reads as "already gone" → a live order believed canceled. **Cancel/replace (gated)** | ASSUMED |
| XA-18 | On replace, the venue terminalizes the predecessor and mints the replacement under our `client_order_id`, discoverable by that id | `app/broker/alpaca_paper.py:991-1012`; mock happy path `app/broker/mock.py:159-182` | Ambiguous-replace recovery reconciles against a predecessor or a phantom. The recovery branch (`:1077-1113`) is real; the mock cannot reach it | MOCK-ONLY |
| XA-19 | A duplicate submit is a *silently successful* idempotent no-op returning the same broker id | `app/broker/mock.py:98-106`; `tests/test_sim_chaos.py:249` asserts this models "the way the real `AlpacaPaperAdapter` does" it | The real adapter **raises** 409/422 then recovers. Mock and sim reproduce the outcome, not the mechanism, so `_canonical_ack_broker_id` / `_validate_ack_scope` / `_validate_ack_state` and the XA-04 substring gate are never exercised against an existing venue order. **Largest S-8 surface in the broker layer** | MOCK-ONLY |
| XA-20 | `filled_avg_price` is a trustworthy price for the synthesized delta fill | `app/broker/alpaca_paper.py:560-566`, `:1478-1496` | Cost basis and P&L wrong on multi-execution orders; the AIR-002 fallback selects a substitute price. **Sizing via P&L limits** | ASSUMED |
| XA-21 | N venue executions between two polls may be collapsed into one local fill without losing any safety-relevant property | `app/broker/alpaca_paper.py:1448-1496` | The local fill log is a coarsened projection, not a venue execution log. INV-9 is satisfied by a synthetic event. Any future property needing per-execution truth is unavailable retroactively | ASSUMED |
| XA-22 | `extended_hours=True` on a LIMIT+DAY order makes it eligible 04:00–09:30 and 16:00–20:00 ET | `app/broker/alpaca_paper.py:641-660,698-701` | Approved premarket candidates silently ineligible in their proposed session | DOC |
| XA-23 | MARKET orders are accepted only in the regular session | `app/broker/alpaca_paper.py:678-684` | Fail-closed today; a false assumption costs availability, not safety | DOC |
| XA-24 | Alpaca echoes `position_intent` as exactly `buy_to_open` / `sell_to_close` for simple orders | `app/broker/alpaca_paper.py` `_validate_ack_scope` (~`:275-300`) | Fail-closed: an unexpected value raises on a legitimate ack. A silent venue vocabulary change halts trading | ASSUMED |
| XA-25 | Alpaca never returns `notional`, `legs`, `stop_price`, `trail_price`, `hwm`, `ratio_qty` on simple limit/market orders | `app/broker/alpaca_paper.py` `_validate_ack_scope` (~`:262-275`) | Fail-closed. Availability, not safety | ASSUMED |
| XA-26 | Every symbol traded returns `asset_class == "us_equity"` | `app/broker/alpaca_paper.py` `_validate_ack_scope` (~`:257-261`) | Fail-closed on ADRs/ETNs/other classes | DOC |
| XA-27 | `get_all_positions()` is complete and unpaginated | `app/broker/alpaca_paper.py:1399-1407` | A truncated position report feeds `PositionMismatch` review (`app/reconciliation.py:809-814`) with phantom divergences, or hides a real one | ASSUMED |
| XA-28 | The configured reconcile query budget stays at or under Alpaca's real per-minute limit | `app/monitoring.py:2846-2852`, budget size in `app/config.py` | Exceeding it produces 429s on *reads* → inconclusive → orders stay quarantined and `needs_review` accumulates. Safe-but-stuck | ASSUMED *(number not compared — see Residual)* |
| XA-29 | `ZoneInfo("America/New_York")` resolves with current DST rules in every deployment container | `app/features.py`, `app/sellside/session.py:20`, `app/recorder/models.py:18` | Missing tzdata raises at import (loud, fine). **Stale** tzdata silently wrong session boundaries system-wide | ASSUMED |
| XA-30 | A tape corpus labelled `regular` was recorded while the exchange was actually open | `app/recorder/models.py:58-70` (third copy of XA-12) | Hazard 2's "replay real paper-session corpora as fixtures" would import XA-12's calendar defect into the fixture layer, making the replay oracle share the premise it exists to test | **CONTRADICTED** (by XA-12) |

## The actionable subset — no venue access required

**Seven rows are already contradicted by evidence inside the repo**, so acting on them needs no probe,
no credentials, and no ratification of the live-probe question: **XA-05, XA-08, XA-10, XA-11, XA-12,
XA-15, XA-30.** These are cheaper than the register that names them and should be cut as work regardless
of what happens to the rest of this proposal.

Two of them are **fail-open on a capital-critical path** and are the register's headline result:

- **XA-05 / XA-04** — the 422 collision. A duplicate rejection worded without the magic substrings
  classifies a live venue order as never-submitted. Fix: stop disambiguating on venue prose. Prefer the
  fail-safe default (treat an ambiguous 422 as `AmbiguousBrokerError`, the way 409 already falls
  through at `:822`) rather than widening the substring list, which would only move the cliff.
- **XA-01 / XA-02** — the 404 inference. Fix: a 404 must not, on its own, resolve a quarantined order to
  `REJECTED`. It is *at most* evidence of absence from the queried window, which is the same distinction
  `app/reconciliation.py:20-25` already draws for the mass report and which the impure caller discards.

## Residual — stated, not hidden

- **XA-08's class rests on Alpaca's documented REST default (50), not on reading the SDK.** `alpaca` is
  not importable in this container. If the SDK auto-paginates, XA-08 downgrades to ASSUMED. One grep in
  a bootstrapped `.venv` closes it and should run before the WO is cut.
- **XA-28's number was never compared** to Alpaca's published limit; the mechanism was found, the value
  was not checked.
- **`app/reconciliation.py` is 1,989 lines and roughly 150 were read.** Position-mismatch tolerance and
  the `PositionMismatch` consumer chain are unexamined; rows touching them (XA-27) are weaker than the
  rest.
- **No test suite was executed** (read-only work order). Absence-of-coverage claims come from `grep` over
  `tests/`, which finds by name and literal; a covering test under an unguessed name would not have
  surfaced. The exception is `tests/test_features.py:148-160`, read in full, which *affirmatively* pins
  the wrong half-day answer — that one is not an absence claim.
