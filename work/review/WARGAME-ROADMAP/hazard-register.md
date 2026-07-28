# WARGAME-ROADMAP — hazard register (beta → live capital)

- **Status:** PROPOSAL. Nothing here is ratified, nothing self-executes. Every verdict is a
  recommendation to the operator.
- **Protocol:** `.ai-os/core/18_WARGAME_PROTOCOL.md`, **FULL scope** (M1–M4). The design drafts ADR
  text, creates three new stateful artifacts (external-assumption register, divergence ledger,
  control manifest) and reuses three existing mechanisms for new purposes (tape recorder → venue
  streams, `work/ledger.jsonl` pattern → divergence ledger, INV registry → capital-critical tier).
  Any one triggers FULL.
- **Kickoff:** `work/queue/WARGAME-ROADMAP-KICKOFF.md` (operator-directed 2026-07-28).
- **Method:** M4a prospective-hindsight brief written inline *before* any agent
  (`M4a-prospective-hindsight.md`), then four fresh-context analysts over partitioned rows, tiered
  and budgeted per `.ai-os/core/17` R7–R9. Every load-bearing analyst claim was then re-verified by
  the planning seat directly against code — see **Verification record** below. Claims that failed
  re-verification were dropped; claims the planning seat's own M4a got wrong are recorded as
  refuted rather than quietly removed.
- **Base:** `14ff12f`, branch `claude/wargame-roadmap-kickoff-2v2tan`.

## Governing principle (ratified in round 1 or amended)

> De-dicing means no obligation may live only in an agent's working memory — every one must exist as
> an artifact a mediocre run cannot skip and a good run cannot silently satisfy. A weak model run
> must produce a loud refusal, never a wrong merge.

Every control below is scored against this and against AUDIT-0003's five-part meta-law: a control is
durable only if it is (1) machine-consumed, (2) semantically complete for the claim it makes,
(3) failure-capable, (4) exercised by a committed negative fixture, (5) current against the guarded
surface.

## The one-sentence version

**The seed map's seven rows are all real hazards, but several of the seed *controls* are themselves
instances of the defect classes they claim to cure** — named individually in the README headline rather
than asserted as a count (the count was refuted in M4b). The cheapest high-yield controls found are not
on the map at all: closing two fail-open branches in the broker adapter, adding one missing
`@invariant()` to a state machine that already generates the fault composition, and dedu&#8203;ping an audit
event on `(order_id, reason)`.

> **M4b correction.** An earlier version of this line claimed the two highest-value controls were a
> one-line `.importlinter` edit and a one-line `pyproject.toml` edit. The first could not have enforced
> the invariant it was sold as closing (F1); the second is unpriced pending a spike (F3). See
> `M4b-refutation.md`.

## Pricing schema

`cost:` S (one bounded WO, ≤1 session) · M (2–3 WOs) · L (program of 4+ WOs / new subsystem).
`buys:` which of AUDIT-0003's S-1..S-8 the control *structurally prevents* (not "helps with"), plus
which meta-law parts it satisfies. `verdict:` RATIFY-NOW · RATIFY-AFTER(prereq) · RE-CUT(how) ·
REJECT(why).

## Verdict summary

| # | Hazard | Hazard real? | Seed control verdict | Cost |
|---|---|---|---|---|
| 1 | R7 conversion cross-product | **Yes — wrong mechanism named** | **RE-CUT** — split by gated surface, not by side; unify the exit-rail twin first | L |
| 2 | Venue-truth asynchrony | **Yes — but two named cells do not exist** | **RE-CUT** — fix two fail-open branches now; register must be machine-joined; tape-recorder extension REJECTED | M (re-cut) / L (as written) |
| 3 | Calendar/clock reality | **Yes — understated; one cell inert** | **RE-CUT** — promote the UTC/Eastern session-identity fix ahead of the generator | M |
| 4 | The shadow→live flip | **Yes** | **RE-CUT** — architecture ADR + producer-independence fixture *before* any promotion language | L |
| 5 | Capital-critical invariants | **Yes — and worse than stated** | **RE-CUT** — a registry tier is blind to the missing row; needs bidirectional coverage | M |
| 6 | Ops/incident reality | **Partly — premise is wrong** | **RE-CUT** — add invariants to the existing generator; do not build a script class | M |
| 7 | Process rot | **Yes — already occurring** | **RE-CUT** — fix the census before building the manifest; cadence REJECTED as specified | M |
| **8** | **Money arithmetic is float** | **New row** | Property-test the fold vs a `Decimal` reference | S–M |
| **9** | **Unconditional startup schema migration on the capital-truth DB** | **New row** | Operator-gated / snapshot-before-migrate | S |
| **10** | **Post-incident evidence is structurally incomplete** | **New row** | `(order_id, reason)` audit dedupe + stuck-in-`Reducing` alert | S |
| **11** | **The store has no I/O-failure semantics** | **New row** | `OperationalError` fault-injection fixtures; fail-closed | S–M |
| **12** | **In-request compensation has no durable convergence arm** | **New row** | Enumerate facade compensations; each names a restart-time arm | M |
| **13** | **The mock/sim is an unratified venue specification** | **New row** | Machine-joined "behaviours deliberately not modelled" list | S |

---

## ROW 1 — R7 conversion cross-product

### Refutation

**The hazard is real; the stated mechanism is not.** "Largest product-space yet" is a plausible story.
The six factors (approval × envelope × single-flight × kill-switch × dual-store × replay) are not new
to R7 — `plan_flatten_position` (`app/store/core.py:2701`) already composes trading-state,
single-flight, envelope preemption and dual-store atomicity in one planner. The product space is not
novel.

What *is* novel, and what the row does not name:

1. **R7 must author a third derivation of a truth that already exists twice, unreconciled.**
   `05-conversion.md:120-122` requires that the new exposure projection agree with the
   `_same_symbol_exit_may_execute` rails. That predicate exists as two independently written
   store-private implementations — `app/store/memory.py:3236` (iterates `self._orders.values()`) and
   `app/store/sqlite.py:4971` (a SQL `SELECT`), three call sites each — whose only agreement
   guarantee is the sqlite docstring's closing words, *"Mirrors memory."* This is a live S-1 that R7
   **inherits**, not one it creates. Verified.
2. **The spec names a function that does not exist.** `project_committed_sell_exposure`
   (`05-conversion.md:79`) has **zero occurrences in `app/`**. Verified.
3. **R7 as specified is an umbrella WO under P-3's own scoring** — it carries ≥2 human-gated
   surfaces: event-log truth (new `SIGNAL_APPROVED` payload fields, `05-conversion.md:133`) and
   schema/DB migration (the R4 correlation DDL, `:135-137`). AUDIT-0003's umbrella bucket ran 13/14
   material findings, 5/14 BLOCK exposure, 8/14 multi-round.

**The seed control is an S-2 instance unless it narrows a type.** The repo already has the "kernel
pattern" the row asks to build: ~14 pure planners and plan dataclasses in `app/store/core.py`
(`FillPlan:172`, `CreateOrderPlan:878`, `FlattenPlan:2647`, `ClaimPlan:3373`, …) consumed 45× in
`memory.py` and 47× in `sqlite.py`. Every one is bespoke, with a per-operation field set and no
common supertype. "Build an effect-permit sink" as written produces the 15th bespoke type — a seventh
place to forget. AUDIT-0003 P-2's own wording is the discriminator: the sink must **accept only** a
shared authorization type. A permit lanes *may* carry is inert (S-3); a permit sinks *structurally
require* is a control. Nothing in the repo can enforce "only" today.

**`AuthorizedVenueEffect` — the permit type — already exists as an illustrative example in
`.ai-os/templates/work-order.md:71` and nowhere else.** The template instructs every seat to justify
an `N/A` lane with a type that has never been built. Verified.

**The permit cannot discharge the obligation the spec calls out by name.** `05-conversion.md:14`
requires no `await` between checks and durable writes. A permit is a data structure; atomicity is a
control-flow property. Nothing a permit carries prevents a seat awaiting between constructing and
consuming it. That needs an AST check — a *different* artifact, and the same one INV-052 has always
needed (see Row 5).

**The reviewer-owned holdout is implementable, but not in its proposed host, and its ownership rule
is unenforceable today.** AUDIT-0003 S-8 reproduces exactly: `tests/r2_conformance_oracle.py:33-57`
imports production modules and calls the production `active_sell_intent_for()` at `:266` and `:527`.
A genuinely independent holdout *is* buildable — `§3a` gives a raw-fact formulation computable from
`app/models.py` records without touching any store query — but **the "implementation seat may not
amend the holdout" rule has no enforcement artifact**: no CODEOWNERS entry, no path check in CI.
Today it is prose in an audit document, which is S-4 by that audit's own meta-law.

