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
wargame: "FULL per .ai-os/core/18 — five M4b passes; rev-4 applies pass-5's 10 findings incl. 1 P0"
stage: "Stage 1 of 5 — runs ALONE; its REV-0044 must disposition before R6b or R7a start"
filter_risk: LOW-MED
---

# WO-0104a (rev-4) — Signal Seat R6a: the rails store surface

> **rev-4 (2026-07-26).** A fifth M4b pass, scoped to the two newest blocks (`D-R6a-16`, `D-R6a-17`),
> returned **10 findings including 1 P0** — all verified against code. **The P0 is a second-order
> consequence of Option A itself:** a second epoch opener decoupled "epoch open" from "budget
> exhausted", and rev-3's gate and both its pins were written when those were one predicate. A separate
> planning-seat probe independently found that rev-3's fractional-carry pin **cannot fail on the defect
> it names**. Both `D-R6a-16` and `D-R6a-17` were **not ratifiable as written**; this revision fixes
> that. `D-R6a-17` is promoted from an M1 checkbox to a **second human-gated stop**.
>
> **Standing lesson recorded for REV-0044:** across five passes, every claim in this document that was
> **measured** has survived; nearly every P0 was a claim **derived by reading two files**. Two of this
> revision's findings were a ~25-line simulation away. Prefer running something.

**What R6a delivers:** the durable rail row behind **one** gated DDL, the producer-rail projector that
makes the event log the source of truth for the *foldable* columns, epoch identity, **both** atomic
debits (budget and rate), the release primitive, and a snapshot-free transition-event builder R6b's
sweeps consume.

**The crown jewel:** a debit — and its epoch opener — happen **if and only if** the event is actually
written. rev-1 would have broken this; rev-2 stated it for the debit but not the opener, and offered a
discriminator that does not discriminate. See D-R6a-4.

---

## Scope boundary

**IN (R6a) — everything below HTTP:**
- `app/store/**` — the rail row; epoch state; the **budget** debit inside `ingest_signal`; the
  **rate** check-and-debit primitive + breach opener (D-R6a-16); the release primitive; dual-store.
- `app/events/**` — the producer-rail projector, its **registration in `replay.py`** (D-R6a-3.7), and
  a snapshot-free identity-only transition-event builder.
- **`app/models.py` is NOT needed** — `PRODUCER_QUARANTINED` / `PRODUCER_RELEASED` already exist at
  **`app/models.py:483-484`**, no new event *types* are required, and both artefacts rev-3 put here
  belong in the store layer by this repo's own precedent: the verdict DTO as a
  `@dataclass(frozen=True)` beside `SignalIngestResult` (**`app/store/base.py:328-338`** — the very
  anchor this WO already cites), and the payload as a `producer_quarantined_event(...)` builder in
  `app/store/core.py` beside `signal_duplicate_conflict_event` (`:5922`). No signal event payload is
  typed anywhere: `ExecutionEvent.payload` is `dict[str, Any]` (`models.py:1159`) and there is no
  `TypedDict` in `app/`, so a typed payload model would be unenforced by the append path regardless.
- **The new SQLite table + `_migrate` + startup guard + `tests/test_signal_sqlite_schema.py`** — behind
  the DDL gate below.
- **`app/facade/signals.py`, `app/facade/signal_commands.py`, `app/api/routes_signals.py`** — minimal
  plumbing to surface the post-exhaustion outcome (D-R6a-8). `facade/signals.py` is **required**:
  `mypy app/` fails at `:102` and `:104` without it once the record is Optional (and at
  `app/store/memory.py:5609`).
- `tests/**`.
- **`work/queue|review/**`** — this WO's status/disposition, its `work/ledger.jsonl` line, and
  `work/review/REV-0044/request.md` — and **`pkl/architecture/signal-seat.md`**, which carries a dated
  per-rung change-log entry that R4, R5a, R5b-1 and R5b-2 all appended to (`:88-110`). CLAUDE.md's
  close-out rule makes these part of the work; CI fails a completed WO parked in a live folder.

**OUT — R6b (WO-0104b):** `app/signals_rails_impl.py` · the provider / `check_ingest` / `SignalRails` /
`is_conforming_rails` / **`app/facade/signal_rails.py` and its `RailsDecision`** · `app/api/deps.py` ·
the **in-memory rejected-counter holder** · the §3 sweeps in `app/monitoring.py` · `/api/producers` +
the release **route** · the cockpit control · `signal_rate_limit_per_hour` / `signal_rate_burst` +
`.env.example` · the launcher positive control · **the step-2 rails call site itself.**

**OUT — later:** R7a/R7b conversion; D-2a.

**`app/server.py` is FORBIDDEN** and stays accurate through R6a, because R6a does **not** create
`app/signals_rails_impl.py`. R6b refreshes it.

---

## ⚠ HUMAN-GATED: TWO approval stops, submitted as ONE request

Both are human-gated per CLAUDE.md and **neither is covered by this WO's M1 ratification**. Submit them
together so the operator has one decision point, not two.

### Stop 2 — the `PRODUCER_QUARANTINED` payload (event-log truth)

`D-R6a-17` ratifies an **append-only event-log payload vocabulary**, including
`breach_trigger ∈ {budget_exhausted, rate_breach}`. CLAUDE.md lists "event-log truth changes" in the
same human-gated sentence as "schema/DB migration", and **this repo has already ruled on exactly this
class**: `work/queue/SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md:110-113` — *"This is an **event-log-truth
change on a human-gated surface** ⇒ operator ratification **plus** its own review packet before any rung
relies on it."* (The `detected_by:"conversion"` token in R5b-2 required exactly such an explicit
ruling.) rev-3 self-ratified this in an M1 checkbox, which was wrong. **STOP and request approval of the
field list and the `breach_trigger` vocabulary before the first append.** Nothing emits these events
today — `grep -rn "PRODUCER_QUARANTINED\|PRODUCER_RELEASED"` over `app/ tests/ cockpit/ harness/`
returns only the two enum members and their model test — so there is no back-compat cover and no
migration owed (`ExecutionEvent.payload` is `dict[str, Any]`; `EXECUTION_EVENT_SCHEMA_VERSION = 1`
marks incompatible *shape* changes, `models.py:1149-1150`).

### Stop 1 — the SQLite DDL

New durable state ⇒ schema/migration ⇒ human-gated per CLAUDE.md, **not** covered by this WO's
ratification. **STOP and request approval with the proposed DDL** before creating or altering any table
or column. The request must include **all six** of:

1. The full rail table — including the **token-bucket columns**, since Option A makes R6a their writer.
   One approval, one migration; **R6b adds no schema.** State the **column types and the fractional-carry
   form** chosen per D-R6a-16.1 — getting this wrong costs a *second* migration, i.e. a second human gate.
2. **The pinned-limit column MUST be nullable** — because a **rate-breach-only** cycle has no first
   attributable-rejection event to read a limit from (`03-rails.md:66,79`), so it can exist with no
   pinnable limit. (A rate breach opening *mid-cycle* does have one — see D-R6a-17's two shapes; the
   nullable case is the rate-breach-only cycle specifically.) `NOT NULL` would force a backfill from live
   `Settings`, silently making config changes retroactive against `03-rails.md:83-87`.
3. `_migrate` — and the disclosure that **`SCHEMA` + `_migrate` run flag-independently**
   (**`sqlite.py:562-563`**; the store layer has zero `signal_seat_enabled` references), so this table
   lands in the operator's live database **with the flag off**.
4. An **R4-style startup guard**: exact-column equality that **refuses startup**, plus the UNIQUE-key
   guard — the precedent for the last durable signal table is `sqlite.py:1041-1082` and `:1083-1101`.
   Without it the rail table ships tamper-blind and an altered column silently serves a wrong budget.
5. The `tests/test_signal_sqlite_schema.py` update.
6. **⚠ The truth-model partition of D-R6a-3, stated per column.** A schema reviewer must be told which
   columns an `initialize()` rebuild may overwrite (**log-derived**) and which it must **preserve**
   (**primary durable** — the bucket). Without this the DDL is approvable while the rebuild silently
   resets the rate rail on every restart.

---

## M1 — Assumption ledger / decision block (rev-4)

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

- [x] **D-R6a-2 Both debits are atomic with their appends — AND `_atomic()` IS A HAND-MAINTAINED
      ENUMERATION R6a MUST EXTEND (⚠ P0).** Deciding availability, consuming, and appending are **one
      store operation**: **`memory.py:5580-5581`** (`async with self._lock: with self._atomic():`),
      `sqlite.py:7655-7656` (`async with self._lock: with self._tx() as cur:`). `cycle_budget_limit` is
      already a required kwarg (`base.py:1329`), already stamped (`core.py:5904-5905,5957`) and validated
      (`:6043-6048`).
      **But the two stores are not symmetric.** SQLite's rollback is automatic (`_tx` issues `ROLLBACK`,
      `sqlite.py:542-557`). The memory store's is a **literal per-field list** (`memory.py:502-565`):
      each collection is snapshotted on enter (`saved_signals` at **`:533`** is the trace of WO-0134
      having had to extend it) and restored in a matching block, with the event log truncated at
      **`:563`**. R6a introduces **at least three** new in-memory collections — the rail row cache, the
      epoch sequence, the token bucket. **Every one is added to BOTH halves in the same change.** Miss one
      and an exception inside the atomic op truncates the event log while the rail debit survives: the
      cache permanently **over**-counts — the mirror image of the P0 D-R6a-4 closes. Invisible to
      dual-store parity (memory is the wrong side) and invisible on the happy path.
      rev-2's citation of `memory.py:502-518` as "real rollback" pointed at the signature and docstring,
      not the enumeration.
      **Pin:** force an exception after the debit and at/just before the append inside `ingest_signal`;
      assert consumed count, epoch state, bucket state **and** the event log all revert — both stores.
      Mutation-check per D-R6a-13: drop one field from the restore block ⇒ RED.
      — TRACED(anchors above; `03-rails.md:44-54`; M4b-4 F-1).

