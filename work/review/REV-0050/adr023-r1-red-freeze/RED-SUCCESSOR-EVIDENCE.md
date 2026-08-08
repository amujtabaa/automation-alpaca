# ADR-023 R1 RED successor evidence

Date: 2026-08-04

Status: P1 CORRECTED; IMMUTABLE SUCCESSOR REVIEW PENDING

## Exact finding and owning correction

The independent exact-commit review of
`7e0b869c852b66a6744b447429f4bf0eca756b5b` returned `ACCEPT-WITH-CHANGES`, P0=0,
P1=1, P2=0. Its sole P1 showed that the generic passive-dataclass seal still required every field
to be constructor-initialized, while ratified R1 requires only
`MarketOccurrence.occurrence_id = field(init=False)`.

The correction changes the owning metadata/reference helper rather than weakening the dedicated
occurrence check:

- the helper accepts an explicit ordered constructor-field inventory;
- every field's exact `init` flag must match that inventory;
- `__match_args__` must contain exactly the constructor fields; and
- the independently generated reference dataclass uses the same per-field metadata.

The exact `MarketOccurrence` constructor inventory is centralized as every named field except
`occurrence_id` and is passed only through the three contract paths that inspect the real public
occurrence type. All other dataclasses retain the default all-fields-initialized requirement.

## Failure-capable evidence

The new synthetic control was observed RED before the helper change with
`unexpected keyword argument 'expected_init_fields'`. After the correction it passes and directly
proves both negative cases:

- omitting the required derived-field exception fails; and
- excluding an additional field from construction fails.

The surrounding passive enum/dataclass/value/lifecycle control selection passes 17/17. The five
focused R1 controls pass 5/5, covering the new metadata control, the exact occurrence field-call
grammar, the cursor known answer, all nineteen cursor parts, and the state-to-cursor commitment
binding.

## Replacement classification and predecessor continuity

The complete successor contract ran once against unchanged pre-ADR-023 production:

- total: 506;
- intentional structural failures: 410;
- passing controls: 96;
- errors: 0;
- skips: 0.

The sole change from the prior 505/410/95 split is the new passing synthetic control. Preserved
successor JUnit SHA-256:
`FCE5BA7AC5A0DFDDE405D1E97DD780089A60C9D2E8BAD5FDA4D9968B89EF4A84`.

The predecessor selector was freshly collected and remains exactly 745 tests while excluding only
the three ADR-023 RED files. No predecessor or application file changed. The prior fresh 745/745
execution artifact remains byte-for-byte preserved at SHA-256
`D35BB7940EC211CBB33B4E75F8C7677CEB795490830AD723CA80BC8735D3DC99`; repeating its
209-second execution would add no new evidence for this test-helper-only delta.

## Boundary

Ruff lint/format and Python 3.11 grammar pass for the changed Python file. Scope, diff,
application-absence, and governance checks are rerun before freeze. No application, runtime,
database, broker, network, credential, M2, master, deletion, or cleanup surface changed.

This evidence does not authorize production edits. The successor must be committed immutably and
receive one fresh review limited to the exact P1 correction, with P0=0 and P1=0.
