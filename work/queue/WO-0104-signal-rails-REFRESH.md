---
type: Work Order
title: "Signal Seat R6 — signal rails: token bucket, non-refilling invalid budget, quarantine epoch, sweeps, human release"
status: DRAFT
work_order_id: WO-0104
supersedes: "work/queue/WO-0104-signal-rails.md (draft 2026-07-11, pre-migration)"
wave: signal-seat reconciliation ladder, step R6
model_tier: strong (LOCAL Codex — single-writer store surface + human-gated release action + gated DDL)
predecessors: [WO-0139 (R5b-2 — MUST be merged and REV-0043 dispositioned first)]
successors: [R7a/R7b (conversion), D-2a joint enablement]
review: "REV-0044 required (human-gated: single-writer store mutation, event-log truth, operator release action, SQLite DDL)"
wargame: "FULL per .ai-os/core/18 — rev-2 applied 11 M4b findings incl. 1 P0; second M4b pass dispatched"
round: "Round 3 of 5 — R6 runs ALONE (see D-R6-14); R7a moves to round 4 with R7b"
filter_risk: MED
---

# WO-0104 (refresh, rev-2) — Signal Seat R6: the rails

> **rev-2 (2026-07-25).** An M4b pass returned **11 findings including a P0**: the rev-1 architecture
> was **unbuildable** — the rails provider is constructed before the store exists, so it could never
> reach the state it needs. rev-1 also **selectively quoted** the budget clause, **dropped an entire
> spec section** that is explicitly R6's, and asserted "no existing test edited" when creating R6's
> provider module breaks a live R5a launcher test. Every P0/P1 was verified against code by the
> planning seat before correction. See §M4b.

R5a made construction refuse without conforming rails. R5b-1 added authenticated ingest. R5b-2 made
every sensitive request require the operator credential. **R6 makes the rails real.**

**The crown jewel:** the budget debit and the terminal event append are **one atomic operation**. If
they can separate, a producer either overspends its budget under concurrency or leaves the counter and
the event log permanently disagreeing — and the event log is the source of truth.

---

## Architecture (rev-2): stateless provider, store-owned state, per-call injection

### What survived rev-1 (verified in both stores)

`03-rails.md:44-54` requires that deciding availability, consuming the slot, and appending the terminal
event be **one store operation**. Verified: `store.ingest_signal` already provides exactly that —
`memory.py:5580` (`async with self._lock: with self._atomic():`) and `sqlite.py:7655`
(`async with self._lock: with self._tx() as cur:`), with real rollback (`memory.py:503-518`,
`sqlite.py:543-557`). It already takes **`cycle_budget_limit` as a required kwarg**
(`base.py:1329`), already stamps it (`core.py:5904-5905,5957`) and validates it (`:6043-6048`).
**A route-consulted provider cannot satisfy atomicity — it holds no lock.** That ruling stands.

### What rev-1 got wrong (the P0)

rev-1 put the token bucket **and** the rate-path epoch check in the provider. But the provider needs the
store — step 2 must read the durable **quarantine epoch** (`03-rails.md:139-141`) and a rate breach must
**append** `PRODUCER_QUARANTINED` (`:21,151-152`) — and the provider is built **before the store
exists**: `server.py:61` calls `_load_production_rails(settings)` (settings only, `:26-40`),
`is_conforming_rails` validates at `main.py:119`, and the store is not created until `main.py:127`
inside the lifespan. rev-1 also claimed `server.py` needs no edit. Unbuildable as written.

### The rev-2 resolution — one decision that closes the P0 *and* the release problem

**The provider becomes a stateless policy adapter; the store owns ALL rail state; the store is injected
per call through the dependency that already has the request.**

