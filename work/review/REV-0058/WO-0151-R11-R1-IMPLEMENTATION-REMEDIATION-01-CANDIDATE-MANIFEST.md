# WO-0151 R11 R1 implementation remediation 01 candidate manifest

Status: **FROZEN LOCAL FOCUSED-RECHECK CANDIDATE**

Tracked parent and current branch HEAD:
`b6cf1aadfd0aae27ada3262b854c2af30912c0d5a`.

This candidate preserves the complete original implementation candidate and
changes only the four implementation/test paths needed to close the sole P1 in
the retained independent result.  It adds the full E2 current/retired
FILL/CORRECT/BUST control matrix, retained failure-capable mutation evidence,
and the exact inactive-successor canonical-fact correction exposed by that
matrix.  It does not reopen the accepted architecture or widen WO-0151.

## Controlling pins

| Record | SHA-256 |
| --- | --- |
| Active WO-0151 | `9906f0eab6f2afac232b321ee188ac7f2b38dc6520d3357bf619df9dc8065c63` |
| R11 contract | `00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d` |
| R11 R1 correction | `d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9` |
| R11 R1 manifest | `e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8` |
| R11 R1 preflight acceptance | `c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b` |
| Original implementation manifest | `9d9a00bc9fa98e65fcd1d891f08ca860175c01b377d35049d0da6fa3b652e955` |
| Original acceptance request | `3f5deb64eb889070bee96986fc42a16baba9a01789ba57b86ef36bcc1d7088e9` |
| Retained `ACCEPT-WITH-CHANGES` result | `84484417c9dce913e8280ec517883646bd3f557678d4ea482734e72f9d929aba` |
| Remediation mutation evidence | `96509cbae091046d4df51c27cfbb45274ab038499c9fe90f3fc57c72bd42de79` |

## Exact implementation candidate

| Path | SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85` |
| `app/execution_core/acquisition.py` | `3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7` |
| `app/execution_core/authority.py` | `d59da7c2659f1decbd3ae30755813106af693ce89d6db91e47bc7489d3f2c4fb` |
| `app/execution_core/identity.py` | `8f4b8472fe1de766cd3eea38472dae97ce9766ac0d93c79553eccee382f1781a` |
| `app/execution_core/protection.py` | `cfdee0230980728f31feb746ccc578b63596b47988abc2388b876184fc80c609` |
| `app/execution_core/venue.py` | `0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f` |
| `tests/execution_core/test_acquisition.py` | `d8156e007ef21584f8bc03081e60b8a79027a09ee9d8b4f0379458ef510f0f7c` |
| `tests/execution_core/test_authority.py` | `f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791` |
| `tests/execution_core/test_import_boundary.py` | `f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4` |
| `tests/execution_core/test_protection.py` | `18c1ac5f50575fd36c2554b816c3313d9c6adcd4c98877fb9f879193d283f330` |
| `tests/execution_core/test_venue_ownership.py` | `63d6f7b04803b7e08c857b1ff9131e5bf8d792a2de2611998ef7d9677a6da754` |

Relative to the original implementation manifest, only
`acquisition.py`, `authority.py`, `test_acquisition.py`, and
`test_protection.py` have changed hashes.  The other seven implementation
paths are byte-identical.

## Exact P1 closure

- Current and follow-on fact controls now include `FILL`,
  `TRADE_CORRECT`, and `TRADE_BUST`, including non-tail reconciliation.
- Retired fact controls now include `FILL`, `TRADE_CORRECT`, tail
  `TRADE_BUST`, non-tail reconciliation `TRADE_BUST`, replay inertness, and
  fact-plus-live-successor preemption.
- Each path pins a single registry/economics/currentness/head update and refuses
  ordinary BUY/SELL authority unless the separately authenticated route owns
  it.
- Thirteen named R11/R11-R1 mutations were executed and turned their focused
  controls RED.  All production mutations were restored.
- The matrix-discovered inactive-slot defect is corrected at the authority
  owner: only an exact authentic inactive slot with matching retained
  descriptor, successor generation, and predecessor effect may omit
  preemption and continue through canonical-fact registration.  All active,
  stale, forked, or mismatched cases retain the stricter path.

## Fresh restored evidence

- Pure `tests/execution_core`: 1,353 collected, 100%, exit code 0.
- Combined matrix and mutation controls: 17/17 passed after restoration.
- Ruff check for `app` and `tests`: passed.
- Ruff format verification for all 11 authorized Python paths: passed.
- Mypy `app`: no issues in 87 source files.
- Work-order scope, ledger, PKL, disposition, and `git diff --check`: passed.
- A repository-wide format probe identified eight pre-existing files outside
  WO-0151 that Ruff would reformat.  None was changed and none is used to
  qualify this candidate.

One earlier local R2 invocation remains inadmissible negative environment
evidence: pytest failed at an inaccessible OS temporary root before collection,
fixture, SQL/DDL, database, or test-body execution.  No conclusion in this
candidate relies upon it.

This manifest does not close WO-0151, satisfy exact-head CI, activate WO-0152,
or authorize runtime, persistence, broker/network, M2, merge, deletion, or
cleanup work.
