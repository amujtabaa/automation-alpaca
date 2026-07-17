---
type: Work Order
title: Link the SellIntent↔Envelope lifecycle + terminal-cancel convergence (treadmill roots R2 + R6)
status: CLOSED
work_order_id: WO-0036
wave: W3 root-cause follow-up (quarantine-treadmill audit, 2026-07-15)
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT, ADR_CREATED]
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

## Implementation status (2026-07-15)

DONE — 6 of 8 findings, each RED→GREEN, dual-store, mutation-checked where applicable
(`tests/test_wo0036_execution_safety.py`), committed b174c5c (cluster 1) + cluster 2:
- #6 (P1) `_live_working_order_id` tracks a live predecessor past a dead reprice replacement.
- #1 (P1) generic submit sweep excludes envelope-minted orders (double-exposure closed).
- #2 (P2) tick threads `now=` into the 4 envelope-terminal transitions.
- #7 (P2) inferred-fill bridge carries RECONCILIATION/SYNTHETIC provenance.
- #5 (P1) `transition_envelope`→CANCELLED refuses a FROZEN envelope with a live child (both stores).
- #3 (P1, R6) `_converge_expired_envelope_cancels` tick arm re-drives an EXPIRED CANCEL_AND_RETURN
  cancel to convergence (scoped to the one terminal state carrying a cancel intent).

**[FABLE DEVIATION] #4 + #8 (the full R2 lifecycle link) DEFERRED to a dedicated pass** — not
rushed at session tail. The correct fix (approve loads + validates + transitions the backing
SellIntent APPROVED→ORDERED; close_session spares envelope-backed intents; flatten's deferral
sees the envelope child) is a genuine architectural migration: ~73 approve/create test call
sites + ~91 synthetic-`sell_intent_id` draft constructions would break (they use "si-1"-style
ids with no real intent row), and it ships with an ADR-010 amendment + independent review. A
lighter NON-breaking interim is available if wanted: #8 → reject only when a REAL intent row
exists with a MISMATCHED symbol (catches the cockpit typo, leaves synthetic-id tests green);
#4 → make `flatten_position` also defer to a live envelope working order for the symbol. Awaiting
Ameen: full R2 migration now vs the lighter interim vs schedule R2 as its own WO.

## Codex PR #8 SECOND review round (commit 15fa484) — all 7 verified REAL, dispositioned

An independent adversarial verification confirmed all 6 inline findings + the floor-precedence
P1 as REAL at tip. Dispositions (2026-07-15):

- **P1 policy.py floor precedence** — FIXED (cluster 3). A deviation-suspect below-floor latest
  print with a healthy bid drove a full-size SELL; now an explicit floor BreachSignal (root-cause
  hole in the WO-0035/INV-088 fix). Pin: `test_puremath0_deviation_band.py::
  test_suspect_below_floor_last_with_healthy_bid_still_fails_closed`.
