# WO-0151 R13-R1 records-only activation R1 candidate manifest

Status: **focused P1 remediation candidate; implementation not authorized**

Review base commit: `051c758ce8b89985aa13cb1240e2fff64f5efac6`
Branch: `codex/arch-reset-2026-07-r1`

R1 changes only the activation scope wording rejected by the first clean
records-only review. The ratified R13 semantics, source/test bytes, frozen E3
detector, and operational exclusions remain unchanged. This manifest excludes
itself and the future R1 reviewer result.

## Current records

| Path | SHA-256 | Current meaning |
|---|---|---|
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | 3f290b47bfc2a828ad334a4ca7e35b2e34093b80f7b77fcf05320298d2d70866 | R13-R1 ratified; activation R1 pending |
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 6fd540520eb809672aabf2379a4e8afb2e7d0ede43e0af78230f4dfb5225ac07 | effective REVIEW; source/test ungranted |
| work/active/WO-0152-reset-kernel-e3-generation-conformance.md | 381f1784525da72608737007a8c51352254a8ad87c07570a59d36a86a20e83ec | ACTIVE/PAUSED; R1 paths allowed |
| pkl/project/goals.md | d9f5c7d69864ffc8cb01c51ca9071e021eeb6e585230d5d26985cd802db08512 | current goal posture |
| pkl/architecture/architecture-map.md | 03be9fc9714d7ccc3d9ac4953705d03f1717bd9f3279f7bd6b2d0b46ea424dbd | exact five-path architecture posture |
| pkl/log.md | 9a3ad801a393def4f736931801c55415ab6e671c85d8907cd446d90020cba828 | append-only chronology |
| work/ledger.jsonl | 303dfd7910084353e8be9313b6f7c3f580e83e0bb4029f7e7f5792bcead02b07 | append-only activation P1/remediation record |

## Unchanged ratified semantic packet

| Path | SHA-256 | Treatment |
|---|---|---|
| work/review/REV-0060/WO-0151-R13-SUCCESSOR-PROTECTION-CURSOR-REMEDIATION-DISPOSITION.md | 2b26ed8332d0d8523a586b60ae0f0686fd187de745f31097fee0f2bdbbe2aaa0 | publication path |
| work/review/REV-0060/WO-0151-RED-CONTRACT-R13.md | 240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90 | unchanged ratified contract; publication path |
| work/review/REV-0060/request-r13.md | 9f78588c7fd42f8f301108eec2684f0be817d9f70bfd5b1bbb1c557a03946fe3 | publication path |
| work/review/REV-0060/result-r13.md | a762764b1e48a663f2873b4dc017c4ee59fb0b67ced94195c12fc6875f46852d | original semantic ACCEPT; publication path |
| work/review/REV-0060/WO-0151-R13-FORMAT-REMEDIATION-DISPOSITION.md | 229f6a1c43e413e13c37e1e2e96bcf2a8a035276a78e4e582b3b3a88b9ad237a | publication path |
| work/review/REV-0060/WO-0151-RED-CANDIDATE-R13-R1-MANIFEST.md | c05cddbc4d6d7d7cede2b893d6a3b287791eb25adc3015f7181fda5629fc9222 | clean ratified semantic manifest; publication path |
| work/review/REV-0060/request-r13-r1.md | b61742ad665f5c962f637b0ca4ca2e40c3cb61cb71b921e2d07aeb7bf514994e | publication path |
| work/review/REV-0060/result-r13-r1.md | 71b7ff74f62bdc64f7f25cff5f8b047a30d82ebad961c0e2cdeb48f16638d1a5 | independent clean semantic ACCEPT; publication path |

## Retained first clean activation candidate and finding

| Path | SHA-256 | Treatment |
|---|---|---|
| work/review/REV-0060/WO-0151-R13-R1-ACTIVATION-DISPOSITION.md | 0919fafbdd3d4f62605bcd56fe63d82d869277b9fd64552eed9e24f22a447af3 | retained unaccepted candidate; publication provenance |
| work/review/REV-0060/WO-0151-R13-R1-ACTIVATION-DELTA-MANIFEST.md | fef6a29391550f46163112af36b130023b5973dd11492cef311c447c98920910 | retained unaccepted manifest; publication provenance |
| work/review/REV-0060/request-r13-r1-activation.md | 8a86bcfc05e29a896f85c984a2748ba7a39c0f72f9eddd80209055b084652c60 | retained first review request; publication provenance |
| work/review/REV-0060/result-r13-r1-activation.md | 72fce061222edf684cdd2684aeebbf740c1432fbefc4df10dc6b3eb1354b2d89 | retained ACCEPT-WITH-CHANGES P1; publication provenance |

