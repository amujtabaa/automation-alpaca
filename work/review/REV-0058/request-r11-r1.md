# REV-0058 R11 R1 focused route-completeness pre-flight request

Status: **REVIEW -- documentation-only replacement candidate**

Review only the exact immutable set recorded in
`WO-0151-RED-CANDIDATE-R11-R1-MANIFEST.md`. Do not read or rely on author
working notes or conversation history. Do not edit source, tests, ADRs, work
orders, PKL, ledger, lifecycle records, candidate files, or retained evidence.
Do not run application, test, database, broker, network, or CI work.

## Objective

Independently determine whether R11 R1 closes the initial R11 preemption-intent
producer gap while keeping preemption cancel-only, SELL exit goal-bearing, and
every other R2-R11 route bounded and constructible under the accepted ADRs and
active WO-0151.

## Required method

1. Verify every manifest hash and candidate/base relationship. Treat current
   code/tests only as read-only feasibility context.
2. Read the accepted ADRs, active WO-0151, R2-R11, and R11 R1 in specification
   order. Derive the intended operation graph before reading the retained
   initial R11 result; use that result only afterward to check that its one P1
   is actually resolved.
3. Re-enumerate every remaining public operation and its bounded producer ->
   authenticated input -> consumer -> mutation owner -> result path. Identify
   stale, replay, wrong-owner, conflict, and partial-result behavior.
4. Disprove or confirm preemption producer totality for:
   - B with one unresolved unclaimed/cancellable BUY and no recovered market
     baseline when a late retired-A fact arrives;
   - an already-applied abnormal current first root;
   - halt, baseline-required, exhausted, or formula-unavailable protection;
   - standalone current preemption; and
   - replay, wrong context, false waiting, wrong provenance, claimed/unknown
     work, duplicate cancellation, and stale-head cases.
5. Confirm the preemption-only intent can authorize only safe BUY stand-down or
   one bounded cancel and can never create/claim SELL, serve as a goal, or
   bypass authority's final currentness/ownership checks.
6. Disprove or confirm the separate protection-exit producer after exact BUY
   closure. Require a current authentic goal-bearing transition and exact
   state/context/terms. Test old, replay-only, goal-less, copied, altered,
   baseline/halt/exhaustion, changed-head, and final-claim-race cases.
7. Test neutral sibling catch-up with sticky exit semantics: fresh raw state
   must preserve preemption availability without a goal; an old goal transition
   must remain stale; a fresh goal-bearing transition may serve SELL only when
   all protection and authority conditions are current.
8. Test combined retired-fact/preemption ordering and abnormal-first-root
   ordering for exactly one aggregate application, one head/currentness
   advance, at most one cancel, no second registration, and no partial result.
9. Recheck terminal A -> B -> C rollover, current/follow-on/reconciliation
   facts, semantic/neutral rebase, create/claim, direct provenance, final claim,
   and no-scan/no-cache boundaries. Flag any still-required public surface,
   private dependency, policy duplication, hidden state, or second writer.
10. Confirm the failure controls are capable of detecting each material rule
    removal and remain proportionate to realistic M1 lifecycle, capital-safety,
    concurrency, provenance, and maintainability risks.

## Required result

Write `result-r11-r1.md` in this directory only. Report findings with exact
requirement/evidence/impact/resolution and end with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT` plus P0/P1/P2 counts. An `ACCEPT` requires
P0=0, P1=0, explicit closure of the initial R11 P1, and an affirmative
route-completeness conclusion. It authorizes neither ratification nor
implementation.