| Concern | Home | Why |
|---|---|---|
| Tunables (rate/burst/budget) | the **provider**, stateless | Satisfies A-4's construction-time presence seam with nothing to bind |
| Token bucket, budget consumed count, **epoch**, saturating rejected-counter | **the store** (rail-state cache; event log is truth) | Everything needing atomicity or durability lives where the lock/transaction is |
| Store handoff | **per-call**, `check_ingest(producer_id, *, store=...)` | `check_signal_rails` (`deps.py:126-158`) already receives `request`, so it can pass `request.app.state.store` |
| Release reset of **both** rails | route → facade → **store**, one atomic op | The provider holds no state, so **no second Protocol method and no provider involvement** |

**Verified, not assumed:** an optional keyword-only parameter still satisfies R5a's guard —
`inspect.signature(bound_check).bind("probe-producer-id")` succeeds for
`check_ingest(self, producer_id, *, store=None)`, and `iscoroutinefunction`/`ismethod` still hold. So
`is_conforming_rails` (`app/facade/signal_rails.py:36-58`) stays **unchanged and un-weakened**, and
`server.py` stays **untouched**.

**Consequences:**
1. **R6 does not modify R5b-1's ingest route file.** The dependency (`app/api/deps.py`, in allowed
   paths) gains the store handoff; the route itself is unchanged. It already emits arbitrary 4xx from
   `RailsDecision.http_status` (`deps.py:145-157`), so **403 (quarantined) and 429 (rate breach) both
   work with no route change**, and it already fails closed on a malformed decision.
2. **`SignalRails` gains one optional keyword parameter** — not a new method. `PermissiveSignalRails`
   (`tests/signal_seat_helpers.py:32-36`) must accept and ignore it (5 files use `build_flag_on_app`).
3. **R6 is predominantly a store change** — `core.py` 6184 / `memory.py` 6112 / `sqlite.py` 8322 lines,
   with mandatory dual-store parity.
4. **Ordering after R5b-2 still holds** on the dependency argument (operator-only, browser-reachable
   release route, `03-rails.md:174,182-183`). The *entanglement* argument is withdrawn.

---

