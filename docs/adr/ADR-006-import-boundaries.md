# ADR-006 — Import-Boundary Enforcement (import-linter)

## Status

Accepted.

## Context

CLAUDE.md §5 and ADR-005 define a layered architecture and require it to be
*mechanically* enforced: "Enforce boundaries with import-linter once the
migration seams exist. A PR that crosses a protected boundary fails CI." Through
Phase 4 the seams existed (facades, adapters, a venue-agnostic engine, a leaf
model kernel) but nothing prevented a future edit from quietly crossing a
boundary — e.g. a Streamlit page importing the store, a route importing the
Alpaca SDK, or the engine importing a concrete adapter.

The migration is only *partial*: Phase 1/4h migrated three routes behind the
typed facade, but most routes still call the store/engine/broker directly (that
demotion is Phase 6). So a single "routes only touch the facade" rule cannot be
turned on as an all-or-nothing gate today without either failing the build or
being disabled entirely.

## Decision

Adopt **import-linter** (`.importlinter`, run in CI and by
`tests/test_import_boundaries.py`) with two tiers of contract:

**Tier 1 — hard invariants that hold today with zero exceptions.** These encode
non-negotiable project rules and fail the build the instant they are crossed:

1. **`alpaca-sdk-confined-to-adapter`** — only `app.broker.alpaca_paper` and
   `app.marketdata.alpaca_stream` may import `alpaca` (invariant #5; ADR-005).
2. **`cockpit-is-a-thin-client`** — `cockpit` imports no `app.*` code (invariant
   #4); it reaches the backend only over HTTP via `cockpit.api_client`.
3. **`engine-is-venue-agnostic`** — engine modules (`monitoring`,
   `reconciliation`, `policy`, `position`, `protection`, `strategy`,
   `strategy_loop`, `features`, `transitions`, `events`, `approval`) may depend
   on the abstract **ports** (`app.broker.adapter`, `app.marketdata.service`)
   but never on a concrete venue implementation or the SDK.
4. **`models-is-a-leaf`** — `app.models` (the shared kernel imported by every
   layer) imports no other `app` layer back, so it can never create a cycle.

All four use `allow_indirect_imports = True`: they forbid a module from
*directly* writing the offending import, which is the real boundary — the
composition root (`app.main`, `app.api.deps`) and pure helpers legitimately
create transitive paths that are not violations.

**Tier 2 — the ADR-005 migration target, enforced as a ratchet.**

5. **`api-routes-reach-backend-only-via-facade`** — route modules
   (`app.api.routes_*`) reach the store/engine/broker only through the facade.
   Because most routes are unmigrated, its `ignore_imports` block is the
   **explicit, exhaustive Phase-6 punch-list** of the remaining direct
   route→backend edges. `unmatched_ignore_imports_alerting = error` makes it a
   **ratchet**: when Phase 6 migrates a route behind the facade, the stale
   ignore entry errors until it is deleted, so the boundary can only tighten and
   never silently regress. When the block is empty, the ADR-005 route boundary
   is fully enforced. `app.api.deps` (the DI/composition root that builds the
   facade and still hands the legacy store to unmigrated routes) and
   `app.api.schemas` (HTTP DTOs) are deliberately not sources.

## Consequences

- A boundary-crossing PR fails both the dedicated CI `lint-imports` step and
  `tests/test_import_boundaries.py` (so the gate holds even if the CI step is
  removed). Two invariants (alpaca confinement, thin UI) are additionally
  re-proven directly against the grimp import graph, independent of the INI, so
  they survive a mis-edit that weakens the config.
- Phase 6 gains a mechanical, self-tightening checklist: empty the Contract-5
  `ignore_imports` block one migrated route at a time.
- import-linter becomes a required dev/CI dependency (`requirements.txt`).
- The contracts check *direct* imports; they do not (and should not) forbid the
  legitimate transitive paths the composition root creates.

## Required tests

- all five contracts KEPT on the current tree (`test_all_import_contracts_hold`);
- alpaca-py is importable only by the two concrete ports, proven against the
  raw import graph (`test_alpaca_sdk_is_confined_to_the_two_concrete_ports`);
- the cockpit imports no backend module, proven against the raw graph
  (`test_cockpit_imports_no_backend_code`);
- the ratchet bites: a stale/unmatched ignore entry and a newly-introduced
  forbidden edge both fail `lint-imports` (verified during Phase 5 build;
  re-checkable by removing any Contract-5 ignore line).
