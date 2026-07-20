---
type: Work Order
title: PR #9 Codex-review round-2 P1 follow-ups — monitoring supersession lineage + emergency-reduce retry wedge
status: COMPLETED
work_order_id: WO-0111
wave: R2 consolidation campaign (CAMPAIGN-0002), PR #9 merge-review follow-up (round 2)
model_tier: strong
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen
implementer_seat: Claude
review_seat: Codex PR reviewer (re-reviews the pushed delta on PR #9)
created: 2026-07-18
gated_surface: envelope fill attribution / monitoring cancel lineage; emergency-reduce override (ADR-003)
---

# Work Order: PR #9 review round-2 P1 follow-ups

> Paper-trading simulator; order-lifecycle correctness only. Operator authorized addressing the
> two P1 findings the Codex automated reviewer raised on the second pass of PR #9 (the R2
> consolidation merge PR), on the WO-0109 code. Both are correctness bugs the round-3 review and the
> REV-0030 independent review (Claude ACCEPT) did not reach — each was **empirically confirmed**
> before any code changed.

## Goal

Close the two round-2 P1 findings under the same discipline as WO-0109/WO-0110 (empirical
confirmation → red-first pin → fix → mutation-verify → both stores where applicable → full gate).

## Findings & fixes (both empirically confirmed real)

- **Finding 1 — monitoring disowns a supersession successor's order (`app/monitoring.py`,
  `_validated_envelope_lineage`).** The REV-0029 P1-1 owner-scoped discovery pulls any
  ENVELOPE_ACTION that claims this envelope's intent (via `correlation_id` or referenced-order
  owner) into the lineage — so store-quarantined malformed actions are not lost. But that discovery
  also reached a **well-formed sibling's** action: after a legitimate supersession, the SUPERSEDED
  predecessor's own action (it carries the shared `sell_intent_id` as `correlation_id`) was folded
  into the successor's **single-envelope** projection (`project_envelope_obligation(envelopes=
  [successor])`). Since the predecessor is not in that one-element set, the projector flagged it a
  "missing envelope" (core.py:1186), and `_envelope_id_for_order` then returned `None` for the
  successor's real order — so the successor's broker fills would silently **skip
  `record_envelope_fill`** (monitoring.py:2280 gate), and the successor envelope would never
  decrement / COMPLETE.
  - *Empirical proof:* a supersession probe (predecessor stages a RELEASED child → supersede →
    successor stages a resting child) returned `_envelope_id_for_order(successor_order) = None` with
    `projection.missing_envelope_ids = (predecessor_id,)` on **both** stores pre-fix; returns the
    successor id with empty `missing_envelope_ids` post-fix.
  - **Fix:** `_owner_scoped` now excludes any action parented by a **known, distinct** envelope
    (`known_sibling_ids`) — that action is the sibling's own obligation, audited under its own
    parent lineage. Discovery still fires for a **fabricated/missing/dangling** parent (the R6
    malformed-lineage diagnostic the whole owner-scoped pass exists for). Every hostile-closure P1-1
    pin uses a fabricated parent id (`p1-1-missing-envelope-row`, `missing-parent-*`), so all stay
    green; the store gates were unaffected (they never combine single-envelope scope with
    owner-scoped discovery — a single-`envelope_id` selector strictly filters, memory.py:1091).

- **Finding 2 — emergency-reduce override wedges the operator's retry (`app/store/{memory,sqlite}.py`
  `authorize_emergency_reduce_override`; symptom at `app/facade/store_backed.py:1075`).** The grant
  authorizes exactly one reduce-only exit and is consumed by the flatten on a create/existing/flat
  outcome. But the WO-0108/REV-0029 P0-1 hardening made the flatten fail **closed** (409) whenever a
  venue-uncertain BUY remains (`_flatten_cancelling_open_buys` max-attempts, or the store returning
  `FLATTEN_BUYS_OPEN` before it consumes) — leaving the grant **active and un-consumed**. The
  operator's own documented remedy ("retry after reconciliation confirms them terminal") then hit
  the defensive "an override is already active" refusal on re-authorization → a **permanent 409
  wedge**: the emergency risk-reduction could never complete.
  - **Fix:** re-authorization is **idempotent** — the ADR-003 preconditions (Halted, open position,
    no TIMEOUT_QUARANTINE) are still re-validated on every call, but an already-active grant is
    **reused** rather than stacked. Exactly one grant, one authorized exit, consumed on the first
    authorized flatten. Both stores.

## Evidence

- **Empirical confirmation first** (both findings), then red-first: `tests/test_wo0111_pr9_review_round2.py`
  (2 pins × both stores) fail on the pre-fix tree.
- **Mutation-verified** (in-place edit-back, never `git checkout` on the uncommitted fix):
  - Neuter the `known_sibling_ids` exclusion → `test_finding1_...` red on both stores; restored green.
  - Restore the memory `raise` on active grant → `test_finding2_...[memory]` + the amended
    `test_reauthorize_reuses_active_grant_without_stacking[memory]` red; restored green.
  - Restore the sqlite `raise` → both `[sqlite]` pins red; restored green.
- **Amended one policy-conflict test** (never silently weakened): `test_spine_phase3e_manual_flatten.py`
  `test_double_authorize_without_flatten_refused` → `test_reauthorize_reuses_active_grant_without_stacking`.
  Its real invariant (exactly one grant, one exit) is kept and strengthened (`== {"AAPL"}`, not two);
  the raise it asserted **was** the wedge. Cited to Finding 2 in-body.
- **Full gate green:** `ruff check` + `ruff format --check`; `mypy app/` (64 files); `lint-imports`
  (6 contracts kept); full `pytest` suite (100%, exit 0) — includes both spec oracles and
  `test_review_hardening_gates.py`; perf gate `passed: true` (runtime 1.19 ≤ 3.0, startup 7.44 ≤
  12.0, limits unchanged); AI-OS hygiene (install/version/ledger/pkl/disposition) all pass;
  contamination guard clean (no tracked `.agents/.codex`).

## Why REV-0030 (ACCEPT) and the round-3 review missed these

Honest disposition: both are correctness gaps outside the diff-scoped round-3 lens.
- Finding 1 only manifests on a **supersession-then-fill** trajectory (predecessor with a persisted
  action → successor stages a child → the child fills). REV-0030 verified the owner-scoped discovery
  caught malformed lineages (fabricated parents) but did not construct a legitimate-sibling
  supersession and follow its order into fill attribution.
- Finding 2's wedge is a **second-order consequence of the WO-0109 hardening itself**: making the
  flatten block on every venue-uncertain BUY turned the un-consumed-grant path from a rare edge into
  the *normal* fail-closed exit, which the defensive re-authorization refusal then wedged. Neither
  review exercised authorize → fail-closed-flatten → re-authorize end to end.

## Done-when

- [x] Finding 1 fixed (monitoring); Finding 2 fixed (both stores); red-first + mutation-verified pins.
- [x] Full native gate + oracles + hardening gates + perf gate + AI-OS hygiene green.
- [ ] Pushed to `consolidate/r2-canonical` (PR #9 head) — Codex PR reviewer re-reviews the delta;
      operator merges after the re-review is clean.
