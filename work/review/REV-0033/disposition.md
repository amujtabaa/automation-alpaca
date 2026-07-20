---
type: Review Disposition
rev_id: REV-0033
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-20
remediated_by: WO-0113
implementation_sha: "cdb7dd98c37e6b05f9e3e4567538f64187603df1"
---

# Disposition — REV-0033

REV-0033 independently reviewed WO-0113 and returned **ACCEPT-WITH-CHANGES** with two
requested changes, one cosmetic consistency note, and two confirmation/note groups. The accepted
changes are remediated at `cdb7dd98c37e6b05f9e3e4567538f64187603df1`. The operator
confirmations in this disposition were carried explicitly by the 2026-07-20 disposition mandate.

## Finding dispositions

| Finding | Disposition | Resolution or confirmation | Strongest evidence |
|---|---|---|---|
| F1 — ADR-001 documentation claimed an audited clear path that does not exist | **ACCEPTED — FIXED** | The intended beta model is now explicit in the projector, ADR-001, INV-002, and the safety PKL: an overfill `QUARANTINED` fact is a permanent, append-only, cross-session latch. Covering fills, restarts, and review do not clear it; no release event exists. No release mechanism was added. | A targeted stale-claim sweep returned `NO_STALE_ADR001_CLEAR_CLAIMS`; `app/events/projectors.py`, `docs/adr/ADR-001-overfill-quarantine.md`, `docs/INVARIANTS.md`, and `pkl/safety/invariants-rationale.md` carry the same permanent-latch contract. |
| F2 — a dynamic protective SELL without current-occurrence venue scope could authenticate any positive LIMIT price | **ACCEPTED — FIXED (option a, fail closed)** | A dynamic wire type/price is session-sensitive and cannot be reconstructed from the durable MARKET intent row. `venue_scope_matches_order` therefore refuses all dynamic reports when the current claim has no persisted scope, leaving the order on targeted uncertainty/recovery. The Alpaca response validator likewise rejects the legacy dynamic allowance without current persisted scope; if a scope is supplied it remains exact authority and the flag cannot widen type/price checks. | Red-first: both new pins failed (`2 failed`). Guard removal: restoring the permissive matcher failed its exact recovery-routing pin; removing the adapter guard failed its exact response-authentication pin. After in-place restoration both pins passed. The eight-file adapter, acceptance, scope, targeted-query, mass-reconcile, and ownership corpus exited 0, confirming exact-scope and legitimate recovery paths remain green. |
| F3 — ordinary accepted-submit recovery omitted `client_order_id` | **ACCEPTED — FIXED** | `_handle_unpersisted_submit` now passes `client_order_id=order.id`, matching the envelope finalizer and repair writer. The existing four-producer/two-store ownership test now requires the field on the recovery row. | `test_cancellation_after_possible_send_keeps_durable_owner`: **32 passed** across first submit, stale redrive, envelope submit, envelope reprice, four cancellation points, and both stores. |
| F4 — `FLATTEN_EXISTING` consumes an emergency grant when it dedupes to a live pre-existing exit | **CONFIRMED — INTENDED, NO CODE CHANGE** | Consumption means one authorized exit existed at the decision point, whether newly minted or already live. If that exit later terminates unfilled, a new authorization is permitted and revalidates every precondition. This is the intended single-use capability semantics for beta. | Operator confirmation carried by the 2026-07-20 disposition mandate; REV-0033's INV-060 probe and existing emergency-capability corpus remain the behavioral evidence. |
| F5(a) — claim-side recovery mirror | **ACCEPTED AS OPTIONAL NOTE, NOT IMPLEMENTED** | The reviewer reproduced fail-closed behavior through an independent recovery-aware guard. Adding a duplicate claim-side mirror is optional defense-in-depth, not required remediation; it is deliberately omitted from this small disposition change. | REV-0033 cancel/claim recovery-asymmetry probe passed on both stores. |
| F5(b) — memory-only defensive envelope-preemption assertion | **ACCEPTED AS OPTIONAL NOTE, NOT IMPLEMENTED** | The missing SQLite assertion is benign diagnostic asymmetry, not a behavior divergence. A twin assertion remains optional hardening and is outside this contained disposition. | REV-0033 store-parity review found no distinguishing behavior defect. |
| F5(c) — five `RATIFIED_YES` decisions needed operator confirmation | **CONFIRMED — MATCH OPERATOR INTENT** | The operator confirms CREATED BUY targeting, protection deferral, append-only attribution, emergency capability, and accepted-submit fallback exactly as recorded in WO-0113. | Explicit 2026-07-20 operator confirmation carried by the disposition mandate. |

## F2 rationale

Fail-closed option (a) was selected because the persisted `Order` records protective intent, not
the exact wire request. During the claim-to-scope crash window, accepting any plausible dynamic
type or positive limit would turn a compatibility heuristic into authentication. Retaining the
report as uncertainty is deterministic, survives restart, and preserves the existing recovery and
manual-review paths without inventing venue scope.

## Verification

- Focused F2 red/green: **2 failed** before production edits; **2 passed** after the guards.
  Independent matcher and adapter guard removals each failed their one exact pin; both edits were
  restored in place and the combined pin returned **2 passed**.
- Acceptance/scope regression corpus: the complete eight-file adapter, targeted-query,
  mass-reconcile, monitoring, fallback, and accepted-identity selection exited 0.
- F3 ownership consistency: **32 passed** for the four producers, four cancellation points, and
  both stores.
- Static/architecture: Ruff check passed; Ruff format reported **258 files already formatted**;
  mypy reported **64 source files** clean; import-linter kept **6/6** contracts with 0 broken.
- Explicit specification gates: Codex oracle **61/61**; Claude oracle **22 passed / 6 documented
  skips**; review hardening **12/12**.
- Scaling: `passed: true`; runtime large/small **1.0604 <= 3.0**, startup elapsed
  **8.1241 <= 12.0**, startup selects **9.1022 <= 12.0**, with no unrelated full scan.
- Full covered suite: **3873 collected; 3861 passed, 11 skipped, 1 xfailed**, exit 0 in
  **590 seconds**. Configured 93.0% branch floor passed at **93.46%**.
- AI-OS: install, version, ledger, PKL, disposition, scope, context hygiene, and contamination
  checks all passed; context hygiene reported **0 violations / 0 advisories**.

```yaml
fable_done:
  task: "REV-0033 disposition remediation and verification"
  done_when_results:
    - item: "F1 permanent-latch contract is consistent across source, ADR, INV, and PKL"
      status: MET
    - item: "F2 missing-current-scope dynamic acknowledgements fail closed with red-first and mutation proof"
      status: MET
    - item: "F3 ordinary accepted recovery carries exact client identity"
      status: MET
    - item: "F4/F5 operator confirmations are durably recorded"
      status: MET
    - item: "Full local gate is green"
      status: MET
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  status: VERIFIED
```

## Gate decision

Every REV-0033 finding is fixed, confirmed, or recorded with the operator-directed optional
disposition above. **REV-0033 disposition: RESOLVED.**