**M4a N4 is refuted on tense, which changes the sequencing conclusion.** N4 said R7 "landed with six
independent effect authorities." Wrong: the six already exist and predate R7
(`app/store/base.py:665,731,814,876,1550,1573`). R7 adds a *seventh consumer*. So building WO-E
"before R7" does **not** retrofit the five pre-existing lanes unless WO-E is explicitly scoped as a
migration program — and N4's own fifth-lane failure is the *predicted outcome* of scoping WO-E as an
R7 prerequisite rather than a migration.

### Extension

- **The manual lane keeps the crash shape R7 is forbidden to reproduce.** `05-conversion.md:19-21`
  calls `app/facade/store_backed.py:869-871` "the original F-002 crash shape" and forbids it *for
  signal conversion* — saying nothing about the existing BUY lane, which still has it (verified: the
  split `await gate.approve(...)` / `await create_order_for_candidate(...)` is live). Compensation at
  `:874-911` is in-process only; `revert_candidate_approval` has exactly two call sites, both inside
  that method, and there is no restart-time sweep for a candidate stranded `APPROVED`-with-no-order.
  Meanwhile `05-conversion.md:26` mandates the conversion lane use "the same candidate approval, risk,
  order-mint, claim, adapter path." **An implementer reading "mirror the manual flow" and "be atomic"
  gets a direct contradiction with no recorded resolution — a decision gap on a human-gated surface.**
- **Replay is in the row's title and in none of the obligations.** `05-conversion.md §5` lists nine
  required negative proofs; **none is a replay or projector obligation**, despite `SIGNAL_APPROVED`
  already having projector entries (`app/events/projectors.py:810,817,827,911`) and R7 adding new
  durable payload fields. AUDIT-0003 P-11 covers exactly this and is unratified.
- **The cockpit consumer pin is unimplementable as written.** `05-conversion.md:88-89` forbids a
  UI-side reimplementation and `:123` requires "T1.3 AST checks enumerate … every store/cockpit
  consumer." But `.importlinter` Contract 2 forbids `cockpit → app.*` entirely, so the cockpit must
  receive the projection as an HTTP DTO — **an AST check cannot see a consumer that reaches the
  producer through JSON.** Either the DTO carries the full breakdown (and the check becomes a
  DTO-field-completeness meta-test, the P-8 shape) or S-1 reopens on the UI side.

### Price

- `cost:` **L**. Minimum decomposition: (a) unify the exit-rail twin into one `core.py` pure function;
  (b) the permit type with a mypy-narrowed sink signature **plus** migration of the six existing
  authorities (the migration is the deliverable, not the type); (c) the no-`await`-under-lock AST
  checker (shared with Row 5); (d) R7 re-cut to one gated surface.
- `recurring:` per-WO — every new effect authority constructs a permit through the shared constructor;
  per-CI-run — one AST pass over `app/store/`.
- `buys:` structurally prevents **S-2** *only if* the sink signature accepts only the permit type — a
  mypy-checkable narrowing, and `mypy app/` is already a CI gate (`ci.yml:43`), so failure-capability
  is free. Prevents **S-1** for the exposure quantity, but only after (a). Meta-law **(1)(3)(5)** via
  mypy + import-linter; **(2)** and **(4)** are *not* satisfied by the seed control and must be bought
  separately (a field-set meta-test, and a committed test that calls a sink without a permit).
- `doesn't buy:` atomicity itself; memory/SQLite *behavioural* twin divergence (a shared type does not
  make two `apply` implementations agree — that needs stateful generation); the cockpit DTO problem;
  the stranded-`APPROVED` crash window; replay/parity for the new fields; and the holdout-ownership
  rule, which remains unenforced prose.
- `prerequisite:` (i) the exit-rail twin unified, or R7's agreement pin has no fixed reference and will
  "prove" agreement against whichever twin the test happens to run; (ii) an enforcement artifact for
  holdout ownership; (iii) an operator ruling on the manual-lane contradiction.
- `verdict:` **RE-CUT.** Reject "build WO-E before R7" as a sequencing instruction. Re-cut as
  **WO-E1** unify the exit-rail twin (S — pays down a live S-1 whether or not R7 ships);
  **WO-E2** the permit type + mypy-narrowed sink + committed no-permit negative fixture, migrating all
  six authorities (M–L); **WO-E3** the no-`await`-under-lock AST checker (S, shared with Row 5); then
  R7 re-cut to drop the R4 correlation-schema surface into its own WO.
  **Separately RATIFY-NOW:** the holdout-ownership enforcement artifact (a CODEOWNERS line plus a
  five-line CI check) — the cheapest item in this row.

> **Amendment to a ratified plan.** `work/queue/SIGNAL-SEAT-R5b-TO-D2a-SEQUENCING-PLAN.md:133-165`
> already splits R7 into R7a (buy) / R7b (sell). That split is by **side**. This row's finding is that
> the load-bearing cut is by **gated surface**. Both cuts are compatible, but the surface cut is not
> in the ratified plan and requires operator ratification to add.

---

## ROW 2 — Venue-truth asynchrony

### Refutation

**The hazard is real; two of its four named cells have no attack surface, and what replaces them is
worse because it is invisible rather than merely untested.**

**There is no venue event stream at all.** `TradingStream` / `trade_updates` return **zero hits across
`app/`** (verified); `app/marketdata/alpaca_stream.py` is market data only. Order truth is 100%
**poll-derived** from Alpaca's cumulative `filled_qty` (`app/broker/alpaca_paper.py:1448-1496`),
deduped on the synthetic key `"<broker_order_id>:<cumulative filled_qty>"` (`:1456-1458`). So **"event
ordering" and "duplicate deliveries" — two of the row's four cells — describe a system we do not
have.** What exists instead:

- **Poll aliasing.** N venue executions between two polls collapse into ONE local fill at the broker's
  `filled_avg_price`. INV-9 ("only fill events change position quantity") holds — but *our* fill event
  is a **synthesized delta**, not a venue execution. The fill log is a coarsened projection of venue
  truth and nothing in the repo says so.
- **Monotonicity is assumed and its violation is silently swallowed.**
  `delta = filled_qty - recorded_quantity; if delta <= 0: return []`
  (`app/broker/alpaca_paper.py:1473-1475`, verified). A venue **trade bust or correction** that lowers
  cumulative `filled_qty` produces no fill, no event, no quarantine, no log line — local position stays
  permanently overstated. **This contradicts the safety rail "broker-authoritative overfill/negative-
  position facts are recorded and quarantined — never hidden": the rail is implemented in the
  over-report direction only.** The same root defeats the dedup key — fill to 100 → bust to 50 →
  refill to 100 is deduped away as already-seen.

**M4a N2 is refuted on mechanism and confirmed on outcome — by the opposite direction of travel.**
N2 said a `TIMEOUT_QUARANTINE` reconcile "resubmitted under an id the venue no longer considered
taken." It does not resubmit; `_resolve_timeout_quarantine` (`app/monitoring.py:2805-2953`) is strictly
read-only, exactly as REV-0011 found. The real path is the inverse and is verified:
`app/broker/alpaca_paper.py:1171-1172` reads

```python
if getattr(exc, "status_code", None) == 404:
    return None  # the venue confirms this client_order_id never landed
```

— an unverified belief written as a statement of fact in a code comment. `None` × `max_attempts` →
`resolve_timeout_quarantine(order.id, OrderStatus.REJECTED, reason="not_found_at_venue")`
(`app/monitoring.py:2937-2946`). **If Alpaca's `get_order_by_client_id` has any finite lookup horizon,
or searches a narrower status set than "all", a *filled* order that aged out returns 404 → we mark it
REJECTED → the shares are real, held, untracked, and carry no protective sell.** Position understated,
no envelope, no exit. Same one-line belief, opposite direction, still capital-critical.

**The sharper finding nobody had written down: the duplicate branch is gated on a substring match
against venue prose, and the fallthrough is fail-open.** Verified at
`app/broker/alpaca_paper.py:741-743`:

```python
if code in (409, 422) and ("duplicate" in exc_msg or "client_order_id" in exc_msg):
```

while `:804-808` classifies `400/401/403/404/422` as `TerminalBrokerError` — "definitively rejected,
never reached the book." **422 appears in both branches; the only disambiguator is a substring match on
the venue's error prose.** Every test drives the duplicate branch with a hand-made message built to
satisfy the predicate (`tests/test_alpaca_paper_submit.py:288,398,427,456,696,767`), and `:299-307`
commits a pin that a 422 worded "no buying power" *is* terminal. So a duplicate rejection worded without
either magic substring classifies a **live venue order as never-submitted**, and the local order is free
to be redriven. The 409 case is fail-safe (falls through to `AmbiguousBrokerError` at `:822`); **the 422
case is fail-open.** This is the highest-yield concrete finding in the war-game and it is one `or` away
from N2's loss.

