# W4 seed notes — buy-side Entry Envelope + replay harness (NOT part of W3)

Planning-seat seeds, 2026-07-11. W4 begins only after W3 merges. Two ADR drafts + one harness WO
are expected; nothing here is authorized work yet.

> **Currency correction (2026-07-20, O-2 ratified by Ameen; AUDIT-0002 F006).** The research
> seeds below (rails, trigger taxonomy, pessimistic fill model, corpus taxonomy) remain LIVE.
> The gate/debt claims are stale and corrected as follows: **ADR-010 is Accepted** (2026-07-15,
> REV-0023 chain — the "must be Accepted post-REV" debt below is CLOSED); the
> `record_envelope_fill(price=None)` poison is **CLOSED** (INV-089 / WO-0033 — required price,
> value-guarded, both stores); the ADR-001/ADR-002 superseding decision records remain open as
> written. Sequencing per the 2026-07-20 roadmap ratification: Entry Envelope runs AFTER the
> Signal Seat revival; the replay corpus starts NOW via WO-0123 (tape recorder), so the
> harness's data dependency accrues in parallel; the Entry Envelope's ARMING gates on replay
> validation against that corpus.

## ADR-011 seed — Entry Envelope (buy side)

> Renumbered 2026-07-12: ADR-010 was taken on master by the merged Signal Seat line (PR #5), so the shipped execution-envelope ADR moved to ADR-010 and this seed moved from ADR-010 to ADR-011.

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
- ADR-010 must be Accepted post-REV (W3 WO-0022).

## REV-0023 / remediation-wave learnings for W4 (appended 2026-07-12)

- **Harness axes confirmed by Phase A:** structural-hold (FINDING-W3-lase-pullback…, SOL-0001
  bake-off) and the redrive staleness ceiling (`REDRIVE_MAX_STAGED_AGE_S`, currently 120s — a
  constant the harness should tune) are both empirical questions, not design questions.
- **Property-strategy reachability lesson (TC-06):** random strategies do not reach rail EDGES
  (the budget off-by-one survived 3/3 property runs). W4 harness scenarios need directed
  edge-drain examples alongside generative ones — treat every rail's boundary as an explicit
  `@example`.
- **Tape-synthesis debt:** a STEADY_SURGE tranche-regime tape good enough for a decide→stage
  END-TO-END multi-tranche test does not exist yet (WO-0025 pinned the predicate mechanism
  instead). The W4 tape library should include it — it is also the F4-regression scenario.
- **Clock discipline:** all envelope-suite clocks are now Wednesday-fixed (2026-07-15 14:00 UTC)
  because validate_action rails on session phase; W4 harness must inject its clock everywhere
  from day one (weekend containers WILL bite otherwise).
- **Projection sharp edge:** `record_envelope_fill(price=None)` poisons position projection
  (surfaced by WO-0026) — W4/planning seat: make price required.
