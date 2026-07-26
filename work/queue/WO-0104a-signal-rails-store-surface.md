---
type: Work Order
title: "Signal Seat R6a — rails store surface: durable rail state, producer-rail projector, epoch identity, atomic budget + rate debits, release primitive"
status: DRAFT
work_order_id: WO-0104a
splits_from: "work/queue/WO-0104-signal-rails-REFRESH.md (R6, split after two M4b passes)"
sibling: "WO-0104b (R6b — provider wiring, sweeps, /api/producers, release route, cockpit, rate settings)"
wave: signal-seat reconciliation ladder, step R6a
model_tier: strong (LOCAL Codex — single-writer store mutation + event-log truth + gated DDL)
predecessors: [WO-0139 (R5b-2 — merged, REV-0043 dispositioned)]
successors: [WO-0104b (R6b), R7a, R7b, D-2a]
review: "REV-0044 required (human-gated: single-writer store mutation, event-log truth, SQLite DDL)"
wargame: "FULL per .ai-os/core/18 — rev-2 applied 15 M4b-3 findings incl. 2 P0; fourth M4b pass dispatched"
stage: "Stage 1 of 5 — runs ALONE; its REV-0044 must disposition before R6b or R7a start"
filter_risk: LOW-MED
---

# WO-0104a (rev-2) — Signal Seat R6a: the rails store surface

> **rev-2 (2026-07-25).** An M4b pass returned **15 findings including 2 P0**. Both P0s were verified
> against code by the planning seat. rev-1's **central claim survived measurement** — the full suite is
> green with exactly one authorized test edit — so the split works; these are corrections, not a
> redesign. **Operator ratified Option A** for P0-2: R6a owns the rate-path store primitive, so
> `app/store/**` is complete in one rung, under one review packet and one migration.

**What R6a delivers:** the durable rail-state cache behind **one** gated DDL, the producer-rail
projector that makes the event log the source of truth, epoch identity, **both** atomic debits (budget
and rate), the release primitive, and a snapshot-free transition-event builder R6b's sweeps consume.

**The crown jewel:** a debit happens **if and only if** its event is actually written. rev-1 would have
broken this — see D-R6a-4.

---

## Scope boundary

**IN (R6a) — everything below HTTP:**
- `app/store/**` — rail-state cache; epoch state; the **budget** debit inside `ingest_signal`; the
  **rate** check-and-debit + breach opener (D-R6a-16); the release primitive; dual-store.
- `app/events/**` — the producer-rail projector + a snapshot-free identity-only transition-event builder.
- `app/models.py` — only if a rail DTO is required (no new event *types*: `PRODUCER_QUARANTINED` /
  `PRODUCER_RELEASED` already exist at `app/models.py:482-483`).
- **The new SQLite table + `_migrate` + startup guard + `tests/test_signal_sqlite_schema.py`** — behind
  the DDL gate below.
- **`app/facade/signals.py`, `app/facade/signal_commands.py`, `app/api/routes_signals.py`** — minimal
  plumbing to surface the post-exhaustion outcome (D-R6a-8). `facade/signals.py` is **required**:
  `mypy app/` fails at `:102` and `:104` without it once the record is Optional (and at
  `app/store/memory.py:5609`).
- `tests/**`.

**OUT — R6b (WO-0104b):** `app/signals_rails_impl.py` · the provider / `check_ingest` / `SignalRails` /
`is_conforming_rails` · `app/api/deps.py` · the **in-memory rejected-counter holder** · the §3 sweeps in
`app/monitoring.py` · `/api/producers` + the release **route** · the cockpit control ·
`signal_rate_limit_per_hour` / `signal_rate_burst` + `.env.example` · the launcher positive control.

**OUT — later:** R7a/R7b conversion; D-2a.

**`app/server.py` is FORBIDDEN** and stays accurate through R6a, because R6a does **not** create
`app/signals_rails_impl.py`. R6b refreshes it.

---

## ⚠ HUMAN-GATED: the SQLite DDL — the one approval stop

New durable state ⇒ schema/migration ⇒ human-gated per CLAUDE.md, **not** covered by this WO's
ratification. **STOP and request approval with the proposed DDL** before creating or altering any table
or column. The request must include **all five** of:

1. The full rail table — including the **token-bucket columns**, since Option A makes R6a their writer.
   One approval, one migration; **R6b adds no schema.**
2. **The pinned-limit column MUST be nullable.** A rate-breach epoch can open with **zero** attributable
   rejections (`03-rails.md:66`), so a cycle can exist with no "first such event" and therefore no
   pinnable limit. `NOT NULL` would force a backfill from live `Settings`, silently making config changes
   retroactive against `03-rails.md:83-87`.
