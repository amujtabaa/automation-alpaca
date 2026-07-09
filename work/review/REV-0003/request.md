---
type: Review Request
rev_id: REV-0003
title: re-review of the REV-0001/REV-0002 remediation (event-truth write-path + manual-flatten)
status: AWAITING_REVIEW
targets: [WO-0013, WO-0015, ADR-008]
human_gated_surfaces: [event-log-truth, order-submission, manual-flatten]
commit_range: 7b704b7..HEAD
created: 2026-07-09
---

## Your Role
You are the **independent review seat** — a different model from the author on purpose.
Follow `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`: re-derive from the code, don't
rubber-stamp, **findings only — do not push fixes**. You have the full repo.

This packet exists because the fix for REV-0001/REV-0002 **re-touches human-gated
surfaces** (event-log truth, the order-submission double-submit gate, manual flatten).
Per the CLAUDE.md Review policy, such a change queues for a fresh independent review
before the gate clears — even though the author already ran an in-process adversarial
pass (which never counts as independent review). Your job: confirm the remediation is
correct and safe, and that it fully closes REV-0001 + REV-0002 without new hazards.

## What You're Reviewing
The remediation of the two prior packets (their `result.md` + `disposition.md` are in
`work/review/REV-0001/` and `REV-0002/`). Run for context:
`git diff 7b704b7..HEAD` (the remediation commit `a7b012d` + the disposition/hardening
commit). Author writeups: the `## Fable DONE` blocks in
`work/queue/WO-0013…md` / `WO-0015…md` and both `disposition.md` files.

## Where to Look (Start Here)
Event-truth write path (WO-0013, REV-0001 F-001/F-002):
- `app/store/memory.py::claim_order_for_submission` + `app/store/sqlite.py` twin — the
  projection-under-lock gate **and the new defense-in-depth assert** pinning the co-write
  invariant. Confirm the assert can only fire on a genuine invariant violation, never in
  normal operation.
- `app/events/projectors.py` — `ORDER_STATUS_EVENT_TYPES` (FILL excluded) + the backfill
  `_backfill_order_status_events_*` predicate in both stores.
- **The load-bearing claim:** the co-write invariant (every `orders.status` write
  co-appends a lifecycle `ExecutionEvent`). The author documented the sibling raw-column
  readers (`transition_order`, `flatten_position`, reconcile/close/exposure) as safe under
  it rather than flipping them. **Independently re-derive this** — grep every `orders.status`
  writer in both stores and find one that does NOT co-write an event, or confirm none.
- `docs/adr/ADR-008-*` (still `Proposed`) — is the `SUBMIT_RELEASED`/`CANCEL_PENDING`
  amendment sound? Should it be Accepted?
- Tests: `tests/test_wo0013_event_truth_writepath.py` (can they fail?).

Manual flatten (WO-0015, REV-0002 F-001/F-002):
- `app/store/core.py::plan_flatten_position` (deferral branch + `actor` payload),
  `app/store/{memory,sqlite}.py` flatten_position (`deferred=plan.deferral_event is not
  None`), `app/facade/store_backed.py` (create_exit / emergency_reduce_override mapping),
  `cockpit/app.py` (`_flatten_button` / `_do`). Confirm **additive-only** (no change to the
  flatten decision, no-blind-cancel, or any order/fill/position state — INV-9) and that the
  `deferred` discriminator never mislabels an idempotent own-manual-flatten.
- `app/facade/dtos.py::FlattenResponse`, `app/store/base.py::FlattenResult`, `docs/INVARIANTS.md`.

Market-data (WO-0014, REV-0002 F-003) — not human-gated, include if time:
- `app/marketdata/alpaca_stream.py` (int() removed), `app/marketdata/service.py` +
  `app/facade/dtos.py` (`volume: float`).

## Review Lenses
- Correctness & Edge Cases — the co-write invariant + the deferred discriminator.
- Security / Data Integrity — double-submit gate, INV-9 single-writer, actor provenance.
- ADR / PKL Consistency — ADR-008 acceptance.

## Specific risks to probe
1. Is the co-write invariant ACTUALLY complete (no `orders.status` write without an event,
   including post-init insert paths)? The claim-gate flip's safety depends entirely on it.
2. Does the new claim-site assert ever fire in a reachable state (false halt)?
3. Backfill: any order shape where the new absence-predicate skips a needed reconstruction
   or fires an unneeded one, or where the two stores diverge?
4. Flatten: any path where `deferred` is wrong, or where the change is not purely additive?
5. Any REV-0001/REV-0002 finding only partially closed?

## How to Respond
Create `result.md` in this folder from `.ai-os/templates/review-result.md`. Verdict:
`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`, per target (WO-0013, WO-0015, ADR-008). State
anything you could not verify.
