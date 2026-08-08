# WO-0151 R13-R1 clean semantic pre-flight candidate manifest

Status: **documentation-only clean re-freeze; not implementation, ratification,
activation, or closeout**

Review base commit: `051c758ce8b89985aa13cb1240e2fff64f5efac6`
Branch: `codex/arch-reset-2026-07-r1`

R13-R1 changes neither the R13 contract nor the private completed A-to-B
successor cursor-rollover correction. It replaces only the publication-blocked
manifest step with a clean-stageable freeze. The original R13 semantic and
activation packets remain immutable historical evidence.

## Authority and current posture

| Path | SHA-256 | Role |
|---|---|---|
| AGENTS.md | d68a54d8abd3d3592eb0815838d9456eb8b3a2954f6e5fd7533180a96c62d840 | repository/Fable adapter |
| CLAUDE.md | f4f4586b4fef74a012cba391dc066d1418e1c741881da2a84649ed1d1f024eae | permanent safety core |
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 | accepted serial/provenance architecture |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c | accepted successor protection authority |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf | accepted market-occurrence overlay |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | b3d7c0cd428bc19e2636d9b9ea9b4e04057532e25b1ef8da416a23caa89141fc | original R13 ratification retained; R13-R1 pending |
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 2cc2e9b4c3598bc1fbc145dc556f3b48ee4e1e1625ceb7fa9a0adf061d7bb6d2 | retained E2 record and R13-R1 preflight gate |
| work/active/WO-0152-reset-kernel-e3-generation-conformance.md | 5bf1e26dc3122b499f31a1a6cc4a7a00c96899d38b3b77e0cfd782dc745104cb | active but paused E3 dependency and detector boundary |
| pkl/project/goals.md | 5012799558a909a7abd84c315cc2081c3cbd5d607e70e665c1234c00ed9f85e2 | current goal posture |
| pkl/architecture/architecture-map.md | cb82883ef6b4521b68074f1e11196e4972437f17c8876338982635bdd45cb853 | current architecture posture |
| pkl/log.md | eb99366bffdd87c0b3f2e95ce764562751bd3e09c638daed59e7782159977c71 | append-only chronology |
| work/ledger.jsonl | e639a05788b0e1a9d6633f48aa92a69fceea506de3a074987cdccdddd2ea6924 | append-only lifecycle ledger |

## Unchanged R13 correction and retained original packet

| Path | SHA-256 | Required treatment |
|---|---|---|
| work/review/REV-0060/WO-0151-R13-SUCCESSOR-PROTECTION-CURSOR-REMEDIATION-DISPOSITION.md | 2b26ed8332d0d8523a586b60ae0f0686fd187de745f31097fee0f2bdbbe2aaa0 | retained P0 disposition |
| work/review/REV-0060/WO-0151-RED-CONTRACT-R13.md | 240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90 | unchanged R13 contract and only semantic implementation authority if later activated |
| work/review/REV-0060/WO-0151-RED-CANDIDATE-R13-MANIFEST.md | 923b23945627e87372e0f9d6e28255247cb3cbaaa4637b9a2cdb272425a5ec95 | original accepted semantic manifest; retained format-blocked provenance, not staged |
| work/review/REV-0060/request-r13.md | 9f78588c7fd42f8f301108eec2684f0be817d9f70bfd5b1bbb1c557a03946fe3 | retained original semantic request |
| work/review/REV-0060/result-r13.md | a762764b1e48a663f2873b4dc017c4ee59fb0b67ced94195c12fc6875f46852d | retained original independent ACCEPT, P0=0/P1=0/P2=0 |
| work/review/REV-0060/WO-0151-R13-ACTIVATION-DISPOSITION.md | 1dd33f0ff44c3095724922847a27dcc89e1728ed2693e24914d60854cc3c3690 | retained original activation plan |
| work/review/REV-0060/WO-0151-R13-ACTIVATION-DELTA-MANIFEST.md | cb1b58234630e695be61a9c3418accef51281df55842c1d119d83d9e1e2c7e9d | retained original activation manifest; R13-R1 retention witness, format-blocked and not staged |
| work/review/REV-0060/request-r13-activation.md | 507593cf102e0a8f9a9d39bd748b9e2998c5034145c9cdca686d603b131e954d | retained original activation request |
| work/review/REV-0060/result-r13-activation.md | 0368f0190ab0df17200d72966f90c68ddb03a6a78c88743b91ff3a6a11b7c743 | retained original activation ACCEPT, P0=0/P1=0/P2=0 |

