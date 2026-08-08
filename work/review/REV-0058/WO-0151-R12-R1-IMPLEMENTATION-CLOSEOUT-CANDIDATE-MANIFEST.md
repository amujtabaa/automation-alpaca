# WO-0151 R12-R1 implementation closeout candidate manifest

Status: **exact implementation plus reconciliation candidate -- focused final recheck pending**

Review base: `f25505cb59afde42e312a3933b85e44e6ad44c41`

This closeout candidate retains the independently accepted R12-R1 code/test
payload unchanged and adds only directly necessary current-posture
reconciliation. It preserves WO-0151 in `REVIEW`, retains WO-0152's FR-08
pause, and does not claim E3 confirmation, external CI, or paired coverage
success.

## Authority and retained evidence

| Record | SHA-256 / exact evidence |
|---|---|
| R12-R1 contract | `9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25` |
| R12-R1 semantic acceptance | `5dfec4ce0425642148561801d69a035f0fb4ddc540fb7baf93d23747dddb581b` |
| R12-R1 activation R2 acceptance | `ef5ba3af97bc76b2e1f77fa4bab0fc9d4677f5dfc7f8eb740c2e5c9dad688444` |
| Independent implementation acceptance | `5631400bf4734c3781dc407b32182a497778a9cac8341f27ed170be433bfaa80` |
| Prior implementation candidate | `abe0df5d723df536263e99a72d1b612ffcf39032de71753aaee9a6304e8166f0` |

The prior implementation candidate remains preserved as an untracked raw
artifact. It is not part of this closeout candidate because one Markdown
hard-break caused `git diff --cached --check` to reject its packaging. The
accepted source/test payload has not changed; this manifest is a clean exact
freeze of that payload plus its current-record reconciliation.

## Exact staged payload

| Path | SHA-256 | Purpose |
|---|---|---|
| `app/execution_core/fills.py` | `6d9f5dcf0c9bc6b04304f3eab4f5822560a8f1f0a2afededb3f5530f4e5f6e4c` | private presence-aware radix lookup and correct physical-key insert/replace semantics |
| `app/execution_core/acquisition.py` | `d94db238acaa586fcce0dcb931b12043ab2ec43ebe6b91074510da08bb3473a3` | sealed direct MarketStreamGenerationId-to-generation route ownership |
| `tests/execution_core/test_fill_position.py` | `fd56c921b66c3238393f25e37490bf2e85c09ed4a983a376b3e273a8eb57ef96` | absent versus present-`None` map behavior controls |
| `tests/execution_core/test_acquisition.py` | `799129974b9facecba3fe576fe89c7a56e0ce0b195e8f939397821b14a54bc14` | serial reuse, malformed route, copy, and mutation controls |
| `tests/execution_core/test_protection.py` | `0d7cf12e220f02485e72566d8a5119f50c8b3f66ad60da01956042dddfb43872` | bounded traversal provenance owner correction |
| `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `10efb27da8368d432579ee49f365884c61e6fe59821fce8fb5883565b4362c2c` | R12-R1 accepted/authority-consumed current record; E2 stays REVIEW |
| `work/active/WO-0152-reset-kernel-e3-generation-conformance.md` | `58f942f8ffcb54d9c8b077f39e3d70a088a46ec60f28e37397189d9ec6514e11` | E3 remains ACTIVE/PAUSED pending exact frozen-detector rerun |
| `pkl/project/goals.md` | `9d9afd26de6fd1a45aff49c861b2c0eb8422e0cce6090da46039319baa253454` | current M1 posture reconciliation |
| `pkl/architecture/architecture-map.md` | `7beb4fd9b590c62ac84d34c72f51fed99f5158ddda19b08de610809679b4223b` | root-boundary architecture reconciliation |
| `pkl/log.md` | `eb98a2adb497e797aa710a6787ffd4335e2f0d235a5ed2e4a1e629729770dea5` | append-only acceptance event |
| `work/ledger.jsonl` | `d6d2528414df1acf469861eed7485a0a5828332873abcb9f9f2fdb91c6b88706` | append-only `REVIEW` disposition |
| `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` | `31de8ff32b76eaf7ebc42742e3d43c20cbbf3c04bf3deb43c03dbda767458def` | provenance-only reconciliation |

## Recheck obligations

1. Rehash all twelve paths, recheck the staged diff, and confirm no code/test
   payload differs from the independently accepted implementation candidate.
2. Confirm the seven record updates are append-only or minimal current-posture
   corrections and do not claim WO-0151 closure, E3 execution, external CI, or
   paired 93% success.
3. Confirm the frozen E3 detector and evidence remain exact and excluded:
   `tests/execution_core/test_acquisition_stateful.py` at
   `1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`,
   and `work/review/REV-0059/evidence.md` at
   `d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`.
4. Require `git diff --cached --check`, work-order scope, disposition, ledger,
   and PKL checks to pass without an exception.

No database/SQL/DDL, runtime/persistence, broker/network, credentials, E3 test
execution, external CI, M2, merge, deletion, cleanup, force-push, or rebase is
part of this closeout candidate.
