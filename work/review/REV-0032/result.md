---
type: Review Result
rev_id: REV-0032
status: COMPLETE
reviewer: Codex
reviewed_range: ba6be70..194343c
reviewed_at: 2026-07-19
verdict: BLOCK
---

# REV-0032 result — WO-0112

## Findings

### P1 — exit preemption is not durable for candidates created after the exit opens

- **Evidence:** candidate creation remains available beside a working exit
  (`app/store/memory.py:592-638`, `app/store/sqlite.py:1300-1347`). Dispatch is only
  temporarily refused while the SELL is non-terminal (`app/store/memory.py:3209-3223`,
  `app/store/sqlite.py:4618-4630`); the candidate is not terminally stood down.
- **Concrete failing sequence:** open a protection exit, then create/approve a new same-symbol BUY
  candidate. Dispatch is blocked while the exit works. Fill the exit to flat, retry dispatch/claim,
  then fill the BUY. Both stores observed:

  ```text
  dispatch-blocked-while-exit=True; flat=0;
  dispatch-after-exit=created; claim=claimed; regrown=20
  ```

- **Why it matters:** the stand-down is a one-time scan, not an exit-preemption epoch. A BUY intent
  born during that epoch revives after the exit and re-grows the just-closed position.
- **Resolution:** refuse or terminally stand down candidates proposed while a same-symbol exit may
  execute, and expire rather than park a candidate whose dispatch meets that exit rail. Pin creation,
  dispatch, and the post-terminal retry on both stores.

### P1 — `filled_quantity == 0` spares a still-claimable CREATED BUY

- **Evidence:** the new filters skip a projected CREATED BUY once `filled_quantity != 0`
  (`app/store/memory.py:2803-2810`, `app/store/sqlite.py:4126-4134`), but submission claim checks
  status rather than remaining/fill quantity (`app/store/core.py:2506-2529`). The stated
  establishing-stub rationale is also inverted: `append_fill` does not update the order scalar, so
  the ordinary append-filled stub still has `filled_quantity == 0` and is canceled anyway.
- **Concrete failing sequence:** hold 100 shares; give a 40-share CREATED BUY a broker fill fact and
  same-status `filled_quantity=10`; open/fill a 110-share exit to flat; claim the spared BUY; append
  its remaining 30-share fill. Both stores observed:

  ```text
  after_stage=created filled_quantity=10 post_exit=0
  claim=claimed post_late_fill=30
  ```

- **Why it matters:** the spared order has future executable quantity and can re-grow the position.
  Cancellation would preserve its fill facts and the derived position.
- **Resolution:** cancel every recovery-free, projected CREATED same-symbol BUY regardless of
  `filled_quantity`; do not make claimability depend on an accidental scalar value.

### P1 — the new local cancel ignores recovery truth

- **Evidence:** the stand-down helpers filter only order projection/status/fill quantity, while the
  exposure helpers separately treat any `RECOVERY_OPEN_STATUSES` record by declared or referenced
  order scope as potentially live (`app/store/memory.py:2713-2725`,
  `app/store/sqlite.py:4046-4056`).
- **Concrete failing sequence:** create a same-symbol CREATED BUY and a public-API unresolved submit
  recovery for it, then stage an envelope exit. Both stores changed the local order to `CANCELED`
  while the recovery remained `unresolved`. The final SELL claim still blocked on the recovery.
- **Why it matters:** the code comment's "CREATED means never venue-submitted / pure local truth"
  premise is false when durable recovery truth says the referenced order may be live. The remaining
  claim rail prevents an immediate cross, but the order row is falsely terminalized.
- **Resolution:** exclude every order referenced by an open recovery from local CREATED cleanup and
  leave it to recovery/claim rails until broker-authoritative resolution.

### P1 — envelope stage can persist a stale-sized SELL beside a venue-uncertain BUY

- **Evidence:** `stage_envelope_action` proceeds from session/lineage validation to plan and mint
  without the protection path's new `MAY_EXECUTE` BUY guard
  (`app/store/memory.py:1982-2038`, `app/store/sqlite.py:3255-3313` versus
  `app/store/memory.py:2414-2438`, `app/store/sqlite.py:3759-3783`).
- **Concrete failing sequence:** hold 100 shares with a same-symbol 40-share BUY in `SUBMITTING`;
  stage an envelope SELL for 100; its claim blocks while the BUY is open; let the BUY fill/terminate;
  claim and fill the stale SELL. Both stores observed an envelope `COMPLETED` at remaining zero while
  the position remained 40.
- **Why it matters:** a crash or deferred redrive can retain the staged stale order; the final claim
  rail prevents simultaneous venue work but cannot correct stale sizing after the BUY becomes
  terminal.
- **Resolution:** before envelope order mint, fail/defer on the same recovery-aware
  `MAY_EXECUTE_ORDER_STATUSES` BUY exposure used by protection, so the next tick replans from the
  post-BUY position.

### P1 — SQLite prefilters raw status before applying event truth

- **Evidence:** memory scans all orders then projects (`app/store/memory.py:2803-2808`); SQLite first
  queries raw `status='created'` and only then projects (`app/store/sqlite.py:4126-4133`).
- **Concrete failing sequence:** claim then release a BUY so lifecycle events project `CREATED`, then
  inject a stale raw `SUBMITTING` column (a distinguishing co-write/crash state). Both stores read
  the order as projected `CREATED` before stage. After exit stage, memory read `CANCELED`; SQLite
  still read `CREATED`.
- **Why it matters:** event truth is authoritative and the two stores make different safety
  decisions from the same projected state.
