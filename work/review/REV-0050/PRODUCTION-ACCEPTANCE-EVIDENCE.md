# WO-0148 production acceptance evidence

Status: **PRE-FREEZE EVIDENCE COMPLETE — INDEPENDENT ACCEPTANCE PENDING**

Review base: `d75806b1a79d1769db25ae962c0977cd9388a886`

Starting implementation head: `486b2500e2767f4874b2188bd81af2c908036b57`

This record consolidates the final working-tree evidence for the pure, unwired WO-0148
candidate. It is not an implementation-seat acceptance verdict and does not close WO-0148,
activate WO-0149, or authorize runtime, persistence, broker, credential, merge, deletion, or
cleanup activity.

## Final root correction

The late P1 family is closed at its owner by one private append-only sequence of advancing
`_ProtectionTransitionProof` values. Slow audit validation reconstructs the sequence commitment,
validates every exact proof and per-scope predecessor chain, and pins each current protection
cursor and retained execution snapshot to the terminal proof. Non-genesis proofs bind their
predecessor cursor to the predecessor execution commitment and checkpoint. The protection reducer
returns `STALE` when an advancing projection's predecessor execution commitment differs from the
current protection state.

Non-advancing unresolved reconciliation remains fail-closed without publishing a replacement
protection snapshot. Exact technical replay retains its bounded path. No public capability,
runtime wiring, persistence path, broker path, or caller-shaped cache was added.

The original failure-capable and restoration evidence remains unchanged under:

- `evidence/p1-transition-chain-red-01/`: two expected failures before correction;
- `evidence/p1-transition-chain-green-02/`: three corrected controls pass;
- `evidence/p1-mutation-14/`: complete terminal-ledger pin comparison removed, control fails,
  then restores;
- `evidence/p1-mutation-15/`: predecessor execution seal comparison removed, control fails,
  then restores; and
- `evidence/p1-mutation-16/`: reducer predecessor continuity comparison removed, control fails,
  then restores.

## Coverage gate correction

`evidence/full-gate-02/` completed 5,616 tests with zero failures/errors and 12 skipped/expected
outcomes, but its raw combined line/branch coverage was only
`92.88836467078332%`. It therefore failed the authoritative 93% coverage gate and is not green
evidence.

The correction adds 35 table-driven negative controls for material ordered-history, terminal
authority, snapshot, account-registry, reconciliation-cursor, immutable update, and proof-envelope
rejection paths. A focused coverage comparison shows they execute 70 line/branch units that were
missing from `full-gate-02`; they add no production behavior.

Failure capability is explicit. With only the ordered-history commitment comparison temporarily
disabled, the exact `history-commitment` case failed because validation did not raise
(`evidence/coverage-strength-mutation-01/mutant.junit.xml`, 1 test / 1 failure). After restoration,
the same case passed and `venue.py` returned to SHA-256
`09867228bff78203c38952de4348b68d4a7b84d9ce3f7d554006f47e1be4a475`.

The final full run used the unchanged CI-equivalent coverage shape plus isolated evidence paths:

```powershell
$env:BROKER_ADAPTER='mock'
$env:COVERAGE_FILE='work/review/REV-0050/evidence/full-gate-03/.coverage-full'
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  --basetemp='work/review/REV-0050/evidence/full-gate-03/pytest-full' `
  --cov=app --cov-branch --cov-report=term-missing `
  --cov-report=json:work/review/REV-0050/evidence/full-gate-03/coverage.json `
  --junitxml=work/review/REV-0050/evidence/full-gate-03/junit.xml
