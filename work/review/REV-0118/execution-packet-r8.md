# REV-0118 R8 — final import-boundary correction proof

Status: **AUTHORIZED by active WO-0170; not yet executed**

R8 rebinds the seven passing R7 cases after one non-semantic test-import correction. The direct
`persistence_setup_support` import was removed from the boundedness test; it now reaches the same
approved helper through `test_persistence_runtime_checkpoint_sqlite`, preserving the frozen
dependency direction.

- Canonical source: `c7e394f52782a9b398ed89bfdc55b45bc09499b4`
- Source tree: `2d5c662f569ec3ee792216863fe46213551773a8`
- Boundedness-test SHA-256:
  `9d44bdbaad3df45a586a6045c4afcf29341397fbcf182ccb206c20c6c418ec98`
- Proof branch: `codex/m2-wo0170-rev0118-correction-sqlite-r3`
- Sole proof-branch change: authorization flag exact boolean `False` to exact boolean `True`
- DDL: 190,705 UTF-8 bytes, SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- `schema.py` canonical blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`

After creating the previously absent parent, execute exactly:

```powershell
New-Item -ItemType Directory -Path .codex-ddl-gate-run\wo0170-rev0118-r8
.\.venv\Scripts\python.exe -m pytest -q tests_gated\execution_core\test_persistence_fault_matrix.py tests_gated\execution_core\test_persistence_boundedness.py --basetemp .codex-ddl-gate-run\wo0170-rev0118-r8\pytest -p no:cacheprovider
```

All seven cases must pass. A substantive failure stops. No configured/in-memory database, DDL
change, migration, runtime composition, credential, broker/network activity, order, promotion,
master merge, or M3 implementation is authorized.

