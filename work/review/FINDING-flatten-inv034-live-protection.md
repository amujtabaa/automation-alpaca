# FINDING — manual-flatten can hand back a live PROTECTION_FLOOR intent (INV-034 gap)

- **Status:** OPEN — decision gap on a **human-gated safety surface** (manual flatten). NOT fixed
  autonomously; the pinning test was NOT weakened. Awaiting human direction.
- **Severity:** correctness / safety (audit + guarantee gap). Not a live-trading path (paper-only beta),
  but it violates a stated safety invariant on the flatten surface.
- **Surfaced by:** WO-0012 memory-store increment validation, 2026-07-09. Pre-existing; unrelated to the
  mypy work that surfaced it.

## What

`tests/test_lifecycle_state_machine.py::TestSqliteLifecycle` (the Hypothesis stateful machine) finds a
sequence where a human **flatten** returns an intent whose `reason` is `PROTECTION_FLOOR`, not
`MANUAL_FLATTEN`:

```
create_candidate(AAPL, qty=1) -> approve_and_dispatch -> divergent_fill_and_reconcile
protection_tick            # floor breach -> PROTECTION_FLOOR SellIntent + order, dispatched (SUBMITTED)
flatten(AAPL)              # -> FlattenResult(outcome='existing', intent.reason=PROTECTION_FLOOR)
```

The rule's inline assertion (X-001) requires every non-flat flatten to return a `MANUAL_FLATTEN` intent.

## Why it is a real conflict (not a too-strict test)

**INV-034** (`docs/INVARIANTS.md:182`) states, unconditionally:

> A human-commanded `POST /positions/{symbol}/flatten` **always returns (or creates) a
> `MANUAL_FLATTEN` intent — never silently hands back a different reason.** … the human's flatten click
> would silently receive back a `protection_floor` intent instead … while the click reads as success.

That is precisely the behavior observed. But `plan_flatten_position`
(`app/store/core.py:1021-1032`) contains an explicit carve-out:

```python
# A protection_floor exit is active. Genuinely live at the broker (an
# order exists and is no longer CREATED) -> already executing, leave it.
if (active_intent.reason is SellReason.PROTECTION_FLOOR
        and active_order is not None
        and active_order.status is not OrderStatus.CREATED):
    return FlattenPlan(FLATTEN_EXISTING, existing_intent=active_intent, existing_order=active_order)
```

The X-001 remediation "Why" says it stands down any **non-live** protection exit — the **live** case was
left returning the protection intent. So there are two irreconcilable positions on a gated surface:

- **(A) INV-034 is absolute** → this is a **latent defect**: a human flatten over a live protection
  order records no `MANUAL_FLATTEN` provenance and reads as success; if that protection order is later
  canceled/rejected (or sized below the full position), the position is silently NOT flattened. The fix
  belongs in `plan_flatten_position` (e.g. supersede/stand-down the live protection exit and mint a
  fresh `MANUAL_FLATTEN`, or explicitly re-badge) — a change to the manual-flatten surface, human-gated.
- **(B) Deferring to a live full-position protection sell is intended** → INV-034's wording is too
  strong and the pinning assertion over-reaches; the invariant + test should be amended to permit
  "an already-live protection exit satisfies the flatten." Amending a safety invariant/test is also
  human-gated (never weaken a test to make code pass).

Either way the resolution is a human decision. Recorded here per the CLAUDE.md conflict rule
("if the conflict touches a safety surface, stop and record the decision gap before coding").

## Why it appears "new"

The targeted flatten suites (`test_phase7_flatten_atomic.py`, `test_phase7_routes.py`) do **not** drive
"protection order becomes LIVE, then flatten," so they pass. Only the stateful machine explores it, and
only once Hypothesis reaches that interleaving. This container installed **Hypothesis 6.156** (see the
dependency note below); the prior environment's version/seed never generated the sequence, so the same
committed code read as green there. The defect was always present.

## Secondary issue — unpinned dependencies (build non-reproducibility)

`requirements.txt` pins with `>=` only. This fresh container resolved to Hypothesis 6.156, Starlette
1.3.1 (emitting `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings), Streamlit 1.59, pydantic 2.13.
The suite's pass/fail set is therefore a function of whatever versions resolve at install time — CI on a
fresh runner is likely to hit this same flatten failure. Options for the human: add a pinned
constraints file / lockfile, or a bounded upper pin on the test-critical libs (Hypothesis). **Do not
pin Hypothesis down merely to hide this finding** — the flatten gap is real independent of the version.

## What I did / did not do

- **Did:** verified the failure reproduces on committed `HEAD` without the WO-0012 change (git stash);
  confirmed the rest of the suite is green (1947 / 0 failures with this one deselected); committed the
  WO-0012 memory increment (orthogonal, mypy-only) with honest evidence carrying this caveat.
- **Did NOT:** modify `plan_flatten_position` or any flatten path; weaken/deselect the X-001 assertion
  in the committed tree; pin dependencies. All of those are either human-gated or require the human's
  decision between (A) and (B).

## Asks (batched, human)

1. **Direction on the flatten conflict:** (A) fix `plan_flatten_position` to honor INV-034 for the
   live-protection case, or (B) amend INV-034 + the X-001 assertion to permit deferring to a live
   protection exit. I can draft either as a work order once you choose.
2. **Dependency pinning:** approve adding a lockfile / bounded pins so CI and local runs are
   reproducible.
