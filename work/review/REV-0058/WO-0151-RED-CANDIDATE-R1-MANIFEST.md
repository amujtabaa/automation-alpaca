# WO-0151 RED pre-flight candidate R1 manifest

Status: **documentation-only candidate; not an activation record**

Base commit: `f1a40d69f301ad7f594a61f202d3bd380607b98a`  
Branch: `codex/arch-reset-2026-07-r1`

## Authority bodies verified against work-order pins

| Path | SHA-256 |
|---|---|
| `docs/adr/ADR-020-current-state-execution-kernel.md` | `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653` |
| `docs/adr/ADR-021-position-protection-liquidity-execution.md` | `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c` |
| `docs/adr/ADR-023-bounded-market-occurrence-authority.md` | `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf` |
| `work/queue/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `ede85d3f40d37c94cdc5af3a973c0cbf37ed0b6aa26e5773113a970dedf041b8` |

## Retained R0 result

| Path | SHA-256 | Role |
|---|---|---|
| `work/review/REV-0058/result-r0.md` | `03c20aff72054fe4ed0f78542f7efd4819fa8da1e078b9c573feebc65487917c` | retained negative evidence; R0 is not accepted |

## R1 candidate path set

| Path | SHA-256 |
|---|---|
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R1.md` | `55a68f393f00b9cd00ef6fe70d07b20a3cdcd8a442f5e3aa58aeb76e95c187e0` |
| `work/review/REV-0058/request-r1.md` | `f58554ea03a82c65535229c2ecb8b21391404ab4bf42db906faf16d9e7d9d864` |

The manifest intentionally excludes itself from the candidate path hash list.
No application, test, lifecycle, ledger, PKL, ADR, or Git state is part of
this pre-flight freeze. A changed R1 body requires a replacement manifest and
another focused review; the retained R0 records must not be altered.
