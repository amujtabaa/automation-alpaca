# WO-0152 E3 implementation remediation 02 candidate manifest

Frozen: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

Base HEAD: `ae626f56fb05c09b312a7383326ebbf9ba584cd3`

Predecessor manifest SHA-256:
`7761f179a0c7c0aefc1045d8d956ab791c76bf425e6117c91bdd0f6853405ee3`

Predecessor result SHA-256:
`1fa71ac536e339b602255d17ef511c32415e5b9353c418af791b3426caba3091`
(`ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0).

## Exact publication candidate

| SHA-256 | Path |
| --- | --- |
| `79f826b9a209d587460d7eb5dfe80ef76691cf255f7a2032d4406289616564c5` | `.github/workflows/ci.yml` |
| `16649fac7dd39c5258eddcc9c2f0a7d80c3903c31f8ea2b21bcdf355a71a1c95` | `pyproject.toml` |
| `ca9ae7f4338827884fe128408c2d98567c48f1779a652157852ca5e92624f5da` | `.ai-os/scripts/check_coverage_ratchet.py` |
| `46aff0e4b450a04bca9a97a3df403eb78ed7229fccba8db103eb249d7dc3576d` | `tests/test_coverage_ratchet.py` |
| `b2f997d8438b198ab4d15985cb25bfb04babb69ea923bdf77c0917ca9fc1876d` | `tests/execution_core/test_acquisition_stateful.py` |
| `d380b333a680d4633ffc4d11e4296f6bf4b515a74f6ba7416ac9c5091f9c0ed2` | `work/active/WO-0152-reset-kernel-e3-generation-conformance.md` |
| `e0ae60e71c43089a67aa4d542a3631b69ad82f32f10db6e1322412814a844e5e` | `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` |
| `2f13df43c8cdb4776a485b0381cbe60395d703cbd866e7352bf2b8756c6cdd87` | `pkl/project/goals.md` |
| `da2cc98d2c2d62515140197147e2b6a7259965850890185d5311e0c915dde236` | `pkl/architecture/architecture-map.md` |
| `e70023ce88da9a09e40dcc746e0dc09331c36540984df38722764888db16fa94` | `pkl/log.md` |
| `1402f3efaf4ef2a2ac39e46142f3c2d3417fc7bb460a8a50c3e1256e3cff5982` | `work/ledger.jsonl` |
| `ee9df0c8a01831f0c6af17682d832babd50b2c8494e85d5e7be1c93f70493354` | `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` |
| `94bf0777e1d5fe6ce7c9b1bc0cb0ada8da048fda8bd5b8850032026d386aaad8` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-EVIDENCE.md` |
| `5bb2c37a1405f19882d9a95a1b8eb219b7f888340327b2b56afd5a9c74dcdd53` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-CANDIDATE-MANIFEST.md` |
| `e5c239e3a8a18c81dddc9eb4a78c35df1fbe14bc61abde8919a1dcb3a8422871` | `work/review/REV-0059/request-implementation.md` |
| `a8279d770bc226670745342f2247f480d3e35723f94cd98318fe20521d4905a9` | `work/review/REV-0059/result-implementation.md` |
| `bb06604708d75d48944cf6ddfc5625f96d3daa7a016274f4cf87187186b32096` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-REMEDIATION-01-DISPOSITION.md` |
| `7761f179a0c7c0aefc1045d8d956ab791c76bf425e6117c91bdd0f6853405ee3` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-R1-CANDIDATE-MANIFEST.md` |
| `049f5e11c09748cf3fa4a8bcc2d4b26be9c21b5cd743af202e47aeb939690909` | `work/review/REV-0059/request-implementation-r1.md` |
| `1fa71ac536e339b602255d17ef511c32415e5b9353c418af791b3426caba3091` | `work/review/REV-0059/result-implementation-r1.md` |
| `54031893ae9e0f7f5c821462848fa48092c9463fdc85b53ffc9ee9a3816c6861` | `work/review/REV-0059/WO-0152-E3-IMPLEMENTATION-REMEDIATION-02-DISPOSITION.md` |
| `d6ca774604c7d89abfed3c1ad8ecc885d5f3de9891fb8d8c7b3eb74a2b6d9b3e` | `work/review/REV-0059/request-implementation-r2.md` |
| `e423ce0a2a8034fbe1ee51b2694dae544916dd64ceb73773f0886dc7fdc5596c` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-SEMANTICS-AMENDMENT.md` |
| `a91a8f03327b07f5448c60549493dc5b777c10a22fe126da9710b085f6c4a7c2` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-CANDIDATE-MANIFEST.md` |
| `7a6062ce48b8a2d573309521cb9f64810cd7e6646bfb8b5a537266f52b3a64f9` | `work/review/REV-0061/request.md` |
| `6d33708046fc7e3ec726b725817b1db9db3e8461f306bf51a1fae5ff29f111dc` | `work/review/REV-0061/result.md` |
| `734f66b34de4a78d9c2f3b8e15e5dae0d11c794d4c76b7acfe6e2426d592a35b` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-REMEDIATION-01-DISPOSITION.md` |
| `230a5ec0d5aeccc68518a7def172e49d52aad7e22e218da692aa04a54aec8309` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-CANDIDATE-R1-MANIFEST.md` |
| `ceca70bbf572701b81d200e739d354766291fae2499e32b925b4452d9070bbe7` | `work/review/REV-0061/request-r1.md` |
| `d8931dda45422622c668927ba5c0777b5c4dda836ddcc17b1c2354f0bbad2d5c` | `work/review/REV-0061/result-r1.md` |
| `a644d68e3cdbda8d2a839824f600143212d76aaeab3523f4acdc49336041007f` | `work/review/REV-0061/implementation-evidence.md` |

The reviewer-owned `work/review/REV-0059/result-implementation-r2.md` is
excluded from this table and must be the independent seat's only write.

## Retained execution evidence

`coverage-e3-final-r3.json` is retained unstaged at SHA-256
`331b6886b8aa55bc1dd512074e67e5faa4578df8f701a1d33efd177966ae06bc`.
It is exact local-run evidence, not a publication source or external-CI claim.
All pytest temp trees, earlier coverage reports, and named historical raw
REV-0058/REV-0060 artifacts remain excluded and unchanged.

## Focused acceptance rule

The independent recheck is limited to the three P1 findings in the predecessor
result. Any change to a listed file invalidates this manifest. Acceptance
requires P0=0 and P1=0. The candidate makes no M1 closeout or external-CI
success claim. The reviewer may not edit candidate files, commit, push, run
broker/Alpaca/network or database/SQL/DDL work, implement M2, merge, create a
PR, delete, clean up, force-push, or rebase.
