# 03 — Rails: rate limits, non-refilling invalid budget, enablement gate, producer quarantine, backpressure

Principle (ADR-009): **rails ship no later than exposure**, and a quarantined or over-limit
producer must not be able to grow the append-only log (SQLite) without bound.

## 1. Per-producer rate limit (WO-0104, the policy rail)

Token bucket per `producer_id`, evaluated at ingest, injected clock:

- `signal_rate_limit_per_hour: int = 60` (**authenticated ingests**/hour — every authenticated
  request debits the bucket whether it validates, quarantines, or duplicates; `Settings`-tunable.
  Codex rev-2: an accepted-only bucket lets unbounded invalid-but-attributable bodies write
  `SIGNAL_QUARANTINED` events without ever breaching)
- `signal_rate_burst: int = 10`

Breach (bucket empty at **any authenticated ingest**, decided at rails-check time **before the body
is read or parsed** — the §4 normative order; no "otherwise-valid" qualifier, which would require
parsing before the rate decision and defeat A-4's pre-body defense, REV-0024-F-004) →
**producer-level quarantine**: `PRODUCER_QUARANTINED` appended once; all further signals from that
producer are handled per §4 until an explicit human release. The breaching request itself gets HTTP
429 and is folded into the coalesced audit (it does NOT get a per-request `SIGNAL_QUARANTINED`).

## 1a. Non-refilling invalid/conflict budget (WO-0104, the storage rail — ADR-009 A-4)

The refilling bucket of §1 bounds *throughput*, not *storage*: a producer paced at or below the
refill rate keeps the bucket non-empty forever and appends one `SIGNAL_QUARANTINED` (validation) or
one novel-hash `SIGNAL_DUPLICATE_CONFLICT` per request indefinitely without ever breaching
(REV-0024-F-002 probe: 10080 events / 7 days at 1/min, bucket never below 9). So each producer also
holds a **non-refilling** budget:

- `signal_invalid_budget_per_epoch: int = 50` — `Settings`-tunable within **`[1, 1000]`**; **1000 is
  a hard architectural cap** no config may exceed, and **startup fails fast** on any value outside the
  range (mirrors `server_max_ttl`; REV-0024-F P2 — the "finite and small" property must not be
  configurable away). Debited by **every attributable terminal-at-ingest append** — one that
  authenticates, embeds the proposal, and grows the log: a validation `SIGNAL_QUARANTINED`, each
  novel-hash `SIGNAL_DUPLICATE_CONFLICT` (a same-hash replay is already coalesced to one event per
  `01-schema.md §3` and does not re-debit), **and each dead-on-arrival `SIGNAL_EXPIRED`**
  (`expires_at ≤ received_at`, or a skew-based `issued_at_future`/`issued_at_stale` terminal
  quarantine, `02-lifecycle.md §3`) — so a producer cannot dodge the budget by pacing unique
  just-expired proposals (REV-0024-F P1). It does **not** refill while the producer is un-quarantined.
- **The debit is linearizable and atomic with the terminal append (REV-0025-F-003).** Deciding
  "is a slot available", **reserving/consuming** it, and appending the terminal event are **one
  store operation** — a single memory lock hold / one SQLite transaction (the same single-writer
  discipline as `app/store/base.py`). A request that cleared the pre-body step-2 rails check does
  **not** get a free slot: at step 4, inside that atomic op, it **re-checks-and-debits** (or consumes
  a reservation taken at step 2), so with one slot left and N concurrent (or slow-streamed-body)
  requests, **exactly one** appends its terminal event and consumes the slot; the rest find zero and
  are handled as post-exhaustion (below). If the budget is event-derived, the atomic append **is**
  the debit; if it is a separate rail record, its update shares the same lock/transaction. Crash
  between decision and append leaves **either** the complete {debit + event} **or** neither, in both
  stores.
- **Exact transition on the final slot — the exhausting append opens the epoch in the SAME atomic op**
  (Ameen decision 2026-07-14, REV-0025-F P1; this **supersedes** the earlier REV-0024 "epoch opens on
  the next ingest" rule). The attributable-rejection append that consumes the **last** slot, in one
  memory-lock/SQLite-transaction, appends **both** its own terminal event (422 validation / 409 novel
  conflict / terminal `SIGNAL_EXPIRED`) **and** the single `PRODUCER_QUARANTINED` epoch-opener — so
  there is **no zero-budget-but-un-quarantined gap** in which the A-2 conversion check would still
  approve an exhausted producer's already-RECEIVED signals, and the epoch is immediately releasable if
  the producer goes silent. It remains **exactly one `PRODUCER_QUARANTINED` per epoch**; subsequent
  rejects are write-free. Event count is exact: ≤ `invalid_budget` attributable events, the last of
  which co-appends one `PRODUCER_QUARANTINED`, then write-free rejects until release. (A pure
  rate-bucket breach with no terminal append still opens the epoch on its own single
  `PRODUCER_QUARANTINED`.)
- The budget **resets only on human release** (`PRODUCER_RELEASED`, §5), never by refill — so each
  further cycle of attributable-rejection flooding requires a human to re-open the producer.
- **Both the pinned limit AND the consumed/remaining count are durable producer-rail state
  (REV-0025-F-004).** It is not enough to persist the cycle's limit: the **consumed count** (or
  equivalently remaining slots) must survive restart/redeploy too, restored **before the app serves**,
  and updated atomically with each terminal append (same op as the debit above). Otherwise an
  implementation could pin `limit=50`, consume 49, restart with `used=0`, and grant a fresh budget
  with no `PRODUCER_RELEASED` — violating reset-only-on-human-release. **Replay is event-authoritative
  (REV-0025-F P1):** the event log alone must reconstruct the binding budget, so **each
  attributable-rejection event (`SIGNAL_QUARANTINED` / novel `SIGNAL_DUPLICATE_CONFLICT` / DOA
  `SIGNAL_EXPIRED`) carries `cycle_budget_limit`** — the pinned limit in force for the current cycle.
  The consumed count folds as the number of such events since the last `PRODUCER_RELEASED` (cycle
  boundary); the limit is read from the cycle's first such event. A side table/snapshot may cache this
  for the live path, but it is **not** the source of truth — after a config change, replay knows
  whether a cycle started at 50 or 100 purely from `cycle_budget_limit` in the log, so live and replay
  never diverge, both stores.
- **Config changes are cycle-scoped, not retroactive** (REV-0024-F P1): a change to
  `signal_invalid_budget_per_epoch` applies **only to cycles that begin after the change** — a cycle
  begins at a producer's first attributable rejection after a release (or from fresh). The limit in
  force when a cycle begins is pinned in that durable rail state, so a mid-cycle config bump cannot
  grant extra writes and a mid-cycle reduction cannot retroactively quarantine on replay.

Consequence: append-only attributable-rejection volume per producer per epoch is **≤
`invalid_budget` events + 2 rail events** (plus the pre-quarantine accepted signals, themselves
rate-limited) — constant, and finite over indefinite hostility. Test contract (WO-0104): pace
invalid, novel-conflict, **and dead-on-arrival-expiry** requests at or below the refill rate over
arbitrarily many windows; assert a constant event-row ceiling and that quarantine opens on budget
exhaustion — both stores.

## 2. Enablement gated on full rails — the interim ceiling is withdrawn (ADR-009 A-4; REV-0024-F-004)

The earlier design shipped an *audit-free interim ingest ceiling* in WO-0102 ahead of the full
rails, on the theory that a counting-only ceiling kept an enabled endpoint from ever being unrailed.
REV-0024 showed that ceiling was **rate-bounded, not storage-bounded** (a producer paced under the
ceiling still appended validation/conflict events forever, §1a). It is **withdrawn**, not tuned —
there is no `signal_ingest_ceiling_*` setting and no interim window to reason about.

In its place, `signal_seat_enabled` carries a **permanent rails-presence startup guard**, exactly
parallel to the credential-presence guard (`04-auth-and-api.md §1`): **with the flag on, `create_app`
startup fails fast unless the full per-producer rails are wired** — the §1 refilling rate bucket, the
§1a non-refilling invalid/conflict budget, the §4 producer-quarantine epoch machinery, and the §5
human release path. The guard is a **standing invariant that WO-0104 SATISFIES by wiring the real
provider — never a scaffold it deletes** (REV-0025-F-005). Because a Protocol-presence check cannot
distinguish a real provider from a permissive fake, **the production entrypoint is proven to
construct the real WO-0104 provider, and any fake is confined to a test-only construction path
production config/environment cannot select**. An enabled endpoint therefore structurally cannot run
without finite-audit flood protection.

**Sequencing consequence — live enablement is the joint WO-0102 + WO-0103 + WO-0104 milestone.**
WO-0102 ships the ingestion endpoint and the A-1 boundary (**not** the atomic conversion — that A-2
approval→conversion is WO-0103's human-gated surface). The flag is **un-enable-able** until WO-0104's
rails **satisfy** the permanent guard, and an enabled seat without WO-0103's conversion path re-opens
F-002. **The WO-0103 half is a release/deployment gate + test, not a new runtime startup check**
(Ameen D-2): binding sequencing dependency + a **joint mounted-app suite proving
ingest → operator approval → exactly one atomically-linked intent** against the real rails. The
matrix **asserts the required sensitive routes exist** (not merely classifies mounted ones,
REV-0025-F-005/F-007). Authored across the WOs, run green at the joint milestone — never against a
half-railed or conversion-less app.

## 3. Sweeps (WO-0104)

One periodic engine-side sweep (injected clock; monitoring-loop cadence):

- RECEIVED signals past `expires_at` → durable EXPIRED (`SIGNAL_EXPIRED`, `detected_by:"sweep"`).
- On `PRODUCER_QUARANTINED`: any RECEIVED signals from that producer are swept to
  `SIGNAL_QUARANTINED` (`"producer_sweep"`) — a quarantined producer has no pending proposals
  lingering on the operator's panel.

## 4. Post-quarantine backpressure (the flood bound — ADR-009 A-4)

**Ingest processing order is normative:** (1) authenticate — constant-time key lookup, before any
body read; (2) rails check — quarantine epoch, rate limit (§1); (3) bounded body
read — `Content-Length` capped at 64 KiB, streamed reject beyond; (4) parse + field-validate. The
non-refilling invalid/conflict budget (§1a) is debited at step 4 **atomically with** the terminal
event append (the §1a linearizable re-check-and-debit — a step-2 pass does not pre-grant a slot) when
an attributable terminal-at-ingest event is appended — validation quarantine, novel-hash conflict,
**and dead-on-arrival `SIGNAL_EXPIRED`** (`expires_at ≤ received_at` / skew-based; REV-0024-F P1 —
omitting expiry here reopens the paced-flood hole) — and its exhaustion opens the epoch on the next
ingest at step 2. Steps 1–2 reject with zero store writes and zero body
processing, with exactly one carve-out: the single request that first crosses **either** breach
threshold — rate-bucket empty (§1) **or** invalid/conflict budget exhausted (§1a) — appends the
epoch-opening `PRODUCER_QUARANTINED` (once per epoch); all subsequent rejects in the epoch are
write-free.

For any ingest from a quarantined producer, or beyond a rate/budget limit:

1. Reject at the boundary: HTTP 429 (over-limit) / 403 (quarantined producer), constant work, no
   store write, no body read beyond step 3's cap.
2. Audit is bounded **per quarantine epoch** (epoch = quarantine → release), NOT per time window
   (a periodic append rate is unbounded over indefinite hostility — REV-0022 F-004; a refilling-
   bucket-only bound is likewise unbounded under paced hostility — REV-0024-F-002, which the §1a
   non-refilling budget closes): at most ONE `PRODUCER_QUARANTINED` event opens the epoch;
   post-quarantine ingress appends NOTHING; a **saturating in-memory counter outside the event log**
   tracks rejected requests (diagnostic, best-effort across restarts by design); `PRODUCER_RELEASED`
   closes the epoch carrying the saturated count + window. Constant ≤ 2 rail events per producer per
   epoch (plus the ≤ `invalid_budget` attributable-rejection events accrued before the epoch opened,
   §1a). (The earlier `PRODUCER_INGEST_REJECTED` per-window event is REMOVED from the vocabulary.)
3. Test contract (WO-0104, run at the joint enablement milestone): model-based/long-duration flood
   tests — paced at or below the refill rate over arbitrarily many windows — assert **constant
   event-row count** and bounded storage, not merely "fewer than request count".

## 5. Release (WO-0104 — human-gated action)

`POST /api/producers/{producer_id}/release` — **operator-only** credential (a producer key can
never release its own quarantine; negative test). Appends `PRODUCER_RELEASED` (actor recorded),
resets **BOTH** the §1 refilling bucket **and the §1a non-refilling invalid/conflict budget**, and
re-opens ingestion. **Resetting the §1a budget is mandatory (REV-0024-F P1):** a producer quarantined
by budget exhaustion that is released without a budget reset re-enters quarantine on its very next
ingest, making the browser release control inert — test asserts a released producer can ingest again
without immediate re-quarantine, both stores. Signals swept to quarantine by §3 stay terminal —
the producer resubmits fresh proposals (new `signal_id`s or identical replays of untouched ids).
**Browser path required** (invariant 11): the cockpit gains a release control on the signal panel
(WO-0104 scope; thin-client rules — typed API client only, no state owned client-side).
