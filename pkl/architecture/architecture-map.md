---
type: Module Knowledge
title: Architecture Map (reset target and frozen Spine v2 evidence)
status: active
authority: high
owner: Ameen
last_verified: 2026-07-31
tags: [architecture, boundaries, layers]
source_refs: [docs/adr/ADR-020-current-state-execution-kernel.md, docs/adr/ADR-021-position-protection-liquidity-execution.md, docs/adr/ADR-022-reset-beta-scope-cutover-governance.md, docs/adr/ARCH-RESET-2026-07-RATIFICATION.md, docs/01_ARCHITECTURE.md]
supersedes: []
superseded_by: null
---

# Architecture Map (reset target and frozen Spine v2 evidence)

## Summary

The accepted reset target is a modular monolith with one sequenced writer, one pure transition
kernel, transactional current state plus a broker-effect outbox, and SQLite as the sole beta
production store. Immutable execution facts, claims, acceptance/closure evidence, venue ownership,
and terminal closures carry narrow durable authority; audit/replay explains and tests decisions but
does not replace current state on the live path.

The checked-in Spine v2 application remains the as-built legacy generation and read-only evidence
until separately activated reset work replaces bounded semantic centers. M0 changes no runtime
behavior and activates neither generation.

## Rules / facts

- Reset target layers and seams:
  - `ui` (Streamlit) → imports only the typed API client + UI-local display helpers.
  - `api` (FastAPI) → schemas, auth, command/query facades only.
  - `facade` → command/query protocols, readiness checks, DTO mapping, domain-error mapping.
  - `engine` → one account sequencer and pure, I/O-free transition kernel.
  - `adapter` → the only module allowed to import `alpaca-py`.
  - `store` → SQLite repository for transactional current state, outbox, immutable fact/ownership/
    closure evidence, receipts, and audit records.
- Single writer: only the sequenced engine commits capital-relevant state. Position quantity changes
  only through first-occurrence canonical `FILL` facts and predecessor-linked broker-authoritative
  `TRADE_CORRECT`/`TRADE_BUST` revisions. `SUBMITTED`/`ACCEPTED` never change quantity.
- Boundary enforcement: import-linter contracts in CI; a PR crossing a protected seam fails.
- Runtime pins: Python 3.11 and 3.12 supported, 3.12 development default, no 3.12-only production
  syntax; FastAPI; Streamlit; `alpaca-py` in the adapter only; SQLite as the sole reset-beta
  production persistence implementation. New dependencies require an ADR and a current-status
  check against official docs/PyPI.
- Signal Seat is disabled and unmounted in reset beta. The R6 branch and legacy stores are evidence,
  not reset dependencies.

## Rationale

Seam discipline is what makes the safety invariants structurally enforceable rather than aspirational. See `pkl/safety/invariants-rationale.md`.

## Applies to

- All source and test code; CI boundary contracts.

## Related pages

- `pkl/architecture/testing-model.md`
- `pkl/safety/invariants-rationale.md`
- `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`
- `work/queue/ARCH-RESET-2026-07/12-proposed-adr-set.md`

## Change log

- 2026-07-07: Created from CLAUDE.md §5/§2 decomposition. `last_verified` date reflects decomposition, not code audit; WO-0002…WO-0005 will verify against code.
- 2026-07-31: M0 recorded the accepted reset target, runtime contract, and frozen-legacy boundary;
  no production behavior changed.
