# FINDING — protection replay disposition returns APPLIED where EXACT_REPLAY is required

- **Status:** OPEN. Found 2026-08-24 during WO-0168c full verification. Not caused by WO-0168c.
- **Severity:** **P1** — protection reducer replay semantics; execution-safety adjacent.
  Not P0 only because no evidence yet ties it to a live order path.
- **Owner:** unassigned. Explicitly **out of scope for WO-0168c** and recorded rather than fixed.
- **Pin:** the failing tests already exist; no new pin needed to reproduce.

## What

`tests/execution_core/test_protection_stateful.py` fails on the assertion that a replayed
protection input is classified `EXACT_REPLAY`:

```text
AssertionError: assert <ProtectionDisposition.APPLIED: 'APPLIED'>
                    is <ProtectionDisposition.EXACT_REPLAY: 'EXACT_REPLAY'>
```

Affected tests (identities vary run to run — see the determinism defect below):

```text
test_high_risk_market_rules_advance_directed_histories[sequenced-cursor-before-context]
test_high_risk_market_rules_advance_directed_histories[sequenced-replay-conflict-precedence]
test_high_risk_market_rules_advance_directed_histories[source-time-cursor-before-context]
test_high_risk_market_rules_advance_directed_histories[source-time-replay-conflict-precedence]
test_retained_market_policy_rules_advance_directed_histories[trigger-branch-reset]
TestProtectionSequencedMarketMachine::runTest
TestProtectionSourceTimeMarketMachine::runTest
TestRetainedMarketPolicyMachine::runTest
```

## Why it matters

`APPLIED` where `EXACT_REPLAY` is expected means a duplicate input is being treated as a new
one. In the protection cursor path that is the shape of a double-advance: the same market
observation counted twice. The stateful machines reach it through directed histories involving
cursor-before-context ordering and replay/conflict precedence, i.e. exactly the reordering that
a restart or a reconnecting market feed produces.

Whether this can reach an order decision has **not** been established. It should be, before the
severity is settled.

## Provenance — this is not WO-0168c's

Three independent checks:

1. **Reproduced at the pre-session base commit.** A clean worktree at `344c32b` with a cold
   hypothesis cache produced 8 failures — the same set.
2. **No import path.** `test_protection_stateful.py` imports only `app.execution_core.fills`,
   `identity`, `recovery`, and `values`. It references `checkpoint_codec`, `persistence`,
   `repository`, and `schema` zero times, so nothing WO-0168c changed can reach it.
3. **Different subsystem.** WO-0168c touches checkpoint projection; this is protection reducer
   replay classification.

## Second, separable defect — the tests are not deterministic

The hypothesis state machines are configured without `derandomize`:

```python
TestProtectionSequencedMarketMachine.settings = settings(
    max_examples=20, stateful_step_count=12, deadline=None,
)
```

Run-to-run the failure count moved between 4 and 8. CLAUDE.md requires engine tests to use
injected clocks, no unseeded randomness, and deterministic IDs/queues; hypothesis without
`derandomize=True` and without a pinned `database` violates that in spirit and in effect.

Consequence for triage: **the failure count above is a floor, not a fixed number.** Any fix must
be validated with `derandomize=True` or a pinned seed, or a green run proves nothing.

### The same setting also makes the full suite unrunnable

`deadline=None` removes any per-example time limit, so one generated example can run unbounded.
Measured 2026-08-24: a full `pytest tests/` run (6,793 collected) reached ~1% and then advanced at
roughly six tests per minute, and had to be abandoned. Excluding the five stateful files
(`test_protection_stateful`, `test_venue_stateful`, `test_acquisition_stateful`,
`test_authority_stateful`, `test_fill_position_stateful` — 37 tests between them) the same suite
completes normally.

So this defect currently costs the project its whole-repository gate, not just a stable failure
count. Fixing the determinism fixes both.

## What resolves it

1. Make the machines deterministic first (`derandomize=True` or an explicit seed/profile), so the
   failure set is stable and a fix is falsifiable.
2. Root-cause the `APPLIED` vs `EXACT_REPLAY` classification in the protection reducer under the
   cursor-before-context and replay-conflict-precedence histories.
3. Establish whether the misclassification can reach an order or protection decision; settle the
   severity on that evidence.
4. Fix the reducer, not the assertion. `EXACT_REPLAY` is the contract-correct answer for a
   duplicate input; if the machines' expectation is wrong instead, that needs its own argued
   disposition rather than a quiet edit.

## Evidence

```text
$ git worktree add --detach <tmp> 344c32b
$ cd <tmp> && pytest tests/execution_core/test_protection_stateful.py -q --tb=no -p no:randomly
8 failures                    # cold hypothesis cache, pre-session base

$ grep -c "checkpoint_codec\|persistence\|repository\|schema" \
      tests/execution_core/test_protection_stateful.py
0
```
