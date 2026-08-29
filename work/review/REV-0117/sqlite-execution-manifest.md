# REV-0117 WO-0169 held SQLite execution manifest

Date: 2026-08-29

Status: **STATIC ACCEPTED CANDIDATE — human execution gate closed**

## Authority boundary

WO-0169 implementation and its sole bounded remediation round have fresh independent acceptance
with P0=0/P1=0/P2=0. This manifest prepares, but does not authorize, one real fresh-file proof of
the cold-start persistence chain. The application-side human flag remains exact boolean `False`,
so collection or execution must refuse before any SQLite connection or database creation.

No DDL byte changed in WO-0169. A matching expected digest is identity only and never execution
authority. Ameen Mujtabaa must separately approve the exact source candidate, manifest hash,
branch, commands, and attempt rules recorded in the descendant execution request.

## Accepted static identities

- Branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Accepted implementation candidate: `112d95115f2997ca613238b63eb161a12fbfc791`.
- Implementation tree: `137f7a7bd8d3bc4838cff905754c3394af07fef1`.
- REV-0117 correction result blob: `f788482c08d6cdbd0717efe29e6be388e602152f`;
  file SHA-256 `ac1668b9544da78f12d32dd9d793fd3fe7349afa97588d27a65d4716d3653a43`.
- Review verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- `startup.py` blob: `ee168dee89f51253af1930544b3c96b78b8f93ff`.
- Pure cold-recovery test blob: `144eca97f5cc401c827dec3df916dd7809450ce7`.
- Held fresh-file proof blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`;
  file SHA-256 `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`;
  file SHA-256 `cde0e1e33b7c78e22a854c192ea4b3b83d64c5d11dd538b3ccf23a6e234dc60d`.
- `SCHEMA_DDL`: 190,705 UTF-8 bytes.
- `SCHEMA_DDL` and `EXPECTED_EXECUTION_DDL_SHA256`:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.

## Static evidence

- Complete `tests/execution_core`: 2,259 collected; exact candidate reached 100%, exit code 0.
- Focused correction slice: 91 passed, zero failed.
- Ruff check passed; all 19 full-range Python paths passed Ruff format check.
- mypy passed all 99 application files.
- Install, version consistency, ledger, PKL, work-order scope, and correction-range whitespace
  checks passed.
- The full WO range is whitespace-clean except the exactly disclosed historical blank EOF in
  immutable reviewer-owned `work/review/REV-0116/result.md`; excluding only that file is clean.
- The held proof was parsed, linted, and statically reviewed but not collected or executed.

## Requested flag-only branch and exact commands

After separate exact human approval only:

1. Create `codex/m2-wo0169-cold-recovery-sqlite-r1` from the exact source candidate named in the
   descendant execution request.
2. Make one unlock commit whose sole source change sets
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean `False` to exact boolean `True`.
3. Publish the unlock branch and verify local equals origin; reverify all identities above and the
   manifest hash before execution.
4. Verify `.codex-ddl-gate-run/rev-0117-attempt-1` does not exist, then execute attempt 1 exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 may be approved in the same decision solely for a proven environmental interruption
with zero tracked changes. It is byte-for-byte identical except:

```text
--basetemp=.codex-ddl-gate-run/rev-0117-attempt-2
```

Any assertion, integrity, fixture, DDL, or other substantive failure ends execution authority
without remediation or rerun. Return exact evidence to the canonical flag-false branch. The
flag-true branch and fresh file database remain quarantined execution evidence and are never an
implementation predecessor.

## Prohibitions

No configured or in-memory database, migration, DDL-byte change, runtime composition,
credentials, broker/network activity, orders, promotion, master merge, history rewrite, later work
order, or M3 implementation is authorized by this manifest.
