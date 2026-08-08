# WO-0152 RED candidate manifest

Status: FROZEN FOR INDEPENDENT PREFLIGHT  
Date: 2026-08-07  
Branch: codex/arch-reset-2026-07-r1  
Local HEAD and frozen code base: a2b84abc1914517cf591f27fb88f0b20b2a47ef7

## Exact purpose

This manifest freezes the documentation-only coverage-order amendment and
WO-0152 test-only RED contract. It is not an activation, implementation, or
acceptance claim.

The reviewer must reject any candidate whose listed hash differs, whose
tracked delta is not the exact eight documentation files below, whose
non-self untracked packet files differ from the listed five records, or which
contains a new E3 test/production file.

## Authority and retained evidence pins

| Item | Exact SHA-256 or identifier | Required meaning |
| --- | --- | --- |
| ADR-020 R2 | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 | Accepted serial-generation kernel authority |
| ADR-021 R2 | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c | Accepted serial acquisition/protection authority |
| ADR-023 R1 | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf | Controlling occurrence overlay |
| WO-0151 R11 | 00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d | Ratified R11 contract |
| WO-0151 R11 R1 | d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9 | Ratified constructibility correction |
| WO-0151 final exact-head coverage recheck | 52bb41f18fdb0b2ce6694b6436db685cbae31cba42a1460472917da3746cba52 | Accepted focused remedy result |
| Exact E2 code predecessor | a2b84abc1914517cf591f27fb88f0b20b2a47ef7 | Current branch HEAD/base |
| GitHub Actions negative coverage evidence | #741 / ID 31185454392 | 5,934 tests pass per 3.11/3.12 job; 91.34% fails unchanged 93% gate |

## Candidate file hashes

### Tracked documentation delta — exactly eight paths

| SHA-256 | Path |
| --- | --- |
| aa6791b9dfed5b81bb43e5ce638082050d8e47dbfee6bb5b04378a11ea9ce69d | docs/adr/ARCH-RESET-2026-07-RATIFICATION.md |
| 2a875fdbca5a9d1bea71063e441f0de407a832b7e0b83c48f679e2e2fe7ffabc | pkl/architecture/architecture-map.md |
| 1b13345ad45254d8727879e0ec838b8bd1a1fc08ae269337076a8a8fe615b87a | pkl/log.md |
| 7b09db8460d981a8f16740e9b27c6979060c2e0572a26a80792438cdb48e1385 | pkl/project/goals.md |
| 91cd99008ff8cbc4a8fc75aec9bdf8f387207eed7ce5adc5020941bf690b8a31 | work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md |
| 26d47ea99de070e4263182542e4b50ca0bb031f29b307ff2ac8ecffccb528ac4 | work/ledger.jsonl |
| 1cb895f31bc6240293e20a887d1622ed3a965e1390b1c7b2a8a9f37e3dff212d | work/queue/WO-0152-reset-kernel-e3-generation-conformance.md |
| 34d6b1f73a65f3dd3255aa7686d983c12e11fc00c8d043938144d68f80b2e021 | work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-CLOSEOUT.md |

### Non-self untracked candidate evidence/packet — exactly five paths before reviewer output

| SHA-256 | Path |
| --- | --- |
| 995e96bfaa37981307523290d03d354b659dad1a39f8d07cce2aa306f6473bef | work/review/REV-0058/WO-0151-EXACT-HEAD-COVERAGE-ATTEMPT-02-DISPOSITION.md |
| a3723a46c008652323bfc010c6cd46c58d173d9c5f38cc03bbbf0c4086a06866 | work/review/REV-0058/WO-0151-EXACT-HEAD-RUN-741-OUTCOME.md |
| aac38ba784ccb21337bbdacd85310c5ba80a76a82e06cf19cbc72d6b97ade84c | work/review/REV-0058/WO-0151-WO-0152-COVERAGE-GATE-ORDER-AMENDMENT.md |
| ce27017d419b2b537d88b618dfc0bdecdc1b01a0a7df3db5f0b5c69b6adf9ce4 | work/review/REV-0059/WO-0152-RED-CONTRACT.md |
| 1a31a21820e9152f4da7bd494607ae4711e75d8c164ad48c956a6039a7e4ee5e | work/review/REV-0059/request.md |

This manifest itself is the sixth untracked candidate file. No result.md
exists before independent review. The reviewer may create only
work/review/REV-0059/result.md.

## Frozen code and test context

These source files are not modified by this candidate. Their hashes freeze the
public contract context for constructibility review:

| SHA-256 | Path |
| --- | --- |
| 63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85 | app/execution_core/__init__.py |
| 3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7 | app/execution_core/acquisition.py |
| eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19 | app/execution_core/authority.py |
| 1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e | app/execution_core/protection.py |
| 0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f | app/execution_core/venue.py |
| b59971afddcc52c725a8ed5de3ab84c5e49ab58b8621250e39fcd169e8a2e767 | app/execution_core/position.py |
| 2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb | tests/execution_core/test_acquisition.py |
| eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 | docs/adr/ADR-020-current-state-execution-kernel.md |
| b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c | docs/adr/ADR-021-position-protection-liquidity-execution.md |
| 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf | docs/adr/ADR-023-bounded-market-occurrence-authority.md |

The authorized exact removal is already reconciled: the pre-removal
tests/execution_core/test_acquisition.py hash was
eb5b3bcf004939f9d934e26f9aa45cf3c6f40e18f42427c6332324465c3a7eb8;
the restored, unmodified file hash is the value above. No new
tests/execution_core/test_acquisition_stateful.py exists at this freeze.

## Static freeze checks

- git diff --check: PASS.
- Current HEAD equals the stated base: PASS.
- Tracked code/test delta: none.
- Tracked candidate delta: exactly the eight documentation paths above.
- No database, SQL/DDL, network, broker, credential, runtime, CI, or test
  execution was performed for this manifest.
