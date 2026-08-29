# REV-0117 WO-0169 held SQLite execution manifest R4

Date: 2026-08-29

Status: **STATIC ACCEPTED — STANDING WO-0169 EXECUTION AUTHORITY**

## Authority boundary

The R3 attempt stopped fail-closed and its flag-true branch/database remain quarantined evidence.
Instrumented diagnosis and the bounded application/test root correction now have fresh exact-head
`ACCEPT`, P0=0/P1=0/P2=0. Ameen then instructed Codex to work self-directedly and granted
permission to get to the end of this work order without repeated basic approvals. That standing
authority covers this one fresh pytest-owned file-database proof because DDL and the held test are
unchanged and the active work order already authorizes bounded fresh-file verification.

The canonical source flag remains exact boolean `False`; collection and execution must refuse
before connection access until the separately published flag-only R4 branch sets it to `True`.
The R4 branch and database are quarantined proof only and never become an implementation
predecessor. Any substantive failure consumes this attempt and forbids repair or rerun on the
flag-true branch. Root diagnosis/remediation may continue only on the canonical flag-false branch
under the standing WO-0169 authority, followed by a new exact review and fresh packet.

## Accepted static identities

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Instrumented-diagnosis base: `4791e780938084637c1c11f5a1896f97d3d9651d`.
- Application correction: `ecee243d5627d06a55f7de1b89c59b9982e253fd`;
  tree `1f35f8204ebab2356885aea17ef19d2748e220b3`.
- Test-evidence correction: `51c90ba480e8b61ea7e57d627f0b90cdb80191e1`;
  tree `b1514e84c5fcb910520353e90115d6a0bb2de6ab`.
- REV-0117 R7 acceptance commit: `b81a5f2fa1fac7d677c2abcfe9bdebcdce435c85`;
  tree `0c6d327063cddf8313d0c110d1e4846c3ff6b843`.
- REV-0117 R7 result blob: `86490aaae7d0da8badc6415b94de7d00cb5db05c`;
  file SHA-256 `77153619da6cd00854531953cfe3b540baeb644fe8994c47b126b2de8b3de686`.
- Review verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- `unit_of_work.py` blob: `1d0879ba4dfddefa59e3c815abbaf62e685131a6`;
  file SHA-256 `12bb7ad3d25f1de23829010bf50bb5cb0ce26896f4696b200dd2744b8079295c`.
- Pure UOW test blob: `d6d86111ee3e668b882cd2229f7a40dcbdf082a3`;
  file SHA-256 `443db52fd83c09c0e148e3268beef18b6fb0bf1fa879c8a9e03a52477e80164a`.
- Held fresh-file proof blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`;
  file SHA-256 `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`;
  file SHA-256 `cde0e1e33b7c78e22a854c192ea4b3b83d64c5d11dd538b3ccf23a6e234dc60d`.
- `SCHEMA_DDL`: 190,705 UTF-8 bytes.
- `SCHEMA_DDL` and `EXPECTED_EXECUTION_DDL_SHA256`:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.

## Root correction and static evidence

The R3 failure was a contract mismatch at the shared UOW preparation boundary: an authentic
retained checkpoint at N was compared byte-for-byte with its authentic same-owner target
projection at N+1. The corrected guard separately authenticates the exact retained head and exact
next-version projection, then compares all owner components through the existing semantic
comparator. Authentic tests kill the former full-payload comparison, predecessor-at-N acceptance,
wrong head/provenance, and a different-owner projection at the valid N+1 boundary.

The author passed all 552 source-confirmed pure tests and all 2,266 ordinary execution-core tests.
Ruff check/format, mypy over 99 application files, install, version, ledger, PKL, disposition,
scope, and whitespace checks pass. The independent R7 reviewer reproduced the decisive corrected
control and returned zero open P0/P1. No SQLite-bearing or held test has run since the R3 failure.

## Flag-only branch and exact command

1. Use the exact flag-false source candidate recorded by the descendant R4 execution request.
2. Create `codex/m2-wo0169-cold-recovery-sqlite-r4` from that exact commit.
3. Make one unlock commit whose sole source change sets
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean `False` to exact boolean `True`.
4. Publish the unlock branch, verify local equals origin, and reverify every identity above plus
   this manifest's hash.
5. Verify `.codex-ddl-gate-run/rev-0117-r4-attempt-1` does not exist, then run attempt 1 exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r4-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 is permitted only for a proven environmental interruption with zero tracked changes and
is byte-for-byte identical except:

```text
--basetemp=.codex-ddl-gate-run/rev-0117-r4-attempt-2
```

An assertion, integrity, fixture, DDL, application, or other substantive failure ends this packet
without same-branch remediation or rerun. Return exact evidence to the canonical flag-false branch.

## Prohibitions

No configured or in-memory database, migration, DDL-byte change, runtime composition,
credentials, broker/network activity, orders, promotion, master merge, history rewrite, later work
order, or M3 implementation is authorized by this manifest or the standing WO-0169 authority.
