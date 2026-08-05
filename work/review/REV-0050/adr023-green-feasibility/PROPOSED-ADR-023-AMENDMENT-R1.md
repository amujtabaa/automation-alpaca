# Proposed ADR-023 amendment R1 — implementable bounded last-primary state

Status: **PROPOSED — exact human ratification required before application**

Controlling accepted ADR-023 SHA-256:
`898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259`

## Reason for the amendment

The immutable ADR-023 RED contract correctly requires maximum-step eligibility to compare an
incoming eligible BID or TRADE primary with the last eligible primary across market kinds. It also
freezes `_market_last_primary` as only the 32-byte SHA-256 commitment of that prior price. A digest
authenticates a value but cannot recover the numeric price required for the next comparison. The
exact state inventory permits no second retained price field. An honest GREEN implementation is
therefore impossible without a bounded representation correction.

The RED contract also requires `MarketOccurrence.occurrence_id` to be a dataclass result field with
`init=False`, while its import grammar rejects `dataclasses.field`. Python's standard dataclass
mechanism needs `field(init=False)` to satisfy that exact public shape. This is a test-grammar
omission, not a new architecture decision.

## Exact ADR-023 text amendment

In ADR-023 Section 3, replace this retained-state bullet:

> one optional last-primary-price commitment and at most one hard-bail bid, trade, and trail-bid
> identity with its paired source time; and

with:

> one optional exact last-primary `ReportedPrice`, retained solely for the next maximum-step
> comparison, whose existing canonical reported-price commitment is serialized as cursor part 13,
> and at most one hard-bail bid, trade, and trail-bid identity with its paired source time; and

No other accepted ADR-023 clause changes. In particular:

- the market cursor remains exactly 19 parts and 480 bytes;
- cursor part 13 remains the optional 32-byte canonical reported-price commitment;
- state and work remain constant in market-history length;
- no receipt map, history scan, raw-feed tape, or variable-cardinality market container is allowed;
- generation, mode, cursor ordering, baseline, invalidation, halt, exhaustion, and goal-suppression
  rules remain unchanged.

## Exact WO-0148 and RED-contract re-gate required by ratification

After ratification, apply only these root corrections before production implementation:

1. Retain `_market_last_primary` as exact `ReportedPrice | None`. Use it only for the next
   maximum-step comparison, and serialize only `_encode_reported_price(_market_last_primary)` into
   optional cursor part 13. Authenticate every nested price/tick leaf through the cursor digest.
2. Revise the exact state inventory, type/authenticity controls, known-answer plumbing, bounded
   histories, and relevant mutations to reflect the retained exact price. Preserve the existing
   cursor known-answer bytes where the represented prices are unchanged.
3. Permit only the canonical private import `from dataclasses import field as _field`, and permit
   only `_field(init=False)` as the class-level default of
   `MarketOccurrence.occurrence_id`. Continue rejecting every other `field` call, argument,
   default, default factory, alias, rebinding, or call site.
4. Add failure-capable controls for the exact permitted form and representative rejected forms.
5. Re-run the focused RED classification, predecessor suite, static/import/scope gates, and the
   one bounded independent exact-delta review needed to prove these two corrections. Freeze one
   replacement RED commit before any production edit.

## Authority and safety boundary

Ratification authorizes only this ADR-023 text amendment, matching ratification/active-WO/PKL
reconciliation, the two named RED-contract corrections, necessary review/evidence, and the already
authorized WO-0148 application/test work after the replacement RED gate passes. It grants no
runtime wiring, persistent application-database or direct database work, SQL/DDL, broker or Alpaca
activity, credentials, network activity, M2 implementation, master merge, deletion, or cleanup.
