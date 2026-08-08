# REV-0058 R8 focused pre-flight request

Status: **REVIEW -- documentation-only candidate**

Review only the exact immutable candidate set recorded in
`WO-0151-RED-CANDIDATE-R8-MANIFEST.md`. Do not edit source, tests, ADRs, work
orders, PKL, ledger, lifecycle records, or candidate files. Do not run runtime,
database, broker, network, or CI work.

## Objective

Determine whether R8 closes the unbound-target first-generation feasibility gap
without weakening the accepted serial M1 architecture, full-input provenance,
or bounded owner-side authority. The candidate must establish one
zero-economic, authenticated target registry/binding projection before first
controller initialization; it must represent that temporary bound/no-effect
state through one sealed direct record and neutral venue checkpoint proof, not
a target-only serving shortcut, dummy effect, or second acquisition route.

## Required checks

1. Verify every manifest hash and current branch/base relationship before
   reasoning. Treat the listed source/test WIP as excluded from this
   documentation-only review.
2. Re-derive the composite from ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151,
   R2-R8, retained R0-R7 results, and the named E1 authority/venue/position
   seams.
3. Confirm the public surface remains one opaque authority-owned
   `AcquisitionContextRefresh` result with no caller factory, raw venue book,
   raw map, raw projection, input ID, or namespace route.
4. Statically exercise these cases:
    - exact empty-account target genesis creates one retained flat target binding,
      one active bootstrap-bound record, and one zero-economic neutral checkpoint
      transition before controller initialization;
   - a current bound same-account other-symbol source establishes the target at
     the source registry high-water without an account-history scan;
    - the returned target satisfies ordinary full binding/registry/reconciliation
      currentness, while a raw unbound target flat snapshot on a nonempty account
      remains non-serving and no generic bound/no-effect state becomes valid;
    - controller initialization alone may consume `UNBOUND_BOOTSTRAP`, after
      which the first specialized BUY requires a fresh normal `CURRENT` or
      `REFRESHED` result;
    - generic `CreateBrokerEffect(BUY)` refuses the target both before and after
      initial registration; only the specialized first-request route may consume
      the active bootstrap-bound record;
    - foreign, unbound, stale, non-prefix, unresolved, copied, target-bound,
      target-active, manual-flattened, preempted, exit-pending, or
      target-substituted source/result cases fail closed;
   - generic `CatchUpExecutionRegistry` remains unbroadened for unbound targets;
     and
   - replay, duplicate bootstrap, changed source/target commitment, and use of
     the special result for successor, claim, preemption, exit, rebase, or BUY
     fail before mutation.
5. Confirm the bootstrap transition cannot create or change an effect, claim,
   permit, controller/currentness coordinate, `PositionProtectionState`, normal
   protection authority, canonical fact, aggregate position, or runtime/broker
   behavior. Its one neutral book-level checkpoint proof must authenticate the
   binding without becoming any of those things. Confirm the source remains
   immediate owner-side proof and is not retained in controller/currentness
   records.
6. Perform a disproof pass: test whether the proposed result shape has enough
   exact predecessor/current and transition evidence to authenticate the returned
   bound target, direct bootstrap record, and neutral checkpoint without
   exposing a private venue seam to acquisition.
7. Identify only concrete P0/P1/P2 findings. Do not add speculative concerns.

## Required result

Write `result-r8.md` in this directory only after the candidate is accepted or
rejected. Use concise requirement/evidence/impact/resolution entries and end
with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` plus P0/P1/P2 counts. An
`ACCEPT` requires P0=0 and P1=0; it authorizes neither activation nor
implementation.
