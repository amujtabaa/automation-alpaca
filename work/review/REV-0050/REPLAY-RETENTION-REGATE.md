# WO-0148 occurrence-receipt successor re-gate

`[FABLE - FULL - verification: DIRECT + stateful + mutation + independent review pending - task: durable market-occurrence replay authority]`

## Authority and finding disposition

The first exact production candidate,
`34eb7f4aeea96c60522c4a8ca1b4575de41ffa39`, received independent verdict
`ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0 in `result.md`. The accepted P1 showed that retaining only
the most recent market-occurrence identity allowed sequence-less `A -> B -> replay(A) -> C`
histories to rebuild either hard-bail or trail-exit corroboration. Reusing A's identity with a
changed payload after B was likewise not refused.

Ameen's continuing authorization to resolve every in-scope M1 P0/P1 permits this bounded repair
inside the existing WO-0148 allowed paths. It does not activate WO-0149 or M2, add runtime or
persistence wiring, grant broker authority, permit credentials/network activity, or authorize
merge, deletion, or cleanup.

## Owning invariant and root correction

Replay/equivocation authority now belongs to one immutable reducer-owned receipt registry:

1. `PositionProtectionState` retains an exact `_PersistentKeyMap` from occurrence-identity digest
   to canonical source-payload digest. The map's commitment is part of versioned state commitment
   `execution-core/position-protection-state/v3`, and state authentication requires the exact map
   type.
2. The identity is the adapter-stable `MarketOccurrenceId` within the already fixed mandate
   source/scope/session namespace. Wrong source, scope, session, and permanently older market
   epochs are rejected before reservation and cannot occupy that namespace.
3. The payload binds source, scope, session, market epoch, optional source sequence, source time,
   kind, quote/trade/ATR/structure values, and halt state. `evaluation_time` is delivery context,
   so changing it cannot turn an exact source replay into payload equivocation.
4. A previously seen identity with the same payload is an exact evidence no-op after any
   intervening history or restart. A previously seen identity with a different payload is refused.
5. Every unseen, well-routed occurrence is receipted before freshness, non-regression, halt,
   quote/tick, step, formula, or policy eligibility. Thus a stale, crossed, step-ineligible, or
   currently non-serving first delivery cannot later gain authority after context changes.
6. Receipts survive trigger changes, venue/economic projection advances, formula loss/restoration,
   halt, `FLAT`, late-positive recovery, and restart for the aggregate lifetime. Evidence counters
   may reset at their owning policy boundary; source identity history does not.
7. When a valid venue/economic projection advances in the same call, its economics remain applied.
   A replayed/equivocated optional market occurrence is suppressed and cannot erase the already
   earned projection result or goal.

No caller-shaped cache, compatibility exception, second transition path, or new public authority
was added. The registry reuses the predecessor's authenticated immutable persistent-map primitive;
`fills.py` remains unchanged.

## Test-contract reconciliation

The changed state shape exposed three test-oracle defects, all corrected at their owner:

- Contextually ineligible but well-routed occurrences now prove a receipt-only transition:
  commitment and receipt map change, while every economic, cursor, stream, evidence, policy, goal,
  and alert field remains inert. Wrong-route and older-epoch inputs still prove complete state
  equality.
- Canonical source attestation now recompiles an inspected function with the canonical module's
  import declarations and the function's deferred-annotation compiler flag. This matches Python
  3.11 imported-class method code generation without weakening bytecode comparison. A dedicated
  altered-source control and the prior source-swap controls remain failure-capable.
- Two generated-history rules now create genuinely unique occurrence identities and anchor the
  first cross-kind price to the current accepted primary before applying the intended oversized
  second step. The previous generators could accidentally exercise equivocation or make the first
  price ineligible.

## Failure-capable evidence

`REPLAY-RETENTION-MUTATION-EVIDENCE.md` preserves five independent fail/restore controls:

- latest-only retention: 4/4 intended failures, restored 4/4 pass;
- dropped ineligible receipts: 3/3 intended failures, restored 3/3 pass;
- cleared receipts on reducer resets: 3/3 intended failures, restored 3/3 pass;
- delivery evaluation time added to payload identity: 6/6 intended failures, restored 6/6 pass;
- receipt map removed from state commitment: 1/1 intended failure, restored 1/1 pass.

The deterministic and stateful contract covers non-last BID/TRADE replay, changed-payload reuse,
trail exit, restart, stale/crossed/step first delivery, formula loss/restoration, trigger ratchet,
halt, flat/late-positive recovery, and same-call venue advancement.

## Current pre-freeze result

- affected authority/protection/stateful/import: 495/495 pass;
- predecessor execution/venue/authority corpus: 745/745 pass;
- R2 conformance: 61/61 pass;
- complete execution core: 1,071/1,071 pass;
- full repository: 5,659 tests, zero failures/errors, 12 skipped;
- raw combined line/branch coverage: `93.14745457067555%`;
- Ruff, changed-file format, mypy, Python 3.11 grammar, six import contracts, diff, scope,
  Project OS governance, ratified ADR hashes, and all nine auxiliary worktrees: pass.

This is implementation-seat evidence, not acceptance. The exact successor must still be frozen,
reviewed independently with `ACCEPT` and zero unresolved P0/P1, closed out, pushed, and proved on
unchanged exact-head Python 3.11/3.12 CI before WO-0149 can activate.