- [x] **D-R6a-3 ⚠ P0 — The rail row has TWO CLASSES OF COLUMN. Only one is a cache.** rev-2 called the
      whole row "a CACHE rebuilt at `initialize()`". Applied to the token bucket that is a **rate-rail
      bypass**: every restart hands the producer a free full burst.
      **(A) Log-derived — the cache.** Rebuilt at `initialize()` before serving (`03-rails.md:71-72`), in
      the `_backfill_*_unlocked` style (`memory.py:264-280`; `sqlite.py:644-646` mirrors it). **Inside**
      the live-vs-replay agreement claim. `03-rails.md:74-82`: "**Replay is event-authoritative** … the
      event log alone must reconstruct the binding budget … the limit is read from the cycle's first such
      event. A side table/snapshot **may cache** this … but it is **not** the source of truth."
      1. consumed count, folded since the last `PRODUCER_RELEASED`;
      2. the pinned limit, read from the cycle's **first** attributable-rejection event;
      3. a **producer-rail projector** — none exists; `projectors.py:850-852` ignores unknown types
         (`PRODUCER_*` is absent from `_SIGNAL_TRANSITION_STATUS` at `:803-808`), so it is purely additive;
      4. the rebuild itself;
      5. **⚠ current quarantine state** — a restart that restores the budget but not the quarantine flag
         **un-quarantines a quarantined producer**, and this is the exact state R7a reads
         (`05-conversion.md:12` "the producer quarantine epoch") in the rung that starts right after
         REV-0044;
      6. **⚠ the epoch sequence** that D-R6a-5 depends on;
      7. **⚠ registration in `app/events/replay.py`** — `ReadModelProjection` gains a `producer_rails`
         field, `project_read_models` (`:175`) folds it, `_describe_read_model_diff` (`:199`) reports it,
         so `compare_read_models` (`:249`) and `verify_dual_store_readmodel_parity` (`:262`) cover the new
         co-written columns. `project_read_models`'s docstring already claims "**the canonical replay
         reconstruction of every co-written read-model column**" (`:176-178`) — omitting registration makes
         that text false, and `work/review/REV-0039/disposition.md:20-23` already records this exact
         un-registered-fold class: "removing `signals=project_signal_records(...)` from
         `project_read_models` **left the suite green**". **Mutation-check it:** delete the registration ⇒
         must go RED.
      **(B) Primary durable — NOT foldable, never rebuilt.** The token-bucket columns
      (`tokens`, refill anchor). `03-rails.md:11-12` debits the bucket on "**every authenticated
      request** … whether it validates, quarantines, or duplicates" — and a same-hash replay appends
      **no event at all** (`core.py:6052-6059`, `outcome=SIGNAL_REPLAYED, event=None`). So the log holds
      no evidence of those debits and the bucket is **not reconstructable**. `02-lifecycle.md:117-118`
      scopes the event-authoritative claim precisely — "**+ consumed/remaining count) is reconstructed
      from the event log alone**" — to the budget rail only. `initialize()` **preserves** these columns.
      **Required proof: live-vs-replay agreement in both stores over class (A) ONLY** — **excluding the
      bucket columns and `rejected_count`** (D-R6a-7), for which the log holds no independent evidence
      and the claim would be vacuous. REV-0044 must not over-claim either.
      **Pin:** append events + spend the bucket, restart ⇒ the budget/quarantine/sequence rebuild from
      the log **and** the bucket is neither refilled nor zeroed. Both stores — where **"restart" means a
      fresh `SqliteStateStore` over the same file for SQLite, and a second `initialize()` on the same
      instance for memory.** A memory-store process restart has nothing durable to preserve
      (`memory.py:264-280` rebuilds an empty instance), so class-(B) preservation is unobservable there
      through a real restart; the memory-side claim is that the rebuild is **bucket-idempotent**. Say which
      reading is meant or the implementer must guess.
      — TRACED(`03-rails.md:11-12,71-82`; `02-lifecycle.md:109-124`; `core.py:6052-6059`;
      `replay.py:175-196,199-227,250-274`; REV-0039 disposition:21; M4b-4 F-2/F-9).

- [x] **D-R6a-4 ⚠ P0 — THREE fold exclusions; the debit AND THE OPENER are conditioned on the event
      actually being written; and the discriminator is IDENTITY, never `sequence`.**
      `03-rails.md:36-41` gives three exclusions:
      1. `SIGNAL_QUARANTINED` with `quarantine_reason = producer_sweep`;
      2. `SIGNAL_EXPIRED` with `detected_by ≠ "ingest"` (R6b's periodic sweep — a non-debiting event of a
         type that *is* on the debit list);
      3. **a same-hash (deduped) `SIGNAL_DUPLICATE_CONFLICT`** — "each **novel-hash**
         `SIGNAL_DUPLICATE_CONFLICT` (a same-hash replay is already coalesced to one event … and **does
         not re-debit**)".
      **The mechanism.** `signal_duplicate_conflict_event` keys on `new_payload_hash` (`core.py:5941`), so
      resubmitting the *same* conflicting payload hits the dedupe no-op (`memory.py:5433-5435`,
      `sqlite.py:7428-7437`) — and **both call sites discard the append's return value**
      (`memory.py:5603-5604`, `sqlite.py:7683-7684`). Measured: `A, B, B` ⇒ two `conflict` outcomes,
      **one** logged event, both stores. A debit keyed on `plan.event is not None` **charges 2 for 1
      logged event**: the cache diverges permanently from the fold on the very quantity the spec declares
      event-authoritative, and a restart *grows the budget back*.
      **The discriminator is `stored.id == plan.event.id`.** Both helpers **already return
      `ExecutionEvent`** (`memory.py:5419`, `sqlite.py:7415`), so **no signature change is required**.
      Two rejected alternatives:
      - **`sequence` is NOT a valid predicate.** The no-op returns the *existing stored* event, whose
        sequence is real. `models.py:1125-1127` says so in terms: "the store overwrites it with
        ``max_sequence + 1`` under its write lock, so **a persisted event always has `sequence >= 1`**"
        (`sqlite.py:401` is `sequence INTEGER NOT NULL UNIQUE`). So `returned.sequence ≥ 1` holds after a
        write **and** after a no-op. rev-2 offered "identity/sequence" as a disjunction; an implementer
        taking the second branch ships the exact P0 this line closes.
      - **An explicit `wrote: bool` is REJECTED** — it would retype two shared helpers with **29 call
        sites each** (`_append_execution_event_unlocked` in `memory.py`, `_insert_execution_event` in
        `sqlite.py`), far outside R6a.
      **⚠ And the OPENER obeys the same predicate.** D-R6a-6 has the *pure planner* emit
      `epoch_event` — decided before the append, from a consumed count of limit−1. If the terminal append
      then no-ops, the debit is correctly skipped **but the opener would still land**, appending a
      producer-level `PRODUCER_QUARANTINED` at a count replay says is **not** exhaustion. That is the same
      P0 re-entering through the opener, and worse: an append-only quarantine the fold disagrees with.
      **Therefore the store ratifies the opener post-append — if `plan.event`'s append did not write, the
      store suppresses `plan.epoch_event` and performs no debit.** The planner proposes; the store decides.
      **And the check is two-sided:** the store also inspects **`plan.epoch_event`'s own** append return.
      A no-op there means an epoch was **already open** — a state D-R6a-8's gate should have refused
      before the planner ran — so **fail closed** (raise, do not proceed): silently continuing is how the
      D-R6a-8 P0 manifests as a log that says `rate_breach` while the store believes it opened a
      budget-exhaustion epoch.
      **Pins (both stores):** (i) `A, B, B` ⇒ consumed == 1, cache == fold; (ii) consumed at limit−1, the
      same novel-hash conflict submitted twice ⇒ one conflict event, one debit, **exactly one** opener;
      (iii) the same at limit−1 with a *fresh* hash ⇒ one opener. Mutation-check: remove the suppression
      ⇒ a spurious/second opener, RED.
      — TRACED(`03-rails.md:36-41`; anchors above; M4b-4 F-3/F-5; planning-seat verified).

