# Conflict record: Option B vs the Codex R2 conformance oracle (STOP-FOR-HUMAN)

> **STATUS: DECISION GAP FOR THE HUMAN. No oracle edited.** Surfaced by the Option B
> test-integrity review (WO-0107 / REV-0024). Per `CONSOLIDATION-CHARTER.md §3` / §B1 a
> spec conformance oracle "is the definition of done for behavior — it may not be edited
> to pass; a needed change here is a spec change and goes to the human." Per `CLAUDE.md`
> conflict rule, a code/spec disagreement on a **human-gated safety surface** (manual
> flatten) is stopped and recorded here before anyone edits the oracle.

## The finding

The Option B change (WO-0107, commit `6480984`) makes the store's `flatten_position`
return `FLATTEN_BUYS_OPEN` (minting nothing) when a HELD position still has an open BUY,
so the caller cancels the buys (broker call, off-lock) and retries — closing the §5.3
self-cross. Running the **Codex** investigator's spec oracle against the current trunk:

```
pytest -q tests/r2_conformance_oracle.py     # the Codex Part-B acceptance oracle
```

- **Current trunk (`6480984`, Option B): 14 failures.**
- **Parent (`15c2dd6`, pre-Option-B): 4 failures.**
- ⇒ **Option B introduces exactly 10 new failures.** (Isolated by running the same oracle
  against both commits in a scratch worktree.)

### The 10 new failures (all Option B)
All are store-level flatten / emergency-reduce scenarios that now reach `FLATTEN_BUYS_OPEN`
before the deferral/mint they assert, because the oracle's `_seed_long` establishes the
position by creating a BUY + `append_fill` and **leaves that BUY open (CREATED)**:

- `test_flatten_defers_after_envelope_terminal_while_child_may_rest[memory,sqlite]`
- `test_flatten_defers_to_every_possibly_live_envelope_child[memory-submitted, memory-timeout_quarantine, sqlite-submitted, sqlite-timeout_quarantine]`
- `test_flatten_preempts_local_staging_without_leaving_a_second_owner[memory,sqlite]`
- `test_emergency_reduce_under_halted_defers_to_resting_envelope_child[memory,sqlite]`

Representative assertion: `assert result.deferred is True` → actual
`FlattenResult(outcome='buys_open', intent=None, order=None, deferred=False)`.

### The 4 pre-existing failures (NOT Option B — flagged separately)
Present at the parent commit too, unrelated to flatten-with-open-buy:
`test_pre_activation_approved_envelope_does_not_survive_session_close[memory,sqlite]` and
`test_needs_review_recovery_retains_owner_after_envelope_terminal[memory,sqlite]` — the
trunk does not yet satisfy these two Codex-derived properties (a broader Part-B-incomplete
signal). **Out of scope for Option B; logged here so the consolidation backlog keeps them.**

## Why this is a decision, not a bug

Two independently spec-derived oracles **disagree** on Option B:

| Oracle | Flatten property it encodes | Seeds an open buy? | Option B verdict |
|---|---|---|---|
| **Claude** (`test_r2_conformance_oracle_claude.py`) | flatten must not *blindly mint a fresh SELL* next to a live child → `outcome != "created"` | No (envelope path) | **PASSES** (22 passed / 6 skipped) — `buys_open` satisfies `!= "created"` |
| **Codex** (`r2_conformance_oracle.py`) | flatten must *DEFER* → `deferred is True` on the raw first store call | Yes (`_seed_long`) | **FAILS** — `buys_open` precedes the deferral |

The disagreement is entirely about the **store-level contract**, not observable behavior:
- The Codex oracle drives `store.flatten_position` **directly** and asserts on the FIRST
  return, so it sees Option B's new intermediate `BUYS_OPEN` signal.
- At the **facade** (the real caller, `_flatten_cancelling_open_buys`) the behavior is
  **identical to before**: cancel the open buy → retry → the same deferral / mint. Option B
  only inserts the cancel+retry round-trip the pre-Option-B facade already performed
  unconditionally.
- This is the same store-contract shift already reconciled in the `_hold` fixtures and the
  `test_lifecycle_state_machine.py` harness (both updated to model the new outcome): a
  held position with an open buy is an **unrealistic direct-flatten input** (the real
  caller always clears buys first), so seeding one and asserting direct deferral over-
  specifies the store layer.

## Evidence Option B is spec-conformant (not the oracle's side)
- The **Claude** spec oracle passes unchanged.
- Three independent adversarial reviews (concurrency, behavior/self-cross, test-integrity)
  returned **SHIP / TESTS-SOUND**: all six prior flatten behaviors preserved, no new mint
  window, convergence proven, fixtures not weakened.
- Operator **ratified** Option B (the only fix with no self-cross window).
- Net facade behavior is unchanged; the change is strictly safety-improving (fails closed).

## Recommendation (for the human — I did not act on it)
1. **Preferred:** treat the Codex oracle's flatten seeds as needing the SAME realism fix
   applied to `_hold` / the lifecycle harness — terminalize the establishing BUY in
   `_seed_long` (or teach the oracle's flatten helper to model the caller's cancel+retry).
   That is a **spec-oracle change**, so it needs your sign-off (and, given the independence
   rule, is the Codex investigator's file — reconciliation is a cross-investigator/human
   call, not mine to edit).
2. **Alternative:** if the R2 spec truly requires the STORE to defer directly even with an
   open buy present (no cancel+retry contract), then Option B's `BUYS_OPEN` store contract
   would need rework — but that re-opens the §5.3 self-cross the operator ratified closing,
   so (1) is strongly preferred.

## Disposition
- `test_lifecycle_state_machine.py` (a regular harness, mine): **FIXED** in the same
  change — models `FLATTEN_BUYS_OPEN` + a deterministic reachability proof (both stores).
- `r2_conformance_oracle.py` (Codex spec oracle): **NOT EDITED** — routed here to you.
  This conflict is also referenced in `work/review/REV-0024/request.md` for the independent
  cross-model reviewer to weigh in on before the WO-0107 flatten gate clears.
