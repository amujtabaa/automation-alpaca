# REV-0117 R4 correction-only review request — WO-0169 stale-proof rollback

Date: 2026-08-29

Status: **FRESH INDEPENDENT REVIEW REQUIRED**

## Exact review binding

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Remediation base: `5bd3473f5d4f34316935369acb5d38e31f1bcee1`.
- Exact implementation candidate: `636c2329ad5a0f90cc316782bee9542016e53e16`.
- Candidate tree: `cd79bf716fdc550bd7ccbc2832bcfb9c486fa555`.
- Review range: `5bd3473f5d4f34316935369acb5d38e31f1bcee1..636c2329ad5a0f90cc316782bee9542016e53e16`.
- `unit_of_work.py` SHA-256:
  `eff9983e624f09435ab3605033a964472f1de61fb5fedba359941d6ab0af53be`.
- Pure UOW test SHA-256:
  `6fddc9167d22022612f66cd83df1276ab2a84bb7fb920ce26e9f2ff32c5fa569`.
- Active work-order SHA-256:
  `3c65f73c8df800533b98e014fc13fdf0b44bb227710228ae86893afc21e592a2`.

Changed paths are exactly:

- `app/execution_core/persistence/unit_of_work.py`
- `tests/execution_core/test_persistence_unit_of_work.py`
- `work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md`

The request file itself is a later documentation-only commit and is outside the review range.

## Failure and claimed root

The authorized R2 fresh-file proof reached startup but returned fail-closed
`UNRESOLVED_EFFECTS` after the injected query supplied an admitted
`RecordTransportOutcome(DISPATCH_CLAIMED -> ACKNOWLEDGED)`. Evidence is frozen in
`execution-result-r2-attempt-1.md`; no second attempt ran.

A database-free pure reproducer showed the exact rollback: `_execute_venue_operation` derived the
correct successor, then called `_bounded_context_changed` with the pre-transaction selection proof.
Checkpoint encoding rejected the successor `ACKNOWLEDGED` lifecycle against the selected
predecessor `DISPATCH_CLAIMED` row, and the outer UOW collapsed that `_TechnicalRefusal` to generic
`REFUSED`.

The candidate removes that stale-proof check only from the relational venue route. It retains and
strengthens the no-op guard at `_store_successor_checkpoint`, after that function reselects the
post-write proof inside the same transaction. Two pure tests must fail if the stale precheck is
restored or an unchanged fresh-proof successor reaches checkpoint storage.

## Evidence available to reproduce

No SQLite-bearing or held test is authorized. The following source-confirmed pure command passed
all 550 collected tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_persistence_unit_of_work.py tests/execution_core/test_persistence_cold_recovery.py tests/execution_core/test_persistence_startup.py tests/execution_core/test_persistence_startup_hydration.py tests/execution_core/test_persistence_runtime_checkpoint_pure.py tests/execution_core/test_persistence_operations.py
```

The two direct controls also passed together. Ruff check/format, mypy `app` (99 files),
install/version/ledger/PKL, work-order scope, and `git diff --check` passed.

Static immutable identities remain:

- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

## Required adversarial lenses

1. Re-derive the stale-proof failure and whether fresh in-transaction reselection is the correct
   authority boundary.
2. Look for any path where removing the venue precheck could store a no-op, spliced, or unrelated
   successor despite the new shared fresh-proof delta guard.
3. Verify the shared guard does not reject a legitimate operation or move a check past an
   irreversible boundary; all work remains inside the caller-owned transaction.
4. Critique both tests for mutation strength, over-mocking, and whether they could pass after a
   band-aid that weakens startup or bypasses relational persistence.
5. Verify scope, DDL/flag/held-test non-drift, and the prohibition on SQLite execution.

Return findings only with P0/P1/P2 severity, exact file and line, impact, and resolution. End with
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, plus explicit P0/P1/P2 counts and unverified items.
Write no source/test fixes. The reviewer-owned result identity is
`work/review/REV-0117/result-r4.md`.
