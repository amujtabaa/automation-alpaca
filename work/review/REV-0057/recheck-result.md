# REV-0057 — WO-0150 focused successor recheck

## Candidate and review boundary

- [reproduced-static] `HEAD` and the requested exact candidate are both
  `d54ffec4e0547be8fcff447d212e1afbebd4489f`; its direct parent is
  `882dbc922fc2611f685344a06f12992840c1143a`.
- [reproduced-static] The candidate path set is exactly:
  - `work/review/REV-0057/CORRECTION-01.md`
  - `work/review/REV-0057/WO-0150-RED-CONTRACT.md`
  - `work/review/REV-0057/recheck-request.md`
  - `work/review/REV-0057/result.md`
- [reproduced-static] The authority-body SHA-256 values still match the WO
  pins: ADR-020 R2 is
  `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653` and
  ADR-021 R2 is
  `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c`.
- [reproduced-static] This was a documentation-only recheck. The predecessor
  `result.md` remains negative evidence for the original candidate; this
  recheck independently evaluates only the corrected successor.

## Focused recheck

### [P0/P1: none] Immutable route provenance now has one direct current-state join

- Location: `work/review/REV-0057/WO-0150-RED-CONTRACT.md:125-131`,
  `:178-198`, and `:213-226`.
- [reproduced-static] `GenerationRouteView` now contains only route kind,
  source commitment, and `AcquisitionGenerationId`. The contract expressly
  prohibits a route from storing mutable economics/class, requires exactly one
  direct route lookup followed by exactly one
  `GenerationRegistry.record(route.generation_id)` lookup, and makes a missing
  or mismatched route/record reconciliation-only.
- [reproduced-static] The corrected boundedness controls require many A routes,
  a late A correction and bust, route-replacement/iteration tripwires, a single
  changed A record reached by the direct registry join, and unchanged B/C
  routes/classifications.
- [reasoned-static] This is the required separation in ADR-020 R2 §§3–4 and
  WO-0150 FR-05–FR-07/NFR-01: permanent source-to-generation provenance stays
  immutable, while the one bounded generation record owns the replaceable head
  and class. The prior stale-view/per-route-rewrite counterexamples are now
  excluded by both the frozen surface and failure-capable RED controls.

### [P0/P1: none] Root correlation now includes broker-correlated human roots without claiming revision-history proof

- Location: `work/review/REV-0057/WO-0150-RED-CONTRACT.md:158-174`,
  `:213-237`, and `work/review/REV-0057/CORRECTION-01.md:28-30`.
- [reproduced-static] The sole venue bridge is backed by one private direct
  `RootFillKey`-to-immutable-correlation map. It requires exactly one entry for
  every canonical broker root admitted to E1 correlation, explicitly including
  broker-correlated human coverage; the stored value is limited to immutable
  request/effect/leg/root provenance. The query is restricted to direct
  request/effect, owner, and root maps and cannot enumerate audit collections
  or call `_current_effect`.
- [reproduced-static] The correction separately states that this provenance
  index is not a substitute for canonical correction/bust validation. The RED
  mutation list fails an implementation that omits a broker-correlated human
  root from the direct map.
- [reasoned-static] This correctly addresses the existing seam: the legacy
  `VenueRecoveryBook` has direct root indexes for coverage but its
  broker-correlated-human helper is keyed by `ExecutionFactKey`
  (`app/execution_core/venue.py:4396-4424`), so it cannot be silently treated
  as universal root correlation. A dedicated immutable root map closes that
  gap without scanning coverage/history. Canonical correction/bust applicability
  remains the reducer's separate predecessor/head/tail validation
  (`app/execution_core/recovery.py:1171-1234`), consistent with ADR-020 R2 §3
  and ADR-021 R2 §5.

## Disproof and scope pass

- [reasoned-static] I attempted the two prior failure modes: copying mutable A
  head/class into each route and using an audit/coverage scan (or fact-key-only
  lookup) to correlate a broker-correlated human root. The revised stored-route
  shape, exact direct-join requirement, dedicated root-map requirement, and
  named tripwire/mutation controls reject each mode.
- [reproduced-static] No new E1 admission, currentness/controller decision,
  protection, effect-eligibility, persistence, runtime, broker, or source/test
  authority enters the documentation-only delta. The contract continues to
  reserve those semantics to E2 and fail closed on unresolved correlation.

## Intentionally not executed

- No application or test code was executed; the proposed E1 surface remains
  absent and this recheck is limited to static contract conformance.
- No SQL/DDL, database, broker/Alpaca/network, credentials, CI, commit, push,
  merge, deletion, or cleanup action was performed.

Verdict: **ACCEPT**

P0: 0  
P1: 0  
P2: 0

Candidate SHA: `d54ffec4e0547be8fcff447d212e1afbebd4489f`

WO-0150 may satisfy this independent successor-review precondition only; its
separate explicit human activation requirement remains in force.
