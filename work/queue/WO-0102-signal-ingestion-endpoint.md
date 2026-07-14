---
type: Work Order
title: Signal ingestion endpoint + event-log provenance
status: ready   # UNFROZEN 2026-07-14 (ADR-009 accepted) — first in sequence, activatable now
work_order_id: WO-0102
wave: W4-signal-seat
model_tier: strong
recommended_model: opus   # defensive-security surface (auth/credentials/rate-limit/quarantine) — Fable dual-use safeguard false-positives here; see .claude/rules/repo-primer.md routing preference
risk: medium
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-11
---

# Work Order: Signal ingestion endpoint + event-log provenance

> **READY — ADR-009 ACCEPTED 2026-07-14; UNFROZEN, activatable now (first in sequence).** REV-0022/0024/0025 hardened the design across three staged packets; the spec is LOCKED (D-1 construction-time bind refusal; D-2 release/deployment gate). This is the first WO of the bundle — build it under Fable/TDD against the LOCKED spec (`docs/spec/signal-seat/`); WO-0103 ∥ WO-0104 follow after it completes. Implementation gets its own independent CODE review; the human-gated surfaces in the CLAUDE.md safety core still stop-and-wait per-action.
> **Enablement is the joint WO-0102 + WO-0103 + WO-0104 milestone** (ADR-009 A-4): this WO ships the **ingestion endpoint + A-1 boundary only** — the **A-2 atomic approval→conversion is WO-0103's** human-gated surface, NOT this WO's (REV-0024-F P1). The flag is structurally un-enable-able until WO-0104's rails satisfy the rails-presence guard, and an enabled seat without WO-0103's conversion path is incoherent (re-opens F-002), so all three co-gate enablement; the flag-on integration tests (route matrix, paced-flood) run at that milestone, not in isolation.
> Sequencing: 0101 → 0102 (ingest endpoint, flag gated off) → 0104 (rails, satisfies the permanent guard) ∥ 0103 (approval/conversion); 0102+0103+0104 co-gate live enablement.

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
  - app/main.py                      # router mount + app construction: docs-route disable/operator-gate, credential-presence + launch-provenance + rails-presence startup guards (A-1/A-4) — Codex rev-3, REV-0024
  - app/server.py                    # NEW backend-owned launch entrypoint (python -m app): programmatic uvicorn, bind derived from validated signal_transport_policy, launch-provenance sentinel (A-1 clause 6, REV-0024-F-001)
  - app/__main__.py                  # NEW: `python -m app` → app.server.run()
  - README.md                        # document `python -m app` as the sole sanctioned start command for an enabled seat; deprecate bare `uvicorn app.main:app` under the flag (A-1 clause 6)
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
- [ ] **Operator credential required on EVERY sensitive route — reads included — from this WO onward** (ADR-009 Amendment A-1): the full route-authorization matrix ({none, invalid, producer-key, operator-key} × every mounted sensitive route incl. positions/orders/sessions/signals-list/producers) asserted against the real mounted app; **credential-presence startup guard** (flag on ⇒ startup fails unless OPERATOR_API_KEY + producer map configured), FastAPI auto-docs routes disabled-or-operator-only and classified, and key-lifecycle rules implemented as specified (Codex rev-3). **The matrix test is flag-on, so it runs at the joint enablement milestone** (WO-0102 routes + WO-0104 rails; the flag is un-enable-able until WO-0104's rails satisfy the rails-presence guard — see the ingest-rails item below); this WO authors it, the milestone runs it green (REV-0024).
- [ ] **Backend-owned launch path — proxy-private bind enforced at CONSTRUCTION, no listener without the launcher** (ADR-009 A-1 clause 6, REV-0025-F-001; Ameen D-1): a request-time 503 is insufficient — `uvicorn app.main:app --host 0.0.0.0 --lifespan off` still accepts TCP + serves 503 on the forbidden port (Codex live-reproduced). Ship `app/server.py::run()` (invoked `python -m app`) that starts uvicorn **programmatically** with the bind derived from + re-validated against `signal_transport_policy`, exiting non-zero **before serving** on any non-loopback/non-socket bind; it mints an **opaque one-shot code-owned capability** (NOT env/config/importable) and passes it to the construction factory. With the flag on, **building the app without the capability raises** — so the module-level `app` import target is removed/refuses, and a bare `uvicorn app.main:app` fails at **import** ⇒ uvicorn opens **no listener**. Keep a fail-closed ASGI request guard as **defense-in-depth only**. Constraints: no env switch, no importable pre-authorized `app`, no zero-arg authorized factory may mint the capability. Document `python -m app` as the sole start command in README; flag off ⇒ construction unrestricted (bare uvicorn dev command unchanged).
- [ ] **Mutation-sensitive launch proof** (REV-0025-F-002): a **subprocess** test with `OPERATOR_API_KEY` + producer map + rails ALL present (so no unrelated startup guard supplies the failure): (a) `uvicorn app.main:app --host 0.0.0.0` + flag on, **both `--lifespan on` and `--lifespan off`**, → **no accepting listener / connection refused**, asserted at the socket level (NOT an HTTP 503); (b) a same-config **positive control** — sanctioned `python -m app` on the policy-valid loopback bind — reaches a **ready listener** serving `GET /api/health`; (c) the launcher with a non-loopback bind + flag on → exit non-zero asserting the **exact A-1 bind-policy reason**. Removing/mutating any single A-1 check must make its own assertion fail.
- [ ] **Ingest processing order per A-4**: authenticate → rails → bounded body read (64 KiB cap) → parse. **The handler takes raw `Request` — no Pydantic body parameter** (FastAPI reads body-model routes before dependencies can reject; Codex rev-2); auth/rails run as **body-blind dependencies**, then manual capped read + validation. Steps 1–2 reject with zero body processing and **zero store writes — with the single exception of the one epoch-opening `PRODUCER_QUARANTINED` append** when a request first crosses a breach threshold (the one permitted carve-out per `03-rails.md §4`; REV-0025-F-006 — do NOT state a blanket "zero writes" that omits it), and with no "otherwise-valid" qualifier on the rate decision (that would require parsing before the rate decision — REV-0024-F-004). This WO defines the **rails seam** (the Protocol the body-blind dependency consults); the rails *implementation* — refilling bucket, non-refilling invalid/conflict budget, quarantine epoch, release — is **WO-0104's** (`03-rails.md §1/§1a/§4/§5`). There is **no interim ceiling** (withdrawn, REV-0024-F-004).
- [ ] **Permanent rails-presence startup guard** (ADR-009 A-4; REV-0024-F-004, REV-0025-F-005): with `signal_seat_enabled` on, `create_app` startup **fails fast unless a conforming rails provider is wired** (rate bucket + non-refilling invalid/conflict budget + quarantine epoch + human release) — exactly parallel to the credential-presence guard, and a **standing invariant, never deleted**. In production that provider is WO-0104's real one (proven wired by the production entrypoint; a Protocol-presence check can't tell it from a permissive fake), so this WO ships the endpoint with the flag **structurally un-enable-able against real wiring** until WO-0104 **satisfies** the guard.
- [ ] **Sanctioned test seam so WO-0102's own route tests are runnable in isolation** (REV-0024-F P1, REV-0025-F-005): the flag-on app has two construction guards — rails-presence and the launch-provenance capability. WO-0102 ships (i) a **test-double rails provider** and (ii) a **test-only construction path that mints the launch capability** — both confined to a test seam that **production config/environment cannot select** (never a production default; the production `python -m app` entrypoint is separately proven to wire WO-0104's *real* provider, REV-0025-F-005). Its accept/dedupe/malformed/auth integration tests use them to build a mounted flag-on `TestClient` app without weakening either guard or implementing WO-0104 early. The **paced-flood constant-event-row** and **full route-authorization matrix** tests still run at the joint enablement milestone against WO-0104's *real* rails (`03-rails.md §1a`) — the seam exercises ingest wiring, not the flood bound.
- [ ] **Cockpit credential plumbing lands in the SAME change as the auth flip** (Codex PR #5 round-5 P1): `cockpit/api_client.py::_request` sends the operator credential header, so the browser client's kill-switch / manual-flatten / candidate / watchlist controls keep working the moment enforcement turns on — invariant 11 (browser-first) must never have a window where the operator is locked out of safety controls. Test: authenticated cockpit client exercises kill switch + flatten + a candidate command against the enforced backend; unauthenticated request to the same routes → 401/403. Scope note: `api_client.py` ONLY — the rest of `cockpit/**` stays forbidden here (signal UI is WO-0103).
- [ ] Producer API keys are **ingestion-scoped** (ADR-009 §Contract 1 role separation): valid for `POST /signals` only; a producer credential is rejected by every other command route (negative test).
- [ ] ~~Post-quarantine backpressure~~ — **moved to WO-0104** (REV-0024-F-004): quarantine-epoch handling (`PRODUCER_QUARANTINED`/`PRODUCER_RELEASED`, coalesced audit, post-quarantine write-free ingress) is WO-0104 behavior, not WO-0102's. This WO no longer carries it — the earlier self-contradiction (requiring epoch handling here while declaring it WO-0104's) is removed.
- [ ] ~~Interim ingest ceiling~~ — **WITHDRAWN** (REV-0024-F-004): the audit-free interim ceiling was rate-bounded, not storage-bounded (a producer paced under it still appended validation/conflict events forever). It is removed, not tuned. The no-unrailed-window guarantee is now provided **structurally** by the rails-presence startup guard above (flag un-enable-able until WO-0104's full rails wire), so an enabled endpoint never runs without finite-audit flood protection.
- [ ] Event-log truth: signals reconstructable purely from events (replay test).
- [ ] Flag off ⇒ endpoint absent/404; proven by test.

## Required tests

- [ ] Unit + integration: accept, dedupe on `(producer_id, signal_id)` incl. the cross-producer duplicate-id case, malformed→`SIGNAL_QUARANTINED`, auth-reject — dual-store. **Constructed via the fake-rails test seam** (flag-on app with the test-double rails provider, satisfying the rails-presence guard without WO-0104) — REV-0024-F P1.
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
- [ ] **Schema/DB-migration human approval RECORDED before any store-schema change** (human-gated surface; `06-invariants.md §Cross-cutting` (b) + CLAUDE.md safety core): the `SignalRecord` table/index (and the additive nullable `signal_*` columns) is **additive-only, NULL-default, no rewrite of existing rows, both stores**, and its migration plan is **stopped for explicit human approval before execution** — the WO cannot close without that approval recorded. Likewise the `ExecutionEventType` additions: if the implementer judges they cross the event-log-truth human-gated surface, **escalate, do not self-decide** (Notes below).
- [ ] **Independent CODE review gate cleared before closeout** (this WO touches human-gated surfaces — transport/auth boundary, event-log vocabulary, schema migration): a review packet is queued and dispositioned ACCEPT / ACCEPT-WITH-CHANGES before the work is relied on for a beta milestone. Completion cannot bypass this gate.

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
