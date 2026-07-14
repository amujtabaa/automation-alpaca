# SOL-0001 incumbent findings — triage at the REMEDIATED tip (2026-07-12)

Sol's `findings.md` probed baseline `5a19410`. Every claim was re-verified against the CURRENT
`feat/execution-envelope` tip (post WO-0024..0029A) by re-running Sol's own probes here.
Verdicts:

| Sol id | Sev claim | Verdict at tip | Disposition |
|---|---|---|---|
| SOL-F-001 (write-time validator can't enforce TTL/phase/status/max-outstanding/reduce-only) | P0 | **REMEDIATED** (independently, before intake): probe A now returns `RailViolation(ttl)` (WO-0024); ACTIVE-status + max-outstanding are structural checks in `plan_stage_envelope_action`; reduce-only is INV-084 at the store seam (WO-0026). | RESIDUAL: document the structural division of responsibility (PlannedAction has no side/reduce_only FIELDS by design — the seam mints SELL-only orders and gates position). One paragraph, goes into ADR-010 §5 or the sellside package docstring with the next doc WO. |
| SOL-F-002 (working stop DECREASES across urgency epochs + intra-bucket rewrites) | P0 | **CONFIRMED OPEN** — both probes reproduce at tip (`0.999994 → 0.99` across the pre-market→regular boundary; `1.12 → 1.111429` on a same-bucket rewrite). The ratchet is monotone only WITHIN one invocation; the WO-0028 monotonicity tape held urgency fixed and extended by whole buckets, so it could not see either mechanism. | Pinned strict: `tests/test_sol0001_incumbent_pins.py::test_PIN_SOLF2_*` (×2). Needs a bounded policy WO (draft below). |
| SOL-F-003 (historical stale/crossed rows drive bars/ATR/VWAP) | P0 | **CONFIRMED OPEN** — a stale+crossed $10 print becomes a bar next to a valid $1 latest row; only `snapshots[-1]` is screened. | Pinned strict: `test_PIN_SOLF3_*`. Same WO. |
| SOL-F-004 (stop path `max(1, absorbable)` exceeds a zero participation allowance, unreported) | P1 | **CONFIRMED (source-proven)** — `app/sellside/policy.py:305`; the profiler docstring even names the exception ("probing is the STOP path's prerogative") but nothing reports it. Deterministic pin needs a crafted stop-trigger/zero-allowance tape — ships with the WO. | Human decision required (Sol is right): keep-and-REPORT (participation ClampNote) vs no-plan-at-zero-allowance. |
| SOL-H-001..007 (7 empirical hypotheses) | n/a | Routed to W4 as designed. Note: H-007's "has ever worked" latch HALF is already fixed (WO-0025 live predicate — cancel/reject/fill now clear it); the no-op-reprice-burns-budget half remains a real W4 item. | Fold into the W4 tape library spec (several of Sol's proposed tapes — boundary gaps, cumulative-volume resets, one-print staircases — are exactly the coverage the harness needs). |

## Assessment

Sol's crosswise critique is high quality: one finding independently converged with our own
remediation (F-001 ≈ REV-0023 F3's validator gap — found by four independent reviewers total
now), and two P0-class mechanism defects (F-002, F-003) survived every internal critic because
they live in trail/bar internals no Phase A lens attacked. That is the cross-model lane doing
exactly what it was built for.

## Draft remediation (awaiting approval — new work, not covered by prior blanket)

**WO-0031 (draft): trail/bar data integrity** —
(a) F-002: make the working stop monotone across the envelope LIFETIME: per-epoch urgency for
historical prefix candidates (or persist/restore the ratchet from event history — Sol's own
rival restores it from events, an approach worth comparing), and immutable treatment of
completed partial-bar candidates; regression pins = the two SOLF2 xfails.
(b) F-003: screen the ACTIVE tape (not just the latest row) before any feature computation;
invalid rows → fail closed per the envelope's stale-data disposition; pin = SOLF3 xfail.
(c) F-004: human chooses keep-and-report vs refuse-at-zero; implement + pin.
(d) DRIFT-SVD-2 (from the crosswise run — OUR WO-0029A regression): refused_stale keeps the
refused action's tranche:true and the policy latch counts it — a benignly-refused tranche
permanently consumes the entitlement. One-line fix + production-shape pin
(FINDING-W3-refused-stale-tranche-latch.md).
Allowed paths: app/sellside/{trails,bars,indicators,policy}.py, app/store/core.py, tests/**.
Non-gated surfaces, but touches the frozen-contract module — sequence AFTER the ultracode
crosswise verdict so one consolidation plan covers both sides' trail mechanisms.
CROSSWISE VERDICT NOW IN (see CROSSWISE-REVIEW.md): WO-0031 is clear to draft formally.
