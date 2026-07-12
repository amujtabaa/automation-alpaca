# WO-0029A — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0029A]

Both ADR-009 text amendments ACCEPTED by Ameen in-chat 2026-07-12 ("I'll
accept both ADR-009 proposals"); carved from the WO-0029 umbrella (parts B/C
— disposition retry/provenance, replaces_used, projector/replay coverage —
remain with the planning seat).

## done_when → met

1. **FROZEN + ceiling-overfill chains BREACHED, both stores** — new legal
   edge FROZEN→BREACHED (transitions.py + ADR-mirror table test);
   plan_envelope_fill chains BREACHED from FROZEN exactly as from ACTIVE;
   remaining floors at 0; resume of a breached envelope structurally refused.
   RED first (both stores failed with status FROZEN/COMPLETED), then GREEN.
   The benign twin (EXACT fill-to-zero while FROZEN → resume auto-completes)
   is separately pinned and unchanged (INV-079).
2. **Stale-vs-defect classification at the write seam** — new outcome
   STAGE_REFUSED_STALE (+ ENVELOPE_EXEC_REFUSED_STALE): state-dependent rails
   (qty_ceiling, structural order-liveness) refuse benignly — evented as
   ENVELOPE_ACTION action=refused_stale (never counted by budget/cooldown),
   envelope UNTOUCHED, zero venue calls, replan works immediately (pinned:
   the retry stages cleanly). Deterministic rails (floor/ttl/phase/cooldown/
   budget) + reduce_only still freeze with ENVELOPE_PLAN_DIVERGENCE. The
   SPEC-09 falsifying case (partial fill between plan and write) is now the
   benign pin, asserting ACTIVE + no divergence event.
3. **Tests updated to the ACCEPTED semantics** (not weakened — a decided
   behavior change with ADR citations in each test): the old blanket-freeze
   pins rewritten; every defect-rail pin retained.
4. **ADR-009 §2/§3 + §5 amendment texts applied** as accepted; proposal file
   marked ACCEPTED; INV-085 registered; INV-082 amended again.
5. **Full gate green** — ruff/format OK, mypy 64 files, imports 6-0, pytest
   exit 0 / zero FAILED.

## Mutation-checks (all KILLED on committed code)

- MC-1 FROZEN-breach chain reverted → 2 failures.
- MC-2 all rails classified stale (defect channel dead) → 3 failures
  (floor-divergence + TTL-rail tests). Evidence note: the FIRST MC-2 run
  reported 0 failures because the nested-shell `-k` expression selected no
  tests — re-run with explicit test ids before trusting it. Recorded so the
  matrix stays honest.
- MC-3 no rails classified stale (old blanket freeze) → 2 failures.

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT + ADR amendments applied
