# WO-0151 R13-R1 clean records-only activation-delta manifest

Status: **documentation-only candidate; source/test authority not yet granted**

Review base commit: `051c758ce8b89985aa13cb1240e2fff64f5efac6`
Branch: `codex/arch-reset-2026-07-r1`

This manifest freezes the current records after exact R13-R1 semantic
ratification. It contains no R13 implementation, E3 detector change, coverage
claim, CI-success claim, or closeout. It intentionally excludes itself and the
future independent result.

## Repository and architecture authority

| Path | SHA-256 | Role |
|---|---|---|
| AGENTS.md | d68a54d8abd3d3592eb0815838d9456eb8b3a2954f6e5fd7533180a96c62d840 | repository/Fable adapter |
| CLAUDE.md | f4f4586b4fef74a012cba391dc066d1418e1c741881da2a84649ed1d1f024eae | permanent safety core |
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 | accepted serial/provenance architecture |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c | accepted successor-protection architecture |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf | accepted market-occurrence overlay |

## Exact current records

| Path | SHA-256 | Required current meaning |
|---|---|---|
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | a4053b7a57aa3cc1f882e293aea26918046d6978a685a4bf14d4d7062959d66a | R13-R1 semantic ratified; activation pending |
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | a380efabc20dc3ff1a88742254d09ef92f51fd71f3ecd16c9136a1f393fc1271 | effective REVIEW; R13 implementation ungranted |
| work/active/WO-0152-reset-kernel-e3-generation-conformance.md | 3363fe2b625b8a898bc4a902eca2a87eb1555596f4627a878389d472d4c51af8 | ACTIVE/PAUSED; clean activation paths allowed |
| pkl/project/goals.md | ed31c41636b95c071cf8fd30d1d2ad6b0c82124192fe7ed4b54a2ae18a0e63e7 | current goal posture |
| pkl/architecture/architecture-map.md | 90e07a0380f686b4d6b8f8ab876ac50389bf7c8c215c477bf5fd7769089df17e | current architecture posture |
| pkl/log.md | adf94b78e09091af70ab147307d51a375260db3a528db8f01024859d49265c99 | append-only chronology |
| work/ledger.jsonl | 224ebc89c77363976cdfd17cc0f06cdec8ac30f72615566c938faccc1130a34b | append-only lifecycle ledger |

## Exact ratified semantic packet

| Path | SHA-256 | Treatment |
|---|---|---|
| work/review/REV-0060/WO-0151-R13-SUCCESSOR-PROTECTION-CURSOR-REMEDIATION-DISPOSITION.md | 2b26ed8332d0d8523a586b60ae0f0686fd187de745f31097fee0f2bdbbe2aaa0 | clean semantic disposition; publication path |
| work/review/REV-0060/WO-0151-RED-CONTRACT-R13.md | 240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90 | unchanged ratified R13 contract; publication path |
| work/review/REV-0060/request-r13.md | 9f78588c7fd42f8f301108eec2684f0be817d9f70bfd5b1bbb1c557a03946fe3 | clean original semantic request; publication path |
| work/review/REV-0060/result-r13.md | a762764b1e48a663f2873b4dc017c4ee59fb0b67ced94195c12fc6875f46852d | clean original semantic ACCEPT; publication path |
| work/review/REV-0060/WO-0151-R13-FORMAT-REMEDIATION-DISPOSITION.md | 229f6a1c43e413e13c37e1e2e96bcf2a8a035276a78e4e582b3b3a88b9ad237a | clean R13-R1 format disposition; publication path |
| work/review/REV-0060/WO-0151-RED-CANDIDATE-R13-R1-MANIFEST.md | c05cddbc4d6d7d7cede2b893d6a3b287791eb25adc3015f7181fda5629fc9222 | clean ratified semantic manifest; publication path |
| work/review/REV-0060/request-r13-r1.md | b61742ad665f5c962f637b0ca4ca2e40c3cb61cb71b921e2d07aeb7bf514994e | clean R13-R1 semantic request; publication path |
| work/review/REV-0060/result-r13-r1.md | 71b7ff74f62bdc64f7f25cff5f8b047a30d82ebad961c0e2cdeb48f16638d1a5 | independent clean semantic ACCEPT; publication path |

## Clean activation candidate

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0060/WO-0151-R13-R1-ACTIVATION-DISPOSITION.md | 0919fafbdd3d4f62605bcd56fe63d82d869277b9fd64552eed9e24f22a447af3 | two-commit records-only activation boundary |
| work/review/REV-0060/request-r13-r1-activation.md | 8a86bcfc05e29a896f85c984a2748ba7a39c0f72f9eddd80209055b084652c60 | independent activation review request |

## Format-blocked retained evidence

| Path | SHA-256 | Required treatment |
|---|---|---|
| work/review/REV-0060/WO-0151-RED-CANDIDATE-R13-MANIFEST.md | 923b23945627e87372e0f9d6e28255247cb3cbaaa4637b9a2cdb272425a5ec95 | original semantic manifest; byte-stable, untracked, never staged |
| work/review/REV-0060/WO-0151-R13-ACTIVATION-DELTA-MANIFEST.md | cb1b58234630e695be61a9c3418accef51281df55842c1d119d83d9e1e2c7e9d | original activation manifest; byte-stable, untracked, never staged |

The original activation disposition, request, and result remain untracked with
that format-blocked packet. They are historical evidence, not publication
inputs for this clean sequence.

## Frozen source, test, and downstream evidence

| Path | SHA-256 | Required treatment |
|---|---|---|
| app/execution_core/venue.py | 0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f | unchanged proposed R13 owner path |
| app/execution_core/authority.py | eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19 | unchanged proposed R13 composition path |
| app/execution_core/acquisition.py | d94db238acaa586fcce0dcb931b12043ab2ec43ebe6b91074510da08bb3473a3 | unchanged proposed R13 receipt-validation path |
| tests/execution_core/test_acquisition.py | 799129974b9facecba3fe576fe89c7a56e0ce0b195e8f939397821b14a54bc14 | unchanged proposed R13 RED path |
| tests/execution_core/test_import_boundary.py | f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4 | unchanged proposed R13 boundary-control path |
| work/review/REV-0059/WO-0152-FR-08-B-FIRST-FILL-DETECTOR-FREEZE.md | d83257b7de12dfa440fae5adc3005cf41165b86b83a2c6f7c96295f8712cc9fb | immutable downstream freeze record |
| tests/execution_core/test_acquisition_stateful.py | c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186 | frozen unstaged detector; excluded from publication |

## Publication and review conditions

- `result-r13-r1-activation.md` is absent before the independent reviewer
  writes it. The Git index is empty.
- This manifest intentionally excludes its own hash and the future reviewer
  result. Any listed-file change requires a replacement manifest and a fresh
  independent review.
- The first publication set is exactly the seven current records, the eight
  clean semantic packet paths, this manifest, its disposition/request, and the
  future accepted result. It contains zero `app/`, `tests/`, `.github/`, or
  ADR-body paths.
- The two original format-blocked manifests and the original activation packet
  remain untracked and excluded. The frozen E3 detector and the four retained
  untracked REV-0058 manifests remain unchanged and excluded.
- Ordinary and cached Git diff checks are necessary but cannot inspect
  untracked candidates. Every clean untracked publication path must also pass
  a direct trailing-whitespace scan before staging.
- `ACCEPT` authorizes only the documentation publication and exact-SHA
  reconciliation sequence. It does not itself grant R13 implementation, E3
  resumption, coverage/CI success, WO-0151 closure, M1 completion, or any
  operational authority.
