# WO-0151 RED pre-flight candidate R2 manifest

Status: **controlling documentation-only R2 freeze; not an activation record**

Base commit: `f1a40d69f301ad7f594a61f202d3bd380607b98a`  
Branch: `codex/arch-reset-2026-07-r1`

R2 replaces R1 for review. R0/R1 bodies, manifests, and result records remain
retained because neither candidate was accepted. R2 incorporates their
root-level findings before implementation, tests, activation, or lifecycle
changes.

## Authority bodies verified against work-order pins

| Path | SHA-256 |
|---|---|
| `docs/adr/ADR-020-current-state-execution-kernel.md` | `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653` |
| `docs/adr/ADR-021-position-protection-liquidity-execution.md` | `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c` |
| `docs/adr/ADR-023-bounded-market-occurrence-authority.md` | `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf` |
| `work/queue/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `ede85d3f40d37c94cdc5af3a973c0cbf37ed0b6aa26e5773113a970dedf041b8` |

## Retained negative results

| Path | SHA-256 | Role |
|---|---|---|
| `work/review/REV-0058/result-r0.md` | `03c20aff72054fe4ed0f78542f7efd4819fa8da1e078b9c573feebc65487917c` | R0 rejected |
| `work/review/REV-0058/result-r1.md` | `f0fbd6c5dd612574935990d23bcd8b08625617f1f46e0530b9a8a55a0ff8e53e` | R1 rejected |

## Exact R2 review set

| Path | SHA-256 |
|---|---|
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R2.md` | `343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5` |
| `work/review/REV-0058/request-r2.md` | `c7bfb56e1657c45331b8704c77c76cdb4893791a8225fd51420b89d394e9e8eb` |

The manifest intentionally excludes itself. This is the only WO-0151 RED
candidate that may be accepted. Any change to its listed files requires a new
freeze and focused re-review.