- **Resolution:** SQLite must select all same-symbol BUY rows, project each, then filter exactly like
  memory (or use an equivalent event-truth query).

### P1 — the late-fill pin cancels the same child whose fill proves venue execution

- **Evidence:** `tests/test_wo0112_pr9_review_round3.py:218-264` uses one order as both the
  broker-authoritative late-fill source and the supposedly never-submitted CREATED child. Terminal
  cleanup cancels every projected CREATED child and does not exclude the fill's `order_id`
  (`app/store/memory.py:1863-1868,2187-2238`,
  `app/store/sqlite.py:3091-3097,3517-3575`).
- **Concrete failing sequence:** on an already-terminal envelope, record a partial broker fill for a
  locally CREATED child. The method records the fill and immediately marks that same child
  `CANCELED`, even though the fill proves it reached the venue and does not prove its remainder is
  terminal.
- **Why it matters:** a broker-authoritative partial fill cannot justify blind local terminalization.
  The test proves memory/SQLite parity, not safe cleanup.
- **Resolution:** exclude the fill-source `order_id` from local CREATED cleanup. Strengthen the
  intended parity test to use a late-filled old child plus a distinct lingering CREATED sibling;
  the source child remains fail-closed until its normal broker status/recovery path resolves it.

### P2 — terminal-fill cleanup reconciles the owner twice

- **Evidence:** `_cancel_staged_envelope_orders_*` already calls the per-order owner reconciliation
  (`app/store/memory.py:2237-2238`, `app/store/sqlite.py:3573-3574`), after which
  `record_envelope_fill` calls owner reconciliation again (`app/store/memory.py:1867-1868`,
  `app/store/sqlite.py:3095-3096`).
- **Concrete failing sequence:** instrument the owner-reconcile method during a late fill on a
  terminal envelope with a CREATED child. Both stores observed `reconcile_calls=2`, child
  `CANCELED`, and one externally visible owner transition event.
- **Why it matters:** the externally visible result is currently idempotent, but the packet's
  "never twice" claim is false and future non-idempotent work would run twice.
- **Resolution:** suppress nested reconciliation for this cleanup call and retain one explicit owner
  reconciliation after all children are processed.

### P2 — F3 drops the injected stage clock

- **Evidence:** `stage_envelope_action(now=...)` invokes the stand-down helper without that time;
  candidate cleanup reads `utcnow()` and `plan_transition_order` also stamps wall time
  (`app/store/memory.py:2033-2038,2756,2812`,
  `app/store/sqlite.py:3307-3313,4082,4135`, `app/store/core.py:2687-2692`).
- **Concrete failing sequence:** stage at injected `2026-07-15T18:00:00Z`. Both stores stamped the
  new order cancellation at July 19 wall time (`equal=False`).
- **Why it matters:** the safety mutation is not replay-deterministic and violates the work order's
  injected-clock discipline.
- **Resolution:** thread one logical timestamp through candidate/order stand-down and the shared
  order-transition planner; assert cancellation and audit time against the injected value.

## Design-choice evaluation

- **F3 targeting:** do **not** retain `filled_quantity == 0`. Cancel all recovery-free projected
  CREATED buys. Fill history and position truth survive cancellation, while the current predicate
  leaves future execution possible and does not even spare the ordinary append-filled stub it cites.
- **F1 deferral:** endorse `None` + durable `protection_open_deferred` + next-tick retry. The fresh
  dual-store probe emitted one audit, minted no intent during uncertainty, and then minted a
  correctly sized 100-share exit after broker-authoritative BUY terminality. Raising would add no
  safety and would lose the structured durable deferral outcome.

## Fresh probes and commands

```text
.\.venv\Scripts\python.exe -m pytest -q \
  tests/test_wo0111_pr9_review_round2.py \
  tests/test_wo0112_pr9_review_round3.py
.......... [100%]
exit 0

git diff --check ba6be70..194343c
exit 0
```

Packet-requested inline async probes against fresh memory and SQLite stores:

```text
F3 re-grow prevention: buy=CANCELED, post-exit claim=SKIPPED, position=0 — PASS
F1 defer/proceed: first=None, audit_events=1, reconciled BUY=CANCELED,
  second protection order quantity=100 — PASS
```

Hostile closure probes:

```text
partial CREATED re-grow (memory/sqlite): CREATED/filled=10 survived; post-exit
  claim=CLAIMED; position 0 -> 30 — FAILURE CONFIRMED
open-recovery CREATED cleanup (memory/sqlite): local=CANCELED, recovery=UNRESOLVED
event-truth selection: memory after=CANCELED, sqlite after=CREATED — PARITY FAILURE
terminal cleanup (memory/sqlite): reconcile_calls=2, owner transition events=1
candidate-after-exit (memory/sqlite): blocked while exit; post-exit claim=CLAIMED;
  position 0 -> 20 — FAILURE CONFIRMED
envelope stale-size (memory/sqlite): stage succeeded beside SUBMITTING BUY; final
  envelope=COMPLETED, residual position=40 — FAILURE CONFIRMED
```

Guard-neutering probes made the exact nominal F3 and F1 pins red on both stores and the F2 memory
pin red. `pytest` was initially unavailable on ambient `PATH`; all recorded tests use the repository
venv explicitly.

## Verdict

**BLOCK.** The three nominal fixes pass their authored pins, but the change set leaves executable
CREATED buys, non-durable candidate preemption, a stale envelope-stage twin, recovery-unaware local
cancellation, event-truth store divergence, unsafe late-fill cleanup, double reconciliation, and a
dropped injected clock. Full repository gates, performance gates, and PR CI were not run during this
packet review.
