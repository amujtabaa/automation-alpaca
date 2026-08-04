---
type: Module Knowledge
title: Architecture Map (reset target and frozen Spine v2 evidence)
status: active
authority: high
owner: Ameen
last_verified: 2026-08-04
tags: [architecture, boundaries, layers]
source_refs: [docs/adr/ADR-020-current-state-execution-kernel.md, docs/adr/ADR-021-position-protection-liquidity-execution.md, docs/adr/ADR-022-reset-beta-scope-cutover-governance.md, docs/adr/ADR-023-bounded-market-occurrence-authority.md, docs/adr/ARCH-RESET-2026-07-RATIFICATION.md, docs/01_ARCHITECTURE.md]
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

The checked-in Spine v2 application remains the as-built legacy generation and read-only evidence.
The first three reset M1 semantic centers are implemented, independently accepted, exact-head
dual-version green, and unwired: `WO-0145` owns immutable execution facts and position truth;
`WO-0146` owns venue effects, concrete acceptances, closure, ambiguity, and ADR-012 recovery; and
`WO-0147` owns deny-by-default trading mode, manual controls, shared request budgets, symbol-wide
execution authority, and atomic final claim. Pure `WO-0148` is active to add a separate position-
protection and hybrid-trailing semantic center against those frozen interfaces. No reset slice
changes runtime behavior or persistence, and no slice authenticates an operational supervisor
fence; acquisition integration and later work remain inactive until separately gated.

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
- Pure reset kernel boundary: `app/execution_core` contains no store, broker adapter, event, API,
  UI, or runtime dependency. Its current venue model retains one-to-many immutable acceptance
  ownership, bounded live indexes, explicit `OPEN -> CLOSED -> INVALIDATED` parent authority, and a
  separate capacity-capped human-fill/non-economic release boundary. Its execution-authority model
  adds exact phase/mode/fence state, kill/manual controls, shared request budgets, permanent query
  identity, symbol-wide uncertainty, and atomic final claim without minting an operational
  supervisor. The package remains an unwired M1 reference center until later persistence and
  composition work orders.
- Boundary enforcement: import-linter contracts in CI; a PR crossing a protected seam fails.
- Runtime pins: Python 3.11 and 3.12 supported, 3.12 development default, no 3.12-only production
  syntax; FastAPI; Streamlit; `alpaca-py` in the adapter only; SQLite as the sole reset-beta
  production persistence implementation. New dependencies require an ADR and a current-status
  check against official docs/PyPI.
- Signal Seat is disabled and unmounted in reset beta. The R6 branch and legacy stores are evidence,
  not reset dependencies.
- ADR-023 governs WO-0148 market-occurrence authority: one mandate-bound stream generation and
  fixed sequence mode, a constructor-derived occurrence identity, and one generation-global strict
  coordinate retained in a constant-size authenticated cursor. Projection, market, and invalidation
  transitions are structurally separate. No lifetime receipt collection, history scan, runtime
  wiring, persistence, adapter fence, or broker authority is part of this pure M1 boundary.

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
- 2026-08-02: Closed pure M1A and filed the independently accepted M1B implementation as a proposed
  `WO-0146` closeout. Venue ownership, ambiguity, immutable acceptance closure, and ADR-012 recovery
  remain I/O-free and unwired. Trading-mode/final-claim authority and later M1 slices remain
  inactive; WO-0146's effective lifecycle remains `REVIEW` until external exact-head Python
  3.11/3.12 CI succeeds.
- 2026-08-02: Repaired the Python 3.11 closeout-oracle failure without production drift. The final
  explicit-stack graph projector closes retained primary/auxiliary map, sequence, metadata, alias,
  cycle, and output-determinism bypasses; REV-0048 addendum-04 returned `ACCEPT` with no P0/P1.
  The effective lifecycle and later-slice activation boundary remain unchanged pending exact-head
  Python 3.11/3.12 CI.
- 2026-08-02: Exact repaired closeout `7d1c9e5` passed GitHub Actions run #685 on Python 3.11 and
  3.12. Closed WO-0146's external gate and activated only pure `WO-0147`; M2 fence persistence/
  hydration, later M4/cutover authentication, runtime wiring, protection, and acquisition remain
  outside it.
- 2026-08-02: Filed proposed WO-0147 closeout after its pure authority kernel passed 710 pure
  cases, 61 R2 cases, the 5,298-test repository gate at `93.02945093976616%`, and independent
  REV-0049 result-addendum-02 `ACCEPT` with every P0/P1 closed. Effective lifecycle remains
  `REVIEW` until immutable exact-head Python 3.11/3.12 CI succeeds; WO-0148 and all runtime,
  persistence, protection, and acquisition integration remain inactive.
- 2026-08-02: Exact WO-0147 closeout `3e39ee6` passed GitHub Actions run #687 on Python 3.11 and
  3.12. Closed its external gate and activated only pure `WO-0148`. The new slice may add one
  opaque protection reducer and a narrow venue-owned bounded proof/projection, but no runtime,
  persistence, broker effect, positive supervisor authority, acquisition integration, or M2 work.
- 2026-08-04: Ratified exact ADR-023 and re-gated active WO-0148 from the rejected lifetime
  occurrence-receipt map to one bounded generation-global cursor with exact split reducers,
  fail-closed invalidation/baseline recovery, and terminal coordinate exhaustion. Implementation
  remains pure and unwired; adapter normalization and the source-authoritative restart fence remain
  deferred to M2.
