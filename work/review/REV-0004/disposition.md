---
type: Review Disposition
rev_id: REV-0004
campaign_id: CAMPAIGN-0001
verdict_received: ACCEPT (non-gating, environment-limited)
disposition_status: VERIFIED
remediation_status: DEFERRED-GATED
verified_env: python 3.12.3 (venv), frozen base b600101 == HEAD app/ (byte-identical)
date: 2026-07-10
---

# Disposition — REV-0004 (ATTACK-CHAIN, cross-container red-team)

Reviewer: GPT-5 Codex, verdict **ACCEPT (non-gating)** — it could not meet its own
Python-3.12 dual-store repro bar (only 3.14 available), so it filed two concerns as
"unverified." **Author-side verification re-ran both in the supported 3.12 env.**

## Per-concern verdicts

### UC-001 — crash-window DOUBLE-SUBMIT (proposed P0) → **REFUTED** (no live defect)
Reproduced both stores against the real `run_monitoring_tick`. The redrive path
(`_redrive_stale_submitting`, `app/monitoring.py:879`) **does** re-call `adapter.submit_order`
with no read-only pre-check — but it re-submits under the **stable `client_order_id = order.id`**,
and the adapter is idempotent by that key. The real `AlpacaPaperAdapter`
(`app/broker/alpaca_paper.py:245/255` set the key; `:264-294` catch the duplicate
`APIError` and recover the existing order via `get_order_by_client_id`; on recovery failure
raise `TerminalBrokerError` — never a blind retry). Repro: real-adapter arm → **1 venue order**
(same broker id both calls); a hypothetical non-dedup adapter arm → 2 (double-submit). This is
exactly the reused-key reconciliation **ADR-002 sanctions**, not a blind fresh-key resubmit.
- Correction to the reviewer's proposed assertion ("first broker action must be a read-only
  lookup, never a second submit"): that **mis-specifies the design** — the crash path is
  deliberately distinct from the `TIMEOUT_QUARANTINE` path (no quarantine event exists in the
  crash window, so the read-only resolver has nothing to act on; re-drive through the idempotent
  `submit_order` is intended). Tick ordering (redrive before resolver) is a **red herring** here.
- **Residual (documentation follow-up, not a defect):** the no-double-submit guarantee rests on
  two things the frozen code cannot self-enforce — (a) any alternate `BrokerAdapter` MUST honor the
  AIR-003 `client_order_id`-idempotency contract (the non-dedup arm proves a non-conforming adapter
  re-introduces a real double-submit), and (b) the external assumption that Alpaca rejects a
  duplicate `client_order_id` for **all** orders including already-terminal/filled ones. Both are
  documented (AIR-003 / ADR-002) and pinned by `tests/test_alpaca_paper_submit.py`; a **live-broker
  confirmation of (b) before beta** is the one open item.

### UC-002 — actor dropped on cancel audit event (proposed P1) → **CONFIRMED** (both stores), **P1**
Reproduced both stores. The route resolves `actor` (`routes_trading.py:240/260` via
`deps.get_actor`) and passes it to `StoreBackedCommandFacade.cancel`
(`app/facade/store_backed.py:838-893`), which **never uses it** — both branches call
`_cancel_transition(order_id, ...)` (`:875/:893`) → `store.transition_order`, whose signature has
**no actor param** (`base.py:815`, `memory.py:1496`, `sqlite.py:2377`). `plan_transition_order`
builds the `order_transition` payload as `{"from","to"}` only (`core.py:1520`); the corroborating
`ExecutionEvent` carries no actor either. Contrast: `plan_flatten_position` **does** stamp actor
(`core.py:1065`, the REV-0002 F-002 fix) and `set_kill_switch` persists it — so the plumbing exists
but was never extended to cancel. Genuine, in-scope instance of the F-002 dropped-actor class on a
**human-gated surface (cancel/replace)**. Not state corruption (the cancel itself is atomic and
dual-store-consistent) — an **audit-completeness** gap that degrades incident reconstructability.
Fix requires an actor-carrying path through `transition_order`/`plan_transition_order` (schema-
touching), not just a facade edit.

## Disposition
- **UC-001:** REFUTED as a gating defect. Record the cross-layer-contract + external-Alpaca-uniqueness
  dependency as a **beta pre-flight check** (live-broker duplicate-rejection incl. post-fill) and a
  note in ADR-002 / the broker-adapter contract. No code change to the spine required.
- **UC-002:** CONFIRMED P1 → **gated remediation WO** (touches cancel/replace + event payload;
  human-approved, Claude-authored test-first, Codex re-review). Fold into the campaign roadmap.

## Gate
The safety spine is **NOT** composition-broken by this packet: the flagship double-submit concern is
refuted, and the confirmed issue is an audit-trail gap, not a state-truth or venue-safety breach.
Evidence: `scratchpad/uc001_repro.py`, `uc001_real_adapter.py`, `uc002_repro.py` (3.12, both stores).
