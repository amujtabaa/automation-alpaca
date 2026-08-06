# WO-0151 RED pre-flight candidate R4 manifest

Status: **controlling documentation-only R4 freeze; not an activation record**

Base commit: f1a40d69f301ad7f594a61f202d3bd380607b98a  
Branch: codex/arch-reset-2026-07-r1

R4 is an additive amendment to immutable R2 and R3 candidate bodies. The exact
R4 review candidate is the R2 body plus the R3 and R4 amendments below. R0
through R3 are retained negative evidence and grant no implementation or
activation authority.

## Authority bodies verified against work-order pins

| Path | SHA-256 |
|---|---|
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf |
| work/queue/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | ede85d3f40d37c94cdc5af3a973c0cbf37ed0b6aa26e5773113a970dedf041b8 |

## Retained negative results

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0058/result-r0.md | 03c20aff72054fe4ed0f78542f7efd4819fa8da1e078b9c573feebc65487917c | R0 rejected |
| work/review/REV-0058/result-r1.md | f0fbd6c5dd612574935990d23bcd8b08625617f1f46e0530b9a8a55a0ff8e53e | R1 rejected |
| work/review/REV-0058/result-r2.md | 2faaf0f53b8623983e8b58f0248f6cce015f8beee114c0c6821c63cef17381d1 | R2 rejected |
| work/review/REV-0058/result-r3.md | 143fad099ab7ff34343c5c34fbdbe46b1b3565daedc2b344d8a97c8db963c34f | R3 rejected |

## Exact R4 review set

| Path | SHA-256 |
|---|---|
| work/review/REV-0058/WO-0151-RED-CONTRACT-R2.md | 343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R3.md | 8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R4.md | bd1f4cabb9071d45586ddfa908f0f4db0c538869b53ee34e0a5b16ee0fa1ae91 |
| work/review/REV-0058/request-r4.md | f323a82396f934379a34d03b890376b012ef6b2a5be58ce8dd80944cf23d95c5 |

The manifest intentionally excludes itself. Only this exact R2+R3+R4 composite
may receive R4 acceptance. Any change to a listed candidate file requires a
new freeze and focused review.
