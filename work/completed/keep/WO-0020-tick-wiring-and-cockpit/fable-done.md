# WO-0020 — fable_done

`[FABLE • FULL • verification: DIRECT • task: WO-0020]` — closed 2026-07-12, commit `4e4f4f0`. Non-gated (consumes prior WOs' gated surfaces).

## done_when → evidence

| done_when | met | evidence |
|---|---|---|
| Envelope pass after `_run_protection`, never crashes the tick | ✅ | pass wired between protection and the submit sweep (same-tick claim+submit of a staged exit); `test_policy_exception_freezes_only_that_envelope` — injected policy bug freezes AAPL's envelope (reason=policy_error), MSFT's envelope still executes its stop-exit in the SAME tick, tick returns cleanly, both stores |
| One snapshot fetch per symbol; no duplicate market-data calls | ✅ | per-pass `snap_memo` (one `get_snapshot` per symbol shared across that symbol's envelopes); protection's own fetch untouched (structural sharing across passes would need refactoring `_run_protection` internals — deferred note) |
| Cockpit renders envelopes; FROZEN/BREACHED/EXHAUSTED prominent; approval surfaces mandatory dispositions; UI intents via typed client only | ✅ | Envelope Monitor screen + `st.error` action-items for attention states (`test_frozen_and_breached_are_prominent`); approval form's two disposition selects + TTL; api_client.list/approve/cancel_envelope only |
| UI holds no envelope state | ✅ | AppTest monkeypatch of api_client is the ONLY data source; refresh re-derives (cockpit convention test) |
| Full loop: approve → tick reprices/exits within bounds → fill completes envelope, both stores | ✅ | `test_full_loop_stop_exit_fill_completes_envelope`: crash tape → stop-exit staged+claimed+SUBMITTED tick 1; venue fill ingested tick 2 → envelope remaining 0 → COMPLETED; ONE envelope-attributed FILL event; position folds exactly once |
| API: list/approve; approve without dispositions rejected end-to-end | ✅ | 422 for each missing mandatory field with zero leakage; kill-switch 409; ACTIVE-cancel 409; unknown 404; pre-activation cancel 200 |
| Full gate | ✅ | ruff check+format (212 files) ✓ · mypy 64 ✓ · lint-imports 6/0 ✓ · pytest full suite exit 0 |

## Key design records
- **Record-first fill bridge**: envelope fills apply via `record_envelope_fill` BEFORE `append_fill` with the same canonical dedupe key — one FILL event (envelope-attributed), position folds once, remaining decrements once. Fills lacking `source_fill_id` can't be bridged deterministically (no venue identity pre-row) — production Alpaca fills always carry one; logged limitation for WO-0021/0022.
- **Injectable policy clock** (`envelope_now`) on the tick — discovered necessary when the container's Saturday wall-clock made the session gate (correctly) refuse; the same discipline that keeps tests deterministic.
- Reconciliation-inferred (synthetic) fills are NOT bridged to envelopes yet — deferred-logged (rare path; WO-0021 chaos should probe it).

## Deviations
- Sell-intent → ORDERED linkage (deferred from WO-0019) remains unwired; envelope orders carry `sell_intent_id` and single-flight holds. Still deferred — needs a planning-seat decision on intent lifecycle semantics under multi-order envelopes (NEEDS-INPUT noted for the wave close-out, not blocking).
- Route/facade typing via local Protocols again (facade ABCs outside allowed paths) — third entry for the queued interface-lift WO (base.py + facade ABCs + EnvelopeTransitionError relocation).

## Status: VERIFIED
