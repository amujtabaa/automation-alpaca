---
type: Work Order
title: Envelope terminal-state semantics, disposition eventing, replay coverage (F8 grouped — planning seat to re-cut)
status: DRAFT — grouped placeholder; planning seat should re-cut into 2-3 WOs. ADR-010 text
  amendments (SPEC-05 FROZEN-overfill edge, SPEC-09 §5 defect claim) are human-gated.
work_order_id: WO-0029
wave: W3 remediation (REV-0023 Phase A)
model_tier: strong
risk: medium
disposition: []
owner: Ameen
created: 2026-07-12
---

# Work Order (umbrella): close the F8 lifecycle/eventing gaps

Authoritative: work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md.

Suggested cut (planning seat decides):

**A. Terminal-state semantics (ADR amendments ship with change):**
- SPEC-05: FROZEN + ceiling-overfill → BREACHED edge (add FROZEN→BREACHED to the matrix), never
  clamp-then-COMPLETE; ADR §2/§3 contradiction resolved in text.
- SPEC-09: ADR §5 amended — write-time rejection distinguishes validator-drift (defect) from
  legitimate-state-change (benign refusal); operator signal recalibrated.
- SPEC-10: reject naive `expires_at` at model validation (422 at the approval gate).
- SPEC-08: `EnvelopeActionPausedError` handled distinctly from policy crashes in the tick
  (quarantine pause ≠ policy_error freeze; resume semantics per INV-080 decided explicitly).

**B. Disposition eventing + budget decision:**
- SPEC-06: expiry/stale disposition venue cancels get a retry/convergence path (reconcile-driven;
  a failed cancel cannot rest forever).
- SPEC-07: disposition cancels emit envelope_action events with envelope_id provenance; DECIDE
  whether they spend budget (either way, `_BUDGET_ACTIONS` and reality must agree).
- CC-05: `replaces_used` gets a writer (or the field is removed and the API computes
  `_replaces_used(events)`); cockpit column shows truth; models.py false comment fixed.

**C. Replay/parity coverage:**
- CC-04: envelope projector in app/events/; envelope surface included in
  `verify_dual_store_parity` / readmodel parity; replay tests fold the 13 event types.
- CC-06: subsumed by the queued interface-lift WO (base.py ABC + facade ABCs; casts removed).
