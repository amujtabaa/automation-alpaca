---
type: Review Disposition
rev_id: REV-0005
campaign_id: CAMPAIGN-0001
verdict_received: BLOCK
disposition_status: VERIFIED
remediation_status: DEFERRED-GATED
verified_env: python 3.12.3 (venv), frozen base b600101 == HEAD app/ (byte-identical)
date: 2026-07-10
---

# Disposition — REV-0005 (ENGINE, runtime execution core)

Reviewer: GPT-5 Codex, verdict **BLOCK** (ENG-001 P0). Author-side verification reproduced both
findings in the supported 3.12 env and **corrects the severity of ENG-001 down (P0 → P1)**.

## Per-finding verdicts

### ENG-001 — protection intent created under HALTED (reviewer P0) → **CONFIRMED (real, reachable)**, **P1**
Control flow confirmed verbatim: `_run_protection` computes `kill_switched` **once**
(`app/monitoring.py:301`) before the per-symbol loop, awaits `market_data.get_snapshot()` (`:306`),
then acts on the **stale** flag (`:310` else → `:316 _open_protective_exit`) with no re-read.
Reproduced in 3.12: a HALTED flip during the loop yields `intent_count=1 reasons=['protection_floor']`
plus a `CREATED` sell order and a `PROTECTION_TRIGGERED` event under HALTED.
- **Realism (crux):** the reviewer's *specific* repro (feed calls `set_kill_switch` inside
  `get_snapshot`) is a **test artifact** — the real `AlpacaMarketDataStream.get_snapshot` has no
  internal `await`, so nothing interleaves *there*. **But the TOCTOU is genuinely reachable** by a
  different real path: `kill_switched` is cached once, and a concurrent `POST /kill` handler sharing
  the event loop can flip HALTED during *any* real await in the tick (e.g. the `adapter.cancel_order`
  network await inside an earlier symbol's exit). Demonstrated with a genuinely separate task — no
  test-only seam required.
- **Why P1, not P0:** INV-060's operative enforcement is the **claim gate** (INV-021 re-checks the
  kill switch atomically under lock). Repro confirms it holds — **the order is blocked at submission;
  0 reached the venue.** The kill switch's ultimate purpose (no new order at the broker) is preserved.
  The real, confirmed harm is intent/audit-layer: (1) a spurious autonomous `PROTECTION_FLOOR` intent
  + `CREATED` order under HALTED (literal violation of safety-core #10 / INV-060 headline); (2) a
  misleading `PROTECTION_TRIGGERED` audit event asserting an exit that is actually blocked; (3)
  skipped `protection_paused` bookkeeping; (4) a **stranded `CREATED` order** that could auto-submit
  an exit on a stale-tick decision once the kill switch lifts. A real bug on a human-gated surface,
  but not a kill-switch *bypass*.

### ENG-002 — timeout-quarantine venue queries not budget-bounded (reviewer P2) → **CONFIRMED (static)**, **P2**
`_resolve_timeout_quarantine` (`app/monitoring.py:952-`) takes no budget and issues one
`get_order_by_client_order_id` per quarantined order (`:985`); the loop's `ReconcileQueryBudget`
(`:460`) is threaded only into `_run_reconciliation` (`:582`), while the loop comment (`:456-459`)
claims the budget covers "ALL … targeted queries." Confirmed. **Read-only** queries, de-facto bounded
by quarantined-order count (not literally unbounded per tick), so low impact — a defense-in-depth /
misleading-comment issue. P2 fair.

## Disposition
- **ENG-001:** CONFIRMED P1 → **gated remediation WO** (kill switch / autonomous intent surface;
  human-approved, test-first, Codex re-review). Fix shape: re-read trading-state per symbol
  immediately before the intent mutation, or serialize the halted-check with intent creation under a
  single point (prefer a store op that atomically validates trading-state while creating the
  autonomous intent). Regression must cover the concurrent-kill-during-await interleaving, both stores.
- **ENG-002:** CONFIRMED P2 → thread the loop budget into quarantine resolution + fix the comment;
  batch with other P2 cleanups.

## Gate
G-E does **not** clear yet (ENG-001 is a real P1 on a gated surface), but the BLOCK is **downgraded**:
the kill switch still stops orders at the venue; the gap is intent-emission + audit integrity + a
stranded-order tail. Evidence: `scratchpad/eng001_repro1.py`, `eng001_repro2.py` (3.12).
