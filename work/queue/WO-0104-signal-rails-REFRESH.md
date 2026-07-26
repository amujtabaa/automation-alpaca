---
type: Work Order
title: "Signal Seat R6 — signal rails: token bucket, non-refilling invalid budget, quarantine epoch, human release"
status: DRAFT
work_order_id: WO-0104
supersedes: "work/queue/WO-0104-signal-rails.md (draft 2026-07-11, pre-migration)"
wave: signal-seat reconciliation ladder, step R6
model_tier: strong (LOCAL Codex — single-writer store surface + human-gated release action)
predecessors: [WO-0139 (R5b-2 — MUST be merged and REV-0043 dispositioned first)]
successors: [R7a/R7b (conversion), D-2a joint enablement]
review: "REV-0044 required (human-gated: single-writer store mutation, event-log truth, operator release action)"
wargame: "FULL per .ai-os/core/18 — M1/M2/M3/M4a below; M4b dispatched (rev-2 folds findings)"
round: "Round 3 of 4 — R6 then [NAMED GATE] then R7a"
filter_risk: MED
---

# WO-0104 (refresh) — Signal Seat R6: the rails

> **Refresh rationale.** The 2026-07-11 draft predates ADR-009's acceptance (2026-07-21), the
> threat model's GAP-08, the war-game protocol, R5a's rails seam, and R5b-1/R5b-2's ingest and
> enforcement surfaces. It is superseded rather than edited. **Its behaviour/test contract survives
> substantially intact** and is carried forward below; what changes is the architecture, the paths,
> and the settings inventory.

R5a made construction refuse without conforming rails. R5b-1 added authenticated ingest. R5b-2 made
every sensitive request require the operator credential. **R6 makes the rails real**: a per-producer
token bucket, a non-refilling invalid/conflict budget, a quarantine epoch with exactly one opener, and
a human release that resets both.

**The crown jewel:** the budget debit and the terminal event append are **one atomic operation**. If
they can separate, a producer either overspends its budget under concurrency or leaves the counter and
the event log permanently disagreeing — and the event log is the source of truth.

---

## The architecture, and why it is store-centric (the central correction)

`03-rails.md:44-54` requires that deciding availability, consuming the slot, and appending the terminal
event be **one store operation** — "a single memory lock hold / one SQLite transaction (the same
single-writer discipline as `app/store/base.py`)", with the exhausting append co-appending
`PRODUCER_QUARANTINED` in that same op, and crash-atomicity giving "**either** the complete
{debit + event} **or** neither, in both stores."

**A rails provider object consulted by the route cannot satisfy that** — it does not hold the store's
lock or transaction. Asking whether a slot is free and *then* writing is the exact race the requirement
exists to forbid.

The two spec-mandated checks therefore land in **different layers**, along seams that already exist:

| Step | Check | Layer | Why |
|---|---|---|---|
| **2** (pre-body) | **Token bucket** — every authenticated ingest debits, decided *before* the body is read (`03-rails.md:17-22`) | the **`SignalRails` Protocol** provider (`app/facade/signal_rails.py`) | Body-blind by A-4; needs no atomicity with a terminal append because a rate breach writes no per-request event |
| **4** (atomic) | **Invalid/conflict/DOA budget** — re-check-and-debit atomic with the terminal event, exhausting append co-opens the epoch | **inside `store.ingest_signal`** | Atomicity is only achievable where the write happens |

**The step-4 seam already exists and was pre-wired a rung ago.** `store.ingest_signal` already takes
**`cycle_budget_limit: int` as a required parameter** (`app/store/base.py:1329`, mirrored in
`memory.py:5531` and `sqlite.py:7606`), already stamps it into event payloads
(`app/store/core.py:5904-5905,5957`), already validates it (`:6032-6045`), and already performs the
atomic terminal append. What is missing is the **consumed count** and the debit itself.

**Consequences (all four are planning-relevant):**
1. **R6 does not modify R5b-1's ingest route.** The route already reaches the store through one facade
   call; the debit lands beneath it. *(This corrects the sequencing plan's C-3, which asserted R6 would
   have to re-open that route.)*
