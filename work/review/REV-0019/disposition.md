---
type: Review Disposition
rev_id: REV-0019
verdict_received: ACCEPT
disposition_status: RESOLVED   # was PARTIAL; ENG-001 residual now cleared via REV-0020 (see addendum)
date: 2026-07-10
addendum_date: 2026-07-11
---

> **Addendum (2026-07-11) — env-corrected re-run.** Codex re-ran REV-0019 on the authoritative env
> (Python 3.12.13, single clean commit `9fd1e74`, no checkout movement — the prior run's transient
> checkout reversion is resolved) and its `result.md` was overwritten with a clean **ACCEPT**. The three
> targets that cleared here are re-confirmed authoritatively: **REV-0006-F-001** (sqlite flatten
> one-`_tx()` atomicity), **UC-002** (cancel operator-actor, both branches, `system` default),
> **ADR-008 / INV-075** wording (pure append-sequence fold; no `ORDER_TRANSITIONS` consultation). The
> **ENG-001** residual (REV-0019-F-001) this packet originally found — the post-create/pre-approval
> HALTED window — has since been **remediated (commit `7d41e4d`) and independently CLEARED under
> REV-0020** (`work/review/REV-0020/disposition.md`). So all four REV-0019 targets are now closed and
> this disposition is RESOLVED. The body below is the original (pre-remediation) record.

# Disposition — REV-0019 (re-review of the Tier-1 gated remediation)

Reviewer: GPT-5 Codex, verdict **ACCEPT-WITH-CHANGES**. Per-target gate decision (I
re-derived each against the frozen code on Python 3.12.3, independent of the reviewer's env):

| Target | Reviewer gate | My disposition | Basis |
|---|---|---|---|
| REV-0006-F-001 — sqlite flatten atomicity | CLEAR | **CONFIRMED-CLEAR** | Whole SUPERSEDE_AND_CREATE branch is one `_tx()` (`app/store/sqlite.py:1753-1813`), dispatch joins it via `cur=cur`; the standalone `create_order_for_sell_intent` (`cur=None`) self-heal path stays durable. |
| ENG-001 — protection under HALTED | DO NOT CLEAR | **CONFIRMED — GATE STAYS OPEN** | Independently reproduced the post-create/pre-approval window in **both** stores (below). |
| UC-002 — cancel actor | CLEAR | **CONFIRMED-CLEAR** | Actor threaded to both cancel branches, `"system"` default holds; purely additive. |
| ADR-008 / INV-075 wording | CLEAR | **CONFIRMED-CLEAR** | Wording now describes a pure sequence-ordered fold with legality enforced at `plan_transition_order`; no false ORDER_TRANSITIONS-consultation claim. |

## Findings

- [x] **REV-0019-F-001 (P1) — ENG-001 incomplete: post-create/pre-approval HALTED window** →
  **CONFIRMED.** The ENG-001 store gate (`create_sell_intent`, both stores) closes only the
  *pre-create* race. `_open_protective_exit` then separately awaits
  `transition_sell_intent(APPROVED)` (`app/monitoring.py:380`), `create_order_for_sell_intent`
  (`:385`) and `append_event(PROTECTION_TRIGGERED)` (`:388`) with no further HALTED check and no
  atomic coupling to the FSM. A kill landing in that later window leaves an **ORDERED** protection
  intent, a **CREATED** sell order, and a **PROTECTION_TRIGGERED** event under **HALTED** — an
  INV-060 violation (audit integrity + a stranded order that becomes claimable after release).
  **P1, not P0:** the submission-time claim gate still blocks venue submission, so no live/paper
  order reaches Alpaca. **Reproduced independently** (my own 3.12.3 venv, worktree at `ed517b3`;
  `app/` byte-identical to the reviewed `8027912`), matching Codex's output exactly:

  ```text
  memory halted [('ordered', True)] ['created'] 1
  sqlite halted [('ordered', True)] ['created'] 1
  ```
  (`[('ordered', True)]` = one sell intent, status ORDERED, with a linked order; `['created']` =
  one CREATED sell order; `1` = one PROTECTION_TRIGGERED event — all under `halted`.)

  **ENG-001's gate DOES NOT CLEAR.** A follow-up remediation is required (see Follow-up).

- [x] **REV-0019-F-002 (P2) — stale contradictory flatten commentary** → **CONFIRMED, doc-only.**
  The top-of-method comment `app/store/sqlite.py:1659-1678` still describes the pre-F-001 model
  ("individual steps below each commit their own small SQL transaction … a hard CRASH between the
  two commits below (insert+approve, then dispatch) … durably strands the fresh MANUAL_FLATTEN
  intent"), directly contradicting the single-`_tx()` branch it introduces at `:1744-1813`.
  The self-heal test docstring `tests/test_phase7_flatten_atomic.py:130-144` carries the same stale
  "one transaction, then dispatches … in a SEPARATE transaction / crash between commits" framing —
  though the test body remains valid (the self-heal supersede path is legitimate defense-in-depth
  for a stranded intent from any source, not only flatten's own now-closed crash window).
  Non-gating; batch with the ENG-001 follow-up.

## Disputed Items
- None. Both findings are accurate and reproduce. F-001, UC-002, and the ADR clarification need no
  behavioural change (independently corroborated — my earlier in-process pass and Codex's
  re-derivation agree).

## Verification
- ENG-001 residual reproduced dual-store on Python 3.12.3 (above); code-path confirmed by reading
  `app/monitoring.py:364-406` and the store gate at `app/store/memory.py:787-796` /
  `app/store/sqlite.py` (gate present only on `create_sell_intent`).
- F-002 confirmed by reading `app/store/sqlite.py:1659-1816` and
  `tests/test_phase7_flatten_atomic.py:130-164`.
- Reviewer's own gates (3.12.13): full suite 2008 collected / 0 failed, ruff / mypy / import-linter
  all pass; standalone sell-intent suite 62 passed (self-heal intact). Corroborated — not the sole
  evidence for any CLEAR.

## Follow-up
- **ENG-001 gate remains OPEN.** The kill-switch surface does not clear until the protection
  exit-open (create → approve → order → audit) is atomic with the current-session HALTED check and a
  regression pins the post-create concurrent-kill interleaving in **both** stores. Two fix shapes
  are on the table for human decision (kill-switch = human-gated surface): **(A)** extend the
  store-atomic gate to `create_order_for_sell_intent` for PROTECTION_FLOOR intents (blocks the
  durable order + audit; may briefly leave an APPROVED orphan intent), or **(B)** a single
  store-atomic exit-open operation that checks-HALTED → creates → approves → dispatches under one
  lock, all-or-nothing (Codex's recommended shape; zero partial). Present diff + evidence for the
  gated commit; then a REV-0019-style re-review clears the gate.
- **REV-0019-F-002 (P2)** batches with the follow-up as a doc-only cleanup (refresh the stale
  sqlite comment + test docstring to the single-transaction contract). Non-gating.
- **F-001, UC-002, ADR-008/INV-075 gates are CLEARED** by this re-review (Codex ACCEPT + my
  independent confirmation). The manual-flatten atomicity fix, the cancel-actor propagation, and the
  event-log-truth wording have passed independent cross-model review.
- Ledger updated (`work/ledger.jsonl`: REV-0019 outcome).
