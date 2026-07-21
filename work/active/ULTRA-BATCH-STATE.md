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
| WO-0114 | REVIEW | `f3be6e3` activation; `b6d4fb0` red-first contract; `759eff0` review-stage | Implementation/evidence complete; REV-0035 staged for CLAUDE; ADR-012 acceptance + independent verdict pending; not closed. |
| WO-0115 | QUEUED / NEEDS-INPUT | — | D-BF-NOW unchecked and source DB path blank; do not run. |
| WO-0118 | CLOSED | `a14a8f7` activation; `30d4ae5` budget contract; `2546188` close-out | VERIFIED: three-run target and 10x stress evidence showed near-linear post-Cluster-E scaling; Phase 2 skipped with no store/DDL/index changes; unchanged 3x/12x/2 MiB limits frozen, dispositioned, and moved to `work/completed/keep/`. |
| WO-0119 | CLOSED | `966b1a7` activation; `5f715a8` implementation; `7387199` close-out | Bootstrapper, Python 3.12 devcontainer, and environment pointer verified in a disposable OS-temp checkout; fresh + rerun smoke gates green; dispositioned and moved to `work/completed/`. |
| WO-0120 | CLOSED | `ecfc2f3` activation; `3a27ec8` checker; `325433f` close-out | VERIFIED: records reconciled, folder-aware checker red/green, 160 passed + 1 expected xfail, five AI-OS checks green. |
| WO-0121 | REVIEW | `b03c0e9` activation; `07f7159` annotations; `36538e8` review-stage | Annotation-only safety-record reconciliation frozen; REV-0036 staged against integrated semantic head `07f7159`; no ledger/disposition until independent review + human disposition. |
| WO-0122 | CLOSED | `114e5c3` activation; `9370311` implementation; `4bfeb55` close-out | VERIFIED: additive 61-case CI oracle, dual-store mutation-proven INV-051/052 pins, stale fixture repaired; 3867 passed, 11 skipped, 1 expected xfail. |
| WO-0123 | CLOSED | `635127b` activation; `710ed09` recorder; `6c072d8` boundary pin; `e4d805b` close-out | Read-only, flag-off-by-default recorder with separate bounded tape store, replay documentation, failure-capable zero-order-flow spy, and green full suite; dispositioned and moved to `work/completed/`. |
| WO-0124 | QUEUED / NEEDS-INPUT | — | Lane 3 after WO-0118; D-0124 requires `_BUDGET_ACTIONS` and model-comment alignment in paths the WO does not allow; do not activate without a narrow scope amendment. |
| WO-0125 | CLOSED | `9dec106` activation; `81a5e64` implementation; `2b39830` close-out | VERIFIED: explicit full envelope vocabulary fold, dual-store read-model parity, two mutation-red pins; 3881 passed, 11 skipped, 1 expected xfail. |
| WO-0126 | QUEUED / NEEDS-INPUT | — | Shared-file prerequisites landed, but D-0126 field removal requires `app/store/core.py` and `app/store/sqlite.py`, which the WO forbids; do not activate without a scope amendment. |
| WO-0127 | REVIEW | `c90a7ae` activation; `ba2e358` reconciliation; `8a76a29` FIX; `961fa7e` review-stage | ADR-009/ADR-013 remain Proposed; REV-0034 staged against integrated semantic head `8a76a29`; no ledger/disposition until independent review + human text approval. |
| WO-0128 | CLOSED / RED-STAGING | `e16866f` activation; `24d3746` close-out on `codex/signal-tests-staging` | VERIFIED intentional RED: 51 tests collected; 10 planned R4/R5 ImportErrors only; never merge until mapped slices turn green. |
| WO-0129 | CLOSED | `094f0df` activation; `6aa678f` close-out | Complete 40/40 configuration sweep after WO-0123; primer and P-1/P-2 protocol landed. |

## Running NEEDS-INPUT list

- WO-0115 — source paper database path is blank and D-BF-NOW is unchecked. Keep queued.
- WO-0114 integration — `docs/00_START_HERE.md:394` still states a three-value recovery FSM and
  both automatic outcomes terminal. A separately authorized correction must add
  `needs_review -> operator_reconciled` as the sole human-gated edge; generic updates cannot take it.
- WO-0114 integration — `docs/00_START_HERE.md:840` must name the separate canonical-fill command
  plus exact full-identity/terminal/cumulative-parity attestation before one record leaves the open
  view. WO-0114 did not cross its allowed documentation paths.
- Repository-wide `ruff format --check .` — pre-existing
  `work/review/AUDIT-0002-priorwork/probe_review_integrity.py` would reformat. WO-0114's scoped
  format check is green; do not edit the prior review artifact from this lane.
- WO-0126 — ratified removal of the stored `replaces_used` domain field cannot satisfy the WO's
  current `app/store/**` prohibition: SQLite schema hydration/writes and the shared draft guard
  still consume the field. Preferred amendment: allow `app/store/core.py` and
  `app/store/sqlite.py`, remove every application read/write, and leave the historical SQLite
  column as an inert compatibility tombstone (no DDL/migration). Physical column removal would
  instead require explicit schema/migration approval and a review posture.
- WO-0124 — ratified reprice-only budget semantics require changing
  `app/sellside/policy.py::_BUDGET_ACTIONS`, and the corresponding accounting comment in
  `app/models.py` is outside that path's current qualifier. Preferred amendment: allow the policy
  file and that narrow comment-only model edit; no field, enum, schema, or migration change.
