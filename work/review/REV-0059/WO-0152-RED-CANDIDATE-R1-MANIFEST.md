# WO-0152 R1 RED candidate manifest

Status: FROZEN FOR INDEPENDENT PREFLIGHT ONLY  
Date: 2026-08-07  
Branch: codex/arch-reset-2026-07-r1  
Review base HEAD: a2b84abc1914517cf591f27fb88f0b20b2a47ef7  
Work order: WO-0152  
Packet: REV-0059

## Authority and retained evidence

This manifest freezes the R1 candidate only. It does not activate WO-0152 or
authorize creation/execution of tests. The R0 candidate remains retained
negative evidence:

| Artifact | SHA-256 |
| --- | --- |
| R0 contract | ce27017d419b2b537d88b618dfc0bdecdc1b01a0a7df3db5f0b5c69b6adf9ce4 |
| R0 manifest | ba9428c2db4bbb9fc0327f9fae9b3de51c16b1fe93c0d98ea4c59bc008116cfe |
| R0 request | 1a31a21820e9152f4da7bd494607ae4711e75d8c164ad48c956a6039a7e4ee5e |
| R0 independent result | ae398751c5c64478748c4fd15a9a9a4124858c449a604d9052b2034f1e592b57 |

R1 exists only because R0 established two deliberately deferred external setup
sources. The exact user authorization allows the one lexical private mandate
minter call site and the one prechecked temporary private parent-closure route
specified by R1; no other private or production capability is in scope.

## Frozen R1 candidate inputs

| Path | SHA-256 |
| --- | --- |
| work/review/REV-0059/WO-0152-RED-R1-PREFLIGHT-REMEDIATION-DISPOSITION.md | 3b99a1f5dc177003279b9c32690bfdc50213a01d03da80fd05e12a1e2f5b3fa5 |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R1.md | 3b2ba052df61f8e128f82b4ee408568774ff8cdd62a815e4387a821ab6f9709b |
| work/review/REV-0059/request-r1.md | a830a1aa75a790c4d54db008c483abe72c363fb3a9f2a16579ae1209b69a1098 |
| work/queue/WO-0152-reset-kernel-e3-generation-conformance.md | 0fbdcf87f5f5e71df8a14f5e780f17b5fba3ddcf4b09c00c51808d773e955d86 |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | 7971d8c5f0aaf8319ea136fbfde9837a042baf2d16864de7a33776effdeaa479 |
| pkl/project/goals.md | 59d12b27a2c3ca925081d9c93ae717c8081424caf1ccac28b7122bd5aea3d697 |
| pkl/architecture/architecture-map.md | 45533a6f9fcb648c8f81eabd8a3e80ceb970a8c045c1e0f3779cd765d3593db3 |
| pkl/log.md | ee99cbae21effacdc362fac1a4536eb2dfd9e9f1ef1fee736cfbfbbd23fb782e |
| work/ledger.jsonl | 2d0c6729aed98c11b5dd44e8aec90540406d44c64f20a563396e90b3f89b83f4 |
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 91cd99008ff8cbc4a8fc75aec9bdf8f387207eed7ce5adc5020941bf690b8a31 |
| work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-CLOSEOUT.md | 34d6b1f73a65f3dd3255aa7686d983c12e11fc00c8d043938144d68f80b2e021 |
| work/review/REV-0058/WO-0151-EXACT-HEAD-COVERAGE-ATTEMPT-02-DISPOSITION.md | 995e96bfaa37981307523290d03d354b659dad1a39f8d07cce2aa306f6473bef |
| work/review/REV-0058/WO-0151-EXACT-HEAD-RUN-741-OUTCOME.md | a3723a46c008652323bfc010c6cd46c58d173d9c5f38cc03bbbf0c4086a06866 |
| work/review/REV-0058/WO-0151-WO-0152-COVERAGE-GATE-ORDER-AMENDMENT.md | aac38ba784ccb21337bbdacd85310c5ba80a76a82e06cf19cbc72d6b97ade84c |

## Frozen governing and implementation context

| Path | SHA-256 |
| --- | --- |
| AGENTS.md | d68a54d8abd3d3592eb0815838d9456eb8b3a2954f6e5fd7533180a96c62d840 |
| CLAUDE.md | f4f4586b4fef74a012cba391dc066d1418e1c741881da2a84649ed1d1f024eae |
| .ai-os/core/15_CROSS_MODEL_REVIEW.md | fe5b6901aff422c4ae6170b06a09a91e9e5937295cec9e406b9832a84d09aeb3 |
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf |
| app/execution_core/acquisition.py | 3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7 |
| app/execution_core/authority.py | eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19 |
| app/execution_core/venue.py | 0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f |
| app/execution_core/protection.py | 1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e |
| app/execution_core/position.py | b59971afddcc52c725a8ed5de3ab84c5e49ab58b8621250e39fcd169e8a2e767 |
| app/execution_core/__init__.py | 63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85 |
| tests/execution_core/test_acquisition.py | 2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb |
| tests/execution_core/test_authority.py | f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791 |
| tests/execution_core/test_venue_recovery.py | 37ed9ecdbe810c6d21780c7a0487505debce54aee9340fb5918f5befeaba3e48 |
| tests/execution_core/test_venue_binding_recovery.py | 9761bfd6e4d140594821a35a24324d79fa301e80c66704ddd99f196c49143bea |
| tests/execution_core/test_import_boundary.py | f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4 |

## Exact preflight state

- The future only E3 test path,
  tests/execution_core/test_acquisition_stateful.py, is absent.
- The reviewer-owned R1 result,
  work/review/REV-0059/result-r1.md, is absent.
- No production or existing test source is part of the candidate delta.
- The only proposed test implementation path is the future E3 module.
- The candidate contains no staged paths.
- The R1 review is static only. Tests, database-capable fixtures, SQL/DDL,
  network, broker, credentials, runtime, CI, and coverage commands are
  prohibited at this gate.
- The reviewer must re-hash every listed input, verify the absent paths, verify
  the exact tracked/untracked delta and diff check, then write only result-r1.md.

## Acceptance rule

An independent ACCEPT with P0=0/P1=0 is the sole condition that permits the
already-authorized test-only WO-0152 implementation to be activated. Any P0/P1
keeps WO-0152 DRAFT and returns only the smallest bounded correction. This
manifest does not satisfy the paired E2/E3 93% closeout condition.

