# WO-0152 E3 implementation remediation 01 candidate manifest

Frozen: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

Base HEAD: `ae626f56fb05c09b312a7383326ebbf9ba584cd3`

Predecessor manifest SHA-256:
`5bb2c37a1405f19882d9a95a1b8eb219b7f888340327b2b56afd5a9c74dcdd53`

Predecessor result SHA-256:
`a8279d770bc226670745342f2247f480d3e35723f94cd98318fe20521d4905a9`
(`ACCEPT-WITH-CHANGES`, P0=0/P1=4/P2=0).

## Exact publication candidate

| SHA-256 | Path |
| --- | --- |
| `79f826b9a209d587460d7eb5dfe80ef76691cf255f7a2032d4406289616564c5` | `.github/workflows/ci.yml` |
| `16649fac7dd39c5258eddcc9c2f0a7d80c3903c31f8ea2b21bcdf355a71a1c95` | `pyproject.toml` |
| `ca9ae7f4338827884fe128408c2d98567c48f1779a652157852ca5e92624f5da` | `.ai-os/scripts/check_coverage_ratchet.py` |
| `153a2e032e5107a811476e41497c16127e685db8880be6df1c63706423f434dd` | `tests/test_coverage_ratchet.py` |
| `25b09fcb22c9e8a8880612c4dcb40f86b798a89378abd670ee4427e1375f6d55` | `tests/execution_core/test_acquisition_stateful.py` |
| `cee87c6cf47cfb93f8b69f5c30984ac7a6837f9bbb5168d548c0c443e5079f7c` | `work/active/WO-0152-reset-kernel-e3-generation-conformance.md` |
| `f4d8e7ed34accb8417dadb037887c2a67b8ced6f828ad31a9059d2977cb61a87` | `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` |
| `e21688333a90bc049bd9e9e32c9572339130bc393a9e80981959b752a6847548` | `pkl/project/goals.md` |
| `abde01183dbc0e5517450c060870f3ef80e88483cdedd99b2c35338710450e69` | `pkl/architecture/architecture-map.md` |
| `09099f3caa6658553d5b9e7c26284ac88b115dd57c64dff807e6efc74ececf39` | `pkl/log.md` |
| `f855b56788d1fbb037925c0a9799a99cea0c10e945e0425c8e323c679ef6eb6c` | `work/ledger.jsonl` |
| `498b76f183b360219f44a09bf2e6bbdc9e669ea11a161d614762d02272af3615` | `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` |
| `a121feab847dda3a34ec3021c842ba499d91079b9cd2a7da0053d52672029547` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-EVIDENCE.md` |
| `5bb2c37a1405f19882d9a95a1b8eb219b7f888340327b2b56afd5a9c74dcdd53` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-CANDIDATE-MANIFEST.md` |
| `e5c239e3a8a18c81dddc9eb4a78c35df1fbe14bc61abde8919a1dcb3a8422871` | `work/review/REV-0059/request-implementation.md` |
| `a8279d770bc226670745342f2247f480d3e35723f94cd98318fe20521d4905a9` | `work/review/REV-0059/result-implementation.md` |
| `bb06604708d75d48944cf6ddfc5625f96d3daa7a016274f4cf87187186b32096` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-REMEDIATION-01-DISPOSITION.md` |
| `049f5e11c09748cf3fa4a8bcc2d4b26be9c21b5cd743af202e47aeb939690909` | `work/review/REV-0059/request-implementation-r1.md` |
| `e423ce0a2a8034fbe1ee51b2694dae544916dd64ceb73773f0886dc7fdc5596c` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-SEMANTICS-AMENDMENT.md` |
| `a91a8f03327b07f5448c60549493dc5b777c10a22fe126da9710b085f6c4a7c2` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-CANDIDATE-MANIFEST.md` |
| `7a6062ce48b8a2d573309521cb9f64810cd7e6646bfb8b5a537266f52b3a64f9` | `work/review/REV-0061/request.md` |
| `6d33708046fc7e3ec726b725817b1db9db3e8461f306bf51a1fae5ff29f111dc` | `work/review/REV-0061/result.md` |
| `734f66b34de4a78d9c2f3b8e15e5dae0d11c794d4c76b7acfe6e2426d592a35b` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-REMEDIATION-01-DISPOSITION.md` |
| `230a5ec0d5aeccc68518a7def172e49d52aad7e22e218da692aa04a54aec8309` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-CANDIDATE-R1-MANIFEST.md` |
| `ceca70bbf572701b81d200e739d354766291fae2499e32b925b4452d9070bbe7` | `work/review/REV-0061/request-r1.md` |
| `d8931dda45422622c668927ba5c0777b5c4dda836ddcc17b1c2354f0bbad2d5c` | `work/review/REV-0061/result-r1.md` |
| `a644d68e3cdbda8d2a839824f600143212d76aaeab3523f4acdc49336041007f` | `work/review/REV-0061/implementation-evidence.md` |

The reviewer-owned `work/review/REV-0059/result-implementation-r1.md` is
excluded from this table and must be the independent seat's only write.

## Retained execution evidence

`coverage-e3-final-r1.json` is retained unstaged at SHA-256
`220e370e82d99b61962e0d4b7460fe711cd97ad2f430bce6b7c3c0484f0e36f2`.
It is exact local run evidence, not a publication source or external-CI claim.
All pytest temp trees, earlier coverage reports, and named historical raw
REV-0058/REV-0060 artifacts remain excluded and unchanged.

## Focused acceptance rule

The independent recheck is limited to the four P1 findings in the predecessor
result. Any change to a listed file invalidates this manifest. Acceptance
requires P0=0 and P1=0. The candidate makes no M1 closeout or external-CI
success claim. The reviewer may not edit candidate files, commit, push, run
broker/Alpaca/network or database/SQL/DDL work, implement M2, merge, create a
PR, delete, clean up, force-push, or rebase.
