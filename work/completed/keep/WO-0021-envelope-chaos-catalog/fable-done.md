# WO-0021 — fable_done

`[FABLE • FULL • verification: DIRECT • task: WO-0021]` — closed 2026-07-12. Tests only; scenario catalog fully covered (regime tapes, thin-market, races, time/session edges, data quality, budget, three wave-level properties). **It did its job: two real findings.**

| Deliverable | Evidence |
|---|---|
| All catalog items → named tests | `test_wo0021_regime_tapes.py` (9), `test_wo0021_envelope_chaos.py` (14 scenarios × stores), `test_wo0021_properties.py` (3 hypothesis properties) — full suite exit 0 |
| FINDING 1 (P2) | `FINDING-W3-lase-pullback-structural-hold` — structural-hold mechanism gap; pinned by strict xfail; W4/SOL bake-off input |
| FINDING 2 (P1) | `FINDING-W3-staged-order-outlives-preemption` — staged order survives flatten preemption, reproduced BOTH stores; pinned by strict xfail; remediation **WO-0024 drafted (human-gated, awaiting approval)** |
| Spec observations | no phase-exit disposition exists (catalog assumed one — ADR-009 §2 gap for the review); reconciliation-inferred fills not envelope-bridged (WO-0020 deferred item, catalog-adjacent) |
| No in-scope fixes | zero app/** changes (`git diff --stat` shows tests/ + work/ only) |

## Status: VERIFIED (as a catalog; the two xfails are deliberate pins, not failures)
