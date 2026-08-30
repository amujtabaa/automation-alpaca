# REV-0118 WO-0170 corrected soak-driver smoke packet R5

Status: authorized narrow correction proof under WO-0170's recorded self-directed completion
authority. It does not repeat or supersede R4's passed 259-case database matrix.

## Exact source and protected identities

- Canonical branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Source commit: `3b3b1462bc8a52e6dd4308121e87545bd11f6a70`
- Source tree: `800b0f7a56eda308d445810dc998107597f7c539`
- Quarantined proof branch: `codex/m2-wo0170-soak-smoke-sqlite-r1`
- `SCHEMA_DDL`: 190,705 UTF-8 bytes
- DDL SHA-256 and expected digest:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- Source authorization flag: exact literal boolean `False`
- Gated fault test SHA-256:
  `920b41ba3b85d530ad0a0232c90b75427e5d57debad6743cd393d810b9e46e89`
- Gated restore test SHA-256:
  `c712c7e08dda0a5173cf6734c619a9e17bd7ab543ce50944b94dd415276afe01`
- Gated boundedness test SHA-256:
  `dde8b1f6a99b5f931cb469f08766b37c21b58bd1c932f6f2c498e1400fd45f75`
- Closeout catalog SHA-256:
  `5bf96014af598bb01d513c6ef6eab2de703886a5fe18f0bccba7aa8fe34a32a8`
- Corrected soak driver SHA-256:
  `9deff7a6be5035e6a7dcbec06482506a6acebf1a655502fa912100d201d0fdd6`
- Pure soak regression test SHA-256:
  `f209f2424848f9bedb47bebd9a3914802f80e5557af359f24fefd5f08ce839b4`

## Evidence inheritance and correction

R4's first command passed all 259 cases against exactly the same production, DDL, and gated-test
bytes listed above. Its smoke then returned 173 passed / 7 setup errors solely because
`harness/m2/soak.py` did not create the parent of each nested pytest basetemp. The canonical fix is
one `cycle_root.mkdir()` call plus a pure test that fails if subprocess invocation precedes parent
creation. That pure file passes 33 tests, and ruff/format checks pass.

R5 therefore proves only the corrected driver path. It must execute the same seven-node schedule
for one cycle, return process exit 0, and write summary status `NOT_RUN` with
`all_cycles_passed=true`. A one-second smoke cannot satisfy the mandatory 24-hour soak.

## Unlock and execution

Create the proof branch from the exact source commit. Its sole source change sets
`DDL_EXECUTION_AUTHORIZED_BY_AMEEN` in
`app/execution_core/persistence/schema.py` from exact boolean `False` to exact boolean `True`.
Publish the unlock and reverify all protected identities except the expected flag-only
`schema.py` blob change.

Create only the empty parent directory `.codex-ddl-gate-run\rev-0118-r5`; the evidence directory
itself must not exist. Then execute exactly:

```powershell
.\.venv\Scripts\python.exe -m harness.m2.soak --duration-seconds 1 --max-cycles 1 --python .\.venv\Scripts\python.exe --evidence-directory .codex-ddl-gate-run\rev-0118-r5\soak-smoke
```

## Stop rules

- Any substantive assertion, integrity, fixture, DDL, or harness failure ends this execution.
- One retry is permitted only for a proven environmental interruption with zero tracked changes
  and a different empty evidence root.
- No changed DDL, configured or in-memory database, migration, runtime composition, credential,
  broker/network activity, order, promotion, master merge, history rewrite, or M3 implementation.
- The proof branch and generated databases are quarantined evidence and never an implementation
  predecessor.
