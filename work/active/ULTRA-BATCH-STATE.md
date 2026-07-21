# ULTRA beta-prep batch state

This file is the durable continuity record for the consolidated beta-prep batch on
`codex/ultra-beta-batch`. The operator decision block below is the authoritative
ratification source for this session.

## Operator decision block (pre-checked = ratified on paste; edit to override)

- [x] D-SIG-2: ADR-009 re-review = one fresh packet **REV-0034**; reviewer = the CLAUDE seat
      (cross-model rule) — you STAGE the request; the review runs out-of-session.
- [x] D-SIG-3: transport vocabulary = `loopback` default + `tailnet_serve`; **Funnel/public
      exposure forbidden** as a spec-level negative test.
- [x] D-SIG-4: revive the construction-time bind guard + `python -m app` launcher regardless
      of topology.
- [x] D-SIG-5: flag-ON makes ALL sensitive reads operator-key-gated; cockpit key plumbing
      ships in the same change as any enforcement flip (no lockout window).
- [x] D-SIG-6: interim key custody = env-injected static keys, multi-key overlap rotation.
- [x] D-SIG-7: **DECLINE** the archive's multi-exit/single-flight relaxation — signal
      conversion conforms to INV-087 single-mandate + existing single-flight, unchanged.
- [x] D-SIG-8: v1 signal conversion mints the SAME Candidate/SellIntent objects the cockpit
      does; downstream execution identical to manual flow; no new execution lane.
- [x] D-SIG-9: seed `docs/adr/ADR-013-external-ingress.md` (status: Proposed, draft only) —
      the Option-C architecture for TradingView/webhook producers: a thin public RECEIVER
      authenticates the webhook (HMAC/secret), normalizes, and forwards into the private path
      as a keyed producer; the trading API itself is never public. Prereqs named: D-HOST-1
      deployment ADR + acceptance review. (Operator intent: Option C "relatively soon.")
- [x] D-0124: envelope disposition cancels do NOT spend the cancel/replace budget (budget
      guards reprice aggression; wind-down is not reprice churn); `_BUDGET_ACTIONS` + ADR-010
      text aligned to that answer.
- [x] D-0126: the stored `replaces_used` field is REMOVED in favor of the single derived
      counter (not demoted-to-cache).
- [x] D-PROC: WO-0129's protocol policies — P-1: a reviewed party never edits a reviewer-owned
      result in place (separate disclosed addendum only); P-2: gated-surface changes get a
      tracked REV packet even when reviewed in PR threads. Execution-preference bullet is
      promoted into the repo primer.
- [ ] **D-BF-NOW (fill or leave unchecked):** run WO-0115 (real paper-DB backfill
      verification) in this session. Source DB path: `____________________`. If unchecked or
      blank, WO-0115 stays queued (NEEDS-INPUT posture, as ratified).

Already ratified, binding, not re-asked: D-PD1-1..4 (WO-0114 banner), D-SIG-1 = Option A
(localhost-only producer for beta), O-1/O-2/O-3 outcomes, D-BF-6/7. Deliberately deferred to
its own moment: the fresh `signal_records` schema approval (asked at R4 with real DDL).

## Per-work-order scoreboard

| WO | Status | Branch commits | Notes |
|---|---|---|---|
| WO-0114 | QUEUED | — | Lane 1; maximum effort; review-gated to REV-0035. |
| WO-0115 | QUEUED / NEEDS-INPUT | — | D-BF-NOW unchecked and source DB path blank; do not run. |
| WO-0118 | QUEUED | — | Lane 3; after WO-0114 lands. |
| WO-0119 | QUEUED | — | Lane 2; mechanical bootstrap. |
| WO-0120 | CLOSED | `e653a24` activation; `ad7c9fd` checker; close-out: this commit | VERIFIED: records reconciled, folder-aware checker red/green, 160 passed + 1 expected xfail, five AI-OS checks green. |
| WO-0121 | QUEUED | — | Lane 2; serialize after WO-0127 on `docs/INVARIANTS.md`; review-gated to REV-0036. |
| WO-0122 | CLOSED | `4eb89a6` activation; `fb6a5c7` implementation; close-out: this commit | VERIFIED: additive 61-case CI oracle, dual-store mutation-proven INV-051/052 pins, stale fixture repaired; 3867 passed, 11 skipped, 1 expected xfail. |
| WO-0123 | QUEUED | — | Lane 2; tape recorder. |
| WO-0124 | QUEUED | — | Lane 3; elevated effort; review-gated to REV-0037. |
| WO-0125 | QUEUED | — | Lane 2; serialize before WO-0126 on `app/events/**`. |
| WO-0126 | QUEUED | — | Lane 2; after WO-0114 and WO-0125 shared-file work lands. |
| WO-0127 | REVIEW | d32dfb1; 1409eae; 7fa9985; HEAD (review-stage) | ADR-009/ADR-013 remain Proposed; REV-0034 staged against semantic head `7fa9985`; no ledger/disposition until independent review + human text approval. |
| WO-0128 | QUEUED | — | Lane 4; separate red staging branch after WO-0127 text stabilizes. |
| WO-0129 | QUEUED | — | Lane 2; final env sweep after WO-0123. |

## Running NEEDS-INPUT list

- WO-0115 — source paper database path is blank and D-BF-NOW is unchecked. Keep queued.
