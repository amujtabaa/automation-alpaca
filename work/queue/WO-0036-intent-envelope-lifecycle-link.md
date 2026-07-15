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

## Allowed paths (on approval)
```yaml
allowed_paths: [app/store/core.py, app/store/memory.py, app/store/sqlite.py, app/monitoring.py, app/reconciliation.py, tests/**, docs/INVARIANTS.md, docs/adr/ADR-010-execution-envelope.md]
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