- [x] **D-R6a-5 Epoch identity = a folded monotonic per-producer sequence; dedupe keys epoch-scoped **for
      the two `PRODUCER_*` events ONLY**.** A duplicate `dedupe_key` is a **silent idempotent no-op
      returning the existing event** in *both* stores (`memory.py:5433-5435`, `sqlite.py:7428-7437`), so
      parity tests cannot see a lost event. A naive `producer_quarantine:{producer_id}` key would silently
      drop epoch #2's opener and every later `PRODUCER_RELEASED`. Include the sequence in the `dedupe_key`
      of **both** `PRODUCER_QUARANTINED` and `PRODUCER_RELEASED`.
      **`signal_conflict` (`core.py:5940-5945`) and `signal_create` (`core.py:5912-5914`) stay GLOBALLY
      scoped.** Epoch-scoping them would make a post-release same-hash resubmission a *new* event and a
      *new* debit, breaking `01-schema.md:102-104` ("further conflicting replays … are boundary-rejected
      409 with coalesced audit only") and `03-rails.md:39`. Global scoping is also self-consistent with the
      fold, which counts events *since* the last `PRODUCER_RELEASED`, so a cycle-1 event replayed in
      cycle 2 counts zero live **and** on replay — load-bearing, so pin it.
      **Note the key format is length-prefixed** (`core.py:5641-5642`:
      `encoded = "|".join(f"{len(part)}:{part}" ...)` → `signal_create:{len}:{producer}|{len}:{signal}`),
      deliberately, to keep tuple boundaries injective for untrusted identities (`core.py:5636-5639`). A
      pin written against a plain `prefix:{a}|{b}` literal will fail.
      **Exactly-once rests on the single `asyncio.Lock`** (`memory.py:5580`, `sqlite.py:7655`) plus the
      existing in-transaction SELECT-then-INSERT check-and-set (`sqlite.py:7428-7437`); the UNIQUE index
      (`sqlite.py:406`) is **not** the mechanism and a cross-process collision surfaces as `SQLITE_BUSY`,
      not `IntegrityError`. **State explicitly whether the write-time sequence comes from the log fold or
      the cache**, and pin it: zero/stale the cache, prove the opener still lands with the correct
      sequence inside the same atomic op.
      **⚠ And state what the sequence function returns WHILE AN EPOCH IS OPEN.** There is no next epoch
      until `PRODUCER_RELEASED`, so the only two candidate answers are (a) the current open epoch's
      sequence — which makes a second opener's key **collide and silently no-op** (measured, both stores),
      the D-R6a-8 P0 — or (b) N+1, which yields two simultaneously-open epochs and an unresolvable
      `release_producer`. Neither is acceptable, which is why D-R6a-8's gate must make this code
      unreachable; D-R6a-4's two-sided check is the backstop if it is not.
      **Pins:** release → re-quarantine → release ⇒ 2 openers, 2 releases; and exhaust → release →
      resubmit a cycle-1 novel hash ⇒ zero new events, zero debits, cache == fold. Both stores.
      — TRACED(anchors above; `01-schema.md:102-104`; M4b-4 F-10).

- [x] **D-R6a-6 The epoch opener is an ADDITIVE plan field — do NOT retype `event`.** The exhausting
      append must carry its terminal event **and** the single `PRODUCER_QUARANTINED` in one op
      (`03-rails.md:55-66`). `SignalIngestPlan.event` is a single `Optional[ExecutionEvent]`
      (`core.py:5968`) and is **read at seven sites** in `tests/test_signal_ingest_properties.py`
      (`:198,203,204,281,300,301,306`) — retyping it breaks all seven. **Add
      `epoch_event: Optional[ExecutionEvent]`** instead; measured, that plus one new required kwarg
      leaves the full suite green with **only** the `:79` edit. Sole planner callers: `memory.py:5583`,
      `sqlite.py:7663`, and the test at `:61`. The opener is **proposed** here and **ratified by the store**
      per D-R6a-4.
      — TRACED(`core.py:5968`; the seven sites; measured).

- [x] **D-R6a-7 The release PRIMITIVE — full signature, validated, and two fields excluded from the
      agreement claim.** R6a lands
      **`release_producer(producer_id, *, actor: str, rejected_count: int, released_at: datetime)`**:
      one atomic op closing the epoch, resetting **both** rails (`02-lifecycle.md:51` — else the producer
      re-quarantines on its next ingest), writing `PRODUCER_RELEASED` with **`actor`** (required by
      `02-lifecycle.md:55` and `03-rails.md:175`; an append-only event cannot be fixed after the fact),
      the count, and the epoch window. `released_at` is **injected** — the repo pattern is
      `ingest_signal(..., received_at=...)` (`base.py:1332`); note **both** `memory.py:274` **and
      `sqlite.py:648`** already regress to a bare `utcnow()` inside `initialize()` and must **not** be
      copied.
      **The counter must NOT be store state:** A-4 specifies a "saturating **in-memory** counter outside
      the event log (diagnostic, **best-effort across restarts by design**)" (`03-rails.md:163-164`;
      `ADR-009:53,346-347`) and **T-14** requires post-quarantine rejects stay **write-free**
      (`THREAT_MODEL_SIGNAL_SEAT.md:64`); a durable counter would make every post-quarantine reject a
      store write, contradicting `03-rails.md:157-158`. **R6b owns the in-memory holder.**
      Because the count is caller-supplied: **validate it** (`0 ≤ count ≤ cap`) in the primitive, on the
      `_require_bounded_int` precedent (`core.py:6043-6048`), and **define the saturation cap here** next
      to `_SIGNAL_CYCLE_BUDGET_MAX` (`core.py:5607`) — accepted text says "saturating" but never gives a
      value, so R6a must ratify one rather than let R6b's holder saturate at an unrelated number.
      `rejected_count` is **OUTSIDE** D-R6a-3's agreement claim, alongside the bucket columns.
      — TRACED(anchors above; M4b-3 F-7/F-8; M4b-4 F-13).

- [x] **D-R6a-8 ⚠ P0 — The post-exhaustion outcome: correct cause, in-store ordering, and the one
      sanctioned retype.**
      **The cause rev-2 stated was wrong.** rev-2 said post-exhaustion rejects originate "inside
      `ingest_signal`". They mostly do not. The append consuming the **last** slot co-appends the opener in
      the same op (`03-rails.md:55-66`), so from that instant the producer **is quarantined** and every
      later ingest is rejected at **step 2** — "Steps 1–2 reject with zero store writes and zero body
      processing" (`03-rails.md:149-150`) → 403 via `RailsDecision`, **never reaching the store**. That
      steady-state path is **R6b's**.
      What genuinely reaches step 4 with zero slots is only the **race**: requests that all cleared step 2
      while the epoch was still closed. `03-rails.md:48-51`: "with one slot left and N **concurrent (or
      slow-streamed-body)** requests, **exactly one** appends its terminal event and consumes the slot;
      the rest find zero and are handled as post-exhaustion". The slow-streamed-body case is the realistic
      one — that is *how* two requests both clear step 2 before either reaches step 4 — so the pin must
      model it, not just concurrency.
      **⚠ P0 — THE GATE IS `epoch-open OR zero-slots`, NOT EXHAUSTION ALONE. Option A decoupled them.**
      Before Option A the only opener was budget exhaustion, co-appended with the last-slot terminal
      event, so `epoch open ⟺ consumed ≥ limit` and one predicate served both. **The rate primitive is a
      second opener**, so an epoch can now be open with the **entire budget unspent** — and that state is
      not exotic, it is the *ordinary* rate breach: only attributable **rejections** debit the budget
      (`03-rails.md:35-43`), so a fresh producer bursting `burst+1` **valid** signals breaches the rate
      rail at `consumed == 0`. The race shape produces it too: X takes the last token and streams a slow
      body; Y finds the bucket empty and opens the epoch; X then arrives at step 4 with the epoch open
      and slots remaining.
      An implementer reading rev-3's "epoch/exhaustion check" as `if consumed >= limit` satisfies **both**
      of rev-3's pins and still ships a defect against accepted text: `ingest_signal` proceeds and appends
      attributable-rejection events **inside an open epoch**, against
      **`ADR-009-signal-seat-boundary.md:343-345`** — *"At most ONE `PRODUCER_QUARANTINED` event per
      quarantine epoch … opened by **either** trigger … **Post-quarantine ingress appends nothing**"* —
      and `03-rails.md:151-153`. Then, when the budget finally exhausts, the co-appended opener's
      epoch-scoped `dedupe_key` **equals the already-open epoch's key and silently no-ops in both
      stores** (measured): the store believes it opened a budget-exhaustion epoch while the log says
      `rate_breach`. Build hazard 15 names the mechanism but rev-3 never connected it to `epoch_event`.
      **So: the gate is `epoch_open OR consumed >= limit`.** The branch to move lives in
      `plan_signal_ingest` (`core.py:6013`, the `existing` test at `:6052`) — reachable either by
      reordering there or by gating in `ingest_signal` before the planner is called. Note the planner
      **cannot** decide this today: measured, its parameters include `cycle_budget_limit` but **no**
      consumed-count, epoch or quarantine input, so R6a adds one (the new required kwarg of D-R6a-6).
      **⚠ In-store ordering.** `01-schema.md:86-92` is normative: "**Boundary rejection takes
      precedence over idempotent replay** … its request, *even an identical replay of an already-accepted
      signal*, is boundary-rejected **403/429**, not 200 … the dedupe contract below is scoped to
      **admitted** ingests only." `plan_signal_ingest` currently does the **opposite** — `core.py:6052`
      `if existing is not None:` precedes anything budget-related (measured: with `cycle_budget_limit=1`,
      an identical replay returns `replayed`). **The gate above must precede the `existing`/`payload_hash`
      dedupe branch.**
      **Representation.** Verified blockers:
      1. `SignalIngestResult.record` is **non-Optional** (`base.py:337-338`, `signal_commands.py:26-27`);
      2. **`SignalIngestPlan.result_record` (`core.py:5969`) becomes `Optional[SignalRecord]` — the ONE
         sanctioned retype in this dataclass**, and the reason `memory.py:5609`
         (`plan.result_record.model_copy(deep=True)`) is mypy-affected while `sqlite.py:7689` (a plain
         pass-through) is not. Its test read sites
         (`test_signal_ingest_properties.py:192,199,202,243,247,283-285,303,304,307`) stay runtime-safe
         because the gate is `mypy app/` only. **`event` still gets the additive sibling** (D-R6a-6) —
         do not generalise this retype to it;
      3. `_OUTCOME_STATUS` is a literal 6-entry dict subscripted **bare** (`routes_signals.py:45-52`,
         used at `:202`), so a 7th outcome is a `KeyError` → 500, then
         `SignalRecordView.model_validate(None)`.
      **Not a blocker:** a missing `except FacadeError` — the outcome arrives as a *return value*; the
      facade raises `RuntimeError` (`facade/signals.py:94-98`) and the store `ValueError`
      (`core.py:6118-6120`), neither a `FacadeError`.
      R6a adds the outcome, makes the record Optional through **both** layers, adds the `_OUTCOME_STATUS`
      entry and a **record-free 403 branch** — and note `_record_response` has **two** ingest call sites
      (`routes_signals.py:261-277` malformed-body and `:279-291`), both of which must be safe.
      **⚠ The gate battery cannot catch this.** With the record Optional and `:200` untouched,
      `mypy app/` returns **Success** (`model_validate` takes `Any`); ruff and lint-imports are equally
      blind. Provable **only** by a mounted-app runtime pin, and D-R6a-13's mutation check **must**
      include it (revert the branch ⇒ assert the 500).
      **Why it belongs in R6a even though nothing goes live:** the debit does **not** activate on merge —
      `main.py:249-250` mounts the route only flag-on, `config.py:192` defaults it off, and flag-on
      requires a conforming provider (`main.py:118-123`) which `server.py:33-40` refuses because
      `app/signals_rails_impl.py` does not exist after R6a. The touch is required because **the sanctioned
      test seam already mounts the route flag-on with `PermissiveSignalRails`**
      (`tests/signal_seat_helpers.py:32-36`, mounted by `build_flag_on_app` at `:54-82`, used at
      `tests/test_signal_routes.py:52-56`) and the pin is stated in HTTP terms.
      **Pins (both stores):** (i) N requests **serialised by the single writer** (model the slow-body
      shape, not just concurrency), one slot ⇒ exactly one terminal + N−1 record-free 403s + exactly one
      opener; (ii) with the epoch open, an **identical replay of an already-accepted signal** returns the
      403, never 200; (iii) **⚠ the P0 pin — a rate-breach epoch at `consumed == 0`, then a novel-hash
      invalid submission ⇒ ZERO new events, zero debit, and still exactly ONE `PRODUCER_QUARANTINED` row
      in the log.** Mutation-check (iii) by weakening the gate to `consumed >= limit` ⇒ must go RED; that
      mutation is precisely what rev-3's pins allowed.
      — TRACED(`01-schema.md:86-92`; `03-rails.md:48-51,145-146`; `core.py:6052-6059`; anchors above;
      M4b-3 F-4/F-5/P2-11; M4b-4 F-4/F-12).

