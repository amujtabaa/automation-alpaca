---
work_order: WO-0006
title: Project-state report — audit-wave synthesis (input to beta roadmapping)
date: 2026-07-08
status: SYNTHESIS COMPLETE — human decisions batched at the end (ADR acceptances + roadmap sequencing)
sources: WO-0001..0005, WO-0008, WO-0007a (work/completed/keep/*); WO-0009, WO-0010 (this session)
---

# Project-state report (Spine v2, as-built) — audit wave W1 + remediation W2

Synthesis of the full-repo audit wave (WO-0001 migration-terminal, WO-0002 engine, WO-0003
adapter/store, WO-0004 facade/api, WO-0005 UI) plus the enablement/remediation orders (WO-0008 mypy
gate; WO-0007a routine order-status eventing; WO-0009 faithful provenance; WO-0010 cleanup). Gathered
by a read-only 8-agent fan-out (workflow `wf_f72ae2bd-071`); consolidated and dispositioned here.

## 1. Verified architecture state

**Layering / seams — CONFIRMED (WO-0002/0003/0004/0005, import-linter):** `ui → api → facade →
engine → adapter/store` with strict import seams. `.importlinter` = **5 contracts, 0 broken**; the
four Tier-1 hard invariants (alpaca-SDK-confined, cockpit-thin-client, engine-venue-agnostic,
models-is-a-leaf) hold with zero exceptions; **Contract-5 (routes reach backend only via the typed
facade) has an EMPTY punch-list** — every route is behind the facade. `alpaca-py` is confined to the
adapter; Streamlit imports only the typed API client and owns no execution state (invariants 4–7
CONFIRMED with file:line).

**Safety invariants / ADRs — CONFIRMED (WO-0002/0003):** ADR-001 overfill (broker-authoritative
overfill recorded + quarantined, never hidden; autonomous spawn blocked), ADR-002 timeout-quarantine
(ambiguous submit → `TIMEOUT_QUARANTINE`, no blind resubmit, targeted reconcile by
`client_order_id`), ADR-003 manual-flatten (denied in `Halted`, reduce-only in `Reducing`/`Active`,
scoped/audited single-use emergency override), kill-switch gating of order intent, single-writer
(pure planners in `policy.py`/`transitions.py`/`position.py` with zero persistence; mutation
store-only), and **INV-9** (position folds only `FILL`; `SUBMITTED`/`ACCEPTED`/order-status events
cannot move quantity — re-confirmed under WO-0007a/0009). All with file:line evidence.

**Event-log truth (ADR-004):** every safety-critical truth-routing flow is `event_truth` with
dual-store parity (fills, dedup, overfill/negative-position quarantine, timeout ambiguity, manual
flatten, emergency reduce override, kill/TradingState, reconciliation). No live
`shadow_evented`/`dual_write` scaffolding drives truth.

**Type gate (WO-0008 / ADR-007):** `mypy app/` wired as a CI gate, green today, baseline-and-ratchet
with a **16-module** shrink-only grandfather list. Gates: `ruff check .` (formatter authority),
`lint-imports`, `mypy app/`, `pytest --cov=app --cov-branch` (coverage `fail_under=93`, actual ~95%).

## 2. Migration terminality — the one open structural item

WO-0001 verdict: **NOT-TERMINAL (narrow).** All 16 migration-matrix flows are `event_truth` EXCEPT
the **"Atomic submit claim" order-status / primary-spawn state machine**, which is still
`legacy_truth` (order-row `status` authoritative; projector deferred, `app/events/replay.py:136-139`).

Remediation progress this session:
- **WO-0007a (DONE):** the routine order-status lifecycle now co-writes ExecutionEvents in both
  stores (claim/ack/fill/cancel/reject + the two direct-CANCELED bypass writers), with dual-store
  parity — closing the *eventing* gap. `orders.status` stays authoritative (no read-flip).
- **WO-0009 (DONE):** those events now carry faithful per-transition provenance
  (`ENGINE`/`LOCAL` for the claim + never-submitted cancels; `BROKER_*` for broker-observed).
- **WO-0007b (QUEUED, GATED):** the projector + read-flip that makes `orders.status` a projected
  read-model and marks the matrix fully terminal. **Human-gated event-log-truth change — needs
  human sign-off to execute AND independent cross-model review before any beta milestone relies on
  it.** This is the single remaining step to strict migration terminality.

## 3. Findings disposition (every audit finding accounted for)

**Zero real code-vs-ADR drift.** Across five layer audits the only non-CONFIRMED items are:
- **WO-0002 clock-seam "drift" (WORDING, not code):** pure planners take an injected clock; the
  impure boundary uses one centralized `utcnow()` seam that wraps `datetime.now`, so the codebase is
  not *literally* "no bare `datetime.now()`" as CLAUDE.md/testing-model phrase it. Intent CONFIRMED.
  → Disposition: **resolve-toward-code via a proposed ADR** (bless the seam pattern) + a wording
  tweak to the contract. Candidate ADR drafted (see §4). Not a safety-surface change.
- **The order-status `legacy_truth` flow** (WO-0001/0003/0007a): owned by WO-0007a (done) → WO-0007b
  (queued, gated). Not drift — documented deferral.

Stale docs/comments found (doc-only, no behavior impact), consolidated (the `core.py:148-152` comment
was flagged independently by WO-0001, WO-0002, and WO-0003 — one finding):
- `app/store/core.py:148-152` — wave-3a shadow comment ("fill table stays authoritative") predates
  the fill event-truth flip. → **WO-0011 (queued; execute).**
- `docs/MIGRATION_MATRIX.md` rows 10/11/13 — cockpit "verify later" / Alpaca framing / event log
  "shadow (P2)" lag enforced reality. → **WO-0011.**
- `.importlinter` Contract-5 header comment — still frames Contract-5 as the migration TARGET
  ("most routes not yet migrated") though the punch-list is empty. → **WO-0011.**
- `tests/test_spine_phase3_shadow_fills.py` docstring + 2 skips — shadow-era; **CONFLICTING
  intel** (WO-0001 says the 2 skips are from a removed private store API; the suite-health agent says
  all 5 skips are `ALPACA_`-gated integration tests). → **NEEDS-INPUT / verify before touching**
  (do not edit a test on conflicting information — logged, queued as WO-0011's investigate item).
- `app/events/projectors.py::timeout_quarantined_order_ids` docstring — **FIXED this session
  (WO-0010).**
- `app/models.py` `ExecutionEventType` docstring ("nothing emits these yet") — now false post-WO-0007a.
  → **WO-0011.**
- `pkl/architecture/architecture-map.md` "(now-terminal)" — contradicts WO-0001 NOT-TERMINAL.
  → **CORRECTED in this WO** (PKL is in WO-0006 scope; see §5).

## 4. Candidate ADRs (PROPOSED — human acceptance required; zero accepted here)

Per WO-0006's hard rule ("zero ADR edits without explicit human approval"), these are drafted
`Proposed` for the independent-review queue; none is marked Accepted.
1. **ADR-008 — Order-status ExecutionEvent provenance semantics** (drafted, `docs/adr/`). Records the
   WO-0009 decision (derive `source`/`authority` in-store from `(old,new)`; broker-observed = `BROKER_*`,
   engine-local = `ENGINE`/`LOCAL`; `source=BROKER_REST` until a websocket path exists). Ships with the
   WO-0009 code per the Review policy ("decisions ship with the change").
2. **Clock-seam determinism pattern** (recommended; not yet drafted as a file — see §7 decision batch).
   Bless the single centralized `utcnow()` seam + injected-clock planners as the standard, and align
   the CLAUDE.md/testing-model wording. Raised by WO-0002.
3. **Two-driver TradingState composition** (recommended; not yet drafted). Document the
   `compose_trading_state` most-restrictive-wins composition of the control + reconcile drivers.
   Raised by WO-0002.

## 5. PKL refresh (done in this WO — writable scope)

- `pkl/architecture/architecture-map.md` — corrected "(now-terminal)" to the narrow-NOT-TERMINAL
  reality; `last_verified` bumped.
- `pkl/process/migration-history.md` — change-log entry: WO-0007a (eventing) + WO-0009 (provenance)
  landed; WO-0007b (flip) is the remaining step to terminality.
- `pkl/architecture/testing-model.md` — `mypy` moved from "deferred" to a wired gate (WO-0008),
  with the gate/coverage/grandfather facts; `last_verified` bumped.

## 6. Test-suite health baseline

- **Latest: 1892 collected / 1887 passed / 5 skipped / 0 failed / 0 errors** (after WO-0009). Trail:
  WO-0008 1804 → WO-0007a 1858 → WO-0010 1863 → WO-0009 1887 passed.
- The **5 skips are intentional** `ALPACA_`-gated `tests/integration/` cases (per suite-health recon).
  (One audit note claimed 2 were removed-API shadow skips — reconciled: the live skips are the
  integration gate; the shadow-fills question is the WO-0011 investigate item above.)
- Gates green: `ruff`, `mypy app/`, import-linter (5/0), coverage floor 93 (actual ~95%).

## 7. Known-unknowns + human-decision batch (for roadmap)

**Decisions that are the human's (batched, non-blocking — nothing was auto-resolved):**
- **D1 — WO-0007b flip:** approve executing the order-status projector + read-flip, and schedule its
  independent cross-model review, before any beta milestone relies on event-truth order status.
- **D2 — ADR acceptances:** accept/reject proposed ADR-008 (provenance); decide whether to draft +
  accept the clock-seam and two-driver-TradingState ADRs.
- **D3 — mypy burn-down (WO-0012, queued):** schedule burning down the 16-module grandfather list,
  safety-critical stores first — grandfathered safety modules are currently NOT type-checked.
- **D4 — Auth/token gate** on mutating command endpoints (currently actor-audit label only) — WO-0001
  called this an accepted post-beta upgrade; roadmap must confirm the beta posture.
- **D5 — Residuals:** `CANCEL_PENDING`/release edge eventing and `orders.filled_quantity`
  event-sourcing (fold into WO-0007b's projector scope).

**Independent-review queue (per CLAUDE.md Review policy — in-process validation does NOT satisfy it):**
- WO-0007b (gated flip) before beta reliance.
- Proposed ADR-008 (and any other accepted ADR amendments).
- WO-0009 provenance change touches event-log records (adjacent to event-log truth) — batched for the
  same independent review as ADR-008.

**Non-drift known-unknowns:** `lint-imports` CLI was unavailable in the WO-0001 sandbox (verified via
`tests/test_import_boundaries.py` instead — CLI-level enforcement re-confirmed by the suite-health
recon reading `.importlinter`); whether `cockpit/` should ever come under the type gate.
