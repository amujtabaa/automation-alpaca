---
type: Work Order
title: Test-integrity repairs + memory-store atomic envelope rollback (F2+F7)
status: DRAFT — recommended FIRST of the remediation set (restores the suite's evidentiary
  value before anything else relies on "green"). Test changes strengthen only — no human gate
  surface EXCEPT it touches tests (no deletions; additions/strengthening only).
work_order_id: WO-0028
wave: W3 remediation (REV-0022 Phase A)
model_tier: strong
risk: medium
disposition: []
owner: Ameen
created: 2026-07-12
---

# Work Order: make the W3 suite mean what it claims; fix the memory-store rollback defect

## Context packet (authoritative)
- work/review/FINDING-W3-test-integrity.md (F2: TC-01/02/04/05/06/07/08)
- work/review/FINDING-W3-memory-atomic-envelope-rollback.md (F7: TC-03 — real app defect)

## Scope
1. TC-01 (**P0**): delete the `or True` tautology (tests/test_wo0019_engine_seam.py:268-271);
   add a mutation-verified pin that the venue replace targets the working order's broker id.
2. TC-03 (**P1 app fix**): snapshot `_envelopes` in memory `_atomic()` (app/store/memory.py:273-327);
   memory-variant crash-injection atomicity tests (transition, staging, fill, supersede units).
3. TC-02: ATR-expansion-collapse tape pinning ratchet monotonicity (later candidate strictly
   below an earlier one; working stop must not drop).
4. TC-04: narrow `pytest.raises` to the two named refusal types.
5. TC-05: force the approval-first ordering in the kill-race test or drop the dead branch.
6. TC-06: directed budget-drain script inside the hypothesis property (or a targeted strategy)
   so the `replace_calls <= 4` leg is reachable.
7. TC-08: `create_autospec(TradingClient)` in WO-0019a adapter tests.
8. Re-run the test-critic's 13-mutation matrix; all 13 must now be KILLED (paste evidence).
9. (Amended at execution start, 2026-07-12) Pin the REV-0022 Phase A repros as
   `xfail(strict=True)` tests — F1 zero-position, F3 redrive shapes, F4 second-leg freeze,
   F5 inferred-fill bypass, F6 supersession (both defects) — so findings cannot silently
   drift and each remediation WO flips its pin loudly (the WO-0021 pattern).
10. (Amended) Fix the pre-existing ruff F841 at tests/test_wo0021_envelope_chaos.py:225
    discovered at baseline — the WO-0021 close-out gate claim did not hold at the merged
    tip; incident noted in the fable-done.

## Allowed paths
```yaml
allowed_paths: [app/store/memory.py, tests/**]
```

## Done-when
- [ ] All 8 items landed; every W3 mutation from the REV-0022 matrix killed, evidence pasted.
- [ ] No assertion weakened anywhere (diff review: strengthen-only).
- [ ] Full gate green both stores.