- [x] **D-R6a-9 A snapshot-free, identity-only transition-event builder with distinct dedupe prefixes.**
      `signal_record_event` (`core.py:5892-5919`) **always** keys on the `signal_create` prefix (literal at
      `core.py:5913`, length-prefixed per D-R6a-5) and **always** embeds a full record snapshot
      (`:5879-5889`). Both §3 sweeps transition an **already-born** record, so reusing it either
      (a) collides with the birth event → **silent no-op**: the record mutates while **no event is
      written**, breaking D-R6a-3's fold proof invisibly; or (b) carrying the snapshot,
      `projectors.py:795-801,838-841` classifies it as a **creation** and overwrites instead of
      transitioning, against `02-lifecycle.md:120-124`. R6a lands the builder (distinct prefix per
      transition, identity-only payload) and pins it against a synthetic transition; R6b wires the real
      sweeps.
      — TRACED(anchors above).

- [x] **D-R6a-10 No new settings in R6a — and this survives Option A.** The budget limit arrives as a
      parameter (`base.py:1329`), read from `Settings` by the *facade* (`facade/signals.py:88`). **The
      store layer reads no config at all** — the only `Settings` references under `app/store/` are the
      factory (`__init__.py:43`) and two docstrings (`base.py:353`, `:808`), both describing
      caller-validated values passed in. The rate primitive takes `limit_per_hour` and `burst` the same
      way, supplied by **R6b's provider** at the step-2 call site. So the two rate settings, their caps,
      their flag-independent validation, and `.env.example` are **R6b's**, and R6a needs **no `config.py`
      change**. (The *architectural* caps for the rate values are ratified in R6a — D-R6a-16 — because
      they belong with the primitive that validates them, not with the config that supplies them.)
      — TRACED(`base.py:1329,353,808`; `store/__init__.py:43`; `facade/signals.py:88`; measured: zero
      `Settings` reads in any store implementation).

