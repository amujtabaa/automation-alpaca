---
type: Work Order
title: "Signal rails: TTL, staleness, rate limits, producer quarantine"
status: ready   # UNFROZEN 2026-07-14 (ADR-009 accepted); sequence-gated — start after WO-0102 completes
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

> **UNFROZEN — ADR-009 ACCEPTED 2026-07-14; sequence-gated: START AFTER WO-0102 completes** (then ∥ WO-0103). REV-0022/0024/0025 hardened the design; the spec is LOCKED. NOTE F-003/F-004 land here: server-max-TTL/expiry formula, per-epoch audit bound, **and the non-refilling invalid/conflict budget (REV-0024-F-004)** are ADR text, not WO discretion. The producer **release** route is human-gated (Complex). **This WO owns the #2 atomic-epoch-open decision (implement + test in code).**
> **This WO co-gates live enablement with WO-0102 + WO-0103** (ADR-009 A-4): it wires the full rails (rate bucket + non-refilling invalid budget + quarantine epoch + human release) and **satisfies the permanent rails-presence startup guard** (never deletes it — REV-0025-F-005), with the production entrypoint proven to construct the real provider. The flag also needs WO-0103's atomic conversion path present (an enabled seat that can't atomically convert re-opens F-002), enforced as a **release/deployment gate + joint conversion oracle** (Ameen D-2), not a new runtime check — so all three co-gate enablement. The flag-on integration suite (route-authorization matrix + conversion oracle + paced-flood) runs green here. Runs after 0102; may run in parallel with 0103. The producer **release** route is a human-gated action — same Complex treatment as WO-0103.

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
  - app/config.py                    # server_max_ttl / rate-limit / signal_invalid_budget_per_epoch Settings (A-3/A-4 tunables + hard caps) — Codex rev-3, REV-0024
  - app/main.py                      # SATISFY the permanent rails-presence startup guard by wiring the real provider (A-4; not delete it — REV-0025-F-005); prove the production entrypoint constructs the real provider
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
- [ ] Rate-limit breach → all subsequent signals from that producer quarantined until an explicit human release event (test). **The refilling bucket debits EVERY authenticated ingest** — valid, invalid, or duplicate — evaluated at rails-check time **before body parse** (no "otherwise-valid" qualifier; REV-0024-F-004). The bucket bounds *throughput*, not *storage*.
- [ ] **Non-refilling invalid/conflict budget** (ADR-009 A-4; REV-0024-F-002/F-004 — the storage bound the refilling bucket cannot provide): `signal_invalid_budget_per_epoch` (default 50; **tunable within `[1, 1000]`, 1000 a hard architectural cap — startup fails fast outside the range**, REV-0024-F P2) debited by **every attributable terminal-at-ingest append** — validation `SIGNAL_QUARANTINED`, each novel-hash `SIGNAL_DUPLICATE_CONFLICT` (same-hash replays already coalesced, `01-schema.md §3`), **and each dead-on-arrival `SIGNAL_EXPIRED`** (`expires_at ≤ received_at` / skew-based `issued_at_future`/`issued_at_stale`, `02-lifecycle.md §3`; REV-0024-F P1 — else a producer dodges the budget with unique just-expired proposals); does **not** refill while un-quarantined; **the check-reserve-debit is atomic with the terminal event append** — one memory lock / one SQLite transaction, so a step-2 pass does not pre-grant a slot and concurrent/slow-body requests cannot append past the cap (REV-0025-F-003); **exact final-slot transition — the exhausting append opens the epoch in the SAME atomic op** (Ameen 2026-07-14, REV-0025-F P1; supersedes the earlier "next ingest opens the epoch"): the append that consumes the last slot co-appends its own terminal event AND the one `PRODUCER_QUARANTINED` in one op, so there is **no zero-budget-but-un-quarantined gap** (an exhausted producer's RECEIVED signals must not stay approvable); still exactly one `PRODUCER_QUARANTINED` per epoch, subsequent rejects write-free; **each attributable-rejection event carries `cycle_budget_limit`** so the budget is reconstructable from the event log alone (REV-0025-F P1); **both the pinned limit AND consumed/remaining count are replay-reconstructable + durable, restored before serving**, so a restart cannot zero the consumed count (REV-0025-F-004); **resets only on human release**. Tests (both stores): (a) pace invalid, novel-conflict, **and dead-on-arrival-expiry** at/below the refill rate over many windows → **constant event-row ceiling** + quarantine-on-exhaustion; (b) **final-slot race** — N concurrent requests with one slot left → exactly one terminal append **co-opening one `PRODUCER_QUARANTINED`**, no approve-during-gap; (c) **delayed/slow-streamed body** admitted at step 2 cannot append after exhaustion; (d) **crash-injection** between debit and append leaves neither; (e) **restart/replay** with 49/50 consumed under raised AND lowered config → consumed count + `cycle_budget_limit` survive from the log, exactly one final append allowed; after release the new config starts the next cycle; (f) **duplicate epoch-open/release** idempotent.
- [ ] Post-quarantine backpressure per ADR-009 **Amendment A-4**: epoch-bounded audit (ONE PRODUCER_QUARANTINED per epoch — opened by **rate-bucket breach OR invalid/conflict-budget exhaustion**; nothing appended post-quarantine; saturating out-of-log counter; count carried on PRODUCER_RELEASED) — model-based flood test asserts CONSTANT event-row count under sustained hostility, both stores.
- [ ] **Wire the full rails and SATISFY the permanent rails-presence startup guard** (ADR-009 A-4; the enablement point; REV-0025-F-005): the guard is a **standing invariant, never deleted** — once the rate bucket + non-refilling invalid budget + quarantine epoch + human release are wired, startup passes it with `signal_seat_enabled` on. **Prove the production entrypoint constructs the REAL provider** (a Protocol-presence check can't tell it from a permissive fake) and that **fakes are confined to a test-only construction path production config/environment cannot select**. This change satisfies the **rails** half of the gate; **live enablement additionally requires WO-0103's conversion capability** — so even if WO-0104 lands before WO-0103, the flag stays **deployment-gated off** until the conversion path is present and proven (Ameen D-2: a release/deployment gate, not a runtime check; REV-0025-F-005). The **flag-on integration suite runs green only at the joint milestone**: the `04-auth-and-api.md §1a` mounted-route authorization matrix (asserting required routes **exist**, not merely classifying mounted ones), the **joint conversion oracle** (ingest → operator approval → exactly one atomically-linked intent, with WO-0103), and the paced-flood constant-event-row tests. WO-0104 alone must NOT declare the flag enable-able.
- [ ] Expiry semantics per **Amendment A-3**: server-computed durable `expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)`, skew bounds, restart-stable, atomically re-checked at conversion (property tests, injected clock).
- [ ] The release route is **operator-only** (same credential split as WO-0103); a producer API key cannot release its own quarantine (negative test).
- [ ] **`PRODUCER_RELEASED` resets BOTH rails** — the §1 refilling bucket **and** the §1a non-refilling invalid/conflict budget (REV-0024-F P1): a producer quarantined by budget exhaustion, once released, must be able to ingest again **without immediate re-quarantine** — else the human release control is inert. Test asserts a released (budget-exhausted) producer's next ingest is accepted, both stores.
- [ ] **Release is reachable from the browser** (Codex PR #5 round-6 P2, invariant 11): the cockpit gains a producer-quarantine release control (on WO-0103's signal panel if it exists, else a minimal standalone control) issuing the release intent via the typed API client — the required human action must not be raw-API-only. Thin-client rules apply (no signal state owned client-side; contract 2 stays green).
- [ ] There is **no interim ingest ceiling to replace** — it was withdrawn (REV-0024-F-004). Instead, the no-unrailed-window guarantee is structural: WO-0102 ships the flag un-enable-able, and **this change wires the full rails and thereby SATISFIES the permanent rails-presence guard** (never deletes it — REV-0025-F-005), so the endpoint is never live without finite-audit flood protection.

## Required tests

- [ ] Expiry sweep emits `SIGNAL_EXPIRED`; expired signal never approvable — property-style, dual-store. **`SIGNAL_EXPIRED` carries `(producer_id, signal_id)`/`record_id`; replay with multiple RECEIVED signals expiring in one sweep transitions each independently** (REV-0024-F P1).
- [ ] Staleness/plausibility on `issued_at` (future / implausibly old → quarantine).
- [ ] Producer quarantine on rate-limit breach; release only via explicit human release event.
- [ ] **Paced-hostility flood** (REV-0024-F-002): invalid, novel-conflict, **and dead-on-arrival-expiry** requests paced at or below the refill rate over many windows → constant event-row count, quarantine opens on non-refilling-budget exhaustion — both stores.
- [ ] **Release resets both rails** (REV-0024-F P1): a budget-exhausted, then released, producer ingests again without immediate re-quarantine — both stores.
- [ ] **Budget config validation + cycle-scope** (REV-0024-F P1/P2): `signal_invalid_budget_per_epoch` outside `[1, 1000]` → startup fails fast; and a mid-cycle config change applies only to cycles beginning after it — an in-flight cycle's pinned limit is unchanged across restart/replay.
- [ ] **Budget linearizability + durability** (REV-0025-F-003/F-004): final-slot concurrency race, slow-body-after-exhaustion, crash-injection (debit⇔append atomic), and restart/replay preserving the **consumed** count (not just the limit) so no fresh budget is granted without release — per the behavior item's (b)–(f), both stores.
- [ ] **Enablement gate**: with `signal_seat_enabled` on and rails NOT wired, `create_app` startup fails the rails-presence guard; with the full rails wired, it starts — and the joint flag-on route-authorization matrix passes at the mounted app.

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
