# WO-0152 E3 R2-R1 activation-gate correction candidate manifest

Status: FROZEN FOR INDEPENDENT PREFLIGHT ONLY  
Date: 2026-08-07  
Branch: codex/arch-reset-2026-07-r1  
Review base HEAD: a2b84abc1914517cf591f27fb88f0b20b2a47ef7  
Work order: WO-0152  
Packet: REV-0059

## Authority and retained evidence

This manifest freezes only R2-R1's stale activation-gate correction. The user
authorized Codex to address issues arising in flight under all standing
exclusions. That authority permits this documentation/preflight correction,
not test implementation or activation.

The R0/R1/R1 remediation 01 packet chain remains retained evidence. The first
R2 candidate is also retained unaccepted evidence: it was stopped before its
independent review issued a verdict, because its frozen work order still named
the superseded R1 future activation condition. The legacy R2 manifest is pinned
as its own immutable record, not reinterpreted as a current source manifest.

| Path | SHA-256 |
| --- | --- |
| work/review/REV-0059/WO-0152-RED-CONTRACT.md | ce27017d419b2b537d88b618dfc0bdecdc1b01a0a7df3db5f0b5c69b6adf9ce4 |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-MANIFEST.md | ba9428c2db4bbb9fc0327f9fae9b3de51c16b1fe93c0d98ea4c59bc008116cfe |
| work/review/REV-0059/request.md | 1a31a21820e9152f4da7bd494607ae4711e75d8c164ad48c956a6039a7e4ee5e |
| work/review/REV-0059/result.md | ae398751c5c64478748c4fd15a9a9a4124858c449a604d9052b2034f1e592b57 |
| work/review/REV-0059/WO-0152-RED-R1-PREFLIGHT-REMEDIATION-DISPOSITION.md | 3b99a1f5dc177003279b9c32690bfdc50213a01d03da80fd05e12a1e2f5b3fa5 |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R1.md | 3b2ba052df61f8e128f82b4ee408568774ff8cdd62a815e4387a821ab6f9709b |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-R1-MANIFEST.md | 86ba85d531186567d289f761fca7ba1f5e658768ff1818ea4d978329b9e48888 |
| work/review/REV-0059/request-r1.md | a830a1aa75a790c4d54db008c483abe72c363fb3a9f2a16579ae1209b69a1098 |
| work/review/REV-0059/result-r1.md | 880a4f2f8874d9e14a77523301a400ef84d02893d421e48822dfb648aa249408 |
| work/review/REV-0059/WO-0152-RED-R1-REMEDIATION-01-DISPOSITION.md | 13464dcd872b25223146e8f3e810a822a087c2eda6ed28184c8a1fb3702c2c5a |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R1-R1.md | c6caaa8bdfacc0ef9e4bbb414961cd1045ec3e693bb06ed72cff2947c431382c |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-R1-R1-MANIFEST.md | 4b3ae783f380260042b289060d95acc4d1c3c8611dd9553a29385f42881ec3c0 |
| work/review/REV-0059/request-r1-r1.md | 7e6020165ea72bee414b3d017ba0358cd2bd056d02fa6b3f6215d2f58e56cbfd |
| work/review/REV-0059/result-r1-r1.md | 8654e55a40dc6215c1f860ff87f9751e1d6d1c0e03f374c3a4a8e544f769945f |
| work/review/REV-0059/WO-0152-RED-R2-SIBLING-HISTORY-REMEDIATION-DISPOSITION.md | b34fb933538ccb4e6ef6a0f2e14ff6f1299da3819ada1ded52b5c64540ef36b4 |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2.md | 99e70f48f3ebeb823ef4c9ad344bb4b48ccab831501cec5a20dbcdcbec7c3b9f |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-MANIFEST.md | 5bf3c529e703a8fef4e243750697a1669afda3801f8cc6d7bfc726ecab9596ba |
| work/review/REV-0059/request-r2.md | e8e9ccf55d2756bf2cb39912b8ae6590434a0fc5432ed961e6283a8b734f03bc |

## Frozen R2-R1 candidate inputs

