---
type: Work Order
title: "Signal Seat R6a — rails store surface: durable rail state, producer-rail projector, epoch identity, atomic budget debit, release primitive"
status: DRAFT
work_order_id: WO-0104a
splits_from: "work/queue/WO-0104-signal-rails-REFRESH.md (R6, split after two M4b passes)"
sibling: "WO-0104b (R6b — provider, token bucket, sweeps, /api/producers, release route, cockpit)"
wave: signal-seat reconciliation ladder, step R6a
model_tier: strong (LOCAL Codex — single-writer store mutation + event-log truth + gated DDL)
predecessors: [WO-0139 (R5b-2 — merged, REV-0043 dispositioned)]
successors: [WO-0104b (R6b), R7a, R7b, D-2a]
review: "REV-0044 required (human-gated: single-writer store mutation, event-log truth, SQLite DDL)"
wargame: "FULL per .ai-os/core/18 — M1/M2/M3/M4a below; M4b dispatched"
stage: "Stage 1 of 5 — runs ALONE; its REV-0044 must disposition before R6b or R7a start"
filter_risk: LOW-MED
---

# WO-0104a — Signal Seat R6a: the rails store surface

> **Why this exists.** R6 was one WO until two M4b passes each returned ~12 findings including a P0.
> The split puts everything **below HTTP** here and everything **at or above HTTP** in R6b. That is not
> cosmetic: it means **R6a creates no provider module, changes no request-time code path, and therefore
> breaks no existing test** — the day-one hazards that dominated R6 (`test_signal_seat_launcher.py`
> hanging, two rails fakes raising `TypeError`, the `is_conforming_rails` probe) are all **R6b's**,
> because they all follow from creating `app/signals_rails_impl.py` and touching `check_ingest`.

**What R6a delivers:** the durable rail-state cache (with its one gated DDL), the producer-rail
projector that makes the event log the source of truth, epoch identity, the **atomic budget debit**, the
release primitive, and a snapshot-free transition-event builder R6b's sweeps will use.

**The crown jewel:** the budget debit and the terminal event append are **one atomic operation**. If
they can separate, a producer overspends under concurrency or the counter and the event log disagree
forever — and the log is the source of truth.

---

## Scope boundary

**IN (R6a) — store layer and the minimum needed to keep it self-consistent:**
- `app/store/**` — durable rail-state cache, epoch state, the atomic debit inside `ingest_signal`, the
  release primitive, dual-store.
- `app/events/**` — the producer-rail projector + a snapshot-free identity-only transition-event builder.
- `app/models.py` — only if a rail DTO is required (no new event *types*: `PRODUCER_QUARANTINED` /
  `PRODUCER_RELEASED` already exist at `app/models.py:483-484`).
- **The new SQLite table + `_migrate` + `tests/test_signal_sqlite_schema.py`** — behind the DDL gate below.
- `app/facade/signal_commands.py`, `app/api/routes_signals.py` — **minimal** plumbing only, to surface
  the new post-exhaustion outcome (D-R6a-8). This is the one place R6a touches request-time code.
- `tests/**`.

**OUT — all of it is R6b (WO-0104b):** `app/signals_rails_impl.py` · the token-bucket *logic* ·
`check_ingest` / the `SignalRails` Protocol / `is_conforming_rails` · `app/api/deps.py` ·
the §3 sweeps in `app/monitoring.py` · `/api/producers` + the release **route** · the cockpit control ·
`signal_rate_limit_per_hour` / `signal_rate_burst` + `.env.example` · the launcher positive control.

**OUT — later rungs:** R7a/R7b conversion; D-2a.

**`app/server.py` is FORBIDDEN.** Its "until R6 lands, fail loudly" text stays accurate through R6a,
because R6a does **not** create `app/signals_rails_impl.py`. R6b refreshes it.

---

## ⚠ HUMAN-GATED: the SQLite DDL — the one approval stop in this rung

The rail-state cache is new durable state ⇒ a schema/migration change, human-gated per CLAUDE.md and
**not** covered by this WO's ratification. **STOP and request approval with the proposed DDL** before
creating or altering any table or column, exactly as R4's `signal_records` DDL was gated. The request
must include the `_migrate` step and the `tests/test_signal_sqlite_schema.py` update.

