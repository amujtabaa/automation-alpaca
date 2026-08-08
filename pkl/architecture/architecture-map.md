---
type: Module Knowledge
title: Architecture Map (reset target and frozen Spine v2 evidence)
status: active
authority: high
owner: Ameen
last_verified: 2026-08-07
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
(#726) on Python 3.11 and 3.12 and is effective `CLOSED`. WO-0151's pure-E2 implementation is
locally closed at remediation manifest
`2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853`; final independent result
`96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd` returned `ACCEPT`,
P0=0/P1=0/P2=0. Exact-head run #741 passed the functional/static gates and all 5,934 tests but
failed only the unchanged 93% coverage threshold at 91.34%; WO-0151 remains effectively `REVIEW`
 pending paired E2/E3 exact-head closure. WO-0152 is ACTIVE only for its test-only E3 proof layer
 after exact R2-R3 independent `ACCEPT`, P0=0/P1=0/P2=0, at
 `8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59`. Its first R1 preflight retained P1=2; R1 remediation 01
 corrected those two gaps but independently retained P1=1 for a pre-bootstrap sibling-history
 authority bridge outside the two-fixture allowlist. The user then authorized bounded in-flight
 resolution: the initial R2 candidate and R2-R2 candidate are retained unaccepted, while R2-R1 is
retained `ACCEPT-WITH-CHANGES` evidence with P1=1. R2-R3 accepted the same extension of the
existing environment fixture plus a bounded public-materialization tripwire with coherent inherited
fixture exceptions. Documentation-only activation preceded the first E3 test source. The active
R2-R4 re-gated only the nonconstructible fixed A/B/C one-mint fixture with a
statically bounded fixed 32-entry pre-genesis schedule, but independently
retained one P1 because that positive schedule cannot itself mint the distinct
sealed duplicate-stream probe. R2-R5 replaces only that probe construction
and independently `ACCEPT`ed at P0=0/P1=0; documentation-only acceptance
commit `ef5e53a5d49e189942545f52b7784ad7648fbf28` is reconciled below before
remaining E3 test work resumes.
 All three named setup fixtures and the boundedness tripwire remain test-only and grant no
 production authority. All M2/runtime/persistence work remains inactive.

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
WO-0151's locally verified implementation closeout is the sole product of the
R2--R11-plus-R11-R1 composite. Its exact-head run #741 is functional/static success but
 coverage-only negative evidence; the unchanged 93% gate is deferred to paired E2/E3 closeout.
 WO-0152 is ACTIVE only for its named test-only scope after R2-R3 independently accepted the bounded
 sibling-history extension, public boundedness tripwire, and inherited fixture limits. Its remaining
 E3 work may resume after the R2-R5 documentation-only acceptance commit
 `ef5e53a5d49e189942545f52b7784ad7648fbf28` is reconciled; M2 and all
 runtime/persistence work remain inactive until their applicable gates.

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
  E2 is now locally implemented and independently accepted under the ratified R2--R11-plus-R11-R1
  composite. Run #741 established functional/static exact-head success but coverage-only failure,
   so E2 remains effectively `REVIEW`; E3 is ACTIVE only for its test-only scope under the narrow paired-closeout
   amendment after R2-R3 independently accepted the bounded sibling-history bridge and public
   boundedness tripwire. No runtime, persistent database, broker, credential, or M2 authority is
   granted.
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
- 2026-08-07: The retained WO-0152 R1 remediation 01 result exposed a test-only pre-bootstrap
  sibling-history handoff gap. The authorized R2 correction is limited to the existing serving
  environment fixture: one fixed public OTHER-symbol lifecycle and one post-guard copied-authority
  `venue` installation from its final public transition. It represents the deferred M2 adapter
  composition boundary without adding production/public authority. R2 remains DRAFT/preflight-only;
  no E3 implementation begins without exact independent P0=0/P1=0 `ACCEPT`.
- 2026-08-07: The first R2 packet was stopped before independent verdict because the work order's
  future gate still named the superseded R1 acceptance. R2-R1 corrects only that current lifecycle
  reference and preserves the same R2 test-only sibling-history bridge. It remains DRAFT/preflight-
  only until exact independent P0=0/P1=0 `ACCEPT`; no implementation or production authority was
  added.
- 2026-08-07: R2-R1 independently returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0 for stale
  current PKL activation wording. The direct boundedness audit additionally required an explicit
  public-only materialization tripwire, including `VenueRecoveryBook.effect`, to make E3's
  boundedness proof failure-capable. R2-R2 corrects only those current/posture and static test
  proof gaps; all R2/R2-R1 sibling-history, fixture, public-API, and safety boundaries remain
  unchanged. WO-0152 stays DRAFT until exact independent R2-R2 P0=0/P1=0 `ACCEPT`.
- 2026-08-07: R2-R2 was stopped before independent verdict because its broad static prohibition
  contradicted inherited exact fixture exceptions and mistyped the public ordered fact reader.
  `result-r2-r2.md` remains absent. A source-level adjudication confirmed that public
  `VenueRecoveryBook.effect` remains trapped because it materializes retained contradiction
  history. R2-R3 corrects only the coherent lexical exception table and the fourteen-property/
  two-method trap shapes; all R2/R2-R1 semantic and safety boundaries remain unchanged. WO-0152
  stays DRAFT until exact independent R2-R3 P0=0/P1=0 `ACCEPT`.
- 2026-08-07: Exact R2-R3 contract
  `881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936`, manifest
  `ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`, and independent result
  `8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59` independently ACCEPTed at
  P0=0/P1=0/P2=0. WO-0152 is active only for the one named test-only E3 proof layer after its
  documentation activation SHA is recorded; WO-0151 remains REVIEW pending paired 93% exact-head
  closure. No production/API, runtime, database/SQL/DDL, broker/network, credential, M2, merge,
  deletion, cleanup, force-push, or rebase authority was added.
- 2026-08-07: Documentation-only WO-0152 activation SHA
  `a3ceee237d8635f280bd6f200f492bef919170f9` is the exact queue-to-active lifecycle commit and
  contains no source/test implementation. Normal push reported success; the later live `ls-remote`
  query could not acquire Windows credentials, so no independent live-ref claim is made. E3 test
  work remains barred until this SHA reconciliation itself is committed.
- 2026-08-07: After the R2-R3 activation, the first public E3 controls established only a retained
  local baseline. The one-lexical-mint/no-loop fixed A/B/C fixture is nonconstructible for distinct
  sealed A/B/C bindings and for the ADR-required 32-generation no-market-stream-reuse proof.
  R2-R4 replaces only that test-only configuration rule with one fixed literal 32-entry
  pre-genesis schedule and one statically bounded mint loop. It preserves every R2-R3 environment,
  terminal, boundedness, provenance, and safety rule; remaining E3 implementation awaits a fresh
  exact independent ACCEPT at P0=0/P1=0.
- 2026-08-07: Independent R2-R4 result
  `48079e3b54beedddbb56382de2b05f49e6f887e2173c17d24e6131de0bce1889` returned
  `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. Its positive 32-mandate schedule remains bounded and
  retained, but cannot build the distinct sealed A-stream-reuse probe needed to isolate the
  no-reuse rule. R2-R5 adds only one fixed zero-argument pre-genesis test fixture and one
  separately bounded literal mint for that probe. The 32-entry schedule, all R2-R3 safeguards,
  M2/runtime exclusions, and paired E2/E3 unchanged 93% closeout remain controlling; further E3
  implementation awaits exact independent R2-R5 ACCEPT at P0=0/P1=0.
- 2026-08-07: The exact R2-R5 packet independently `ACCEPT`ed at P0=0/P1=0/P2=0: contract
  `79c734b7c0a929d43aeca83ef00e797b7afc8d97754eb30f1c812b1dd5b3221e`, manifest
  `3fbcffbec46dd43248a1a8b569df39880c96e9d539d5a84a07cf58fde19be946`, and result
  `f3c86daa71a36108bb2757f853d922e992c7c77eed4d7d7626b5e9091e3d5245`. The docs-only
  acceptance publication and exact SHA reconciliation precede further E3 test work. The accepted
  probe provides a public detector for an E2 stream-ownership disagreement; it creates no E3
  production authority. M2/runtime exclusions and paired E2/E3 93% closeout remain controlling.
- 2026-08-07: Documentation-only commit
  `ef5e53a5d49e189942545f52b7784ad7648fbf28` published the exact R2-R4/R2-R5
  packet. This append-only current-posture reconciliation permits only the active R2-R5 test
  module scope to resume; it changes no production architecture or M2 boundary.
- 2026-08-07: R2-R5's first public A -> B -> fresh-binding-with-A-stream control exposed an E2
  implementation nonconformance: `GenerationRegistry` keeps direct generation records but no
  immutable controller-lifetime MarketStreamGenerationId ownership route, while successor admission
  compares only against B. The exact failed trace is retained in
  `work/review/REV-0059/evidence.md` SHA-256
  `d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`. WO-0152 is ACTIVE but
  implementation-paused at FR-08. WO-0151 R12 must install one sealed private direct stream-to-
  generation provenance sub-index in GenerationRegistry and preserve it across record replacement;
  no new ADR, controller history, authority duplicate, public reader, or runtime/persistence scope
  is allowed. R12's fresh independent acceptance gates resumption of E3 and the paired 93% closeout
  remains unchanged.
- 2026-08-07: WO-0151 R12's exact stream-provenance RED contract independently ACCEPTed at
  P0=0/P1=0/P2=0 (contract `36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e`,
  manifest `a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0`, result
  `0bd78212be49059fcc87ae02e23d08867c99944bf21ca1bf92af596612a99ac5`). It confirms the root
  repair belongs in GenerationRegistry: one private sealed direct stream-to-generation route map,
  no public reader, controller history, authority duplicate, or scan. R12 source/test work remains
  barred until a docs-only activation plus exact SHA reconciliation; E3 remains paused through its
  later independent implementation acceptance and the paired 93% gate remains unchanged.
- 2026-08-07: R12's original semantic freeze intentionally remains immutable. The post-freeze
  status/provenance entries are instead governed by a separately reviewed activation-delta manifest
  whose only possible follow-on is substitution of the first documentation activation SHA in exact
  named fields. This avoids silently treating changed live posture as part of the prior semantic
  review. The owner and architecture stay unchanged: one private GenerationRegistry route map,
  no public reader, duplicate authority, controller history, or scan; E3 remains paused.
- 2026-08-07: The independently accepted records-only activation delta (manifest
  `59ab3d16a4057fe2d3e763d5909ba1751ba0266453551ba07830b2c872bb68f4`, result
  `b8382a504c8bb9ac5456067e758a81ec42f9f546ed6194fae4f31b814378e28d`) is published at
  `a124b3cda866e2a5aaf99d4527e7b231dd4f675d`. It activates only the frozen R12 E2 repair path;
  the GenerationRegistry remains the sole owner, and WO-0152 remains paused until focused R12
  implementation acceptance and public detector confirmation.
