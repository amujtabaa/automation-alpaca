# W3 wave — Execution Envelope (ADR-010): sequencing and branch strategy

## Order of operations

```
ADR-010 (Proposed) + this wave committed first, alone
        │
     WO-0016  envelope entity / transitions / events / persistence   [gated: migration]
        │
   ┌────┴────┐
WO-0017    WO-0018        approval+precedence ∥ pure policy          [0017 gated]
   └────┬────┘
     WO-0019  engine seam + divergence tripwire                      [gated]
        │
     WO-0020  tick wiring + cockpit
        │
     WO-0021  chaos/property catalog (tests only)
        │
     WO-0022  adversarial review: Phase A critic agents → Phase B Codex
        │
   ADR-010 → Accepted (human) → merge decision
```

## Branch strategy (decided guidance)

- **Base:** branch from the current dev tip (`claude/fable-mode-os-install-1dlyk8`, the
  fast-forward superset of master carrying the CAMPAIGN-0001 record) — or from master if the
  pending merge lands first. Do not base on master while it lags the review record.
- **One integration branch for the wave:** `feat/execution-envelope`. First commit on it is this
  planning drop (ADR-010 + WO-0016..0022 + this README + the Codex prompt), so every implementation
  session and the reviewer share one pinned spec in-repo.
- **One short-lived branch per WO** off the integration branch (`feat/execution-envelope/wo-0016`
  etc.), merged back after the WO's in-process checks. Disposable Claude Code session per WO, per
  standing practice.
- **Worktrees:** use two worktrees only for the WO-0017 ∥ WO-0018 fan-out — it's the single
  parallel point. Overlap risk is small but real (`app/models.py` is allowed in 0017;
  `tests/` in both): 0018 must not touch `app/models.py`, and test files should be new files named
  per-WO to keep the merge trivial. Everything else is sequential; extra worktrees buy nothing.
- **Review pinning:** WO-0022 Phase B runs on the integration branch tip as a clean single-commit
  checkout on the authoritative env (REV-0020/0021 practice); record the SHA in the review prompt.
- **Merge gate:** integration branch merges to the mainline only after WO-0022 is dispositioned
  and ADR-010 is marked Accepted by Ameen. Until then master/dev stay untouched by W3.

## Standing cautions for implementers

- All repo-state anchors in these WOs were verified against the 2026-07-11 planning-seat snapshot
  only; re-verify file/line anchors against the live tip at each WO's gate (UNVERIFIED until then).
- Subagents do not load CLAUDE.md — inline invariant criteria in every agent prompt (WO-0022
  Phase A block is the template).
- The adapter replace/edit capability is unconfirmed (see FINDING-alpaca-adapter-wrong-sdk-method):
  WO-0019 stops with NEEDS-INPUT rather than widening into `app/broker/**`.
