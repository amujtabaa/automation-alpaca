---
type: Review Result
rev_id: REV-0001
reviewer_model: GPT-5 (Codex)
verdict: BLOCK
date: 2026-07-09
---

## Verdict

**Overall: BLOCK.**

- **WO-0007b:** gate may **not** clear.  The status read-flip leaves the atomic
  submission claim column-authoritative, allowing a stale read-model value to
  reopen an event-log-submitted order; restart backfill can also write a new
  terminal event from that stale value.
- **ADR-008:** gate may **not** clear.  Its proposed provenance matrix omits the
  `SUBMIT_RELEASED` and `CANCEL_PENDING` transitions that WO-0007b added and
  relies on for the flip.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| F-001 | P0 | `app/store/memory.py:1188`, `app/store/sqlite.py:1950` | **reproduced-live, both stores.** After an ordinary `SUBMITTED` event, I changed only the legacy `orders.status` value to `CREATED`. `get_order` still correctly returned `submitted`, but `claim_order_for_submission` read the raw row/object (`memory.py:1190`; `sqlite.py:1952-1953`), returned `claimed`, appended `SUBMIT_PENDING`, and made the event-derived read return `submitting`. Probe output: `memory_claim submitted claimed submitting`; `sqlite_claim submitted claimed submitting`. This contradicts ADR-004's event-truth rule that business logic must not treat legacy tables as authoritative (`docs/adr/ADR-004-event-log-truth-migration.md:15`). | The atomic submission claim is the gate that prevents a second send. A stale/corrupt co-written status column can reopen an already broker-submitted order, regress the log's latest lifecycle state, and permit the normal claimed-order submit path to run again. The pinning test verifies read APIs only, so it misses this safety-critical write-path bypass. | Before every status-dependent planner/transition, derive the order status from the log under the same lock/transaction (or make the projected status the only stored working value). Add dual-store regressions proving a stale `CREATED` column cannot claim a log-`SUBMITTED` order or append another `SUBMIT_PENDING` event. Audit the other status-dependent write paths as part of the same correction. |
| F-002 | P0 | `app/store/memory.py:166-186`, `app/store/sqlite.py:429-455` | **reproduced-live, both stores.** The backfill equates “no lifecycle events” with `projected.status == CREATED`. That predicate is false for a valid evented release cycle: `SUBMIT_PENDING`, then `SUBMIT_RELEASED`, legitimately projects `CREATED`. I made only the co-written column stale (`FILLED`) after that cycle and restarted/initialized. Both stores appended a synthetic `FILLED` event and now projected `filled`: `memory_backfill filled ['submit_pending', 'submit_released', 'filled']`; `sqlite_backfill filled ['submit_pending', 'submit_released', 'filled']`. | Initialization lets a non-authoritative column manufacture a terminal event over an existing lifecycle stream. This violates the promised event-log truth and can convert a re-claimable released order into a terminal filled order solely from stale read-model state. It also disproves the code comments' claim that the path “never overrides an order that already has events.” | Detect actual lifecycle-event presence for the order (or use a one-time migration watermark/version), rather than inferring absence from the folded status. Do not append a status backfill event when any lifecycle event already exists, including `SUBMIT_RELEASED`; add the reproduced release-cycle regression for memory and SQLite. |
| F-003 | P1 | `docs/adr/ADR-008-order-status-event-provenance.md:35-43`, `app/store/core.py:1584-1710` | The ADR says its table defines provenance for routine order-status transitions, but it lists only claim, `CANCELED`, and broker-observed `SUBMITTED`/`PARTIALLY_FILLED`/`FILLED`/`REJECTED`. WO-0007b adds and emits `SUBMIT_RELEASED` (`SUBMITTING -> CREATED`) and `CANCEL_PENDING`; the implementation assigns both `ENGINE`/`LOCAL`, but the proposed ADR never records either decision. | The review target asks whether ADR-008 is safe to accept as the provenance contract for the new status projector. Accepting a table that omits two log-completeness edges leaves the event-truth decision and its authority semantics only in implementation comments, not in the accepted ADR. | Amend ADR-008's decision table and required evidence to cover `SUBMIT_RELEASED` and `CANCEL_PENDING`, including why both are engine-initiated/local and how that remains consistent with ADR-001. Re-review the amended ADR with the corrected implementation. |
| F-004 | P1 | `pyproject.toml:51-55` (in `97123d6~1..64715fe`), `work/queue/WO-0012-mypy-grandfather-burndown.md:18-45` (same range) | The declared WO-0007b commit range also contains commits `e3fb487` and `4537aa2` for WO-0012. They remove `app.store.core` from the mypy grandfather list, add runtime `assert` narrowing changes to `app/store/core.py`, and update the unrelated WO-0012 queue artifact. These files/changes are not named in REV-0001's target or design decision. | This mixes an independent type-ratchet change into a human-gated event-log-truth review. It obscures what the review gate is approving and violates the review policy's P1 scope boundary. | Split WO-0012 commits from the WO-0007b review range (or explicitly amend the review request, scope, and evidence to include them) before dispositioning this packet. |

## Proposed Fixes Summary

Do not clear either target until F-001 and F-002 are corrected and tested across
both stores.  Then update ADR-008 for F-003 and review a WO-0007b-only commit
range or explicitly broaden the packet for F-004.

## Notes

- Pinning suite reproduced green: `python -m pytest -q tests/test_wo0007a_transition_order_eventing.py tests/test_wo0007b_stagea_eventing.py tests/test_wo0007b_stageb_projector.py tests/test_wo0007b_stagec_readiness.py tests/test_wo0007b_staged_readflip.py --basetemp=.pytest-tmp-rev0001` -> **76 passed**.
- The full-suite green claim was **not reproduced** in this checkout: `python -m pytest -x --basetemp=.pytest-tmp-rev0001-firstfail` -> **1 failed, 341 passed, 4 skipped** at `tests/test_candidate_flow_api.py::test_inject_and_list_scoped_to_session`, due to two unclosed SQLite `ResourceWarning`s promoted to errors. The active interpreter is Python 3.14.5; this failure is outside the reviewed diff and I did not establish whether it reproduces on the project's intended Python 3.12 environment.
- `ruff` and `mypy` executables are not available on this checkout's PATH, so I could not independently reproduce those static-gate claims.
- I verified both stores for the two concrete failure modes above. I did not exhaustively prove dual-store parity for every historical/backfill shape, nor verify production backfill against a real pre-eventing database snapshot.
