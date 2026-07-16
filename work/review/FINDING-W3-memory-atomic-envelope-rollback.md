# FINDING — memory-store `_atomic()` does not snapshot `_envelopes`: crash leaves state/log disagreeing

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
