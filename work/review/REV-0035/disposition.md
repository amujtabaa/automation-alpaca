---
type: Review Disposition
rev_id: REV-0035
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-21
remediated_by: WO-0132
implementation_sha: "2ae9d44"   # pins; core.py conservatism + close-out in 3361d8d; re-verified at d589da4
---

# Disposition — REV-0035

REV-0035 (reviewer: Claude, independent of the Codex builder) reviewed WO-0114 (the PD-1
release valve) and returned **ACCEPT-WITH-CHANGES**: no reproducible safety-invariant
violation, no economic-truth hole; one P1 (an inert pin of the REV-0029 P0-4 class on the
HUMAN_ATTESTED fill rail), two P2s. WO-0132 remediated; the Claude seat independently
re-verified on ref d589da4:

REV-0035 P1-1 / P2-1 — disposition confirmation (Claude seat, 2026-07-21, ref d589da4)

P1-1 mutation re-applied verbatim in a scratch worktree of d589da4: app/store/core.py:586
widened to `authority in (EventAuthority.BROKER_AUTHORITATIVE, EventAuthority.HUMAN_ATTESTED)`.
Result: exactly 4 RED —
  tests/test_wo0114_pd1_release_valve.py::test_PIN_human_attested_plan_append_fill_keeps_strict_rails[memory-buy-5-5-fill_rejected_invalid-cumulative_exceeds_order_quantity]
  ...[memory-sell-0-0-fill_rejected_negative_position-negative_position]
  ...[sqlite-buy-5-5-fill_rejected_invalid-cumulative_exceeds_order_quantity]
  ...[sqlite-sell-0-0-fill_rejected_negative_position-negative_position]
(4 failed, 108 passed). Restored via git checkout, re-ran file: 112 passed, worktree pristine.
The formerly-inert rail is now directly pinned at plan_append_fill, both stores, both rails
(overfill -> FILL_REJECT/cumulative_exceeds_order_quantity; SELL-cross -> negative_position).
=> P1-1 RESOLVED by WO-0132 (pins added in commit 2ae9d44; WO closed by 3361d8d). Minor note:
the tasking said the pins were "in commit 3361d8d" — they are in 2ae9d44; 3361d8d holds the
core.py change and close-out. Substance unaffected.

P2-1 CONFIRMED conservative by 3361d8d: direct_sell_order_may_execute occurrence-less release
now returns True (possibly-live, fail-closed — core.py:1332-1338); project_envelope_obligation
occurrence-less release marks the order invalid and retains intent (core.py:1959-1963) instead
of clearing all intervals. Targeted pins test_occurrence_less_release_cannot_clear_direct_sell_
venue_interval and test_occurrence_less_release_marks_envelope_child_invalid: 4 passed
(memory+sqlite). No discrepancy with the builder's claims found.

**P2-2 (pinned-toolchain verification):** closed by the remediation session's full Python 3.12
suite run (4193 passed / 11 skipped / 1 xfailed), with counts independently reproduced by the
Claude seat's REV-0038 verification run.

Beta reliance on the valve remains gated on **ADR-012 acceptance** (operator). WO-0114's own
close-out (status flip, ledger, move) follows the operator's merge decision per the batch's
review-gated-WO rule. **REV-0035 disposition: RESOLVED.**

## Operator acceptance record (2026-07-22)

**ADR-012 accepted by Ameen** — explicit in-session acceptance, recorded by the planning seat
in the same commit that closes WO-0114. The beta-reliance gate named above is cleared pending
the batch merge to master.