- **F1 P1 stale-SUBMITTING redrive** — FIXED (cluster 3). Envelope-minted orders excluded from
  `_redrive_stale_submitting`'s blind submit; routed to TIMEOUT_QUARANTINE for ADR-002 targeted
  reconciliation (the venue's atomic replace keeps A/B consistent). Pin: `test_wo0036_execution_safety.py::
  test_c1b_stale_submitting_redrive_skips_envelope_orders` (both stores).
- **F2 P2 supersedes_id on fresh draft** — FIXED (cluster 4). `envelope_draft_reason` now rejects
  BOTH supersession link fields. Pin: `test_wo0016_envelope_supersede.py::
  test_fresh_draft_cannot_predeclare_supersedes_id` (both stores).
- **F3 P2 sqlite NOOP ACTIVE session bootstrap** — FIXED (cluster 4). NOOP early-returns before the
  session bootstrap (memory parity + matches its own comment). Pin (sqlite-specific, rollover-forced):
  `test_wo0036_execution_safety.py::test_c_f3_noop_active_transition_does_not_mint_a_session_on_rollover`.
- **F4 P2 quarantine pause → FROZEN** (= WO-0029 SPEC-08) — FIXED (cluster 4). The tick catches
  `EnvelopeActionPausedError` separately, leaving the envelope ACTIVE/paused. Pin:
  `test_wo0020_envelope_tick.py::test_quarantined_child_pauses_not_freezes_the_envelope` (both stores).
  WO-0029 SPEC-08 marked DONE.
- **F5 P2 replaces_used stale read-model** (= WO-0029 CC-05) — PARTIAL (cluster 4). The false
  models.py comment (claimed a writer) is corrected; the read-model/cockpit projection stays in
  WO-0029 (recommended: one shared event-log counter for BOTH enforcement + display, no second
  stored writer). WO-0029 CC-05 marked PARTIAL.
- **F6 P2 naive expires_at → TypeError freeze** (= WO-0029 SPEC-10) — FIXED (cluster 4).
  `_hard_rails` rejects a naive `expires_at`. Pin: `test_wo0016_envelope_model.py::
  test_expires_at_must_be_timezone_aware`. WO-0029 SPEC-10 marked DONE.

## R2 DESIGN — finalized after full investigation (2026-07-15)

The pre-build Fable GATE investigation (lifecycle map + the `sell_intent_is_active`
and flatten-deferral seams) changed the recommended mechanism. Key findings:

1. **The WO's "Recommended" option 1 (transition intent → ORDERED at activation) is
   flawed.** `sell_intent_is_active` (core.py:794) keys an `ORDERED` intent's
   activeness on its ONE linked order: `if order is None or order.status in
   _TERMINAL: return False`. An envelope has NO single durable order (it mints a
   sequence across reprices, with gaps). So transitioning the backing intent to
   `ORDERED` with `order_id=None` makes `sell_intent_is_active` return **False while
   the envelope is very much ACTIVE** — the incoherence the WO wanted to fix gets
   WORSE, and the legacy `create_order_for_sell_intent` idempotency guard
   ("ORDERED but has no linked order", memory.py:1548) becomes a latent trap.

2. **Migration surface is MUCH smaller than the ~73/~91 estimate:** approve is called
   from 45 sites/15 files, but only **~25 sites across 4 files** carry synthetic
   `sell_intent_id`s (`test_wo0017_envelope_approval.py` ~12, `test_wo0032` 6,
   `test_wo0017_precedence.py` 5, `test_wo0035_root_causes.py` 2). The other 11 files
   already back drafts with a real `create_sell_intent` id. `SELL_INTENT_TRANSITIONS`
   (app/transitions.py): PENDING→{APPROVED,REJECTED,EXPIRED}, APPROVED→{ORDERED,EXPIRED}.

3. **`create_sell_intent` single-flight dedup is per-symbol.** Two real same-symbol
   intents CANNOT coexist — so `test_wo0032`'s two synthetic same-symbol intents
   can't be literally migrated; the per-symbol ENVELOPE guard test is reframed (the
   intent layer now structurally blocks the second same-symbol intent; INV-087 stays
   the defense-in-depth backstop, tested directly via same-intent / hand-set draft).

**CHOSEN mechanism — "Option A+" (close-side spare + terminal propagation, NO ORDERED
overloading):**
- `approve_envelope_activation` (both stores): LOAD the backing SellIntent; validate it
  exists, its symbol matches, and it is non-terminal (PENDING/APPROVED, not ORDERED/
  terminal). Normalize PENDING→APPROVED (the envelope approval IS the human approval).
  Leave it APPROVED for the envelope's life → `sell_intent_is_active`=True (coherent,
  unchanged predicate). Closes #8 (typo/mismatch mints an owner-less mandate).
- `close_session` (both stores): exclude from `open_sell_intents` any intent backing a
  NON-terminal envelope → the P0 orphan is never minted. (Gated session-close event
  truth.)
- `transition_envelope` → a FINAL terminal state (COMPLETED/EXPIRED/EXHAUSTED/BREACHED/
  CANCELLED, NOT SUPERSEDED — the successor keeps the intent) expires the backing intent
  when no other non-terminal envelope backs it → releases the symbol for fresh
  protection (no stale-mandate lingering-APPROVED hole).
- `plan_flatten_position` / flatten (#4): defer to a LIVE envelope working order for the
  symbol (not just the intent's single `active_order`, which is None for an
  envelope-backed intent) → a manual flatten never double-books a live envelope child.

Rationale vs option 1: A+ keeps `sell_intent_is_active` coherent WITHOUT overloading
ORDERED or rippling a new param through every dedup caller; the intent lifecycle mirrors
the envelope's (in-flight while non-terminal, released at terminal). **This diverges from
the WO's stated recommendation → flagged for Ameen's ratification at the REV gate (gated
event-truth semantics; the ADR-010 amendment records the decision).**

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

---

## CLOSE-OUT (2026-07-17, CAMPAIGN-0002 Part B completion run)

Two full independent implementations were produced from this WO (charter §0a): **Claude R2**
(`claude/sellintent-envelope-linking-h2z7i7`, evented terminal propagation) and **Sol R2**
(`codex/r2-lifecycle-link-sol-impl`, delegation projection). The consolidation campaign
(CAMPAIGN-0002, WO-0105/0106 Part A; operator ratification I.1) selected **Sol's
delegation-projection mechanism as canonical** — credit for the shipped R2 core belongs to
**Sol**, whose commit carried the mechanism, the reconcile write-back, the startup re-projection,
and the hostile/assurance/parity regression corpus, but zero `work/` planning artifacts; this
close-out is the planning-plane record Sol's commit never shipped (report §C.2.5/§G.2). The
unchecked items in the list above were superseded by the consolidation's own program — their
substance landed via the campaign (masked-predecessor pins P3c; provenance P3b/§6 amendments) or
is explicitly parked (below), and the campaign report §C/§G is the authoritative disposition of
each.

**What landed on `consolidate/r2-canonical`** (evidence: `work/review/CAMPAIGN-0002-claude/`
`PARTB-COMPLETION-PLAN.md` §6 outcome log):
- Sol's projection core + reconcile write-back, ported (step 1a), then indexed/memoized as a
  precondition per ratification I.2 (steps 1b/1c), with the R6 fail-closed logging fix (I.5).
- The Part B completion run (operator ratifications D1–D9): Codex-oracle reconciliation (P1);
  the two close/retention spec properties (P2 — strict/widened/across-close predicates, P-A
  pre-activation sweep, P-B needs-review quarantine); the Claude-attempt F.2 grafts (P3 —
  spared counter, granular deferral reason, 3 ported gap pins; 23/23 dispositioned);
  perf-gate disposition (P4 — no regression this run; pre-existing marginal wall-clock misses
  named for review); governance (P5 — ADR-010 §3/§4/§6 amendments, INV-090, INV-081/037/052
  refresh).
- WO-0107 (Option B atomic flatten) closed the adjacent §5.3 stale-read class on the same trunk.
- Both spec oracles green (Codex 61/0, explicit run; Claude 22 passed + 6 recorded NEEDS-INPUT
  skips, file unmodified since Part A).

**Review lineage:** REV-0028 (the Claude-attempt packet, `AWAITING_REVIEW` on the attempt branch,
never dispositioned) is **SUPERSEDED** by **REV-0029** — the consolidated independent cross-model
packet covering the entire Part B diff (it also subsumes REV-0024/Option B, per ratification D4).
The independent-review gate for every human-gated surface this WO touched clears only on
REV-0029's ACCEPT / ACCEPT-WITH-CHANGES.

**Open by design:** PD-1 (needs-review reconciliation release valve — `BLOCKED-DECISIONS.md`);
H.1-step-7 backfill verification (deferred post-merge/pre-beta-reliance, D5); the P4 perf
follow-up WO candidate.
