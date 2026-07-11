# W4 seed notes — buy-side Entry Envelope + replay harness (NOT part of W3)

Planning-seat seeds, 2026-07-11. W4 begins only after W3 merges. Two ADR drafts + one harness WO
are expected; nothing here is authorized work yet.

## ADR-010 seed — Entry Envelope (buy side)

Reuses W3 machinery (entity/transitions pattern, engine seam, divergence tripwire, event
provenance, flatten/kill precedence). The inversion vs. sell side: worst case is **unbounded
acquisition**, and premarket spikes are disproportionately manipulated tape. Additional hard
rails beyond the W3 set:
- Aggregate exposure cap across ALL envelopes (not per-symbol) + daily new-risk budget.
- Mandatory liquidity gate before any entry: RVOL floor, minimum session volume, spread ceiling,
  price band (defaults in pkl/architecture/sellside-research-notes.md) — refuse to enter what
  you couldn't exit.
- **No-averaging-down rail**: never add size while mark < average cost (anti-martingale).
- Post-halt cooldown; overextension filter (no entry far above anchored VWAP without
  consolidation).
- Trigger taxonomy as approved envelope fields: BREAK_HOLD_PMH | BREAK_RETEST |
  PULLBACK_TO_ANCHOR — not naive %-move triggers.
- Acquisition ceiling replaces reduce-only; chase limit (max % above trigger price).
- **Atomic spawn**: an entry fill atomically creates the protective sell envelope (one store op);
  no owned share is ever unprotected.

## Replay harness WO seed

- Record real extended-hours tapes (snapshots + events) via the existing event-sourced log;
  replay candidate policies deterministically (pure `decide` makes this free).
- **Pessimistic fill model**: fill only when the tape trades through the limit price, with queue
  haircut; no mid-spread fills. Paper-trading fills are optimistic in thin books — never trust
  them for validation.
- Scoring: the five-metric spec in sellside-research-notes.md, bucketed by regime label.
- Corpus to record: real spikes, grinders, trend-pullback days, fakeout pumps, halt-resume gaps.

## Owed governance before W4 relies on any of this

- ADR-001/ADR-002 superseding decision records (INV-002 / INV-023) — still open.
- ADR-009 must be Accepted post-REV (W3 WO-0022).
