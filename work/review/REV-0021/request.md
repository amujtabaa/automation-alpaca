---
type: Review Request
rev_id: REV-0021
campaign_id: CAMPAIGN-0001
title: re-review of the Wave-2 remediation batch (W2-CAND, W2-STALE, W2-SESS, W2-RISK)
status: AWAITING_REVIEW
targets: [W2-CAND, W2-STALE, W2-SESS, W2-RISK]
human_gated_surfaces: [protective-floor]
review_branch: claude/fable-mode-os-install-1dlyk8
base_sha: b600101                 # the frozen campaign base
gated_fix_commits: [2aac709]      # the Wave-2 remediation batch
env: python 3.12                  # see work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md
supersedes_findings: [REV-0012-W2-STALE, REV-0013-W2-CAND, REV-0013-W2-SESS, REV-0014-W2-CAND, REV-0010-W2-RISK]
created: 2026-07-11
---

# Review Request REV-0021 — re-review of the Wave-2 remediation batch

## Your role
Independent review seat (a different model from the author). Read `AGENTS.md`
("## Review guidelines") and `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`: **re-derive from the
code, don't rubber-stamp, findings only — do not push fixes.** The fix is commit `2aac709` on branch
`claude/fable-mode-os-install-1dlyk8`. `git show 2aac709 -- app` is the whole remediation.

This batch remediates four Wave-2 findings — two of them (**W2-STALE**, **W2-SESS**) recovered by the
author-side completeness pass that your own Wave-2 ACCEPTs did not surface (see
`work/review/REV-0012/disposition.md`, `REV-0013/disposition.md`). **W2-STALE touches the protective-
floor safety surface**, so this batch queues for a fresh independent review before that gate clears. An
in-process adversarial pass never counts as independent review.

> Run on **Python 3.12** (`work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md`).

## What you're reviewing

### 1. W2-CAND (P1) — active-candidate single-flight at the store (REV-0013/0014)
`create_candidate` (both stores) now returns the existing active (PENDING/APPROVED) candidate for a
symbol+session idempotently instead of inserting a duplicate — under the SAME lock/transaction as the
insert, mirroring `create_sell_intent`. New `_active_candidate_(un)locked` helper; single-flight clause
added to `StateStore.create_candidate` in `app/store/base.py`.
- **Probes:** can ANY path still create two active candidates for one symbol/session (concurrent ticks,
  dev-inject, retry)? Is "active" (PENDING/APPROVED, per symbol+session) the right bound — does it
  correctly ALLOW a re-buy after a candidate reaches ORDERED, and NOT dedup across different sessions?
  Is input (numerics/session) still validated BEFORE the idempotent return (an invalid duplicate must
  still raise)? Does the idempotent-return break the strategy loop or `inject_mock_candidate`? Dual-store
  parity. Pinned by `tests/test_w2cand_candidate_singleflight.py`.

### 2. W2-STALE (P1, protective-floor) — per-symbol market-data staleness (REV-0012)
`AlpacaMarketDataStream` now marks a snapshot stale if the feed is stale (connection-liveness, the
feed-wide `_last_message_at` clock) **OR** the symbol's own `updated_at` is older than the window
(`_snapshot_stale_locked`). `get_snapshot`/`list_snapshots` use it.
- **Probes:** does a quiet held symbol now read stale even while another symbol keeps the feed clock
  fresh (the REV-0012 masking case), in BOTH directions (masked breach AND spurious exit)? Is the
  feed-wide connection-liveness term still intact (a total outage marks every symbol stale)? Is the
  change **widen-only** (nothing that was stale becomes fresh — the fix can only ADD staleness, never
  remove it)? Any consumer that now over-freezes (e.g. a legitimately illiquid but still-valid symbol)?
  Confirm the fix is in the REAL stream (the `FakeMarketDataFeed` returns `stale` verbatim — the reason
  the original bug escaped unit tests). Pinned by `tests/test_w2stale_per_symbol.py`.

### 3. W2-SESS (P2) — session-close operator actor (REV-0013)
`actor` threaded `close_session` (ABC + both stores) → `plan_close_session` → the `session_closed`
audit payload; the facade stops dropping it; default `"system"`.
- **Probes:** does every close path stamp the actor (operator on a manual close, `"system"` on an
  automatic one)? Purely additive (no session/order/position state change)? A pre-existing test that
  pinned the old `session_closed` payload was updated to include `"actor"` — confirm it was **corrected,
  not weakened**. Pinned by `tests/test_w2sess_close_actor.py`.

### 4. W2-RISK (P3, non-gated) — fail-closed finite guard (REV-0010)
`risk_limit_reason` returns a `nonfinite_risk_input_*` reason on a non-finite `exposure_before_order`/
`order_limit_price` instead of silently approving (NaN/±Inf make each `> cap` comparison False).
Defense-in-depth; every ingress is still finite-gated upstream. Pinned by
`tests/test_w2risk_finite_guard.py`.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check against the invariant **statements** — the safety core ("invalid/stale market data must halt or
quarantine, never drive sizing or submission"), the "at most one active proposal per symbol/session"
buy-side rule, INV-050/060, and the audit contract — not against the new pinning tests. Re-derive what
must always hold and probe the code directly, dual-store where relevant.

## Evidence & how to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** and fill it: a findings
table, an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a **per-target gate
decision** (W2-CAND / W2-STALE / W2-SESS / W2-RISK). Every P0/P1 needs a runnable repro + pasted 3.12
output, dual-store / real-stream where relevant. State plainly anything you could not verify. Do **not**
edit `request.md`; do **not** push code fixes.
