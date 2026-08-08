# WO-0149 specification and activation preflight result

Review target: `work/queue/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md`

Target SHA-256: `A85192BDC18455FBE7D6E2EA6178DBAA76ABB14608987EB7B8F9F61BB782DBEF`

Activation base: `2462fb557172dd28a7475a763eca0b440c0298e3`

## Findings

No findings.

## Independent disproof result

Static re-derivation from AGENTS.md, the permanent safety core, ADR-020 through ADR-023, the
ratification index, the acquisition/domain contract, predecessor public contracts, and current
execution-core interfaces found the candidate complete enough for documentation-only activation:

- FR-03 closes the current generic `CreateBrokerEffect(BUY)` gap with one reducer-owned composite
  head registered in authority-owned state and rechecked at both creation and final claim. A
  caller-supplied seal or stale preemption state is expressly insufficient.
- FR-01 and FR-03 require distinct acquisition-owner and protection-authority identities plus the
  complete linked protection authority. They reject a single overloaded mandate ID, an ID-only
  comparison, and linkage hidden in `economic_scope`.
- FR-04 consumes the one opaque venue transition whose post-transition execution snapshot already
  contains canonical economics. Acquisition and protection advance together without a second fill
  fold or partial publication.
- FR-05 rejects direct `ProtectionTransition`, `ExecutionGoal`, boolean, closure, and copied-
  commitment authority. Preemption requires an opaque protection-owned projection matched to the
  authority-owned current composite head.
- FR-02 and FR-05 preserve exact broker-authoritative economics, terminal acquisition behavior,
  sticky exit policy, late-fill protection, multi-acceptance uncertainty, and exact parent
  `CLOSED` release. Net position and protection SELLs cannot restore acquisition capacity.
- FR-05 and FR-06 require a current-index active-leg projection with one-next-leg progression and
  explicitly prohibit every named venue audit materializer, private-state shortcut, duplicated
  fill/closure/formula reducer, and test-only authority seam.
- The Fable M1-M4 war-game identifies both missing current public seams as future implementation
  gates rather than claiming they already exist. The lifecycle table carries the irrevocable
  preemption/abort-required rule, and the RED contract includes direct-transition, stale-head,
  multi-leg, history-scan, cap, cross-side, and late-economic counterexamples.
- The pure M1 boundary distinguishes mandate ceilings from liquidity-dependent child-price or
  broker-syntax selection. It grants no human authentication, serving fence, claim, I/O,
  persistence, SQL/DDL, broker/network activity, runtime wiring, M2 work, merge, deletion, or
  cleanup authority.
- The allowed paths and stop conditions are consistent with a narrow new acquisition semantic
  module and directly necessary predecessor-interface seams. Accepted ADR bodies, fill/position
  reducers, persistence/runtime paths, CI workflows, and retained evidence remain excluded.
- Activation and implementation authority are unambiguous: the candidate remains
  `implementation_authority: NOT_GRANTED`, requires a separately authorized RED and implementation
  boundary, and makes exact implementation/review/CI evidence mandatory before closeout.

The current generic BUY path, constructible public protection transition, and absent exact
active-leg projection are real implementation hazards, but the candidate does not represent them
as completed behavior. It names each as a fail-closed implementation gate with negative controls
and stop conditions. No accepted-ADR conflict or new architectural decision is required to express
the specified bounded pure-M1 solution.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: none