**Both seed controls are instances of the classes they claim to cure.**

- *"Extend the tape-recorder pattern to venue event streams"* — **not an extension; a new subsystem,
  and the current spec forbids it.** `docs/spec/replay/tape-format.md:3-5` states the recorder "never
  receives a `BrokerAdapter` or `StateStore`, and therefore cannot submit, cancel, or replace orders or
  change position/fill/envelope truth"; `app/recorder/runner.py:24-40` constructs only
  `create_market_data_service`. Handing it a `BrokerAdapter` **inverts the exact isolation property the
  spec sells** — and per the finding above there is no venue event stream to record, so one would first
  have to build order-event ingestion.
- *"A register of assumptions" as a table* — **prima facie S-4.** A markdown table of Alpaca beliefs is
  not machine-consumed, cannot fail, and rots. The precedent is in this repo: REV-0011 recorded exactly
  this obligation as prose in a closed disposition and it was never run. **A second table will do what
  the first sentence did.** The `verified-against-recorded-reality` bit is only failure-capable if
  something reads it, and nothing in CI can read a live-venue probe without a committed corpus or a
  credentialed job. Neither exists.

**S-5 decay, found free.** REV-0011's anchors no longer resolve: `alpaca_paper.py:245/255/270-285/305-332`
cited in `work/review/REV-0011/disposition.md:17-30` now land inside `_validate_ack_scope`; the verified
surface moved to `:617-836` and `:1140-1235`. **The packet that flagged this hazard can no longer be
replayed against the code it cleared.**

### Extension

1. **Fill-after-*terminal*-cancel is unobservable** (narrowed from the analyst's broader claim — see
   Verification record). `app/monitoring.py:3707` polls only `_OPEN_STATUSES`; `CANCELED` is terminal
   (`app/transitions.py:154`); the mass report is `get_orders(status=OPEN)`, which by definition
   excludes a venue order that filled and closed. The **`CANCEL_PENDING`** lane *is* covered
   (`tests/test_sim_chaos.py:81`, fill correctly wins); the post-terminal lane enters through no lane.
2. **`get_orders(status=OPEN)` is unpaginated** — `app/broker/alpaca_paper.py:1250-1255` passes no
   `limit`. Two consumers depend on report completeness: absent managed rows route to the 404 belief
   above, and **external/unmanaged venue exposure is derived solely from this report**
   (`app/reconciliation.py:1128-1156`), so truncation silently under-reports unmanaged exposure.
3. **`AmbiguousBrokerError` on submit is raised from a bare `except Exception`** (`:828-836`) — safe,
   but an SDK *parse* bug and a network timeout become the same fact; no consumer can distinguish
   "possibly live" from "definitely never serialized."
4. **The sim models duplicate-submit as silent idempotent success**, and
   `tests/test_sim_chaos.py:249` asserts this is "the way the real `AlpacaPaperAdapter` does" it. The
   real adapter *raises* and then recovers. The sim reproduces the outcome, not the mechanism — so the
   substring gate, `_validate_ack_scope` and `_validate_ack_state` are unexercised through sim too, and
   **that docstring asserts a fidelity the code does not have.**

### Price

- `cost:` **M** re-cut (three WOs); **L** as written, and it hits a spec prohibition.
- `recurring:` one register row per new external call, plus a CI check that every `status_code ==` /
  message-substring branch in `app/broker/` names a register id.
- `buys:` structurally prevents **S-8** (the register forces the premise out of the oracle into a named,
  refutable row) and **S-3** (a register id no branch references, or a branch with no id, fails the
  build — the check cannot be inert). Meta-law **(1)(3)(5)** via the join, recomputed against the
  guarded file every push; **(4)** cheaply — one committed fixture adding an unregistered `status_code`
  branch, asserted RED.
- `doesn't buy:` **(2) semantic completeness is unreachable without a live probe.** A register row
  proves a belief is *named*, never that it is *true*. The verified bit is a data field, not a control,
  until a credentialed paper-venue probe exists and its output is a committed fixture. Also does not buy
  the post-terminal fill-after-cancel lane — that needs an architectural lane, not a register row.
- `prerequisite:` **a ratified decision on whether any credentialed live-paper probe may run.** If no,
  the register's fifth column must be renamed `unverifiable-in-beta` and those rows stay `ASSUMED`
  permanently — a legitimate answer, but one that must be ratified rather than defaulted into.
- `verdict:` **RE-CUT.** **(2a) RATIFY-NOW** — the register as a keyed machine-joined artifact **plus
  the two fail-open branch fixes** (the 422 message-gate and the 404⟹never-landed inference). Bounded,
  capital-critical, no venue access needed. **(2b) RATIFY-AFTER(live-probe decision)** — the verified
  bit and recorded-corpus fixtures. **(2c) REJECT as scoped** — "extend the tape recorder to venue event
  streams" contradicts `tape-format.md:3-5` and presumes a stream that does not exist; if venue-event
  capture is wanted it is its own ADR and its own subsystem.

---

## ROW 3 — Calendar/clock reality

### Refutation

**Hazard confirmed and understated. One of its four cells is largely inert, one is not a calendar cell
at all, and the seed control has nothing to attach to.**

