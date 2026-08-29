# REV-0117 R3 instrumented diagnosis — WO-0169 UOW checkpoint authentication

Date: 2026-08-29

Status: **ROOT CAUSE CONFIRMED — REMEDIATION NOT YET AUTHORIZED**

## Exact diagnostic binding

- Canonical flag-false head: `123b5d2edac71738122df2f1c8a2b9cfce3fc3b7`;
  tree `df38341f418971b2092536942e881da236df0b04`.
- Quarantined R3 flag-only branch/head:
  `codex/m2-wo0169-cold-recovery-sqlite-r3` /
  `a854f93eb93a70c324fcb9ae5a5d77ceefe3bed1`.
- Preserved R3 database:
  `.codex-ddl-gate-run/rev-0117-r3-attempt-1/test_cold_startup_commits_c1_t0/wo0169-cold-startup.db`.
- Original preserved file metadata remained 794,624 bytes with timestamp
  `2026-08-29T11:48:50.9999670-10:00` after diagnosis.

The probe copied that database into five disposable diagnostic directories. It installed no
schema, changed no DDL, queried no configured database, and changed no tracked source or test.
Runtime wrappers only recorded `_TechnicalRefusal` propagation; later copies transiently replaced
one comparison with the module's existing semantic comparator to test the root hypothesis.

## Confirmed root cause

The UOW refuses in `_prepare_transaction` before `_execute_venue_operation` or any venue write:

```text
_TechnicalRefusal: runtime owners do not equal the retained checkpoint payload
```

The mismatch is created by contradictory metadata roles:

1. `repository.select_runtime_checkpoint` deliberately issues a write proof whose target checkpoint
   version is `predecessor.checkpoint_version_ordinal + 1`
   (`repository.py:5416-5417`).
2. `_project_runtime_checkpoint` correctly encodes that target version into the projected envelope
   (`checkpoint_codec.py:5366`).
3. `_prepare_transaction` uses that successor-target proof to authenticate the current owners, then
   `_require_retained_checkpoint_payload` requires the entire projected canonical payload to equal
   the retained predecessor payload (`unit_of_work.py:623-639`).
4. Whole-payload equality must therefore fail whenever a predecessor exists, even when every owner
   component is exact, because the projected and retained checkpoint versions differ by design.

Observed exact values:

```text
context/retained head: currentness 0, checkpoint version 1,
  SHA-256 3bda780ca1b9a025f89cf5ef53c4f6110d23077656e11f1c473319f2b02fbfb0
projected target:      currentness 0, checkpoint version 2,
  SHA-256 9e3c4d0ad5a09a780b5c157b6159173f50668d3fec78d67e223bde02aadcadc2
payload length:        12,070 bytes on both sides
```

Venue, authority, position-scope, acquisition, execution, and protection component bytes all
matched exactly. Only successor metadata made the whole payload differ.

## Test gap

`test_owner_projection_must_equal_the_retained_checkpoint_payload`
(`tests/execution_core/test_persistence_unit_of_work.py:3379`) replaces the authentic envelope type
with a fake carrying caller-selected `b"retained"` bytes. It never combines an authentic retained
version-1 envelope with the authentic version-2 target proof returned for its next write. The test
therefore freezes the incorrect whole-payload requirement and cannot expose the real repository
contract.

## Root-hypothesis disproof pass

The module already has `_m2_checkpoint_semantics_match` (`unit_of_work.py:5833`), whose explicit
purpose is to compare all owner components while ignoring successor metadata. A transient probe
accepted the current owners only when all of the following held: authentic loaded envelope,
`LOADED` provenance, exact retained application/head/version/digest identity, and that existing
owner-semantic comparison.

On a fresh copy, changing only that diagnostic comparison produced the complete required behavior:

```text
first startup:  SERVING; one effect query
first state:    currentness 1, checkpoint version 2, two payloads, ACKNOWLEDGED
second startup: SERVING; zero effect queries
second state:   byte-identical head/state; no additional checkpoint write
```

No later `_TechnicalRefusal` appeared. This disproves the earlier cursor/stale-proof theory as the
active R3 blocker and confirms the whole-payload/current-owner contract as the sole observed cause
of this held failure.

## Impact and risk

Risk: **HIGH / critical availability**, fail-safe rather than unsafe execution.

The shared `_prepare_transaction` boundary precedes every public M2 UOW route. With a real retained
checkpoint, its proof always targets the next version, so the defect is broader than venue recovery:
real SQLite-backed M2 operations can fail closed before reaching their domain reducer/persistence
path. For WO-0169, startup safely remains non-serving and does not blindly repeat or misrecord the
effect; however, recovery and normal durable progress are unavailable.

## Bounded remediation shape

A root correction should:

1. retain exact loaded-envelope authenticity, `LOADED` provenance, application/profile, and all
   retained checkpoint head fields/digest checks;
2. replace whole canonical-payload equality at current-owner authentication with the existing
   exact owner-semantic comparison that intentionally ignores successor metadata;
3. replace the fake-byte unit test with authentic predecessor/target envelopes proving version
   `N` owners authenticate under a target-`N+1` proof, while component or retained-head mutations
   fail; and
4. add one pure compact-reread-to-`_prepare_transaction` regression so the real proof metadata
   relationship cannot be mocked away again.

This requires no DDL, schema, public API, startup contract, or held-test semantic change. After a
bounded implementation and fresh exact-head review with zero open P0/P1, a new separately approved
fresh-file execution packet would still be required.
