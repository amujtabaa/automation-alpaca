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
- **Exact transition on the final slot (no ambiguity — REV-0024-F P2):** the attributable-rejection
  append that debits the **last** slot completes **normally** — its own event is appended and its own
  status returned (422 for validation, 409 for novel conflict, the `SIGNAL_EXPIRED`-at-ingest 201/terminal
  for dead-on-arrival). The budget is then at zero; the **next** ingest (step 2, before body read)
  observes exhaustion and opens the epoch with `PRODUCER_QUARANTINED` (429/403, write-free). The
  budget reaching zero never retroactively suppresses the append that consumed it. Event count is
  therefore exact: ≤ `invalid_budget` attributable events, then one `PRODUCER_QUARANTINED` on the
  following ingest.
- The budget **resets only on human release** (`PRODUCER_RELEASED`, §5), never by refill — so each
  further cycle of attributable-rejection flooding requires a human to re-open the producer.
- **Config changes are cycle-scoped, not retroactive** (REV-0024-F P1): a change to
  `signal_invalid_budget_per_epoch` (restart/redeploy) applies **only to accumulation cycles that
  begin after the change** — a cycle begins at a producer's first attributable rejection after a
  release (or from fresh). The limit in force when a cycle begins is **pinned and persisted with the
  producer's rail state** (replay- and restart-stable), so a mid-cycle config bump cannot silently
  grant a producer extra writes, and a mid-cycle reduction cannot retroactively quarantine on replay.
  This preserves the non-refilling / resets-only-on-release contract across deploys.

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

In its place, `signal_seat_enabled` carries a **rails-presence startup guard**, exactly parallel to
the credential-presence guard (`04-auth-and-api.md §1`): **with the flag on, `create_app` startup
fails fast unless the full per-producer rails are wired** — the §1 refilling rate bucket, the §1a
non-refilling invalid/conflict budget, the §4 producer-quarantine epoch machinery, and the §5 human
release path. An enabled endpoint therefore structurally cannot run without finite-audit flood
protection.

**Sequencing consequence — live enablement is the joint WO-0102 + WO-0103 + WO-0104 milestone.**
WO-0102 ships the ingestion endpoint and the A-1 boundary (**not** the atomic conversion — that A-2
approval→conversion is WO-0103's human-gated surface, REV-0024-F P1), but the flag is **structurally
un-enable-able** in that WO alone: turning it on fails the rails-presence guard until WO-0104's rails
exist, and an enabled seat without WO-0103's conversion path re-opens F-002. WO-0104 lands
§1/§1a/§3/§4/§5 and lifts the guard in the same change that first makes enablement possible. The
flag-on integration suite (the `04-auth-and-api.md §1a` mounted-route matrix, and the
constant-event-row flood tests of §1a/§4) is authored across the WOs and runs green
at that joint milestone — never against a half-railed app.

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
non-refilling invalid/conflict budget (§1a) is debited at step 4 when an attributable terminal-at-ingest
event is actually appended — validation quarantine, novel-hash conflict, **and dead-on-arrival
`SIGNAL_EXPIRED`** (`expires_at ≤ received_at` / skew-based; REV-0024-F P1 — omitting expiry here
reopens the paced-flood hole) — and its exhaustion opens the epoch on the next ingest at step 2. Steps 1–2 reject with zero store writes and zero body
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
