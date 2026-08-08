# WO-0151 R12-R1 records-only activation-delta R2 manifest

Status: **whitespace-clean documentation-only activation candidate**

Review base commit: 6cd32a5f56d8ad3a303ef69b137dc43d4ffad9ce
Branch: codex/arch-reset-2026-07-r1

R2 replaces only the R1 manifest formatting diagnostic. It retains all
semantic, current-record, and frozen-exclusion content exactly and adds no
source/test authority.

## Retained R1 diagnostic evidence

| Path | SHA-256 | Treatment |
|---|---|---|
| work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-DELTA-R1-MANIFEST.md | f2b75ff6d774c5c79a95809a266cce94ecbf0be30542bf78b2aa03adc22448b1 | retained R1 manifest with P2 trailing-whitespace diagnostic |
| work/review/REV-0058/result-r12-r1-activation-r1.md | c5a19a3d0aa620bec4f8627916bee84e8e6c1518a28bd3acaf30f56af3d1496d | retained R1 ACCEPT P0=0/P1=0/P2=1 |
| work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-DELTA-R2-WHITESPACE-DISPOSITION.md | c85e447c7a00d10763e8302cdfc36922757c5166a1fd394641d1d1764ee14189 | R2 whitespace-only disposition |
| work/review/REV-0058/request-r12-r1-activation-r2.md | d811b99211fec50dd85fa439d2d7842cb931c378a6f7913d8da9304cabf50af9 | independent R2 request |

## Immutable semantic acceptance

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0058/WO-0151-RED-CONTRACT-R12-R1.md | 9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25 | accepted R12-R1 semantic contract |
| work/review/REV-0058/WO-0151-RED-CANDIDATE-R12-R1-MANIFEST.md | fd187177bc5815ef901b29e760eb7aa0c75dc4338e8866f541ccdc82ea216543 | accepted semantic freeze |
| work/review/REV-0058/result-r12-r1.md | 5dfec4ce0425642148561801d69a035f0fb4ddc540fb7baf93d23747dddb581b | independent semantic ACCEPT P0=0/P1=0/P2=0 |

## Retained initial activation packet

| Path | SHA-256 | Treatment |
|---|---|---|
| work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-DISPOSITION.md | fed532cc84e9183bfa513e1b035e586441beb9edebf81bdeeba1004f5b098430 | immutable original input with factual placeholder |
| work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-DELTA-MANIFEST.md | 80ee5b381dcdddd9662d21450bfa3e268fe3faac66e2dbd9e3496212310286a9 | immutable original activation freeze |
| work/review/REV-0058/request-r12-r1-activation.md | 97ca08ef481589ada6c45914c50692f28cd9c9723f7399fbac75c1c5f2cc2af6 | immutable original request |
| work/review/REV-0058/result-r12-r1-activation.md | c52df76eb6880d80be25d9c627b49066e182c1de4ef0b1c34878324f2195270b | retained ACCEPT not used for R2 activation |

## Exact current-record activation delta

| Path | SHA-256 | Permitted change |
|---|---|---|
| work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-DELTA-R1-DISPOSITION.md | b014abbc0fcd70cce47b2702fdc97a8efa55df5414835539333d4242b3f153bf | retain R1 correction disposition |
| work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-R1-DISPOSITION.md | 31dc7e1087b548538954f88a04a4ae66dc22200dc1a298f1518f89b6c86178cb | corrected publication/reconciliation plan |
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 782d6c2c48418d85018fc1140e3bc5c50215d3fcfb0cefc2a41c7824cccbfaf9 | semantic-ACCEPT/activation-pending posture |
| work/active/WO-0152-reset-kernel-e3-generation-conformance.md | a2e07e50d5eed1e0fa9acdbc0d2019b83bb005a20b8b217ab1d416d29967c299 | retain E3 pause through R12-R1 |
| pkl/project/goals.md | 0829310129db1cc02cc953b72f66d34b75df5d7c209d07d0bcdcf377467cbc31 | current-goal posture only |
| pkl/architecture/architecture-map.md | d6c68d583ab5ffb090069c87cdda9c0fa7abb081548951327617308534771126 | current architecture posture only |
| pkl/log.md | 87509707fe3b24a97f05289813d2e82eb64c981a0ae391e6c7ee9f3133bb1ac6 | append-only chronology only |
| work/ledger.jsonl | e3510d23829cb940ec8c5b7e1ce68e8125fa36a2158f97e9b3ea1ebe29e68e93 | append-only acceptance/activation-pending row |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | 907f115c589823c95e71c06f5659dca9b1b4abc90273da2afeabbc02efa58423 | append-only provenance only |

## Frozen exclusions and unaccepted working context

| Path | SHA-256 | Required treatment |
|---|---|---|
| tests/execution_core/test_acquisition_stateful.py | 1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22 | untracked frozen E3 detector; exclude and do not execute/edit |
| work/review/REV-0059/evidence.md | d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7 | frozen E3 negative evidence; unchanged |
| app/execution_core/acquisition.py | 15a7445ab590cef026283fce72d292441f22158060fcb13f52d83da90e78b5df | unaccepted former-R12 working context; exclude from commit |
| tests/execution_core/test_acquisition.py | 676617c02bc5582aa94987fe692a6b6234bd02ae4b3e24a611d37f64e3bbcef1 | unaccepted former-R12 working context; exclude from commit |
| app/execution_core/fills.py | 50832e3849aa3d3be888dd400a646dca04180dcf885aecabdecac0b3dbab6666 | unchanged proposed R12-R1 owner; no implementation yet |
| tests/execution_core/test_fill_position.py | 6b828be69059db39fac134cb31395d295d0c99574f275f53ad9327ec1c0e2d45 | unchanged proposed R12-R1 control owner; no implementation yet |

## Integrity and post-acceptance action

- result-r12-r1-activation-r2.md is absent before the independent reviewer
  writes it, and no path is staged.
- All listed pins must match. The R2 manifest itself must pass the focused
  untracked-candidate diff check with no trailing-whitespace diagnostic.
- An ACCEPT authorizes only a documentation-only activation commit containing
  named posture records and clean R2 packet artifacts, explicitly excluding
  all six frozen-exclusion rows and the retained R1 manifest.
- After that first commit, the only follow-up change is an exact-SHA
  reconciliation in named current records. Only that second documentation
  commit can make the four R12-R1 implementation paths active.
- Any other delta, including source/test, E3, contract, public API, database,
  runtime, network, CI, M2, merge, deletion, cleanup, force-push, or rebase
  work, is out of scope.
