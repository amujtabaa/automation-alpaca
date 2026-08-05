# WO-0148 ADR-023 R1 RED metadata-seal successor review

Review type: independent exact-delta functional-conformance review

Target commit: `9fe4c37f4114aee2ac5ca2f499b784cabc657cc6`

Exact parent/base: `7e0b869c852b66a6744b447429f4bf0eca756b5b`

## Seat and output

Review only the correction for the single P1 recorded in
`work/review/REV-0050/adr023-r1-red-freeze/result.md`. Re-derive the exact committed delta and write
only `result.md` in this folder. Do not edit this request or any other file. Do not commit or push.

Return `ACCEPT` only with P0=0 and P1=0. Each finding must identify exact file/line evidence, why it
is material, and the smallest resolution. State anything not independently verified.

## Materiality and scope

The parent review found exactly one P1: the generic passive-dataclass metadata/reference seal
unconditionally required every field to be constructor-initialized, contradicting ratified
`MarketOccurrence.occurrence_id = field(init=False)`.

The target changes exactly five files:

- `tests/execution_core/test_protection.py`
- `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`
- `work/review/REV-0050/adr023-r1-red-freeze/request.md`
- `work/review/REV-0050/adr023-r1-red-freeze/result.md`
- `work/review/REV-0050/adr023-r1-red-freeze/RED-SUCCESSOR-EVIDENCE.md`

No application or predecessor file changes. Review only whether this delta closes the named P1
without weakening the passive-value seal or introducing an inaccurate acceptance claim. Naming,
style, preferred refactors, and unrelated already-reviewed ADR-023 behavior are non-blocking.

## Required checks

1. Verify target, sole parent, exact five-file path set, clean committed diff, WO scope, and no
   `app/**` delta.
2. Confirm the helper now takes an explicit exact constructor-field inventory, checks every
   field's `init` metadata, restricts `__match_args__` to constructor fields, and builds its
   independent reference dataclass with identical per-field metadata.
3. Confirm only the real `MarketOccurrence.occurrence_id` receives the one-field exception across
   every applicable public-value/lifecycle graph path. Every other dataclass remains all-init.
4. Reproduce the new synthetic control and its two negative cases. Run the surrounding passive
   helper selection and proportionate Ruff/format/Python 3.11 grammar/diff/scope checks.
5. Rehash and inspect the successor JUnit: 506 total / 410 intentional structural failures / 96
   passes / 0 errors / 0 skips at SHA-256
   `FCE5BA7AC5A0DFDDE405D1E97DD780089A60C9D2E8BAD5FDA4D9968B89EF4A84`.
   Confirm predecessor collection remains 745 and the unchanged prior 745/745 artifact remains
   `D35BB7940EC211CBB33B4E75F8C7677CEB795490830AD723CA80BC8735D3DC99`.
   Do not repeat either long full execution unless an artifact or sampled-control inconsistency is
   found.

Text inspection, static analysis, collection, and focused pure tests are allowed. Do not use SQL or
DDL, a database engine, persistent application data, broker or Alpaca services, network access,
credentials, runtime wiring, M2 implementation, master merge, deletion, or cleanup.

Acceptance authorizes only the already approved WO-0148 production-implementation gate. It does
not accept production behavior or close WO-0148.
