# Spine v2 — Wave 3e Plan: Manual flatten under `Halted`/`Reducing` + emergency reduce override (ADR-003)

Accepted-design scaffold for Phase 3 wave 3e. Mirrors the wave-3c/3d template:
**record the safety-critical conflicts before coding**, migrate exactly the *facts*
named by ADR-003, keep the read-model rows co-written, and defer Phase-4
responsibilities explicitly. Migrates `docs/MIGRATION_MATRIX.md` rows **"Manual
flatten"** (`legacy_truth → event_truth`) and **"Emergency reduce override"**
(`blocked → event_truth`). Migrates the Flow-1 characterization
(`tests/test_spine_v2_characterization.py::TestCharacterizeManualFlatten`).

> **This wave carries a DECISION GAP (E1) that a human must rule on before the
> behavior-flip slices (3–4) are coded.** The scaffolding slices (1–2) are
> behavior-preserving and can proceed; the flip is gated.

---

## 1. Summary — current vs target behavior (file:line citations)

### Current ("manual flatten always works", D-P2)

- **Route** `POST /api/positions/{symbol}/flatten` — `app/api/routes_trading.py`.
  Docstring: "an operator-commanded full exit that **always works**: it bypasses the
  kill switch, buys-paused, and a closed session." Checks `position.quantity <= 0` →
  409, calls `cancel_open_buys` (a monitoring helper, direct), then
  `store.flatten_position(key)`.
- **Store** `flatten_position` — `app/store/memory.py`, `app/store/sqlite.py`.
  Delegates to pure `plan_flatten_position` (`app/store/core.py`), which on
  `SUPERSEDE_AND_CREATE` inserts a `MANUAL_FLATTEN` `SellIntent`, auto-approves it, and
  dispatches a MARKET order via `_dispatch_order_for_sell_intent` — sizing off the live
  event-log-derived position.
- **The bypass** — `app/store/core.py` `_claim_hold_reason`. The `MANUAL_FLATTEN`
  branch returns `None` **unconditionally**: "never held: a human-commanded flatten
  always exits, even kill-switched / buys-paused / closed / unknown-session (D-P2)." A
  `PROTECTION_FLOOR` sell bypasses pause/close but is held by the kill switch (`HALTED`).
- **Submit path** consuming the gate — `app/monitoring.py` `_submit_pending_orders` →
  `store.claim_order_for_submission` → `plan_claim_order_for_submission` with
  `sell_reason=MANUAL_FLATTEN`.
- **Reason model** `SellReason.MANUAL_FLATTEN` — `app/models.py`.
- **Legacy doc** encoding (A) — `docs/01_ARCHITECTURE.md` (Rule 8 / D-P2), and the
  flatten route "always works (D-P2)".
- **TradingState (wave 3d, post-review)** — `app/models.py`. `trading_state` is an
  **independent** co-written read-model (NOT a pure derivation of the booleans — the
  slice-5 validator was reviewed out); enforcement predicates read the FSM field
  (`HALTED` blocks; `monitoring` pauses protection when `trading_state is HALTED`).

### Target (ADR-003 / Addendum Decision 3 / CLAUDE.md §4.3)

- Manual flatten **allowed in `Reducing`** (reduce-only, quantity-capped,
  reconciled-position basis).
- Manual flatten **denied by default in `Halted`**; cancels + reconciliation stay
  allowed in `Halted`.
- Exit-while-halted only via an **explicit audited emergency reduce override** that
  transitions to *scoped* `Reducing`, routes through the normal reduce-only
  primary/spawn execution path, and returns to `Halted` by default after resolution.

---

## 2. Numbered conflicts (CLAUDE.md §1 conflict rule — kill switch + order submission + state mutation)

### E1 — Manual flatten under `Halted` (HEAD-ON, safety-critical) — DECISION GAP

- **(A) Legacy invariant.** `docs/01_ARCHITECTURE.md` Rule 8 / D-P2: manual flatten is
  *always allowed even while kill-switched*. Enforced in `_claim_hold_reason` (returns
  `None` unconditionally for `MANUAL_FLATTEN`). Pinned by characterization + claim-gate
  tests.
