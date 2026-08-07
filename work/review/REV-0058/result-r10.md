# REV-0058 R10 independent static pre-flight result

Status: **INDEPENDENT STATIC REVIEW -- DOCUMENTATION ONLY**

## Exact candidate and integrity

- Reviewed HEAD / candidate base: `a95af72ee8d7a41f8e0b7859f5124c8a9e929548` on
  `codex/arch-reset-2026-07-r1`.
- R10 manifest SHA-256: `f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b`.
- R10 contract SHA-256: `081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3`.
- All 27 manifest-listed SHA-256 values matched: the four authority bodies,
  six retained-evidence artifacts, eleven exact R10 review artifacts, and six
  read-only feasibility-context files. The manifest intentionally excludes
  itself and this result.

## Findings

No P0, P1, or P2 findings.

## Independent re-derivation and disproof pass

- **Exact immutable replay is a value-equivalence issue, not object identity.**
  The existing protection projection authenticity check deterministically
  recomputes its seal from every sealed field
  (`app/execution_core/protection.py:907-1146`). The predecessor context is
  likewise a deterministic commitment of application generation, scope,
  scope-execution token, semantic protection token, and raw-source protection
  token (`app/execution_core/protection.py:764-788`). An exact immutable replay
  therefore proves the same narrow relation as its source; making the one
  read-only matcher reject it would require an identity or mutable replay
  mechanism outside the R9 boundary. R10 correctly replaces that infeasible R9
  requirement rather than adding one.

- **Altered, spliced, malformed, and substituted values remain non-serving.**
  R10 retains exact-type, fixed-width, owner-seal, semantic-kind, and component
  checks. A changed or field-spliced projection with its retained seal fails
  owner authentication; wrong-type, missing-component, and malformed input
  return `False`. For a valid semantic projection, the proposed matcher
  recomputes the predecessor context using the supplied semantic token in its
  semantic position and the sealed raw-source token in its distinct source
  position (R9 section 1, especially lines 43-56). Thus a distinct semantic
  token or a raw-source token substituted for it cannot reproduce the sealed
  predecessor context. A separately owner-authentic projection is not
  automatically current: R10 correctly sends its freshness decision to the
  composition route.

- **Neutral and stale cases remain separated.**
  `NEUTRAL_REPROJECTION` is excluded from the semantic predicate and remains
  governed by R7's refresh-owned authority-pair checks (R7:59-84). An authentic
  historical semantic projection may answer the narrow predecessor relation,
  but R6 requires a matching `CURRENT` or `REFRESHED` handoff, fresh target
  protection context, and immediate pre-mutation rechecks (R6:349-360). R9
  additionally retains exact application-generation, scope, scope-execution,
  venue, fresh authority/venue-context, and raw-protection comparisons
  (R9:64-71). A changed refresh, controller semantic commitment, or controller
  head therefore makes the semantic-rebase route non-serving before mutation.

- **Replay cannot become standalone registration, effect, claim, or authority.**
  R2 already confines currentness registration to four sealed sources and
  explicitly includes `PROTECTION_REBASE` (`WO-0151-RED-CONTRACT-R2.md:436-454`).
  Its rebase route rechecks controller and authority currentness and registers
  only the exact rebase outcome (`WO-0151-RED-CONTRACT-R2.md:504-512`). R10
  adds no source, registration type, authority input, controller state, effect,
  claim, factory, ledger, or cross-module dependency. After an accepted
  semantic rebase, the predecessor semantic relation and/or retained
  controller/refresh state is no longer the pre-state required by the replay;
  a repeated call cannot create a second registration or a new effect/claim.
  This preserves ADR-020's exact controller-head revalidation rule
  (`docs/adr/ADR-020-current-state-execution-kernel.md:95-103`) and ADR-021's
  one-controller/one-active-authority boundary
  (`docs/adr/ADR-021-position-protection-liquidity-execution.md:55-58`).

- **Scope and authority remain narrow.** R10 replaces only R9's impossible
  copy-rejection wording and its associated control. It introduces no policy
  decision, no alternate bootstrap or refresh path, no authority material in
  `protection.py`, and no change to canonical fact truth. That is consistent
  with the active work order's pure, I/O-free, single-writer boundary and with
  R7's lawful ownership split.

## Scope and unverified limits

This review independently read the active WO-0151, ADR-020 R2, ADR-021 R2,
ADR-023 R1, the immutable R2-R10 composite, retained R8/R9 evidence, and the
named E1 seams. The current source is feasibility context only: the requested
matcher is not implemented and `rebase_acquisition_protection` is currently
not admitted (`app/execution_core/acquisition.py:3047-3054`). No tests, runtime,
database, broker, network, or CI work ran. No implementation behavior,
ratification, or implementation authority is claimed by this result.

Verdict: **ACCEPT**

P0: 0
P1: 0
P2: 0
Unverified: Future implementation and failure-capable test execution of the R10 matcher and semantic-rebase route; both were intentionally outside this static pre-flight scope.
