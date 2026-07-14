# 03 — Rails: rate limits, interim ceiling, producer quarantine, backpressure

Principle (ADR-009): **rails ship no later than exposure**, and a quarantined or over-limit
producer must not be able to grow the append-only log (SQLite) without bound.

## 1. Per-producer rate limit (WO-0104, the policy rail)

Token bucket per `producer_id`, evaluated at ingest, injected clock:

- `signal_rate_limit_per_hour: int = 60` (**authenticated ingests**/hour — every authenticated
  request debits the bucket whether it validates, quarantines, or duplicates; `Settings`-tunable.
  Codex rev-2: an accepted-only bucket lets unbounded invalid-but-attributable bodies write
  `SIGNAL_QUARANTINED` events without ever breaching)
- `signal_rate_burst: int = 10`

Breach (bucket empty at an otherwise-valid ingest) → **producer-level quarantine**:
`PRODUCER_QUARANTINED` appended once; all further signals from that producer are handled per §4
until an explicit human release. The breaching request itself gets HTTP 429 and is folded into the
coalesced audit (it does NOT get a per-request `SIGNAL_QUARANTINED`).

## 2. Interim ingest ceiling (WO-0102 — ships WITH the endpoint, superseded by §1, never merely removed)

Hard caps, deliberately cruder than §1, so there is no unrailed window between WO-0102 and WO-0104:

- `signal_ingest_ceiling_per_producer_per_minute: int = 10`
- `signal_ingest_ceiling_global_per_minute: int = 60`

Over-ceiling → HTTP 429, **no event append at all** — the interim ceiling is **audit-free in the
event log**: rejected requests only bump a saturating in-memory counter (there is no
`PRODUCER_INGEST_REJECTED` event — it was removed from the vocabulary). Test contract (WO-0102):
sustained over-ceiling ingest appends **zero** events (constant event-row count — a per-window
append rate is unbounded over indefinite hostility, Codex rev-3). WO-0104 replaces the ceiling with
§1's full rails (rate-limit → quarantine epoch) **in the same change** it lands them.

## 3. Sweeps (WO-0104)

One periodic engine-side sweep (injected clock; monitoring-loop cadence):

- RECEIVED signals past `expires_at` → durable EXPIRED (`SIGNAL_EXPIRED`, `detected_by:"sweep"`).
- On `PRODUCER_QUARANTINED`: any RECEIVED signals from that producer are swept to
  `SIGNAL_QUARANTINED` (`"producer_sweep"`) — a quarantined producer has no pending proposals
  lingering on the operator's panel.

## 4. Post-quarantine / over-ceiling backpressure (the flood bound — ADR-009 A-4)

**Ingest processing order is normative:** (1) authenticate — constant-time key lookup, before any
body read; (2) rails check — quarantine epoch, rate limit / interim ceiling; (3) bounded body
read — `Content-Length` capped at 64 KiB, streamed reject beyond; (4) parse + field-validate.
Steps 1–2 reject with zero store writes and zero body processing, with exactly one carve-out:
the single breach-crossing request appends the epoch-opening `PRODUCER_QUARANTINED` (once per
epoch); all subsequent rejects in the epoch are write-free.

For any ingest from a quarantined producer, or beyond a ceiling/limit:

1. Reject at the boundary: HTTP 429 (over-limit) / 403 (quarantined producer), constant work, no
   store write, no body read beyond step 3's cap.
2. Audit is bounded **per quarantine epoch** (epoch = quarantine → release), NOT per time window
   (a periodic append rate is unbounded over indefinite hostility — REV-0022 F-004): at most ONE
   `PRODUCER_QUARANTINED` event opens the epoch; post-quarantine ingress appends NOTHING; a
   **saturating in-memory counter outside the event log** tracks rejected requests
   (diagnostic, best-effort across restarts by design); `PRODUCER_RELEASED` closes the epoch
   carrying the saturated count + window. Constant ≤ 2 rail events per producer per epoch.
   (The earlier `PRODUCER_INGEST_REJECTED` per-window event is REMOVED from the vocabulary.)
3. Test contract (WO-0102 for the ceiling, WO-0104 for quarantine): model-based/long-duration
   flood tests assert **constant event-row count** and bounded storage — not merely "fewer than
   request count".

## 5. Release (WO-0104 — human-gated action)

`POST /api/producers/{producer_id}/release` — **operator-only** credential (a producer key can
never release its own quarantine; negative test). Appends `PRODUCER_RELEASED` (actor recorded),
resets the §1 bucket, and re-opens ingestion. Signals swept to quarantine by §3 stay terminal —
the producer resubmits fresh proposals (new `signal_id`s or identical replays of untouched ids).
**Browser path required** (invariant 11): the cockpit gains a release control on the signal panel
(WO-0104 scope; thin-client rules — typed API client only, no state owned client-side).