- **(B) ADR-003 / Decision 3 target.** Denied by default in `Halted`; only the audited
  emergency-reduce override exits while halted.
- **Supersede vs reconcile.** The Addendum "Binding effect" and CLAUDE.md §4.3 make the
  ADR-003 behavior **binding for migrated flows**; ADR-003's Context names the current
  global bypass as the exact thing it changes. Read together, ADR-003 **supersedes D-P2
  for this migrated flow** but is a *refinement*: D-P2 was written pre-FSM when
  "kill-switched" was the only stop state; ADR-003 keeps flatten allowed in `Reducing`
  (D-P2's spirit — a human getting out is never blocked by a control meant to stop *new*
  intent) and only tightens the stricter `Halted` all-stop.
- **Risk of each resolution.**
  - **(A)-preserved:** operator can always dump risk in one click, but the kill switch
    is **not a true all-stop** — a confused/compromised cockpit can still push exit
    orders while "halted", the hole ADR-003 closes.
  - **(B)-adopted:** a halted operator must take one extra audited step to exit, which
    under stress **could delay an emergency exit** if the override UX is slow.
- **Status:** RECORDED, not resolved. See §5.

### E2 — Emergency reduce override is a NEW command + event flow (matrix: `blocked`)

`ExecutionEventType` currently reserves `TRADING_STATE_CHANGED` + `QUARANTINED` +
`TIMEOUT_QUARANTINE` but has **no** override vocabulary. Add
`EMERGENCY_REDUCE_OVERRIDE` (grant), resolution modeled by a paired resolution event or
by folding the linked order's terminal lifecycle. Facade methods `create_exit` and
`emergency_reduce_override` are already declared (`app/facade/commands.py`) but raise
`NotYetImplementedError` (`app/facade/store_backed.py`).

### E3 — "Scoped `Reducing` that returns to `Halted`" — the central design decision

`trading_state` is authoritative but today `HALTED` dominates. ADR-003's "scoped
Reducing" must NOT be a global `HALTED → REDUCING → HALTED` flip:
- **(a) Recommended — a separate, audited, narrowly-scoped override grant** (its own
  `EMERGENCY_REDUCE_OVERRIDE` event, scoped to `{session_id, symbol}`,
  single-use/consumed-on-resolution), consulted by the claim gate *in addition to*
  `trading_state`. The **global state stays `HALTED`** throughout, so "returns to
  `Halted` by default" is trivially true (grant consumed/expires; global state never
  mutated), and the override does **not** globally re-enable autonomous
  `PROTECTION_FLOOR` exits — it is scoped to the operator's one exit. Matches ADR-003's
  "scoped" + "explicit".
- **(b) Rejected — flip global `trading_state`.** Unsafe: a global `REDUCING` re-enables
  autonomous protection exits + reduce-only flow for *every* symbol.

### E4 — Quantity-cap / reconciled-position basis (Phase-4 dependency)

ADR-003 wants the exit "quantity-capped, based on **reconciled broker position**." No
reconciliation engine exists yet (Phase 4). Current flatten sizes off the
event-log-derived position (wave 3a-truth) — the best available basis. Wave 3e caps at
that derived quantity and records the cap; the reconciled-broker-position basis is
deferred to Phase 4 (recorded conflict, mirror of 3c C6).

### E5 — Auth / actor-audit for the override (ADR-005)

ADR-005 required tests include "command endpoints require auth/actor audit." No auth
system exists (`store_backed.py` `UNAUTHENTICATED_ACTOR`). The override is the most
sensitive command in the repo. Wave 3e stamps an `actor` into the override's audit +
`ExecutionEvent` payload (minimum viable audit); a real shared-token/JWT gate stays on
the Matrix's own auth row.

### E6 — Facade boundary for the flatten command (ADR-005)

The flatten route currently mutates the store directly **and** calls a monitoring
helper directly (`cancel_open_buys`) — an ADR-005 violation. Wave 3e migrates flatten
behind `ExecutionCommandFacade.create_exit` and the override behind
`emergency_reduce_override`, moving the `cancel_open_buys` step behind the facade.

### E7 — `event_truth` scope (mirror of 3c-C5 / 3d-D1)