## M1 — Assumption ledger / decision block (rev-2)

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`;
no `ASSUMED` line is pre-checked.

- [x] **D-R6-1 HARD predecessor gate.** R5b-2 merged **and REV-0043 dispositioned**. Verify
      `git ls-tree master tests/test_route_authorization_matrix.py` returns a blob **and**
      `work/review/REV-0043/disposition.md` exists, else **STOP**. Branch `codex/signal-r6-rails` from
      the merged master. — TRACED(ratified round gate).

- [x] **D-R6-2 Architecture exactly as the rev-2 table above.** Stateless provider; **all** rail state
      in the store; store injected per call via an **optional keyword-only** `store` parameter on
      `check_ingest`; budget debit inside `store.ingest_signal`, atomic with the terminal append. Do
      **not** edit `app/server.py`. Do **not** weaken `is_conforming_rails`. Do **not** add a second
      Protocol method. — TRACED(`03-rails.md:44-54`; `server.py:26-40,61`; `main.py:119,127`;
      `deps.py:126-158`; planning-seat bind verification).

- [x] **D-R6-3 Allowed paths.** Create `app/signals_rails_impl.py` (the module `server.py:33` already
      imports and which does not exist). Carry forward the old draft's list: `app/events/**`,
      `app/models.py`, `app/config.py`, `app/main.py`, `app/store/**`, `app/api/**`, `app/facade/**`,
      `cockpit/**`, `.importlinter`, `tests/**`. **`app/server.py` remains FORBIDDEN** — its import is
      already correct and the rev-2 design needs no change there. **`app/monitoring.py` is ADDED** (the
      §3 sweeps, D-R6-11). — TRACED(`server.py:33`; module absent).

- [x] **D-R6-4 Settings, with the caps decided here rather than invented.** Add
      `signal_rate_limit_per_hour: int = 60` and `signal_rate_burst: int = 10` (absent today, verified).
      `03-rails.md:11-15` specifies **no** hard cap, so ratify them now to stop the implementer
      inventing unratified numbers: **`signal_rate_limit_per_hour ∈ [1, 10000]`**,
      **`signal_rate_burst ∈ [1, 1000]`**, and **`signal_rate_burst ≤ signal_rate_limit_per_hour`**
      (a burst larger than the hourly allowance is incoherent). Validate in
      `validate_signal_seat_settings` — the single validation point — in the R5a style
      (`config.py:477-488`). R5a already landed the budget/TTL settings (`config.py:200,202`); the old
      draft's claim that R6 adds those is **wrong**. — TRACED(`03-rails.md:11-15`; grep: absent;
      `config.py:200,202,477-488`).

- [x] **D-R6-5 Budget truth = THE EVENT LOG; the rail record is only a CACHE.** rev-1 quoted the
      either/or at `03-rails.md:51-52` and stopped. The binding clause is `:74-82`: "**Replay is
      event-authoritative** … the event log alone must reconstruct the binding budget … The consumed
      count folds as the number of such events since the last `PRODUCER_RELEASED`; **the limit is read
      from the cycle's first such event**. A side table/snapshot **may cache** this for the live path,
      but it is **not** the source of truth." So:
      1. Each attributable-rejection event carries `cycle_budget_limit` (already implemented).
      2. The consumed count **folds from the log** since the last `PRODUCER_RELEASED`.
      3. The pinned limit is **read from the cycle's first such event** — pinning is event-derivable, so
         rev-1's stated rationale for a record was factually wrong.
      4. A durable rail record is permitted **as a live-path cache**, updated in the same
         lock/transaction, and must be **rebuilt at `initialize()`** before serving (`:71-72`).
      **R6 therefore owes a producer-rail projector** — none exists
      (`app/events/projectors.py:795-831` folds `SIGNAL_*` only) — **plus a live-vs-replay agreement
      proof in both stores.** — TRACED(`03-rails.md:74-82`; `02-lifecycle.md:118-124`;
      `projectors.py:795-831`).

- [x] **D-R6-6 Epoch identity is a folded monotonic per-producer sequence, and `dedupe_key` is
      epoch-scoped.** `dedupe_key` is `TEXT UNIQUE` (`sqlite.py:406`) and a collision is a **silent
      idempotent no-op returning the existing event** in *both* stores (`sqlite.py:7428-7436`,
      `memory.py:5430-5435`) — so dual-store parity tests cannot catch it. A naive
      `producer_quarantine:{producer_id}` key would **silently drop epoch #2's opener** and every later
      `PRODUCER_RELEASED`, destroying the cycle boundary the D-R6-5 fold depends on. Define an epoch
      sequence folded from the log and include it in the `dedupe_key` of **both**
      `PRODUCER_QUARANTINED` and `PRODUCER_RELEASED`. **The existing UNIQUE index is then the
      exactly-once mechanism** — no bespoke check-and-set is required (rev-1 over-decided this).
      **Required pin:** release → re-quarantine → release yields **2 openers and 2 releases** in both
      stores. — TRACED(`sqlite.py:406,7428-7436`; `memory.py:5430-5435`; `core.py:5915-5917`;
      `03-rails.md:62`).

- [x] **D-R6-7 Step-2 ordering: EPOCH FIRST, then rate.** `03-rails.md:139-141` orders step 2 as
      "**quarantine epoch, rate limit**". A quarantined producer must get **403** (`:155-156`), **not**
      429, and **must not burn tokens** during the epoch. So: check the epoch → if open, 403 write-free;
      only otherwise debit the bucket. A same-request rate-breach + budget-exhaustion collision is
      **impossible by the normative order** (step 2 rejects before step 4) — record that rather than
      guarding it. — TRACED(`03-rails.md:139-141,155-156`).

- [x] **D-R6-8 Release resets BOTH rails, atomically, in the store.** `PRODUCER_RELEASED` closes the
      epoch and resets **both** the §1 bucket **and** the §1a budget — "else the producer re-quarantines
      on its next ingest" (`02-lifecycle.md:51`) — and carries the **saturated `rejected_count`** plus
      the epoch window. Because the provider is stateless (D-R6-2), the counter is **store rail state**
      ("the counter itself lives outside the event log" permits store-held non-event state), so release
      needs no provider involvement. Unknown producer → 404; not quarantined → 409.
      — TRACED(`02-lifecycle.md:51`; `03-rails.md §5`).

- [x] **D-R6-9 The `producer_sweep` carve-outs.** A `producer_sweep` `SIGNAL_QUARANTINED` **does not
      debit** the budget and carries **no** `cycle_budget_limit` — folding sweep quarantines as budget
      consumption "would let accepted traffic consume the invalid budget and diverge replay from live".
      Pin both properties. — TRACED(`02-lifecycle.md:69-72`; `03-rails.md:37-38`).

- [x] **D-R6-10 The §3 SWEEPS are R6's — rev-1 dropped them entirely.** `03-rails.md:128-135` is headed
      "## 3. Sweeps (**WO-0104**)" and requires **two**: (a) a periodic engine-side RECEIVED→EXPIRED
      sweep (`SIGNAL_EXPIRED`, `detected_by:"sweep"`), injected clock, monitoring-loop cadence; and
      (b) on `PRODUCER_QUARANTINED`, sweeping that producer's RECEIVED signals to `SIGNAL_QUARANTINED`
      (`"producer_sweep"`) so "a quarantined producer has no pending proposals lingering on the
      operator's panel". Both dual-store, injected clock, no bare wall-clock.
      — TRACED(`03-rails.md:128-135`).

- [x] **D-R6-11 The no-zero-budget-gap: R6 owns the sweep, R7 owns only the A-2 re-check.** rev-1
      pushed the exhausted-producer concern to R7. **Wrong:** the spec's own mechanism is R6's
      `producer_sweep` (D-R6-10b), which terminalizes the pending records so there is nothing left for
      R7 to wrongly approve. R6 exposes epoch/quarantine state through the facade for R7's atomic
      re-check and implements **no** conversion. — TRACED(`03-rails.md:55-66,133-135`).

- [x] **D-R6-12 Existing tests R6 must STRENGTHEN (not "no test edited" — rev-1 was false).**
      `tests/test_signal_seat_launcher.py:129-137` currently asserts a flag-on loopback launch **fails**
      with `"WO-0104"`/`"rails"` in stderr. The moment `app/signals_rails_impl.py` exists that launch
      **succeeds** and the 15 s `subprocess.run` timeout raises `TimeoutExpired` — a **day-one break
      presenting as a hang, not an assertion failure**. That file's own docstring defers the positive
      control to "the joint WO-0102+0104 milestone against WO-0104's REAL rails", and
      `03-rails.md:111-114` requires proving the production entrypoint constructs the real provider.
      **Authorized strengthening (a bounded list, and this is NOT test-weakening):**
      1. `test_signal_seat_launcher.py:129-137` → a **positive control**: flag-on loopback launch
         reaches a ready listener with the real provider.
      2. `tests/signal_seat_helpers.py:32-36` `PermissiveSignalRails` → accept and ignore the optional
         `store` kwarg.
      3. `tests/test_route_authorization_matrix.py` → extend the literal `REQUIRED` set (D-R6-13).
      Any other existing-test edit is a **STOP**. — TRACED(`test_signal_seat_launcher.py:13-15,118,129-137`;
      `03-rails.md:111-114`).

- [x] **D-R6-13 `/api/producers` + release + cockpit is a FROM-SCRATCH build-out.** Nothing exists: no
      `routes_producers` module, no `ProducerStateView` (`04-auth-and-api.md:159-166`), no facade
      method, no store accessor, and **no cockpit signal/producer surface at all**. R6 authors: the
      route module; its `.importlinter` **contract-5 `source_modules`** entry (the contract runs
      `unmatched_ignore_imports_alerting = error`); the conditional mount in `app/main.py`; the DTOs;
      facade command + query; dual-store accessors; **two new `OPERATOR_ONLY` entries** in the matrix's
      literal `REQUIRED` set; and a **standalone cockpit release control** — R7/WO-0103 owns the signal
      panel, so do not assume one exists. Note the matrix asserts an **exact count**
      (`test_route_authorization_matrix.py:192-196`), so two new routes fail two assertions, and
      `_concrete_path` (`:167-171`) will call `POST /api/producers/missing/release`, which must return
      **404, never 500**. Note also that deny-by-default middleware already makes these operator-only,
      so the "producer key cannot self-release" negative passes **without proving anything
      route-specific** — pin the *action*, not just the status.
      — TRACED(grep: all absent; `04-auth-and-api.md:112-115,159-166,169-176`; matrix `:28-87,167-171,192-196`).

- [x] **D-R6-14 R6 RUNS ALONE; R7a moves to round 4.** The ratified plan grouped R6 + R7a behind a named
      gate *conditional* on neither war-game revealing WO-0139-style growth. It did. R6's footprint:
      2 settings + caps; abstract store methods; `SignalIngestPlan.event` (`core.py:5968`) becoming
      **two** events with `plan_signal_ingest`'s signature changing (touching
      `tests/test_signal_ingest_properties.py:79`); rail state + epoch + release in both stores; a **new
      SQLite table + migration behind a mid-session human DDL STOP**; a new projector; two §3 sweeps in
      `app/monitoring.py`; a new route module + importlinter + mount + DTOs + facade; a from-scratch
      cockpit surface; the launcher positive control; and **~25-40 dual-store proofs**. A mid-session
      approval halt plus that surface is not a co-tenant. **Five rounds, not four.**
      — TRACED(M4b F-8, planning-seat concurrence).

- [x] **D-R6-15 No pre-authored corpus ⇒ implementer mutation-checking is MANDATORY.** Unlike
      R5a/R5b-1/R5b-2, no staged rails corpus exists (staged `test_signal_quarantine_totality.py` is the
      **ingest** boundary, labelled WO-0102). For **every** decisive pin: revert the control, prove the
      pin goes RED, restore, paste the red-green evidence. REV-0041's inert pin and REV-0043's F-1 both
      arose exactly where a corpus was authored fresh. — TRACED(staging tree; REV-0041/REV-0043).

- [x] **D-R6-16 The old draft's behaviour contract carries forward IN FULL — not just six proofs.**
      rev-1 said "VERBATIM" then narrowed to the six lettered budget proofs. The old draft
      (`WO-0104-signal-rails.md:66-90`) also requires the §3 expiry sweep, the staleness tests, the
      enablement-gate test, and "prove the production entrypoint constructs the REAL provider" — all
      still mandated by accepted text. Carry all of it; re-anchor to rev-2's architecture.
      **Exception:** the A3 interleaving property test that `02-lifecycle.md:32` assigns to WO-0104
      needs R7's `approve`; **defer that single item to R7 and record the deferral** rather than
      silently dropping it. — INHERITED(old draft `:66-90`) + TRACED(`02-lifecycle.md:32`).

- [x] **D-R6-17 Flag stays OFF; flag-off byte-equivalent except the D-R6-12 strengthenings.** No new
      mounted route flag-off; `harness/bootstrap.py` green; all three hygiene scripts green.
      — INHERITED(D-2a).

- [x] **D-R6-18 Record the F-11 carve-out deliberately.** `app/api/routes_signals.py` rejects a body
      whose `producer_id` disagrees with the authenticated principal with **422 and no store call** — so
      no event and no budget debit — while `04-auth-and-api.md:141` describes 422 as "validation failure
      — recorded as `SIGNAL_QUARANTINED`". Not a flood hole (no log growth, and the request is
      attributable and rate-debited), but R6 owns budget totality and must record this as a **deliberate
      accepted carve-out** rather than inherit it silently. — TRACED(`routes_signals.py` identity
      binding; `04-auth-and-api.md:141`).

- [x] **D-R6-19 Inherited REV-0043 register items.** **F-6:** the fixed `"operator:authenticated"`
      principal is not losslessly separable once producer principals exist — R6 introduces
      producer-attributed rail state, so state the attribution scheme explicitly. **F-8:**
      `StoreBackedSignalFacade.list_signals` cannot push the status filter down and materializes the
      full scope; R6's rails bound **ingest**, not this read — decide whether to add a limit here or
      record it still-open. — INHERITED(REV-0043 `result.md` F-6/F-8).

---

## M2 — Lifecycle totality: the quarantine epoch

| Edge | Driver | Requirement / anchor |
|---|---|---|
| **birth (rate)** | step-2 bucket empty, **epoch closed** | one `PRODUCER_QUARANTINED`, request 429, **no** per-request `SIGNAL_QUARANTINED` (`03-rails.md:17-22`) |
| **birth (budget)** | step-4 append consuming the **last** slot | co-appends its terminal event **and** the single opener in the **same** op (`:55-66`) |
| **birth (exactly once)** | epoch-scoped `dedupe_key` + existing UNIQUE index | D-R6-6; no bespoke check-and-set |
| **on birth → sweep** | `producer_sweep` of that producer's RECEIVED signals | D-R6-10b; **no debit, no `cycle_budget_limit`** (D-R6-9) |
| **open → reject** | any further ingest while quarantined | **403 write-free**, no token burn (D-R6-7) |
| **open → released** | operator `POST /api/producers/{id}/release` | `PRODUCER_RELEASED` resets **bucket + budget**, carries saturated `rejected_count` + epoch window (D-R6-8) |
| **released → re-quarantine** | next breach after release | a **new** epoch sequence ⇒ a **new** opener survives dedupe (D-R6-6 pin) |
| **terminal** | none — epochs end only by human release | "resets only on human release, never by refill" |
| **crash mid-debit** | death between decide and append | **{debit + event} or neither**, both stores (`:44-54`) |
| **restart** | `initialize()` | rail-state cache **rebuilt from the log** before serving (`:71-72`) |

**Precondition proof:** no terminal append without its debit, none without an append, in either store,
under concurrency, and across restart — **and** the live rail cache must always agree with a fold of the
log alone.

---

## M3 — Consumer inventory + control-action sweep

| Consumer | Class | Control-action finding |
|---|---|---|
| `store.ingest_signal` (3 impls) | **affected — core** | (1)/(3): a non-atomic debit overspends under concurrency or desynchronises counter from log. |
| `SignalIngestPlan.event` (`core.py:5968`) | **affected** | Must carry **two** events for the exhausting op; `plan_signal_ingest`'s signature changes, touching `tests/test_signal_ingest_properties.py:79`. |
| `cycle_budget_limit` stamping (`core.py:5904,5957`) | **affected** | (3): must stamp the **pinned cycle** limit, not a live `Settings` read, or replay diverges. `app/facade/signals.py:88` passes a live read every ingest — its meaning becomes "the limit to pin **iff** a new cycle begins", and `base.py:1339-1340`'s docstring becomes false. Six test files pass it directly; two assert the stamped value. |
| The provider (`check_ingest`) | **affected** | (2): stateless — must not hold or debit state. Fails closed if no store is supplied. |
| Producer-rail projector | **MISSING — R6 authors it** | (1): without it the log cannot reconstruct the budget, breaking D-R6-5. |
| `initialize()` restore path | **affected** | (4) *stopped too soon*: a cache not rebuilt before serving lets a restarted process re-grant a spent budget. |
| Epoch `dedupe_key` | **affected** | (1): a non-epoch-scoped key silently drops later openers — invisible in both stores. |
| R7's A-2 conversion re-check | **unknown → resolved** | D-R6-11: R6's sweep terminalizes pending records; R7 re-checks atomically. |
| `/api/producers` + release + cockpit | **MISSING — R6 authors all of it** | D-R6-13; matrix `REQUIRED` + exact-count assertions must be extended. |
| `app/monitoring.py` | **affected** | Two §3 sweeps, injected clock, dual-store (D-R6-10). |
| `tests/test_signal_seat_launcher.py:129-137` | **affected — day-one break** | D-R6-12: must become a positive control or the suite hangs. |
| `PermissiveSignalRails` + 5 `build_flag_on_app` users | **affected** | Must tolerate the optional `store` kwarg. |
| `.importlinter` contract 5 | **affected** | New route module must be added; `unmatched_ignore_imports_alerting = error`. |
| Existing suite + `harness/bootstrap.py` | **unaffected (must prove)** | Beyond D-R6-12's bounded list. |

---

## M4a — Prospective hindsight

1. *"A producer got more strikes than allowed."* → non-atomic debit (D-R6-2).
2. *"The counter said spent, no event explained why."* → crash edge (M2).
3. *"Two openers for one epoch."* / *"A second epoch never opened."* → `dedupe_key` scope (D-R6-6).
4. *"A released producer re-quarantined immediately."* → release reset one rail (D-R6-8).
5. *"A restart re-granted a spent budget."* → cache not rebuilt at `initialize()` (D-R6-5.4).
6. *"Replay disagreed with live after a config change."* → live `Settings` read instead of the pinned limit (M3).
7. *"A quarantined producer got 429 and burned tokens."* → step-2 order (D-R6-7).
8. *"Sweep quarantines ate the invalid budget."* → `producer_sweep` carve-out (D-R6-9).
9. *"Quarantined producers' proposals lingered on the operator's panel."* → §3b sweep dropped (D-R6-10).
10. *"An exhausted producer's stale signals were still approvable."* → R6 sweep + R7 re-check (D-R6-11).
11. *"Memory passed, SQLite overspent."* → dual-store parity (D-R6-16).
12. *"The rails corpus was green and proved nothing."* → mandatory mutation-checking (D-R6-15).
13. *"The session hung on day one with no failure message."* → launcher test (D-R6-12).
14. *"The session stalled: the provider had no store."* → the rev-1 P0 (D-R6-2).
15. *"R6 shipped `/release` unauthenticated."* → R5b-2's ratchet catches it, **by design** (D-R6-13).

---

## ⚠ HUMAN-GATED: SQLite schema change

The durable rail-state cache is a **schema/migration change** — human-gated per CLAUDE.md and **not**
covered by this WO's ratification. **STOP and request approval with the proposed DDL** before creating
or altering any table or column, exactly as R4's `signal_records` DDL was gated. Include the `_migrate`
step and the `tests/test_signal_sqlite_schema.py` update in the request. Do not self-authorize.

## ⚠ BUILD HAZARDS (M4b-verified)

1. **`tests/test_signal_seat_launcher.py:129-137` breaks the instant `app/signals_rails_impl.py` exists**
   — and presents as a **15 s timeout**, not an assertion failure. Convert it first (D-R6-12).
2. **The provider cannot be handed a store at construction** — `build_production_rails(settings)` takes
   settings only and the store is created later. Use the per-call injection in D-R6-2; do **not** edit
   `server.py`, do **not** let the provider build its own store (two stores = two locks = single-writer
   broken).
3. **A duplicate `dedupe_key` is a silent no-op in *both* stores** — parity tests cannot catch a lost
   opener. Epoch-scope the key (D-R6-6).
4. **`SignalIngestPlan` carries one event**; the exhausting op needs two.
5. **`app/facade/signals.py:88` passes a live `Settings` read**; `base.py:1339-1340`'s docstring becomes
   false once the store pins per cycle.
6. **`initialize()` must rebuild the rail cache** in the `_backfill_*_unlocked` style before serving.
7. **The matrix asserts an exact route count** — two new routes fail two assertions; and
   `POST /api/producers/missing/release` must be **404, never 500**.
8. **No cockpit signal surface exists** — the release control needs a standalone panel.
9. **Deny-by-default already makes `/api/producers*` operator-only**, so the wrong-role negative passes
   without proving anything route-specific. Pin the action.

## Filter-safety clause (rung risk: **MED**)

Authorized defensive engineering on the operator's own local, paper-only application. No external
target, no network probing, no credential access, no live trading, no persistence objective.

The sustained-arrival proof is the trigger risk. **Say** *paced-arrival accounting* ·
*sustained-arrival conformance test* · *budget-exhaustion accounting defect* · *non-atomic transaction
boundary* · *unauthorized-role acceptance*. **Avoid** "flood attack", "DoS test", "hammer the
endpoint", "exhaust the server". Report at the defect level: cause · impact · affected local files ·
fix · pass/fail evidence. No reusable bypass procedures. Do **not** run open-ended adversarial
discovery — **REV-0044's Claude seat is the sanctioned adversarial net**.

## Gate battery

`ruff check .` · `ruff format --check` on R6-owned files · `mypy app/` · `lint-imports` (contracts 2 and
5 green) · the R6 corpus + full suite · `python -m pytest -q tests/r2_conformance_oracle.py` ·
`pytest -q tests/test_wo0113_repair_scaling.py` · `python harness/bootstrap.py` · all three hygiene
scripts.

## Stop conditions

**Any schema/migration DDL (approval-gated above)** · any existing-test edit beyond D-R6-12's bounded
list · any weakening of `is_conforming_rails` or R5b-2's matrix · any `app/server.py` edit · any
conversion/approve work (R7) · anything making the flag independently enable-able · any accepted-text
conflict not recorded here · a P0-equivalent hole in accepted text.

## Close-out

Human-gated ⇒ **REV-0044 packet**; the gate clears only on a dispositioned `ACCEPT`/
`ACCEPT-WITH-CHANGES`. Set WO-0104 to REVIEW and stage `work/review/REV-0044/request.md` stating
explicitly **which GAP-08 clauses are closed**, the DDL that was approved, and the D-R6-16 A3-test
deferral to R7. **R6 runs alone (D-R6-14)** — no co-tenant rung, no named gate in this session.

## §M4b record — 11 findings (1 P0, 5 P1), all planning-seat verified

| # | Finding | Verified | Applied |
|---|---|---|---|
| **F-1 (P0)** | Architecture **unbuildable**: the provider is built before the store exists (`server.py:61`, `main.py:119` vs `:127`), yet the rate path needs epoch state and must append an event; rev-1 also claimed `server.py` needs no edit | **YES** | rev-2 architecture: stateless provider + store-owned state + per-call injection via an optional kwarg (bind-verified against R5a's guard) |
| **F-2 (P1)** | "No existing test edited" is **false** — `test_signal_seat_launcher.py:129-137` asserts the launch FAILS on missing rails; creating the module makes it hang for 15 s | **YES** | D-R6-12 bounded strengthening list |
| **F-3 (P1)** | `03-rails.md §3` **Sweeps (WO-0104)** dropped entirely, and D-R6-10 wrongly gave the exhausted-producer mechanism to R7 | **YES** | D-R6-10 + D-R6-11 |
| **F-4 (P1)** | rev-1 **selectively quoted**: replay is event-authoritative, a record is only a cache, and pinning IS event-derivable — rev-1's rationale was factually wrong | **YES** | D-R6-5 rewritten; projector + replay-parity added |
| **F-5 (P1)** | Epoch identity undefined; a duplicate `dedupe_key` is a **silent no-op in both stores**, so a naive key drops epoch #2's opener | **YES** | D-R6-6 |
| **F-6 (P1)** | "No second Protocol method" unsatisfiable while the bucket/counter live in the provider | **YES** | Resolved by making the provider stateless — state moves to the store, so release needs no provider access |
| F-7 (P2) | `/api/producers` + cockpit understated to near-zero; nothing exists | **YES** | D-R6-13 |
| F-8 (P2) | Round-3 grouping with R7a unrealistic | Concur | D-R6-14 — five rounds |
| F-9 (P2) | Intra-step-2 ordering undecided (403 vs 429, token burn) | **YES** | D-R6-7 |
| F-10 (P3) | "VERBATIM" contradicted by the six-proof narrowing | **YES** | D-R6-16 |
| F-11 (P3) | An unrecorded 422 that writes no event | **YES** | D-R6-18 |

**Survived rev-1 unchanged:** the atomicity thesis (claim 1, probed in both stores), the human-gated
DDL stop, and the M4a hindsight list — all carried forward.
