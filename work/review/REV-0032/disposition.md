---
type: Review Disposition
rev_id: REV-0032
verdict_received: BLOCK
disposition_status: RESOLVED
date: 2026-07-19
remediated_by: WO-0113
implementation_sha: "9a7af3b08a2d050e324a862d59548ff2da747c48"
---

# Disposition — REV-0032

REV-0032 independently reviewed the prior implementer's WO-0112 range and returned **BLOCK** with
six P1 and two P2 findings. Every finding is accepted and remediated by WO-0113 at
`9a7af3b08a2d050e324a862d59548ff2da747c48`.

This disposition records remediation of the prior findings. It does not count as independent review
of the WO-0113 implementation; REV-0033 is the independent gate for that change set.

## Finding dispositions

| REV-0032 finding | Disposition | Final remediation | Strongest evidence |
|---|---|---|---|
| P1 — exit preemption was not durable for candidates created after an exit opened | **ACCEPTED — FIXED** | Exit preemption covers the proposal-to-order epoch. Candidate admission refuses while a same-symbol exit may execute. A candidate that loses the race at final dispatch is atomically expired rather than parked for later revival. | `tests/test_wo0113_primary_remediation.py::test_candidate_creation_is_refused_during_exit_preemption` and `test_exit_blocked_candidate_dispatch_expires_instead_of_reviving`, both stores. |
| P1 — `filled_quantity == 0` spared a still-claimable projected-CREATED BUY | **ACCEPTED — FIXED** | The scalar heuristic was removed. Exit stand-down targets every safely local, event-projected `CREATED` BUY regardless of cached fill progress. Fill facts and position truth are preserved while future claimability is terminated. | `test_exit_preempt_cancels_nonzero_filled_created_buy`; the order becomes `CANCELED`, its recorded fill progress remains, and position truth is unchanged. |
| P1 — local CREATED cleanup ignored recovery truth | **ACCEPTED — FIXED** | Every local CREATED cancel delegates one shared proof: projected `CREATED`, no concrete broker identity, no open unresolved/needs-review recovery, and no accepted-submit fallback owner. Envelope staging first treats a recovery-owned BUY as venue exposure and defers without terminalizing it. | `test_envelope_stage_defers_without_canceling_recovery_owned_created_buy`; `test_direct_created_cancel_is_blocked_by_open_recovery`; `test_terminal_cleanup_spares_recovery_owned_created_child`; and accepted-fallback cancel pins. |
| P1 — envelope stage could persist a stale-sized SELL beside a venue-uncertain BUY | **ACCEPTED — FIXED** | Both store twins re-evaluate same-symbol BUY exposure at the envelope-stage mutation boundary before minting any child. Status, concrete broker identity, recovery, and accepted-submit uncertainty all participate. Deferral writes no SELL artifact; a later tick replans from the converged live position. | `test_envelope_stage_defers_on_venue_uncertain_buy`, plus recovery-owned and broker-owned CREATED variants in the primary and SELL-boundary files. |
| P1 — SQLite filtered the raw status column before applying event truth | **ACCEPTED — FIXED** | SQLite selects by immutable symbol/side scope, projects every candidate order from lifecycle events, and only then filters for `CREATED`, matching memory's decision structure. The common local-cancel primitive also reprojects under the deciding lock/transaction. | `test_exit_preempt_selects_event_projected_created_buy` and `test_direct_created_cancel_uses_event_projection_not_raw_status`. |
| P1 — terminal late-fill cleanup canceled the same child whose fill proved venue execution | **ACCEPTED — FIXED** | Terminal cleanup takes an explicit source-order exclusion. The fill source is retained fail-closed for broker lifecycle/recovery convergence, while a distinct safely local sibling may be canceled. | `test_terminal_fill_excludes_source_cancels_sibling_and_reconciles_once` and the strengthened hostile-closure late-fill scenario; the source remains nonterminal, only the sibling gets one `CANCELED` fact, and the owner obligation is retained. |
| P2 — terminal-fill cleanup reconciled the owner twice | **ACCEPTED — FIXED** | Nested staged-child cleanup runs with `reconcile_owner=False`; `record_envelope_fill` performs one explicit owner reconciliation after all children are processed. Memory and SQLite use the same branch shape. | `test_terminal_fill_excludes_source_cancels_sibling_and_reconciles_once` instruments the seam and requires exactly one call on each store. |
| P2 — exit stand-down dropped the injected stage clock | **ACCEPTED — FIXED** | One logical `action_now` is threaded through stage planning, candidate expiry, local-order cancellation, audit/execution facts, and owner reconciliation. SQLite captures it before the transaction and uses that same value throughout. | `test_exit_preempt_companion_cancel_uses_injected_stage_clock` and `test_terminal_cleanup_uses_injected_fill_clock`. |

## Ratified design decisions

- CREATED BUY targeting: every recovery-free, event-projected `CREATED` BUY, regardless of
  `filled_quantity`; broker identity, open recovery, and accepted-submit fallback are exclusions.
- Protection deferral: audited `None`, no SELL artifact, recompute on a later tick after BUY
  convergence.

Both are recorded as `RATIFIED_YES` in WO-0113 and the affected ADR/invariant documentation.

## Verification

- Focused dual-store remediation: primary exit epoch **14/14** and safe local cancel **24/24**,
  included in the final **580/580** WO/quarantine corpus.
- Guard removal: nonzero-filled CREATED targeting **2 red**; stage BUY rail **4 red**; raw-status
  distinguisher **SQLite red / memory green**; candidate admission **2 red**; terminal dispatch
  expiry **2 red**; injected stage clock **2 red**. Locality/CAS/source/session-close mutations
  failed **18** exact nodes, audit/execution mutations **10**, and rollback **2/2**. All restored.
- Final implementation gate: full suite three consecutive times at **3859 passed, 11 skipped,
  1 xfailed**; coverage **93.50%**; static, oracles, hardening, scaling, scope, AI-OS, and CI
  **#482** green.
- Exact implementation SHA: `9a7af3b08a2d050e324a862d59548ff2da747c48`.

## Gate decision

All eight REV-0032 findings are remediated. **REV-0032 disposition: RESOLVED.**

The WO-0113 implementation remains subject to independent REV-0033 review.