The *facts* wave 3e flips to `event_truth` are: (i) the **allow/deny-flatten decision**
(already routed through the `event_truth` `trading_state` from 3d) and (ii) the
**emergency-reduce-override grant/consume** (new event + projector). The
`MANUAL_FLATTEN` **order/sell-intent rows stay legacy read-models** — the order/spawn
projector is Phase 4.

### E8 — Ambiguous active spawn blocks emergency flatten (INV-3)

ADR-003 required test: "ambiguous active spawn blocks emergency flatten." Add a gate: if
the symbol has an active `TIMEOUT_QUARANTINE` order (`list_timeout_quarantined_orders`),
the emergency reduce is **blocked** (INV-3 — no exit while a possibly-live spawn is
unresolved). (`UNKNOWN_RECONCILE_REQUIRED` has no status yet — Phase 4; 3e keys only on
`TIMEOUT_QUARANTINE`.)

---

## 3. Implementation slices (each gated: suite + coverage + parity + harness)

**Slice 0 — Resolve E1 (human ruling).** No code. See §5. Slices 3–4 blocked on this;
1–2 are not.

**Slice 1 — Inert scaffolding** (additive; nothing routes to it; corpus stays green).
- `ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE`, schema-only (like the 3c/3d
  reservations).
- Pure projector `active_emergency_reduce_overrides(events, session_id)` in
  `app/events/projectors.py` — latest-wins grant/consume fold, session-scoped, same
  shape as `current_trading_state`.
- A core planner `plan_grant_emergency_reduce_override(...)` in `app/store/core.py`
  (sibling to `trading_state_change_event`) + store method
  `grant_emergency_reduce_override(symbol, *, actor, reason)` on both stores (atomic
  evented write) + `list_emergency_reduce_overrides()` query on
  `base.py`/`memory.py`/`sqlite.py`.
- Tests: pure projector unit tests; dual-store parity; replay-stable. **No behavior
  wired.** (NOT gated on E1 in shape, but only *worth building* if E1 ≠ "keep D-P2" —
  hold until the ruling to avoid dead scaffolding.)

**Slice 2 — Facade migration of manual flatten** (behavior-preserving, ADR-005 / E6).
- Implement `StoreBackedCommandFacade.create_exit` wrapping today's `flatten_position`
  **exactly** (including the `cancel_open_buys` pre-step, now behind the facade). Route
  calls the facade; thread `actor=UNAUTHENTICATED_ACTOR` (E5 placeholder).
- Behavior byte-identical; equivalence test. Full corpus green (Flow-1 still asserts the
  *old* behavior — unchanged until Slice 3). *Safe in ALL E1 options — but note slices
  3–4 re-touch the same flatten path, so consider doing 2–4 as one coherent unit after
  the ruling to avoid churn.*

**Slice 3 — Deny ordinary manual flatten under `Halted`** (THE behavior change; gated on
E1 = B).
- Thread `trading_state` (+ override set) into the `MANUAL_FLATTEN` branch of
  `_claim_hold_reason`: allowed in `ACTIVE`/`REDUCING`; in `HALTED`, denied **unless** a
  matching active override exists for `{session, symbol}`. Greppable reason string
  (proposed `trading_halted`).
- Also gate at *creation* in `plan_flatten_position` so a denied flatten returns a clean
  domain error (facade → 409) instead of a stranded `CREATED`-but-held order. Pass
  `trading_state` + override set into the planner (same pattern as `sell_reason` /
  `quarantined` in `plan_claim_order_for_submission`).
- **Migrate the pinning tests** (they must consciously break): `TestCharacterizeManualFlatten`
  and `test_manual_flatten_claims_under_kill_switch`. Under-buys-paused / after-close
  flatten tests stay green (`REDUCING`/closed ≠ `HALTED`).

**Slice 4 — Emergency reduce override command** (exit-while-halted; gated on E1 = B).
- Implement `emergency_reduce_override` + route (proposed
  `POST /api/positions/{symbol}/emergency-reduce`): actor-audited, first-writes the
  `EMERGENCY_REDUCE_OVERRIDE` grant event (Slice 1), **then** routes through the SAME
  reduce-only `create_exit` path — which now sees the grant and permits the claim +
  submit while global `trading_state` stays `HALTED`.
