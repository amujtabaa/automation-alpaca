---
type: Project Rule
title: Project Goals and Current Posture
status: active
authority: high
owner: Ameen
last_verified: 2026-08-04
tags: [goals, posture, roadmap]
source_refs: [docs/adr/ADR-020-current-state-execution-kernel.md, docs/adr/ADR-021-position-protection-liquidity-execution.md, docs/adr/ADR-022-reset-beta-scope-cutover-governance.md, docs/adr/ADR-023-bounded-market-occurrence-authority.md, docs/adr/ARCH-RESET-2026-07-RATIFICATION.md]
supersedes: []
superseded_by: null
---

# Project Goals and Current Posture

## Summary

Build a narrow, reliable, browser-operated protection/acquisition engine for Alpaca Paper. The
accepted reset target is a modular monolith with one sequenced writer, one pure transition kernel,
one SQLite production store, transactional current state/outbox, and broker-neutral protection and
side-symmetric liquidity execution. The integrated Spine v2 application and R6 branch are frozen
evidence, not the reset foundation. M0 and pure M1A/M1B/M1C `WO-0145` through `WO-0147` are
effective `CLOSED` after independent acceptance and exact-head Python 3.11/3.12 CI. Pure M1D
`WO-0148` is filed as an independently accepted, locally green conditional closeout for position
protection and hybrid trailing; its effective lifecycle remains `REVIEW` until its immutable exact
SHA passes the unchanged dual-version workflow. No reset implementation work order is active.
`WO-0149`, M2, and every runtime/persistence/cutover slice remain inactive.

## Rules / facts

- Beta target: usable, feature-rich, **paper-only** trading platform. Live trading remains disabled by config.
- Alpaca Paper, one account, a small US-equity symbol set, and manual acquisition/protection
  approval define reset beta. Signal Seat is disabled and unmounted.
- Python 3.11 and 3.12 are supported, Python 3.12 is the development default, and production code
  may not require 3.12-only syntax.
- Legacy migration/event-log/dual-store behavior remains read-only evidence; reset live decisions
  use transactional current state under ADR-020.
- The permanent safety core lives verbatim in `CLAUDE.md` and is never overridden by tooling or convenience defaults.
- Reset implementation advances only through independently reviewed work orders explicitly
  activated after their predecessor gates. `WO-0145` through `WO-0147` are effective `CLOSED`;
  `WO-0148` is a proposed `CLOSED` closeout but remains effectively `REVIEW` pending exact-head CI.
  No reset work order is active, and neither `WO-0149` nor M2 may begin from the local closeout.

## Rationale

Roadmapping against an unverified codebase state repeats the failure mode Fable exists to prevent: building on unpasted claims. The audit wave converts "migration is done" from assertion to evidence.

## Applies to

- All planning, roadmap, and feature work.

## Related pages

- `pkl/safety/invariants-rationale.md`
- `pkl/architecture/architecture-map.md`
- `pkl/process/migration-history.md`

## Change log

- 2026-07-07: Created from CLAUDE.md decomposition.
- 2026-07-31: M0 replaced the completed-Spine-v2 posture with the ratified reset target and retained
  the existing application as frozen evidence. No implementation was activated.
- 2026-07-31: After M0 acceptance and exact-head Python 3.11/3.12 CI, Ameen's explicit implementation
  authority activated only the pure, credential-free first reset slice as `WO-0145`.
- 2026-08-01: Closed `WO-0145` after its focused, R2, full-coverage, implementation-checkpoint
  dual-version CI, and independent kernel/test review gates. No reset implementation work order is
  active; all later slices remain inactive pending separate explicit human authorization.
- 2026-08-01: After exact closeout `dfb8ed3` passed independent review and unchanged Python
  3.11/3.12 CI, Ameen authorized options 1–4. Activated only RESET-WO-02 as `WO-0146`, a pure
  I/O-free venue-ownership/recovery kernel; produced a read-only retirement inventory whose
  deletion actions remain gated by complete M1 review, non-squashed merge, and exact-master CI.
