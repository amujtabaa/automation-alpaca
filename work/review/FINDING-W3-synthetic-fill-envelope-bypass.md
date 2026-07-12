# FINDING — reconciliation-inferred fills bypass the envelope: the qty ceiling silently re-arms

- **Status:** OPEN (REV-0022 Phase A, completeness-critic CC-01, both stores). Previously
  deferred-logged as "synthetic-fill bridge (rare path)" — the H1-violation compounding was never
  assessed; upgraded to FINDING.
- **Severity:** **P1** (H1/H8; 200 shares reached the venue under a 100-share human-approved
  ceiling in the repro).
- **Cluster:** F5 in `work/review/REV-0022/phase-a.md`. **Must be remediated together with F4**
  (FINDING-W3-multileg-false-divergence-livelock): today F4's second-leg freeze masks this venue
  leg on the assembled tick path; fixing F4 alone converts F5 into a live oversell.

## What

`_apply_inferred_fills` (app/monitoring.py:2184) calls `store.append_fill(...)` directly
(source=RECONCILIATION, authority=SYNTHETIC) — no `_envelope_id_for_order` lookup, no
`record_envelope_fill` — unlike the stream path (app/monitoring.py:1851-1875) which is correctly
record-first. Position folds; `envelope.remaining_quantity` does not move. Both `validate_action`
and `stage_envelope_action` check quantity ONLY against the envelope counter, so after a
reconcile-inferred fill (the designed recovery path for exactly the fills the stream missed and
will never redeliver), both halves of D-3 validate against a provably wrong number.

Repro decisive output (both stores): after a 100-sh inferred fill, envelope still
`active remaining=100 (ceiling=100)`; second venue action `submitted`; venue-submitted SELL qty
total = **200 vs qty_ceiling=100**.

Reachability today: (a) any direct executor call, (b) operator sizing a successor envelope off the
stale remaining/ceiling cockpit column (successor must start remaining == qty_ceiling,
app/store/core.py:2311), (c) automatically the moment F4 is fixed the obvious way.

## What resolves it

WO-0025 (DRAFT, paired with F4): route reconciliation-inferred fills for envelope-linked orders
through the same record-first bridge as the stream path (record_envelope_fill BEFORE append_fill,
same canonical dedupe key), dual-store tests, and a strict pin of the 200-vs-100 repro.

## Repro

Completeness-critic `test_critic_inferred_fill_gap.py` (session scratchpad; mirrors
`_apply_inferred_fills` argument-for-argument). Output quoted in the critic report under REV-0022.
