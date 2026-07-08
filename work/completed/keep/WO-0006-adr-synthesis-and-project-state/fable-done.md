# WO-0006 — Fable DONE block

`[DONE]` WO-0006 — ADR synthesis + project-state report (audit-wave W1 synthesis).

STATUS: VERIFIED

## What shipped

- **`project-state-report.md`** (this folder) — the deliverable: verified architecture state, the one
  open structural item (order-status flow, NOT-TERMINAL narrow → WO-0007a/0009 done, WO-0007b gated),
  every audit finding dispositioned (zero real code-vs-ADR drift), test-suite health baseline,
  retired-scaffolding + stale-doc inventory, known-unknowns, and a batched human-decision list.
- **`docs/adr/ADR-008-order-status-event-provenance.md`** — candidate ADR, **Proposed** (NOT accepted;
  awaits human acceptance + independent review), documenting the WO-0009 provenance decision.
- **PKL refreshed:** `pkl/architecture/architecture-map.md` (corrected the stale "(now-terminal)"
  claim to the narrow-NOT-TERMINAL reality; `last_verified` bumped); `pkl/process/migration-history.md`
  (change-log: WO-0007a/0009 landed, WO-0007b remaining). `testing-model.md` already current (WO-0008).
- **Code-fix orders drafted to `work/queue/`:** WO-0011 (stale doc/comment refresh + a shadow-fills
  NEEDS-INPUT investigate item) and WO-0012 (mypy grandfather burn-down, stores-first).

## done_when / acceptance — met

- [x] Every WO-0001..0005 + 0007a/0008 finding dispositioned (ADR proposed | code-fix order drafted |
      corrected here | rejected-with-reason). Cross-layer duplicates reconciled (the `core.py:148-152`
      comment, flagged by three audits, is one finding → WO-0011).
- [x] **Zero ADR edits without human approval:** ADR-008 is `Proposed`; no ADR marked Accepted.
- [x] Safety-surface items flagged, not auto-resolved: the WO-0007b flip and ADR-008 are queued for
      independent cross-model review (report §7); no safety-surface drift existed to resolve.
- [x] PKL refreshed / contradicted facts corrected.
- [x] Project-state report complete and stored.

## Evidence

```
command: python -m pytest -q   (canonical; current HEAD after WO-0009)
=> 1895 collected, 1890 passed, 5 skipped, 0 failed, 0 errors
   (5 skips = ALPACA_-gated tests/integration/ cases — intentional)
gates: ruff check . PASS; mypy app/ Success; import-linter 5 kept / 0 broken; coverage floor 93 (~95%)
synthesis: read-only 8-agent fan-out wf_f72ae2bd-071 (verdicts CONFIRMED x4, NOT-TERMINAL narrow, N-A)
OS checks: check_fable_done PASSED; check_work_order_disposition PASSED; check_ledger PASSED
```

## Scope / disposition

- Writes confined to `docs/adr/` (proposed ADR-008), `pkl/`, and `work/` (report + queued WOs) — no
  `app/`, `cockpit/`, or `tests/` touched (WO-0006 forbidden paths respected). (Minor: the WO's
  `write_allowed` list omitted `work/queue/`, which its own body directs code-fix orders to; noted.)
- Disposition: **ADR_CREATED** (ADR-008 proposed), **PKL_UPDATED**, **RESULT_SUMMARY_KEPT**.

## Human-decision batch (report §7 — nothing auto-resolved)

D1 WO-0007b flip sign-off + independent review · D2 ADR-008 (+ optional clock-seam / two-driver ADRs)
acceptance · D3 schedule WO-0012 mypy burn-down · D4 command-endpoint auth gate beta posture ·
D5 CANCEL_PENDING/filled_quantity residuals (fold into WO-0007b).
