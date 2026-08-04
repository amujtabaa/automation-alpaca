# WO-0148 occurrence-receipt successor evidence

Status: **PRE-FREEZE IMPLEMENTATION EVIDENCE — NOT ACCEPTANCE**

Candidate predecessor: `34eb7f4aeea96c60522c4a8ca1b4575de41ffa39`

Activation review base: `d75806b1a79d1769db25ae962c0977cd9388a886`
Successor candidate: pending immutable freeze

## Exact candidate inputs before freeze

| Path | SHA-256 | Git blob |
|---|---|---|
| `app/execution_core/protection.py` | `3A969AB9729C15A4846A4E8B1B10E61C565BBF3C107AAB766FD1B7B8E74A09B6` | `e6ad45456e412761843fb2b49e76b4f6afb080e6` |
| `tests/execution_core/test_protection.py` | `D4F031877F7F6A45A66D9BA8B748FB85E7F05B3D4A370031C68AE71EA2028786` | `6add21100ec4f815ce577824a011a9ca4d09ce30` |
| `tests/execution_core/test_protection_stateful.py` | `BDE0E57055437CEDC6AB34B8264842E15DEAC3E55037D3C95CF4A32B12D8F421` | `9e0df600ecce0fbc28df2169955f6c7d37639347` |

`venue.py`, `authority.py`, and every other production file are unchanged from candidate
`34eb7f4`. The compact review request/result and successor evidence documents are separate audit
records; raw test artifacts remain intentionally untracked under `evidence/`.

## Fresh executable gates

| Gate | Result | JUnit SHA-256 |
|---|---:|---|
| Affected authority/protection/stateful/import | 495/495 pass | `8859933B20EE7FD1008102E31D301516635C86D17571C43A3AD8CE29AEA65CA6` |
| Predecessor corpus | 745/745 pass | `C07F74964C2859E8E81B1D073D9B9D773E5D8DF81E18692CCFB6D85D8807DC43` |
| R2 conformance oracle | 61/61 pass | `13DF9E3A75E0F2F90314BFFE579CC0E784C996309CFE5E3A3A45943E28391129` |
| Complete execution core | 1,071/1,071 pass | `C4A146C573DD0841853C072DF4FCB002EF277013E28FFD66E9D12FA3F47EA0E7` |
| Full repository | 5,659 tests; 0 failures; 0 errors; 12 skipped | `E6703C122B7D07B0D34C479ACCC1837D47A7E61700336237C913383597F07534` |

The full command was:

```powershell
$env:BROKER_ADAPTER='mock'
$env:COVERAGE_FILE='work/review/REV-0050/evidence/replay-retention-full-gate-01/.coverage-full'
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  --basetemp=work/review/REV-0050/evidence/replay-retention-full-gate-01/pytest-full `
  --cov=app --cov-branch --cov-report=term-missing `
  --cov-report=json:work/review/REV-0050/evidence/replay-retention-full-gate-01/coverage.json `
  --junitxml=work/review/REV-0050/evidence/replay-retention-full-gate-01/junit.xml
```

Raw combined coverage is `93.14745457067555%`: 19,812 of 20,876 statements and 7,048 of 7,960
branches covered. The configured 93% floor passes. Artifact hashes are:

- coverage JSON: `70ABC0E43E69278AB7E0E282675ED9A7BD0EE9E42C71B77A9939EFB320FD9BCA`;
- raw coverage database: `D5527FD269ADC0E9D65BB9C47EFA377CB8072A5BCA8B278637CA5D0032833B83`.

Existing mock/disposable test-only fixtures ran under recorded authority. No credential, Alpaca,
external broker/network, runtime wiring, or persistent application-database operation was used.

## Static, scope, and governance gates

- Ruff repository lint: pass; exact nine changed Python files format-check: pass.
- Mypy: success across 86 application source files.
- Python 3.11 grammar parse: 9/9 changed Python files pass.
- Import Linter: six contracts kept, zero broken.
- `git diff --check`: pass.
- Activation-base tracked range plus allowed untracked `REV-0050` paths: scope check pass.
- AI Project OS install/version/ledger/PKL/disposition checks: pass.
- ADR-020/021/022 hashes exactly match the ratification index.
- Ten registered worktrees: primary contains this expected candidate; 9/9 auxiliaries clean.

The first worktree probe was rejected by Git's sandbox ownership check and is not evidence. The
reported clean result comes from a second read-only probe using command-local `safe.directory`
values; no global Git configuration changed.

## Deferred gates

Immutable successor freeze, fresh independent exact-candidate acceptance, WO/ledger/PKL closeout,
push, and unchanged exact-head Python 3.11/3.12 CI remain pending. WO-0149 and M2 remain inactive.
