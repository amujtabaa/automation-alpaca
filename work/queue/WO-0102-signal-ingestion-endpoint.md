---
type: Work Order
title: Signal ingestion endpoint + event-log provenance
status: draft
work_order_id: WO-0102
wave: W4-signal-seat
model_tier: strong
risk: medium
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-11
---

# Work Order: Signal ingestion endpoint + event-log provenance

> **RE-GATED (2026-07-14) — DO NOT ACTIVATE**: REV-0022's formal run returned BLOCK; gated on ADR-009 F-001..F-004 remediation + re-review acceptance, and on WO-0101's spec (drafted, `docs/spec/signal-seat/`, itself draft pending the same remediation)
> **and** WO-0101's spec is complete (this WO must be implementable from that spec alone).
> Sequencing: 0101 → 0102 → {0103, 0104 in parallel}.

## Goal

Implement `POST /signals` (auth: per-producer API key), Pydantic validation, dedupe on **`(producer_id, signal_id)`** (never bare `signal_id`), and append-only `SIGNAL_RECEIVED`/`SIGNAL_QUARANTINED` events. Feature-flagged, **default off**.

## Context packet

Read only these first:

- `CLAUDE.md`
- `docs/adr/ADR-009-signal-seat-boundary.md`
- `docs/spec/signal-seat/**` (WO-0101 output — the implementation contract)
- `app/api/deps.py`, `app/api/schemas.py` (route conventions)
- `app/events/`, `app/store/base.py` (event-type + store conventions)
- `app/features.py`, `app/config.py` (feature-flag conventions)

## Allowed paths

```yaml
allowed_paths:
  - app/api/routes_signals.py        # new signal routes only
  - app/api/schemas.py               # signal DTOs
  - app/api/deps.py                  # wiring + producer/operator credential dependencies
  - app/main.py                      # router mount only (create_app mounts routers explicitly)
  - app/facade/**                    # signal command/query facade — the ADR-005 seam the route talks to
  - cockpit/api_client.py            # operator-credential header plumbing ONLY (no signal UI — that is WO-0103)
  - app/models.py                    # signal event types
  - app/events/**                    # event-type additions + projection
  - app/store/**                     # signal store, both paths
  - app/features.py                  # feature flag (default off)
  - app/config.py
  - .importlinter                    # REQUIRED: add routes_signals to contract 5 source_modules
  - tests/**                         # new signal tests only
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**                    # broker adapter
  - app/facade/commands.py           # order submission path
  - app/protection.py                # kill switch
  - app/transitions.py
  - cockpit/** (except cockpit/api_client.py — credential header plumbing only, see allowed_paths)
```

## Required behavior