2. **`check_ingest` stays exactly what it claims to be** — body-blind step-2 admission. No second
   Protocol method, and `is_conforming_rails` needs no change.
3. **R6 is predominantly a store change** — the largest, most safety-critical code in the repo
   (`core.py` 6184 / `memory.py` 6112 / `sqlite.py` 8322 lines), with mandatory dual-store parity.
4. **Ordering still holds:** R6 after R5b-2, because the release route is operator-key-only and
   browser-reachable (`03-rails.md:174,182-183`) — both R5b-2 deliverables. The *entanglement* argument
   is withdrawn; the *dependency* argument stands.

---

## M1 — Assumption ledger / decision block

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`;
no `ASSUMED` line is pre-checked.

- [x] **D-R6-1 HARD predecessor gate.** R5b-2 merged to master **and REV-0043 dispositioned**. Verify:
      `git ls-tree master tests/test_route_authorization_matrix.py` returns a blob **and**
      `work/review/REV-0043/disposition.md` exists. Else **STOP**. Branch `codex/signal-r6-rails` from
      the merged master. — TRACED(ratified round-3 gate).

- [x] **D-R6-2 Two-layer architecture** exactly as the table above: token bucket in the provider at
      step 2; budget debit **inside `store.ingest_signal`**, atomic with the terminal append. Do **not**
      add a debit method to `SignalRails`; do **not** attempt the debit from the route or facade.
      — TRACED(`03-rails.md:44-54`; `app/store/base.py:1329`; `app/facade/signal_rails.py:26-31`).

- [x] **D-R6-3 Allowed-paths amendment — the day-one STOP in the old draft.** `app/server.py:33`
      already contains `from app.signals_rails_impl import build_production_rails` and **that module
      does not exist**, yet the old draft's `allowed_paths` omitted it. **Authorized:** create
      `app/signals_rails_impl.py` (the production provider factory the sanctioned launcher already
      expects). `app/server.py` itself stays **forbidden** — the import line is already correct, so no
      edit is needed there. Everything else in the old draft's path list carries forward (`app/events/**`,
      `app/models.py`, `app/config.py`, `app/main.py`, `app/store/**`, `app/api/**`, `app/facade/**`,
      `cockpit/**`, `.importlinter`, `tests/**`).
      — TRACED(`app/server.py:33` verified; module absent; old draft `:43-54`).

- [x] **D-R6-4 Settings to add (absent today, verified).** `signal_rate_limit_per_hour: int = 60` and
      `signal_rate_burst: int = 10` appear **nowhere** in `app/`. The old draft claimed R6 must add the
      budget/TTL settings — **wrong, R5a already landed those** (`app/config.py:200,202`, validated at
      `:477-487`). Add the two rate settings with hard caps and validation in the same style; keep
      `validate_signal_seat_settings` the single validation point.
      — TRACED(`03-rails.md:11-15`; grep: absent; R5a `config.py:200,202`).

- [x] **D-R6-5 Budget representation = a DURABLE RAIL RECORD, not event-derived.** `03-rails.md`
      permits either ("if the budget is event-derived, the atomic append **is** the debit; if it is a
      separate rail record, its update shares the same lock/transaction"), but it also requires that
      **"both the pinned limit AND the consumed/remaining count are durable producer-rail state"**
      (archive REV-0025-F-004). A rail record makes the cycle's **pinned** limit explicit (so a
      mid-cycle `Settings` change cannot retroactively move the ceiling), makes the consumed count
      readable for the `/api/producers` view without a scan, and avoids an O(events) count on every
      ingest. Event-derived counting would satisfy atomicity but not the pinning or the read path.
      **Chosen: a durable per-producer rail record** (pinned limit, consumed count, epoch state),
      updated inside the same lock/transaction as the terminal append.
      — TRACED(`03-rails.md:44-54` + the durable-state clause; archive REV-0025-F-004).

- [x] **D-R6-6 ⚠ THE HAZARD: `PRODUCER_QUARANTINED` has TWO writers, and the spec allows exactly one
      per epoch.** A **rate breach** opens an epoch from the step-2 path (`03-rails.md:17-22`: "the
      breaching request itself gets HTTP 429 and is folded into the coalesced audit (it does NOT get a
      per-request `SIGNAL_QUARANTINED`)"), while **budget exhaustion** opens it from the step-4 atomic
      path (`:55-66`, co-appended with the exhausting terminal event). Both must honour "**exactly one
      `PRODUCER_QUARANTINED` per epoch**; subsequent rejects are write-free." Therefore the **epoch
      record is the single point of truth**, and *both* paths must perform an **atomic check-and-set**
      against it — never a read-then-write. Required pins: concurrent rate-breach + budget-exhaustion
      against the same producer yields **exactly one** opener; and a rate breach during an already-open
      epoch is **write-free**.
      — TRACED(`03-rails.md:17-22,55-66`; `02-lifecycle.md:50`).

- [x] **D-R6-7 Release resets BOTH rails.** `PRODUCER_RELEASED` closes the epoch and resets **both**
      the §1 token bucket **and** the §1a non-refilling budget — "else the producer re-quarantines on
      its next ingest" (`02-lifecycle.md:51`). Release is operator-only and idempotent-safe: unknown
      producer → 404, not-quarantined → 409.
      — TRACED(`02-lifecycle.md:51`; `03-rails.md §5`; spec `04 §2` producers routes).

- [x] **D-R6-8 The old draft's behaviour contract carries forward VERBATIM.** Its six lettered budget
      proofs across both stores are spec-faithful and are the acceptance core. Re-anchor them to the
      D-R6-5 rail record; do not re-derive them.
      — INHERITED(old draft `:69-88`, judged spec-faithful in the sequencing-plan war-game).

- [x] **D-R6-9 No pre-authored RED corpus exists — the planner specifies the decisive pins.** Unlike
      R5a/R5b-1/R5b-2, no staged rails corpus exists (the staged `test_signal_quarantine_totality.py` is
      the **ingest** boundary, labelled WO-0102). Codex authors the corpus from this WO. **Every
      decisive pin must be mutation-checked by the implementer** — revert the control, prove the pin
      goes RED, restore — and the red-green evidence pasted. This replaces the missing corpus as the
      anti-inert-pin control; REV-0041's inert pin and REV-0043's F-1 both arose exactly here.
      — TRACED(staging tree; REV-0041/REV-0043 findings).

- [x] **D-R6-10 The no-zero-budget-gap consumer: the A-2 conversion check.** The exhausting append
      co-opens the epoch specifically so there is "**no zero-budget-but-un-quarantined gap** in which
      the A-2 conversion check would still approve an exhausted producer's already-RECEIVED signals."
      R6 owns the epoch state that check will read; **R7 owns the check itself.** R6 must therefore
      expose the epoch/quarantine state through the facade in a form R7 can consult, and must **not**
      implement conversion. Pin the state transition, not the approval refusal.
      — TRACED(`03-rails.md:55-66`).

- [x] **D-R6-11 Release route is operator-only and browser-reachable — the R5b-2 dependency.**
      `POST /api/producers/{producer_id}/release` is operator-key-only with a negative test that a
      producer key cannot self-release, and the control must be reachable from the cockpit
      (`03-rails.md:174,182-183`). **Add it to the R5b-2 authorization matrix's literal `REQUIRED` set**
      in the same change (`tests/test_route_authorization_matrix.py`) — R5b-2 deliberately left it as a
      deferred member. Also add `GET /api/producers` if landed here (D-R5b2-15 deferred it to R6).
      — TRACED(`03-rails.md:174,182-183`; REV-0043 result §deferred `REQUIRED` members).

- [x] **D-R6-12 Flag stays OFF; flag-off byte-equivalent.** No new mounted route under flag-off; no
      existing test edited; `harness/bootstrap.py` green. D-2a still requires R7.
      — INHERITED(D-2a).

- [x] **D-R6-13 Inherited register items from REV-0043.** **F-6:** the fixed
      `"operator:authenticated"` principal is not losslessly separable once producer principals exist —
      R6 introduces producer-attributed rail state, so state the principal/producer attribution scheme
      explicitly. **F-8:** `StoreBackedSignalFacade.list_signals` cannot push the status filter down and
      materializes the full scope; R6's rails bound ingest but **not** this read — decide whether to add
      a limit here or record it as still-open.
      — INHERITED(REV-0043 `result.md` F-6/F-8).

---

## M2 — Lifecycle totality: the quarantine epoch

| Edge | Driver | Anchor / requirement |
|---|---|---|
| **birth (rate)** | step-2 bucket empty at any authenticated ingest | one `PRODUCER_QUARANTINED`, request gets 429, **no** per-request `SIGNAL_QUARANTINED` (`03-rails.md:17-22`) |
| **birth (budget)** | step-4 append consuming the **last** slot | co-appends its terminal event **and** the single opener in the **same** op (`:55-66`) |
| **birth collision** | both paths concurrently | atomic check-and-set on the epoch record ⇒ **exactly one** opener (D-R6-6) |
| **open → reject** | any further ingest while quarantined | **write-free** boundary reject (403), coalesced audit; no new events |
| **open → released** | operator `POST /api/producers/{id}/release` | `PRODUCER_RELEASED`; resets **bucket and budget**; carries saturated `rejected_count` + epoch window |
| **terminal** | none — an epoch only ends by human release | budget "resets only on human release, never by refill" (`03-rails.md`) |
| **crash mid-debit** | process death between decide and append | **{debit + event} or neither**, both stores (`:44-54`) |

**Precondition proof required:** no path may append a terminal event without the debit, and none may
debit without appending — in either store, under concurrency, and across restart.

---

## M3 — Consumer inventory + control-action sweep

| Consumer | Class | Control-action finding |
|---|---|---|
| `store.ingest_signal` (all three impls) | **affected — the core change** | (1)/(3): a non-atomic debit overspends under concurrency or desynchronises the counter from the log. |
| `cycle_budget_limit` event-payload stamping (`core.py:5904,5957`) | **affected** | (3): the stamped limit must be the **pinned** cycle limit, not a live `Settings` read, or replay diverges from live. |
| The step-2 provider (`check_ingest`) | **affected** | (2): a provider that also tried to debit would double-charge or race the store. Bucket only. |
| Epoch record | **affected — two writers** | (1)/(3): D-R6-6. Read-then-write yields two openers. |
| R7's A-2 conversion check | **unknown → resolved by D-R6-10** | (4) *stopped too soon*: without the co-opened epoch, an exhausted producer's RECEIVED signals stay approvable. |
| `/api/producers` read + release route | **affected** | R5b-2's matrix `REQUIRED` set must gain them (D-R6-11), else the ratchet fails — by design. |
| Cockpit release control | **affected** | Browser-first: the required human action needs a browser path (`03-rails.md:182-183`). |
| SQLite schema | **affected — HUMAN-GATED** | The rail record is durable state ⇒ a schema/migration change. **Its own approval gate** (see below). |
| Existing suite + `harness/bootstrap.py` | **unaffected (must prove)** | Flag-off byte-equivalence. |
| `tests/test_route_authorization_matrix.py` | **affected** | Shared with R5b-2/R7 — extend `REQUIRED`, do not restructure. |

---

## M4a — Prospective hindsight

1. *"A producer got more strikes than the budget allowed."* → non-atomic debit under concurrency (D-R6-2/-5).
2. *"The counter said spent but no event explained why."* → crash between debit and append (M2 crash edge).
3. *"Two `PRODUCER_QUARANTINED` events opened one epoch."* → read-then-write on the epoch record (D-R6-6).
4. *"A released producer re-quarantined on its next request."* → release reset the budget but not the bucket (D-R6-7).
5. *"An exhausted producer's stale signals were still approvable."* → zero-budget gap (D-R6-10).
6. *"Replay diverged from live."* → a live `Settings` read instead of the pinned cycle limit (M3 row 2).
7. *"Memory passed, SQLite overspent."* → dual-store parity gap (D-R6-8).
8. *"The rails corpus was green and proved nothing."* → no staged corpus; mutation-checked pins (D-R6-9).
9. *"A producer released itself."* → release not operator-only (D-R6-11).
10. *"R6 shipped `/release` unauthenticated."* → R5b-2's ratchet catches it, **by design** (D-R6-11).
11. *"The session stalled on day one."* → the `app/signals_rails_impl.py` path gap (D-R6-3).

---

## ⚠ HUMAN-GATED: SQLite schema change

The durable rail record is a **schema/migration change**, which CLAUDE.md lists as a human-gated
surface. This is **not** covered by the WO's ratification. Codex must **STOP and request approval**
with the proposed DDL before creating or altering any table/column, exactly as R4's
`signal_records` DDL was gated. Do not self-authorize.

## ⚠ BUILD HAZARDS

1. `app/server.py:33` imports `app.signals_rails_impl` — create that module (D-R6-3); do **not** edit
   `server.py`.
2. `is_conforming_rails` (`app/facade/signal_rails.py:36-58`) checks a bound async `check_ingest` with
   arity 1. The production provider must satisfy it **and** be rejected if it is a class, sync, or
   wrong-arity — R5a already pins that; do not weaken it.
3. `cycle_budget_limit` is already a **required** kwarg of `store.ingest_signal` in all three impls —
   R6 changes behaviour *inside*, not the signature, unless the war-game says otherwise.
4. The matrix test is shared by R5b-2/R6/R7 — **extend** `REQUIRED`; do not restructure it.
5. The old draft's `allowed_paths` also omitted `app/signals_rails_impl.py`; use D-R6-3's list.

## Filter-safety clause (rung risk: **MED**)

Authorized defensive engineering on the operator's own local, paper-only application. No external
target, no network probing, no credential access, no live trading.

The sustained-arrival proof is the trigger risk here. **Say** *paced-arrival accounting* ·
*sustained-arrival conformance test* · *budget-exhaustion accounting defect* · *non-atomic transaction
boundary* · *unauthorized-role acceptance*. **Avoid** "flood attack", "DoS test", "hammer the endpoint",
"exhaust the server". Report at the defect level: cause · impact · affected local files · fix ·
pass/fail evidence. No reusable bypass procedures. Do **not** run open-ended adversarial discovery —
**REV-0044's Claude seat is the sanctioned adversarial net**.

## Gate battery

`ruff check .` · `ruff format --check` on R6-owned files · `mypy app/` · `lint-imports` · the R6 corpus
+ full suite · `python -m pytest -q tests/r2_conformance_oracle.py` ·
`pytest -q tests/test_wo0113_repair_scaling.py` · `python harness/bootstrap.py` · all three hygiene
scripts (`check_work_order_disposition`, `check_ledger`, `check_pkl`).

## Stop conditions

**Any schema/migration DDL (approval-gated, above)** · any accepted-text conflict not recorded here ·
any need to weaken an existing assertion (esp. R5a's rails-presence pins or R5b-2's matrix) · any
conversion/approve work (R7) · any route-behaviour change outside the two producer routes · anything
making the flag independently enable-able · a P0-equivalent hole in accepted text.

## Close-out

Human-gated ⇒ **REV-0044 packet**; the gate clears only on a dispositioned `ACCEPT`/
`ACCEPT-WITH-CHANGES`. Set WO-0104 to REVIEW and stage `work/review/REV-0044/request.md` stating
explicitly which of GAP-08's clauses are closed. Then the **named gate** before R7a in the same
session (round 3): rung A closes completely — status, disposition, ledger, move, all three hygiene
scripts green — then STOP and report with R7a's preflight re-verified against the just-closed tree, and
wait for an explicit go/no-go.
