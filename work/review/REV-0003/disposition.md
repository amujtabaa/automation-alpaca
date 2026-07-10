---
type: Review Disposition
rev_id: REV-0003
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-09
---

# Disposition — REV-0003 (re-review of the REV-0001/REV-0002 remediation)

Reviewer: GPT-5 (Codex), verdict **ACCEPT-WITH-CHANGES**. Per-target:
**WO-0013 — gate may clear**, **WO-0015 — gate may clear**, **ADR-008 — gate may not
clear as written** (one P1). The single finding is fixed doc-only (no production code
change to the safety-critical fold).

## Changes Applied
- [x] **F-001 (P1) — ADR-008 claimed authority-weighted status projection that does not
  exist** → **Fixed** by clarifying `docs/adr/ADR-008-order-status-event-provenance.md` to
  match the implementation (option a, confirmed with the human). The ADR now states that
  order-status projection (`project_order_status`) folds by **append sequence
  (latest-lifecycle-event-wins) + the legal-transition graph** and treats `source`/
  `authority` as **provenance/audit-only** — it does not read them. The overclaiming spots
  (Context, the `SUBMIT_RELEASED`/`CANCEL_PENDING` rationale, the "authority is the field
  that matters" bullet, and Consequences) were corrected; a **"Truth model (this flow)"**
  statement was added; **authority-aware conflict resolution** is recorded as deferred
  future work (gated on a real conflicting/out-of-order ingest path). The `ENGINE`/`LOCAL`
  vs `BROKER_REST`/`BROKER_AUTHORITATIVE` table was already sound (Codex agreed) and is
  unchanged. The clarified contract is now **pinned by a test**
  (`tests/test_wo0007b_stageb_projector.py`: a `BROKER_AUTHORITATIVE` `FILLED` then a
  `LOCAL` `CANCEL_PENDING` folds to `cancel_pending`; the in-sequence case folds to
  `filled`) so it cannot silently drift toward authority-weighting.

## Disputed Items
- None. The finding was accurate — the overclaim was introduced by the WO-0013 amendment.

## Verification
- `tests/test_wo0007b_stageb_projector.py` — 17 pass (15 prior + 2 new pinning tests);
  `ruff check` clean. No production code touched, so `mypy app/` and the full app suite are
  unaffected.
- `.ai-os` checkers (`check_ledger` / `check_work_order_disposition` / `check_pkl` /
  `check_install`) → PASS.

## Follow-up
- **WO-0013 and WO-0015 independent-review gates are now CLEARED** (Codex ACCEPT for both;
  the ADR-008 P1 did not touch them). The event-log-truth write-path completion and the
  manual-flatten deferral/actor change have passed independent cross-model review.
- **ADR-008 acceptance remains a HUMAN decision.** The clarification addresses the reviewer's
  and the operator's stated concern ("would not accept it unchanged"); ADR-008 stays
  `Proposed` until a human records acceptance in its Status section.
- **Full-suite note:** the reviewer could not verify the full suite (four SQLite
  `ResourceWarning` failures in unrelated candidate/session tests under Python 3.14.5, and
  `ruff`/`mypy` unavailable in that environment). This is a known reviewer-environment
  artifact; the full suite is green in the project's supported environment
  (**1983 passed / 5 skipped / 0 failed** on Python 3.11, `ruff`/`mypy`/`import-linter`
  clean), so the author's full-suite claim stands.
- Ledger updated (`work/ledger.jsonl`: REV-0003 outcome).
