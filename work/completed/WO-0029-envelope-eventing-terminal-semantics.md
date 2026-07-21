---
type: Work Order
title: Envelope terminal-state semantics, disposition eventing, replay coverage (F8 grouped — planning seat to re-cut)
status: SUPERSEDED
work_order_id: WO-0029
wave: W3 remediation (REV-0023 Phase A)
model_tier: strong
risk: medium
disposition: [SUPERSEDED, RESULT_SUMMARY_KEPT]
owner: Ameen
created: 2026-07-12
superseded_by: [WO-0124, WO-0125, WO-0126]
---

> **CLOSE-OUT (2026-07-20, O-1 ratified by Ameen; AUDIT-0002 F005).** Re-cut executed: the
> verified-open items became WO-0124 (SPEC-06/07 disposition-cancel convergence + eventing/
> budget decision), WO-0125 (CC-04 replay/parity coverage), WO-0126 (CC-05 single-source
> replace-budget projection). Already-landed rows stay recorded below as history: SPEC-05 +
> SPEC-09 landed via WO-0029A (`33945c0`/merge `d1d2e4b`, recorded in ADR-010 + INV-082/085);
> SPEC-10 + SPEC-08 landed via WO-0036 cluster 4 (inline DONE notes below); CC-06 subsumed by
> WO-0030. Historical body unchanged.

# Work Order (umbrella): close the F8 lifecycle/eventing gaps

Authoritative: work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md.

Suggested cut (planning seat decides):

**A. Terminal-state semantics (ADR amendments ship with change):**
- SPEC-05: FROZEN + ceiling-overfill → BREACHED edge (add FROZEN→BREACHED to the matrix), never
  clamp-then-COMPLETE; ADR §2/§3 contradiction resolved in text.
- SPEC-09: ADR §5 amended — write-time rejection distinguishes validator-drift (defect) from
  legitimate-state-change (benign refusal); operator signal recalibrated.
- SPEC-10: reject naive `expires_at` at model validation (422 at the approval gate).
  **[DONE — WO-0036 cluster 4 (Codex PR#8 F6), 2026-07-15]** `_hard_rails` now rejects a
  naive `expires_at`; pinned by `test_wo0016_envelope_model.py::test_expires_at_must_be_timezone_aware`.
- SPEC-08: `EnvelopeActionPausedError` handled distinctly from policy crashes in the tick
  (quarantine pause ≠ policy_error freeze; resume semantics per INV-080 decided explicitly).
  **[DONE — WO-0036 cluster 4 (Codex PR#8 F4), 2026-07-15]** the envelope tick now catches
  `EnvelopeActionPausedError` separately and leaves the envelope ACTIVE (paused for
  reconciliation), never FROZEN; pinned by
  `test_wo0020_envelope_tick.py::test_quarantined_child_pauses_not_freezes_the_envelope`.

**B. Disposition eventing + budget decision:**
- SPEC-06: expiry/stale disposition venue cancels get a retry/convergence path (reconcile-driven;
  a failed cancel cannot rest forever).
- SPEC-07: disposition cancels emit envelope_action events with envelope_id provenance; DECIDE
  whether they spend budget (either way, `_BUDGET_ACTIONS` and reality must agree).
- CC-05: `replaces_used` gets a writer (or the field is removed and the API computes
  `_replaces_used(events)`); cockpit column shows truth; models.py false comment fixed.
  **[PARTIAL — WO-0036 cluster 4 (Codex PR#8 F5), 2026-07-15]** the false models.py comment
  is corrected (it no longer claims a writer exists). STILL OPEN here: the read-model /
  cockpit projection — recommended as a SINGLE shared counter over the ENVELOPE_ACTION event
  log used by BOTH `app.sellside.policy._replaces_used` (enforcement) and the read projection,
  so display and enforcement cannot drift (do NOT add a second stored writer — that is the
  "same truth derived twice" anti-pattern AUDIT-0001 flagged).

**C. Replay/parity coverage:**
- CC-04: envelope projector in app/events/; envelope surface included in
  `verify_dual_store_parity` / readmodel parity; replay tests fold the 13 event types.
- CC-06: subsumed by the queued interface-lift WO (base.py ABC + facade ABCs; casts removed).
