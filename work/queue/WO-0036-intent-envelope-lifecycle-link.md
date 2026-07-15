---
type: Work Order
title: Link the SellIntent↔Envelope lifecycle + terminal-cancel convergence (treadmill roots R2 + R6)
status: DRAFT — HUMAN APPROVAL REQUIRED (order-intent lifecycle + session-close truth + cancel surface)
work_order_id: WO-0036
wave: W3 root-cause follow-up (quarantine-treadmill audit, 2026-07-15)
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-15
gated_surface: order-intent lifecycle, session-close event truth, cancel/replace
---

# Work Order: close the two structural roots the audit confirmed as gated

## R2 — the SellIntent↔Envelope lifecycle is UNLINKED (root of the P0)

**Root (verified by two independent audit lenses + the implementer):** no envelope
operation ever advances its backing SellIntent — the only `ORDERED` writer is the
legacy `create_order_for_sell_intent` path. An envelope-backed intent therefore sits
`APPROVED` for the mandate's whole life; `plan_close_session` blindly expires every
PENDING/APPROVED intent with zero envelope awareness (core.py `sell_intent_events`),
orphaning a still-ACTIVE envelope. The WO-0032 per-symbol guard correctly blocks the
double-mandate consequence but is a BACKSTOP: the orphan itself remains — an ACTIVE
envelope whose intent is EXPIRED. Coverage continues (the orphan keeps working its
exit) but its mandate parameters go stale vs any Day-2 re-trigger, its
`sell_intent_is_active` view is incoherent, and every session boundary mints more
lifecycle-mismatch traffic (redrive `envelope_state` refusals, dedup edge cases).

**Fix options (Ameen picks; both dual-store + evented):**
1. **[Recommended] Both ends.** (a) `approve_envelope_activation` transitions the
   backing intent `APPROVED → ORDERED` (the envelope IS the dispatch — the store
   already has `_transition_sell_intent_*`); (b) `plan_close_session` SPARES an
   intent whose envelope is non-terminal (or equivalently: only expires intents
   with no live envelope). Result: no orphan is ever created; the intent lifecycle
   is truthful; `close_session` semantics change is evented + documented.
2. **Close-side only.** Spare envelope-backed intents at close; intent stays
   APPROVED-forever (lifecycle still untruthful, but no orphan).
3. **Freeze-orphan.** At close, freeze (evented `orphaned_at_session_close`) any
   ACTIVE envelope whose intent is being expired — human re-arms next day.

## R6 — terminal-state write then ONE best-effort cancel, never reconciled

