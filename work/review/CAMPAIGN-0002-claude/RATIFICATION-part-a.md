# CAMPAIGN-0002 R2 Consolidation — Part A Ratification Record

Records the repo owner's ratification of the seven batched decisions in
`work/review/CAMPAIGN-0002-claude/report.md` §I, per `CONSOLIDATION-CHARTER.md`'s Part A →
hard-stop → human-ratification gate. This is the in-repo record the charter requires ("the
ratification is the human's, recorded in-repo... not inferred from silence").

- **Ratified by:** Ameen (repo owner)
- **Date:** 2026-07-16
- **Basis:** the Part A report as committed at `7300433` (report §A–§J + Executive Summary) and
  its spec-derived conformance oracle `tests/test_r2_conformance_oracle_claude.py`.
- **Mode:** in-chat decision by the operator, transcribed here by the Claude investigator
  (consistent with this repo's established governance practice of recording in-chat approvals —
  cf. the WO-0024/WO-0026/WO-0027 ledger entries' "Approved in-chat").
- **Scope of this record:** it clears the **Part A hard stop** and authorizes *entering* Part B.
  It does **not** waive Part B's own human-gated surfaces. Part B still proceeds through every
  `STOP-FOR-HUMAN` gate in report §H.2 (order-intent lifecycle changes, event-log-truth changes,
  the review-packet dispatch, and the merge itself remain individually human-gated per CLAUDE.md).

---

## Decisions (report §I.1–§I.7)

### I.1 — Canonical mechanism · **RATIFIED as recommended**
Adopt **Sol's delegation-projection** (one shared, full-lineage `project_envelope_obligation`)
as the canonical R2 semantic core, **conditioned on** the performance remediation in I.2. Not
Claude's evented-terminal-propagation as the primary architecture; not defer/re-scope. Basis:
report §F — 125 adversarial cross-verification findings against Claude's code (two independently
reverified as real, incl. a reachable double-exposure past a BREACHED sibling) vs. zero real
findings against Sol's, plus a confirmed reachable pre-existing-data migration gap in Claude's
attempt. Consistent with CLAUDE.md's "safety and correctness outrank velocity."

### I.2 — Performance remediation timing · **RATIFIED as recommended**
The indexed/memoized per-symbol projection (closing report §D's performance gap) is a
**precondition** for Part B code — built and passing its gate *before* the mechanism is relied
on, not a fast-follow. Basis: Sol's current implementation misses its own performance gate by a
wide, reproduced margin (independently re-measured 2026-07-16 at 42 SELECTs/call and ~66× p95
growth on the read path that runs every 15 s in the monitoring tick).

### I.3 — Merge order / PR shape · **RATIFIED as recommended**
The consolidated R2 lands as a **fresh, stacked PR onto current `master`** (`2aa377a`), not a
fold into PR #8 (already merged 2026-07-16, so the fold target no longer exists). PR #7
(signal-seat, unrelated to R2) rebases onto post-consolidation `master` afterward, as its own
merged PR #8 description already anticipated.

### I.4 — Namespace resolutions · **RATIFIED as recommended**
(a) **ADR-010 amendment convention:** use **inline, dated "Amended … (WO-0036 R2)" paragraphs**
within existing §3/§4/§6 (Sol's / the file's own established style), not a new top-level §8
section, for consistency with the file's existing amendment pattern.
(b) **INV-090:** **synthesize** one canonical text from both attempts' wordings (weighted toward
Sol's, as the closer match to the shipped mechanism), rather than adopting either verbatim — the
final text must name the new indexed projection and the grafted pins.

### I.5 — Scope of the monitoring/reconciliation rework · **RATIFIED as recommended**
**Land Sol's `app/monitoring.py` / `app/reconciliation.py` rework together** with the store-layer
mechanism (with report §E.3.2's R6 logging/alerting fix applied in the same change), rather than
deferring it to a separate WO. Basis: that rework is where the R6 silent-gap fix and the
CREATED-excluded-from-`venue_orders` strength both live; splitting the projection from its
real-time driver risks landing one un-co-reviewed with the other.

### I.6 — "Repro 2" severity · **RESOLVED (conditional) by the operator — no prior recommendation**
Report §I.6 deliberately made no recommendation; the operator's ruling:

> "#6 Could be left for SOL to solve. I wouldn't be concerned if it would never occur in beta or
> production environment with live capital being traded (e.g. theoretical/paperwork only issue)."

**Recorded resolution:** resolution of Repro 2 (`flatten_position` can return `flat` in the window
after a fill is recorded but before the order's own `.status` column is advanced) is **delegated
to Sol as part of the Part B mechanism work**, and classified **non-blocking *conditional on*
confirmation that it is theoretical/paperwork-only** — i.e. that it cannot manifest as a real
erroneous exposure (a real double-sell, a mis-sized order, or a position-quantity error) in beta
(PAPER) or any later live/shadow mode. **The condition is load-bearing, not a formality:** if the
Part B investigation finds Repro 2 *is* reachable with real consequence (not merely a transient
stale read the surrounding logic already tolerates), it escalates back to a **beta blocker** and
returns to the operator before any beta-relevant reliance. Discharging this condition (a focused
reachability/consequence analysis of the flatten-vs-fill ordering against INV-001/INV-004) is a
named Part B acceptance item.

### I.7 — Independent review dispatch · **RATIFIED as recommended**
Queue the **REV-0029** independent cross-model review packet **immediately upon Part B
completion**, before any beta-relevant reliance — not batched with other milestones. Basis: the
consolidated change touches human-gated order-intent-lifecycle and event-log-truth surfaces, which
CLAUDE.md's review rule exempts from the default "batched at milestones" cadence. REV-0028
(Claude's own, currently incomplete) is superseded/closed by this new packet.

---

## Effect

- The Part A hard stop is **cleared**. WO-0105 remains **ACTIVE** and is now authorized to enter
  **Part B** under its pre-declared Part B `allowed_paths`, building the canonical R2 per report
  §H.1's ordered program (Sol's projection core → **indexed/memoized projection first (I.2
  precondition)** → monitoring/reconciliation rework with the R6 fix → Claude-side grafts →
  mechanism-agnostic fixes → merged R2 test file → pre-cutover backfill verification).
- Part B execution does **not** auto-run to completion. It advances gate-by-gate through report
  §H.2's `STOP-FOR-HUMAN` checkpoints; the first (the order-intent-lifecycle change: the reconcile
  write-back + the indexed projection) is a human-gated surface and pauses for the operator.
- Repro 2's conditional (I.6) travels into Part B as a named acceptance item that can re-open a
  human decision if its theoretical-only premise fails.
