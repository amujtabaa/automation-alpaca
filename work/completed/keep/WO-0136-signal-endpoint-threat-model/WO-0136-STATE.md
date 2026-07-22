---
type: Work Order State
work_order_id: WO-0136
status: ACTIVE
created: 2026-07-22
---

# WO-0136 State — Signal-endpoint threat model

## Decision block (as pasted)

- [x] D-TM-1 **Advisory-only, hard boundary.** The deliverable is `docs/THREAT_MODEL_SIGNAL_SEAT.md`
      only. You NEVER edit `docs/adr/**`, `docs/spec/**`, `pkl/**`, `app/**`, `tests/**`, or
      `cockpit/**`. Findings propose; they never amend accepted text.
- [x] D-TM-2 **Every threat row terminates in exactly one of:** an existing accepted control (cited
      to a spec/ADR `file:line` anchor), an explicitly accepted risk (naming the ratifying
      decision), or a numbered **GAP** owned by a rung (R5 / R6 / R7 / ADR-013 / operator
      NEEDS-INPUT). No orphan threats — a self-audit table at the end proves zero orphans.
- [x] D-TM-3 **GAP register is written R5-ready:** each gap phrased as a *testable requirement*
      ("R5 must refuse …", never "R5 should consider …"), so the planning seat can lift the R5 rows
      straight into the R5 WO. This is the document's primary downstream product.
- [x] D-TM-4 **Archive citations use archive-ref provenance** — never bare `REV-0024`/`REV-0025`
      ids (they collide with master's namespace): cite as
      `archive REV-00xx @ origin/archive/claude-wo-0001-install-checks-2x5ys8` (the provenance form
      holds even when you read the content from the master fallback sources below).
- [x] D-TM-5 **Option C (internet/webhook producers) is SIZED, not approved.** The internet-attacker
      section scopes what the future ADR-013 must answer; it approves nothing and proposes no
      deployment. Internet exposure stays STRUCTURALLY excluded today (loopback bind + construction
      bind guard + Funnel prohibition).
- [x] D-TM-6 **Non-gated close-out in-session.** No REVIEW packet. Close out fully in the finishing
      commit (below). A confirmed **P0-equivalent hole in ACCEPTED text** (a safety-surface threat
      the accepted controls demonstrably fail to cover) is the ONE exception: STOP, record the
      decision gap, and escalate to the operator immediately — do not silently downgrade it to a GAP
      row and do not draft an ADR amendment yourself.

## Section checklist

- [x] Assets/boundaries
- [x] Attacker profiles
- [x] STRIDE-per-surface
- [x] Appendix A A-1/A-4
- [x] Appendix B pre-found attacks
- [x] GAP register
- [x] Non-goals
- [x] Self-audit

## Evidence log

- 2026-07-22: Setup adapted to no-remote in-place checkout; `git merge-base --is-ancestor 8d8c0d8 HEAD && echo BASE-OK` printed `BASE-OK`.
- 2026-07-22: Precondition guard passed for WO file, ADR-009 accepted status, ADR-013 proposed status, and fallback pre-found-attack sources.

- 2026-07-22: Drafted `docs/THREAT_MODEL_SIGNAL_SEAT.md`; all required sections checked complete.