- [x] **D-R6a-11 SIX stale claims R6a invalidates — refresh all of them in the same change.** Beyond
      `base.py:1339-1340`: **`base.py:332`**, **`core.py:5577`**, **`core.py:6034`**,
      **`signal_commands.py:14`** (all say "six outcomes"), and **`base.py:1336-1338`** ("a changed
      payload appends **only** an audit-conflict event" — it now debits and may co-append the opener).
      Also `app/facade/signals.py:88` passes a live `Settings` read every ingest; its meaning becomes
      "the limit to pin **iff** a new cycle begins". The 7th-member edits (`SIGNAL_INGEST_OUTCOMES` at
      `core.py:5590-5599`, `SignalIngestOutcome` at `signal_commands.py:16-21`, `_OUTCOME_STATUS` at
      `routes_signals.py:45-52`) follow from D-R6a-8. Six test files pass `cycle_budget_limit=` directly
      and two assert the stamped value (`tests/test_signal_ingest_store.py:141,188`;
      `test_signal_ingest_properties.py:305`) — those must keep holding. **Independently swept: the
      "six outcomes" family has exactly these four production sites**; all other hits are `work/**`
      history, `.claude/backups/**`, and REV packets. CLAUDE.md's close-out rule makes refreshing
      invalidated claims part of the work, not a follow-up — **including the `pkl/` change-log entry**
      (scope IN).
      — TRACED(anchors above; M4b-3 P2-13; M4b-4 stale-claim sweep).

- [x] **D-R6a-12 Existing tests: ZERO breakage expected — MEASURED, with a named tripwire list.** The
      claim held under measurement: full suite green with exactly the `:79` edit, and suite-wide maximum
      attributable rejections per (store, producer) is **2** against a budget of 50. Authorized edits:
      **only** `tests/test_signal_ingest_properties.py:79` (the `plan_signal_ingest` kwarg, D-R6a-6) and
      `tests/test_signal_sqlite_schema.py` (the DDL). **Tripwire — if any of these seven sites needs
      editing, `event` was retyped instead of adding `epoch_event`, and that is a STOP:**
      `test_signal_ingest_properties.py:198,203,204,281,300,301,306`. Any other existing-test edit is
      likewise a **STOP** — it signals scope leaked into R6b's. Independently checked as surviving a 7th
      outcome and a new table: `test_signal_ingest_properties.py:254-263` (sum-is-1 + membership) and
      `test_phase7_schema.py:117-123` (membership, not equality).
      — TRACED(measured; the seven sites; `test_signal_seat_launcher.py:129-137` and
      `test_signal_routes.py:91-102` both keep passing because R6a creates no provider module and does
      not touch `check_ingest`).

- [x] **D-R6a-13 No pre-authored corpus ⇒ implementer mutation-checking is MANDATORY.** For every decisive
      pin: revert the control, prove RED, restore, paste the red-green evidence. It **must** include
      (i) the D-R6a-8 record-free branch (invisible to every static gate), (ii) the D-R6a-4 opener
      suppression, (iii) the D-R6a-2 `_atomic()` restore fields, and (iv) the D-R6a-3.7 `replay.py`
      registration. REV-0041's inert pin, REV-0043's F-1, and REV-0039's un-registered fold all arose
      exactly where a corpus was authored fresh.
      — TRACED(staging tree; REV-0039/0041/0043; M4b-3 F-4; M4b-4 F-9).

- [x] **D-R6a-14 Flag stays OFF; flag-off byte-equivalence is scoped to the HTTP SURFACE ONLY.** R6a
      mounts no route and changes no request-time behaviour flag-off. **But it is NOT byte-equivalent at
      the database:** **`sqlite.py:562-563`** runs `SCHEMA` + `_migrate` **unconditionally** (zero
      `signal_seat_enabled` references in the store layer; measured — a flag-off `Settings` still creates
      `signal_records`), so the rail table lands in the operator's live DB with the flag off. Say so in
      the DDL request. `harness/bootstrap.py` green; all three hygiene scripts green.
      — TRACED(`sqlite.py:562-563`; measured).

- [x] **D-R6a-15 Dual-store parity throughout.** Rail state, both debits, epoch, release, the projector
      fold, the `initialize()` rebuild **and its bucket-preservation counterpart**, and the `_atomic()`
      rollback all prove out on **both** stores — with **"restart" defined per store** as in D-R6a-3
      (fresh `SqliteStateStore` over the same file; second `initialize()` on the same memory instance).
      — TRACED(CLAUDE.md Testing; `conftest.py:29` `any_store`; `memory.py:264-280`).

- [x] **D-R6a-16 ⚠ P0 RESOLUTION (operator: Option A) — the RATE-PATH store primitive is R6a's, it is a
      STEP-2 primitive, and it ships with ZERO consumers in this rung.** rev-1 gave R6a `app/store/**` but
      wrote no D-line for the rate path, while giving R6b the bucket *logic* without `app/store/**` — so
      the bucket columns would have shipped with **no authorized writer**. **Option A ratified:** R6a lands
      it. Consequences to honour:
      0. **⚠ It CANNOT live inside `ingest_signal`.** `03-rails.md:139-141` fixes the normative order —
         (1) authenticate, (2) rails check *quarantine epoch, rate limit*, (3) bounded body read,
         (4) parse — and §1 requires the rate decision "**before the body is read or parsed** … no
         'otherwise-valid' qualifier, which would require parsing before the rate decision and defeat
         A-4's pre-body defense". `ingest_signal` is step 4 and its signature proves it: `symbol: str`,
         `direction: str`, `thesis: str`, `provenance: dict[str, str]` are required non-Optional kwargs
         (`base.py:1320-1332`). So the rate rail is a **separate `StateStore` method**, reachable from
         authenticated producer identity alone.
         **Signature ratified here:**
         **`check_and_debit_producer_rate(producer_id, *, now: datetime, limit_per_hour: int, burst: int)`**
         → a **verdict DTO as a `@dataclass(frozen=True)` in `app/store/base.py`, beside
         `SignalIngestResult` (`:328-338`)** — the store-layer DTO precedent, not `app/models.py` —
         discriminating `ok` / `quarantined` (403) / `rate_breached` (429, opener appended). It must
         **not** return `RailsDecision`: that lives in `app/facade/signal_rails.py`, which **R5a already
         merged** and which is **OUT** for R6a, so returning it would silently edit an out-of-scope file.
         R6b's provider maps the verdict.
         **⚠ `lint-imports` does NOT guard this.** Measured: `app.store` is a **source** module in none of
         the six contracts (it appears only in `forbidden_modules` at `.importlinter:104,150,192`), so
         `app.store → app.facade` passes green (`lint-imports` → 6 kept, 0 broken). Enforce it with a grep
         assertion in the R6a corpus — *no file under `app/store/` imports `app.facade`* (true today:
         `grep -rn "from app.facade" app/store/` returns nothing) — plus review.
         `now` is **injected** (`03-rails.md:9`; do not copy `memory.py:274` or `sqlite.py:648`).
         `limit_per_hour` / `burst` are **validated** on the `_require_bounded_int` precedent
         (`core.py:6043-6048`). **⚠ Accepted text gives the rate rail NO cap** (`03-rails.md:11-15` gives
         defaults only; the budget rail's `[1, 1000]` at `03-rails.md:32-34` is normative), so R6a
         ratifies these three **literal values** — rev-3 said "caps ratified here" and stated no numbers,
         which is unratifiable:
         - **`SIGNAL_RATE_LIMIT_PER_HOUR_MAX = 3600`** — one authenticated ingest per second already far
           exceeds a single local paper operator's plausible need, and it keeps the "finite and small"
           property from being configured away, mirroring the budget rail's hard 1000.
         - **`SIGNAL_RATE_BURST_MAX = 100`** — bounds worst-case instantaneous pre-body work while
           comfortably exceeding the default 10.
         - **`SIGNAL_REJECTED_COUNT_MAX = 10_000`** (D-R6a-7's saturation cap) — informative across a long
           hostile epoch, still bounded and readable inside an append-only event payload.
         **Declare all three as PUBLIC module-level constants so R6b's `config.py` validation imports them
         rather than re-declaring them.** The repo already carries the budget cap **twice** —
         `SIGNAL_INVALID_BUDGET_HARD_CAP = 1000` (`app/config.py:47`, used at `:478`) and
         `_SIGNAL_CYCLE_BUDGET_MAX = 1000` (`app/store/core.py:5607`, used at `:6047`) — with no shared
         import. Since D-R6a-10 leaves config-side validation to R6b, a private constant here **guarantees**
         that duplication recurs on a hostile-input rail. Do not repeat it.
      1. **The epoch check lives INSIDE the primitive**, in the same atomic op as the rate debit. That is
         what makes consequence 2 R6a-pinnable; if the epoch check sat in `deps.py` the ordering would be
         R6b's and `app/store/**` would not be complete after all.
      2. **Epoch-check precedes rate-debit** (`03-rails.md:139-141`): a quarantined producer gets **403,
         not 429** (`:157-158`), and **must not burn tokens**.
      3. **The bucket is lazily refilled and evaluated READ-ONLY on the reject path.** This is sound
         because refill is a pure monotone function of `(anchor, tokens_at_anchor, now)` — recomputing
         from a stale anchor yields the same answer across restarts and idle gaps. A natural "update the
         anchor on every evaluation" makes post-quarantine 403s and 429s store writes, violating
         `03-rails.md:157-158` and T-14.
      4. **⚠ The ACCEPT path must not lose the fractional remainder — and the failure is TOTAL, not
         gradual.** Truncating the refill to an integer **and** advancing the anchor to `now` discards the
         sub-token remainder permanently. rev-3 described this as "throttled below its configured rate,
         drifting further with every accept" and illustrated it with two accepts 90 s apart. **Both were
         wrong**, measured: at any arrival gap **shorter than one token interval** the truncated refill is
         `floor(<1) = 0` while the anchor still advances, so **the bucket never refills at all.** At 60/hr
         with 60 requests paced every 30 s: exact-carry grants **30**, truncate-and-advance grants **0**.
         A producer running at **half its configured rate** is therefore starved permanently — and since a
         bucket-empty ingest is what opens an epoch, it is **permanently quarantined**. That makes the
         column-type choice a safety decision, not a tidiness one.
         Choose one and **state it in the DDL request with the column types**: store tokens as `REAL`, or
         keep them `INTEGER` and advance the anchor only by whole-token increments
         (`anchor += floor(elapsed·rate)/rate`).
      5. A rate breach opens an epoch **with no terminal event**, so the fold must handle a cycle whose
         pinned limit is unknowable — hence the nullable limit column (DDL item 2) and the
         `breach_trigger` of D-R6a-17.
      6. **The primitive has ZERO consumers in R6a.** `deps.py:126-138` and the provider are R6b's, so
         nothing in this rung calls it — the same shape as `release_producer` (route is R6b's) and the
         D-R6a-9 builder (sweeps are R6b's). It is proven by **direct store-level pins on both stores**
         with an injected clock and explicit values, not through HTTP; the write-free-reject property is
         pinned **at the store**, not at the boundary. This is *more* provable than a route-mediated
         version, not less.
         **Gate-safety of dead code, checked:** no dead-code gate threatens it — no `vulture`, and
         `pyproject.toml` has **no `[tool.ruff.lint]` section**, so ruff runs default `E4/E7/E9/F`, which
         never flags an uncalled method; `tests/test_air_remediation.py:150-154` reads
         `StateStore.__abstractmethods__` only to assert `create_order` is *absent*, so a new abstract
         method is harmless. **But CI's branch-coverage ratchet does bite:** `fail_under = 93`
         (`pyproject.toml:38`) under `pytest --cov=app --cov-branch` (`.github/workflows/ci.yml:101`).
         The primitive's validation and reject branches, the record-free 403 branch, and the
         `_migrate`/startup-guard path must all be **branch**-covered by their direct pins or CI fails.
      **Pins (both stores):** epoch open ⇒ 403, token count **unchanged**; bucket empty ⇒ 429 **and
      exactly one** opener; two rejects past exhaustion ⇒ zero new event rows and zero bucket mutation.
      **⚠ The carry pin — rev-3's was INERT and must not be reused.** rev-3 pinned "accepts paced at
      1.5× the token interval grant exactly the configured rate with no drift". Measured, the correct and
      the defective implementations are **identical** there (40/40 and 60/60), for two compounding reasons:
      at 1.5× the interval the producer runs *under* the configured rate, so a correct bucket sits at the
      burst cap where truncation costs nothing; and `floor(1.5) = 1` refill against 1 consumption is
      net-zero for the defective one. An idle-then-burst pin is inert too (10/10 both). **Use instead:**
      from a **sub-cap** bucket, accepts paced at a **sub-token-interval** pace (e.g. 0.75× the interval)
      over ≥ 60 requests ⇒ exactly `floor(rate·window) + initial_tokens` accepts, with the first rejection
      at the arithmetically predicted index (measured: request 41 correct vs request 11 defective); **and**
      a bank-then-burst case — pace under the rate, then submit `burst` requests (measured: 29/30 correct
      vs 20/30 defective). D-R6a-13's mandatory mutation check for 16.4 comes out **GREEN** on rev-3's pin,
      which is exactly the inert-pin class REV-0041 and REV-0043-F-1 established.
      **Restart pin — define "restart" per store** (see D-R6a-3): a fresh `SqliteStateStore` over the same
      file for SQLite; a **second `initialize()` on the same instance** for memory, where a process restart
      has nothing durable to preserve (`memory.py:264-280`). The memory-side claim is that the rebuild is
      **bucket-idempotent**, not that memory survives death.
      **No import-boundary blocker:** `.importlinter` Contract 5 forbids `app.store` only from the nine
      named `app.api.routes_*` modules; `app.api.deps` is explicitly excluded (`.importlinter:129-132`)
      and `app.signals_rails_impl` is not a contract source, so R6b's provider can reach this primitive
      without a contract change. **Confirm by running `lint-imports`.**
      — TRACED(`03-rails.md:9,11-12,32-34,44-54,66,139-141,151-152,155-156`; `base.py:1320-1332`;
      `.importlinter:129-132`; operator ratification 2026-07-25; M4b-4 F-7/F-8).

- [ ] **D-R6a-17 ⚠ NOT PRE-CHECKED — the `PRODUCER_QUARANTINED` PAYLOAD is HUMAN-GATED (Stop 2 above).**
      rev-2 specified the release event's payload (D-R6a-7) and left the *opener's* entirely unstated,
      while Option A made R6a its writer on **two** paths that need different values. rev-3 then ratified
      it in a pre-checked M1 line — wrong: this is append-only event-log payload vocabulary, which
      CLAUDE.md gates and which this repo has already ruled needs "operator ratification **plus** its own
      review packet before any rung relies on it"
      (`SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md:110-113`). **Proposed** field list, per
      `02-lifecycle.md:54` ("`producer_id`, **breach trigger + counters**, epoch start"):
      - `producer_id`;
      - **`breach_trigger` ∈ {`budget_exhausted`, `rate_breach`}** — required by `02-lifecycle.md:54`, and
        it records the cause **directly** instead of leaving the fold to infer it. **rev-3's necessity
        argument was false** and is withdrawn: a budget-exhaustion opener co-appends with the event
        consuming the last slot, so `consumed == pinned_limit` holds **iff** the epoch is a budget
        exhaustion, and the fold *can* discriminate without the field. The field is still right — the
        inference is correct only until a third opener path exists, and an append-only log cannot be
        amended later — but the honest reason is directness plus `02-lifecycle.md:54`, not impossibility;
      - the counters in force — consumed/limit on the budget path; bucket capacity on the rate path;
      - **`epoch_start` carried as `.isoformat()`** — both stores normalise through
        `normalize_json_payload` (`app/store/base.py:124-135`, called at `memory.py:5428` and
        `sqlite.py:7426`), which **raises `InvalidEventError` on a raw `datetime`**; the repo convention is
        `.isoformat()` (`core.py:5884`);
      - the folded epoch sequence (D-R6a-5).
      **Home:** a `producer_quarantined_event(...)` builder in `app/store/core.py` beside
      `signal_duplicate_conflict_event` (`:5922`) — *not* a model in `app/models.py`; no signal payload is
      typed anywhere (`ExecutionEvent.payload` is `dict[str, Any]`, `models.py:1159`; no `TypedDict` in
      `app/`), so a typed model would be unenforced by the append path.
      **⚠ Two epoch shapes, both of which the fold and the pin must handle:** a rate breach opening a
      **fresh** cycle folds to `(pinned limit NULL, consumed 0)`; a rate breach opening **mid-cycle**,
      after k attributable rejections, folds to `(pinned limit NON-NULL, consumed k > 0)` — the limit is
      read from the cycle's *first attributable-rejection* event (`03-rails.md:79`), which exists in that
      case. rev-3 asserted only the first shape.
      **Pin:** the fold recovers `breach_trigger` and both shapes — both stores.
      — TRACED(`02-lifecycle.md:54`; `03-rails.md:66,79`; `store/base.py:124-135`; `core.py:5884,5922`;
      `SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md:110-113`; M4b-4 F-6; M4b-5 F-4/F-5/F-10).

---

## M2 — Lifecycle totality (R6a owns every edge below)

| Edge | Driver | Requirement |
|---|---|---|
| **cycle birth** | first attributable rejection after a release | pins the limit from that event; cache mirrors it. A **rate-breach-only** cycle has **no** pinnable limit (nullable column + `breach_trigger`) |
| **budget debit** | validation/skew quarantine · novel-hash conflict · DOA expiry | atomic with its append, and **only if the append actually wrote**, by event **identity** (D-R6a-4) |
| **rate debit** | every authenticated ingest, epoch closed | atomic in the step-2 primitive; **read-only on the reject path**; fractional carry preserved on accept (D-R6a-16.3/16.4) |
| **epoch birth (budget)** | the append consuming the last slot | terminal event **+** opener, same op, via `epoch_event` — **suppressed if the terminal no-oped** (D-R6a-4) |
| **epoch birth (rate)** | bucket empty at an authenticated ingest | opener alone, no terminal event, `breach_trigger: rate_breach` (D-R6a-16.5/17) |
| **epoch birth (exactly once)** | epoch-scoped `dedupe_key` + the single lock | D-R6a-5 |
| **post-exhaustion (steady state)** | any ingest once the epoch is open | rejected at **step 2**, write-free — **R6b's**; never reaches the store (D-R6a-8) |
| **post-exhaustion (race)** | slow-body/concurrent requests that cleared step 2 | **403, write-free**, record-free response, **including for an identical replay** (D-R6a-8) |
| **⚠ epoch open + budget slots REMAINING** | the ordinary rate breach (valid signals never debit, `03-rails.md:35-43`), or a request that cleared step 2 before a rate breach opened the epoch | **403, write-free, record-free** — **no** terminal event, **no** debit, **no** second opener. The gate is `epoch_open OR consumed >= limit`, never exhaustion alone (D-R6a-8 P0) |
| **quarantined ingest** | any ingest while the epoch is open | **403, write-free, no token burn** (D-R6a-16.2) |
| **epoch release** | `release_producer(..., actor, rejected_count, released_at)` | resets **both** rails; writes `PRODUCER_RELEASED` (D-R6a-7) |
| **re-quarantine** | next breach after release | **new** sequence ⇒ a new opener survives dedupe; a cycle-1 hash resubmitted debits **nothing** (D-R6a-5) |
| **restart** | `initialize()` | class-(A) columns rebuilt from the log — **including quarantine state and epoch sequence**; class-(B) bucket **preserved, never rebuilt** (D-R6a-3) |
| **crash mid-debit** | death between decide and append | **{debit + event} or neither** — requires extending `_atomic()`'s field enumeration in the memory store (D-R6a-2) |

---

## M3 — Consumer inventory

| Consumer | Class | Finding |
|---|---|---|
| `store.ingest_signal` (3 impls) | **affected — core** | Budget debit; a debit not conditioned on an actual write diverges cache from fold (D-R6a-4). |
| **`memory.py:_atomic()` (`:502-565`)** | **⚠ affected — P0** | Hand-maintained field enumeration; every new rail collection joins **both** halves or the rollback silently half-applies (D-R6a-2). |
| The new rate primitive | **NEW — R6a authors it** | Step-2 method, epoch check inside, read-only on reject, **zero R6a consumers** (D-R6a-16). |
| `SignalIngestPlan.event` (`core.py:5968`) | **affected** | **Additive** `epoch_event`; retyping breaks seven sites. |
| `SignalIngestPlan.result_record` (`core.py:5969`) | **affected — the one sanctioned retype** | Becomes Optional; why `memory.py:5609` is mypy-affected and `sqlite.py:7689` is not (D-R6a-8). |
| `SignalIngestResult.record` (`base.py:337-338`, `signal_commands.py:26-27`) | **affected** | Optional, or post-exhaustion is unrepresentable. |
| `_OUTCOME_STATUS` / `_record_response` — **two** call sites (`routes_signals.py:45-52,202,261-277,279-291`) | **affected** | A 7th outcome is a `KeyError` → 500; **static gates cannot see it**. |
| `plan_signal_ingest` gate + branch order (`core.py:6013`, `:6052`) | **⚠ affected — P0** | It receives **no** consumed/epoch/quarantine input today (measured), so R6a adds one; the gate is `epoch_open OR consumed >= limit` — **not exhaustion alone**, which Option A decoupled — and it must precede the `existing`/`payload_hash` dedupe branch per `01-schema.md:86-92` (D-R6a-8). |
| **`app/events/replay.py`** — `ReadModelProjection`, `project_read_models` (`:175-196`), `_describe_read_model_diff` (`:199-227`), `verify_dual_store_readmodel_parity` (`:250-274`) | **⚠ affected — P1** | R6a adds co-written read-model columns; without registration the `:176-178` docstring claim goes false and REV-0039's un-registered-fold class recurs (D-R6a-3.7). |
| `app/facade/signals.py:88,102,104` | **affected — mypy-proven required** | Without the edit the new outcome is an `AttributeError` → 500. |
| `app/store/memory.py:5609` | **affected — mypy-proven** | Optional-record narrowing. |
| Producer-rail projector | **MISSING — R6a authors it** | Purely additive (`projectors.py:850-852`; `PRODUCER_*` absent from `:803-808`). |
| `initialize()` rebuild | **affected** | Restores class (A); **preserves** class (B). Must not copy `memory.py:274` / `sqlite.py:648`'s bare `utcnow()`. |
| `dedupe_key` space | **affected** | Epoch-scope the two `PRODUCER_*` keys **only**; `signal_conflict`/`signal_create` stay global (D-R6a-5). Format is length-prefixed. |
| Transition-event builder | **MISSING — R6a authors it** | Snapshot-carrying transitions mis-fold as creations. |
| `PRODUCER_QUARANTINED` payload | **NEW — ratified in D-R6a-17** | Append-only; `breach_trigger` is what makes the two epoch kinds distinguishable. |
| Six stale doc claims + the `pkl/` change log | **affected** | D-R6a-11; scope IN. |
| **`tests/test_route_authorization_matrix.py:238-247`** | **⚠ affected — cross-rung coupling** | Asserts a valid producer key gets a status **not in (401, 403)**. Green today because each parametrised case builds a **fresh app and store** (`:239`), so the budget is never approached — not because of suite-wide headroom. The forward risk stands and now spans **two rungs**: R6a contributes the race-path 403, **R6b the steady-state step-2 403**. R6a's 403 must carry a machine-distinguishable reason, and the coupling must be recorded for R6b to inherit. |
| R6b (provider, holder, sweeps, route, cockpit, rate settings) | **downstream** | Consumes R6a's primitives, builder, epoch state, verdict DTO. **No store change, no schema.** |
| R7a's A-2 re-check | **downstream** | Reads the quarantine epoch R6a persists (`05-conversion.md:12`). |
| Existing suite + `harness/bootstrap.py` | **unaffected (measured)** | Only the two authorized edits. |

---

## M4a — Prospective hindsight

1. *"A producer was charged twice for one logged event."* → debit not conditioned on an actual write, or keyed on `sequence` (D-R6a-4). **The original P0.**
2. *"A quarantine opened at a count replay says is not exhaustion."* → opener not suppressed when the terminal append no-oped (D-R6a-4). **The P0 rev-2 left open.**
3. *"A quarantined producer kept appending rejection events, against ADR-009."* → the gate tested exhaustion, not epoch-open; Option A decoupled them (D-R6a-8). **The P0 rev-3 left open.**
4. *"The budget epoch's opener vanished into the rate epoch's dedupe key."* → same, plus a one-sided suppression check (D-R6a-4, D-R6a-5).
5. *"A producer running at HALF its configured rate was permanently quarantined."* → integer refill truncated to zero while the anchor still advanced (D-R6a-16.4).
6. *"The carry pin was green and the bucket never refilled."* → the pin paced above the token interval from a full bucket, where correct and defective are identical (D-R6a-16.4).
7. *"The operator ratified caps that were not in the document."* → three "ratified here" values with no numbers (D-R6a-16.0).
8. *"The rate cap drifted from config's copy."* → a private constant R6b had to re-declare, repeating the `SIGNAL_INVALID_BUDGET_HARD_CAP` / `_SIGNAL_CYCLE_BUDGET_MAX` split (D-R6a-16.0).
9. *"Append-only event vocabulary shipped without an operator ruling."* → D-R6a-17 self-ratified in an M1 checkbox (Stop 2).
10. *"`lint-imports` was green while the store imported the facade."* → `app.store` is a source module in no contract (D-R6a-16.0).
11. *"CI's coverage ratchet failed on the zero-consumer primitive."* → branch coverage omitted from the battery (D-R6a-16.6).
12. *"The opener carried a raw `datetime` and both stores raised."* → `normalize_json_payload` rejects it; use `.isoformat()` (D-R6a-17).
13. *"A restart handed the producer a free full burst."* → the bucket was rebuilt as if it were a cache (D-R6a-3B).
14. *"A rollback left the debit but truncated the log."* → a new rail collection missing from `_atomic()`'s enumeration (D-R6a-2).
15. *"A quarantined producer earned cheap 200s by replaying an accepted signal."* → dedupe checked before the boundary (D-R6a-8, `01-schema.md:86-92`).
16. *"A same-hash resubmission re-debited."* → missing third exclusion (D-R6a-4.3).
17. *"A restart un-quarantined a quarantined producer."* → fold omitted quarantine state (D-R6a-3A.5).
18. *"A restart re-granted a spent budget."* → no `initialize()` rebuild (D-R6a-3A.4).
19. *"A second epoch never opened."* → non-epoch-scoped `PRODUCER_*` key, or a stale cache supplying the sequence (D-R6a-5).
20. *"A post-release resubmission of an old hash re-debited."* → epoch-scoping the conflict key (D-R6a-5).
21. *"A released producer re-quarantined immediately."* → release reset one rail (D-R6a-7).
22. *"`PRODUCER_RELEASED` had no actor" / "the opener had no breach trigger."* → unfixable in an append-only log (D-R6a-7, D-R6a-17).
23. *"The fold could not tell a rate breach from a budget exhaustion."* → no `breach_trigger` (D-R6a-17).
24. *"Post-quarantine rejects wrote to the store."* → durable counter, or a bucket that writes on evaluation (D-R6a-7, D-R6a-16.3).
25. *"A quarantined producer got 429 and burned tokens."* → epoch checked after rate, or outside the primitive (D-R6a-16.1/16.2).
26. *"The producer was throttled below its configured rate and drifted."* → fractional remainder discarded on the accept path (D-R6a-16.4).
27. *"Exhaustion returned 500."* → unmapped 7th outcome; **no static gate would catch it** (D-R6a-8).
28. *"Dual-store replay parity passed while the new columns went unchecked."* → no `replay.py` registration (D-R6a-3A.7).
29. *"Sweep events silently vanished."* → reused `signal_create` prefix (D-R6a-9).
30. *"Sweep expiries ate the budget."* → missing `detected_by ≠ ingest` exclusion (D-R6a-4.2).
31. *"An altered rail column silently served a wrong budget."* → no startup guard (DDL item 4).
32. *"A config change retroactively moved a cycle's ceiling."* → non-nullable pinned limit backfilled from live `Settings` (DDL item 2).
33. *"We needed a second migration."* → bucket column types / carry rule not settled in the one DDL request (DDL item 1).
34. *"The authorization matrix went green while a producer route 403'd for a new reason."* → the M3 cross-rung coupling.
35. *"Memory passed, SQLite overspent."* → dual-store parity (D-R6a-15).
36. *"The corpus was green and proved nothing."* → mandatory mutation-checking (D-R6a-13).
37. *"The gate said OK on a missing file."* → `git ls-tree` exit-0 (D-R6a-1).
38. *"The WO was done but the rung left no knowledge trace."* → `work/**` and `pkl/**` omitted from scope (scope IN).

---

## ⚠ BUILD HAZARDS (verified)

1. **The repeated-novel-hash double debit** — the dedupe no-op is invisible because **both call sites
   discard the append's return value** (`memory.py:5603-5604`, `sqlite.py:7683-7684`). The original P0.
2. **`sequence` does not discriminate a write from a no-op** — the no-op returns the *stored* event
   (`memory.py:5433-5435`, `sqlite.py:7434-7436`), whose `sequence ≥ 1`. Use `id`.
3. **The opener can land without its debit** — the planner decides it pre-append (D-R6a-4).
4. **`memory.py:_atomic()` is a literal field list** (`:502-565`, `saved_signals` at `:533`, log truncated
   at `:563`) — SQLite's rollback is automatic, memory's is not.
5. **The token bucket is not foldable** — `03-rails.md:11-12` debits it on duplicate ingests, which append
   no event (`core.py:6052-6059`). A rebuild resets the rate rail.
6. **`plan_signal_ingest` checks `existing` first** (`core.py:6052`), the opposite of
   `01-schema.md:86-92`.
7. **`mypy` does NOT flag `SignalRecordView.model_validate(result.record)`** — `model_validate` takes
   `Any`, so the 500 is invisible to ruff, mypy and lint-imports alike. Only a runtime pin catches it.
8. **The rate primitive cannot live in `ingest_signal`** — step 2 vs step 4; `base.py:1320-1332`'s
   required parsed fields prove it. And it must not return R6b's `RailsDecision`.
9. **An INTEGER token column with `anchor = now` does not "drift" — below one token interval per
   arrival it NEVER refills** (measured: 0/60 granted vs 30/60). A compliant producer at half its rate is
   permanently quarantined (D-R6a-16.4).
10. **`test_route_authorization_matrix.py:238-247` collides with the new 403** — and green today only
    because `:239` builds a fresh app per case.
11. **`_migrate` runs flag-independently** (`sqlite.py:562-563`) — the gated DDL touches every existing
    operator database.
12. **The write-time epoch-sequence source must be specified** — a cache lagging the log makes epoch #2's
    opener a silent no-op by a *different* route than the key design.
13. **R4's exact-column + UNIQUE startup guard** (`sqlite.py:1041-1101`) must be carried to the rail table.
14. **`memory.py:274` AND `sqlite.py:648`** both call bare `utcnow()` in `initialize()` — do not copy
    either; inject the clock.
15. **A duplicate `dedupe_key` is a silent no-op in both stores** — parity cannot see a lost event. And
    the key format is **length-prefixed** (`core.py:5641-5642`).
16. **A 7th `SignalIngestOutcome` is a `KeyError` → 500** via a bare-subscripted `_OUTCOME_STATUS`.
17. **`SignalIngestPlan.event` must gain a sibling, not change type** — seven read sites — while its
    sibling `result_record` **does** get retyped. Do not generalise either way.
18. **`app/events/replay.py` registration is easy to omit and green when omitted** — REV-0039 records the
    precedent.
19. **⚠ `epoch open` ≠ `budget exhausted` after Option A** — the rate primitive is a second opener, so a
    gate written as `consumed >= limit` passes every rev-3 pin and still appends inside an open epoch,
    against `ADR-009:343-345`. The single most likely wrong build in this rung.
20. **`lint-imports` cannot see `app.store → app.facade`** — `app.store` is a source module in none of the
    six contracts.
21. **CI runs a branch-coverage ratchet** (`fail_under = 93`, `--cov-branch`) that rev-3's battery omitted
    — the one gate a zero-consumer primitive can trip.
22. **rev-3 "ratified" three caps and stated no numbers** — and the repo already carries the budget cap
    twice, in two modules, with no shared import.
23. **`normalize_json_payload` raises on a raw `datetime`** (`store/base.py:124-135`) — the opener's
    `epoch_start` must be `.isoformat()`.
24. **A memory-store "restart" preserves nothing** — the class-(B) pin needs a per-store definition or it
    is unsatisfiable as worded.

## Filter-safety clause (rung risk: **LOW-MED**)

Authorized defensive engineering on the operator's own local, paper-only application. No external
target, no network probing, no credential access, no live trading. R6a is store-internal, but keep the
vocabulary: **say** *paced-arrival accounting* · *budget-exhaustion accounting defect* · *non-atomic
transaction boundary*; **avoid** "flood attack", "DoS test", "exhaust the server". Report at the defect
level: cause · impact · affected local files · fix · pass/fail evidence. No reusable bypass procedures.
**REV-0044's Claude seat is the sanctioned adversarial net** — no open-ended adversarial discovery.

## Gate battery

`ruff check .` · `ruff format --check` on R6a-owned files · `mypy app/` · **`lint-imports`** ·
**`pytest --cov=app --cov-branch`** (CI's ratchet, floor `fail_under = 93`, `pyproject.toml:38` /
`.github/workflows/ci.yml:101` — rev-3 omitted it, and it is the **one** gate a zero-consumer primitive
plus a record-free branch can actually trip) · the R6a corpus + full suite · `python -m pytest -q
tests/r2_conformance_oracle.py` · `pytest -q tests/test_wo0113_repair_scaling.py` ·
`python harness/bootstrap.py` · all three hygiene scripts.
**Two gates cannot prove what rev-3 implied they could:** the static gates cannot prove D-R6a-8 (needs the
runtime pin), and **`lint-imports` cannot prove D-R6a-16.0's `RailsDecision` prohibition** — `app.store` is
a *source* module in none of the six contracts, so `app.store → app.facade` passes green. That one needs
the corpus grep assertion.

## Stop conditions

**Any DDL before approval** · **any existing-test edit beyond the two authorized in D-R6a-12** — and
specifically any edit to the seven `plan.event` read sites, which means `event` was retyped · any
provider / `check_ingest` / `is_conforming_rails` / **`app/facade/signal_rails.py`** / `deps.py` / sweep /
route / cockpit / counter-holder work · any `app/server.py` edit · any new **setting** (the rate *caps*
are ratified here; the two `Settings` fields are not) · anything making the flag independently
enable-able · any accepted-text conflict not recorded here · a P0-equivalent hole in accepted text.

## Close-out

Human-gated on **two** surfaces (Stop 1 DDL, Stop 2 event-log payload) ⇒ **REV-0044 packet**; the gate clears only on a dispositioned `ACCEPT`/
`ACCEPT-WITH-CHANGES`. Set WO-0104a to REVIEW and stage `work/review/REV-0044/request.md` stating: which
GAP-08 clauses R6a closes and which remain R6b's; the approved DDL including the nullable columns, the
bucket column types + carry form, the truth-model partition, and the startup guard; the live-vs-replay
agreement evidence **with the bucket columns and `rejected_count` explicitly excluded from that claim**;
the `01-schema.md:86-92` in-store ordering evidence; and the `test_route_authorization_matrix.py`
403-overloading coupling **as a two-rung item R6b inherits**. **R6a runs alone**, and **its REV-0044 must
disposition before R6b or R7a start.**

## §M4b record — pass 5 (10 findings, 1 P0), scoped to D-R6a-16/17, all planning-seat verified

*Scope: the two blocks rev-2/rev-3 created and nobody had refuted, plus their interactions with the rest
of the document. Both were judged **not ratifiable as written**; rev-4 fixes that.*

| # | Finding | Verified | Applied |
|---|---|---|---|
| **F-1 P0** | Option A gave the epoch a **second opener**, so `epoch open` and `budget exhausted` are no longer the same predicate. rev-3's gate and **both** its pins are satisfiable by `consumed >= limit`, which lets `ingest_signal` append inside an open epoch (against `ADR-009:343-345` "Post-quarantine ingress appends **nothing**") and then lose its own opener to the open epoch's dedupe key | **YES** — ADR + `03-rails.md:35-43,151-153` read; the ordinary rate breach (valid signals never debit) reaches it at consumed 0 | D-R6a-8 gate rewritten to `epoch_open OR consumed >= limit`; new M2 row; D-R6a-4 two-sided suppression; D-R6a-5 sequence-while-open; new pin + mutation check |
| F-2 P1 | rev-3's fractional-carry pin is **inert** — correct and defective implementations are identical at 1.5× interval from a full bucket | **YES** — independently found by a planning-seat probe *before* the agent reported, and confirmed by both | D-R6a-16.4 rewritten (total starvation, not drift); new sub-cap/sub-interval + bank-then-burst pins |
| F-3 P1 | Three caps "ratified here" carry **no values**, and the repo declares the budget cap **twice** (`config.py:47`, `core.py:5607`) with no shared import | **YES** — `grep` over the WO returns no cap literals | D-R6a-16.0: three literal values + rationale, declared **public** so R6b imports rather than re-declares |
| F-4 P1 | `breach_trigger` is new **event-log payload vocabulary** self-ratified in an M1 checkbox, against this repo's own recorded ruling | **YES** — `SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md:110-113` quoted verbatim | D-R6a-17 **un-checked** and promoted to **Stop 2**, folded into the DDL request |
| F-5 P2 | D-R6a-17's necessity argument is false — `consumed == pinned_limit` holds iff budget exhaustion, so the fold *can* discriminate; and a mid-cycle rate breach has a **non-NULL** limit and consumed k > 0 | **YES** | D-R6a-17 justification withdrawn and replaced; both epoch shapes recorded; DDL item 2 restated |
| F-6 P2 | `lint-imports` **cannot** enforce the `RailsDecision` prohibition — `app.store` is a source module in no contract | **YES** — `.importlinter:104,150,192` are all `forbidden_modules` | D-R6a-16.0 caveat + corpus grep assertion; gate battery note; `signal_rails.py` re-attributed to R5a |
| F-7 P2 | The battery omits CI's **branch-coverage ratchet** — the one gate a zero-consumer method can trip | **YES** — `pyproject.toml:38`, `ci.yml:101` | Gate battery + D-R6a-16.6 (which also records that no dead-code gate exists) |
| F-8 P2 | The class-(B) restart pin has **no memory-store form** — a memory restart preserves nothing | **YES** — `memory.py:264-280` | "Restart" defined per store in D-R6a-3, D-R6a-15 and D-R6a-16 |
| F-9 P3 | `03-rails.md:156` is a **blank line**; the 403/429 + no-store-write rule is at `:157-158` | **YES** — `awk` dump | Three citations retargeted |
| F-10 P3 | `app/models.py` is the wrong home by precedent for both artefacts, and `epoch start` must be pre-serialised | **YES** — `base.py:328-338`; `normalize_json_payload` at `base.py:124-135`; no `TypedDict` in `app/` | Verdict DTO → `store/base.py`; payload → a `core.py` builder; `.isoformat()`; `app/models.py` dropped from Scope IN |

**Claims pass 5 attacked and could NOT break:** consequence 0's signature is reachable and sufficient
(the step-2 seam already passes producer identity alone); D-R6a-4's identity discriminator works and
`sequence` genuinely does not (measured, both stores); D-R6a-17's field list is complete against every
enumerated consumer; no schema-version or migration handling is owed for the payload; D-R6a-3.7's
registration cannot contradict the class-(B) exclusion (`verify_dual_store_readmodel_parity` compares two
*log-derived* projections, never a live column); **D-R6a-10 survives Option A** (`grep "signal_rate"
app/config.py` → 0).

**Planning-seat probes run this revision** (the process change that produced F-2 independently):
`sequence` vs identity on a dedupe no-op; `plan_signal_ingest`'s parameter list (no consumed/epoch input
exists today); the fractional-carry simulation across four pacings; `ingest_signal`'s required parsed
fields. Scripts retained under the session scratchpad. **Every claim this document has measured has
survived five passes; nearly every P0 was a claim derived by reading two files.**

## §M4b record — pass 4 (14 findings, 4 P0), all planning-seat verified

*(Pass 3's 15-finding table is retained below. Passes 1 and 2 are in the superseded parent,
`WO-0104-signal-rails-REFRESH.md` §M4b.)*

| # | Finding | Verified | Applied |
|---|---|---|---|
| **F-1 P0** | `memory.py:_atomic()` is a hand-maintained field enumeration; rev-2 cited `:502-518` (signature + docstring) as "real rollback" and asserted "{debit + event} or neither, both stores" as pre-existing. False for the memory store until R6a extends both halves | **YES** — read `:502-565`; `saved_signals` at `:533` is the WO-0134 precedent | D-R6a-2 rewritten + forced-exception pin + mutation check |
| **F-2 P0** | Option A merged two rails with different truth models: the bucket debits on paths that append no event (`03-rails.md:11-12` + `core.py:6052-6059`), so `initialize()` rebuild ⇒ free full burst every restart, and the agreement claim is unsatisfiable over it | **YES** — spec + code; `02-lifecycle.md:117-118` scopes the claim to limit + consumed count | D-R6a-3 partitioned into class (A) log-derived / class (B) primary durable; **DDL item 6** |
| **F-3 P0** | The opener-suppression rule was unwritten and the pure planner cannot decide it — D-R6a-4 vs D-R6a-6 tension re-admits the P0 through the opener | **YES** — `core.py:6060-6063` planner path vs `memory.py:5603-5604` | D-R6a-4: store ratifies the opener post-append; three pins |
| **F-4 P0** | `01-schema.md:86-92` mandates boundary rejection before idempotent replay; `core.py:6052` does the opposite, so a race-loser replay earns a 200 | **YES** — read both | D-R6a-8: in-store ordering + identical-replay pin |
| F-5 P1 | rev-2's own remedy offered `sequence`, which is populated on both paths; and `wrote: bool` would retype two helpers with 29 call sites each | **YES** — `memory.py:5419,5433-5435`; `models.py:1127`; `sqlite.py:401`; counted call sites | D-R6a-4: `stored.id == plan.event.id`; both alternatives explicitly rejected |
| F-6 P1 | `PRODUCER_QUARANTINED`'s payload was unspecified though `02-lifecycle.md:54` requires a breach trigger — the only thing letting the fold distinguish the two epoch kinds. Append-only | **YES** | **new D-R6a-17** |
| F-7 P1 | The rate primitive had no name/signature/clock/caps and no R6a consumer; 16.2's ordering is pinnable only if the epoch check is inside it | **YES** — `deps.py:126-138` is R6b's; no rate cap in accepted text | D-R6a-16.0/16.1/16.6 |
| F-8 P1 | Read-only-on-reject is sound, but an INTEGER token column with `anchor = now` silently under-grants and drifts — and the types are inside the one gated DDL | **YES** — arithmetic; DDL item 1 named no types | D-R6a-16.4 + DDL item 1 |
| F-9 P1 | `app/events/replay.py` / `ReadModelProjection` / `verify_dual_store_readmodel_parity` unenumerated; REV-0039 already recorded this class | **YES** — `replay.py:175-196,199-227,250-274`; REV-0039 disposition:21 | D-R6a-3A.7 + M3 row + D-R6a-13 |
| F-10 P1 | D-R6a-5's unqualified title would epoch-scope the conflict key, breaking `01-schema.md:102-104` coalescing | **YES** | D-R6a-5 retitled and scoped to `PRODUCER_*` only; post-release pin |
| F-11 P2 | Scope IN omitted `work/**` and `pkl/architecture/signal-seat.md` though close-out requires both and CI enforces it | **YES** — `pkl/.../signal-seat.md:88-110` has a per-rung entry from all four predecessors | Scope IN extended |
| F-12 P2 | `SignalIngestPlan.result_record` must be retyped — the cause of the cited `memory.py:5609` error — next to a D-line forbidding a retype of its sibling | **YES** | D-R6a-8 blocker 2 + M3 row |
| F-13 P3 | Anchor errors, **including `models.py:482-483` which pass 3's table recorded as already corrected** | **YES** — all six re-read | `models.py:483-484`, `memory.py:5580-5581`, `sqlite.py:562-563`, `sqlite.py:648`, length-prefixed key format, `signal_seat_helpers.py:32-36`/`:54-82` |
| F-14 P3 | M3 overstated *why* the matrix test is green (fresh app per case, not suite headroom) | **YES** — `:239` | M3 row reworded; forward risk retained and made two-rung |

**Planning-seat additions (not from the agent), from tracing the D-R6a-10/16 settings question:** the
rate primitive is a **step-2** method and cannot live in `ingest_signal` (`base.py:1320-1332`); its
settings therefore arrive as parameters from R6b's provider, so **D-R6a-10 holds unamended**; the
steady-state post-exhaustion 403 is **R6b's step-2 reject**, not R6a's, which corrects D-R6a-8's stated
cause and makes the matrix-test coupling a two-rung item; and the verdict DTO must **not** be
`RailsDecision`, whose module is R6b's.

**Process note for REV-0044:** pass 3's table claimed an anchor correction that was not applied (F-13).
Every anchor in rev-3's own record was re-read against the tree at `67c2ca3` before being recorded.

### §M4b record — pass 3 (15 findings, 2 P0), retained

| # | Finding | Verified | Applied |
|---|---|---|---|
| **P0-1** | Debit ≠ event on a repeated novel-hash conflict; `03-rails.md:39-40` already forbids re-debiting. Measured `A,B,B` ⇒ 2 outcomes, 1 event, both stores | **YES** | D-R6a-4: third exclusion + debit conditioned on an actual write |
| **P0-2** | The split left the rate rail with no authorized writer while its columns shipped in R6a's DDL | **YES** | D-R6a-16: **Option A** — R6a owns the rate primitive |
| P1-3 | `app/facade/signals.py` required (mypy `:102`,`:104`) and out of scope | YES | Scope IN += `facade/signals.py`, `store/memory.py` |
| P1-4 | The gate battery cannot catch the 500 the route touch prevents | YES | D-R6a-8 + D-R6a-13 runtime pin |
| P1-5 | Two `_record_response` call sites; "blocker 3" (`except FacadeError`) is not a blocker | YES | D-R6a-8 corrected |
| P1-6 | Retyping `event` breaks seven sites | YES | D-R6a-6 additive `epoch_event`; D-R6a-12 tripwire |
| P1-7 | `PRODUCER_RELEASED` requires `actor`; no injected clock | YES | D-R6a-7 full signature |
| P1-8 | `rejected_count` unvalidated, uncapped, unauditable | YES | D-R6a-7 validation + cap + agreement-claim exclusion |
| P1-9 | The fold omitted quarantine state and the epoch sequence | YES | D-R6a-3A.5/3A.6 |
| P1-10 | DDL traps: non-nullable limit, unwritable bucket columns, no startup guard | YES | DDL items 2/4 |
| P2-11 | D-R6a-8's "goes live on merge" rationale false; "concurrency" wrong | YES | D-R6a-8 rationale replaced |
| P2-12 | Flag-off byte-equivalence false at the database | YES | D-R6a-14 scoped to HTTP |
| P2-13 | Five further stale doc claims | YES | D-R6a-11 (six total) |
| P2-14 | Eight TRACED citations pointed at a nonexistent record | YES | these tables |
| P3-15 | Anchor errors: `models.py:482-483`; `core.py:5913`/`:5941`; delta 30 not 32; the `IntegrityError` claim | **PARTIAL** — `models.py` was recorded corrected but was not; fixed in rev-3 (F-13) | corrected throughout |

**Survived measurement across both passes:** rev-1's central claim — *R6a breaks no existing test* —
held, with the full suite green on exactly one authorized edit and 25× budget headroom. Pass 4
independently confirmed the 7th-outcome and new-table dimensions statically
(`test_signal_ingest_properties.py:254-263`, `test_phase7_schema.py:117-123`).