- [ ] TDD per Fable: failing tests first for accept / dedupe / malformed→quarantine / auth-reject; both in-memory and SQLite paths.
- [ ] Dedupe keys on **`(producer_id, signal_id)`**, never bare `signal_id` (ADR-009 §Contract 2): the same `signal_id` from two different producers is two distinct signals — cross-producer duplicate-id test required (Codex PR #5 P2).
- [ ] **`producer_id` derived from the authenticated API key, never trusted from the body** (ADR-009 §Contract 1 identity binding); body/credential mismatch rejected at the boundary — mismatch tests for dedupe and rate-limit/quarantine accounting (Codex PR #5 round-3 P1).
- [ ] `app.api.routes_signals` added to `.importlinter` contract 5 `source_modules` in the same change — contract 5 enumerates route modules explicitly, so a new route is NOT gated until listed; `lint-imports` must show the new module covered (Codex PR #5 P1).
- [ ] Router mounted in `create_app` (`app/main.py`) behind the feature flag — the flag-off⇒404 test is only meaningful against the real mount path; route-registration test included (Codex PR #5 P1).
- [ ] **Route reaches the backend only through a typed signal facade** (ADR-005 / `.importlinter` contract 5): `routes_signals` imports the facade, never `app.store`/`app.events` directly and never via the `get_store` dependency loophole — once listed in contract 5, `lint-imports` proves it (Codex PR #5 round-4 P1).
- [ ] **Operator credential required on EVERY sensitive route — reads included — from this WO onward** (ADR-009 Amendment A-1): the full route-authorization matrix ({none, invalid, producer-key, operator-key} × every mounted sensitive route incl. positions/orders/sessions/signals-list/producers) asserted against the real mounted app; transport-policy startup guard (loopback fail-fast / tls_proxy) and key-lifecycle rules implemented as specified.
- [ ] **Ingest processing order per A-4**: authenticate → rails → bounded body read (64 KiB cap) → parse. **The handler takes raw `Request` — no Pydantic body parameter** (FastAPI reads body-model routes before dependencies can reject; Codex rev-2); auth/rails run as body-blind dependencies, then manual capped read + validation. Steps 1–2 reject with zero store writes (sole carve-out: the one epoch-opening PRODUCER_QUARANTINED append at breach) and zero body processing; epoch-bounded audit (one PRODUCER_QUARANTINED per epoch, saturating out-of-log counter, count on PRODUCER_RELEASED); model-based flood test asserts constant event-row count.
- [ ] **Cockpit credential plumbing lands in the SAME change as the auth flip** (Codex PR #5 round-5 P1): `cockpit/api_client.py::_request` sends the operator credential header, so the browser client's kill-switch / manual-flatten / candidate / watchlist controls keep working the moment enforcement turns on — invariant 11 (browser-first) must never have a window where the operator is locked out of safety controls. Test: authenticated cockpit client exercises kill switch + flatten + a candidate command against the enforced backend; unauthenticated request to the same routes → 401/403. Scope note: `api_client.py` ONLY — the rest of `cockpit/**` stays forbidden here (signal UI is WO-0103).
- [ ] Producer API keys are **ingestion-scoped** (ADR-009 §Contract 1 role separation): valid for `POST /signals` only; a producer credential is rejected by every other command route (negative test).
- [ ] Post-quarantine backpressure per ADR-009 rails: ingress from a quarantined producer is rejected at the boundary WITHOUT per-request event appends; coalesced audit only — event log proven bounded under post-quarantine flood (test) (Codex PR #5 P2).
- [ ] **Interim ingest ceiling ships WITH the endpoint** (Codex PR #5 round-6 P2): a conservative hard per-producer + global requests-per-window ceiling, boundary-rejected (429) beyond it with bounded/coalesced audit — so there is NO configurable window between this WO and WO-0104 in which an authenticated producer can flood the append-only log with unique or malformed proposals. Test: sustained over-ceiling ingest leaves the event log bounded. WO-0104's full rails (policy limits + producer quarantine + human release) supersede this ceiling; the ceiling is not removed until they land.
- [ ] Event-log truth: signals reconstructable purely from events (replay test).
- [ ] Flag off ⇒ endpoint absent/404; proven by test.

## Required tests

- [ ] Unit + integration: accept, dedupe on `(producer_id, signal_id)` incl. the cross-producer duplicate-id case, malformed→`SIGNAL_QUARANTINED`, auth-reject — dual-store.
- [ ] Replay: signal state reconstructable purely from events.
- [ ] Flag-off: endpoint absent/404.

## Required commands

```bash
pytest
ruff check .
mypy app/
lint-imports
```

## Acceptance criteria

- [ ] All required behavior implemented; tests prove behavior; evidence pasted.
- [ ] `ruff` + `mypy` + `pytest` + import-linter green.
- [ ] Scope limited to allowed paths; no forbidden paths touched.
- [ ] Fable DONE block includes evidence.
- [ ] PKL update completed or explicitly not required.

## Model-tier rationale

Strong: new API surface writing first-class event types into the event log, dual-store. **Never LITE** (planning-seat directive).

## Notes

- **Escalation rule (planning seat, verbatim intent):** this touches event-log event *additions*, not mutations of existing truth — if the implementer judges this crosses the "event-log truth changes" human-gated surface, **escalate; do not self-decide.**
- `allowed_paths` corrected on install from the draft's `src/api/**`/`src/engine/**` to the as-built tree; finalize file-level scope against WO-0101's spec at activation.
- Disposition intent from planning seat: RESULT_SUMMARY_KEPT + ledger entry.

## Completion disposition

Complete this section after merge, closure, abandonment, or supersession.

Choose all that apply:

- [ ] PKL_UPDATED
- [ ] ADR_CREATED
- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED
- [ ] DELETED
- [ ] SUPERSEDED
- [ ] ABANDONED

## Distillation checklist

- [ ] Durable product facts captured in PKL or not needed.
- [ ] Architecture decisions captured in ADR or not needed.
- [ ] Failure lessons captured in drift/error log or not needed.
- [ ] Compact work result created if future retrieval value exists.
- [ ] Ledger updated.
- [ ] Raw work order marked for archive or deletion.

## Deletion decision

Deletion reason:

<pending completion>
