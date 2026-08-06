# WO-0150 RED-contract correction 01

[FABLE • FULL • verification: DIRECT plus independent recheck • task: WO-0150 RED contract]

fable_fix:
  symptom: "The first exact-commit preflight found mutable current economics/class data in immutable lineage route views."
  root_cause: "The route projection did not distinguish permanent source-to-generation provenance from the one replaceable generation record."
  evidence: "REV-0057/result.md P1 at contract lines 125-130, 175-188, and 206-214."
  fix: "Store only immutable route kind/source commitment/generation in AcquisitionLineageIndex; resolve current head/class with one direct GenerationRegistry lookup. Freeze a universal direct root-correlation map for broker-correlated human roots."
  regression_test: "The RED contract requires many A routes followed by late correction/bust with route rewrite/iteration traps and explicit broker-correlated-root coverage."
  red_green_verified: false
  attempt: 1

## Preserved predecessor evidence

The independent `ACCEPT-WITH-CHANGES` result in `result.md` is retained unchanged. It found
P0=0, P1=1, P2=0 for exact candidate
882dbc922fc2611f685344a06f12992840c1143a. It is negative evidence for the original contract and
cannot be used as acceptance of this corrected successor.

## Exact correction

1. An AcquisitionLineageIndex route now stores only immutable route kind, source commitment, and
   AcquisitionGenerationId. Its public lookup is followed by exactly one direct registry record
   lookup for mutable head/class state.
2. A late fact must update only the routed generation record and append its one fact binding; it
   cannot rewrite every historical route held by the generation.
3. Venue correlation is backed by a dedicated direct root-correlation index that includes every
   canonical broker root admitted to E1, including broker-correlated human coverage. It is a
   provenance index, not a substitute for the existing canonical correction/bust validation.

No architectural decision, production code, test code, runtime behavior, database work, broker
activity, cleanup, or operating authority is added by this correction.