```

Result: **5,651 tests / 0 failures / 0 errors / 12 skipped or expected outcomes** in
1,662.558 seconds. Raw combined coverage is **93.13120099909804%**: 19,804 of 20,870 statements
and 7,042 of 7,956 branches covered. The configured 93% floor passes.

Existing mock/disposable test-only fixtures ran under the recorded authorization. No credential,
Alpaca/broker call, external network I/O, or persistent application-database change was used.

## Fresh final-tree functional gates

| Gate | Result | Evidence SHA-256 |
|---|---:|---|
| Coverage-strength matrix | 35/35 pass | `dea5b357c3564fd1f485ccc0a6b3a40e2400ccf78e457d7302a90fdee5a648f5` |
| Coverage mutation | 1/1 expected failure | `d7f5caf26ceaa7910ae7e2d52f8529ac461f5ddd0d63a2c3ff2b3e1f8708555f` |
| Mutation restoration | 1/1 pass | `9a0867c7b705e22a3af3841a4008b5f9d0173738fb31cb4a0a3858f5bc07db65` |
| Affected authority/protection/stateful/import | 487/487 pass | `4a1a2a0c33928ec6feda35fafc1b1d140e7242f8a7997c345213de6fd54b4863` |
| Predecessor corpus | 745/745 pass | `6d1417d88be25d40fe2402bd4a3f69a6eda4490884241f9e4f60fdb59739fb50` |
| R2 conformance oracle | 61/61 pass | `4b4fe313bb65a439612849cb890d18b25f82331b15ba37f1476f887d3d20c216` |
| Complete execution core | 1,063/1,063 pass | `76e7d231b98e48dc420d52cd01a7c6286afb25a8dcba04e10afce97779a38868` |
| Import/public-boundary controls | 17/17 pass | `852e6458105e1fb38fad6dae8fa942e4d38bd46cb786a58988e16b41ae7a00e0` |
| Full repository JUnit | 5,651 / 0 failures / 0 errors / 12 skipped | `be1624870d6b92a0fbaa6f7bbfaf7db58a6e5a736003ab20e1bfc04b3bf8dbe8` |
| Full repository coverage JSON | 93.13120099909804% | `12d2fe88df7c425a83b76b7445221acc137affd12d5aef8af03bd781ccfbe95b` |

The affected-set JUnit is
`work/review/REV-0050/evidence/coverage-regate-01/junit.xml`; its SHA-256 is
`4a1a2a0c33928ec6feda35fafc1b1d140e7242f8a7997c345213de6fd54b4863`.

## Fresh final-tree static and governance gates

- `python -m ruff check .`: pass.
- Ruff format check over all nine changed Python files: 9/9 pass.
- `python -m mypy app`: success across 86 source files.
- Python 3.11 grammar parse over all nine changed Python files: 9/9 pass.
- `lint-imports`: six contracts kept, zero broken.
- `git diff --check`: pass.
- Activation-base plus allowed untracked candidate paths through
  `.ai-os/scripts/check_work_order_scope.py`: `SCOPE CHECK PASSED`.
- AI Project OS install, version, ledger, PKL, and work-order-disposition checks: pass.
- Accepted ADR-020/021/022 SHA-256 values: 3/3 match the ratification index.
- Registered auxiliary worktrees: 9/9 clean using per-worktree `status --porcelain`.

A repository-wide `ruff format --check .` also reports ten pre-existing out-of-scope files that
would be reformatted. That scan is not reported as green, those files were not changed, and the
authoritative WO changed-file format gate above passes. CI's repository-wide lint gate is
`ruff check .`, which also passes.

## Candidate file hashes before freeze

| Path | SHA-256 |
|---|---|
| `app/execution_core/__init__.py` | `bff2315b6b0c4e69ff228ac6e1a6837ecd143b0063100b7b1b7a4e8038d4e0d5` |
| `app/execution_core/authority.py` | `bb23bad8341bd815402483b2f26931b67b865d664dfe79e15464f4296b15fce0` |
| `app/execution_core/identity.py` | `24428e5c1992a5d2d0578161019dba5dbb67f784c9f69b43fd1c7a1149fad007` |
| `app/execution_core/protection.py` | `af0a44537721b75308efd5af786e3c1e38e15fb69da7520df94c68249f08e4e7` |
| `app/execution_core/venue.py` | `09867228bff78203c38952de4348b68d4a7b84d9ce3f7d554006f47e1be4a475` |
| `tests/execution_core/test_authority.py` | `ab0abbd92f793433aebd48f96c1d54094cba916faad6cac28be226164df57f7d` |
| `tests/execution_core/test_import_boundary.py` | `c90d00bfb65885fc7bb9def333e335f9e7e04812b669412405a50d9d3df31c9f` |
| `tests/execution_core/test_protection.py` | `35066ac8e8858809137672bd3ce3bad762bf4ea093cef9f81687760abca8628e` |
| `tests/execution_core/test_protection_stateful.py` | `094cfa7a11b69b462dc03dfe04c22dc3b56fd780bd21cc8dc899e96b1a8c2957` |

## Remaining gates

The implementation seat has not accepted or closed WO-0148. The next required steps are:

1. freeze this exact candidate as an immutable commit and rerun exact-range scope/status checks;
2. obtain a fresh independent exact-candidate `ACCEPT` with P0=0/P1=0;
3. resolve and re-gate any finding before closeout;
4. only after independent acceptance, move the WO to `work/completed/keep`, append the ledger,
   update PKL and the narrowly authorized status-only documents, and commit the closeout; and
5. push that unchanged closeout head and require Python 3.11 and 3.12 CI success before WO-0149
   activation.
