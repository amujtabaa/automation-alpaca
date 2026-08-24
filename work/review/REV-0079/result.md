# REV-0079 independent review result

Date: 2026-08-24  
Review target: `2f16f52763add275892836b396f1f8b9decfd1f7`  
Target tree: `5adb2e2c266f9cb93145e670e993fb03156f9d83`  
Review range: `3b26c1cd636615cf0d85c13951eaebf099b88bdc..2f16f52763add275892836b396f1f8b9decfd1f7`

## Verdict

**ACCEPT-WITH-CHANGES — P0=0, P1=2, P2=0.**

Two fresh-context read-only reviewers independently inspected the exact target. Their
findings are recorded below without treating the later review-request commit as part of
the reviewed implementation target.

### P1 — Ownerless selected effects bypass full selected-scope binding

- Location: `app/execution_core/persistence/checkpoint_codec.py:3648`
- Requirement: R15 §2 / R17 §1 require proof-selected current state to equal its full
  selected relationship. Q4a can select an OPEN or INVALIDATED effect without Q5
  selecting an owner.
- Evidence: **reproduced-live** pure probe. A selected runtime effect with
  `VenueEffectScope.generation` changed to a foreign generation was accepted and
  serialized. The full-scope binder was used by owner paths but not effect-row encoding.
- Impact: an inert checkpoint can authenticate an effect under foreign
  application/scope coordinates.
- Resolution: call `_require_selected_effect_scope(...)` in the effect-row encoder
  before encoding and add ownerless-effect mutants for generation, position scope, and
  target leg.

### P1 — The source audit did not reject dynamic self-approval or late approval

- Location: `tests/execution_core/test_persistence_write_capability.py:1061-1075, 1169-1232`;
  `app/execution_core/persistence/schema.py:4763-4771`
- Requirement: WO-0168c requires a human-controlled static-only DDL gate with
  failure-capable controls; self-derived approval must be refused.
- Evidence: **reproduced-live** pure audit. A string-composed dynamic lookup of
  `install_schema` supplied with `schema.schema_ddl_digest()` returned no audit
  violation. A source that opened a connection before calling the gate also returned no
  audit violation. The audit recognized only constant `getattr` attribute names and
  did not prove approval preceded connection opening.
- Impact: a future source change could restore a self-approving DDL installation while
  the central approval literal remains `None`.
- Resolution: fail closed for dynamic schema-installer lookup/import paths, require the
  gate to dominate audited connection openings, and add direct negative controls for
  composed lookup, dynamic import, and late gate order.

## Unverified

- No SQLite connection, DDL installation, or SQLite-bearing test ran.
- The held 10,000-row EXPLAIN proof was inspected statically only; actual planner behavior
  remains subject to the separately authorized fresh-file gate.
- External human/session approval provenance was available only through repository records.

The implementation seat must remediate both P1 findings, freeze a new exact candidate,
and obtain a new fresh exact-head review.