3. `_migrate` — and the disclosure that **`SCHEMA` + `_migrate` run flag-independently**
   (`sqlite.py:561-562`; the store layer has zero `signal_seat_enabled` references), so this table lands
   in the operator's live database **with the flag off**.
4. An **R4-style startup guard**: exact-column equality that **refuses startup**, plus the UNIQUE-key
   guard — the precedent for the last durable signal table is `sqlite.py:1041-1082` and `:1083-1101`.
   Without it the rail table ships tamper-blind and an altered column silently serves a wrong budget.
5. The `tests/test_signal_sqlite_schema.py` update.

---

## M1 — Assumption ledger / decision block (rev-2)

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`; no
`ASSUMED` line is pre-checked.

- [x] **D-R6a-1 Base and gate.** Base is **`origin/master` after an explicit fetch** — a *local* `master`
      ref can be stale (it was, by **30** commits). Verify with **`git cat-file -e`**, never
      `git ls-tree`: the latter **exits 0 with empty output** on a missing path, so a scripted `&&`
      reports success.
      ```
      git fetch origin
      git cat-file -e origin/master:tests/test_route_authorization_matrix.py
      git cat-file -e origin/master:work/review/REV-0043/disposition.md
      ```
      Both must succeed, else **STOP**. Branch `codex/signal-r6a-rails-store` from `origin/master`.
      — TRACED(measured: `ls-tree` exit 0/empty vs `cat-file` exit 128; both files present on
      `origin/master`).

- [x] **D-R6a-2 Both debits live inside the store, atomic with their appends.** Deciding availability,
      consuming, and appending are **one store operation**: `memory.py:5579-5580`
      (`async with self._lock: with self._atomic():`), `sqlite.py:7655-7656`
      (`async with self._lock: with self._tx() as cur:`), real rollback at `memory.py:502-518` /
      `sqlite.py:542-557`. `cycle_budget_limit` is already a required kwarg (`base.py:1329`), already
      stamped (`core.py:5904-5905,5957`) and validated (`:6043-6048`). Crash between decision and append
      leaves **{debit + event} or neither**, both stores. — TRACED(anchors above; `03-rails.md:44-54`).

- [x] **D-R6a-3 The event log is the SOURCE OF TRUTH; the rail record is a CACHE — and the fold has SIX
      products.** `03-rails.md:74-82`: "**Replay is event-authoritative** … the event log alone must
      reconstruct the binding budget … the limit is read from the cycle's first such event. A side
      table/snapshot **may cache** this … but it is **not** the source of truth." R6a delivers:
      1. consumed count, folded since the last `PRODUCER_RELEASED`;
      2. the pinned limit, read from the cycle's **first** attributable-rejection event;
      3. a **producer-rail projector** — none exists; `projectors.py:850-852` ignores unknown types, so
         it is purely additive;
      4. the cache **rebuilt at `initialize()` before serving** (`03-rails.md:71-72`), in the
         `_backfill_*_unlocked` style (`memory.py:264-280`; `sqlite.py:644-646` mirrors it);
      5. **⚠ the current quarantine state** — a restart that restores the budget but not the quarantine
         flag **un-quarantines a quarantined producer**, and this is the exact state R7a reads
         (`05-conversion.md:12` "the producer quarantine epoch") in the rung that starts right after
         REV-0044;
      6. **⚠ the epoch sequence** that D-R6a-5 depends on.
      **Required proof: live-vs-replay agreement in both stores** — **excluding `rejected_count`**, which
      is unauditable by design (D-R6a-7).
      — TRACED(`03-rails.md:71-82`; `02-lifecycle.md:109-124`; anchors above).

- [x] **D-R6a-4 ⚠ P0 — THREE fold exclusions, and the debit is conditioned on the event ACTUALLY BEING
      WRITTEN.** rev-1 quoted `02-lifecycle.md:64-68` and specified two exclusions. `03-rails.md:36-41`
      adds a third that rev-1 dropped: "each **novel-hash** `SIGNAL_DUPLICATE_CONFLICT` (a same-hash
      replay is already coalesced to one event … and **does not re-debit**)". Exclusions:
      1. `SIGNAL_QUARANTINED` with `quarantine_reason = producer_sweep`;
      2. `SIGNAL_EXPIRED` with `detected_by ≠ "ingest"` (R6b's periodic sweep — a non-debiting event of a
         type that *is* on the debit list);
      3. **a same-hash (deduped) `SIGNAL_DUPLICATE_CONFLICT`.**
      **And the mechanism matters, not just the list.** `signal_duplicate_conflict_event` keys on
      `new_payload_hash` (`core.py:5941`), so resubmitting the *same* conflicting payload hits the dedupe
      no-op (`memory.py:5433-5435`, `sqlite.py:7428-7437`) — and **both call sites discard the append's
      return value** (`memory.py:5603-5604`, `sqlite.py:7683-7684`), so the store cannot see that nothing
      was written. Measured: `A, B, B` ⇒ two `conflict` outcomes, **one** logged event, both stores.
      **A debit keyed on `plan.event is not None` therefore charges 2 for 1 logged event** — the live
      cache diverges permanently from the fold on the very quantity the spec declares event-authoritative,
      the opener co-appends at a count replay says is not exhaustion, and a restart *grows the budget
      back*. Invisible to dual-store parity; already on a path the suite walks
      (`tests/test_signal_ingest_store.py:144-193`).
      **Therefore: condition the debit on the append having actually written** — use the returned
      event's identity/sequence, or an explicit `wrote: bool` — **never** on `plan.event is not None`.
      **Pin:** `A, B, B` ⇒ consumed == 1, cache == fold, both stores.
      — TRACED(`03-rails.md:36-41`; anchors above; planning-seat verified both halves).

- [x] **D-R6a-5 Epoch identity = a folded monotonic per-producer sequence; dedupe keys epoch-scoped.**
      A duplicate `dedupe_key` is a **silent idempotent no-op returning the existing event** in *both*
      stores (`memory.py:5433-5435`, `sqlite.py:7428-7437`), so parity tests cannot see a lost event. A
      naive `producer_quarantine:{producer_id}` key would silently drop epoch #2's opener and every later
      `PRODUCER_RELEASED`. Include the sequence in the `dedupe_key` of **both** `PRODUCER_QUARANTINED`
      and `PRODUCER_RELEASED`. **Exactly-once rests on the single `asyncio.Lock`** (`memory.py:5580`,
      `sqlite.py:7655`) plus the existing in-transaction SELECT-then-INSERT check-and-set
      (`sqlite.py:7428-7437`); the UNIQUE index (`sqlite.py:406`) is **not** the mechanism and a
      cross-process collision surfaces as `SQLITE_BUSY`, not `IntegrityError` — rev-1 was wrong in both
      directions. **State explicitly whether the write-time sequence comes from the log fold or the
      cache**, and pin it: zero/stale the cache, prove the opener still lands with the correct sequence
      inside the same atomic op. **Pin:** release → re-quarantine → release ⇒ 2 openers, 2 releases,
      both stores. — TRACED(anchors above; `core.py:5913,5941`).

- [x] **D-R6a-6 The epoch opener is an ADDITIVE plan field — do NOT retype `event`.** The exhausting
      append must carry its terminal event **and** the single `PRODUCER_QUARANTINED` in one op
      (`03-rails.md:55-66`). `SignalIngestPlan.event` is a single `Optional[ExecutionEvent]`
      (`core.py:5968`) and is **read at seven sites** in `tests/test_signal_ingest_properties.py`
      (`:198,203,204,281,300,301,306`) — retyping it breaks all seven. **Add
      `epoch_event: Optional[ExecutionEvent]`** instead; measured, that plus one new required kwarg
      leaves the full suite green with **only** the `:79` edit. Sole planner callers: `memory.py:5583`,
      `sqlite.py:7663`, and the test at `:61`.
      — TRACED(`core.py:5968`; the seven sites; measured).

- [x] **D-R6a-7 The release PRIMITIVE — full signature, validated, and one field excluded from the
      agreement claim.** R6a lands
      **`release_producer(producer_id, *, actor: str, rejected_count: int, released_at: datetime)`**:
      one atomic op closing the epoch, resetting **both** rails (`02-lifecycle.md:51` — else the producer
      re-quarantines on its next ingest), writing `PRODUCER_RELEASED` with **`actor`** (required by
      `02-lifecycle.md:55` and `03-rails.md:175`; rev-1 omitted it and an append-only event cannot be
      fixed after the fact), the count, and the epoch window. `released_at` is **injected** — the repo
      pattern is `ingest_signal(..., received_at=...)` (`base.py:1332`); note `memory.py:274` already
      regresses to a bare `utcnow()` inside `initialize()` and must **not** be copied.
      **The counter must NOT be store state:** A-4 specifies a "saturating **in-memory** counter outside
      the event log (diagnostic, **best-effort across restarts by design**)" (`03-rails.md:163-164`;
      `ADR-009:53,346-347`) and **T-14** requires post-quarantine rejects stay **write-free**
      (`THREAT_MODEL_SIGNAL_SEAT.md:64`); a durable counter would make every post-quarantine reject a
      store write, contradicting `03-rails.md:156`. **R6b owns the in-memory holder.**
      Because the count is caller-supplied: **validate it** (`0 ≤ count ≤ cap`) in the primitive, on the
      `_require_bounded_int` precedent (`core.py:6043-6048`), and **define the saturation cap here** next
      to `_SIGNAL_CYCLE_BUDGET_MAX` (`core.py:5607`) — accepted text says "saturating" but never gives a
      value, so R6a must ratify one rather than let R6b's holder saturate at an unrelated number.
      **And record that `rejected_count` is OUTSIDE D-R6a-3's live-vs-replay agreement claim** — because
      rejects are write-free by design, the log holds no independent evidence, so the agreement proof is
      vacuous for this field. REV-0044 must not over-claim it.
      — TRACED(anchors above; M4b-3 F-7/F-8).

- [x] **D-R6a-8 The post-exhaustion outcome — representable, surfaceable, and provable only at runtime.**
      `03-rails.md:48-51`: with one slot left and N requests "**exactly one** appends its terminal event
      and consumes the slot; **the rest find zero and are handled as post-exhaustion**" → 403, no store
      write (`:155-157`). The reject originates **inside** `ingest_signal`, so `RailsDecision.http_status`
      cannot carry it. Verified blockers:
      1. `SignalIngestResult.record` is **non-Optional** (`base.py:337-338`, `signal_commands.py:26-27`);
      2. `_OUTCOME_STATUS` is a literal 6-entry dict subscripted **bare** (`routes_signals.py:45-52`,
         used at `:202`), so a 7th outcome is a `KeyError` → 500, then
         `SignalRecordView.model_validate(None)`.
      **Not a blocker (rev-1 was wrong):** a missing `except FacadeError` — the outcome arrives as a
      *return value*; the facade raises `RuntimeError` (`facade/signals.py:94-98`) and the store
      `ValueError` (`core.py:6118-6120`), neither a `FacadeError`.
      R6a adds the outcome, makes the record Optional through **both** layers, adds the `_OUTCOME_STATUS`
      entry and a **record-free 403 branch** — and note `_record_response` has **two** ingest call sites
      (`routes_signals.py:261-277` malformed-body and `:279-291`), both of which must be safe.
      **⚠ The gate battery cannot catch this.** With the record Optional and `:200` untouched,
      `mypy app/` returns **Success** (`model_validate` takes `Any`); ruff and lint-imports are equally
      blind. So the record-free branch is provable **only by a mounted-app runtime pin**, and
      D-R6a-13's mutation check **must** include it (revert the branch ⇒ assert the 500).
      **Why it belongs in R6a even though nothing goes live:** the debit does **not** activate on merge —
      `main.py:249-250` mounts the route only flag-on, `config.py:192` defaults it off, and flag-on
      requires a conforming provider (`main.py:118-123`) which `server.py:33-40` refuses because
      `app/signals_rails_impl.py` does not exist after R6a. rev-1's stated rationale was false. The touch
      is required because **the sanctioned test seam already mounts the route flag-on with
      `PermissiveSignalRails`** (`tests/signal_seat_helpers.py:34-38`, used at
      `tests/test_signal_routes.py:52-56`) and the pin is stated in HTTP terms.
      **Pin (both stores):** N requests **serialised by the single writer** (not "concurrent" — the lock
      serialises them), one slot ⇒ exactly one terminal + N−1 403s + exactly one opener.
      — TRACED(anchors above; M4b-3 F-4/F-5/P2-11).

- [x] **D-R6a-9 A snapshot-free, identity-only transition-event builder with distinct dedupe prefixes.**
      `signal_record_event` (`core.py:5892-5919`) **always** keys `signal_create:{producer}|{signal}`
      (literal at `core.py:5913`) and **always** embeds a full record snapshot (`:5879-5889`). Both §3
      sweeps transition an **already-born** record, so reusing it either (a) collides with the birth event
      → **silent no-op**: the record mutates while **no event is written**, breaking D-R6a-3's fold proof
      invisibly; or (b) carrying the snapshot, `projectors.py:795-801,838-841` classifies it as a
      **creation** and overwrites instead of transitioning, against `02-lifecycle.md:120-124`. R6a lands
      the builder (distinct prefix per transition, identity-only payload) and pins it against a synthetic
      transition; R6b wires the real sweeps.
      — TRACED(anchors above).

- [x] **D-R6a-10 No new settings in R6a.** The budget limit arrives as a parameter (`base.py:1329`). The
      two **rate** settings, their caps, their flag-independent validation, and `.env.example` are
      **R6b's** — R6a implements the bucket *mechanics* against values passed in, so it needs no
      `config.py` change. — TRACED(`base.py:1329`; `03-rails.md:11-15`).

- [x] **D-R6a-11 SIX stale claims R6a invalidates — refresh all of them in the same change.** Beyond
      `base.py:1339-1340`: **`base.py:332`**, **`core.py:5577`**, **`core.py:6034`**,
      **`signal_commands.py:14`** (all say "six outcomes"), and **`base.py:1336-1338`** ("a changed
      payload appends **only** an audit-conflict event" — it now debits and may co-append the opener).
      Also `app/facade/signals.py:88` passes a live `Settings` read every ingest; its meaning becomes
      "the limit to pin **iff** a new cycle begins". Six test files pass `cycle_budget_limit=` directly
      and two assert the stamped value (`tests/test_signal_ingest_store.py:141,188`;
      `test_signal_ingest_properties.py:305`) — those must keep holding. CLAUDE.md's close-out rule makes
      refreshing invalidated claims part of the work, not a follow-up.
      — TRACED(anchors above; M4b-3 P2-13).

- [x] **D-R6a-12 Existing tests: ZERO breakage expected — MEASURED, with a named tripwire list.** The
      claim held under measurement: full suite green with exactly the `:79` edit, and suite-wide maximum
      attributable rejections per (store, producer) is **2** against a budget of 50 — a factor of 25 of
      headroom, which is *why* nothing breaks. Authorized edits: **only**
      `tests/test_signal_ingest_properties.py:79` (the `plan_signal_ingest` kwarg, D-R6a-6) and
      `tests/test_signal_sqlite_schema.py` (the DDL). **Tripwire — if any of these seven sites needs
      editing, `event` was retyped instead of adding `epoch_event`, and that is a STOP:**
      `test_signal_ingest_properties.py:198,203,204,281,300,301,306`. Any other existing-test edit is
      likewise a **STOP** — it signals scope leaked into R6b's.
      — TRACED(measured; the seven sites; `test_signal_seat_launcher.py:129-137` and
      `test_signal_routes.py:91-102` both keep passing because R6a creates no provider module and does
      not touch `check_ingest`).

- [x] **D-R6a-13 No pre-authored corpus ⇒ implementer mutation-checking is MANDATORY**, and it **must**
      include the D-R6a-8 record-free branch (invisible to every static gate). For every decisive pin:
      revert the control, prove RED, restore, paste the red-green evidence. REV-0041's inert pin and
      REV-0043's F-1 both arose exactly where a corpus was authored fresh.
      — TRACED(staging tree; REV-0041/REV-0043; M4b-3 F-4).

- [x] **D-R6a-14 Flag stays OFF; flag-off byte-equivalence is scoped to the HTTP SURFACE ONLY.** R6a
      mounts no route and changes no request-time behaviour flag-off. **But it is NOT byte-equivalent at
      the database:** `sqlite.py:561-562` runs `SCHEMA` + `_migrate` **unconditionally** (zero
      `signal_seat_enabled` references in the store layer; measured — a flag-off `Settings` still creates
      `signal_records`), so the rail table lands in the operator's live DB with the flag off. Say so in
      the DDL request. `harness/bootstrap.py` green; all three hygiene scripts green.
      — TRACED(`sqlite.py:561-562`; measured).

- [x] **D-R6a-15 Dual-store parity throughout.** Rail state, both debits, epoch, release, the projector
      fold, and the `initialize()` rebuild all prove out on **both** stores.
      — TRACED(CLAUDE.md Testing; `conftest.py:29` `any_store`).

- [x] **D-R6a-16 ⚠ P0 RESOLUTION (operator: Option A) — the RATE-PATH store primitive is R6a's.** rev-1
      gave R6a `app/store/**` but wrote no D-line for the rate path, while giving R6b the bucket *logic*
      without `app/store/**` — so the bucket columns would have shipped with **no authorized writer**,
      and R6b's only outs were editing `app/store/**` out of scope (another human gate + packet) or
      appending the opener from the provider, re-creating the non-atomic shape the split existed to bury.
      **Option A ratified:** R6a lands the rate primitive — a **token-bucket check-and-debit and, on
      breach, the `PRODUCER_QUARANTINED` opener, in one atomic store op** (`03-rails.md:44-54,151-152`).
      Consequences to honour:
      1. The **bucket must be lazily refilled and evaluated READ-ONLY on the reject path** — a natural
         "update `last_refill_ts` on every evaluation" makes post-quarantine 403s and 429s store writes,
         violating `03-rails.md:156` and T-14.
      2. **Epoch-check precedes rate-debit** (`03-rails.md:139-141`: "quarantine epoch, rate limit"): a
         quarantined producer gets **403, not 429** (`:155-156`), and **must not burn tokens**.
      3. A rate breach opens an epoch **with no terminal event**, so the fold must handle a cycle whose
         pinned limit is unknowable — hence the nullable limit column (DDL item 2).
      4. R6a implements the mechanics against caller-passed values; the **settings** stay R6b's
         (D-R6a-10). `app/store/**` is then genuinely complete in R6a: **R6b adds no schema and no store
         change.**
      — TRACED(`03-rails.md:44-54,139-141,151-152,155-156,66`; operator ratification 2026-07-25).

---

## M2 — Lifecycle totality (R6a owns every edge below)

| Edge | Driver | Requirement |
|---|---|---|
| **cycle birth** | first attributable rejection after a release | pins the limit from that event; cache mirrors it. A **rate-breach-only** cycle has **no** pinnable limit (nullable column) |
| **budget debit** | validation/skew quarantine · novel-hash conflict · DOA expiry | atomic with its append, and **only if the append actually wrote** (D-R6a-4) |
| **rate debit** | every authenticated ingest, epoch closed | atomic; **read-only on the reject path** (D-R6a-16.1) |
| **epoch birth (budget)** | the append consuming the last slot | terminal event **+** opener, same op, via `epoch_event` (D-R6a-6) |
| **epoch birth (rate)** | bucket empty at an authenticated ingest | opener alone, no terminal event (D-R6a-16.3) |
| **epoch birth (exactly once)** | epoch-scoped `dedupe_key` + the single lock | D-R6a-5 |
| **post-exhaustion** | further ingest while exhausted | **403, write-free**, record-free response (D-R6a-8) |
| **quarantined ingest** | any ingest while the epoch is open | **403, write-free, no token burn** (D-R6a-16.2) |
| **epoch release** | `release_producer(..., actor, rejected_count, released_at)` | resets **both** rails; writes `PRODUCER_RELEASED` (D-R6a-7) |
| **re-quarantine** | next breach after release | **new** sequence ⇒ a new opener survives dedupe |
| **restart** | `initialize()` | cache rebuilt from the log — **including quarantine state and the epoch sequence** (D-R6a-3.5/3.6) |
| **crash mid-debit** | death between decide and append | **{debit + event} or neither**, both stores |

---

## M3 — Consumer inventory

| Consumer | Class | Finding |
|---|---|---|
| `store.ingest_signal` (3 impls) | **affected — core** | Both debits; a debit not conditioned on an actual write diverges cache from fold (D-R6a-4). |
| The new rate primitive | **NEW — R6a authors it** | D-R6a-16; read-only on the reject path. |
| `SignalIngestPlan` (`core.py:5968`) | **affected** | **Additive** `epoch_event`; retyping `event` breaks seven sites. |
| `SignalIngestResult.record` (`base.py:337-338`, `signal_commands.py:26-27`) | **affected** | Optional, or post-exhaustion is unrepresentable. |
| `_OUTCOME_STATUS` / `_record_response` — **two** call sites (`routes_signals.py:45-52,202,261-277,279-291`) | **affected** | A 7th outcome is a `KeyError` → 500; **static gates cannot see it**. |
| `app/facade/signals.py:88,102,104` | **affected — mypy-proven required** | Without the edit the new outcome is an `AttributeError` → 500. |
| `app/store/memory.py:5609` | **affected — mypy-proven** | Same Optional-record narrowing. |
| Producer-rail projector | **MISSING — R6a authors it** | Purely additive (`projectors.py:850-852` ignores unknown types). |
| `initialize()` rebuild | **affected** | Must restore budget **and** quarantine state **and** epoch sequence; must not copy `memory.py:274`'s bare `utcnow()`. |
| `dedupe_key` space | **affected** | Non-epoch-scoped keys silently drop later openers, invisibly, in both stores. |
| Transition-event builder | **MISSING — R6a authors it** | Snapshot-carrying transitions mis-fold as creations. |
| Six stale doc claims | **affected** | D-R6a-11. |
| **`tests/test_route_authorization_matrix.py:238-247`** | **⚠ affected — cross-rung coupling** | It asserts a valid producer key gets a status **not in (401, 403)**. R6a's post-exhaustion reject **is a 403 for a valid producer key**. Green today only because the corpus never exhausts (max 2 vs budget 50). **R6a's 403 must carry a machine-distinguishable reason, and this must be recorded** — R5b-2's authorization guarantee weakens the moment 403 has two meanings on that route. |
| R6b (provider, holder, sweeps, route, cockpit) | **downstream** | Consumes R6a's primitives, builder, epoch state. **No store change, no schema.** |
| R7a's A-2 re-check | **downstream** | Reads the quarantine epoch R6a persists (`05-conversion.md:12`). |
| Existing suite + `harness/bootstrap.py` | **unaffected (measured)** | Only the two authorized edits. |

---

## M4a — Prospective hindsight

1. *"A producer was charged twice for one logged event."* → debit not conditioned on an actual write (D-R6a-4). **The P0.**
2. *"A same-hash resubmission re-debited."* → missing third exclusion (D-R6a-4.3).
3. *"A restart un-quarantined a quarantined producer."* → fold omitted quarantine state (D-R6a-3.5).
4. *"A restart re-granted a spent budget."* → no `initialize()` rebuild (D-R6a-3.4).
5. *"A second epoch never opened."* → non-epoch-scoped `dedupe_key`, or a stale cache supplying the sequence (D-R6a-5).
6. *"A released producer re-quarantined immediately."* → release reset one rail (D-R6a-7).
7. *"`PRODUCER_RELEASED` had no actor."* → unfixable in an append-only log (D-R6a-7).
8. *"Post-quarantine rejects wrote to the store."* → durable counter, or a bucket that writes on evaluation (D-R6a-7, D-R6a-16.1).
9. *"A quarantined producer got 429 and burned tokens."* → epoch checked after rate (D-R6a-16.2).
10. *"Exhaustion returned 500."* → unmapped 7th outcome; **and no static gate would have caught it** (D-R6a-8).
11. *"Sweep events silently vanished."* → reused `signal_create` prefix (D-R6a-9).
12. *"Sweep expiries ate the budget."* → missing `detected_by ≠ ingest` exclusion (D-R6a-4.2).
13. *"An altered rail column silently served a wrong budget."* → no startup guard (DDL item 4).
14. *"A config change retroactively moved a cycle's ceiling."* → non-nullable pinned limit backfilled from live `Settings` (DDL item 2).
15. *"The authorization matrix went green while a producer route 403'd for a new reason."* → the M3 cross-rung coupling.
16. *"Memory passed, SQLite overspent."* → dual-store parity (D-R6a-15).
17. *"The corpus was green and proved nothing."* → mandatory mutation-checking incl. the record-free branch (D-R6a-13).
18. *"The gate said OK on a missing file."* → `git ls-tree` exit-0 (D-R6a-1).

---

## ⚠ BUILD HAZARDS (verified)

1. **The repeated-novel-hash double debit** — the dedupe no-op is invisible because **both call sites
   discard the append's return value** (`memory.py:5603-5604`, `sqlite.py:7683-7684`). The P0.
2. **`mypy` does NOT flag `SignalRecordView.model_validate(result.record)`** — `model_validate` takes
   `Any`, so the 500 is invisible to ruff, mypy and lint-imports alike. Only a runtime pin catches it.
3. **`test_route_authorization_matrix.py:238-247` collides with the new 403** — see M3.
4. **`_migrate` runs flag-independently** (`sqlite.py:561-562`) — the gated DDL touches every existing
   operator database.
5. **The write-time epoch-sequence source must be specified** — a cache lagging the log makes epoch #2's
   opener a silent no-op by a *different* route than the key design.
6. **R4's exact-column + UNIQUE startup guard** (`sqlite.py:1041-1101`) must be carried to the rail table.
7. **`memory.py:274` already calls bare `utcnow()` in `initialize()`** — do not copy it; inject the clock.
8. **A duplicate `dedupe_key` is a silent no-op in both stores** — parity cannot see a lost event.
9. **A 7th `SignalIngestOutcome` is a `KeyError` → 500** via a bare-subscripted `_OUTCOME_STATUS`.
10. **`SignalIngestPlan.event` must gain a sibling, not change type** — seven read sites.

## Filter-safety clause (rung risk: **LOW-MED**)

Authorized defensive engineering on the operator's own local, paper-only application. No external
target, no network probing, no credential access, no live trading. R6a is store-internal, but keep the
vocabulary: **say** *paced-arrival accounting* · *budget-exhaustion accounting defect* · *non-atomic
transaction boundary*; **avoid** "flood attack", "DoS test", "exhaust the server". Report at the defect
level: cause · impact · affected local files · fix · pass/fail evidence. No reusable bypass procedures.
**REV-0044's Claude seat is the sanctioned adversarial net** — no open-ended adversarial discovery.

## Gate battery

`ruff check .` · `ruff format --check` on R6a-owned files · `mypy app/` · `lint-imports` · the R6a corpus
+ full suite · `python -m pytest -q tests/r2_conformance_oracle.py` ·
`pytest -q tests/test_wo0113_repair_scaling.py` · `python harness/bootstrap.py` · all three hygiene
scripts. **Note explicitly: the static gates cannot prove D-R6a-8** — that needs the runtime pin.

## Stop conditions

**Any DDL before approval** · **any existing-test edit beyond the two authorized in D-R6a-12** — and
specifically any edit to the seven `plan.event` read sites, which means `event` was retyped · any
provider / `check_ingest` / `is_conforming_rails` / `deps.py` / sweep / route / cockpit / counter-holder
work · any `app/server.py` edit · any new setting · anything making the flag independently enable-able ·
any accepted-text conflict not recorded here · a P0-equivalent hole in accepted text.

## Close-out

Human-gated ⇒ **REV-0044 packet**; the gate clears only on a dispositioned `ACCEPT`/
`ACCEPT-WITH-CHANGES`. Set WO-0104a to REVIEW and stage `work/review/REV-0044/request.md` stating: which
GAP-08 clauses R6a closes and which remain R6b's; the approved DDL including the nullable columns and the
startup guard; the live-vs-replay agreement evidence **with `rejected_count` explicitly excluded from
that claim**; and the `test_route_authorization_matrix.py` 403-overloading coupling. **R6a runs alone**,
and **its REV-0044 must disposition before R6b or R7a start.**

## §M4b record — pass 3 (15 findings, 2 P0), all planning-seat verified

*(Passes 1 and 2 are recorded in the superseded parent, `WO-0104-signal-rails-REFRESH.md` §M4b. rev-1 of
this WO cited "M4b-2 F-*" against a table that was never written down — recorded here so REV-0044 can
audit the chain.)*

| # | Finding | Verified | Applied |
|---|---|---|---|
| **P0-1** | Debit ≠ event on a repeated novel-hash conflict: the key is the payload hash, the dedupe no-ops, **both call sites discard the append's return value**, and `03-rails.md:39-40` already forbids re-debiting. Measured `A,B,B` ⇒ 2 outcomes, 1 event, both stores | **YES** — spec clause + both discard sites | D-R6a-4: third exclusion **and** debit conditioned on an actual write |
| **P0-2** | The split left the rate rail with no authorized writer, while its columns shipped in R6a's DDL | **YES** — from the WO's own scope lists | D-R6a-16: **Option A** — R6a owns the rate primitive |
| P1-3 | `app/facade/signals.py` required (mypy: `:102`,`:104`) and out of scope | YES | Scope IN += `facade/signals.py`, `store/memory.py` |
| P1-4 | The gate battery cannot catch the 500 the route touch prevents | YES | D-R6a-8 + D-R6a-13 runtime pin |
| P1-5 | Two `_record_response` call sites; "blocker 3" (`except FacadeError`) is not a blocker | YES | D-R6a-8 corrected |
| P1-6 | Retyping `event` breaks seven sites | YES | D-R6a-6: additive `epoch_event`; D-R6a-12 tripwire |
| P1-7 | `PRODUCER_RELEASED` requires `actor`; no injected clock | YES | D-R6a-7 full signature |
| P1-8 | `rejected_count` unvalidated, uncapped, unauditable | YES | D-R6a-7 validation + cap + agreement-claim exclusion |
| P1-9 | The fold omitted quarantine state and the epoch sequence | YES | D-R6a-3.5/3.6 + M4a #3 |
| P1-10 | DDL traps: non-nullable limit, unwritable bucket columns, no startup guard | YES | DDL gate items 2/4 |
| P2-11 | D-R6a-8's "goes live on merge" rationale false; "concurrency" wrong | YES | D-R6a-8 rationale replaced; "serialised by the single writer" |
| P2-12 | Flag-off byte-equivalence false at the database | YES | D-R6a-14 scoped to HTTP |
| P2-13 | Five further stale doc claims | YES | D-R6a-11 (six total) |
| P2-14 | Eight TRACED citations pointed at a nonexistent record | YES | this table |
| P3-15 | Anchor errors: `models.py:482-483`; `core.py:5913`/`:5941`; delta 30 not 32; the `IntegrityError` claim | YES | corrected throughout |

**Survived measurement:** rev-1's central claim — *R6a breaks no existing test* — held, with the full
suite green on exactly one authorized edit and 25× budget headroom explaining why.
