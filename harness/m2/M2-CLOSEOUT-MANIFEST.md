# M2 persistence closeout manifest

Status: **WO-0170 ACCEPTED — terminal M2/M3-preparation review remains**

This manifest closes the implementation-evidence boundary of M2. It does not authorize promotion,
configured-database use, runtime composition, a broker connection, an order, a merge to `master`,
or any M3 implementation. `NOT_RUN` and `NOT_EVALUATED` below remain real residuals.

## Repository and source identity

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Canonical branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Accepted WO-0169 predecessor: commit
  `0e9c5aadf003aae7dc66cf6df497b1a1d1d6d130`, tree
  `b5f1042247804ad9fde4347c8729d5bde29a172d`
- Final WO-0170 implementation/test source: commit
  `c7e394f52782a9b398ed89bfdc55b45bc09499b4`, tree
  `2d5c662f569ec3ee792216863fe46213551773a8`
- Final flag-only proof head: commit
  `b14cbb88061aab09f69ce219e9c1427a01873761`, tree
  `f4571503ad5a3b507b0ee33997d3335c317f68b4`
- REV-0118 accepted closeout candidate: commit
  `2051afe2bbc21918fac6b69875e0a536fe722e49`, tree
  `2d3fef0011412ec432fd26f43f526be6946ad00c`
