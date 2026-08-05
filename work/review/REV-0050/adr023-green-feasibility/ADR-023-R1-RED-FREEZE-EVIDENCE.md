# ADR-023 amendment R1 replacement RED freeze evidence

Date: 2026-08-04

Status: PRE-FREEZE VERIFIED; INDEPENDENT EXACT-COMMIT ACCEPTANCE PENDING

## Authority and bounded delta

Ameen approved proposed ADR-023 amendment R1 at exact SHA-256
`F0403B87770648DE233575CE29D853327FD0B48559CE032B4CEF529A6EFE34E9`.
The proposal rehashes to that value. Applying only its named ADR-023 text change produces amended
ADR-023 SHA-256
`9A61D4F952079B5F78DA7A8F1A17F70DC3099D20FB359596923C5938CC421EAF`.

The tracked pre-freeze delta is limited to the accepted ADR, ratification record, active WO, three
matching PKL history records, the two named RED-contract files, and this evidence record. The ADR
change is the one approved retained-state bullet. The other governance records are append-only.
There is no `app/**` delta.

The two RED corrections are:

1. `_market_last_primary` retains exact `ReportedPrice | None` solely for the next cross-kind
   maximum-step comparison; cursor part 13 remains absent for `None` and otherwise contains only
   the existing canonical reported-price commitment.
2. The import grammar admits only canonical private `dataclasses.field` binding and only
   `_field(init=False)` for `MarketOccurrence.occurrence_id` with the required annotation and
   class context. Broader calls, aliases, rebinding, and placements remain rejected.

The authenticated cursor remains exactly 19 parts and 480 bytes. State and work remain constant in
market-history length.

## Failure-capable RED evidence

Focused positive/negative controls passed 4/4. They cover the exact occurrence-identity field
shape, the literal cursor known answer, independent binding of all nineteen cursor parts, and the
state-to-cursor commitment expression. Direct mutants reject raw retained-price serialization,
encoding an absent price as present, incorrect or broader `field` calls, and wrong declaration
contexts.

The complete corrected contract ran against unchanged pre-ADR-023 production:

- total: 505;
- intentional structural failures: 410;
- passing controls: 95;
- errors: 0;
- skips: 0.

The failures remain honest production-absence outcomes. They do not claim that semantic lifecycle
paths blocked by the absent public surface were executed. Preserved JUnit SHA-256:
`093A43BDC0E79EC94A2770A56118844D535064C68DF6EF6E35BB58E994593B44`.

## Predecessor and static evidence

The exact predecessor corpus is all `tests/execution_core` tests except
`test_import_boundary.py`, `test_protection.py`, and `test_protection_stateful.py`. Fresh collection
and execution produced 745/745 passes, zero failures, zero errors, and zero skips. Preserved JUnit
SHA-256:
`D35BB7940EC211CBB33B4E75F8C7677CEB795490830AD723CA80BC8735D3DC99`.

Fresh checks also passed:

- Ruff lint for the repository and Ruff format check for both changed Python files;
- Python 3.11 grammar parsing of both changed Python files;
- mypy across 86 application source files;
- `git diff --check` and active-WO scope validation;
- PKL, ledger, work-order disposition, install, and version consistency;
- exact ADR-020, ADR-021, ADR-022, proposal, and amended ADR-023 hashes;
- application-diff absence; and
- clean status for all nine auxiliary registered worktrees using read-only per-command trust
  overrides, without changing global Git configuration.

## Explicit boundary

No SQL/DDL, database engine, persistent application database, broker, Alpaca, network, credential,
runtime wiring, M2 implementation, master merge, deletion, or cleanup was used or changed. No
prohibited or deferred surface is accepted by this evidence.

This record does not authorize application edits. The exact replacement RED candidate must first
be frozen as an immutable commit and receive one fresh materiality-bounded independent exact-delta
`ACCEPT` with P0=0 and P1=0. Review is limited to defects capable of affecting ADR authority,
protection-state authenticity, restart/replay correctness, boundedness, determinism, execution-goal
safety, or the failure capability of a required regression control; style-only preferences and
already-excluded generalized variants are non-blocking.