**There is no market-calendar source anywhere.** Session classification is pure time-of-day arithmetic,
implemented **three independent times** — `app/features.py:91-133`, `app/sellside/session.py:44-63`,
and `app/recorder/models.py:58-70` (whose own docstring says *"Classify an observed timestamp without
consulting external calendars"*). None consults `GetCalendarRequest` or any holiday table. **This is a
live S-1 instance — the same truth derived three times — that AUDIT-0003's S-1 section does not list.**

**The half-day defect is not untested; it is committed as a passing assertion of the wrong answer.**
`tests/test_features.py:148-160` (verified in full):

```python
def test_early_close_half_day_is_a_documented_known_limitation(self):
    """2026-11-27 is the day after Thanksgiving — a real early-close half-day
    (regular session ends 13:00 ET, not 16:00) ... misclassified as REGULAR
    even though the exchange is closed."""
    assert session_type_for(self._et(2026, 11, 27, 14, 0, dst=False)) is SessionType.REGULAR
```

**M4a N3 is refuted in the most dangerous way: a test *did* choose a half-day, and chose to certify the
misclassification.** It is honestly documented as a known limitation — but it is green, it will stay
green forever, and **a calendar generator built over the existing cells would re-certify it.** The
mitigation both texts lean on ("staleness surfaces it") is itself an assumption that converts a calendar
fact into a latency inference, and cannot distinguish a half-day from a halt from a websocket drop.

**DST is largely inert for session classification — refuting a quarter of the row.** US transitions
occur 02:00 ET Sunday; Sunday returns `None` at `app/features.py:124` before any time-of-day comparison,
and `session_context`'s arithmetic is aware-datetime subtraction on `ZoneInfo`. No session window spans
a transition, and `tests/test_features.py:125-131` already parametrizes both offsets.

**DST bites somewhere else entirely, and that place is unguarded.** Session *identity* is the **UTC**
date — `app/store/memory.py:831` and `app/store/sqlite.py:1951` both compute
`today = utcnow().date().isoformat()` (verified) — while session *type* is Eastern. **The session record
therefore rolls over at 19:00 ET in winter and 20:00 ET in summer**, while the after-hours window runs
16:00–20:00 ET. For roughly four and a half months of the year there is a **one-hour interval
(19:00–20:00 ET) in which the durable session record has already rolled to tomorrow while the Eastern
trading session is still live** — and for the rest of the year that interval is zero. A restart at
19:30 ET in January and at 19:30 ET in July land in different session records from identical clock
inputs. That is precisely N3's "a restart disagreed about which session it was in," and DST is what
makes it non-obvious.

**This is CONTRADICTED, not merely assumed.** `app/policy.py:437-441` already names it (verified):
*"`get_current_session` auto-mints a fresh, permissive session on UTC date rollover, so gating
submission only on the current session let a kill-switched order from a prior session slip through to
the broker (a Rule 8 bypass)."* **One** consumer was hardened. Every other reader of `session_date` —
per-session counters, `app/api/routes_review.py:35`, envelope-per-session logic — was never enumerated.
Textbook **S-2: the rail exists on the lane where the bug was found.**

**Existing "rollover" tests dodge the calendar entirely.** `tests/test_submission_gate.py:32-33`'s
`_force_rollover(store)` *mutates stored session dates* rather than choosing a timestamp — so rollover
is proven against a hand-set artifact, never against `utcnow()` at 19:30 ET on a January Tuesday. N3's
diagnosis holds with a wider escape hatch than stated: the test bypasses the clock altogether.

**The seed control is non-actionable as written.** "Calendar-generator dimension in obligation matrices
for session-touching WOs" presupposes a checker-evaluable definition of "session-touching" and a
calendar source to generate cells *from*. Neither exists. Without a source the generator can only
reproduce the weekday/time-of-day cells already covered — **re-certifying the half-day misclassification,
S-8 reproduced by the control meant to cure it.** And "halts" are in the row's title but there is no halt
concept in the codebase at all: every `halt` hit in `app/` is the kill-switch `HALTED` state, and
`app/marketdata/alpaca_stream.py:328-334` mentions a security halt only as something deliberately
*indistinguishable* from a quiet symbol.

### Extension

1. **The three session copies are only pairwise drift-checked.** `app/sellside/session.py:7-8` claims a
   pin so "the **two** copies cannot drift silently." `app/recorder/models.py:58-70` is a third, with its
   own vocabulary (`premarket`/`regular`/`after_hours`/`closed` vs `SessionType`). **A tape recorded
   during a half-day is labelled `regular` in the corpus — so Row 2's "replay real paper-session corpora
   as fixtures" would import the calendar defect into the fixture layer**, making the replay oracle share
   the premise it exists to test.
2. **Envelope expiry is wall-clock, not session-relative.** `app/monitoring.py:1800-1874` drives expiry
   off durations and `app/reconciliation.py:1636-1642` picks `extended_hours` purely from
   `session_type_for(submission_now)`. At 13:00 ET on a half-day, `session_type_for` returns `REGULAR`,
   `extended_hours=False`, and a limit order is submitted into a **closed exchange**, where it sits
   unfilled holding envelope capacity until wall-clock expiry. N3's "envelope stayed ACTIVE past the
   close" is reachable.
3. **The market-data layer got the boundary right and the store layer got it wrong, in the same repo.**
   `app/marketdata/alpaca_stream.py:98-108` uses Eastern for the reseed boundary and documents why —
   *"a UTC-date comparison would fire up to an hour early for EST."* Nobody joined that reasoning to
   `session_date`.
4. **`ZoneInfo("America/New_York")` resolution is unpinned.** Three modules construct it; nothing asserts
   tzdata presence or version. Missing tzdata raises at import (fail-loud, fine); **stale** tzdata fails
   silently.

### Price

- `cost:` **M** — (1) one canonical session/calendar module with a real source, deleting the other two
  copies; (2) `session_date` consumer enumeration + the Eastern-vs-UTC decision; (3) the generator, which
  is only possible after (1).
- `recurring:` a calendar fixture refreshed per year, plus every session-touching test parametrized over
  ~6 date classes instead of 1.
- `buys:` structurally prevents **S-1** (three→one implementation) and **S-2** (the `session_date` sweep
  `app/policy.py:437-441` skipped). Meta-law **(1)(3)(4)** for the generator — the negative fixture is
  trivially strong here: assert `2026-11-27T14:00 ET` is **not** REGULAR, i.e. `test_features.py:148-160`
  inverted. **(5)** free once there is one implementation to guard.
- `doesn't buy:` **(2) semantic completeness — and this is the trap.** A generator proves the classifier
  right on the cells you enumerated; it says nothing about halts (not modelled at all) or LULD/circuit
  breakers. **It also cannot surface the DST session-identity defect**, which is a UTC-vs-Eastern
  decision, not a generator dimension.
- `prerequisite:` **a ratified decision on the calendar source.** `alpaca-py` ships `GetCalendarRequest`,
  but using it is a **new external call inside the adapter boundary**, another register row, and it makes
  the classifier network-dependent in a layer that is currently pure and IO-free. A committed static
  calendar table with an expiry date is the alternative and is probably right for beta. Either way it is
  an ADR, and the generator cannot be specified until it lands.
- `verdict:` **RE-CUT into three, with one piece promoted.** **(3a) RATIFY-NOW, ahead of the generator**
  — the `session_date` UTC-vs-Eastern decision and its consumer enumeration: an already-known
  Rule-8-adjacent defect with a written-down root cause, needing no calendar source, and it is the cell
  N3 actually describes. **(3b) RATIFY-AFTER(calendar-source ADR)** — the generator dimension plus
  deleting two of the three copies. **(3c) RE-CUT(drop "halts")** — halts are a market-data-semantics gap
  (`alpaca_stream.py:328-334`), not a calendar cell; leaving them in Row 3 guarantees they get "covered"
  by a generator that structurally cannot see them.

---

## ROW 4 — The shadow→live flip

### Refutation

**Hazard real. Seed control cannot be ratified as written, because the mode it gates does not exist.**

`LIVE_SHADOW` has **zero code substrate**, verified three ways: `app/config.py`'s `Settings`
(`:176-304`) declares no execution-mode field; the only mode-adjacent knob is
`broker_adapter: str = "auto"` validated to `{auto, mock, alpaca}` (`:220-221, 585-589`);
`app/broker/factory.py:24-64` constructs only `MockBrokerAdapter` or `AlpacaPaperAdapter`. The ladder
`PAPER → LIVE_SHADOW → LIVE_MICRO → LIVE_CONTROLLED → LIVE_PROD` exists in prose at
`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md:337`, and "all live modes disabled by config" describes
config that does not exist to disable anything. `CLAUDE.md:27` cites LIVE_SHADOW as an acceptance
criterion as though it were operative.

**The architecture document already names the exact trap.**
`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md:320-321`: *"determinism holds inside the seam (engine +
simulated adapter). Real Alpaca and real wall-clock are outside it — **live-shadow soak against paper
is a separate activity; don't conflate.**"* The warning is prose; nothing enforces it. **M4a N1 is
confirmed**: ratify promotion-gate ADRs now and an implementer under schedule pressure can satisfy
their letter by diffing the paper adapter against itself — structurally zero divergence, not
empirically zero.

**The divergence ledger is unbuildable today and cannot reuse the ledger it is named after.**
`work/ledger.jsonl`'s confirmed schema is `{id, title, status, disposition, commit, date, reason}` — a
human-authored work-order log, structurally unrelated to a machine-classified runtime trading-divergence
record. "Reuse the ledger pattern" means building a new artifact.

**"N clean sessions, zero class-A" is not measurable.** Counting sessions is; *classing* a divergence
is exactly the judgment the gate exists to remove, and no A/B/C taxonomy exists anywhere in the repo.
The nearest coded precedent, `app/reconciliation.py`'s `STAGE_DIVERGENCE`, classifies broker-vs-local
*fact* divergence as binary open/resolved and does not generalise.

**Nothing in the repo measures latency of anything** in the kill/flatten path — verified across `app/`,
`tests/`, and `docs/INVARIANTS.md`. INV-060/061/080 are atomicity and ordering invariants, not timing
SLAs. The only latency-measuring infrastructure is `tests/performance/r2_scaling_gate*.py`, which
targets throughput. And a single-operator paper fire drill cannot reproduce the order-book pressure
and broker duress that make kill latency matter at real capital — a drill number would be a
local-process round trip under artificial conditions.

### Extension

- No CI *reader* for a divergence table. `check_ledger.py`/`check_work_order_disposition.py` are the
  precedent: a gate needs a machine reader, not just a writer.
- The ladder cell is itself two phases ("emulated→released, log-only") that the seed control collapses
  into one flip. The ADR must decide whether emulated→released is separately gated.
- CAPI limits (`app/config.py:287-291`) and protection settings (`:294-304`) are unaddressed for a
  "released, log-only" leg — do they apply at real notional, or does shadow need its own ceiling?
  Nothing answers this.

### Price

- `cost:` **L** — new subsystem: adapter lane + store schema (+ `_migrate` + dual-store parity) + event
  type (+ projector/replay per P-11) + comparator + CI reader + cockpit surface.
- `recurring:` every promotion cycle re-runs an unaudited classification step unless the taxonomy and
  producer-independence rule ship first.
- `buys:` **as specified, none of S-1..S-8 structurally** — an ADR alone enforces nothing. Built with a
  code-enforced producer-independence rule and a machine-read taxonomy it would structurally prevent
  **S-8** at this gate. Meta-law: (1) only once a CI reader exists; (2)(3)(4) fail until "divergence"
  and "class-A" are code-defined and negative-fixture-proven; (5) moot pre-implementation.
- `doesn't buy:` production-condition kill latency — a beta drill's number does not transfer to live
  duress. This residual survives any version of this control and belongs in the phase-gate ADR as a
  stated limitation, not a solved problem.
- `prerequisite:` LIVE_SHADOW must exist as a real second lane with a **code-enforced** (not
  doc-enforced) producer-independence rule.
