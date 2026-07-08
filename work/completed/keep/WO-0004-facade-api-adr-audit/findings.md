---
work_order: WO-0004
title: Facade + API layer ADR audit — findings
verified_by: Claude (implementer)
date: 2026-07-08
scope: read-only; facade = app/facade; api = app/api
baseline: "72 tests / 72 passed / 0 failed — GREEN (facade/api subset)"
verdict: ADR-005 CONFIRMED (all clauses); 1 stale-config-comment finding; no candidate ADRs
---

# WO-0004 — Facade + API layer ADR audit: findings

Read-only at commit `ebdd84a` (source unchanged since `3989984`). No source/test/ADR edits.

## ADR-005 verdicts (per clause) → **CONFIRMED**
| Clause | Verdict | Evidence |
|---|---|---|
| Routes depend only on typed command/query facades | CONFIRMED | Contract-5 (`api-routes-reach-backend-only-through-the-facade`) `ignore_imports` = **0 edges**; no `from app.store/events/... import` in `app/api/`; facade Protocols `ExecutionCommandFacade`/`ExecutionQueryFacade` (`facade/commands.py:35`, `queries.py:18`) |
| Routes map domain errors to HTTP | CONFIRMED | `facade_error_to_http` (`facade/http_mapping.py:31`) with a fallback so no raw `FacadeError` leaks (`:68`) |
| Routes must not mutate stores / call adapters / inspect internals | CONFIRMED | import-linter Contract-5 empty ratchet + `unmatched_ignore_imports_alerting=error` (any regression fails CI); asserted by `tests/test_import_boundaries.py` (green) |
| engine-not-ready → 503 for commands | CONFIRMED | `EngineNotReadyError` (`facade/errors.py`, exported `facade/__init__.py:20`) mapped via `facade_error_to_http` |
| Command endpoints require auth/actor audit | CONFIRMED | every `ExecutionCommandFacade` method takes `actor: str` (`facade/commands.py:50-109`: create_exit/cancel/pause_buys/set_kill_switch/…); P6-C stamps actor on durable events (`tests/test_phase6c_actor_audit.py` green). NB (WO-0001): it's an audit LABEL, token gate is post-beta. |
| Quarantine/emergency surface through query DTOs | CONFIRMED | `facade/queries.py` + `facade/dtos.py`; `store_backed.py` implements the protocols |

## Focus areas
| Area | Verdict | Evidence |
|---|---|---|
| All routes behind typed facades | CONFIRMED | Contract-5 empty (above) |
| DTO + domain-error mapping | CONFIRMED | `http_mapping.py`, `dtos.py` |
| Auth on mutating endpoints | CONFIRMED | actor threaded through all command methods |
| No engine/store internals leaking through api | CONFIRMED | no direct imports; import-linter enforced |

## Candidate new ADRs
- **None.** The facade layer is fully governed by ADR-005 (+ ADR-006 import boundaries); no undocumented significant decisions found.

## Boundary & stale-doc notes
- **Stale config comment:** `.importlinter` Contract-5 header still frames it as the "migration TARGET… most routes are not yet migrated… `ignore_imports` block is the Phase-6 punch-list." That punch-list is now **empty** (Phase 6 complete; 0 ignored edges). Recommend refreshing the comment to "Phase 6 complete — ratchet holds at zero." (Config edit is out of scope here — report only.)
- Facade/api boundary otherwise clean and enforced.

## Baseline suite (this layer)
```yaml
evidence:
  phase: FULL_SUITE
  command: "pytest -q <facade/api subset: phase6 foundations/command-facade/actor-audit, phase7 routes, import-boundaries>"
  result: PASS
  decisive_output: "72 tests | 72 passed | 0 failed — GREEN"
```

## fable_done
```yaml
fable_done:
  task: "WO-0004 — facade + api layer ADR audit (read-only)"
  done_when_results:
    - "every ADR-005 clause has a file:line verdict: MET (all CONFIRMED)"
    - "4 focus areas checked: MET"
    - "candidate-ADR list: MET (none; stated explicitly)"
    - "boundary + stale-doc note: MET (.importlinter Contract-5 comment stale)"
    - "facade/api test subset baseline: MET (72/72 GREEN)"
    - "no source/test/ADR edits: MET"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Contract-5 ignore_imports = 0 route->backend edges (routes fully behind facade)"
    - "facade_error_to_http mapping; actor:str on every command method"
  status: VERIFIED   # facade/api match ADR-005; only a stale .importlinter comment to refresh
```