## Focused R1 replacement

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0060/WO-0151-R13-R1-ACTIVATION-R1-DISPOSITION.md | 324d6ee68dca884a33ad998ce2cf3af1f4bd37866a5ccfddbcac32fce8b446fd | exact-five-path replacement boundary |
| work/review/REV-0060/request-r13-r1-activation-r1.md | 4c95673b7c3ed21464a3730ea4ec785a3ae582e7c59c65bfc0018ad1e41e1fd7 | focused independent recheck request |

## Frozen implementation and downstream evidence

| Path | SHA-256 | Required treatment |
|---|---|---|
| app/execution_core/venue.py | 0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f | exact R13 edit path; unchanged before activation |
| app/execution_core/authority.py | eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19 | exact R13 edit path; unchanged before activation |
| app/execution_core/acquisition.py | d94db238acaa586fcce0dcb931b12043ab2ec43ebe6b91074510da08bb3473a3 | exact R13 edit path; unchanged before activation |
| tests/execution_core/test_acquisition.py | 799129974b9facecba3fe576fe89c7a56e0ce0b195e8f939397821b14a54bc14 | exact R13 edit path; unchanged before activation |
| tests/execution_core/test_import_boundary.py | f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4 | exact R13 edit path; unchanged before activation |
| tests/execution_core/test_authority.py | f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791 | execution-only regression evidence; no edit authority |
| tests/execution_core/test_venue_recovery.py | 37ed9ecdbe810c6d21780c7a0487505debce54aee9340fb5918f5befeaba3e48 | execution-only regression evidence; no edit authority |
| tests/execution_core/test_protection.py | 0d7cf12e220f02485e72566d8a5119f50c8b3f66ad60da01956042dddfb43872 | execution-only regression evidence; no edit authority |
| work/review/REV-0059/WO-0152-FR-08-B-FIRST-FILL-DETECTOR-FREEZE.md | d83257b7de12dfa440fae5adc3005cf41165b86b83a2c6f7c96295f8712cc9fb | immutable downstream freeze record |
| tests/execution_core/test_acquisition_stateful.py | c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186 | frozen detector; unchanged, unstaged, excluded |

## Format-blocked retained evidence

| Path | SHA-256 | Required treatment |
|---|---|---|
| work/review/REV-0060/WO-0151-RED-CANDIDATE-R13-MANIFEST.md | 923b23945627e87372e0f9d6e28255247cb3cbaaa4637b9a2cdb272425a5ec95 | original semantic manifest; byte-stable, untracked, never staged |
| work/review/REV-0060/WO-0151-R13-ACTIVATION-DELTA-MANIFEST.md | cb1b58234630e695be61a9c3418accef51281df55842c1d119d83d9e1e2c7e9d | original activation manifest; byte-stable, untracked, never staged |

## Acceptance and publication conditions

- `result-r13-r1-activation-r1.md` is absent before independent review. The
  index is empty.
- Only the five exact source/test paths in this manifest may be edited after
  successful two-step activation. The three named regression suites are
  execution-only. Every other source/test path requires a replacement exact
  freeze and independent review before editing.
- The first publication set contains exactly 23 paths after the future result
  exists: seven current records, eight semantic paths, four retained first
  activation paths, and the R1 disposition/manifest/request/result. It contains
  zero `app/`, `tests/`, `.github/`, or ADR-body paths.
- The second commit changes only the seven current records to reconcile the
  first publication SHA and activate the exact five paths. It contains no
  source/test implementation.
- The two original format-blocked manifests, their original activation packet,
  the frozen detector, and four retained untracked REV-0058 manifests remain
  excluded and unchanged.
- Every clean untracked publication path must pass a direct trailing-whitespace
  scan before staging; ordinary/cached Git checks alone are insufficient.
- R1 `ACCEPT` authorizes only the two records-only commits. It does not by
  itself authorize source/test edits before exact-SHA reconciliation, E3
  resumption, coverage/CI success, WO-0151 closure, M1 completion, or any
  operational authority.
