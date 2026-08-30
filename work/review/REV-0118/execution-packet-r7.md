# REV-0118 R7 — corrected boundedness fresh-file execution packet

Status: **AUTHORIZED by the active WO-0170 execution authority; not yet executed**

R7 supersedes failed R6 and repeats the same seven-case fresh-file boundary after one test-only
root correction. It creates no configured or in-memory database and changes no DDL byte.

## Exact canonical source

- Branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Source commit: `106fa7c4be39adc974af038264ed74d4349f19c7`
- Source tree: `782fcbe39ec2df524bce1012b2d818979c670bd8`
- Proof branch to create: `codex/m2-wo0170-rev0118-correction-sqlite-r2`
- Proof-branch sole tracked change: `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` exact boolean
  `False` to exact boolean `True`
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- `SCHEMA_DDL`: 190,705 UTF-8 bytes
- DDL SHA-256:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- Corrected boundedness-test SHA-256:
  `1ca281db1aae8b32e3229a0f7beae9bd680be32d99a4eb91878f71d8bd68d860`
- All other corrected-artifact hashes remain exactly those in R6 packet
  `ef7e0b19889d7b5e08c4e7d1fc8736aa051a25a9da4465b5b569d1917299fdba`.

## Exact execution

After verifying the flag-only branch and creating a previously absent evidence parent:

```powershell
New-Item -ItemType Directory -Path .codex-ddl-gate-run\wo0170-rev0118-r7
.\.venv\Scripts\python.exe -m pytest -q tests_gated\execution_core\test_persistence_fault_matrix.py tests_gated\execution_core\test_persistence_boundedness.py --basetemp .codex-ddl-gate-run\wo0170-rev0118-r7\pytest -p no:cacheprovider
```

Expected collection: seven cases; all must pass. Any assertion, integrity, fixture, DDL, or other
substantive failure ends R7. Only a proven environmental interruption with zero tracked changes
may use one new-root retry. No failed or flag-true branch is an implementation predecessor.