- INV-3 gate (E8): block the override if the symbol has an active `TIMEOUT_QUARANTINE`
  order.
- Consume/expire the grant on resolution (linked order terminal) → "returns to `Halted`
  by default."

**Slice 5 — Characterization migration + docs + review.**
- Matrix rows: "Manual flatten" `legacy_truth → event_truth`; "Emergency reduce
  override" `blocked → event_truth`, with the E7 scope note.
- Update `docs/01_ARCHITECTURE.md` Rule 8 / D-P2 to record ADR-003 supersession for the
  migrated flow (annotate, don't delete — CLAUDE.md §9). Update `docs/INVARIANTS.md` /
  ADR-003 status note.
- New `tests/test_spine_phase3e_manual_flatten.py` (mirror the 3d test module). Then
  stop for independent adversarial review (CLAUDE.md §11).

---

## 4. ADR-003 required-tests checklist → coverage

| ADR-003 required test | Satisfied by |
|---|---|
| `Reducing` allows reduce-only manual flatten | Slice 3: flatten under `REDUCING` still creates + claims + submits; INV-7 "sell crossing to short still rejected" stays green. |
| `Halted` denies ordinary manual flatten | Slice 3: kill on → `create_exit` returns denied (409), **no order created**, denial audited; migrated `TestCharacterizeManualFlatten`. |
| `Halted` allows cancels/reconciliation | Slice 3 regression: `POST /orders/{id}/cancel` still works under `HALTED`; timeout-quarantine resolution + fill ingestion still run. |
| emergency reduce transitions through scoped `Reducing` | Slice 4: override grant → flatten claims + submits while global `trading_state` stays `HALTED`; recorded as `EMERGENCY_REDUCE_OVERRIDE`; consumed on resolution. |
| ambiguous active spawn blocks emergency flatten | Slice 4 (E8/INV-3): symbol with a `TIMEOUT_QUARANTINE` order → override/flatten blocked. |
| replay reproduces the lifecycle | Slices 1+4: replay of `TRADING_STATE_CHANGED` + `EMERGENCY_REDUCE_OVERRIDE` events reproduces the allow/deny decision; dual-store parity + replay verifier extension. |

Plus ADR-005 coverage (E5/E6): command endpoints stamp an actor; flatten + override go
through the facade; engine-not-ready → 503.

---

## 5. DECISION GAP — needs human ruling (E1, with recommended default)

**The question:** In `Halted` (kill switch engaged), should an *ordinary* manual flatten
still submit an exit order?

- **Option B — adopt ADR-003 (RECOMMENDED DEFAULT).** Deny ordinary flatten in `Halted`;
  the operator exits via one explicit **audited** emergency-reduce override (scoped grant,
  routes through the reduce-only path, global state stays `Halted`). Cancels +
  reconciliation stay allowed in `Halted`. *Rationale:* ADR-003 is Accepted and binding
  per CLAUDE.md §4.3 + the Addendum; it refines rather than flatly contradicts D-P2
  (flatten stays allowed in `Reducing`, only `Halted` tightens). *Ship condition:* do
  **not** merge Slice 3 (denial) without Slice 4 (override) in the same wave, so the
  operator is never left unable to exit.
- **Option A — keep D-P2 (status quo).** Manual flatten remains an unconditional bypass;
  mark ADR-003 amended/deferred and keep the pinning tests. *Risk:* the kill switch is
  not a true all-stop.
- **Option C — audited-but-automatic (compromise).** Keep "flatten always exits", but a
  flatten issued while `Halted` *implicitly emits* the `EMERGENCY_REDUCE_OVERRIDE` audit
  event and proceeds. Preserves one-click exit + audit trail; diverges from ADR-003's
  "explicit separate step" → needs an ADR-003 amendment.

**Why a human ruling (not silently resolved):** it changes the kill switch's meaning,
order submission, and state mutation simultaneously — the exact trigger in CLAUDE.md
§1.4 — and reverses D-P2, a previously reviewed operator-facing decision. Recommend
confirming **Option B, override shipped atomically with the denial**, before Slices 3–4.
