# REV-0075 R7 test-critic result

Exact candidate reviewed: `a6c687a399d3e4c547eefa7b10ce090af83b9789`, tree
`31da5be0bc5028bd761dc902e27d095aa436f577`.

## P1 — Expected wire control aliased production codecs

Location: `tests/execution_core/test_protection.py:9831` and `:9836`.

The expected mapping called the production policy and optional-M1 encoders.
Live mutations of those encoders left the component test green, admitting a
second wire grammar. Build the policy and optional-M1 values from independent
contract-defined literals and add alternate-wrapper rejection controls for each
affected optional slot.

## P1 — Real-state corpus missed valid fixed-field values

Location: `tests/execution_core/test_protection.py:9869` and `:9964`.

Every selected state used `raw_quantity=4`, `formula_available=True`, and
false halted/exhausted flags. Hardcoding those values passed the component
test. Extend the corpus with ordinary reducer routes for zero/flat,
formula-unavailable/hard-bail, halted, and exhausted states, then assert the
observed values.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=2, P2=0.

Unverified: broader cross-module pure suites, mypy, and import-boundary checks.
SQLite, DDL, network, and runtime composition were not invoked.
