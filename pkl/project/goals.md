---
type: Project Rule
title: Project Goals and Current Posture
status: active
authority: high
owner: Ameen
last_verified: 2026-08-07
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
`WO-0148` is effectively `CLOSED`: immutable SHA
`2462fb557172dd28a7475a763eca0b440c0298e3` passed unchanged GitHub Actions push run
`30996686588` (#693) on Python 3.11 and 3.12. ADR-020 R2 and ADR-021 R2 now control the
serial acquisition-generation foundation. The retained `WO-0149` lifecycle record does not
grant R2 implementation authority. `WO-0150` is effectively `CLOSED`: its exact closeout SHA
`f1a40d69f301ad7f594a61f202d3bd380607b98a` passed GitHub Actions run `31089203210` (#726) on
Python 3.11 and 3.12. `WO-0151` has a locally verified pure-E2 closeout at remediation manifest
`2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853`; its final independent
recheck `96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd` returned `ACCEPT`,
P0=0/P1=0/P2=0. Its effective lifecycle remains `REVIEW` until unchanged exact-head Python
3.11/3.12 CI succeeds. `WO-0152` remains DRAFT/inactive. M2 and every
runtime/persistence/cutover slice remain inactive. WO-0153
has completed its bounded cleanup scope with environment-controlled deferred artifacts only; it
adds no implementation authority.

## Current R2 ratification posture

ADR-020 R2 and ADR-021 R2 now control serial same-symbol acquisition. WO-0149 is formally
SUPERSEDED and retained as evidence; it grants no implementation authority for the new
serial-generation scope. The predecessor REV-0057 successor and its WO-0150 activation are
historical R0 evidence only. The R1 documentation gate is satisfied by manifest
`785b394c3bcdc59f80c9d7a718a45d61da7f5ef9ee108466b01a4469c6541e1f`. The resulting E1
implementation closeout is frozen at remediation-03 manifest
`a68c5897717e0e3ee735af6a95ff768c59951338dff321aca9ab42bc662acfde` with independent
`ACCEPT`, P0=0/P1=0. Its immutable closeout SHA
`f1a40d69f301ad7f594a61f202d3bd380607b98a` then passed run `31089203210` (#726) on both
supported Python jobs. The accepted R7 contract remains retained evidence. The ratified
R2--R11-plus-R11-R1 composite, whose R11 base and R11 R1 correction are
`00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d` and
`d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9`, controls the filed pure-E2
`WO-0151` implementation closeout. Its exact remediation manifest
`2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853` received final independent
`ACCEPT`, P0=0/P1=0/P2=0. External exact-head CI remains the sole effectiveness gate; WO-0152
remains DRAFT/inactive. M2 and every runtime/persistence/cutover slice remain inactive.

Historical E1 amendment (2026-08-05): the original REV-0057 successor is retained historical evidence.
WO-0150's narrower R1/E2 boundary contract is independently accepted at P0=0/P1=0. E1 is limited
to identity data, immutable view/inert-reader shapes, and direct venue correlation. Registry/index
population, serial routing, and late-fact mutation remain future E2 obligations. This changes no
ADR and, at that time, did not activate WO-0151/WO-0152 or grant runtime, persistence, database,
broker, credential, or M2 authority.

Current R1 clarification: identity validation is wire-shape only; semantic predecessor/currentness
admission remains E2-only. The acquisition module has a narrow exact export set while the existing
package root remains broader. Venue correlation is a current-book-derived output-only projection,
not a standalone authority object; future E2 must obtain it by re-querying the authenticated current
book inside its composite transition. Replacement-02 manifest
`785b394c3bcdc59f80c9d7a718a45d61da7f5ef9ee108466b01a4469c6541e1f` is accepted; E1 then
proceeded under its active work order and is now effectively closed.

Current E2 R10 re-gate (2026-08-06): R10 independently accepted the narrow
exact-immutable-replay clarification at P0=0/P1=0/P2=0 and received exact user ratification.
Manifest `f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b`,
contract `081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3`, and
result `dd91f3a1403658cf116767c534ad080daf47acc23458e899c6431db290d6c431`
control only pure E2 WO-0151. R8 is retained ratification provenance; R9 is retained but is
not a ratification basis. The exact R10 re-gate documentation SHA is
`638c73cff1e02a8834309362cc5dc762b165871b`; R10 remains a contract, not proof of runtime
behavior.

Current E2 R11 R1 re-gate (2026-08-06): the initial R11 static review found one P1 because
cancel-only BUY preemption was coupled to protective-SELL goal eligibility. R11 R1 separates the
private `PREEMPT_BUY_ONLY` intent from the separately goal-bearing protection-exit intent. Exact
R11 body `00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d`, R11 R1 body
`d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9`, manifest
`e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8`, and fresh independent
result `c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b` (`ACCEPT`,
P0=0/P1=0/P2=0, affirmative route completeness) now control only pure E2 WO-0151. The initial
R11 `BLOCK` result is retained negative evidence and is not an acceptance basis. This re-gate adds
no runtime, database, SQL/DDL, broker/network, credential, M2, merge, deletion, cleanup, rebase,
force-push, or later-work-order authority.
The exact documentation-only R11 R1 re-gate SHA is
`8ebe9350520e28409c33c28cc958ee926639f28e`.

Current E2 implementation closeout (2026-08-07): the complete pure implementation is frozen by
remediation manifest `2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853`.
The first independent implementation review remains retained `ACCEPT-WITH-CHANGES` evidence; its
sole current/retired FILL/CORRECT/BUST matrix and mutation-evidence P1 was corrected at the owner
boundary. The focused final result
`96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd` accepted the exact
candidate at P0=0/P1=0/P2=0 after an independent 1,353-test pure run and 17/17 focused controls.
The local closeout is filed, but unchanged Python 3.11 and 3.12 CI on its immutable commit remains
required before effective `CLOSED` status or any WO-0152 activation. No prohibited local R2,
database, runtime, broker, network, credential, M2, merge, deletion, or cleanup result was used.

## Cleanup posture

WO-0153's documentation/evidence reconciliation and approved branch retirement are complete as far
as the filesystem permitted. Its exact outcome is `PARTIAL CLEANUP - DEFERRED TARGETS REMAIN`: five
unregistered worktree remnants, 55 root cache directories, and ten generated fixture files remain
because exact direct deletion returned `AccessDenied`. This does not activate WO-0150 through
WO-0152, M2, runtime wiring, persistence, broker/network activity, or master landing.
On 2026-08-06, only `WO-0154` was activated to retry those exact environment-controlled residuals
through a frozen literal allowlist and component-wise filesystem controls. It adds no implementation
or product authority.
The fixture and root-cache portions are now complete, but `WO-0154` is in `REVIEW` with a documented
blocker: five residual paths are unregistered full worktree remnants, so their cache-only removal
condition is false and their fallback branches remain retained.
The later bounded standard-Git repair re-gate reconciled exact checkpoint/local/live reset SHA
`3da1dc381827d4ab7812925d085dce3388c791a7` and all five fallback tips, but every remnant lacks both
a `.git` marker and corresponding `.git/worktrees` administrative metadata. Each is therefore
`DEFERRED — METADATA UNAUTHENTICATED`, not eligible for repair/removal; no branch is eligible for
deletion. This is `PARTIAL CLEANUP — MANUAL RETIREMENT STILL REQUIRED`, not an M1, master, or
successor-work authorization.
The user has now authorized a new `WO-0154` manual-retirement pass for only those five literal
full-tree roots and their matching local fallback branches. It requires a new documentation-only
live baseline, one-target critical preflight, component-scoped nonrecursive access repair only if
needed, exact-root deletion, and normal (`git branch -d`) branch retirement only after matching-path
absence. It does not authorize a branch force-delete, remote operation, metadata reconstruction,
fixture/cache retry, or any product work.
That manual pass reached the required access gate on all five rows but could not read the named
protected cache child or obtain its ownership with the only authorized nonrecursive command. No
full-tree or branch deletion was therefore eligible. WO-0154 returned to `REVIEW` as
`PARTIAL CLEANUP - ACCESS REPAIR FAILED`.
In a later elevated, exact-root pass, `.claude/worktrees/codex-lane2-bootstrap` and
`.claude/worktrees/codex-lane2-docs` were independently retired after fresh complete inventories;
all five local fallback branches remain retained at their frozen tips. The user has authorized only
one three-stage, stop-on-first-failure serial batch for the remaining three literal roots. Every
stage retains the per-root preflight and confirmation requirements; no branch force-delete, remote
operation, metadata change, product work, or other cleanup target is authorized.
That batch completed: all five frozen unregistered full-tree roots are now absent, while all five
fallback branch refs remain retained at their frozen tips. WO-0154 remains `REVIEW` only for a later
separately authorized branch-retirement decision; it adds no M1, master-landing, implementation,
runtime, persistence, broker/network, credential, database, or M2 authority.

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
  activated after their predecessor gates. `WO-0145` through `WO-0148` are effective `CLOSED`.
  WO-0150 is effectively `CLOSED` after exact-head Python 3.11/3.12 CI. WO-0149 is formally
  SUPERSEDED; WO-0151 alone is active for pure E2 implementation, while WO-0152 remains DRAFT.
  Runtime wiring, persistent database work, broker/network activity, credentials, M2, merge,
  deletion, and cleanup remain outside current authority.

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
- 2026-08-05: Immutable WO-0148 closeout `2462fb557172dd28a7475a763eca0b440c0298e3` passed
  GitHub Actions push run #693 (`30996686588`): Python 3.11 job `92275345844` and Python 3.12 job
  `92275345943` both concluded `SUCCESS`. This satisfies its external effectiveness gate; failed
  #691 remains negative evidence only. Activated only the frozen, pure-M1E WO-0149 specification
  after `REV-0052` exact-candidate review and addendum returned `ACCEPT` with P0=0/P1=0. No
  application/test implementation or operational authority was added.
- 2026-08-05: Ameen approved the exact REV-0056 R3 serial acquisition-generation architecture
  candidate: ADR-020 R2 eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653,
  ADR-021 R2 b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c,
  manifest d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c, and independent
  static preflight c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9
  (ACCEPT, P0=0/P1=0/P2=0). The approval permits documentation reconciliation and three
  DRAFT-only M1E candidates, not their activation or implementation. No operating boundary changed.
- 2026-08-05: Ameen formally superseded WO-0149 solely because the ratified R2 ADRs replace its
  one-lifetime same-symbol premise. All artifacts remain retained evidence; WO-0150 through WO-0152
  remain DRAFT/inactive. No application/test, database, runtime, broker/network, credential, M2,
  merge, deletion, or cleanup authority was added.
- 2026-08-06: WO-0153 completed the authorized cleanup's reconcilable scope: retained the
  superseded WO-0149 partial source/test artifact outside active paths, reconciled current posture,
  deleted eleven exact live remote refs, nine local branches, four worktrees, and measured generated
  files. Filesystem `AccessDenied` retained five worktree remnants, 55 root cache directories, and
  ten generated fixtures; no ACL/ownership or other bypass was attempted. WO-0150 through WO-0152
  remain DRAFT/inactive.
