# WO-0151 RED pre-flight candidate R9 manifest

Status: **documentation-only R9 freeze; not an activation record**

Review base commit: a95af72ee8d7a41f8e0b7859f5124c8a9e929548
Branch: codex/arch-reset-2026-07-r1

R9 is an additive amendment to the immutable R2, R3, R4, R5, R6, R7, and R8
candidate bodies. The exact R9 review candidate is the R2 body plus the R3
through R9 amendments. The documented application/test working tree is
read-only feasibility context, not implementation acceptance. This manifest
grants no implementation, activation, or runtime authority.

## Authority bodies verified against the active-work-order pins

| Path | SHA-256 |
|---|---|
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf |
| work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 1b54a86a96e3f3259fbfc5c0c6b8cad16af100b929c4466a92dd633e9546dcd3 |

## Retained controlling R8 evidence

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0058/WO-0151-RED-CANDIDATE-R8-MANIFEST.md | b6faddc624a227382f80ebefe57044ce2e2e372328df3528e027fc4bcd924311 | pins R2-R8 and retained R0-R7 evidence |
| work/review/REV-0058/result-r8.md | 5dc43bcaab99af837ee89e83880a1484cb79f649ea67e7218e5a2dd798699e80 | accepted R8 pre-flight result |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R8.md | d6a0295f14652222d9fa05e1f826e77ecd306c07dbf1b8faf4525976396eec1f | ratified controlling R8 amendment |

## Exact R9 review set

| Path | SHA-256 |
|---|---|
| work/review/REV-0058/WO-0151-RED-CONTRACT-R2.md | 343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R3.md | 8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R4.md | bd1f4cabb9071d45586ddfa908f0f4db0c538869b53ee34e0a5b16ee0fa1ae91 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R5.md | a83bf31578e66b92fdb0e0f27987b9070a127037be2f50490347464a07fffbad |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R6.md | 58839fb965e3bd962ed5ffa0914eed6957a8e7097e35f9ccc8d64c2889a6ff64 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R7.md | c82ab206d154cdcccf06794e139966724f7a814d4d2201a4fdf27bf3d7cbcb1e |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R8.md | d6a0295f14652222d9fa05e1f826e77ecd306c07dbf1b8faf4525976396eec1f |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R9.md | 168ebd0478faa6abb326f56859ff5efb64b3b66517ff72eade1f51b99f3a5479 |
| work/review/REV-0058/request-r9.md | 7767be192f2effd4a60540dab3e884583d7442763abf38c761e087e33853a69f |

## Read-only feasibility context

| Path | SHA-256 |
|---|---|
| app/execution_core/acquisition.py | c757447df8f81545fd2d5a0769d5ce1ad3fa003b567a65f72b006b88eb617f42 |
| app/execution_core/protection.py | 54c72282d6b40ed13b5a20f2edfc2144a5d43057783cfe145401ae3419265f39 |
| app/execution_core/authority.py | c79a89c0a6943a30c1fb492d3dddb2489d70d9bcf926cc4b7b19caa6eeda2c3e |
| tests/execution_core/test_acquisition.py | cf77a7767ff39bad7b3f7f6c1f934356511e40f64ad2c3297ac53cac7f5665f9 |
| tests/execution_core/test_protection.py | 28c5af8cd7ed9e64b474fb809e9b9a567e6c623e5098a509de056de559591c1b |
| tests/execution_core/test_import_boundary.py | 236976dae16ce009f826dd558285e192f27fee30eca1259a17319b2fc7e57c82 |

The manifest intentionally excludes itself and the future review result. Any
change to a listed candidate file requires a new exact freeze and focused
review.
