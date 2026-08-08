# WO-0152 E3 R2-R3 correction candidate manifest

Status: FROZEN FOR INDEPENDENT PREFLIGHT ONLY  
Date: 2026-08-07  
Branch: codex/arch-reset-2026-07-r1  
Review base HEAD: a2b84abc1914517cf591f27fb88f0b20b2a47ef7  
Work order: WO-0152  
Packet: REV-0059

## Authority and retained evidence

This manifest freezes only R2-R3's coherent static-exception-table correction.
The user authorized direct in-flight issue resolution under all standing
exclusions. That authority permits this documentation/preflight correction, not
test implementation or activation.

The first R2 candidate remains retained unaccepted evidence: it was stopped
before review issued a verdict and `result-r2.md` remains absent. R2-R1 result
`098b2a3791505064406cd1087a654dc89a3a96d9b42906d7ec491cb4bca5bae9`
remains `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0 evidence. R2-R2 also remains
retained unaccepted evidence: it was stopped before verdict and
`result-r2-r2.md` remains absent. The immutable R2-R2 manifest below
transitively pins the complete retained R0 through R2-R2 packet chain.

## Retained chain and R2-R3 inputs

| Path | SHA-256 |
| --- | --- |
| work/review/REV-0059/WO-0152-RED-R2-R1-REMEDIATION-DISPOSITION.md | 3db2520002754ea995d079ead1faf92df0a6e2ab00ff3c6bc3a48d65364403bb |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R1.md | 4dd085ddfd57f05973fde85ef9de6ba9ba936e047b955dc2e93986b9a5b205e9 |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R1-MANIFEST.md | d51393c7862fea52367851d0b1a81e6481a9997aad516508a47a596bc90f649d |
| work/review/REV-0059/request-r2-r1.md | 2f3d1c7a2345754bf375641c460bc4141e74a3fd61c048f2ecd686be8a1b679f |
| work/review/REV-0059/result-r2-r1.md | 098b2a3791505064406cd1087a654dc89a3a96d9b42906d7ec491cb4bca5bae9 |
| work/review/REV-0059/WO-0152-RED-R2-R2-REMEDIATION-DISPOSITION.md | 2503e21c597f472e0e05c51ed72e856c8d29add4116c6b31786dd4918ea95ce8 |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R2.md | 2e94a9b8c57bb16d6b73c11a88b09d4baeed9bd786f0a245406504ee6c56b230 |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R2-MANIFEST.md | 2e6de7561b21810efada266ce5687fd375edbec431e57d93496609f6d0e089bc |
| work/review/REV-0059/request-r2-r2.md | dd84c8d5a4ee1f92d407b64ed9c843ddab783281dd6e1415191c24c3ec3f1fb9 |
| work/review/REV-0059/WO-0152-RED-R2-R3-REMEDIATION-DISPOSITION.md | 9c2d1b99316ac4d6cbf9e1e4e588570b49e885cc8788c034a3d79a44754b72a2 |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R3.md | 881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936 |
| work/review/REV-0059/request-r2-r3.md | 0b924f38ba2e5f2ad116384e1a8d9b048548b30046cde9c3da50ffaa375ec2d8 |
| work/queue/WO-0152-reset-kernel-e3-generation-conformance.md | fb94b8a3a1f1954d2710f9c989e1d1f7f5b2b943b2f072610d1d749ecd606dce |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | 6b2ea299c81f4856c54e3a05caf765630f0a139b241d2c9fe831a09530f8118c |
| pkl/project/goals.md | 90d0e2f37d35a5e396e5cd384e869f79f16abadabedba1ba2cf1281fa1a66ef4 |
| pkl/architecture/architecture-map.md | 4ec2766b0ea7b3530d6b36a71ab1bc970d790ee85118228f05885c08379f7cc8 |
| pkl/log.md | 1b2f62fa92596850207e708e85b2d1f8e1dfc70ddda4c230bee89062cd09fc77 |
| work/ledger.jsonl | e401f2ace3173c0f79d360258601f65fe48c3589652746b7f1f2cb4d76c617cf |
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
| app/execution_core/fills.py | 50832e3849aa3d3be888dd400a646dca04180dcf885aecabdecac0b3dbab6666 |
| tests/execution_core/test_acquisition.py | 2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb |
| tests/execution_core/test_authority.py | f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791 |
| tests/execution_core/test_venue_recovery.py | 37ed9ecdbe810c6d21780c7a0487505debce54aee9340fb5918f5befeaba3e48 |
| tests/execution_core/test_venue_binding_recovery.py | 9761bfd6e4d140594821a35a24324d79fa301e80c66704ddd99f196c49143bea |
| tests/execution_core/test_import_boundary.py | f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4 |

## Exact preflight state

- The future-only E3 test path `tests/execution_core/test_acquisition_stateful.py` is absent.
- `work/review/REV-0059/result-r2.md`, `result-r2-r2.md`, and reviewer-owned
  `result-r2-r3.md` are absent.
- No production or existing test source is part of this R2-R3 candidate delta.
- No `INV-*` entry is added or amended by this documentation-only candidate.
- The candidate contains no staged paths.
- The review is static only. Tests, database-capable fixtures, SQL/DDL, network, broker,
  credentials, runtime, CI, and coverage commands are prohibited at this gate.
- The reviewer must re-hash every listed input, verify the absent paths, verify the exact
  tracked/untracked delta and `git diff --check`, and write only `result-r2-r3.md`.

## Acceptance rule

An independent `ACCEPT` with P0=0/P1=0 is the sole condition that permits the
already authorized test-only WO-0152 activation and implementation. Any P0/P1
keeps WO-0152 DRAFT and returns only the smallest bounded correction. This
manifest does not satisfy or waive the paired E2/E3 unchanged 93% exact-head
closeout condition.
