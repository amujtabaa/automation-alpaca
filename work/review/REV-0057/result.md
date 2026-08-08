# REV-0057 — WO-0150 RED-contract independent preflight result

## Candidate and static evidence

- [reproduced-static] `HEAD` is exactly
  `882dbc922fc2611f685344a06f12992840c1143a`; its parent is
  `ceb614a8ea90766f62d5d8240ab34d2cd961099b`.
- [reproduced-static] `git log --diff-filter=A --format=%H --reverse --
  work/review/REV-0057/WO-0150-RED-CONTRACT.md` returned only
  `882dbc922fc2611f685344a06f12992840c1143a`, so the target is the commit
  that first contains the contract.
- [reproduced-static] The candidate delta is exactly:
  `A work/review/REV-0057/WO-0150-RED-CONTRACT.md` and
  `A work/review/REV-0057/request.md`. `git diff --check` against its parent
  was clean.
- [reproduced-static] SHA-256 checks of the two authority bodies match the
  WO pins: ADR-020 R2 is
  `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653` and
  ADR-021 R2 is
  `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c`.

### [P1] Make current generation state a direct registry join, not mutable route state

- Location: `work/review/REV-0057/WO-0150-RED-CONTRACT.md:125-130`,
  `work/review/REV-0057/WO-0150-RED-CONTRACT.md:175-188`, and
  `work/review/REV-0057/WO-0150-RED-CONTRACT.md:206-214`
- Requirement: WO-0150 FR-05 through FR-07 and NFR-01 require one replaceable
  economics head per bounded `GenerationRecord`, direct immutable lineage,
  and no live transition work that scans retained request/effect/owner/root/fact
  history. ADR-020 R2 §3-4 likewise requires a directly indexed replaceable
  head and root/effect/owner lookup without controller traversal or history
  materialization.
- Evidence: [reasoned-static] `GenerationRouteView` exposes
  `economics_head_commitment` and `serving_class`, while the contract calls
  lineage bindings immutable and separately says a late fact updates only A's
  record/head. The text does not state that the index persists only immutable
  `source -> generation_id` routing and that each returned route view obtains
  the current head/class through one direct `GenerationRegistry` lookup. The
  stated long-serial boundedness control does not exercise a single generation
  with many routes followed by a late correction/bust, nor trip iteration or
  replacement of those routes.
- Why it matters: A conforming-looking GREEN implementation could either leave
  route views stale after A's economics/class changes or rewrite every A route
  to keep the copied fields current. The latter makes a late fact scale with
  A's retained request/effect/owner/root/fact bindings and violates the
  no-history/constant-transition rule; the former can expose stale lineage
  economics for a valid retired-generation fact.
- Resolution: Freeze the stored lineage binding as the immutable route kind,
  source commitment, and `AcquisitionGenerationId` only. Require
  `route_*()` to form its public current head/class fields by exactly one
  direct registry-record lookup (mismatch or absence is reconciliation-only),
  never by copying or rewriting every route. Add a RED control with many A
  bindings followed by an A correction/bust that traps lineage iteration and
  route replacement, proves the returned A view has the new head/class, and
  proves B/C remain unchanged.

## Other material questions

- [reproduced-static] No P0 provenance or scope defect was found: the exact
  candidate is documentation-only and its two-path delta matches the request.
- [reasoned-static] The identity coordinate order, exact 32-byte commitments,
  first-controller genesis rule, opaque E2 commitments, and fail-closed
  refusals in `WO-0150-RED-CONTRACT.md:37-66` trace to ADR-020 R2 §2 and
  ADR-021 R2 §2 without introducing a caller authority constructor.
- [reproduced-static] `app/execution_core/venue.py:4258-4265` documents that
  `VenueRecoveryBook.effect()` materializes contradiction history, while the
  contract expressly prohibits that call and the other audit views at
  `WO-0150-RED-CONTRACT.md:31-35`. Existing direct root coverage helpers at
  `app/execution_core/venue.py:4396-4405` and the audit-view tripwire
  convention at `tests/execution_core/test_venue_binding_recovery.py:157-190`
  support the proposed no-history venue bridge. No additional venue-correlation
  finding is warranted on this static preflight.
- [reasoned-static] The public surface keeps admission, currentness,
  protection, effect eligibility, and sealed `AcquisitionLineageRelation`
  semantics outside E1; the contract's explicit E2 ownership and its
  failure-capable identity/no-fallback/private-access controls are sufficient
  except for the route-current-state ambiguity above.

## Intentionally not executed

- No application or test code was changed or executed: this is a
  documentation-only RED preflight and the proposed E1 surface is absent.
- No SQL/DDL, database initialization, credentials, broker/Alpaca/network,
  CI, commit, push, merge, deletion, or cleanup action was performed.

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0  
P1: 1  
P2: 0

Candidate SHA: `882dbc922fc2611f685344a06f12992840c1143a`  
Candidate path set:

- `work/review/REV-0057/WO-0150-RED-CONTRACT.md`
- `work/review/REV-0057/request.md`

WO-0150 may **not** advance to the explicitly authorized activation/RED
implementation gate until the P1 contract/control correction is made and this
exact-candidate preflight is repeated with P0=0 and P1=0.
