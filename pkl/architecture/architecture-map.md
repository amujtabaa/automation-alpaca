---
type: Module Knowledge
title: Architecture Map (reset target and frozen Spine v2 evidence)
status: active
authority: high
owner: Ameen
last_verified: 2026-08-06
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
execution authority, and atomic final claim. Pure `WO-0148` adds the separate formula-bound
position-protection, bounded market-occurrence, hybrid-trailing, wait/flat/late-fill, and typed SELL-
goal semantic center; its exact closeout `2462fb557172dd28a7475a763eca0b440c0298e3` is now
dual-version CI green and effective `CLOSED`. ADR-020 R2 and ADR-021 R2 now define the
serial acquisition-generation architecture. The retained `WO-0149` lifecycle record is not
authority for that R2 scope. WO-0150's pure E1 closeout SHA
`f1a40d69f301ad7f594a61f202d3bd380607b98a` passed exact-head GitHub Actions run `31089203210`
(#726) on Python 3.11 and 3.12 and is effective `CLOSED`. WO-0151 is now active only for its
ratified pure-E2 R2--R11-plus-R11-R1 composite, whose R11 base and R11 R1 correction are
`00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d` and
`d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9`, following documentation-only
activation SHA `466e712b6f507ee165a7fc0c80e826fa8a35a710` and R10 re-gate SHA
`638c73cff1e02a8834309362cc5dc762b165871b`, with R11 R1 re-gate SHA
`8ebe9350520e28409c33c28cc958ee926639f28e`; WO-0152 and all
M2/runtime/persistence work remain inactive until separately gated.

## Current R2 ratification posture

ADR-020 R2 and ADR-021 R2 are the accepted authority for serial same-symbol acquisition:
direct immutable generation lineage, one SymbolAcquisitionController, at most one LIVE generation,
and one active protection/broker authority. WO-0149 is formally SUPERSEDED and retained as
evidence; it grants no implementation authority for this R2 serial-generation scope. The original
WO-0150 activation and accepted REV-0057 successor are historical R0 evidence only. The R1
documentation gate is accepted. Its E1 closeout manifest
`a68c5897717e0e3ee735af6a95ff768c59951338dff321aca9ab42bc662acfde` received final independent
`ACCEPT` with P0=0/P1=0, and exact closeout SHA
`f1a40d69f301ad7f594a61f202d3bd380607b98a` passed dual-version CI. R7 remains retained
predecessor evidence. R8 remains ratification provenance. R9 and its initial acceptance remain
retained but are not an acceptance basis. R10 then independently accepted and the user ratified
the narrow exact-immutable-replay clarification. The initial R11 result is retained negative
evidence; R11 R1 closes its single P1 by separating cancel-only BUY preemption from goal-bearing
protective SELL exit. The fresh R11 R1 review accepted the complete route set at P0=0/P1=0/P2=0.
WO-0151 alone is active under the R2--R11-plus-R11-R1
composite; WO-0152, M2, and all runtime/persistence work remain inactive until separately gated.

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
  supervisor. Its protection model derives formula-bound floors, bounded market authority, hybrid
  trails, exact wait/flat/late-fill semantics, and typed SELL goals from authenticated execution and
  venue state without creating an effect. The package remains an unwired M1 reference center until
  later persistence and composition work orders.
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
- The R2 serial acquisition foundation is split across E1 identity/direct venue correlation, E2
  controller/recovery behavior, and E3 generated/stateful conformance. WO-0150's exact E1
  closeout manifest `a68c5897717e0e3ee735af6a95ff768c59951338dff321aca9ab42bc662acfde` was
  independently `ACCEPT`ed at P0=0/P1=0, and its exact closeout SHA is dual-version CI green.
  Successful registry/index population, permanent routing, and late-fact mutation are E2-only.
  E2 is active under the ratified R2--R11-plus-R11-R1 composite; E3 remains inactive. No runtime, persistent database, broker,
  credential, or M2 authority is granted.
- Current posture amendment (2026-08-05): E1 provides only deterministic non-authoritative identity
  data, immutable view and inert-reader shapes, and the no-history venue correlation bridge.
  Successful direct registry/index population, A-to-B-to-C routing, and late-fact mutation are
  deferred to future E2; the preceding permanent-index statement is retained historical
  pre-amendment context, not current E1 implementation authority.
- Current R1 clarification: wire-shape validation does not decide predecessor authenticity or
  controller currentness; E2 owns those decisions. The acquisition module's exact narrow export set
  is separate from the broad established package root. Venue correlation is a current-book-derived,
  output-only read projection rather than a transferable proof; future E2 must re-query the current
  authenticated book within its composite transition.

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
- 2026-08-04: Ratified ADR-023 amendment R1 at exact proposal SHA-256
  `F0403B87770648DE233575CE29D853327FD0B48559CE032B4CEF529A6EFE34E9`. The bounded cursor
  now retains one exact last-primary `ReportedPrice` solely for the next maximum-step comparison and
  serializes only its canonical commitment in unchanged cursor part 13. The RED grammar narrowly
  permits `_field(init=False)` only for the derived occurrence identity. A replacement RED freeze
  remains required; every constant-history, pure-M1, and deferred-M2 boundary is unchanged.
- 2026-08-04: Filed the pure WO-0148 position-protection closeout candidate after exact root-
  successor and runtime-envelope reviews returned `ACCEPT` with no unresolved P0/P1, 61/61 R2 cases
  passed, and 5,847 repository tests completed with zero failures/errors at
  `93.01194919026261%` raw combined coverage. The local metadata is proposed `CLOSED`, but effective
  lifecycle remains `REVIEW` until unchanged exact-head Python 3.11/3.12 CI succeeds. No reset work
  order is active; WO-0149, acquisition, M2, runtime, and persistence remain inactive.
- 2026-08-04: Exact-head Python 3.11 exposed recursive whole-graph equality in shared WO-0148 test
  helpers; Python 3.12 passed and production behavior was not implicated. The accepted tests-only
  successor uses one complete alias-aware explicit-stack graph fingerprint across authority,
  stateful authority, and protection reducers. Fresh R2 and 5,848-test coverage gates are green;
  the repaired closeout remains effectively `REVIEW` pending new exact-head dual-version CI.
- 2026-08-05: Exact WO-0148 closeout `2462fb557172dd28a7475a763eca0b440c0298e3` passed GitHub
  Actions push run #693 on Python 3.11 and 3.12, closing its external gate. Activated only
  documentation/specification `WO-0149` after final independent exact-candidate preflight returned
  `ACCEPT` with no P0/P1. The new acquisition/cross-side semantics remain unimplemented and unwired;
  M2, persistence, runtime, broker, credentials, merge, deletion, and cleanup remain inactive.
- 2026-08-05: Ameen ratified ADR-020 R2
  eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 and ADR-021 R2
  b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c from REV-0056 R3 manifest
  d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c. The ratified design
  requires serial direct acquisition-generation lineage and one aggregate controller. Three
  successor work orders are DRAFT only; no R2 implementation, activation, runtime, persistence,
  broker, credential, database, M2, merge, deletion, or cleanup authority was added.
- 2026-08-05: Ameen formally superseded WO-0149 because the ratified R2 ADRs replace its
  one-lifetime same-symbol premise. The record and all related material are retained as evidence;
  WO-0150 through WO-0152 remain DRAFT/inactive. No implementation, test, database, runtime,
  broker, credential, M2, merge, deletion, or cleanup authority was added.
