# FINDING — memory-store `_atomic()` does not snapshot `_envelopes`: crash leaves state/log disagreeing

> **Authoritative disposition (2026-07-20): RESOLVED.** The original OPEN record below is
> retained as historical finding text; the additive resolution block is authoritative.

- **Status:** OPEN (REV-0023 Phase A, test-critic TC-03 — a real app defect discovered through a
  test-coverage gap: the staging atomicity test is sqlite-only with no memory twin).
- **Severity:** **P1** (H3/H10; the memory store can end with envelope=APPROVED while the event
  log replays to PENDING — "the log is the truth" broken; dual-store parity broken on the crash
  path).
- **Cluster:** F7 in `work/review/REV-0023/phase-a.md`.

## What

Memory `_atomic()` (app/store/memory.py:273-327) snapshots orders/events/intents/etc. but not
`self._envelopes`, and `_apply_envelope_transition_unlocked` (memory.py:925-940) mutates the
envelope dict BEFORE appending events. An injected crash in the audit append during
`transition_envelope` yields:

```
envelope status after rollback: EnvelopeStatus.APPROVED
exec event kinds: ['envelope_created']
```

State says APPROVED; the log replays to PENDING. The WO-0021 replay property never injects
crashes, so it cannot see this; `test_sqlite_staging_is_all_or_nothing` has no memory variant.

## What resolves it

WO-0028 (DRAFT): one-line fix (snapshot `_envelopes` in `_atomic`) + a memory-variant
crash-injection atomicity test mirroring the sqlite one, covering transition, staging, fill, and
supersede units.

## Repro

Test-critic injected-crash probe; decisive output above. Quoted in the critic report under
REV-0023.

## Resolution / disposition (recorded by WO-0120)

**RESOLVED by WO-0028.** The memory atomic unit now snapshots/restores envelopes. The exact pins
are `test_memory_envelope_transition_is_all_or_nothing`,
`test_memory_staging_is_all_or_nothing`,
`test_memory_envelope_fill_is_all_or_nothing_and_dedupe_unpoisoned`, and
`test_memory_supersede_is_all_or_nothing` in `tests/test_wo0019_engine_seam.py`; WO-0028's
mutation M14 proves the restore is load-bearing. The assembled W3 remediation review is
dispositioned RESOLVED in REV-0023, and AUDIT-0002 F009 independently reconciled this class as
fixed. **Disposition: CLOSED / RESULT_SUMMARY_KEPT.**
