# WO-0151 RED pre-flight candidate R12 manifest

Status: **documentation-only R12 freeze; not implementation, ratification, or closeout**

Review base commit: `4e7e5807833acc604cf75231e2719078965e8ba6`  
Branch: `codex/arch-reset-2026-07-r1`

R12 is a bounded response to the public E3 FR-08 disagreement. The listed
application and test files are read-only feasibility context. No R12 source or
test implementation has occurred. The untracked E3 module is frozen negative
evidence only; it is neither a candidate implementation input nor acceptance
evidence. The reviewer must not run it.

## Authority and current posture

| Path | SHA-256 | Role |
|---|---|---|
| AGENTS.md | d68a54d8abd3d3592eb0815838d9456eb8b3a2954f6e5fd7533180a96c62d840 | repository/Fable adapter |
| CLAUDE.md | f4f4586b4fef74a012cba391dc066d1418e1c741881da2a84649ed1d1f024eae | permanent safety core |
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 | accepted serial/provenance architecture |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c | accepted no-stream-reuse authority |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf | accepted market-occurrence overlay |
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 43028d2b609266ff40436c17b6100dd70b985499015f4c7dfc8907053bb3c74d | retained E2 record plus current R12 re-gate |
| work/active/WO-0152-reset-kernel-e3-generation-conformance.md | 6d41d5418a039027219661e45357b5d15b885cf7fad470764a5f39824a347fe8 | active E3 FR-08 pause and dependency |
| pkl/project/goals.md | a4be0c2c4c3c1ff48aebcd899060e2eee42d9438e12b4f7ad0f8168afd3ac58e | current goal posture |
| pkl/architecture/architecture-map.md | f00aa7101d97bcbfda6532f4fc5e2276f2a7b55c12a26de27a2172d1e226547b | current architecture map |
| pkl/log.md | bbb892cef3d0e4d71780bebb6a2c45dee436140cb2e5d5206fabceaa01630faf | append-only chronology |
| work/ledger.jsonl | 3c2579e8290edf33b2bf29b839a287f80f8bb7321748872bcd684aa3899de059 | append-only lifecycle ledger |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | 19453c2f2a207c0e4962be5637f5d257b3ca36b27fb6cb2d71746727cdb59e0c | ratification/provenance index |

## R12 candidate documents

| Path | SHA-256 |
|---|---|
| work/review/REV-0058/WO-0151-R12-NONADJACENT-STREAM-REMEDIATION-DISPOSITION.md | 50a70a3371cb992059266b5700f2f6ddb834804bc4414557c66938fbb925d2c9 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R12.md | 36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e |
| work/review/REV-0058/request-r12.md | 01fc7537bb72f12ac8a2c467d9edba7584ba957647ae99b17a8c987f69c12b23 |

## Retained predecessor and negative evidence

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0058/WO-0151-RED-CONTRACT-R11-R1.md | d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9 | accepted predecessor contract |
| work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-REMEDIATION-01-RECHECK-RESULT.md | 96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd | accepted prior E2 recheck |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R5.md | 79c734b7c0a929d43aeca83ef00e797b7afc8d97754eb30f1c812b1dd5b3221e | accepted E3 detector contract |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R5-MANIFEST.md | 3fbcffbec46dd43248a1a8b569df39880c96e9d539d5a84a07cf58fde19be946 | accepted E3 detector manifest |
| work/review/REV-0059/result-r2-r5.md | f3c86daa71a36108bb2757f853d922e992c7c77eed4d7d7626b5e9091e3d5245 | accepted E3 detector review |
| work/review/REV-0059/evidence.md | d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7 | frozen E3 FR-08 observation |
| tests/execution_core/test_acquisition_stateful.py | 1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22 | untracked frozen detector snapshot; read only after evidence |

## Read-only feasibility context

| Path | SHA-256 |
|---|---|
| app/execution_core/acquisition.py | 3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7 |
| tests/execution_core/test_acquisition.py | 2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb |

## Candidate integrity conditions

- `result-r12.md` is absent before the independent reviewer writes it.
- No tracked application or test source differs from review base
  `4e7e5807833acc604cf75231e2719078965e8ba6`.
- The only non-base source is the listed untracked E3 detector. It is frozen as
  negative evidence and must not be changed, executed, or treated as R12
  implementation during this pre-flight.
- This manifest intentionally excludes itself and the future reviewer result.
  Any change to a listed file requires a replacement manifest and fresh review.
