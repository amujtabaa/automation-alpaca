# WO-0152 E3 implementation candidate manifest

Frozen: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

Base HEAD: `ae626f56fb05c09b312a7383326ebbf9ba584cd3`

## Exact publication candidate

| SHA-256 | Path |
| --- | --- |
| `79f826b9a209d587460d7eb5dfe80ef76691cf255f7a2032d4406289616564c5` | `.github/workflows/ci.yml` |
| `16649fac7dd39c5258eddcc9c2f0a7d80c3903c31f8ea2b21bcdf355a71a1c95` | `pyproject.toml` |
| `ca9ae7f4338827884fe128408c2d98567c48f1779a652157852ca5e92624f5da` | `.ai-os/scripts/check_coverage_ratchet.py` |
| `153a2e032e5107a811476e41497c16127e685db8880be6df1c63706423f434dd` | `tests/test_coverage_ratchet.py` |
| `c046519bf15e87fb2b63f438d2dc9c65baffe51c4625255fe0297cfbdc231360` | `tests/execution_core/test_acquisition_stateful.py` |
| `5f6602f3e0e0d70820fa2ecc76a02d3ac6c425f2e9d7525ce0e52f82a056743b` | `work/active/WO-0152-reset-kernel-e3-generation-conformance.md` |
| `0bb4c87b0d247095a8446a1d73867453cd1a96038ea45b7386463bd6d96250c5` | `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` |
| `5742f5e3ab210fad91c638282fe4c1e8789e98d44349ed86307c8b90f72d8e7a` | `pkl/project/goals.md` |
| `7c311860f7e6ef545d63448f2f6bfbc4bb00c6e7725216106d677b021e4f267b` | `pkl/architecture/architecture-map.md` |
| `31befcf5ea7e1cc67fcb5512e8bc6e048352303a35016c24c9e9d5c5f03d4aa0` | `pkl/log.md` |
| `8553675082ee79552df9c0006c30ee2bf5de784cb134f8075bcd85a06d160a0b` | `work/ledger.jsonl` |
| `4bf1662adab9028b80ed38d219130ea2744addf08bdffec36bd93ec2306fef35` | `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` |
| `3ba5b09915e385a7e2b2f34c47e88c6657362025349ea9b616c90f3e49601b82` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-EVIDENCE.md` |
| `e5c239e3a8a18c81dddc9eb4a78c35df1fbe14bc61abde8919a1dcb3a8422871` | `work/review/REV-0059/request-implementation.md` |
| `e423ce0a2a8034fbe1ee51b2694dae544916dd64ceb73773f0886dc7fdc5596c` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-SEMANTICS-AMENDMENT.md` |
| `a91a8f03327b07f5448c60549493dc5b777c10a22fe126da9710b085f6c4a7c2` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-CANDIDATE-MANIFEST.md` |
| `7a6062ce48b8a2d573309521cb9f64810cd7e6646bfb8b5a537266f52b3a64f9` | `work/review/REV-0061/request.md` |
| `6d33708046fc7e3ec726b725817b1db9db3e8461f306bf51a1fae5ff29f111dc` | `work/review/REV-0061/result.md` |
| `734f66b34de4a78d9c2f3b8e15e5dae0d11c794d4c76b7acfe6e2426d592a35b` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-REMEDIATION-01-DISPOSITION.md` |
| `230a5ec0d5aeccc68518a7def172e49d52aad7e22e218da692aa04a54aec8309` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-CANDIDATE-R1-MANIFEST.md` |
| `ceca70bbf572701b81d200e739d354766291fae2499e32b925b4452d9070bbe7` | `work/review/REV-0061/request-r1.md` |
| `d8931dda45422622c668927ba5c0777b5c4dda836ddcc17b1c2354f0bbad2d5c` | `work/review/REV-0061/result-r1.md` |
| `a644d68e3cdbda8d2a839824f600143212d76aaeab3523f4acdc49336041007f` | `work/review/REV-0061/implementation-evidence.md` |

The reviewer-owned `work/review/REV-0059/result-implementation.md` is excluded
from this table and must be the independent seat's only candidate write.

## Retained execution evidence

`coverage-e3-final.json` is retained unstaged at SHA-256
`02941f1052a912a9484736f478e44495fc3ed08d4a4f719d90ba7eb168c638e0`.
It is local exact-run evidence, not a publication source or external-CI claim.
All pytest temp trees, earlier coverage reports, and named historical raw
REV-0058/REV-0060 artifacts remain excluded and unchanged.

## Freeze and acceptance rule

Any change to a listed file invalidates this manifest and requires replacement
freeze/review. Acceptance requires P0=0 and P1=0. The candidate makes no M1
closeout or external-CI success claim. The reviewer may not edit candidate
files, commit, push, run broker/Alpaca/network or database/SQL/DDL work,
implement M2, merge, create a PR, delete, clean up, force-push, or rebase.