**Root (verified):** `_run_envelopes` lists ACTIVE envelopes only; the
EXPIRED/CANCEL_AND_RETURN and StaleDataSignal/CANCEL paths write the terminal state
first, then attempt the venue cancel ONCE (`_cancel_envelope_working_order`,
monitoring.py — exactly two call sites, no retry arm anywhere). A failed/crashed
cancel strands a live protective LIMIT resting at the venue under a terminal
envelope — which a DIFFERENT defense later has to quarantine (self-inflicted
treadmill traffic; SPEC-06's "stuck protective LIMIT can rest forever").

**Fix:** a reconcile-driven convergence arm — scan non-ACTIVE envelopes whose
working order is still live-at-venue and re-drive the cancel to convergence
(bounded retries → recovery ledger escalation, mirroring the submit-recovery
loop's shape). Cancel is a gated surface → this WO.

## Independent confirmation + 2 new P1s — Codex PR #8 review (2026-07-15)

The GitHub Codex bot reviewed PR #8 (8 inline findings, commit ac73ad5). SIX
independently confirm this WO's roots or already-tracked items; TWO are genuinely
new P1s (verified against tip by the implementer) and are ADDED to this WO's scope.

Confirms R2 (intent↔envelope unlinked):
- **P1 #4** (`memory.py` flatten preemption): flatten cancels only CREATED envelope
  orders; the submitted child isn't on `SellIntent.order_id`, so `flatten_position`
  skips its live-protection deferral → fresh manual-flatten sell double-books a live
  envelope child. Closed by R2's order-linkage.
- **P1 #8** (`sqlite.py` approve): `approve_envelope_activation` never loads the
  referenced `SellIntent`, so a mismatched/typo `sell_intent_id`/`symbol` mints an
  ACTIVE mandate with no real owner. R2's "activation transitions the backing intent"
  requires loading it → add existence + symbol-match validation there.

Confirms R6 (terminal-then-best-effort cancel):
- **P1 #3** (`monitoring.py` expiry): CANCEL_AND_RETURN marks EXPIRED then one
  best-effort cancel; a transient BrokerError strands the live sell forever.
- **P1 #5** (`store_backed.py` cancel_envelope): FROZEN→CANCELLED is store-only, no
  broker cancel — a kill-switch-frozen envelope with a live child stops being
  monitored while its venue order works. Add "reject/wind-down live child" to R6.

NEW — added to this WO's scope (both verified real at tip):
- **P1 #1 — generic submit sweep double-submits released envelope orders**
  (`_submit_pending_orders`, monitoring.py). It claims EVERY `CREATED` order with no
  envelope exclusion. An envelope reprice released to CREATED (transient BrokerError
  after `replace_order`, or crash before redrive) is then generically `submit_order`'d
  in the SAME tick — a NEW independent order while the predecessor is still live →
  double sell exposure, bypassing the atomic-replace/redrive path. FIX: exclude
  envelope-minted orders from the generic sweep (they are driven ONLY by the envelope
  executor's redrive). Verify via `_envelope_id_for_order` / the ENVELOPE_ACTION event.
- **P1 #6 — working-order predicate misses a live predecessor** (`_live_working_order_id`,
  policy.py). It tracks only `working[-1]`; when a reprice replacement B is REJECTED
  without cancelling predecessor A, the newest order is terminal → predicate returns
  None → policy plans a fresh SUBMIT → write-time sees A live → STAGE_REFUSED_STALE →
  the envelope can neither reprice nor manage the still-working A. FIX: the predicate
  must return the newest order whose lifecycle is non-terminal, scanning back past a
  dead replacement to a still-live predecessor.

Also noted (tracked elsewhere, not this WO):
- **P2 #2** (`now=now` on the BREACHED/EXHAUSTED/EXPIRED/FROZEN transition calls in
  `_run_one_envelope`) — the mechanical tick-side tail explicitly deferred in WO-0035
  F1 (the store root is closed). Non-gated determinism; fold in here or a fast follow.
- **P2 #7** (inferred-fill bridge provenance): `record_envelope_fill` at monitoring.py
  ~2192 omits `source=RECONCILIATION, authority=SYNTHETIC`, so the record-first FILL
  event mis-stamps a synthetic inferred fill as BROKER_AUTHORITATIVE. Small event-log
  -truth fix — pass the reconciliation source/authority into the bridge.

## Allowed paths (on approval)
```yaml
allowed_paths: [app/store/core.py, app/store/memory.py, app/store/sqlite.py, app/monitoring.py, app/reconciliation.py, app/sellside/policy.py, app/facade/store_backed.py, tests/**, docs/INVARIANTS.md, docs/adr/ADR-010-execution-envelope.md]
```

## Done-when
- [ ] No session boundary can orphan an envelope (chosen option pinned across the
      store matrix; the WO-0032 pin extended to assert the intent's post-close state).
- [ ] `sell_intent_is_active` and the envelope lifecycle agree at every point of an
      envelope-backed exit's life (pinned).
- [ ] A failed disposition-cancel converges (chaos test: cancel fails N times →
      retried → escalates to recovery ledger; never silently stranded).
- [ ] ADR-010 amendment recording the intent-lifecycle semantics ships WITH the code;
      independent review queued (gated surfaces).
- [ ] NEW #1: envelope-minted orders are excluded from the generic submit sweep
      (pinned: a released envelope reprice is NOT independently submit_order'd; only
      the envelope executor drives it).
- [ ] NEW #6: `_live_working_order_id` returns a still-live predecessor when the
      newest replacement is terminal (pinned; reprice-rejected-predecessor-live).
- [ ] #7 provenance + #2 now=now folded in or explicitly split to a fast-follow WO.
