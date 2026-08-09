# WO-0151/WO-0152 M1 closeout records candidate manifest

Frozen: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

Implementation HEAD: `c148b93bb66cc7d943615337eb4ddf1ab61313ee`

Implementation parent: `ae626f56fb05c09b312a7383326ebbf9ba584cd3`

Implementation tree: `0bbe3a0432bb1a62bfa1a5cd849e43d989b5bbaa`

## Accepted implementation authority

- Final R3 candidate manifest SHA-256:
  `ecc85f9ad803080a7a159468be404ecacb60464db0249316fdfba0a962f3ae46`.
- Final independent R3 result SHA-256:
  `96680be9a550bf40e48104e12686dfab985866cd76d5c0de6e46519698a2ac9c`,
  verdict `ACCEPT`, P0=0/P1=0/P2=0.
- Coverage semantics R1 manifest SHA-256:
  `230a5ec0d5aeccc68518a7def172e49d52aad7e22e218da692aa04a54aec8309`.
- Coverage semantics R1 result SHA-256:
  `d8931dda45422622c668927ba5c0777b5c4dda836ddcc17b1c2354f0bbad2d5c`,
  verdict `ACCEPT`, P0=0/P1=0/P2=0.

## Exact-head implementation CI

GitHub Actions run #771, ID `31291594513`, URL
`https://github.com/amujtabaa/automation-alpaca/actions/runs/31291594513`,
tested exact SHA `c148b93bb66cc7d943615337eb4ddf1ab61313ee`.

| Python | Job ID | Conclusion | Tests | Lines | Branches |
| --- | --- | --- | --- | --- | --- |
| 3.11 | `93189636264` | `success` | 5,977 passed; 11 skipped; 1 xfailed | 24,826/26,530 = `93.577083%` | 8,460/9,920 = `85.282258%` |
| 3.12 | `93189636234` | `success` | 5,977 passed; 11 skipped; 1 xfailed | 24,826/26,530 = `93.577083%` | 8,461/9,920 = `85.292339%` |

Every workflow step completed successfully in both jobs, including Ruff,
mypy, import boundaries, contamination guard, AI-OS hygiene, R2 oracle, full
pytest/coverage, and the independent `93.00%` line / `85.25%` branch ratchets.

## Exact records-only closeout candidate

| SHA-256 | Path |
| --- | --- |
| `a361936a215d1a8298b9cf57d1445c6e5359ae336d31e4656b4755f3d8367c1c` | `work/completed/keep/WO-0152-reset-kernel-e3-generation-conformance.md` |
| `ee68a27344f7bd018d603bb0a22ec42f2a5901bece40c2c36e4be6c3033a1449` | `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` |
| `e89483556f2b56c84279311c453523a9c994f8c9a4c39aa88c465d267897c197` | `pkl/project/goals.md` |
| `dd59a1398dc096699f9f3720d4991067def01981dad55ba167c6cac177d8b7fa` | `pkl/architecture/architecture-map.md` |
| `b7b880326a07164dd9f4bf5fcd75d10cc8c74745e4b4c51744e3c317655c7d2a` | `pkl/log.md` |
| `89a4188bd07a51f4f39ae82782ace6680092f4d58279af77feae2e3c6fb64352` | `work/ledger.jsonl` |
| `6f51408f75e1b68f16d2e995c1611ffbf2373dcbe60cf5488d0a889a1e2e83f0` | `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` |
| `aab4b336c1cc124db3b9d865425fa18c0355873bb2cd5d399b638c64fb6345f0` | `work/review/REV-0059/handoff.md` |
| `488ed8cf9a49109fcab4cafef12d09eaa9743496cdc2751df6a9a7eb6bcaeb6b` | `work/review/REV-0059/request-closeout.md` |

This manifest is self-excluded. The reviewer-owned
`work/review/REV-0059/result-closeout.md` is also excluded and must be the
independent closeout seat's only write.

## Retained predecessor evidence

| SHA-256 | Path |
| --- | --- |
| `0ed4ce1c6283144089ddc9cb0a160da8f8e5eecd9e24a40f3d0ecad9c24aafd2` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-EVIDENCE.md` |
| `ecc85f9ad803080a7a159468be404ecacb60464db0249316fdfba0a962f3ae46` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-R3-CANDIDATE-MANIFEST.md` |
| `96680be9a550bf40e48104e12686dfab985866cd76d5c0de6e46519698a2ac9c` | `work/review/REV-0059/result-implementation-r3.md` |
| `230a5ec0d5aeccc68518a7def172e49d52aad7e22e218da692aa04a54aec8309` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-CANDIDATE-R1-MANIFEST.md` |
| `d8931dda45422622c668927ba5c0777b5c4dda836ddcc17b1c2354f0bbad2d5c` | `work/review/REV-0061/result-r1.md` |

All accepted manifests/results and dated negative evidence remain byte-stable.
Run #741 remains coverage-negative evidence and is not reclassified.

## Scope and final effectiveness rule

The candidate delta from `c148b93bb66cc7d943615337eb4ddf1ab61313ee` is
records-only. It contains no `app/`, `tests/`, `.github/`, `.ai-os/scripts/`,
`pyproject.toml`, accepted ADR body, generated pytest/coverage artifact, or
runtime/configuration change. The source work order moves atomically from
`work/active` to `work/completed/keep`.

Generated pytest/coverage artifacts and retained format-blocked historical
REV-0058/REV-0060 artifacts remain unstaged and unchanged. No deletion or
cleanup is part of this candidate.

The records-only publication commit must itself pass exact-head Python 3.11
and 3.12 CI before the overall M1 completion claim becomes effective. That
external run binds the immutable records commit and terminates the closeout;
no recursive evidence-only successor commit is required.