- `verdict:` **RE-CUT.** Do **not** "ratify promotion-gate ADRs NOW." Ratify instead, in order:
  (a) an ADR specifying LIVE_SHADOW's actual architecture — *what independently produces each side of
  the comparison* — at the file:line rigor of the ADR-009 precedent; (b) a **committed negative
  fixture proving the comparator refuses same-producer inputs**; only then (c) the soak-count and
  class-A promotion language. Drafts in `phase-gate-ADRs.md` are written in exactly this dependency
  order and each states what it does not yet bind.

---

## ROW 5 — Capital-critical invariants

### Refutation

**The hazard is real and materially worse than the row states: two of its three named invariants do
not exist, and the seed control is structurally incapable of detecting a missing row.**

- **No *account-level daily-loss or drawdown* control exists.** `daily_loss`, `max_daily`, `drawdown`,
  `daily_pnl` return zero hits across `app/` — but note that is an **account-level-daily search only**,
  and the conclusion originally drawn from it was wrong.
  > **CORRECTED after M4b F2 — the original text claimed "there is no P&L-based control anywhere in the
  > system." That is false.** `app/protection.py` is an always-on **per-position hard stop-loss**:
  > `stop_loss_pct: float = 0.08` (`:48`), `floor_price = average_price * (1.0 - stop_loss_pct)`
  > (`:66-70`), producing a full-exit `FloorBreach`. It ships enabled by default —
  > `protection_enabled: bool = True` (`app/config.py:295`) under the comment *"On by default: a beta
  > operator shouldn't have to opt in to a stop-loss"* (`:293`). Unrealized loss measured against
  > average cost and enforced by an order is a P&L-based control by any ordinary reading.
- **The capital-limit inventory is six knobs, not three:** `capi_max_shares_per_order`,
  `capi_max_notional_per_order`, `capi_max_total_exposure`, `capi_trading_allowlist`
  (`app/config.py:286-290`), plus `protection_stop_loss_pct` and `protection_limit_buffer_pct`
  (`:297,:300`). Row 5's coverage checker and ADR-017 gate E6 are scoped against this corrected set.
- **What remains true, and is the real finding:** there is no *account-level* loss ceiling. Per-position
  loss is floored at ~8% **except through the floor's own failure modes** — gap-through, a halted book,
  and no evaluation at all on a stale feed (XA-13/XA-14) — none of which this row originally named. So
  the platform's aggregate loss is bounded only by the exposure ceiling times the number of positions,
  and the per-position floor is only as good as the market-data path that feeds it.
- **Position limits have no invariant.** The registry's 55 entries contain no row asserting "an order
  exceeding `capi_max_total_exposure` is refused." The limit is enforced in code
  (`app/facade/store_backed.py:855-866` pre-check, authoritative in the planner) but is not an
  invariant — so it sits **outside every registry-based control the roadmap proposes, including P-14.**
- **Therefore the seed control is category-mismatched.** "A registry tier where the meta-law is
  mandatory per row" is a control *over rows that exist*. It cannot fire on max-daily-loss, because
  there is no row to tag. It upgrades ceremony on the invariants we already remembered to write and is
  blind to the one the row's own title names first. **The control this hazard needs is a coverage
  obligation, not a tier**: "every configured capital limit names an INV, and every capital-tier INV
  names its config key" is bidirectional, machine-checkable, and **fails today at row zero.**

**INV-051 / INV-052 confirmed exactly as W-1 reports.** `docs/INVARIANTS.md:410-412` — INV-051's pin
is literally *"no dedicated test (a real deadlock hangs the suite, which is its own signal) — reviewed
structurally."* `:420-422` — INV-052's is *"structural."* Both fail meta-law (1), (3) and (4) outright.

**M4a N5 is refuted on mechanism and confirmed on outcome — and the gap between them is the finding.**
N5 blamed "a broker call under the store lock." Not reachable at this tip: `app/store/*.py` holds no
adapter reference, and `app/broker/alpaca_paper.py` has no backoff loop (a 429 is classified
pre-flight-safe-transient and raised for the next tick, `:803-820, :1121-1123`). **But the reason is
convention, and the enforcement hole is precise:** `.importlinter` Contract 3
(`engine-is-venue-agnostic`) lists eleven `source_modules` — `app.monitoring, app.reconciliation,
app.policy, app.position, app.protection, app.strategy, app.strategy_loop, app.features,
app.transitions, app.events, app.approval` — and **`app.store` is not among them**
(`.importlinter:70-81`, verified). Nothing stops `app.store.memory` importing `app.broker.adapter` and
awaiting it inside `async with self._lock`. A mediocre run adding "just poll the venue here" to a store
method passes ruff, mypy, lint-imports and the whole suite. **N5's incident is one careless edit away,
and every control that should stop it is inert.** That is a better finding than the incident as written.

**Kill latency is not one quantity.** The architecture has three intervals and only the first is
covered: **(a) intent-block ≈ 0** — `set_kill_switch` and `claim_order_for_submission` serialize on the
same store lock (`app/store/base.py:899-903`); **(b) in-flight completion — unbounded and *ratified***
— `docs/INVARIANTS.md:441-444` states a `MANUAL_FLATTEN` minted while Active "may finish under Halted
(accepted D-P2 claim semantics)"; **(c) sweep — one `poll_cadence_seconds`**
(`app/monitoring.py:2150`). At live capital the operator's model is "I hit the button, nothing more
goes out." Interval (b) falsifies that and is recorded only as a subordinate clause inside INV-060.

**INV-060's quantifier outruns its pins.** The text claims "*every* new order-intent path remain[s]
blocked in `Halted`" — a universal over the six effect authorities — and pins it with three named tests
covering the flatten and direct-manual lanes only (`docs/INVARIANTS.md:428-452`, verified). The
envelope activation and stage lanes (`app/store/base.py:1550,1573`) are not among them, and R7 adds a
seventh consumer under the same universal claim. **P-14 as written would not catch this** — INV-060
*does* name ≥1 enforcing test, so it passes. A linkage checker that counts to one cannot see the gap.

### Extension

- **Kill-switch holds produce at most one audit event per order, ever.** `app/monitoring.py:2406-2421`
  dedupes `ORDER_SUBMISSION_BLOCKED` on `order.id` alone, while the reason is carried in the payload
  and distinguished at decision time (`app/policy.py:895,929-930`). An order previously held for
  `buys_paused` and later held by a kill-switch engagement **writes no event recording the kill-switch
  hold.** Post-incident, the event log cannot answer "which orders did the kill switch stop?" — the
  first question a live-capital incident review asks. Verified. Fix: dedupe on `(order_id, reason)`.
- **The manual-flatten backstop shares the sequential monitoring tick with everything it backstops.**
  `05-conversion.md:70-71,130` lean on manual flatten as "the independent human fallback," but its
  completion path runs inside one straight-line `await` chain (`app/monitoring.py:2318-2353`): submit →
  redrive → quarantine-resolve → reconcile → envelope-cancels → recovery → mass reconcile. A slow
  `_reconcile_open_orders` delays the next flatten sweep. **"Independent" is a claim about authority,
  not scheduling, and nothing records the distinction.** `app/config.py:301-303` already contemplates a
  dedicated fast loop for protection and notes beta keeps it in the tick; the same reasoning applies to
  flatten and is unwritten.
- **Resolved, not a defect:** the CAPI limits are buy-side only *by deliberate documented design* —
  `app/store/core.py:2505-2507`: "No CAPI risk gate and no kill-switch/session block here — a
  protective exit reduces risk and its submission is gated separately at claim time." An analyst
  flagged this as a possible worsening; it is not.

### Price

- `cost:` **M**, and cheaper than the seed control implies because the two highest-value items are
  checker-sized. **WO-1:** add `app.store` to `.importlinter` Contract 3 (**one line**) + the INV-052
  no-`await`-on-adapter-under-lock AST checker + its negative fixture. **WO-2:** bidirectional
  capital-limit↔INV coverage check, and author the missing rows — a position-limit INV, a
  kill-effect-latency INV separating intervals (a)/(b)/(c), and an explicit `NO-CONTROL` sentinel row
  for max-daily-loss so its absence is a *registry fact* rather than an oversight. **WO-3:** the
  `(order_id, reason)` audit dedupe.
- `recurring:` per-CI-run for two sub-second checkers; per-WO only when adding a capital limit or an
  effect authority.