## R13-R1 clean re-freeze documents

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0060/WO-0151-R13-FORMAT-REMEDIATION-DISPOSITION.md | 229f6a1c43e413e13c37e1e2e96bcf2a8a035276a78e4e582b3b3a88b9ad237a | retained-format diagnosis and R13-R1 scope |
| work/review/REV-0060/request-r13-r1.md | b61742ad665f5c962f637b0ca4ca2e40c3cb61cb71b921e2d07aeb7bf514994e | independent clean-manifest review request |

## Retained predecessor and frozen E3 evidence

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0058/WO-0151-RED-CONTRACT-R12-R1.md | 9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25 | retained direct-map ownership contract |
| work/review/REV-0058/result-r12-r1-implementation.md | 5631400bf4734c3781dc407b32182a497778a9cac8341f27ed170be433bfaa80 | retained E2 implementation acceptance |
| work/review/REV-0058/result-r12-r1-implementation-closeout-recheck.md | dafe37f12b58899d4d0ae58fc534f28f99aed71937684608bcfabee1b8c085d7 | retained records/evidence recheck |
| work/review/REV-0059/WO-0152-FR-08-B-FIRST-FILL-DETECTOR-FREEZE.md | d83257b7de12dfa440fae5adc3005cf41165b86b83a2c6f7c96295f8712cc9fb | immutable R13 trigger record |
| tests/execution_core/test_acquisition_stateful.py | c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186 | unstaged frozen E3 detector; negative evidence only |

## Unchanged source and test context

| Path | SHA-256 | Treatment |
|---|---|---|
| app/execution_core/venue.py | 0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f | proposed private R13 owner path; no change yet |
| app/execution_core/authority.py | eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19 | proposed atomic-composition path; no change yet |
| app/execution_core/acquisition.py | d94db238acaa586fcce0dcb931b12043ab2ec43ebe6b91074510da08bb3473a3 | proposed receipt-validation path; no change yet |
| app/execution_core/protection.py | 1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e | strict projector context; not an R13 production path |
| tests/execution_core/test_acquisition.py | 799129974b9facecba3fe576fe89c7a56e0ce0b195e8f939397821b14a54bc14 | proposed integration RED controls; no change yet |
| tests/execution_core/test_authority.py | f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791 | proposed authority/receipt controls; no change yet |
| tests/execution_core/test_venue_recovery.py | 37ed9ecdbe810c6d21780c7a0487505debce54aee9340fb5918f5befeaba3e48 | proposed private-proof controls; no change yet |
| tests/execution_core/test_protection.py | 0d7cf12e220f02485e72566d8a5119f50c8b3f66ad60da01956042dddfb43872 | retained strict ordinary-projector control only |
| tests/execution_core/test_import_boundary.py | f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4 | proposed exact static-boundary control; no change yet |

## Format equivalence and integrity conditions

- The unchanged R13 contract, source/test rows, ADR rows, R12-R1 evidence,
  frozen E3 detector/evidence, and safety exclusions are identical in meaning
  to the original R13 semantic packet.
- The original semantic manifest has exactly one retained trailing Markdown
  hard-break at its review-base line; the original activation manifest has
  exactly one at its review-base line. Those two bytes make their staged
  `git diff --check` gate fail. Neither original artifact is normalized,
  staged, or used as a clean publication candidate.
- This R13-R1 manifest has no trailing whitespace. An untracked-safe
  whitespace check is mandatory because ordinary/cached Git diff checks omit
  untracked candidate files. It is an independent, clean-stageable candidate,
  not an amended copy of either retained manifest.
- `result-r13-r1.md` is absent before the independent reviewer writes it. No
  path is staged. The frozen E3 detector is the only permitted tracked
  application/test delta and is excluded from this semantic review.
- Existing untracked `REV-0058` R12-R1 raw manifests remain outside this
  candidate, unchanged and not relied upon. The original R13 packet remains
  untracked retained evidence and is not part of a staging set.
- This manifest intentionally excludes itself and the future reviewer result.
  Any change to a listed file requires a replacement manifest and fresh
  independent review.
- A semantic ACCEPT here is not ratification, source/test authority,
  activation, E3 resumption, coverage evidence, CI success, or M1 closeout.
  A fresh exact R13-R1 user ratification and a separate clean R13-R1
  records-only activation sequence still precede implementation.
