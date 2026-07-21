---
type: Work Order
title: "Real-tape recorder: capture extended-hours market data + derived events for replay validation"
status: ACTIVE
work_order_id: WO-0123
wave: post-R2 beta-prep (Entry-Envelope enabler; runs early to accumulate corpus)
model_tier: mid
risk: medium
disposition: []
owner: Ameen / implementer TBD / from W4-SEED-NOTES replay-harness seed
created: 2026-07-20
gated_surface: none for order flow (read-only market data only); reads broker market data (paper)
---

# Work Order: start accumulating the replay corpus now

> **Why early:** the Entry Envelope (buy-side autonomy) cannot be trusted until its triggers and
> thresholds are validated against REAL recorded tapes through a pessimistic fill model
> (`W4-SEED-NOTES.md`; paper fills are optimistic in thin books). Tapes accumulate in calendar
> time — every week the recorder runs is corpus that cannot be created retroactively. Building
> and running this now removes the Entry Envelope's data dependency from its critical path.

## Goal

[FABLE • FULL • verification: DIRECT • task: WO-0123 tape recorder]

```yaml
fable_gate:
  goal: "Capture a deterministic, durable, replayable record of market-data snapshots without any execution-state or order-flow interaction."
  assumptions:
    - "MarketDataService is the existing abstract read-only market-data port; its concrete Alpaca stream remains the only SDK ingress."
    - "The operator supplies paper credentials and recorder symbols only when intentionally operating the recorder; no test or implementation step needs credentials."
    - "A separate NDJSON tape store under the configured ignored data path satisfies durability without extending execution-event truth."
  approach: "Write red tests for inert/off, order-flow-spy isolation, deterministic replay, invalid-data preservation, and rotation; add a recorder package and flag/path configuration; document the operational contract and tape schema."
  out_of_scope:
    - "Order submission, cancellation, replacement, execution state, positions, fills, envelopes, app/store, facade, API routes, cockpit, and live trading."
    - "Replay-policy scoring or a fill model."
  done_when:
    - "Recorder captures only MarketDataService snapshots with injected time and explicit validity flags."
    - "Tape data round-trips byte-identically, rotates within its configured retention bound, and is documented."
    - "Flag-off is inert and the required spy proves zero order-flow calls."
  blast_radius: "new isolated development/operations recorder package and configuration only"
```

A deterministic recorder that captures real market-data snapshots and the events the engine
derives from them, into a durable tape store replayable later — with ZERO order flow.

## Context packet

- `CLAUDE.md` (safety core: only fills change position; the UI never calls Alpaca; adapter is
  the only broker seam) + `work/queue/W4-SEED-NOTES.md` (replay-harness seed: pessimistic fill
  model, five-metric scoring, corpus taxonomy)
- `pkl/architecture/sellside-research-notes.md` (regime labels, metric spec)
- `app/broker/adapter.py` + `app/broker/alpaca_paper.py` (the market-data read seam)
- `app/events/` (the event-sourced log the recorder mirrors) + `app/config.py` (feature flags)

## Allowed paths

```yaml
allowed_paths:
  - app/recorder/**          # new package: subscribe → snapshot → append tape
  - app/config.py            # ENABLE_TAPE_RECORDER flag + tape path/config
  - app/events/**            # tape event schema iff it reuses the log machinery
  - tests/**
  - docs/spec/replay/**      # tape format + scoring spec (new)
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**             # the recorder does not touch execution/position truth
  - app/facade/**
  - app/api/routes_trading.py
  - cockpit/**
```

## Required behavior

- [ ] **Read-only broker boundary:** the recorder consumes market data through the existing
      adapter seam ONLY. It never submits, cancels, or replaces an order; it never mutates
      position/order/fill/envelope state. A test proves zero order-flow adapter calls from the
      recorder path.
- [ ] **Deterministic capture:** every snapshot stamped with an injected clock (no bare
      `now()`); the tape is append-only and replayable to reproduce the exact observed sequence.
      Invalid market data (stale/NaN/negative/out-of-range) is recorded WITH its validity flags,
      never silently dropped — replay must see what the engine would have seen.
- [ ] **Tape store:** durable, outside execution truth (a separate file/table under a configured
      path; gitignored like `data/`). Bounded/rotated so a long recording run stays manageable
      (the event log grows linearly — document the growth rate).
- [ ] **Corpus taxonomy hooks:** capture enough to later label tapes by regime (real spikes,
      grinders, trend-pullback, fakeout pumps, halt-resume gaps) per the seed notes — at minimum
      symbol, session phase, and raw print stream; scoring itself is the replay-harness WO, not
      this one.
- [ ] **Flag-gated + off by default:** `ENABLE_TAPE_RECORDER` (default false); enabling it starts
      capture without touching any trading path. Running the recorder is an operational step
      (home PC now, VPS later), documented in the replay spec.

## Required tests

- [ ] Zero-order-flow proof (adapter spy): recorder path makes no submit/cancel/replace call.
- [ ] Deterministic replay: a recorded tape replays to a byte-identical snapshot sequence under
      the injected clock.
- [ ] Invalid-data capture: stale/NaN/negative prints are recorded with validity flags intact.
- [ ] Flag-off is fully inert (no capture, no broker call).

## Acceptance criteria

- [ ] Recorder captures real paper market data with zero order flow (proven), off by default.
- [ ] Tape format documented in `docs/spec/replay/`; growth rate stated.
- [ ] `ruff`/`mypy app/`/`lint-imports`/`pytest -q` green; Fable DONE with evidence.
- [ ] Close-out + ledger with the work.

## Stop conditions

Stop if capturing real data would require any order-flow or state-mutation path (it must not),
or if market-data access needs a live/non-paper mode (paper-only). Rollback: revert; the tape
store is disposable, outside execution truth.

## Model-tier rationale

`mid` — self-contained capture with a strict read-only boundary; the perilous part (the fill
model + policy validation) is the separate replay-harness WO, not this.

## Notes

Independent of every other stream (touches no `app/store/*`, no gated order surface) — safe to
run in parallel with Lane P, the remediation batch, and the Signal Seat revival. Its output
(the corpus) is what the Entry Envelope's eventual arming gate consumes.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.
