# REV-0058 R8 pre-flight result

Status: **ACCEPTED PRE-FLIGHT EVIDENCE -- DOCUMENTATION ONLY**

## Exact candidate

- Branch / reviewed HEAD: `codex/arch-reset-2026-07-r1` at
  `832e0b8784c15c08f26584cb69a07ff6aa79b4b8`.
- Candidate base: `f1a40d69f301ad7f594a61f202d3bd380607b98a`, confirmed as
  an ancestor of reviewed HEAD.
- R8 contract SHA-256:
  `d6a0295f14652222d9fa05e1f826e77ecd306c07dbf1b8faf4525976396eec1f`.
- Review request SHA-256:
  `1837d5792d27a869c3d769785827aaa8d3b273a2536b164b551a65a58bc6adcd`.
- Candidate manifest SHA-256:
  `b6faddc624a227382f80ebefe57044ce2e2e372328df3528e027fc4bcd924311`.

All 20 manifest-listed hashes matched before acceptance. The manifest excludes
itself and this result, as intended. The review used static source/document
analysis only; no source/test/ADR/work-order/PKL/ledger/lifecycle file changed
during review, and no test, runtime, database, broker, network, or CI work ran.

## Result

**ACCEPT — P0: 0, P1: 0, P2: 0.**

Two independent static re-derivations compared the exact R2+R3+R4+R5+R6+R7+R8
composite with the accepted ADRs, WO-0151, retained evidence, and the current
E1 authority/venue/position seams.

1. The sealed, direct bootstrap-bound target record and neutral venue checkpoint
   make the otherwise invalid bound-with-zero-effect state finite, explicit,
   and mutually authenticated. The record is target-local, has no effect/owner/
   claim/operation/protection authority, and is disjoint from ordinary effect
   scopes.
2. The private bootstrap transition binds an exact flat target at the authentic
   account registry high-water, including the exact empty-account case, without
   a history scan, dummy effect, caller-selected identity, or public projection
   route. The R7 retained-target predecessor condition is replaced only for this
   one unbound disposition; all other source-freshness controls remain required.
3. The shared exact pair/venue-view predicate authenticates the bootstrap
   transition and permits only the first specialized request to consume its
   active record. After initialization, a fresh ordinary `CURRENT` or
   `REFRESHED` handoff is required before the first specialized BUY.
4. The initialization composite commits the sealed handoff and its one venue
   transition alongside the ordinary bootstrap registration receipt without
   falsely attributing the venue transition to that receipt.
5. `CreateBrokerEffect(BUY)` remains refused both before and after initial
   registration while the bootstrap-bound record is active. Generic catch-up,
   raw unbound snapshots, caller-built records/results, manual flatten,
   preemption, exit, and all later lifecycle reuse remain fail-closed.

The candidate is an internal WO-0151 implementation clarification, not a new
market, policy, or public authority decision. This acceptance freezes the RED
contract only. It does **not** activate the R8 contract, authorize implementation
or test implementation, change the active work-order authority, or authorize
runtime, persistence, database, broker, network, M2, merge, deletion, or
cleanup work.