**Include the token-bucket columns in this one DDL even though the bucket *logic* is R6b's** — one
migration for the whole rail surface is safer than two, and R6b then adds no schema. State that in the
approval request so the operator is approving the complete rail table once.

---

## M1 — Assumption ledger / decision block

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`; no
`ASSUMED` line is pre-checked.

- [x] **D-R6a-1 Base and gate — name the base, and use a command that actually fails.** Base is
      **`origin/master` after an explicit fetch** (R5b-1/R5b-2/REV-0043 are merged there; a *local*
      `master` ref can be stale — it was, in the planning container, by 32 commits). Verify with
      **`git cat-file -e`**, not `git ls-tree`: the latter **exits 0 with empty output** for a missing
      path, so a scripted `&&` reports success on a missing file.
      ```
      git fetch origin
      git cat-file -e origin/master:tests/test_route_authorization_matrix.py
      git cat-file -e origin/master:work/review/REV-0043/disposition.md
      ```
      Both must succeed, else **STOP**. Branch `codex/signal-r6a-rails-store` from `origin/master`.
      — TRACED(M4b-2 F-1; planning-seat verified the stale-ref and exit-code behaviours).

- [x] **D-R6a-2 The atomic debit lives inside `store.ingest_signal`.** Deciding availability, consuming
      the slot, and appending the terminal event are **one store operation**. Verified present:
      `memory.py:5580` (`async with self._lock: with self._atomic():`) and `sqlite.py:7655`
      (`async with self._lock: with self._tx() as cur:`), with real rollback (`memory.py:503-518`,
      `sqlite.py:542-557`). `cycle_budget_limit` is already a required kwarg (`base.py:1329`) and is
      already stamped (`core.py:5904-5905,5957`) and validated (`:6043-6048`). Crash between decision
      and append must leave **{debit + event} or neither**, in both stores.
      — TRACED(`03-rails.md:44-54`; anchors above).

- [x] **D-R6a-3 The event log is the SOURCE OF TRUTH; the rail record is a CACHE.**
      `03-rails.md:74-82`: "**Replay is event-authoritative** … the event log alone must reconstruct the
      binding budget … The consumed count folds as the number of such events since the last
      `PRODUCER_RELEASED`; **the limit is read from the cycle's first such event**. A side
      table/snapshot **may cache** this for the live path, but it is **not** the source of truth."
      Therefore R6a delivers **all four**:
      1. the consumed count **folds from the log** since the last `PRODUCER_RELEASED`;
      2. the pinned limit is **read from the cycle's first** attributable-rejection event;
      3. a **producer-rail projector** — none exists (`app/events/projectors.py` folds `SIGNAL_*` only,
         keyed `(producer_id, signal_id)`; it ignores unknown types, so this is purely additive);
      4. the cache is **rebuilt at `initialize()` before serving** (`03-rails.md:71-72`), in the
         existing `_backfill_*_unlocked` style (`memory.py:264-280` is the pattern).
      **Required proof: a live-vs-replay agreement test in both stores.**
      — TRACED(`03-rails.md:71-82`; `02-lifecycle.md:109-124`; `projectors.py`).

- [x] **D-R6a-4 Budget-fold exclusions — TWO of them, both pinned.** `02-lifecycle.md:64-68` scopes the
      debiting set to exactly: a **validation/skew** `SIGNAL_QUARANTINED`, a **novel-hash**
      `SIGNAL_DUPLICATE_CONFLICT`, and a **dead-on-arrival** `SIGNAL_EXPIRED`. So the fold must exclude:
      1. `SIGNAL_QUARANTINED` with `quarantine_reason = producer_sweep` (`02-lifecycle.md:69-72`;
         `03-rails.md:37-38`) — folding sweep quarantines as consumption "would let accepted traffic
         consume the invalid budget and diverge replay from live";
      2. **`SIGNAL_EXPIRED` with `detected_by ≠ "ingest"`** — the periodic sweep's expiry (R6b) is a
         non-debiting event of a type that *is* on the debit list. A projector folding all
         `SIGNAL_EXPIRED` produces exactly the divergence (1) forbids.
      Discriminator available today: the presence of `cycle_budget_limit` in the payload
      (`core.py:5904-5905`). **Pin both exclusions** — including exclusion (2) against a synthetic
      sweep-shaped event, since R6b has not yet produced real ones.
      — TRACED(`02-lifecycle.md:64-72`; `03-rails.md:37-38`; M4b-2 F-6).

- [x] **D-R6a-5 Epoch identity = a folded monotonic per-producer sequence; dedupe keys are
      epoch-scoped.** `dedupe_key` is `TEXT UNIQUE` (`sqlite.py:406`) and a duplicate is a **silent
      idempotent no-op returning the existing event** in *both* stores (`sqlite.py:7428-7437`,
      `memory.py:5430-5435`) — so dual-store parity tests cannot see a lost event. A naive
      `producer_quarantine:{producer_id}` key would **silently drop epoch #2's opener** and every later
      `PRODUCER_RELEASED`, destroying the cycle boundary D-R6a-3's fold depends on. Fold an epoch
      sequence and include it in the `dedupe_key` of **both** `PRODUCER_QUARANTINED` and
      `PRODUCER_RELEASED`. **Exactly-once rests on the single `asyncio.Lock`** (`memory.py:5580`,
      `sqlite.py:7655`) plus the in-transaction check-and-set that already exists
      (`sqlite.py:7428-7437`); the UNIQUE index is a cross-process backstop that would surface as
      `IntegrityError`, **not** a no-op — do not describe it as the primary mechanism.
      **Required pin:** release → re-quarantine → release yields **2 openers and 2 releases**, both stores.
      — TRACED(anchors above; `core.py:5912-5914`; M4b-2 F-5/F-12).

- [x] **D-R6a-6 The exhausting append co-appends the epoch opener in the SAME op.** The attributable
      rejection consuming the **last** slot appends **both** its terminal event **and** the single
      `PRODUCER_QUARANTINED`, in one memory-lock/SQLite-transaction — "so there is **no
      zero-budget-but-un-quarantined gap**". Exactly one opener per epoch; subsequent rejects are
      write-free. **`SignalIngestPlan.event` is currently a single `Optional[ExecutionEvent]`
      (`core.py:5968`) and must carry two**; `plan_signal_ingest`'s signature changes, touching
      `tests/test_signal_ingest_properties.py:79`.
      — TRACED(`03-rails.md:55-66`; `core.py:5968`).

- [x] **D-R6a-7 The release PRIMITIVE only — and the saturated count is a PARAMETER, not store state.**
      R6a lands `release_producer(producer_id, *, rejected_count: int, ...)`: one atomic op that closes
      the epoch, resets **both** the bucket and the budget ("else the producer re-quarantines on its next
      ingest", `02-lifecycle.md:51`), and writes `PRODUCER_RELEASED` carrying the count and the epoch
      window. **The count is supplied by the caller.** It must NOT be store state: A-4 specifies a
      "**saturating in-memory counter outside the event log** (diagnostic, **best-effort across restarts
      by design**)" (`03-rails.md:163-164`; `ADR-009:53,346-347`) and threat-model **T-14** requires
      post-quarantine rejects stay **write-free**. A durable counter would make every post-quarantine
      reject a store write, contradicting `03-rails.md:156` and T-14. **R6b owns the in-memory holder**
      and passes the value in. Unknown producer / not-quarantined are the caller's concern (R6b's route
      maps 404/409); the primitive reports them as typed refusals.
      — TRACED(`03-rails.md:156,163-164`; `ADR-009:53,346-347`; `THREAT_MODEL_SIGNAL_SEAT.md:64`;
      M4b-2 F-2, which found rev-2's store-held counter to be an accepted-text violation).

- [x] **D-R6a-8 The post-exhaustion outcome must be representable AND surfaceable — the one
      request-time touch.** `03-rails.md:48-51`: with one slot left and N concurrent requests "**exactly
      one** appends its terminal event and consumes the slot; **the rest find zero and are handled as
      post-exhaustion**" → 403, no store write (`:155-157`). That reject originates **inside**
      `ingest_signal`, so `RailsDecision.http_status` cannot carry it. Three blockers, all verified:
      1. `SignalIngestResult.record` is **non-Optional** in `app/store/base.py:337-338` *and*
         `app/facade/signal_commands.py:26-27` — "wrote nothing, no record" is unrepresentable;
      2. `_OUTCOME_STATUS` is a literal 6-entry dict subscripted **bare** (`routes_signals.py:45-52`,
         used at `:202`) — a 7th outcome is a `KeyError` → 500, then
         `SignalRecordView.model_validate(None)`;
      3. the ingest call site has **no `except FacadeError`** (contrast `list_signals` at `:219-226`).
      R6a therefore: adds the outcome, makes the record Optional through both layers, adds the
      `_OUTCOME_STATUS` entry + a **record-free 403 response branch**, and adds the missing
      `except FacadeError`. **Pinned dual-store under concurrency: N requests, one slot ⇒ exactly one
      201/422-class terminal + N−1 403s + exactly one opener.** This is required *in R6a* because the
      debit goes live the moment R6a lands, and an unmapped outcome is a 500.
      — TRACED(`03-rails.md:48-51,155-157`; anchors above; M4b-2 F-4).

- [x] **D-R6a-9 A snapshot-free, identity-only transition-event builder with distinct dedupe
      prefixes — R6a provides it, R6b's sweeps consume it.** Only two prefixes exist repo-wide,
      `signal_create` and `signal_conflict` (`core.py:5633-5642`), and `signal_record_event`
      (`:5892-5919`) **always** keys `signal_create:{producer}|{signal}` and **always** embeds a full
      record snapshot (`:5879-5889`). Both §3 sweeps transition an **already-born** record, so reusing
      that builder either (a) collides with the record's birth event → **silent no-op**: the record
      mutates while **no event is written**, breaking D-R6a-3's fold-agreement proof invisibly; or (b)
      carrying the snapshot, `projectors.py` classifies it as a **creation** and overwrites instead of
      transitioning, contradicting `02-lifecycle.md:120-124`'s identity-only transition rule. R6a lands
      the correct builder (distinct prefix per transition, identity-only payload) and pins it against a
      synthetic transition; R6b wires the real sweeps.
      — TRACED(`core.py:5633-5642,5879-5919`; `projectors.py`; `02-lifecycle.md:120-124`; M4b-2 F-5).

- [x] **D-R6a-10 No new settings in R6a.** The budget limit already arrives as a parameter
      (`base.py:1329`); the two **rate** settings, their caps, their flag-independent validation, and
      `.env.example` are **R6b's** (the bucket logic is R6b's). R6a adds none — so nothing here needs the
      `config.py` / `.env.example` reconciliation M4b-2 F-9 flagged.
      — TRACED(`base.py:1329`; `03-rails.md:11-15`).

- [x] **D-R6a-11 `app/facade/signals.py:88` semantics change — record it.** That call site passes a live
      `Settings` read on every ingest. Once the store pins per cycle, the parameter's meaning becomes
      "the limit to pin **iff** a new cycle begins", which makes `app/store/base.py:1339-1340`'s
      docstring false. Update the docstring in the same change. Six test files pass
      `cycle_budget_limit=` directly and two assert the stamped value
      (`tests/test_signal_ingest_store.py:141,188`; `test_signal_ingest_properties.py:305`) — those
      assertions must keep holding.
      — TRACED(`facade/signals.py:88`; `base.py:1339-1340`; M4b-1 hazard 5).

- [x] **D-R6a-12 Existing tests: R6a expects ZERO breakage — and that is a claim to verify, not assume.**
      Because R6a creates no `app/signals_rails_impl.py` and does not touch `check_ingest` /
      `is_conforming_rails` / `deps.py`, the R6 day-one hazards do not apply here:
      `test_signal_seat_launcher.py:129-137` keeps passing (the provider module still does not exist),
      and `test_signal_routes.py`'s two rails fakes (`:91-97`, `:100-102`) keep passing (the dependency
      still calls `check_ingest(producer_id)` with one argument). The **only** authorized edits are:
      `tests/test_signal_ingest_properties.py:79` (the `plan_signal_ingest` signature, D-R6a-6) and
      `tests/test_signal_sqlite_schema.py` (the DDL). **Any other existing-test edit is a STOP** — if
      one breaks, that is a signal R6a's scope leaked into R6b's.
      — TRACED(`test_signal_seat_launcher.py:129-137`; `test_signal_routes.py:91-102`; M4b-2 F-7).

- [x] **D-R6a-13 No pre-authored corpus ⇒ implementer mutation-checking is MANDATORY.** No staged rails
      corpus exists (staged `test_signal_quarantine_totality.py` is the **ingest** boundary, labelled
      WO-0102). For **every** decisive pin: revert the control, prove the pin goes RED, restore, paste
      the red-green evidence. REV-0041's inert pin and REV-0043's F-1 both arose exactly where a corpus
      was authored fresh. — TRACED(staging tree; REV-0041/REV-0043).

- [x] **D-R6a-14 Flag stays OFF; flag-off byte-equivalent.** No new mounted route (R6a adds none);
      `harness/bootstrap.py` green; all three hygiene scripts green. D-2a needs R6b + R7.
      — INHERITED(D-2a).

- [x] **D-R6a-15 Dual-store parity is mandatory throughout.** Rail state, epoch, debit, release, the
      projector fold, and the `initialize()` rebuild all prove out on **both** in-memory and SQLite.
      — TRACED(CLAUDE.md Testing; `conftest.py:29` `any_store`).

---

## M2 — Lifecycle totality: rail state and the epoch (R6a's half)

| Edge | Driver | Requirement |
|---|---|---|
| **cycle birth** | first attributable rejection after a release (or ever) | pins `cycle_budget_limit` from that event; cache mirrors it |
| **debit** | each validation/skew quarantine, novel conflict, DOA expiry | atomic with its terminal append (D-R6a-2); excluded events never debit (D-R6a-4) |
| **epoch birth (budget)** | the append consuming the **last** slot | co-appends terminal event **+** the single opener, same op (D-R6a-6) |
| **epoch birth (rate)** | *R6b* — the bucket path | R6a's primitive must accept an opener written without a terminal event |
| **post-exhaustion** | further ingest while exhausted | **403, write-free**, record-free response (D-R6a-8) |
| **epoch release** | `release_producer(...)` | resets **both** rails, writes `PRODUCER_RELEASED` with the caller-supplied count + window (D-R6a-7) |
| **re-quarantine** | next exhaustion after release | **new** epoch sequence ⇒ a new opener survives dedupe (D-R6a-5) |
| **restart** | `initialize()` | cache **rebuilt from the log** before serving (D-R6a-3.4) |
| **crash mid-debit** | death between decide and append | **{debit + event} or neither**, both stores |

**Precondition proof:** no terminal append without its debit, none without an append, in either store,
under concurrency, across restart — **and the live cache must always equal a fold of the log alone.**

---

## M3 — Consumer inventory

| Consumer | Class | Finding |
|---|---|---|
| `store.ingest_signal` (3 impls) | **affected — core** | A non-atomic debit overspends or desynchronises counter from log. |
| `SignalIngestPlan.event` (`core.py:5968`) | **affected** | Must carry two events; signature change reaches `test_signal_ingest_properties.py:79`. |
| `SignalIngestResult.record` (`base.py:337-338`, `signal_commands.py:26-27`) | **affected** | Must become Optional or post-exhaustion is unrepresentable. |
| `_OUTCOME_STATUS` + `_record_response` (`routes_signals.py:45-52,202`) | **affected** | A 7th outcome is a `KeyError` → 500 without the new entry and a record-free branch. |
| Ingest call site (`routes_signals.py:279-291`) | **affected** | No `except FacadeError` ⇒ a typed refusal becomes a 500. |
| Producer-rail projector | **MISSING — R6a authors it** | Without it the log cannot reconstruct the budget (D-R6a-3). |
| `initialize()` rebuild path | **affected** | A cache not rebuilt before serving lets a restarted process re-grant a spent budget. |
| `dedupe_key` space | **affected** | Non-epoch-scoped keys silently drop later openers — invisible in both stores. |
| Transition-event builder | **MISSING — R6a authors it** | Snapshot-carrying transitions mis-fold as creations (D-R6a-9). |
| `facade/signals.py:88` + `base.py:1339-1340` | **affected** | Parameter meaning changes; docstring becomes false. |
| R6b (provider, bucket, sweeps, release route, counter) | **downstream** | Consumes R6a's primitives, builder, and epoch state. |
| R7a's A-2 conversion re-check | **downstream** | Reads epoch/quarantine state R6a persists (`05-conversion.md:12`). |
| Existing suite + `harness/bootstrap.py` | **unaffected (must prove)** | Only the two authorized test edits (D-R6a-12). |

---

## M4a — Prospective hindsight

1. *"A producer got more strikes than allowed."* → non-atomic debit (D-R6a-2).
2. *"The counter said spent, no event explained why."* → crash edge (M2).
3. *"A restart re-granted a spent budget."* → no `initialize()` rebuild (D-R6a-3.4).
4. *"Replay disagreed with live after a config change."* → limit not read from the cycle's first event.
5. *"A second epoch never opened."* → non-epoch-scoped `dedupe_key` (D-R6a-5).
6. *"A released producer re-quarantined immediately."* → release reset one rail (D-R6a-7).
7. *"Post-quarantine rejects wrote to the store."* → counter made durable (D-R6a-7; A-4/T-14 violation).
8. *"Sweep events silently vanished."* → reused `signal_create` prefix (D-R6a-9).
9. *"Sweep expiries ate the invalid budget."* → missing `detected_by ≠ ingest` exclusion (D-R6a-4.2).
10. *"Exhaustion returned 500."* → unmapped 7th outcome (D-R6a-8).
11. *"Memory passed, SQLite overspent."* → dual-store parity (D-R6a-15).
12. *"The corpus was green and proved nothing."* → mandatory mutation-checking (D-R6a-13).
13. *"The gate said OK on a missing file."* → `git ls-tree` exit-0 (D-R6a-1).

---

## ⚠ BUILD HAZARDS (verified)

1. **A duplicate `dedupe_key` is a silent no-op in *both* stores** — parity tests cannot see a lost
   event. Epoch-scope the keys (D-R6a-5); use a distinct prefix for transitions (D-R6a-9).
2. **A 7th `SignalIngestOutcome` is a `KeyError` → 500** — `_OUTCOME_STATUS` is subscripted bare and
   `_record_response` requires a non-None record (D-R6a-8).
3. **`SignalIngestPlan` carries one event**; the exhausting op needs two (D-R6a-6).
4. **`initialize()` must rebuild the cache** in the `_backfill_*_unlocked` style (`memory.py:264-280`)
   **before serving**.
5. **Do not put the rejected-counter in the store** — A-4 requires in-memory/out-of-log and T-14
   requires write-free rejects (D-R6a-7).
6. **Include the bucket columns in the single DDL** even though the bucket logic is R6b's — one
   approval, one migration.
7. **`projectors.py` ignores unknown event types**, so the producer-rail projector is purely additive —
   but a *snapshot-carrying* transition will be mis-folded as a creation.

## Filter-safety clause (rung risk: **LOW-MED**)

Authorized defensive engineering on the operator's own local, paper-only application. No external
target, no network probing, no credential access, no live trading. R6a is store-internal, so the
sustained-arrival vocabulary matters less here than in R6b — but keep it: **say** *paced-arrival
accounting* · *budget-exhaustion accounting defect* · *non-atomic transaction boundary*; **avoid**
"flood attack", "DoS test", "exhaust the server". Report at the defect level: cause · impact · affected
local files · fix · pass/fail evidence. No reusable bypass procedures. **REV-0044's Claude seat is the
sanctioned adversarial net** — do not run open-ended adversarial discovery.

## Gate battery

`ruff check .` · `ruff format --check` on R6a-owned files · `mypy app/` · `lint-imports` · the R6a corpus
+ full suite · `python -m pytest -q tests/r2_conformance_oracle.py` ·
`pytest -q tests/test_wo0113_repair_scaling.py` · `python harness/bootstrap.py` · all three hygiene
scripts (`check_work_order_disposition`, `check_ledger`, `check_pkl`).

## Stop conditions

**Any DDL before approval** (the gate above) · **any existing-test edit beyond the two authorized in
D-R6a-12** — treat it as a signal that scope leaked into R6b · any provider / `check_ingest` /
`is_conforming_rails` / `deps.py` / sweep / route / cockpit work · any `app/server.py` edit · any new
setting · anything making the flag independently enable-able · any accepted-text conflict not recorded
here · a P0-equivalent hole in accepted text.

## Close-out

Human-gated ⇒ **REV-0044 packet**; the gate clears only on a dispositioned `ACCEPT`/
`ACCEPT-WITH-CHANGES`. Set WO-0104a to REVIEW and stage `work/review/REV-0044/request.md` stating
explicitly: which GAP-08 clauses R6a closes and which remain R6b's, the DDL that was approved, and the
live-vs-replay agreement evidence. **R6a runs alone**, and **its REV-0044 must disposition before R6b or
R7a start** — both depend on this store surface, so a late BLOCK would invalidate two downstream rungs.
