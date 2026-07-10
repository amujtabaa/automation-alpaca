---
type: Review Disposition
rev_id: REV-0001
verdict_received: BLOCK
disposition_status: RESOLVED
date: 2026-07-09
---

# Disposition — REV-0001 (order-status event-truth flip + ADR-008)

Reviewer: GPT-5 (Codex), verdict **BLOCK** on both targets (WO-0007b, ADR-008).
All findings were re-derived, confirmed against the code, and remediated under
**WO-0013** (commit `a7b012d`, hardening in the disposition commit). Independently
re-verified by a 6-agent adversarial pass (all PASS, zero blocking).

## Changes Applied
- [x] **F-001 (P0)** — the double-submit claim gate read the raw `orders.status`
  column, not the projection → **Fixed** in `a7b012d`: `claim_order_for_submission`
  now derives status from `project_order_status` under the same lock in BOTH stores
  (`app/store/memory.py`, `app/store/sqlite.py`). A stale/drifted column can no
  longer re-claim an already-submitted order (proven by dual-store RED→GREEN in
  `tests/test_wo0013_event_truth_writepath.py`). **Sibling-audit** (F-001 second
  bullet): the recon confirmed the raw-column read is systemic (also `transition_order`,
  `flatten_position`, reconcile paths). Rather than flip every write path (larger,
  riskier), the **co-write invariant** — every `orders.status` write co-appends its
  lifecycle `ExecutionEvent` in the same atomic block — was verified across every
  writer (claim→SUBMIT_PENDING, transition_order→exec_event, evented-plan, flatten
  supersede-cancel, close-session cancel; TIMEOUT_QUARANTINE set only via the evented
  co-writing path). So the projection is complete and the siblings are safe under the
  invariant. The gate flip is therefore strictly safer (robust to drift, never worse).
  **Hardening (from the re-review):** a defense-in-depth assert now pins the invariant
  in code at the claim site (mirrors `execution_event_for_routine_transition`) — a raw
  column past CREATED that projects CREATED fails LOUD instead of blind-resubmitting.
- [x] **F-002 (P0)** — the init backfill keyed on `projected==CREATED`, clobbering a
  released-cycle order → **Fixed** in `a7b012d`: keys on status-lifecycle-event
  ABSENCE via the new `projectors.ORDER_STATUS_EVENT_TYPES` (which excludes FILL), in
  both stores. A `SUBMIT_PENDING→SUBMIT_RELEASED` order is no longer re-backfilled; a
  pre-eventing FILLED order (fills, no lifecycle event) is still reconstructed. Proven
  new-fires ⊂ old-fires (removes exactly the buggy cases). Dual-store RED→GREEN +
  idempotency + FILL-exclusion guard tests.
- [x] **F-003 (P1)** — ADR-008 omitted `SUBMIT_RELEASED`/`CANCEL_PENDING` → **Fixed**:
  `docs/adr/ADR-008-order-status-event-provenance.md` amended with both edges
  (`ENGINE`/`LOCAL`) + the ADR-001 consistency rationale (CANCEL_PENDING must not be
  authoritative or it would wrongly win against a late broker FILL). ADR stays
  **Proposed** (human acceptance still required).

## Disputed Items
- None. **F-004 (P1, scope note):** the REV-0001 request's `commit_range` bled in two
  WO-0012 commits — acknowledged; that is a request-metadata artifact, not a code
  defect. The remediation commit `a7b012d` carries no scope bleed.

## Verification
- Tests added: `tests/test_wo0013_event_truth_writepath.py` (12 dual-store, RED→GREEN).
- Gates on the combined tree: full suite green (0 failed), `ruff check` clean, `mypy app/`
  Success, `import-linter` 5 kept / 0 broken.
- Adversarial re-verification: `wf_eb46fdce-662` (VER-13a/13b/X) — all **PASS**, no
  blocking issue; the sibling-audit rationale was independently confirmed defensible.

## Follow-up
- **Gate CLEARED by REV-0003.** WO-0013 re-touched event-log truth (a human-gated surface),
  so the fix queued for a fresh independent review; **REV-0003 (Codex ACCEPT for WO-0013)
  cleared it** — see `work/review/REV-0003/disposition.md`.
- **ADR-008** is now **Accepted** (2026-07-09), after the REV-0003 clarification of its truth model.
- Ledger updated (`work/ledger.jsonl`: WO-0013).
- Deferred (documented, not blocking): a full projection-flip of every order-status
  write path (vs. the verified co-write invariant) is a possible future WO.