| Path | SHA-256 |
| --- | --- |
| work/review/REV-0059/WO-0152-RED-R2-R1-REMEDIATION-DISPOSITION.md | 3db2520002754ea995d079ead1faf92df0a6e2ab00ff3c6bc3a48d65364403bb |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R1.md | 4dd085ddfd57f05973fde85ef9de6ba9ba936e047b955dc2e93986b9a5b205e9 |
| work/review/REV-0059/request-r2-r1.md | 2f3d1c7a2345754bf375641c460bc4141e74a3fd61c048f2ecd686be8a1b679f |
| work/queue/WO-0152-reset-kernel-e3-generation-conformance.md | ed0b862b29867bd4e68e74259990ec4e4abf6036b0689776aabc152cf3ade151 |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | a65120ecbfd9048e338c08d5ef163f64d418e0a3c1e88db25f91e4182e5a4e56 |
| pkl/project/goals.md | 505fe72d1d6def3561097a06bfa8764a40200674c1db9165de8a4d3883c7f265 |
| pkl/architecture/architecture-map.md | 4a7159dfdddb55adf7b989cc980a10c32638164bfe868320c5bcf3cbf084a234 |
| pkl/log.md | e3bf468d9b84ad52046d4a250c2acb1ede6eea52de5fdf5da6cde0e64d4f85d4 |
| work/ledger.jsonl | c84eede7a54e927116b2e476062fe87ce8e0146537a010a8b8aed7ee7fcc6c86 |
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 91cd99008ff8cbc4a8fc75aec9bdf8f387207eed7ce5adc5020941bf690b8a31 |
| work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-CLOSEOUT.md | 34d6b1f73a65f3dd3255aa7686d983c12e11fc00c8d043938144d68f80b2e021 |
| work/review/REV-0058/WO-0151-EXACT-HEAD-COVERAGE-ATTEMPT-02-DISPOSITION.md | 995e96bfaa37981307523290d03d354b659dad1a39f8d07cce2aa306f6473bef |
| work/review/REV-0058/WO-0151-EXACT-HEAD-RUN-741-OUTCOME.md | a3723a46c008652323bfc010c6cd46c58d173d9c5f38cc03bbbf0c4086a06866 |
| work/review/REV-0058/WO-0151-WO-0152-COVERAGE-GATE-ORDER-AMENDMENT.md | aac38ba784ccb21337bbdacd85310c5ba80a76a82e06cf19cbc72d6b97ade84c |

## Frozen governing and source context

| Path | SHA-256 |
| --- | --- |
| AGENTS.md | d68a54d8abd3d3592eb0815838d9456eb8b3a2954f6e5fd7533180a96c62d840 |
| CLAUDE.md | f4f4586b4fef74a012cba391dc066d1418e1c741881da2a84649ed1d1f024eae |
| .ai-os/core/15_CROSS_MODEL_REVIEW.md | fe5b6901aff422c4ae6170b06a09a91e9e5937295cec9e406b9832a84d09aeb3 |
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf |
| app/execution_core/__init__.py | 63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85 |
| app/execution_core/acquisition.py | 3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7 |
| app/execution_core/authority.py | eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19 |
| app/execution_core/venue.py | 0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f |
| app/execution_core/recovery.py | 684003e1ca480e1c6cd7bf2e2e8c864732bb2e0f67809acb3a550a814fddd40c |
| app/execution_core/protection.py | 1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e |
| app/execution_core/position.py | b59971afddcc52c725a8ed5de3ab84c5e49ab58b8621250e39fcd169e8a2e767 |
| tests/execution_core/test_acquisition.py | 2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb |
| tests/execution_core/test_authority.py | f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791 |
| tests/execution_core/test_venue_recovery.py | 37ed9ecdbe810c6d21780c7a0487505debce54aee9340fb5918f5befeaba3e48 |
| tests/execution_core/test_venue_binding_recovery.py | 9761bfd6e4d140594821a35a24324d79fa301e80c66704ddd99f196c49143bea |
| tests/execution_core/test_import_boundary.py | f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4 |

## Exact preflight state

- The future-only E3 test path `tests/execution_core/test_acquisition_stateful.py` is absent.
- Both `work/review/REV-0059/result-r2.md` and reviewer-owned
  `work/review/REV-0059/result-r2-r1.md` are absent.
- No production or existing test source is part of this R2-R1 candidate delta.
- No `INV-*` entry is added or amended by this documentation-only candidate.
- The candidate contains no staged paths.
- The review is static only. Tests, database-capable fixtures, SQL/DDL, network, broker,
  credentials, runtime, CI, and coverage commands are prohibited at this gate.
- The reviewer must re-hash every listed input, verify the absent paths, verify the exact
  tracked/untracked delta and `git diff --check`, and write only `result-r2-r1.md`.

## Acceptance rule

An independent `ACCEPT` with P0=0/P1=0 is the sole condition that permits the
already authorized test-only WO-0152 activation and implementation. Any P0/P1
keeps WO-0152 DRAFT and returns only the smallest bounded correction. This
manifest does not satisfy or waive the paired E2/E3 unchanged 93% exact-head
closeout condition.
