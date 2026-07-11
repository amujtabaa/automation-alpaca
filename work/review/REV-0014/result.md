# REV-0014 result — Strategy engine + approval workflow

Reviewed at frozen base `b60010148f3201a9f8c62ee0bda45371d5c964f4` using Python 3.12.3. I treated the packet as findings-only and did not edit production code.

| Finding | Severity | Evidence | Why it matters | Required action |
|---|---:|---|---|---|
| Buy-side candidate single-flight is not enforced at the store/facade boundary. | P1 | `run_strategy_tick` computes `open_symbols` once before the per-symbol loop and passes a boolean into `evaluate`; the authoritative `create_candidate` store method validates session/numerics but inserts unconditionally; `inject_mock_candidate` calls that same store method without a dedup check. | The stated buy-side rule is at most one active proposal per symbol/session. Today that rule is a caller-side convention, not a store invariant: any second producer, dev injection, retry, or concurrent loop can create multiple PENDING candidates for the same symbol/session. That can produce ambiguous human review and multiple later BUY intents if both are approved. | Move active-candidate dedup into `StateStore.create_candidate` (both stores, same transaction/lock as insert) or an equivalent authoritative planner, and add dual-store tests covering loop plus dev-inject/concurrent producers. |

## Additional verification notes

- `evaluate` is deterministic and IO-free with respect to its inputs; I found no clock/RNG/network/store access reachable from it. The loop's wall-clock read is outside `evaluate` and only classifies session.
- `evaluate` rejects non-finite present numeric snapshot fields before arithmetic and treats `None` through explicit gates; I did not find an input shape that reaches the final `assert` falsely.
- Candidate approval re-runs the safety/risk gates in `create_order_for_candidate`, and created orders remain `CREATED`; I found no strategy/approval path that directly submits or bypasses `claim_order_for_submission`.

## Verdict

ACCEPT-WITH-CHANGES

Could not verify live Alpaca behavior; this review used code inspection and local unit-level reasoning only.
