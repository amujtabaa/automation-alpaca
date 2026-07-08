---
work_order: WO-0005
title: UI (Streamlit cockpit) ADR audit — findings
verified_by: Claude (implementer)
date: 2026-07-08
scope: read-only; ui = cockpit/ (app.py 637L, api_client.py 184L)
baseline: "32 tests / 32 passed / 0 failed — GREEN (cockpit + import-boundaries subset)"
verdict: ADR-005 + invariants 4-7 CONFIRMED; no candidate ADRs; no stale docs
---

# WO-0005 — UI (Streamlit cockpit) ADR audit: findings

Read-only at commit `4555503` (source unchanged since `3989984`). No source/test/ADR edits.

## ADR-005 (thin-client clause) + safety invariants 4-7 → **CONFIRMED**
| Invariant / clause | Verdict | Evidence |
|---|---|---|
| #4 Thin client — observes + issues intents, never mutates state directly | CONFIRMED | `cockpit/` imports **nothing** from `app.*`; grimp proof `tests/test_import_boundaries.py:106` `test_cockpit_imports_no_backend_code` (GREEN); all backend interaction is HTTP via `cockpit/api_client.py` |
| #5 UI never calls Alpaca — only the Broker Adapter does | CONFIRMED | no `alpaca` SDK import/call in `cockpit/`; the only "alpaca" strings are cosmetic (page title, the caption "no Alpaca calls from here", env var `ALPACA_API_BASE`) |
| #6 UI owns no strategy/risk/order/fill/position state | CONFIRMED | no `Store`/`Engine`/`Position`/`Order` class, no `_orders`/`_fills`/`apply_fill`/mutation in `cockpit/`; `list_orders`/`list_operator_orders` (`api_client.py:127,148`) are read-through HTTP calls |
| #7 All important logic in the backend | CONFIRMED | `api_client.py` only does `requests.request(method, url, …)` (`:31`) to `ALPACA_API_BASE`/`http://127.0.0.1:8000`; `app.py` renders + issues intents through the client — "no trading decisions" (`api_client.py:4`) |
| ADR-005 "Streamlit imports only the typed API client" | CONFIRMED | import-linter Contract-2 (inv #4) + the grimp proof above |

## Focus areas
| Area | Verdict |
|---|---|
| UI imports only the typed API client | CONFIRMED (no `app.*` imports; HTTP client is cockpit-local) |
| Owns no order/fill/position state | CONFIRMED |
| Never imports alpaca-py or engine/store | CONFIRMED |
| Issues intents only | CONFIRMED (POST/GET via `api_client`) |

## Candidate new ADRs
- **None.** The cockpit is fully governed by ADR-005 + invariants 4-7; no undocumented significant decisions.

## Boundary & stale-doc notes
- Boundary clean and doubly enforced (import-linter INI contract + INI-independent grimp test).
- No stale UI docs found; `cockpit/__init__.py` docstring accurately states "owns no business logic and never talks to Alpaca."

## Baseline suite (this layer)
```yaml
evidence:
  phase: FULL_SUITE
  command: "pytest -q tests/test_cockpit_{candidates,positions,watchlist}.py tests/test_import_boundaries.py"
  result: PASS
  decisive_output: "32 tests | 32 passed | 0 failed — GREEN"
```

## fable_done
```yaml
fable_done:
  task: "WO-0005 — UI (cockpit) ADR audit (read-only)"
  done_when_results:
    - "ADR-005 thin-client clause + invariants 4-7 each have a file:line verdict: MET (all CONFIRMED)"
    - "4 focus areas checked: MET"
    - "candidate-ADR list: MET (none)"
    - "stale-doc note: MET (none)"
    - "UI test subset baseline: MET (32/32 GREEN)"
    - "no source/test/ADR edits: MET"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "cockpit imports no app.* (grimp test:106 green); no alpaca; requests-only HTTP client"
  status: VERIFIED   # cockpit is a clean thin client per ADR-005 + invariants 4-7
```
