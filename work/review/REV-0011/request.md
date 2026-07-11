---
type: Review Request
rev_id: REV-0011
campaign_id: CAMPAIGN-0001
packet: BROKER
container_group: G-G (broker adapters)
packet_lens: adversarial red-team (primary) + config-safety (secondary cluster)
status: AWAITING_REVIEW
targets: [G-G-broker]
human_gated_surfaces: [order-submission, live-shadow-config]
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [safety-core #1, safety-core #2, safety-core #5, safety-core #8, INV-020, INV-022, INV-023, INV-070, "spine INV-3"]
adr_in_scope: [ADR-002, ADR-006]
created: 2026-07-10
---

# Review Request REV-0011 — Broker adapters (venue seam), red-team + config-safety

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes no correctness claims — code beats the atlas, and if they
disagree that is itself a finding). You have the full repo at the frozen SHA.

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/broker/adapter.py` (270 LOC) — the `BrokerAdapter` ABC and the **typed error contract**
  (`BrokerError` / `TerminalBrokerError` / `AmbiguousBrokerError`) the engine quarantines on.
- `app/broker/alpaca_paper.py` (581 LOC) — the `AlpacaPaperAdapter`, the **ONLY** sanctioned site
  that imports the `alpaca` SDK (INV-070). Paper-only by construction.
- `app/broker/mock.py` (286 LOC) + `app/broker/sim.py` (292 LOC) — the IO-free test doubles the
  whole engine-side suite runs against; their contract fidelity is what makes every green
  monitoring test meaningful.
- `app/broker/factory.py` (63 LOC) — the composition-root selector (`create_broker_adapter`) that
  decides *which* adapter is built from config.

**Owned by other packets (follow leads freely into them):** these have a deep-coverage owner
elsewhere, so you need not audit them exhaustively — but **do not assume their contract holds**.
If the adapter *relies* on a behavior these modules don't actually guarantee (or vice-versa),
re-derive it from their code and report the reliance as **your** finding; and any defect you spot
inside them while chasing a broker lead is a finding wherever it lives.
- the runtime engine that DRIVES this adapter (submit sweep, timeout re-drive, quarantine
  resolution) → REV-0005 (ENGINE). The no-blind-resubmit guarantee is a **joint** property of the
  engine's control flow and this adapter's idempotency + classification; your half is the adapter.
- `app/config.py` credential/settings resolution → REV-0010 (KERNEL). But the **config→live-path
  reachability** question below is yours to answer from the adapter/factory side.
- the marketdata Alpaca port (`app/marketdata/alpaca_stream.py`, the *other* sanctioned SDK site)
  → REV-0012 (MARKETDATA).

## What you're reviewing
`app/broker/*` is the venue seam: the abstract port every caller depends on, the one real adapter
that speaks to Alpaca, the mocks the test suite trusts, and the factory that chooses among them.
It carries four safety-critical duties:

1. **SDK confinement + paper-only.** `alpaca_paper.py` is the single module allowed to `import
   alpaca` (INV-070 / ADR-006), and it constructs `TradingClient(..., paper=True)`
   unconditionally. Beta is Alpaca-Paper-only (safety-core #1/#2); the UI never calls Alpaca, only
   this adapter does (safety-core #5). A reachable live-trading path — via a config permutation, an
   alternate adapter, or a stray SDK import elsewhere — would breach the top-level safety core.
2. **The timeout / ambiguous contract.** `submit_order` is idempotent via a stable
   `client_order_id = order.id` (AIR-003): a crash-then-retry recovers the already-created venue
   order instead of double-submitting. An ambiguous outcome raises `AmbiguousBrokerError`, and the
   read-only `get_order_by_client_order_id` (ADR-002) is the ONLY way the engine resolves a
   `TIMEOUT_QUARANTINE` order. **The whole no-blind-resubmit guarantee rests on this adapter
   classifying correctly and its idempotency being airtight.**
3. **Error mapping.** Every broker failure mode must map to the *right* typed error so the engine
   does the safe thing: transient `BrokerError` (retry), `TerminalBrokerError` (escalate to
   `needs_review`), or `AmbiguousBrokerError` (quarantine + targeted reconcile, never resubmit).
4. **Config-safety.** No misconfiguration — of `BROKER_ADAPTER`, of credentials, of adapter
   selection — may enable live trading or silently disable the paper guard.

Run for context:
`git show b600101:app/broker/alpaca_paper.py` (or read the files at `b600101` — the broker
container, `docs/adr/ADR-002-timeout-quarantine.md`, and `docs/INVARIANTS.md` are byte-identical
between `b600101` and the current tip, so the anchors below are exact).

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
Every anchor was opened and paired with a stable symbol; line numbers are exact at `b600101`.

- **Paper-only construction (safety-core #1/#2).** `AlpacaPaperAdapter.__init__`
  (`app/broker/alpaca_paper.py:156` class, `:168` the `TradingClient(api_key, api_secret,
  paper=True)` call). There is no live-key env var and no `paper=` toggle anywhere (`app/config.py`
  reads only `ALPACA_PAPER_API_KEY`/`ALPACA_PAPER_API_SECRET`, `:150-151`). Trace whether ANY
  reachable path constructs a non-paper client, or mutates `_client` after construction.
- **SDK confinement (INV-070 / ADR-006).** The `import alpaca` block (`alpaca_paper.py:24-35`) is
  the only sanctioned trading-side occurrence. The factory imports the concrete adapter **lazily**
  inside the alpaca branch (`app/broker/factory.py:55`) so the bare package stays SDK-free
  (ADR-006 Finding 1). Confirm no engine/api/facade/store/ui module reaches the SDK by any chain —
  the `.importlinter` contract `alpaca-sdk-confined-to-adapter` and its transitive test are the
  oracle, but re-derive from the imports, not from the contract's say-so.
- **Idempotency key (AIR-003).** `submit_order` sets `client_order_id=order.id` on BOTH request
  shapes — `MarketOrderRequest` (`alpaca_paper.py:245`) and `LimitOrderRequest` (`:255`). The
  submit itself is `:262`. This is the deterministic key the whole no-blind-resubmit design leans
  on.
- **Duplicate-recovery path (the UC-001 REFUTATION contract — see known-item below).** The
  `except APIError` block (`alpaca_paper.py:264`): a 409/422 naming a duplicate (`:270`) triggers a
  read-only lookup of the already-created order via `self._client.get_order_by_client_id`
  (`:282`), returning its venue id (`:285`) so re-submit is idempotent. If that lookup itself fails,
  it raises `TerminalBrokerError` (`:291`) rather than looping. **This is the branch UC-001 was
  refuted on — stress it (probes 1–3), do not merely re-confirm it.**
- **Error classification (ADR-002 §6 / spine §6).** In the same `except APIError`: a definitive
  4xx `400/401/403/404/422` → `TerminalBrokerError` (`:305-309`); a `429` rate-limit → transient
  `BrokerError` (`:318-322`, on the stated reasoning that a pre-flight reject never reached the
  book); anything else (5xx incl. 504, unknown) → `AmbiguousBrokerError` (`:323`). The bare
  `except Exception` for transport/timeout after the request may have left → `AmbiguousBrokerError`
  (`:327` / `:332`). Trace each HTTP/transport outcome to the error the engine will act on.
- **The ADR-002 targeted query (read-only reconcile key).** `get_order_by_client_order_id`
  (`alpaca_paper.py:420`) calls `self._client.get_order_by_client_id` (`:436`); returns `None`
  ONLY on a confirmed 404 (`:440-441`), raises `BrokerError` on any query FAILURE (`:442`), and is
  strictly read-only (it never submits/cancels). Contract is also stated on the ABC
  (`app/broker/adapter.py:219`). Confirm a failed query can NEVER be read as "absent" — that would
  be a not-found→reject oversell path (§7 safeguard).
- **The typed error contract (what the engine branches on).** `BrokerError` (`adapter.py:26`,
  transient-by-default), `TerminalBrokerError` (`:41`, definitive → `needs_review`),
  `AmbiguousBrokerError` (`:52`, quarantine + reconcile). Since `AmbiguousBrokerError` is a
  `BrokerError` subclass, a caller's `except BrokerError` still catches it — verify the adapter
  never raises a *plain* `BrokerError` on a genuinely ambiguous outcome (that would demote a
  quarantine to a blind retry).
- **The `submit_order` ABC contract (AIR-001 non-empty id).** `adapter.py:156` — the contract that
  a submit returns a non-empty broker id or raises. The impl returns `str(resp.id)` (`:263`);
  confirm no path returns `""`/whitespace/`None`.
- **The MARKET-outside-regular-hours guard.** `alpaca_paper.py:229` (branch) / `:235` (the
  `current_session is not SessionType.REGULAR` fail-closed → `BrokerError`). Check the
  fail-closed classification is right (retryable, not a silent send into thin liquidity).
- **Factory selection (config-safety).** `create_broker_adapter` (`factory.py:24`): `use_alpaca`
  is `choice == "alpaca"` OR (`choice == "auto"` AND creds present) (`:38-40`); every other path
  returns `MockBrokerAdapter` (`:47`). `alpaca` without creds raises (`:49-53`). `broker_adapter`
  is validated to `{auto, mock, alpaca}` at load (`app/config.py:314-317`). Enumerate the config
  space; find a permutation that reaches a non-paper venue, or prove none exists.
- **Mock/sim fidelity (the test-double contract).** `MockBrokerAdapter` (`mock.py:42`;
  `submit_order` `:83`; `get_order_by_client_order_id` `:124`) and `SimBrokerAdapter`
  (`sim.py:52`; `submit_order` + on-submit hook `:84`). These are what the engine suite trusts. If
  a mock's behavior diverges from what `AlpacaPaperAdapter` actually does on the same input, every
  green test built on it is asserting against a fiction — that divergence is a finding.

## Probe checklist (find the failure, or prove it cannot exist — symmetric challenges)
**RED-TEAM / SAFETY**
1. **Stress the UC-001 refutation across ALL states (not just the happy recover).** Construct a
   duplicate-`client_order_id` submit where the already-live venue order is (a) working, (b)
   partially filled, (c) fully filled, (d) canceled/rejected. Does `:282-285` recover and return
   the correct venue id in every case, so the engine adopts reality rather than resubmitting? **Find
   a state where the recovery returns a wrong/stale id, swallows a post-fill order as still-open, or
   escalates a recoverable order to `needs_review` — or prove the recovery is correct for all
   states including post-fill.**
2. **Map every broker outcome to its typed error and check it is the *safe* one.** For each of
   {timeout, transport drop, parse failure, 504, other 5xx, 429, 400/401/403/404/422, duplicate-id
   409/422, duplicate-id-then-lookup-fails}: does `submit_order` raise the error the engine needs
   (`Ambiguous`→quarantine, `Terminal`→escalate, plain→retry)? **Find one outcome that raises the
   wrong class — especially a genuinely ambiguous result demoted to a retryable plain `BrokerError`
   (blind-resubmit path), or a live-may-exist result classified `Terminal`/`REJECTED` — or prove
   the mapping is exhaustive and safe.**
3. **Break idempotency.** Find any submit path that can double-fire a live venue order: a
   `client_order_id` NOT set (`:245`/`:255`), a retry that skips the duplicate branch, a
   `get_order_by_client_id` failure at `:286` mis-swallowed, or the targeted query at `:436`
   returning a value the caller can read as "absent" on a failure rather than a confirmed 404
   (`:440` vs `:442`). Show the double-submit / oversell, or prove the `client_order_id` +
   read-only-query design closes it end-to-end at the adapter boundary.
4. **The overfill fact (INV-4 / ADR-001 record-not-hide).** `get_order_status` reports the
   broker's cumulative `filled_qty` as authoritative (`alpaca_paper.py:366`) and emits fills as a
   delta over `recorded_quantity` (`_get_fills` `:523`, `:553`). Confirm the adapter never *hides*
   or *caps* a broker-authoritative overfill — it surfaces the cumulative truth and lets the engine
   quarantine — and never fabricates a price for an unpriceable fill (`_resolve_fill_price` `:112`
   rejects `0.0`/NaN/negative, returns `[]` at `:557` so the divergence escalates). Find a path that
   drops or masks the fact, or prove it is always surfaced.

**CONFIG-SAFETY** (can a misconfig enable live trading, or disable the paper guard)
5. **Enumerate the config → adapter map.** Across every value of `BROKER_ADAPTER`
   (`auto`/`mock`/`alpaca`/invalid) × {creds present / absent / partial}, does `create_broker_adapter`
   (`factory.py:24`) ever return anything but `MockBrokerAdapter` or a `paper=True`
   `AlpacaPaperAdapter`? Is there a partial-credential state (`has_alpaca_credentials`,
   `config.py:233`) that half-configures the real adapter? **Find a permutation that builds a
   non-paper client or a broken paper guard, or prove the config space is closed under paper-only.**
6. **Prove there is no *second* SDK site and no live toggle.** Confirm `import alpaca` appears at
   exactly one trading-side module (`alpaca_paper.py:24-35`) and that no `paper=False` /
   `execution_mode` / `LIVE_SHADOW` construction exists anywhere reachable from the adapter or
   factory. The `live-shadow-config` surface is gated and currently un-wired — verify it is truly
   absent (no dead-but-flippable switch), not merely unused. Find a reachable live/shadow
   construction, or prove the adapter can only ever be paper.

**ERROR-MAPPING / CONTRACT**
7. **Mock vs real-adapter divergence.** Diff the *observable contract* of `MockBrokerAdapter` /
   `SimBrokerAdapter` against `AlpacaPaperAdapter` for the paths the engine relies on: duplicate-id
   recovery, ambiguous-submit → seeded venue order (`mock.py:260` `seed_venue_order`), targeted
   query returning `broker_order_id` for adoption (`alpaca_paper.py:449-456` vs `mock.py:124`),
   non-empty-id contract, cancel idempotency. **Find a behavior the mock guarantees that the real
   adapter does not (or vice-versa) — a fidelity gap means green engine tests assert against a
   fiction — or show the doubles are faithful on every path the engine depends on.**
8. **Cancel idempotency by status, not free-text.** `cancel_order` (`alpaca_paper.py:383`) treats
   only 404/422 as an idempotent no-op (`:404`) and raises every other code. Confirm a *live* order
   can never be reported canceled by a transient error, and a genuinely-terminal one never raises.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the CODE against the invariant **statements**, not against the adapter's pinning tests. Per
X-002 a test can assert the very bug it should catch — and this container has a **named, on-file
instance of exactly that** (see the disclosed in-scope item below), so the tests here are
specifically not to be trusted as the oracle. Re-derive "what must always hold" from:
- **`docs/INVARIANTS.md`** — INV-070 (only the two concrete ports import the SDK), INV-020
  (`submitted` never without a real non-empty broker id — the adapter is layer 1 of 3), INV-022
  (a live-at-broker order is never untracked), INV-023 (stale `SUBMITTING` recovered by *idempotent*
  re-drive — the property that rests on this adapter's `client_order_id`).
- **`CLAUDE.md` safety core** — #1 (no live in beta; PAPER/`LIVE_SHADOW` only, live disabled by
  config), #2 (Alpaca Paper only), #5 (the UI never calls Alpaca, only the adapter does), #8
  (submitted ≠ filled — the adapter must never let an ack read as a fill).
- **`docs/adr/ADR-002-timeout-quarantine.md`** — the stable-`client_order_id`-is-a-reconcile-key-
  not-a-redrive-permission decision and its required-tests list, and **`docs/adr/ADR-006`** /
  `.importlinter` for the SDK-confinement contract.
- **`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` §5–§6** — spine **INV-3** (block on ambiguity; while a
  spawn is `TIMEOUT_QUARANTINE` the primary is `BLOCKED`, no replacement) and §6's order-outcome
  classification table. Note §6's letter lists `400/401/403/422/429` as definitive rejects while the
  adapter deliberately treats `429` as *transient* and adds `404` to terminal (`alpaca_paper.py:305`
  vs `:318`, with an in-code "conflict C2" note): decide whether the adapter's classification is
  safety-correct against the **statement** (does the chosen class ever enable a blind resubmit of a
  possibly-live order?), independent of what any test pins.

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro plus its pasted output**. A good harness here is
  a **fake SDK `TradingClient`** that (a) enforces `client_order_id` uniqueness (raises a 409/422
  naming the duplicate on a repeat), (b) can be scripted to raise `APIError(status_code=...)` /
  timeouts / parse failures, and (c) records calls — inject it into `AlpacaPaperAdapter` in place of
  the real `alpaca` client and drive `submit_order` / `get_order_by_client_order_id` / `cancel_order`
  directly. The IO-free `MockBrokerAdapter`/`SimBrokerAdapter` are also fair game for engine-side
  interleavings. A finding with no repro is marked **"unverified concern"** and **cannot gate**.
- **State plainly what you could not exercise:** real-broker wall-clock timing, true network
  partitions, and Alpaca's actual 5xx/504 behavior cannot be reproduced in-repo — reason about them
  from the classification code and mark those results environment-limited, don't fabricate a repro.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran.** A bare
  "looks fine / LGTM" with no probe log is a **rejected review** for that area — show your work on
  clean code too.
- If the code contradicts the Atlas, ADR-002, or a disclosed known-item, that disagreement is
  itself a finding (≥ P1).

### Disclosed in-scope known-items (CALIBRATION, not answers — Atlas anti-bias rule 3)
Confirm/expand these as a check that your probing works — do **not** re-file them as fresh P0/P1;
a genuinely *distinct* adjacent defect IS wanted.
- **UC-001 (crash-window double-submit) was REFUTED**, precisely because `submit_order` recovers a
  duplicate `client_order_id` (`alpaca_paper.py:282` lookup, `:285` return, `:264-294` block).
  **Do not re-raise UC-001.** Your job is to *stress that recovery contract* (probes 1–3): is it
  correct for ALL venue states including post-fill; is `TerminalBrokerError` raised on the right
  conditions (`:291`, `:306`); can a config or alternate-adapter path break the idempotency it
  depends on? The full Wave-1 VERIFIED set is in the Atlas — treat any of those as known.
- **Adapter SDK method-name fix (RESOLVED, still queues for independent review):**
  `work/review/FINDING-alpaca-adapter-wrong-sdk-method.md` records that the adapter formerly called
  a non-existent `get_order_by_client_order_id` on the SDK; the fix (now `self._client.
  get_order_by_client_id` at `alpaca_paper.py:282` and `:436`) landed but **explicitly queues for
  this independent review** because it is the order-submission/reconciliation surface. Confirm the
  corrected SDK method name is right against the pinned `alpaca-py` and that BOTH call sites are
  fixed and typed — this is calibration, not a fresh finding.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** and fill it: the
findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters | Proposed fix`),
an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and whether **G-G's broker gate may
clear**. Because this packet touches human-gated surfaces (order-submission, live-shadow-config),
its gate clears only when this packet's review is dispositioned `ACCEPT`/`ACCEPT-WITH-CHANGES`.
State plainly anything you could not verify (real-broker timing/network). Do **not** edit
`request.md`; do **not** push code fixes.
