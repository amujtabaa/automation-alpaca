# WO-0151 R11 R1 implementation candidate manifest

Status: **FROZEN LOCAL IMPLEMENTATION CANDIDATE**

Tracked parent: `b6cf1aadfd0aae27ada3262b854c2af30912c0d5a`.

This exact 11-path candidate implements only the ratified pure, deterministic,
I/O-free WO-0151 E2 controller, serial successor, canonical-fact, protection,
preemption, and constrained recovery behavior. It remains bounded by the active
work order and the accepted R11/R11-R1 composite. It adds no runtime wiring,
persistence, SQL/DDL, database, credential, broker/network, M2, merge, deletion,
cleanup, rebase, or force-push behavior.

## Authority pins

| Authority | SHA-256 |
| --- | --- |
| `work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `9906f0eab6f2afac232b321ee188ac7f2b38dc6520d3357bf619df9dc8065c63` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md` | `00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R11-R1.md` | `d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9` |
| `work/review/REV-0058/WO-0151-RED-CANDIDATE-R11-R1-MANIFEST.md` | `e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8` |
| `work/review/REV-0058/result-r11-r1.md` | `c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b` |

## Exact implementation paths

| Path | SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85` |
| `app/execution_core/acquisition.py` | `22326c338a6c5c0c3c6c3c98c24bcd3b95acb300eb064d168f1f060db3595985` |
| `app/execution_core/authority.py` | `5d9f22a77ba5e8ea38b126b2413f0c6a279c6a0a10e85d27d2358a4d2956d2c0` |
| `app/execution_core/identity.py` | `8f4b8472fe1de766cd3eea38472dae97ce9766ac0d93c79553eccee382f1781a` |
| `app/execution_core/protection.py` | `cfdee0230980728f31feb746ccc578b63596b47988abc2388b876184fc80c609` |
| `app/execution_core/venue.py` | `0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f` |
| `tests/execution_core/test_acquisition.py` | `d158a568aea701ed6a7c2500fdc11f620b4fa6534d86e1dde1fa0011235323b9` |
| `tests/execution_core/test_authority.py` | `f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791` |
| `tests/execution_core/test_import_boundary.py` | `f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4` |
| `tests/execution_core/test_protection.py` | `269ebeb2b1a5b87bec2685784843c78aab236179cbeb02a9fa8ccd0f80bbbffd` |
| `tests/execution_core/test_venue_ownership.py` | `63d6f7b04803b7e08c857b1ff9131e5bf8d792a2de2611998ef7d9677a6da754` |

## Fresh local evidence

- The complete pure `tests/execution_core` suite collected 1,344 tests and
  reached 100% with exit code 0 on Python 3.12.
- The combined acquisition, authority, venue-ownership, protection, and import-
  boundary semantic-center suites reached 100% with exit code 0.
- Ruff check and Ruff format verification passed for `app/execution_core` and
  `tests/execution_core`.
- Mypy passed with no issues in 87 application source files.
- Work-order scope, ledger, PKL, disposition, and `git diff --check` gates passed.
- The repository-configured 93% branch gate is not claimed from the lawful
  execution-core-only run. That run reached 87.62% across the whole configured
  package because repository tests outside `tests/execution_core` were omitted.
  Exact-head Python 3.11/3.12 CI remains the controlling full-repository gate.

One earlier local R2 invocation reached only pytest temporary-directory setup
and failed before test collection/body execution because the OS-owned pytest
temporary root was inaccessible. No fixture, SQL/DDL, database, or application
test body ran; it is not acceptance evidence and no conclusion relies on it.

## Remaining acceptance sequence

One fresh independent exact-candidate functional-conformance review must return
`ACCEPT` with P0=0/P1=0. Closeout reconciliation, commit/push, and unchanged
exact-head Python 3.11/3.12 CI remain subsequent gates; this manifest alone does
not close WO-0151 or activate WO-0152.