- `buys:` structurally prevents **S-4** for INV-052 — the rule stops being prose and becomes a build
  failure, exactly the transition W-2 identified as separating rules that bit from rules that failed.
  Prevents **S-2** for the store's broker-isolation lane, because an import contract covers *modules*,
  not diffs, and therefore covers lanes nobody thought to look at. Meta-law (1)(3) yes via
  `lint-imports` (already `ci.yml:51`); (4) yes and cheaply — the negative fixture is a two-line module
  awaiting an adapter inside a lock; (5) yes for the import contract (module-scoped, cannot go stale),
  partial for the AST checker, which must assert the lock idiom's *shape*, not merely search for it.
  **(2) is where the AST checker is weakest and must be scoped honestly:** it can prove "no `await` on
  an `app.broker` symbol inside `async with self._lock`"; it cannot prove "no `await` on anything slow."
- `doesn't buy:` **any max-daily-loss control** — the sentinel row makes the absence auditable, not the
  system safe. That is a product feature and belongs in the shadow→small-capital gate. Also not bought:
  interval (b) shrinkage (a ratified semantic; changing it is an ADR); measurement of interval (c)
  (needs Row 4's instrument); INV-051 reentrancy (a deadlock still hangs the suite rather than failing
  it — a separate, larger analysis).
- `prerequisite:` **an operator decision on whether max-daily-loss is a beta requirement or a pre-live
  requirement.** This is the fork the row turns on and the seed map does not ask it. Pre-live → the
  sentinel row suffices now and the control lands with the phase-gate ADR. Beta → WO-2 grows a real
  P&L subsystem and the cost becomes L.
- `verdict:` **RE-CUT** into three artifacts. **(i) RATIFY-NOW, but split and re-priced after M4b F1** —
  the INV-052 **AST checker + committed negative fixture** carries the entire invariant claim and is
  **M-cost, not S**. Adding `app.store` to `.importlinter` Contract 3 is a *separate, marginal*
  direct-edge guard against `app.store.* → app.broker.{alpaca_paper,mock,sim}` and is **explicitly not an
  INV-052 control**: Contract 3 forbids only concrete adapters, deliberately permitting the abstract port
  (`.importlinter:61-64, 82-88`), and import-linter has no concept of a call site, an `await`, or a lock
  context. **(ii) RATIFY-NOW** — bidirectional capital-limit
  ↔ INV coverage with `NO-CONTROL` sentinels: its first run converts "we forgot max daily loss" from an
  omission into a tracked fact. **(iii) RATIFY-AFTER(a lane registry exists)** — the P-14 quantifier
  upgrade: a universal-claim INV must enumerate its lanes and name a pin per lane. That lane registry is
  the same one P-2 needs, so **Rows 1 and 5 should buy it once.**
  **REJECT as currently sequenced:** the per-row mutation-certificate requirement. ADR-015's job is
  still `MAX_SURVIVORS=999` with no recorded baseline, so mandating certificates now mandates producing
  an artifact that structurally cannot fail — S-3, manufactured on purpose.

---

## ROW 6 — Ops/incident reality

### Refutation

**The hazard is partly real; the row's stated premise — "prose runbooks decay" — does not match this
repo, which has no prose runbooks to decay.** A repo-wide search found no runbook document for
crash-mid-submit, partition, outage or rate-limit. Recovery is embedded in the hot path and already
tested:

- `app/main.py:126-165` lifespan calls `run_startup_reconcile` (`app/monitoring.py:2168-2200`) before
  the monitoring loop, forcing Reducing-until-parity on **every** real restart. It cannot bit-rot the
  way a doc can, because it runs on every deploy rather than during a drill.
- ADR-002's WO-0113 addendum documents the crash-mid-submit design with each behaviour named to a
  present test file (`tests/test_wo0113_lifecycle_closure.py`, `test_wo0113_monitoring_failclosed.py`,
  `test_wo0113_submit_acceptance_fallback.py` — all confirmed present).
