# Ratification record — Part B completion run (D1–D8)

- **Operator:** Ameen
- **Date:** 2026-07-17
- **Verbatim:** "Ratify all as recommended."
- **Scope:** `PARTB-COMPLETION-PLAN.md` decisions **D1–D8, all as recommended**:
  - D1 — YES: setup-only reseed of the 10 Option-B-induced Codex-oracle failures (spec-change
    ratification; assertions byte-identical; dual-baseline proof per plan §3-R4).
  - D2 — YES with park hatch: TDD both pre-existing oracle properties (P-A pre-activation
    sparing; P-B needs-review owner retention) within the named bounded seams; park if exceeded.
  - D3 — YES: F.2 grafts (spared_sell_intents counter; deferred_to_live_envelope_child audit
    reason; masked-predecessor pin reconciliation).
  - D4 — YES: REV-0029 is the single consolidated independent packet (subsumes REV-0024;
    records REV-0028 superseded).
  - D5 — DEFER: backfill verification to post-merge / pre-beta-reliance.
  - D6 — COEXISTENCE: H.1 step 6 resolved as named coexistence of the R2 test files.
  - D7 — YES: conditional widening to `app/models.py` / `app/transitions.py` only if
    mechanically required (flagged; expected unused).
  - D8 — YES: standing no-stop rule (§3-R1 park lane); hard-gated surfaces outside D1–D7
    envelopes always stop.

## Supplemental (asked in the same exchange)

- **D9 (schema-adjacent, asked before run start):** whether an **additive, idempotent
  `CREATE INDEX IF NOT EXISTS`** on the SQLite store (startup-DDL pattern; no table shape or data
  changes) is pre-approved if P2-B / P4 measurements demand it — or whether index-requiring work
  parks instead. **Outcome:** recorded below on answer.
  - Outcome: —

## Defaults applied unless the operator objects (recorded for the run)

1. Perf gates run the default corpus AND `R2_STRESS=1` best-effort; stress-corpus resource limits
   are recorded, not treated as failures.
2. Reporting cadence: commits per phase (visible on the branch); one consolidated operator report
   at the end. No mid-run pings.
3. WO-0036 close-out **archives** the file to `work/completed/keep/` (established convention) —
   never deletes it.
4. If `master` has moved: P8 reports divergence read-only; no rebase, no conflict resolution
   before the review gate.
