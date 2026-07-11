---
type: Review Request
rev_id: REV-0010
campaign_id: CAMPAIGN-0001
packet: KERNEL
container_group: G-A (kernel + predicates)
packet_lens: adversarial red-team (primary) + correctness/totality (secondary)
status: AWAITING_REVIEW
targets: [G-A-models, G-A-transitions, G-A-position, G-A-policy, G-A-features, G-A-protection]
human_gated_surfaces: [order-submission, manual-flatten, kill-switch]   # kernel is a LEAF (no I/O, calls none of these) — but a wrong predicate verdict here silently *enables* one of them upstream; see "Human-gated surfaces" note below
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [safety-core #8, safety-core #9, safety-core #10, INV-001, INV-002, INV-003, INV-004, INV-020, INV-021, INV-025, INV-060, INV-061, INV-075, "spine INV-1..9"]
adr_in_scope: [ADR-001, ADR-002, ADR-008]
created: 2026-07-10
---

# Review Request REV-0010 — The leaf kernel (pure predicates + model), red-team / correctness

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes **no** correctness claims — code beats the atlas, and if they
disagree that is itself a finding, at least P1). You have the full repo at the frozen SHA.

This packet is the **leaf of the whole spine**: the pure predicate/model modules everything else
imports. `models.py` is the type kernel (`INV-073` — it imports no other `app` layer);
`transitions.py` is the legal-transition graph both stores enforce; `policy.py`, `position.py`,
`features.py`, and `protection.py` are pure, IO-free, async-free functions that decide *is this a
real number, a legal transition, a safe fill, a breached limit, a floor breach*. Every higher
packet — STORE-SPEC (REV-0006), ENGINE (REV-0005), EVENTS (REV-0007), STRATEGY (REV-0014) —
**delegates** its legality/validity/sizing decisions down to these functions. **You own their
correctness.** A predicate that returns the wrong verdict for some input shape is a defect *in
every caller at once*, and the callers were reviewed on the assumption these are total and correct.

Two lenses, both at once:
- **Correctness / totality (primary here):** for every input shape, does each predicate return the
  *right* answer or a typed rejection — never a silent wrong verdict, never a `None`-fallthrough,
  never a raw `TypeError`/`ValueError` that escapes as a 500? Pure functions are exactly the thing
  you can prove total by exhausting their input shapes — **do that, don't hand-wave.**
- **Adversarial red-team:** can a wrong verdict here *enable an unsafe action upstream* — permit an
  order/size that should be blocked, clear a fill that should be quarantined, admit an illegal
  transition, or drive sizing off invalid market data? Trace the reach; the kernel is a leaf but its
  verdicts gate order-submission, manual-flatten, and the kill switch.

