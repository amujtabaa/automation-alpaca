# REV-0117 WO-0169 held SQLite execution manifest R3

Date: 2026-08-29

Status: **STATIC ACCEPTED APPLICATION CORRECTION — new human execution gate closed**

## Authority boundary

The approved R2 attempt reached the real startup/unit-of-work path and stopped fail-closed at
`UNRESOLVED_EFFECTS`. Its authorization is consumed, and its flag-true branch and database remain
quarantined evidence. They are not predecessors for this packet.

The bounded application/test correction now has fresh independent `ACCEPT` with P0=0/P1=0/P2=0.
This manifest prepares, but does not authorize, one new fresh-file proof. The application-side
human flag remains exact boolean `False`, so collection or execution must refuse before any SQLite
connection or database creation. No DDL byte or held-test byte changed. Ameen Mujtabaa must
separately approve the exact flag-false source candidate, this manifest's hash, the new quarantined
branch, command, and stop rules recorded in the descendant R3 execution request.

## Accepted static identities

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Authorized remediation base: `5bd3473f5d4f34316935369acb5d38e31f1bcee1`.
- Application/test correction candidate: `fe59068d9129d417d0d9c85e4a9b53e0bd97d995`;
  tree `a92dc7fb91ceb349323eee92a9e677fc03769279`.
- REV-0117 R5 acceptance commit: `73b6fcb048d9039fe541524be6bf96e0d24c5d3e`;
  tree `4d21088ea18db848cfa08f88ac8817b764e99897`.
- REV-0117 R5 result blob: `8ec9b2b6a5f7b67313492e80240b054673df8755`;
  file SHA-256 `a26f674986654f387ca83a392a8324753211c1a16fe21e8cfc7dae81a20bbf90`.
- Review verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- `unit_of_work.py` blob: `26761f32d51c1c85cbb7d2131e33418564bc3422`;
  file SHA-256 `03788a738d7a80964a87bc8a93a574264676a407d7ed1df7e00d7b243a60f315`.
- Pure UOW test blob: `21835f07ede94ec656d4c1a6d15f1dc5ba87e5d2`;
  file SHA-256 `4e16a2e697cb25535d561f993481d36515b1ab930c78213cb48441b3ec715329`.
- Held fresh-file proof blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`;
  file SHA-256 `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`;
  file SHA-256 `cde0e1e33b7c78e22a854c192ea4b3b83d64c5d11dd538b3ccf23a6e234dc60d`.
- `SCHEMA_DDL`: 190,705 UTF-8 bytes.
- `SCHEMA_DDL` and `EXPECTED_EXECUTION_DDL_SHA256`:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.

## Root correction and static evidence

The R2 failure had two serial application-side causes. First, dormant venue recovery required a
market cursor even though no protection was active. Second, after relational writes, the venue
route checked its successor against the stale pre-transaction selection proof. The correction:

1. permits an absent cursor only for dormant venue recovery while every active/default caller
   retains exact-one enforcement;
2. projects and stores the successor only after same-transaction post-write reselection; and
3. retains the shared no-op refusal at that fresh-proof storage boundary.

Three direct failure-capable controls passed for the author and independent reviewer. The author
also ran the source-confirmed six-file pure slice: all 550 tests reached 100% with exit code 0.
Ruff check/format pass on changed Python paths; mypy passes all 99 application files. Install,
version consistency, ledger, PKL, exact work-order scope, and authored-content whitespace checks
pass. The held proof remains byte-identical to R2 and has not been rerun.

## Requested flag-only branch and exact command

After separate exact human approval only:

1. Create `codex/m2-wo0169-cold-recovery-sqlite-r3` from the exact source candidate named in the
   descendant R3 execution request.
2. Make one unlock commit whose sole source change sets
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean `False` to exact boolean `True`.
3. Publish the unlock branch and verify local equals origin; reverify all identities above and this
   manifest's hash before execution.
4. Verify `.codex-ddl-gate-run/rev-0117-r3-attempt-1` does not exist, then execute attempt 1 exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r3-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 may be approved in the same decision solely for a proven environmental interruption
with zero tracked changes. It is byte-for-byte identical except:

```text
--basetemp=.codex-ddl-gate-run/rev-0117-r3-attempt-2
```

Any assertion, integrity, fixture, DDL, application, or other substantive failure ends this
execution authority without remediation or rerun. Return exact evidence to the canonical
flag-false branch. The flag-true branch and fresh database remain quarantined evidence and are
never an implementation predecessor.

## Prohibitions

No configured or in-memory database, migration, DDL-byte change, runtime composition,
credentials, broker/network activity, orders, promotion, master merge, history rewrite, later work
order, or M3 implementation is authorized by this manifest.
