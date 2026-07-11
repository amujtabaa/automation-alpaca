# REV-0013 result — Facade + API routes

Reviewed at frozen base `b60010148f3201a9f8c62ee0bda45371d5c964f4` using Python 3.12.3. I treated the packet as findings-only and did not edit production code.

| Finding | Severity | Evidence | Why it matters | Required action |
|---|---:|---|---|---|
| Dev candidate injection bypasses the facade/store active-candidate single-flight rule. | P1 | `StoreBackedCommandFacade.inject_mock_candidate` checks only session-open and then calls `create_candidate`; the store inserts candidates without checking for an existing PENDING/APPROVED candidate for the same symbol/session. | Even if the strategy loop dedups proposals, a facade/API caller can create multiple active candidates for the same symbol/session. That undermines the operator review model and can lead to multiple BUY intents if the duplicates are approved. | Add authoritative active-candidate dedup at the store/planner boundary and map the duplicate error to a domain 409 in the facade/API. |

## Additional verification notes

- `approve_candidate` pre-checks dispatchability, kill/buy-pause, and CAPI limits, and the store's `create_order_for_candidate` re-runs the authoritative safety/risk gates before creating a BUY order intent.
- Created candidate orders are not submitted by the facade; submission still flows through the monitoring claim gate.
- I did not identify a fresh raw-500 route with a concrete reachable input during this pass beyond disclosed known-read-route error-wrap risk.

## Verdict

ACCEPT-WITH-CHANGES

Could not verify every route against a running ASGI server; this review used code inspection and facade call-chain tracing.