## Human-gated surfaces (why a leaf packet lists them)
The kernel calls **no** human-gated surface directly — it has no I/O. It is listed against
order-submission / manual-flatten / kill-switch because a **wrong predicate verdict is the enabling
condition** for one: `risk_limit_reason`/`fill_value_reason` returning `None` (=allow) on a
malformed input clears an order-submission path; `order_intent_block_reason`/`kill_switch_block_reason`
returning `None` on a HALTED session would leak intent past the kill switch; `would_go_negative`/
`apply_fill` disagreeing corrupts the overfill-quarantine decision that gates autonomous trading. So
a P0/P1 here is a **safety** finding even though the fix lands in a pure function. Flag any such
reach explicitly.

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/models.py` (~810 LOC) — the Pydantic v2 entity kernel + every enum + the `Order` origin-XOR
  validator (`models.py:512`) + `TradingState.of` (`models.py:115`).
- `app/transitions.py` (129 LOC) — `ORDER_TRANSITIONS` (`transitions.py:45`), `CANDIDATE_TRANSITIONS`
  (:13), `SELL_INTENT_TRANSITIONS` (:30), and the timestamp maps.
- `app/policy.py` (614 LOC) — the pure reason-code predicates: numeric guards, fill/limit/candidate
  validity, the CAPI risk gate, and the operational-status classifier.
- `app/position.py` (145 LOC) — `apply_fill` (`position.py:37`), `fold_fills` (:118),
  `would_go_negative` (:142), `NegativePositionError` (:19).
- `app/features.py` (131 LOC) — `pct_move`/`spread`/`spread_pct`/`session_type_for` and the `_finite`
  market-data gate.
- `app/protection.py` (179 LOC) — `floor_breach_reason` (`protection.py:82`),
  `protective_limit_price` (:135), `exit_quantity` (:73), `floor_price` (:66), `ProtectionConfig`/
  `FloorBreach`.

**`app/config.py`** is nominally in group G-A (Atlas) but is `Settings`-loading, not a pure
predicate; its load-time numeric validation is the precondition several `policy.py` predicates
*assume* (e.g. `risk_limit_reason`'s "production always passes validated-positive limits" claim,
`policy.py:477`). Treat `config.py` as **adjacent**: where a kernel predicate's correctness rests on
`config.py` having rejected a bad value, re-derive that from `config.py`'s own code — do not take the
docstring on faith — and report the reliance if the guard isn't actually there.

**Owned by other packets (follow leads freely into them):** these consume the kernel's verdicts, so
where their safety rests on what a kernel predicate decides, re-derive that decision *here* and report
the reliance as **your** finding.
- the store **planners** that call these predicates (`app/store/core.py`, `base.py`) → REV-0006
  (STORE-SPEC). REV-0006 explicitly **delegates legality/validity down to this container** (see its
  scope note "the kernel predicates … → REV-0010"); several of its probes end "re-derive that decision
  in KERNEL." Those re-derivations are **your** verdict to sign off.
- the **engine** that sequences predicate calls under the store lock → REV-0005 (ENGINE).
- the **projectors** that fold `ExecutionEventType.FILL` and project order status off `ORDER_TRANSITIONS`
  → REV-0007 (EVENTS).
- the **strategy** layer that consumes `features.py` outputs to size candidates → REV-0014 (STRATEGY).

## What you're reviewing
There is **no in-range diff** to read: `git diff b600101 -- app/models.py app/transitions.py
app/policy.py app/position.py app/features.py app/protection.py` is empty (verified — all six files
are byte-identical between the frozen base and the review branch tip). Review the files as they stand
at `b600101`.

The kernel's contract with everything above it is: **"the pure decision lives here, exactly once, so
no two callers drift."** `policy.py`'s own docstring (`policy.py:1`) states this is the single home
every layer imports so "a policy decision … is made in exactly one place and can never drift between
callers." That makes a wrong decision here *un-catchable* by a caller that trusts it — which is why
the bar is totality, not spot-checks.

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
Each anchor is a `file:line` **paired with a stable symbol** so it re-locates if lines drift. These
are starting points, not verdicts.

**Position math (safety-core #8/#9, INV-001/002/004, spine INV-1/INV-9, ADR-001):**
- `apply_fill` (`position.py:37`): the BUY branch (`position.py:75`) with the **cover-a-short**
  re-basis `cost_basis = new_quantity * fill.price` (`position.py:89`) vs the normal-accumulation
  branch (`position.py:81`); the SELL branch (`position.py:95`) with its `NegativePositionError`
  raise (`position.py:99`), the proportional-reduction basis `cost_basis * (new_quantity /
  old_quantity)` (`position.py:102`), and the flat/short zero-basis else (`position.py:105`); the
  `average_price = cost_basis / quantity if quantity > 0 else None` (`position.py:108`).
- `would_go_negative` (`position.py:142`) — the SELL-only underflow predicate the overfill-quarantine
  branch keys on (called from `core.py`'s `plan_append_fill` overfill check, REV-0006).
- `fold_fills` (`position.py:118`) — the from-flat fold; the `PositionProjector` reuses `apply_fill`
  to continue a fold from a snapshot (`ExecutionEvent` model note, `models.py:714`).

**The transition graph (INV-020/021/025/075, ADR-002/008, spine INV-1..9):**
- `ORDER_TRANSITIONS` (`transitions.py:45`): the deliberate **absence** of `CREATED → SUBMITTING`
  (`transitions.py:47` comment — the claim gate writes `SUBMITTING` directly, so `transition_order`
  is not a back door; INV-021); the `SUBMITTING` fan-out incl. `TIMEOUT_QUARANTINE` (`transitions.py:71`);
  the `TIMEOUT_QUARANTINE` resolution set `{SUBMITTED, REJECTED, CANCELED}` (`transitions.py:73`)
  which excludes a direct `→ FILLED` (`transitions.py:76` comment — "submitted != filled", conflict C4);
  the `PARTIALLY_FILLED` and `CANCEL_PENDING` **self-loops** (`transitions.py:92`, `:98`); the terminal
  sets `FILLED`/`CANCELED`/`REJECTED` → `set()` (`transitions.py:103-105`).
- The module docstring's claim "Same-status transitions are handled as idempotent no-ops by the
  stores, **not encoded here**" (`transitions.py:5-6`) — read it against the two self-loops that *are*
  encoded (`transitions.py:92`, `:98`).
- `NON_TERMINAL_ORDER_STATUSES` (`policy.py:54`) — derived from `ORDER_TRANSITIONS` (`if transitions`)
  rather than hand-listed, so "counts toward CAPI exposure" == "has ≥1 outgoing edge". The derivation
  is the single point where the graph's shape decides the exposure set.
- `SELL_INTENT_TRANSITIONS` (`transitions.py:30`) with `APPROVED → EXPIRED` (`transitions.py:38`) —
  the self-heal edge INV-033 depends on; contrast `CANDIDATE_TRANSITIONS` (`transitions.py:13`) which
  has **no** `APPROVED → EXPIRED` (candidates revert to `PENDING` instead — INV-010).

**Numeric / fill / limit predicates (INV-002/003/004, the CAPI gate, the market-data safety rail):**
- The shared numeric guards: `finite_number_reason` (`policy.py:186`, bool→non_numeric→non_finite
  order), `whole_count_reason` (`policy.py:213`), `fill_value_reason` (`policy.py:233`),
  `limit_price_reason` (`policy.py:265`), `candidate_numeric_reason` (`policy.py:286`).
- `fill_order_match_reason` (`policy.py:318`): checks symbol (`:333`), side (`:335`), cumulative-qty
  (`:337`) — and note what it does **not** check (order *status*).
- `filled_quantity_reason` (`policy.py:358`): the monotonic non-decreasing + `<= order.quantity`
  guard (`policy.py:379-382`), called by `plan_transition_order` (REV-0006).
- `existing_exposure` (`policy.py:391`): the BUY-only exposure sum (`policy.py:448`, the
  `OrderSide.BUY` filter `:456`, the fill-derived-remaining `:449`), and `risk_limit_reason`
  (`policy.py:461`): the check order allowlist→shares→notional→total (`policy.py:490-501`) and its
  `order_limit_price: float`/`order_quantity: int` parameters (no in-function finiteness/sign guard).

**Control-gate predicates (INV-060, safety-core #10):**
- `order_intent_block_reason` (`policy.py:59`) — `HALTED → "kill_switch"`, `REDUCING → "buys_paused"`,
  `None`/`ACTIVE → None`; `kill_switch_block_reason` (`policy.py:109`) — the narrower predicate that
  only `HALTED` holds (the `PROTECTION_FLOOR` carve-out, INV-060); `session_submission_block_reason`
  (`policy.py:86`) — adds `session_closed`/`unknown_session`; `order_session_resolution_reason`
  (`policy.py:133`) — the load-bearing `None → "unresolved_session"` that is *deliberately opposite*
  to `order_intent_block_reason`'s `None → None`. These four differ on `None`/closed handling **on
  purpose** — map each one's convention and why it must differ.
- `TradingState.of` (`models.py:115`) — kill dominates pause; the `SessionRecord.trading_state`
  read-model note (`models.py:791-803`) explaining why it is an **independent** field, not a pure
  derivation of the two booleans.

**Market-data features (the "never trade on invalid market data" safety rail):**
- `_finite` (`features.py:22`) → `market_data_field_reason` (`policy.py:159`) → `finite_number_reason`
  (`policy.py:186`): the single market-data usability gate. Note what `finite_number_reason` rejects
  (bool / non-numeric / NaN / ±Inf) and what it does **not** (sign).
- `pct_move` (`features.py:52`), `spread` (`features.py:65`), `spread_pct` (`features.py:73`),
  `session_type_for` (`features.py:88`, the naive-datetime raise `:118`, weekend `:121`, the
  inclusive-start/exclusive-end windows `:124-129`).
- Contrast: `protection.py` adds its **own** `<= 0` positivity guards (`protection.py:113`, `:121`,
  `:163`, `:176`) on top of `finite_number_reason`; `features.py` does not. Read that asymmetry
  against the safety rail.

**Protection engine (Rule 12 / floor-exit sizing):**
- `floor_breach_reason` (`protection.py:82`): the full guard cascade (`:103-125`) and the returned
  `FloorBreach.quantity = exit_quantity(position)` (`:131`); `exit_quantity` (`protection.py:73`) —
  the full-position exit; `protective_limit_price` (`protection.py:135`): the bid-validity/crossed
  handling (`:165-172`), tick rounding (`:174`), and strict-`> 0` clamp (`:176`).

## Probe checklist (find the input where the predicate returns the wrong answer, or prove it total + correct — symmetric challenges)
Grouped by cluster. **Every probe is answerable with a tiny unit repro** — these are pure functions
of their arguments, so you can construct any input by hand and assert the return value. A P0/P1 needs
a **runnable repro + pasted output** (see Evidence). Enumerate input shapes; do not spot-check.

**A. POSITION MATH (`position.py`)**
1. **`would_go_negative` ⇔ `apply_fill` agreement.** The overfill-quarantine decision (REV-0006's
   `plan_append_fill`) branches on `would_go_negative`; the *recording* math is `apply_fill`. If the
   predicate and the math disagree on any `(current_quantity, quantity)`, a fill the predicate clears
   as safe could still raise in `apply_fill` (or vice versa), splitting the "record + quarantine" path
   from the "reject" path. Enumerate the boundary (`quantity == current_quantity`, `quantity =
   current_quantity + 1`, `current_quantity = 0`, a pre-existing negative `current_quantity`): show
   `would_go_negative(q, SELL, n) is True` **exactly when** `apply_fill(pos_q, sell_n,
   allow_short=False)` raises `NegativePositionError` — or find the input where they diverge.
2. **`apply_fill` sign / cost-basis correctness across the short crossing (ADR-001).** Trace
   `cost_basis`/`average_price` through: (a) a normal long accumulation; (b) a proportional sell that
   leaves a long remainder (`position.py:102` — does it hold `average_price` invariant?); (c) a sell
   that lands **exactly flat**; (d) `allow_short` sells that cross long→short; (e) a BUY that covers a
   recorded short back to long (`position.py:89` re-basis) and one that covers **exactly to flat**
   (`position.py:93`). Confirm `average_price` is `None` for every `quantity <= 0` and never a
   negative or `ZeroDivisionError`, and that the covering re-basis never additively inflates basis off
   the zeroed short (the docstring's stated hazard). Find a quantity/basis/avg that is wrong (off-by-one,
   wrong sign, inflated basis), or prove the formula correct over the crossing.
3. **Integer vs float discipline.** `Fill.quantity`/`Order.quantity`/`Position.quantity` are `int`;
   `price`/`cost_basis` are float. Does any `apply_fill` path produce a non-integer `quantity`, or a
   `cost_basis`/`average_price` that a downstream `int`-typed field then truncates? Prove quantity
   stays integral, or find the coercion.

**B. TRANSITION GRAPH (`transitions.py`)**
4. **Terminal states are truly terminal; no illegal edge; no missing edge.** For each `OrderStatus`,
   enumerate its outgoing set and check against the *intent* (the inline comments + the invariant
   statements, **not** the pinning tests — X-002). Specifically: (a) are `FILLED`/`CANCELED`/`REJECTED`
   dead-ends with *no* path out (`transitions.py:103-105`)? (b) is any edge present that should not be
   — e.g. a backward edge other than the one deliberate `SUBMITTING → CREATED` claim-release
   (`transitions.py:63`)? (c) is any *needed* edge absent — e.g. can a `PARTIALLY_FILLED` order ever
   need `→ REJECTED` (not in the set, `:91`) and does its absence strand a real broker outcome?
5. **`CREATED → SUBMITTING` absence is the sole INV-021 guarantee at the graph level.** Confirm the
   edge is absent from `ORDER_TRANSITIONS` (`transitions.py:46-60`) so the generic `transition_order`
   (which reads this table) cannot mint `SUBMITTING`. Then check the *converse hazard*: `SUBMITTING →
   TIMEOUT_QUARANTINE` **is** a legal edge (`transitions.py:71`), but the graph cannot encode "only via
   the evented co-write path." From the graph alone, could a generic (non-evented) `transition_order`
   caller drive `SUBMITTING → TIMEOUT_QUARANTINE` and flip the status column with **no**
   `TIMEOUT_QUARANTINE` `ExecutionEvent` (ADR-004/ADR-008/INV-075)? The graph legality is
   necessary-but-not-sufficient — determine whether the sufficiency lives entirely in a caller (a
   store `assert`, REV-0006 `core.py:1689`) and flag the graph's inability to express the constraint,
   or prove the edge is unreachable except through the evented path.
6. **Self-loop vs INV-025 "same-status is a no-op".** The docstring says same-status transitions are
   no-ops "not encoded here" (`transitions.py:5-6`), yet `PARTIALLY_FILLED → PARTIALLY_FILLED`
   (`transitions.py:92`) and `CANCEL_PENDING → CANCEL_PENDING` (`transitions.py:98`) **are** encoded
   (for "further partial fills" / "a late partial fill progressed"). Reconcile: is a same-status
   `PARTIALLY_FILLED` transition a no-op (INV-025, no audit row) or a fill-progress (a real
   `order_fill_progress` row)? A doc/code disagreement is itself a finding (≥P1 per Atlas rule 2).
   Determine whether the graph + INV-025 can be read to either drop a legitimate fill-progress row or
   mint a spurious audit row, or prove the self-loops and INV-025 are consistent (the no-op rule keys
   on unchanged `filled_quantity`, the self-loop on a changed one).
7. **`NON_TERMINAL_ORDER_STATUSES` binning (`policy.py:54`).** This drives CAPI exposure. Confirm the
   derivation classifies **exactly** `{CREATED, SUBMITTING, SUBMITTED, PARTIALLY_FILLED, CANCEL_PENDING,
   TIMEOUT_QUARANTINE}` as non-terminal and `{FILLED, CANCELED, REJECTED}` as terminal. A terminal
   status wrongly counted over-restricts (rejects a legitimate order); a live status wrongly omitted
   under-restricts (admits an order over `max_total_exposure`). Find a mis-bin, or prove the
   "has-an-outgoing-edge ⇔ counts-as-risk" equivalence holds for every status.
8. **`SELL_INTENT_TRANSITIONS` vs `CANDIDATE_TRANSITIONS` divergence.** The sell-intent table has
   `APPROVED → EXPIRED` (`transitions.py:38`, the INV-033 self-heal); the candidate table does not
   (`transitions.py:19`). Confirm each table's edge set matches its lifecycle's invariant (INV-033
   self-heal for sell-intents; INV-010 revert-to-`PENDING` for candidates), and that no terminal
   sell-intent/candidate status (`REJECTED`/`EXPIRED`/`ORDERED`) has an outgoing edge.

**C. RISK / LIMIT / FILL VERDICTS (`policy.py`) — can a wrong verdict permit an unsafe order/size?**
9. **`risk_limit_reason` totality against malformed inputs.** Its signature types `order_limit_price:
   float` and `order_quantity: int`, but Python does not enforce that, and the function has **no
   internal finiteness/sign guard** — every check is a bare `>` comparison (`policy.py:492-501`). Feed
   it a `NaN`/`±Inf`/negative `order_limit_price`, and separately a negative `order_quantity`, with the
   other caps set so only the total-exposure or notional check would fire. Does it return a breach
   reason, or `None` (= *allow the order*)? (A `NaN` notional makes every `>` False.) Then determine
   **reachability**: does any caller reach `risk_limit_reason` with a price/qty it has **not** already
   validated via `limit_price_reason`/`whole_count_reason`/`config.py` load-validation? If reachable,
   this is a predicate returning the wrong "safe" verdict on an unsafe order (safety-core / order-
   submission enabling). If not, prove every caller validates first and document that `risk_limit_reason`
   is total **only under that precondition** (an unguarded total function that silently permits is still
   a latent hole the ABC/config must be shown to close).
10. **`existing_exposure` under a malformed order book (`policy.py:391`).** A `limit_price` of `NaN`
    makes `o.limit_price or 0.0` (`policy.py:449`) evaluate to `NaN` (NaN is truthy), so the returned
    exposure is `NaN`, which then makes `risk_limit_reason`'s total-exposure check `NaN + notional >
    max` False (probe 9). Also check the fill-derived-remaining `o.quantity -
    filled_by_order.get(o.id, o.filled_quantity)` (`:449`): can it go negative (an over-recorded fill)
    and *reduce* total exposure, admitting an order that should breach? Find an order-book shape that
    yields a wrong exposure total, or prove the inputs are always pre-validated positive/finite.
11. **`fill_order_match_reason` ignores order status (`policy.py:318`).** It gates symbol/side/
    cumulative-qty but not `order.status`. Construct an order in `CREATED` (never submitted),
    `REJECTED`, and `CANCELED`, and a matching in-bounds fill; the predicate returns `None`
    (=record the fill). Decide the kernel-level verdict REV-0006 delegates here: is that **correct**
    (a broker-authoritative fill is a fact to record regardless of local status — INV-001/ADR-001,
    position truth is fill-derived and firewalled) or a **gap** (a fill recorded against a
    never-submitted `CREATED`/`REJECTED` order moves position off an order that never reached the
    venue, violating "only fills from real orders")? This is the *predicate's* correctness, not the
    caller's dedup/overfill (a Wave-1 known-item at the caller level) — you own this leaf verdict.
12. **The numeric-guard family is total and its reason vocabulary is stable.** Enumerate
    `finite_number_reason` (`policy.py:186`), `whole_count_reason` (`:213`), `fill_value_reason`
    (`:233`), `limit_price_reason` (`:265`), `candidate_numeric_reason` (`:286`), `filled_quantity_reason`
    (`:358`) over: `True`/`False` (bool-before-int, `:204`), `"5"`/`None`/`object()`, `NaN`/`±Inf`,
    `0`, negative, fractional (`0.5`), `5.0` (integral float), and a huge value. Confirm each returns a
    reason **or** `None` on every shape (no `TypeError`/`ValueError` escapes), that the `assert
    isinstance(...)` narrowings (`policy.py:225,252,259,280,306,378`) are **not load-bearing** (stripped
    under `python -O` without changing any verdict — each is preceded by the guard that decides), and
    that the `f"{base}_quantity"` / `_price` / `_limit_price` / `_filled_quantity` reason composition
    (`:251,258,377`) never yields a malformed/duplicated code. Find a shape that escapes as a raw
    exception or returns the wrong reason, or prove the family total.
13. **Boundary semantics of the caps.** `risk_limit_reason` uses strict `>` (`policy.py:492,495,499`)
    and `fill_value_reason`/`limit_price_reason` reject `<= 0`. Confirm "exactly at the cap" is
    *allowed* by design (order qty == `max_shares_per_order` passes) and that a fill/limit of exactly
    `0` is rejected. Find an off-by-one at a cap boundary (an order that should breach passing, or an
    exactly-legal order rejected), or confirm the `>` / `<=` choices are deliberate and consistent
    across the family.

**D. CONTROL GATES (`policy.py`, `models.py`) — INV-060, safety-core #10**
14. **The four control predicates' `None`/closed conventions.** `order_intent_block_reason`
    (`None → None`, `:77`), `kill_switch_block_reason` (`None → None`, `:126`),
    `session_submission_block_reason` (`None → "unknown_session"`, `:102`), and
    `order_session_resolution_reason` (`None → "unresolved_session"`, `:154`) treat a missing session
    **oppositely on purpose**. Prove each convention matches its INV: does `kill_switch_block_reason`
    hold **only** `HALTED` (so a `PROTECTION_FLOOR` exit bypasses buys-paused/closed but never the kill
    switch — INV-060), and does `order_intent_block_reason` return `"kill_switch"` for `HALTED` and
    never `None` for a HALTED session (safety-core #10)? Find a session shape where a gate that must
    block returns `None` (intent leaks past the kill switch), or a shape where the narrow carve-out
    widens beyond the one enumerated `PROTECTION_FLOOR`-bypasses-buys-paused exception.
15. **`TradingState.of` dominance + the independent read-model field.** Confirm `of(kill=True,
    pause=True) is HALTED` and `of(kill=False, pause=True) is REDUCING` (`models.py:114-122`), and read
    the `SessionRecord.trading_state` note (`models.py:791-803`): it is deliberately **not** a
    validator-forced derivation of the booleans (so a future stream-degradation `REDUCING` isn't healed
    away into an all-stop bypass). Since the kernel provides `of()` but does **not** enforce the field
    equals it, verify there is no predicate that reads `trading_state` while assuming it always equals
    `of(kill, pause)` in a way a Phase-4 independent `REDUCING` would break. (Forward-looking, like
    INV-075 — flag the reliance, don't manufacture a today-reachable bug if there isn't one.)

**E. MARKET-DATA FEATURES (`features.py`) — "never trade on invalid market data"**
16. **Negative-price admission.** The safety rail (`CLAUDE.md` safety core) lists **negative** market
    data among the values that must halt/quarantine, but the single market-data gate `_finite`
    (`features.py:22`) → `market_data_field_reason` → `finite_number_reason` checks **finiteness only,
    not sign**. Feed `pct_move`, `spread`, `spread_pct` a negative `last_price`/`bid`/`ask`. Does a
    negative price produce a computed feature (rather than `None`)? Then trace: can a negative
    market-data value reach the feature layer (is the market-data ingestion path — REV-0012 — guarding
    positivity before `features` sees it), and can a negative-price-derived feature drive a candidate's
    `suggested_limit_price` or a strategy decision? Note the asymmetry: `protection.py` adds its own
    `<= 0` guard (`:113,:121,:163`), `features.py` relies solely on `_finite`. Find a negative-price
    path that reaches sizing/submission, or prove every `features` consumer adds a positivity guard the
    kernel gate omits.
17. **`session_type_for` totality (`features.py:88`).** Confirm it is total over all datetimes: naive
    input raises `ValueError` (`:118`, never silently assumed UTC/Eastern), weekend → `None` (`:121`),
    the three inclusive-start/exclusive-end windows partition the weekday clock with no overlap and no
    gap (`:124-129`), and the boundary instants (04:00, 09:30, 16:00, 20:00 ET) each resolve to exactly
    one session. Check DST transition days (a "missing"/"repeated" wall-clock hour in `America/New_York`)
    don't throw or mis-classify. Find a datetime that raises unexpectedly or lands in two/zero windows,
    or prove the partition total.

**F. DETERMINISM (all six modules)**
18. **No kernel predicate reads a bare clock or RNG.** The engine-determinism rule (`CLAUDE.md`
    "Testing and CI": no bare `datetime.now()`/`time.time()`, no unseeded randomness) is written for the
    engine — decide whether it binds these leaves, and **regardless**, confirm no *predicate's verdict*
    depends on wall-clock or `uuid4`. `models.py`'s `new_id` (`models.py:30`, uuid4) and `utcnow`
    (`models.py:63`, bare `datetime.now(timezone.utc)`) are model **default_factories** that stamp
    construction-time ids/timestamps only. Confirm no function in `policy.py`/`position.py`/
    `features.py`/`protection.py`/`transitions.py` calls a clock or RNG, and that `apply_fill` derives
    `updated_at` from the input fill's `filled_at` (`position.py:114`), not `utcnow()`. Find an
    output-affecting non-determinism, or prove every module's *decision* is a pure function of its
    explicit arguments.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the CODE against the invariant **statements** in `docs/INVARIANTS.md`, the `CLAUDE.md` safety
core, and the ADRs — **not** against the pinning tests. Per X-002 a test can assert the very bug it
should catch (the on-the-record case, INV-033, lives one hop up in `core.py` but *depends on this
container's* `SELL_INTENT_TRANSITIONS` `APPROVED → EXPIRED` edge). For the transition graph specifically:
probe against the **invariant statement + the graph's stated intent (the inline comments)**, not the
`ORDER_TRANSITIONS` pinning tests.

In scope for this packet (verified present in `docs/INVARIANTS.md` / the ADRs with the meaning cited):
- **Position / fill:** safety-core #8 (submitted ≠ filled), safety-core #9 (only fill events change
  quantity), INV-001 (position derived from fills — `position.py` is the *only* folding site), INV-002
  (never negative — `would_go_negative` / `apply_fill`'s `NegativePositionError`, and the ADR-001
  `allow_short` recording exception), INV-004 (`filled_quantity` == sum of fills — `filled_quantity_reason`
  monotonicity + bound). INV-003 (duplicate fill idempotent) is *keyed* by `Fill.source_fill_id`
  (`models.py:582`) / `ExecutionEvent.dedupe_key` (`models.py:748`) but the dedup **decision** is a
  caller (REV-0006/0007) — verify only that the model carries the key; the dedup logic is not this
  container's.
- **Order lifecycle / transitions:** INV-020 (`SUBMITTED` never without a broker id — the *graph* allows
  `SUBMITTING → SUBMITTED`; the id guard is `plan_transition_order`, REV-0006 — confirm the graph does
  not itself pretend to enforce it), INV-021 (`claim_order_for_submission` is the *sole* entry into
  `SUBMITTING` — provable at the graph level by the absent `CREATED → SUBMITTING` edge), INV-025
  (same-status = no-op — probe 6), INV-075 (latest-lifecycle-event-wins over a transition-guarded log —
  the graph is the "transition-guarded" half; a graph that admits an illegal or un-evented edge breaks
  the projection's ordering guarantee).
- **Control:** INV-060 (kill switch blocks new order intent, one enumerated `PROTECTION_FLOOR`/
  `MANUAL_FLATTEN` carve-out — `order_intent_block_reason` / `kill_switch_block_reason`), safety-core
  #10 (kill switch blocks new order intent). **INV-061** (control setters accept only a real `bool`)
  lives in `require_bool` in `core.py` (REV-0006), **not** this container — `policy.py` has no bool
  coercion; note it as delegated, don't claim it here.
- **CAPI risk gate:** there is **no numbered INV** for the CAPI limits (it is D-016 / the `CLAUDE.md`
  safety rail "invalid market data … must halt or quarantine … never drive sizing or submission" +
  "gate-and-reject, never silently resize"). Probe `risk_limit_reason`/`existing_exposure` against that
  *rail statement*, and against `risk_limit_reason`'s own docstring precondition (`policy.py:477`,
  "production always passes real, validated-positive values from Settings") — if that precondition is
  load-bearing and unguarded in-function, say so.
- **Market-data safety rail:** `CLAUDE.md` safety core, "Invalid market data (stale/NaN/negative/
  out-of-range) must halt or quarantine the flow — never drive sizing or submission." Probe `features.py`
  and the `finite_number_reason` gate against the **negative** and **out-of-range** words specifically.
- **Spine `INV-1..9`** (`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5` — ⚠ a *separate* numbering from
  INV-0xx): INV-1 (only fill events change quantity — `apply_fill`/`ExecutionEventType.FILL` at
  `models.py:363`, the ONLY type the position fold consumes), INV-9 (a position-affecting terminal flows
  through a fill — the `TIMEOUT_QUARANTINE → SUBMITTED`-not-`FILLED` graph choice, `transitions.py:76`).

ADRs in scope (verified relevant): **ADR-001** (broker-authoritative overfill recorded + quarantined,
never hidden or blind-rejected — `apply_fill`'s `allow_short` recording path and `would_go_negative`),
**ADR-002** (ambiguous submit → `TIMEOUT_QUARANTINE`, resolved read-only, never blind-resubmit — the
`transitions.py:71/73` edges and their `→ SUBMITTED`-not-`FILLED` restriction), **ADR-008** (order-status
`ExecutionEvent` provenance: the projector folds by sequence + the transition graph and treats
`source`/`authority` as provenance-only — so `ORDER_TRANSITIONS` *is* the authority half; an illegal or
un-evented edge here is exactly what ADR-008's ordering guarantee can't absorb).

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro + its pasted output**. The bar is high and the repro
  is small: import the predicate, hand-build the input (`Order(...)`, `Fill(...)`, `Position(...)`, a
  `SessionRecord`, a `MarketSnapshot`, a raw `float("nan")`), call it, and `assert` on the return — no
  store, no async, no DB. Paste the script and its output. A finding with no repro is marked
  **"unverified concern"** and **cannot gate**. Where the claim is about how a *caller* uses the verdict
  (a reachability argument, probe 9/11), say so and, if you can, drive it through the caller
  (dual-store via `any_store` where a store is involved).
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran** (the constructed
  inputs and the returns you got). A bare "looks fine / LGTM" with no probe log is a **rejected review**
  for that area — show your work on the clean predicates too (the totality proofs are the point).
- If the code contradicts the Atlas, a docstring's own claim (e.g. `transitions.py:5-6` vs the encoded
  self-loops), or a disclosed known-item, that disagreement is itself a finding (≥ P1) — the
  map/comment is wrong.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** (`work/review/REV-0010/`)
and fill it: the findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters |
Proposed fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a plain statement
of whether **G-A's foundation gate may clear** — i.e. do the leaf predicates + the transition graph +
the model kernel hold up as the correct, total foundation every higher packet delegates to? State
plainly anything you could not verify. Do **not** edit `request.md`; do **not** push code fixes.
