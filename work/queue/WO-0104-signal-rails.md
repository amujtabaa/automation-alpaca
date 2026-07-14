---
type: Work Order
title: "Signal rails: TTL, staleness, rate limits, producer quarantine"
status: draft
work_order_id: WO-0104
wave: W4-signal-seat
model_tier: strong
recommended_model: opus   # defensive-security surface (auth/credentials/rate-limit/quarantine) — Fable dual-use safeguard false-positives here; see .claude/rules/repo-primer.md routing preference
risk: medium
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-11
---

# Work Order: Signal rails — TTL, staleness, rate limits, producer quarantine

> **RE-GATED (2026-07-14) — DO NOT ACTIVATE**: REV-0022's formal run returned BLOCK; gated on ADR-009 F-001..F-004 remediation + re-review acceptance, then WO-0102. NOTE F-003/F-004 land here: server-max-TTL/expiry formula and per-epoch audit bound become ADR text, not WO discretion
> and WO-0102 is complete. Runs after 0102; may run in parallel with 0103. The producer
> **release** route is a human-gated action — same Complex treatment as WO-0103.

## Goal

Implement expiry sweep (`SIGNAL_EXPIRED`), staleness/plausibility checks on `issued_at`, per-producer rate limiting with producer-level quarantine and human release action.

## Context packet

Read only these first:

- `CLAUDE.md`
- `docs/adr/ADR-009-signal-seat-boundary.md`
- `docs/spec/signal-seat/**` (TTL/staleness/rate-limit rules)
- `app/events/`, `app/store/base.py`
- `pkl/architecture/testing-model.md` (injected clock, dual-store rules)

## Allowed paths

```yaml
allowed_paths:
  - app/events/**                    # signal rails + SIGNAL_EXPIRED events
  - app/models.py
  - app/store/**
  - app/api/**                       # release route — human-gated action
  - app/facade/**                    # signal facade (release command/queries) — contract 5: the route never reaches store/events directly; commands.py stays forbidden below
  - cockpit/**                       # producer-quarantine RELEASE control only (browser-first: the required human action needs a browser path)
  - .importlinter                    # if the release route is a new module: add it to contract 5
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - cockpit/** (except the producer-quarantine release control — see allowed_paths; no other UI changes)
  - app/facade/commands.py           # order submission path stays forbidden (release is not an order intent)
```

## Required behavior

- [ ] Injected clock throughout (no bare `datetime.now()` / `time.time()`).
- [ ] Property-style tests: no ordering of signal events can yield an APPROVED state for an expired/quarantined signal.
- [ ] Rate-limit breach → all subsequent signals from that producer quarantined until an explicit human release event (test). **The bucket debits EVERY authenticated ingest** — valid, invalid, or duplicate — so validation-quarantine events are bucket-bounded (Codex rev-2; test: sustained invalid-body flood breaches the limit and the log stays bounded).
- [ ] Post-quarantine backpressure per ADR-009 **Amendment A-4**: epoch-bounded audit (ONE PRODUCER_QUARANTINED per epoch; nothing appended post-quarantine; saturating out-of-log counter; count carried on PRODUCER_RELEASED) — model-based flood test asserts CONSTANT event-row count under sustained hostility, both stores.
- [ ] Expiry semantics per **Amendment A-3**: server-computed durable `expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)`, skew bounds, restart-stable, atomically re-checked at conversion (property tests, injected clock).
- [ ] The release route is **operator-only** (same credential split as WO-0103); a producer API key cannot release its own quarantine (negative test).
- [ ] **Release is reachable from the browser** (Codex PR #5 round-6 P2, invariant 11): the cockpit gains a producer-quarantine release control (on WO-0103's signal panel if it exists, else a minimal standalone control) issuing the release intent via the typed API client — the required human action must not be raw-API-only. Thin-client rules apply (no signal state owned client-side; contract 2 stays green).
- [ ] WO-0102's interim ingest ceiling is replaced by the full rails **in this change** — never removed before them.

## Required tests

- [ ] Expiry sweep emits `SIGNAL_EXPIRED`; expired signal never approvable — property-style, dual-store.
- [ ] Staleness/plausibility on `issued_at` (future / implausibly old → quarantine).
- [ ] Producer quarantine on rate-limit breach; release only via explicit human release event.

## Required commands

```bash
pytest
ruff check .
mypy app/
lint-imports
```

## Acceptance criteria

- [ ] All required behavior implemented; tests prove behavior; evidence pasted (full CI gate green).
- [ ] Both storage paths covered.
- [ ] Scope limited to allowed paths; no forbidden paths touched.
- [ ] Fable DONE block includes evidence.
- [ ] PKL update completed or explicitly not required.

## Model-tier rationale

Strong: quarantine/rails semantics are safety rails; deterministic-clock property testing. Never LITE.

## Notes

- `allowed_paths` corrected on install from the draft's `src/engine/**`/`src/api/**` to the as-built tree; finalize against WO-0101's spec at activation.
- Bundle-wide out of scope (log, don't build): L1/L2 trust levels, any Vibe-Trading code import, reference producer shim (revisit post-beta as separate repo), backtest/data sharing with external agents.
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
