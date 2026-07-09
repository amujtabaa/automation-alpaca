# FINDING — manual-flatten can hand back a live PROTECTION_FLOOR intent (INV-034 gap)

- **Status:** ADDRESSED (human-authorized 2026-07-09) — the deep-dive corrected the original framing
  (INV-036 makes deferral to a live protective order INTENTIONAL; the "cancel + re-mint" option would
  have violated it and risked a double-sell). Applied the SAFE subset: (a) provenance event on the
  deferral, (b) INV-034 + stateful-test reconciliation with INV-036. Deliberately did NOT tighten the
  predicate (see "Predicate" below — it would be a blind-cancel hazard). Two follow-ups remain
  (TIMEOUT_QUARANTINE messaging + actor threading). Still queues for **independent review** per Review
  policy (manual-flatten surface). What shipped:
  - New `manual_flatten_deferred` event (`app/models.py`) emitted by `plan_flatten_position` on the
    live-protection deferral and written by both stores in the same lock hold — closes the audit gap.
    Test: `tests/test_phase7_flatten_atomic.py::test_live_protection_floor_deferral_records_provenance`.
  - INV-034 amended to state the INV-036 carve-out explicitly (`docs/INVARIANTS.md`); the
    `test_lifecycle_state_machine.py` flatten rule now permits a PROTECTION_FLOOR deferral **only** when
    the linked order is genuinely in-flight/live (past CREATED) — which also removes the flaky failure.
  - **Predicate NOT tightened (safety):** the investigation suggested routing TIMEOUT_QUARANTINE to
    "supersede/self-heal," but that path LOCAL-CANCELS the order, which for an ambiguous/possibly-live
    order is exactly the blind-cancel ADR-002 forbids. Deferring is the safe action for every
    non-CREATED status; the real defect there is misleading *messaging*, addressed via the provenance
    event. Correctly distinguishing confirmed-live from in-flight/ambiguous on flatten (block vs.
    distinct outcome vs. re-drive) is a design decision left as a follow-up (noted in INV-034).
  - **Actor threading** (operator identity dropped on all flatten paths) remains a separate follow-up.
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

## Why it appears "new" — and why it is FLAKY, not deterministic

The targeted flatten suites (`test_phase7_flatten_atomic.py`, `test_phase7_routes.py`) do **not** drive
"protection order becomes LIVE, then flatten," so they pass. Only the stateful machine explores it, and
only once Hypothesis's random search reaches that interleaving within its example budget.

**Important correction (verified):** the failure is **flaky**, not deterministic. My earlier local runs
failed reproducibly only because Hypothesis had cached the falsifying example in `.hypothesis/examples/`
(git-ignored, per-checkout). After `rm -rf .hypothesis`, a fresh `TestSqliteLifecycle` run **passes** —
the search does not hit the interleaving every time. CI runs with no cache, so **CI passed pytest on
`f04d4ee`** (`ci.yml` run 28992127521 = success) once the mypy blocker below was fixed. So:

- The mypy dep-drift break (below) was the ACTUAL cause of the long CI-red streak — it fails before
  pytest even runs. Fixed → CI is green again.
- The flatten defect is a **real latent bug** that Hypothesis surfaces only intermittently. It is a
  flaky-red risk on any future CI run AND a genuine INV-034 safety gap — the fix/amend decision below
  still stands regardless of the flakiness. Do not treat "CI is green" as "the bug is gone."

## Secondary issue — unpinned dependencies (build non-reproducibility) — CONFIRMED CI-RED

`requirements.txt` pins with `>=` only, so CI resolves whatever is latest at install time. **CI on
`chore/ai-os-install` has been RED for many commits** (verified via the Actions API: runs for
`35362a7`, `e072482`, `4537aa2e`, `b2ed3e1`, `64715fe` all `failure`). The failure is **two** distinct
dependency-drift breaks, both from `>=`:

1. **mypy step (the current CI-red — fails before pytest even runs).** CI installed **mypy 2.2.0 +
   numpy 2.5.1**; mypy 2.x follows `alpaca-py`'s transitive pandas/numpy/pyarrow stubs, whose modern
   wheels use PEP 695 `type` statements, which mypy rejects under `python_version = "3.11"`
   (`numpy/__init__.pyi:737: Type statement is only supported in Python 3.12 and greater` → exit 2).
   Only the `test (3.12)` matrix job hits it (the 3.11 job resolves an older numpy). **Fixed here**
   (commit adding this note): a surgical `[[tool.mypy.overrides]] follow_imports = "skip"` for
   `numpy.*` / `pandas.*` / `pyarrow.*` — mypy now skips those third-party stubs (proven locally:
   `mypy --verbose` logs `Skipping .../numpy/__init__.pyi`), consistent with the existing
   `ignore_missing_imports`. `app/` imports none of them directly, so app-code checking is unchanged.
2. **pytest step (the NEXT CI-red, once mypy passes).** Under Hypothesis 6.156 the flatten/X-001
   contradiction above fails `TestSqliteLifecycle`. This is NOT fixed here — it is the gated decision.

**Net:** CI is green again after the mypy fix (the flatten test is flaky and did not trigger that run).
The remaining exposure is (a) the real INV-034 flatten gap, which can flaky-red CI at any time, and
(b) build non-reproducibility generally. Root-cause fix for reproducibility is **pinning dependencies**
(lockfile or bounded upper pins). **Do NOT pin Hypothesis down merely to hide the flatten finding** —
that gap is real independent of the version; pin for reproducibility, fix flatten on its own merits.

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
