# FINDING — supersession neither adopts the predecessor's venue order nor conserves remaining

> **Authoritative disposition (2026-07-20): RESOLVED.** The original OPEN record below is
> retained as historical finding text; the additive resolution block is authoritative.

- **Status:** OPEN (REV-0023 Phase A; spec-attacker SPEC-02 + interleaving-attacker INT-002 —
  same seam, two distinct defects, both stores, both lock-serialization orders).
- **Severity:** **P1 (latent)** — no production caller of `supersede_envelope` exists yet (API
  exposes only approve/cancel); becomes live P1 the moment the ADR-010 §3 amendment flow is
  wired. Blocks that wiring.
- **Cluster:** F6 in `work/review/REV-0023/phase-a.md`.

## What

Two defects in one seam (`plan_supersede_envelope`, app/store/core.py:2586-2699):

1. **Orphaned venue order** (SPEC-02): the atomic status swap never cancels or adopts the
   predecessor's SUBMITTED working order. Successor goes ACTIVE with a fresh ceiling while the
   SUPERSEDED envelope's SELL still rests → two live venue orders, aggregate 180 sh vs the 100 the
   human approved once (`venue cancels issued: 0` in the repro). A late fill on the resting order
   decrements the SUPERSEDED envelope's counter, never the successor's. INV-077's rationale
   ("double exposure the human approved once") is violated in substance while holding in status.
2. **Remaining reset** (INT-002): `envelope_draft_reason` (core.py:2311-2312) forces every
   successor to start `remaining == qty_ceiling`; no conservation check (e.g.
   `successor.qty_ceiling ≤ old.remaining_quantity`) exists at commit time. A fill racing the
   amendment is silently absorbed into a widened live mandate: successor ACTIVE remaining=100
   with only 60 unsold; the D-3 write-time rail then passes a 100-share submit (140 total vs 100
   held) because both halves validate against the successor's own reset counter.

## What resolves it

WO-0027 (DRAFT): supersede's atomic unit must (a) cancel-or-adopt the predecessor's live working
order (adopt = re-link order + future fills to the successor; cancel = venue cancel sequenced
before successor activation), and (b) enforce conservation at commit time against the
predecessor's CURRENT remaining. Racing-fill interleaving tests both stores, both orders. ADR-010
§3 amendment recording the decision ships with the change.

## Repros

Spec-attacker harness R5; interleaving probe `test_F3_supersede_first_then_late_fill_and_venue_followthrough`
(pristine-worktree confirmed). Outputs quoted in the critic reports under REV-0023.

## Resolution / disposition (recorded by WO-0120)

**RESOLVED by WO-0027.** Supersession refuses a live venue child, sweeps a staged CREATED child,
and enforces remaining-quantity conservation at commit time. The exact property pins are
`test_PIN_F6_supersede_conserves_remaining_fill_first` and
`test_PIN_F6_supersede_first_late_fill_venue_followthrough` in
`tests/test_rev0023_phase_a_pins.py`, with direct seams in
`tests/test_wo0027_supersession.py`. The assembled W3 remediation review is dispositioned
RESOLVED in REV-0023, and AUDIT-0002 F009 independently reconciled this class as fixed.
**Disposition: CLOSED / RESULT_SUMMARY_KEPT.**