- Rate limits are genuinely handled: `app/broker/alpaca_paper.py:803-820, 968, 1011, 1121-1123` plus a
  query budget (`app/config.py:117-122, 634-638`, default 200/min matching Alpaca's documented limit).

**Building "recovery as executable scripts" would therefore create a second, independently maintained
implementation of what `app/monitoring.py` already does — a manufactured S-1.**

**M4a N7 is refuted on its central claim, and the refutation is cheaper than the original.** N7 implied
no generative infrastructure exists for composed faults. False: `tests/test_lifecycle_state_machine.py`
already contains a Hypothesis `RuleBasedStateMachine` (`:127`) whose rules include `crash_after_claim`
(`:256`), `divergent_fill_and_reconcile` (`:297`) and `set_kill_switch` (`:503`), running at
`max_examples=60, stateful_step_count=30` (`:849`). **All three of N7's fault ingredients are already
generatable in the same machine.** What is missing is the *invariant*: `kill_switch` appears exactly
**twice** in that file — both at the rule definition — and in **none** of the ten `@invariant()` methods
(`position_never_negative`, `filled_quantity_bounded_and_whole`, `order_filled_matches_recorded_fills`,
`no_candidate_stranded_approved`, `no_sell_intent_stranded_approved`,
`at_most_one_active_sell_intent_per_symbol`, two `correlation_id_matches_*`,
`every_order_has_a_resolvable_session`, `no_live_untracked_broker_order`). All verified.
**The gap is one invariant, not a new artifact class.**

N7's narrower claim survives: composed-fault coverage is thin. Of ~15 tests in
`test_wo0113_monitoring_failclosed.py`, exactly one touches `kill_switch`
(`test_kill_cannot_mask_reconcile_gate_establishment_failure:827`) and it is a static precondition, not
a live interleaving.

### Extension

- **The store has no I/O-failure semantics.** No `sqlite3.OperationalError`, "database is locked", or
  disk-full handling exists anywhere in `app/store/sqlite.py` (verified: zero hits). ADR-002's entire
  crash-mid-submit design assumes the store is always writable, and ADR-003's Halted-vs-crash
  distinction has no path for "the store itself cannot be written."
- **`run_startup_reconcile` is explicitly best-effort and can leave the system in `Reducing`
  indefinitely** with only a log line (`app/monitoring.py:2178-2181, 2200`) — no operator-facing alert.
- **The live trade-update stream reconnect has never run against anything real.**
  `app/monitoring.py:2212-2216`'s own docstring states there is no real trade-update stream yet and
  reconnect wiring is deferred to real credentials. The outage recovery path is untested against a live
  feed by construction.

### Price

- `cost:` **M** — three bounded WOs, not a subsystem: (a) new invariants on the existing state machine
  for the kill-switch/reconcile/crash composition; (b) SQLite I/O-failure handling and fixtures;
  (c) a stuck-in-Reducing alert path.
- `recurring:` none beyond ordinary suite runtime if built inside the existing generator. A *separate*
  runbook-script artifact class would instead add a standing parallel-implementation tax every time
  `monitoring.py`'s real recovery logic changes.
- `buys:` in the re-cut form, prevents **S-8** (no new scenario-certifying script that proves the
  scenario instead of the machine) and **S-1** (no duplicate recovery implementation). Meta-law (1) free
  (already in pytest), (3) by construction, (5) automatically — it exercises live code, not a frozen
  fixture. The literal "executable scripts" reading satisfies none of these better and risks S-1/S-5.
- `doesn't buy:` infra-layer outage — SQLite corruption, disk-full, extended venue outage — unaddressed
  by either form. This residual survives.
- `prerequisite:` none for the invariant path; the generator exists today.
- `verdict:` **RE-CUT** — replace "recovery procedures as executable scripts with fixtures" with
  "recovery **invariants** added to the existing `RuleBasedStateMachine`, scoped first to the
  kill-switch/reconcile/crash composition, plus dedicated SQLite I/O-failure fixtures." This is
  strictly cheaper than the seed control and strictly more durable.

---

## ROW 7 — Process rot

### Refutation

**Hazard real and already occurring. Both seed controls fail — and the manifest would certify roughly
half its own census incorrectly if built today.**

- **"AUDIT-000N as standing per-phase-gate cadence" is not a control anywhere.** The phrase appears in
  exactly one place in the repository: the kickoff itself (`:25`). No cron, no Routine, no template
  field, no CI check would force AUDIT-0004 to happen. AUDIT-0001/0002/0003 were each triggered by an
  ad hoc operator directive (`AUDIT-0003:4`). **A cadence that fires only when a human remembers is a
  ritual, not a control** — it fails meta-law (1) and (3) by construction, since nothing detects a
  *missed* cadence. M4a N8 understates the case: the roadmap would not need three months to rot,
  because no mechanism could have kept it current at all.
- **The manifest itself does not exist**, so N6 is a prediction rather than an observation — but the
  prediction is already borne out by controls that exist today without a manifest to launder them:
  - **`mutation-nightly.yml` is the N6 example, live.** `MAX_SURVIVORS: "999"` (`:27`) and an explicit
    `REPORT-ONLY` marker (`:38`). It can fail only on tool crash or empty mutant population, never on a
    regression. (AUDIT-0003's `|| true` description is **stale** — the round-2 repair replaced it with a
    real run-state guard at `:44-52`. The ratchet is still inert at 999.)
  - **A large, well-built negative-fixture suite is invisible to CI.** `.ai-os/scripts/tests/`
    (`test_scripts.py`, `test_promoted_scripts.py`, `test_phase3_checks.py`) holds ~30 real red/green
    pairs covering six checkers. **`pyproject.toml:5` sets `testpaths = ["tests"]`**, and no workflow
    ever points pytest at that directory. Verified. This is the control-plane's own S-3: the checkers
    look enforced, but the tests proving they *can* fail sit one directory outside collection.
  - **Three checkers are never invoked at all.** `check_fable_done.py`, `check_work_order_scope.py` and
    `check_mcp_spec.py` appear in **no workflow** (verified). `check_fable_done.py` is also weak on its
    own terms — substring matching rather than parsing the declared evidence grammar, exactly
    addendum-01 C1.

**Census verdict:** a manifest built today by asking "does this obligation have a green CI line" would
certify ~9 controls. A closure checker built to AUDIT-0003's own standard — "does the negative fixture
run where CI actually looks" — would find at least four of those have their only failure-capability
proof outside `testpaths`, and one whole job architecturally incapable of failing. **A manifest built
before fixing the census would be an N6 instance on day one.**

### Extension

- **No closure checker for the closure checker.** The manifest checker is itself a script needing a CI
  slot and a negative fixture; recursion must terminate, and the row does not say where. Precedent shows
  the terminal step — put the fixture under `tests/`, not `.ai-os/scripts/tests/` — is exactly the step
  already missed for six checkers.
- **ADR-015's baseline handoff is prose.** It says to record the baseline in
  `pkl/architecture/testing-model.md` — a manual doc handoff with no checker confirming it happened.
  This is precisely the queued-and-unratified P-5 gap.
- **The checker family has no staleness signal of its own.** `check_pkl.py` flags stale *pkl pages*;
  nothing flags a stale *checker* whose predicate stopped matching current file shapes after a rename —
  the INV-082 class from W-1.

### Price

- `cost:` **M** — three WOs: (1) fold `.ai-os/scripts/tests/` into CI collection and wire the three
  unexecuted checkers; (2) build the manifest + closure checker against the corrected census; (3) give
  `mutation-nightly.yml` a real baseline and ratchet per ADR-015's own stated obligation.
- `recurring:` one CI minute per PR, plus the standing discipline that every new gate ships a manifest
  row **and** a CI-collected negative fixture in the same commit.
- `buys:` prevents recurrence of **S-4** (a rule not machine-reachable at guard time) and **S-3** (an
  inert pin recorded as active); satisfies meta-law (1) and (4) — *conditional on* fixing the
  `testpaths` orphaning first.
- `doesn't buy:` **(2) semantic completeness** — a manifest row pointing at a real CI line says nothing
  about whether that line checks the *right* property; S-8 is untouched. And it does not buy **(5)
  currency** by itself: a manifest built once still needs a re-verification cadence, which has no
  mechanism.
- `prerequisite:` fix `testpaths` and the `MAX_SURVIVORS` sentinel **first**. Building a manifest over
  the uncorrected census would certify the two worst existing instances of the defect class it exists to
  catch.
- `verdict:` **RE-CUT** into three: **(a) RATIFY-NOW** — an S-cost WO folding the orphaned
  `.ai-os/scripts/tests/` suite into CI collection and wiring the three unexecuted checkers. This kills
  the concrete N6 instances that already exist and is, with Row 5's Contract-3 line, the cheapest
  high-yield item in the war-game. **(b) RATIFY-AFTER(a)** — the manifest + closure checker.
  **(c) REJECT as specified** — the "AUDIT-000N cadence": a prose cadence with no trigger is not a
  control at any price. Replace with a CI-visible staleness ratchet (days since the last `AUDIT-*`
  artifact, failing the build past a threshold), which is repo-local and survives any session, in
  preference to an operator-side scheduled Routine, which does not live in the tree.

---

## New rows — the eighth-row hunt

The kickoff asked for "the missing eighth row." Six survived anchoring and verification. They are
ranked by how directly they reach capital. Rows 8 and 9 are, in the planning seat's judgement, more
urgent than three of the seven seed rows.

### ROW 8 — Money arithmetic is float, in the one function permitted to move position truth

`Position.cost_basis` is `ResponseSafeRequiredFloat = 0.0` (`app/models.py:957`, verified), and
`fold_fills` — the single source the safety core permits to change position quantity — accumulates it
with repeated float arithmetic over a position's entire life: `cost_basis + fill.quantity * fill.price`
on every BUY, `cost_basis * (new_quantity / old_quantity)` on every partial SELL, then
`average_price = cost_basis / quantity` (`app/position.py:83-110`, verified). `quantity` is correctly
`int`, which *masks* the issue: a reviewer checking "is quantity exact" passes right over the float
accumulator beside it.

**Why hard for AI seats:** tests use 2–3 fills; drift needs many fills over a long-lived position —
exactly the shape a live soak first produces for real and no synthetic suite naturally generates.
**Control:** property-test `fold_fills` over long randomized fill sequences (the Hypothesis machinery
already exists) against a `Decimal`-computed reference fold. **Price:** `cost:` S for the property test,
M if the `Decimal` migration lands with it; `buys:` a defect class **not covered by S-1..S-8 as written**
— silent numeric drift in a value that gates risk; `doesn't buy:` it detects drift, it does not fix it;
`verdict:` **RATIFY-NOW** for the property test; the `Decimal` migration is
**RATIFY-AFTER(a phase-gate ADR)** since it touches a capital-critical field.

### ROW 9 — Unconditional startup schema migration on the capital-truth database

`SQLiteStore.initialize()` calls `self._migrate(conn)` unconditionally on every process start
(`app/store/sqlite.py:616-620`, verified), and `_migrate` performs `ALTER TABLE orders RENAME TO
orders_old; CREATE TABLE orders (...)` (`:1030-1033`) and the same rename-and-rebuild for `fills`
(`:1220-1224`), detected by `PRAGMA table_info` column-presence heuristics — with no operator
confirmation, no dry run, and no backup step, against whatever file `STATE_STORE` points at.

**Scoping this claim honestly:** CLAUDE.md's human-gated surface "schema/DB migration" is best read as a
*development-time* gate — an agent may not author a migration without approval — and by that reading
this is not a current violation. **At paper scale it is ordinary practice.** The hazard is specific to
the destination: an unconfirmed destructive table rebuild on the database holding real position truth,
with no snapshot, is a pre-live gap. **Why hard for AI seats:** the code is carefully commented and
idempotent, so it reads as safe; "runs automatically with no gate" is an orthogonal property the
comments never address. **Control:** a pre-migration snapshot plus a ledgered migration event, and an
operator-confirmation path once a non-test database is in use. **Price:** `cost:` S; `recurring:` one
confirmation per genuine schema change (3–4 in the project's whole history); `verdict:` **RATIFY-NOW**
as a pre-live precondition, and name it explicitly in the shadow→small-capital gate.

### ROW 10 — Post-incident evidence is structurally incomplete

Two independent instances. (a) Kill-switch holds are audited **once per order, ever**:
`app/monitoring.py:2406-2421` dedupes `ORDER_SUBMISSION_BLOCKED` on `order.id` alone while the reason
lives in the payload, so an order previously held for `buys_paused` and later held by a kill-switch
engagement **writes no event recording the kill-switch hold** — the event log cannot answer the first
question a live-capital incident review asks. (b) `run_startup_reconcile` is explicitly best-effort and
can leave the system in `Reducing` indefinitely with only a log line
(`app/monitoring.py:2178-2181, 2200`), with no operator-facing alert.

**Control:** dedupe on `(order_id, reason)` with a negative fixture asserting two distinct events with
distinct `payload["reason"]`; a durable event + cockpit alert once `Reducing` persists past N reconcile
cycles. **Price:** `cost:` S; `buys:` **S-4** — it converts an evidence obligation into a tested
behaviour; `verdict:` **RATIFY-NOW.** This is the cheapest row here and the one whose absence is only
discovered *after* it is needed.

### ROW 11 — The store has no I/O-failure semantics

Zero handling for `sqlite3.OperationalError`, "database is locked", or disk-full anywhere in
`app/store/sqlite.py` (verified). ADR-002's entire crash-mid-submit design assumes the store is always
writable; ADR-003's Halted-vs-crash distinction has no path for "the store itself cannot be written."
**Control:** fault-inject the connection to raise mid-transaction during submit and reconcile, and
assert fail-closed (`Reducing`/`Halted`), never silent loss. **Price:** `cost:` S–M; `verdict:`
**RATIFY-AFTER(Row 6's invariant WO)** — same test surface, buy them together.

### ROW 12 — In-request compensation has no durable convergence arm

`app/facade/store_backed.py:874-911` compensates the split-await BUY lane in-process only;
`revert_candidate_approval` has exactly two call sites, both inside that method, and there is no
restart-time sweep for a candidate stranded `APPROVED`-with-no-order. A SIGKILL in that window strands
it permanently. This generalizes: **every in-request compensating transaction in the facade has the same
unbounded window and none is enumerated.** **Control:** enumerate them as a registry; each must name a
restart-time convergence arm in `app/monitoring.py` or carry a recorded operator waiver — the same
enumerate-then-require shape P-7 proposes for actor/clock threading, which suggests **one registry
mechanism could serve P-2, P-7 and this row.** **Price:** `cost:` M; `verdict:` **RE-CUT into the shared
lane-registry WO** that Rows 1 and 5 also need.

### ROW 13 — The mock/sim is an unratified venue specification

Every integration test above the adapter is an assertion about `MockBrokerAdapter`, whose behaviour is
strictly more benign than the real venue on at least four axes: duplicate submit succeeds silently
rather than raising (`app/broker/mock.py:98-106`), cancel never grows fills (`:138-144`), replace is
always clean (`:159-182`), and the derived open-order report is always complete and unpaginated. `sim.py`
narrows some of this — it genuinely exercises fill-after-cancel-*request* and orphan recovery — but
`tests/test_sim_chaos.py:249` asserts its duplicate-submit idempotency models "the way the real
`AlpacaPaperAdapter` does" it, when the real adapter *raises and recovers*. **The imagined broker is a
concrete committed file that nobody has diffed against reality.** **Control:** a machine-joined list, in
the mock/sim itself, of every register id it deliberately does **not** model — so "the mock cannot
produce this venue behaviour" becomes a machine-readable fact and the omitted behaviours have a named
home in `sim.py`'s hostility profile. **Price:** `cost:` S; `buys:` **S-8** directly; `verdict:`
**RATIFY-NOW alongside 2a** — it is the register's other half.

## Verification record (planning seat, direct against code)

Per `.ai-os/core/17` R6, every load-bearing analyst claim was independently re-verified before being
admitted here. **17 of 17 checked claims held.** Verified: `project_committed_sell_exposure` absent from
`app/`; no `daily_loss|max_daily|drawdown|daily_pnl` anywhere in `app/`; `.importlinter:70-81` omits
`app.store`; two `_same_symbol_exit_may_execute` implementations at `memory.py:3236` / `sqlite.py:4971`;
the forbidden split-await live at `store_backed.py:869-871`; `AuthorizedVenueEffect` only in
`work-order.md:71`; `pyproject.toml:5` `testpaths = ["tests"]` with `.ai-os/scripts/tests/` holding three
fixture modules; `check_fable_done.py`/`check_work_order_scope.py`/`check_mcp_spec.py` in no workflow;
`mutation-nightly.yml:27` `MAX_SURVIVORS: "999"` and `:38` REPORT-ONLY; `cost_basis:
ResponseSafeRequiredFloat` (`models.py:957`) with repeated float ops in `position.py:83-110`;
`sqlite.py:616-620` unconditional `_migrate` and `:1030-1033`/`:1220-1224` destructive
`RENAME`+rebuild; zero `OperationalError` handling in `sqlite.py`; `LifecycleMachine` rules at
`test_lifecycle_state_machine.py:127/256/297/503` with `kill_switch` in no invariant;
`SPINE_EXECUTION_ARCHITECTURE_v2.md:320-321` don't-conflate warning; `monitoring.py:2406-2421` dedupe on
`order.id` alone; INV-060's universal quantifier vs three named pins (`INVARIANTS.md:428-452`);
INV-051/052 pin text (`:410-412`, `:420-422`).

**Corrections made to inherited text.** Two AUDIT-0003 statements are stale at this tip and are not
repeated here: the conformance oracle is invoked **once** (`ci.yml:97`), not twice; and
`mutation-nightly.yml` no longer uses `|| true` — it has a real run-state guard, though the ratchet
remains inert at 999.

A further **13 of 13** venue/calendar claims verified: no `TradingStream`/`trade_updates` anywhere in
`app/`; `delta <= 0: return []` (`alpaca_paper.py:1473-1475`); the 404⟹never-landed comment
(`:1171-1172`); 422 in both the duplicate branch (`:741-743`) and the terminal branch (`:804-808`);
`get_orders` unpaginated (`:1250-1255`); `test_early_close_half_day_is_a_documented_known_limitation`
asserting `REGULAR` (`tests/test_features.py:148-160`); `utcnow().date().isoformat()` as session
identity (`memory.py:831`, `sqlite.py:1951`); the Rule-8 UTC-rollover diagnosis (`policy.py:437-441`);
three session-classification copies; `sim.py`'s chaos seam and `tests/test_sim_chaos.py`.

**Three analyst claims corrected by verification** — recorded because a register that hides its own
corrections is the artifact class this war-game exists to prevent:

1. **A2's "fill-after-cancel is structurally unobservable" is too broad.** `tests/test_sim_chaos.py:81`
   (`test_late_fill_after_cancel_pending_wins_chaos_1`) genuinely covers a fill arriving while the order
   is `CANCEL_PENDING`, and the fill correctly wins. **Narrowed** in Row 2 to the post-terminal-`CANCELED`
   lane only. A2 had declared `sim.py` and `test_sim_chaos.py` unread; its not-falsified list is what made
   this catchable.
2. **A2's XA-19 is confirmed and sharpened.** `tests/test_sim_chaos.py:249` models duplicate submit as
   silent idempotent success while claiming to model "the way the real `AlpacaPaperAdapter` does" it —
   the real adapter raises and recovers. The sim reproduces the outcome, not the mechanism; that docstring
   asserts a fidelity the code does not have. Promoted to new Row 13.
3. **A1's CAPI speculation refuted.** A1 flagged that CAPI limits might be buy-side only in a way that
   "would materially worsen" Row 5. Checked: `app/store/core.py:2505-2507` documents the asymmetry as
   deliberate — "a protective exit reduces risk and its submission is gated separately at claim time."
   Not a defect.

**Two items remain open and are NOT claimed as verified.** (i) Whether `alpaca-py`'s `get_orders`
wrapper injects a default `limit` — `alpaca` is not importable in this container, so XA-08's
`CONTRADICTED` class rests on Alpaca's documented REST default of 50, not on reading the SDK. One grep
in a bootstrapped `.venv` closes it. (ii) The reconcile query budget's numeric value versus Alpaca's
published rate limit (XA-28) — the mechanism was found, the number was not compared.

## What this war-game refuted about its own M4a

Recorded rather than deleted, because the protocol's value is in the refutations:

| Cause | Verdict |
|---|---|
| **N1** — the flip that was never a flip | **Confirmed**, and strengthened: the architecture doc already contains the don't-conflate warning (`:320-321`) with nothing enforcing it |
| **N4** — kernel arrived after the surface | **Refuted on tense.** The six authorities predate R7; R7 is a seventh consumer. This inverts the sequencing conclusion — WO-E must be scoped as a *migration*, not an R7 prerequisite |
| **N5** — broker call under the store lock | **Refuted on mechanism, confirmed on outcome.** Not reachable today; but `.importlinter` Contract 3 omits `app.store`, so nothing prevents it. The enforcement hole is the real finding |
| **N6** — manifest certifying existence | **Confirmed in advance** — the pattern is already live in `mutation-nightly.yml` and the orphaned fixture suite, without a manifest to launder it |
| **N7** — the runbook that ran | **Refuted.** The stateful generator already exists with all three fault rules; the gap is a single missing invariant. Cheaper diagnosis than the narrative |
| **N8** — the war-game itself rots | **Confirmed and understated** — the proposed cadence has no trigger mechanism of any kind |
| **N2** — assumption true in paper, false in live | **Refuted on mechanism, confirmed on outcome — by the opposite direction of travel.** The reconcile does not resubmit; it infers `REJECTED` from a 404. Same belief, inverse path, still capital-critical. Had the narrative gone into a fixture unchecked, the fixture would have pinned the wrong lane — an S-8 in the making |
| **N3** — the calendar cell nobody generated | **Refuted, and worse than written.** A test *did* choose the half-day and certifies the misclassification as correct (`tests/test_features.py:148-160`). And DST does not bite the classifier at all — it bites session *identity* (UTC date vs Eastern type), which a calendar generator structurally cannot see |
