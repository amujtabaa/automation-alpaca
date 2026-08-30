# REV-0118 R6 — correction-only fresh-file execution packet

Status: **AUTHORIZED by the active WO-0170 execution authority; not yet executed**

This packet proves only the three accepted REV-0118 P1 corrections. It creates fresh
pytest-owned file databases and does not use a configured database, `:memory:`, migration,
runtime composition, credentials, broker/network activity, orders, promotion, or M3 code.

## Exact canonical source

- Branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Source commit: `a18924131e0e2534bbdf51fb9374dbdd5bac4c9f`
- Source tree: `c9ee080be59a4847e82258c615289da456c2f195`
- Proof branch to create from that exact commit:
  `codex/m2-wo0170-rev0118-correction-sqlite-r1`
- Canonical authorization flag: exact boolean `False`
- Proof-branch change: the sole tracked change is that flag from exact boolean `False` to
  exact boolean `True`
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- `SCHEMA_DDL`: 190,705 UTF-8 bytes
- DDL SHA-256:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`

## Exact corrected artifacts

| Artifact | SHA-256 |
| --- | --- |
| `harness/m2/closeout.py` | `460d404ad441a7f8f409c6aabacc8bfce116d5217aff733045f40884363eca6f` |
| `tests/execution_core/test_persistence_fault_matrix.py` | `9d3721c59e51193985160cf8a9039dbcf798296acb69be6f7ef820aba23397e0` |
| `tests/execution_core/test_persistence_restore.py` | `2c9f82bb48dca46dd41fd2daf8311b9af9a595b5af1facb278721687394e87e9` |
| `tests_gated/execution_core/test_persistence_fault_matrix.py` | `7fe3611333ec007ff6c0eec4ffb0cd05ae405d66622db18ed167bb13df48d40d` |
| `tests_gated/execution_core/test_persistence_boundedness.py` | `b7e4a97a7e916ab20ce7bb6746bf69a35e942f9fca38d79416611e8c8c6e2be4` |

The canonical correction already passed 60 pure closeout controls, Ruff lint/format,
`mypy app` over 99 files, gated collection, schema identity verification, and
`git diff --check`, without opening SQLite.

## Exact execution

From the proof branch, after independently verifying that its only source difference from
`a18924131e0e2534bbdf51fb9374dbdd5bac4c9f` is the authorization flag:

```powershell
New-Item -ItemType Directory -Force .codex-ddl-gate-run\wo0170-rev0118-r6
.\.venv\Scripts\python.exe -m pytest -q tests_gated\execution_core\test_persistence_fault_matrix.py tests_gated\execution_core\test_persistence_boundedness.py --basetemp .codex-ddl-gate-run\wo0170-rev0118-r6\pytest -p no:cacheprovider
```

Expected collection: seven cases. All must pass. The boundedness test must execute real
checkpoint load, decode, and compact restoration at 1,000 and 10,000 unrelated rows, consume
the frozen 12x startup SELECT/elapsed and 2 MiB canonical-projection budgets, and validate all
selection/load plans at both coordinates.

Any assertion, integrity, fixture, DDL, or other substantive failure ends R6. Root diagnosis may
continue on canonical source, but no failed proof branch becomes a predecessor. There is no retry
except a proven environmental interruption with zero tracked changes and a brand-new basetemp.