- Canonical DDL authorization flag: exact literal boolean `False`
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- `SCHEMA_DDL`: 190,705 UTF-8 bytes
- DDL SHA-256 and expected digest:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`

The accepted serial M2 sources recorded by their owning closeouts are WO-0165
`3c85b17bc04fa587cac1995c8999155d6583006b`, WO-0166
`b00c2dec5fab7f87fd30aecc130a29bec600bf39`, WO-0167
`3c028b9ae5fd3e1b6bf84b7d73c2f3039ac14043`, WO-0168
`f637295e42be8430edb14be03c0dd23d24bef394`, and WO-0169
`ae6277b38fb8e9e9823e512373a8c2d19938c7e9`. The exact WO-0170 branch predecessor above includes
WO-0169's governance closeout.

## Exact WO-0170 artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `harness/m2/__init__.py` | `c088f3d38a2a6a9745760365a13adbd76c3530bd22960f76c0a23a0d4e729b73` |
| `harness/m2/closeout.py` | `460d404ad441a7f8f409c6aabacc8bfce116d5217aff733045f40884363eca6f` |
| `harness/m2/soak.py` | `9deff7a6be5035e6a7dcbec06482506a6acebf1a655502fa912100d201d0fdd6` |
| `tests/execution_core/test_persistence_boundedness.py` | `8d472a1c96f60ce859aed7a95e4529a34a673d8c48c99df04cdd5bd897ab888d` |
| `tests/execution_core/test_persistence_fault_matrix.py` | `9d3721c59e51193985160cf8a9039dbcf798296acb69be6f7ef820aba23397e0` |
| `tests/execution_core/test_persistence_restore.py` | `2c9f82bb48dca46dd41fd2daf8311b9af9a595b5af1facb278721687394e87e9` |
| `tests/execution_core/test_sqlite_boundary.py` | `25690965f4ee8b77dd6660464cbb0d3814c2264cba003c40a7149b4693666656` |
| `tests/performance/m2_persistence_budget.py` | `32bc0d6905855ae71b4062b4aae0b4ae503ac17a53f013449c4f001fa271a085` |
| `tests_gated/execution_core/test_persistence_boundedness.py` | `9d44bdbaad3df45a586a6045c4afcf29341397fbcf182ccb206c20c6c418ec98` |
| `tests_gated/execution_core/test_persistence_fault_matrix.py` | `7fe3611333ec007ff6c0eec4ffb0cd05ae405d66622db18ed167bb13df48d40d` |
| `tests_gated/execution_core/test_persistence_restore.py` | `c712c7e08dda0a5173cf6734c619a9e17bd7ab543ce50944b94dd415276afe01` |

## Environment

- OS: Microsoft Windows 10.0.26200, x64
- Python: CPython 3.12.13 from `.venv`
- pytest: 9.1.1
- Ruff: 0.15.20
- mypy: 2.2.0
- Git: 2.53.0.windows.2
- Database destinations: fresh pytest-owned files under explicit workspace-local `--basetemp`
  roots only; no `:memory:` and no configured database

## Failure, mutant, restore, and boundedness coverage

The finite catalog contains 19 named fault obligations, 10 named mutant obligations, and four
boundedness obligations. Pure tests fail if an obligation disappears, a node ID is missing, a
gated boundary is misclassified, or any current repository write loses either its before/after
fault case.

The live proof covers complete pre/post COMMIT old-or-new state against an independent clean
control, recovery and replay equality, DB/WAL copy and independent restore, profile/catalog
corruption refusal, duplicate/forked lineage, stale/missing and cross-owner routes, two-LIVE,
claim erasure, acceptance/closure gaps, cursor regression, no serving-time history fold, direct
query plans, and 1,000-to-10,000 unrelated-history measurement. The review correction gives claim,
claim-erasure, acceptance, closure, and each cursor ordinal its own decisive failure path; actual
checkpoint load, decode, and compact restoration now consume the startup budget. Frozen limits
are 3x runtime p95 growth, 12x startup SELECT/elapsed growth, and 2 MiB peak canonical-projection
memory.

## Fresh evidence

| Gate | Exact result |
| --- | --- |
| Pure WO-0170/static boundary controls | 60 passed |
| Canonical ordinary `tests/execution_core` | 2,310 passed, 0 failed, 0 skipped |
| R2 conformance oracle | 61 passed |
| R4 fresh-file matrix | 259 passed; packet `048265cf73aff73c1c83bdbf09a1b7bb71db339af2bb9b888d422bba85e02850` |
| R5 one-cycle driver smoke | 180 passed in 7.29 seconds; process exit 0; summary `NOT_RUN` |
| R8 final review-correction proof | 7 passed; packet `08427d02ba8e3e25c33ef3cf14e121a95aac2f9b01e7e3704e1579916d159344` |
| REV-0118 final verification | `ACCEPT`, P0=0, P1=0, P2=0, `Unverified: NONE` |
| Ruff lint | passed repository check; inaccessible user-owned temp roots emitted warnings only |
| Ruff format | all 11 changed Python files clean |
| mypy | success over 99 application files |
| Import Linter | 6 contracts kept, 0 broken |
| AI Project OS | install, version, ledger, PKL, disposition, and work-order scope passed |
| Git hygiene | base-to-head `git diff --check` passed |

Authoritative execution records:

- R4 packet: `work/review/REV-0118/execution-packet-r4.md`, SHA-256
  `048265cf73aff73c1c83bdbf09a1b7bb71db339af2bb9b888d422bba85e02850`
- R4 result: `work/review/REV-0118/execution-result-r4.md`, SHA-256
  `81dc3e0218d57ea9e69189d017553bcde7898ae0f24cf679a5d26bcce3126ee0`
- R5 packet: `work/review/REV-0118/execution-packet-r5.md`, SHA-256
  `2aa5a119c47afeaba764e1f97ed98e8f967e3a198a6ca2aaef3b932d15dc5da3`
- R5 result: `work/review/REV-0118/execution-result-r5.md`, SHA-256
  `80199754f53512437b0497e74e4f3bb484a76b5bd0028d7b056999c6df4754eb`
- R6 failed-result record: `work/review/REV-0118/execution-result-r6.md`, SHA-256
  `03935315da3f2e36d79d6249f5767d7f00af09bbd4c1d0a332275c519ff4241a`
- R7 passing result: `work/review/REV-0118/execution-result-r7.md`, SHA-256
  `5bbc1cbe042e31c2bbf1482c8a131934cdf529b9788c0f7a84223f9677b3aa34`
- R8 final packet: `work/review/REV-0118/execution-packet-r8.md`, SHA-256
  `08427d02ba8e3e25c33ef3cf14e121a95aac2f9b01e7e3704e1579916d159344`
- R8 final result: `work/review/REV-0118/execution-result-r8.md`, SHA-256
  `4f4f26c609db486d333c7cbc1a6c1f09d75b4801aa84b4da08157f6ba48a7b9a`
- REV-0118 correction result: `work/review/REV-0118/result-r1.md`, SHA-256
  `cb5adaafc687a6a80a53709d8a66c6ffa361545b6da2f77210ea82f2d5694080`
- REV-0118 final verification: `work/review/REV-0118/result-r2.md`, SHA-256
  `14ebde3fb24498b0b9d2272c486eda7efef5a7524f9b84431cfd7741cd9a2a23`
- R4 matrix proof branch: `codex/m2-wo0170-fault-restore-sqlite-r3` at
  `1ed68fa79961c1a23b27e6da039c344c6cae4667`, tree
  `a4b3dbbd7da6c584ccbde37fd0a00acdb43063a0`
- R5 smoke proof branch: `codex/m2-wo0170-soak-smoke-sqlite-r1` at
  `87dbf2ece6f4b1fcf97dc55ca94a873b4be83cb7`, tree
  `d607bef24bd773b90e7de4c0454afe3c9afee63e`
- R8 final correction proof branch: `codex/m2-wo0170-rev0118-correction-sqlite-r3`
  at `b14cbb88061aab09f69ce219e9c1427a01873761`, tree
  `f4571503ad5a3b507b0ee33997d3335c317f68b4`

Every retained proof branch differs from its exact canonical source only by the authorized literal
`False` to `True` flag change. They and all generated databases are quarantined evidence, never
implementation predecessors. Failed R6 is retained honestly and superseded by passing R7/R8.

## Honest residuals

### Mandatory 24-hour soak — `NOT_RUN`

Only the one-cycle driver smoke ran. A future separately authorized run must create
`codex/m2-wo0170-24h-soak-r1` as a flag-only branch from accepted candidate
`2051afe2bbc21918fac6b69875e0a536fe722e49`, use one new evidence directory, no configured
database, and no other tracked change. The command is:

```powershell
New-Item -ItemType Directory -Path .codex-ddl-gate-run\wo0170-24h-r1
.\.venv\Scripts\python.exe -m harness.m2.soak --duration-seconds 86400 --python .\.venv\Scripts\python.exe --evidence-directory .codex-ddl-gate-run\wo0170-24h-r1
```

Interruption, any failed cycle, a changed build/profile, or less than 86,400 elapsed seconds remains
`NOT_RUN` or `FAILED`; it is never promoted to PASS.

### Frozen R16 G0-G7 conjunction — `NOT_EVALUATED`

The repository preserves the requirement but does not contain a current exact G0-G7 input
manifest with source coordinates, freshness/expiry identities, and one complete exact build/profile
binding. Those missing coordinates prevent an evidence-faithful evaluation. This is not a failed
implementation test and is not silently treated as satisfied.

### Operational and promotion surfaces — unpassed and unauthorized

Configured-database migration/use, runtime composition, credentials, broker/network calls, orders,
Paper observation, production soak, promotion, `master` merge, and M3 implementation were not run
or authorized. M2 closeout therefore freezes a reviewed persistence/startup baseline; it grants no
operational readiness or trading authority.

## Reproduction commands

```powershell
New-Item -ItemType Directory -Path .codex-temp\wo0170-reproduction
.\.venv\Scripts\python.exe -m pytest -q tests\execution_core --basetemp .codex-temp\wo0170-reproduction\ordinary -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -q tests\r2_conformance_oracle.py --basetemp .codex-temp\wo0170-reproduction\r2 -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\lint-imports.exe
```

Fresh-file SQLite reproduction requires the exact recorded flag-only proof branch and the packet's
new-root/stop rules. Do not run those commands from canonical flag-false source and do not edit the
DDL or authorization flag outside a separately recorded gate.