- 2026-08-02: The first `WO-0146` closeout candidate failed exact-head Python 3.11 CI in a recursive
  test-oracle rendering path. Reviewer-owned addendum-03 then blocked the first repair, and two
  independent audits blocked an incomplete successor on auxiliary retained maps. Final test-only
  freeze `5a89841` uses a complete iterative graph projector, passed 536 pure cases, 22 stateful
  cases at recursion limit 700, 61 R2 cases, and a 5,124-case repository run at
  `93.00594652069468%` combined coverage. Reviewer-owned addendum-04 accepted exact evidence target
  `982d213` with no unresolved P0/P1. The repaired candidate remains effectively `REVIEW` and
  non-activating until its immutable exact SHA passes Python 3.11/3.12 CI; RESET-WO-03 and every
  later slice remain inactive.
- 2026-08-02: Repaired immutable closeout `7d1c9e5` passed GitHub Actions run #685 on Python 3.11
  and 3.12, satisfying WO-0146's final external gate. Activated only `WO-0147`, the pure execution-
  authority/manual-control/request-budget slice. It cannot authenticate the later M4/cutover
  supervisor fence or perform broker, database, persistence, runtime, merge, deletion, or cleanup
  work. M2 may persist and hydrate the deny-only fence but cannot promote it without those later
  adapter/cutover gates.
- 2026-08-02: Filed the repaired WO-0147 closeout after the 710-case pure kernel, 61-case R2 oracle,
  5,298-test repository gate at `93.02945093976616%` combined coverage, and REV-0049 result
  addendum 02 `ACCEPT` closed every preserved P0/P1. The closeout is effective `REVIEW` until its
  immutable SHA passes unchanged Python 3.11/3.12 CI. WO-0148 and all later slices remain inactive;
  no runtime, persistence, broker, credential, database cutover, merge, deletion, or cleanup
  authority was added.
- 2026-08-02: Immutable WO-0147 closeout `3e39ee6` passed GitHub Actions run #687 on Python 3.11
  job `91626251701` and Python 3.12 job `91626251758`. Closed its external gate and separately
  activated only pure `WO-0148` for exact formula-driven position protection, distinct market-
  occurrence evidence, hybrid trailing, BUY-resolution wait policy, flat finalization, and late-
  fill re-protection. `WO-0149`, M2, broker, credential, persistence, runtime, merge, deletion,
  and cleanup remain inactive.
- 2026-08-04: Ameen ratified exact ADR-023 SHA-256
  `898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259` and its WO-0148 re-gate.
  The rejected lifetime receipt map is superseded by a constant-size generation/mode-bound strict
  market cursor with split projection, market, and invalidation reducers. Production remains barred
  until a replacement immutable RED contract receives independent exact-commit `ACCEPT` with zero
  P0/P1; `WO-0149`, M2, runtime/persistence, broker/network, merge, deletion, and cleanup remain
  inactive.
- 2026-08-04: Ameen ratified ADR-023 amendment R1 at exact proposal SHA-256
  `F0403B87770648DE233575CE29D853327FD0B48559CE032B4CEF529A6EFE34E9`. The correction retains
  one exact bounded last-primary price for the required next-step comparison and narrowly admits the
  derived-identity dataclass field form. WO-0148 remains pure and unwired; application work remains
  barred until one corrected immutable RED contract receives independent acceptance with zero
  unresolved P0/P1.
- 2026-08-04: Filed the independently accepted pure WO-0148 closeout candidate after the final
  position-local successor, exact runtime-envelope review, 61/61 R2 oracle, and 5,847-test repository
  gate passed with zero failures/errors and `93.01194919026261%` raw combined coverage. Effective
  lifecycle remains `REVIEW` until the immutable closeout SHA passes unchanged Python 3.11/3.12 CI.
  No reset work order is active; `WO-0149`, M2, runtime/persistence, broker/network, credentials,
  merge, deletion, and cleanup remain inactive.
- 2026-08-04: Exact-head run #691 invalidated the first WO-0148 closeout only on Python 3.11's
  recursive test-oracle equality; Python 3.12 passed and no production reducer failed. A test-only
  complete explicit-stack successor received independent `ACCEPT` with no P0/P1, then passed 61/61
  R2 cases and 5,848 repository tests at `93.01194919026261%`. Effective lifecycle remains `REVIEW`
  pending a new unchanged dual-version exact-head run; WO-0149 and M2 remain inactive.
