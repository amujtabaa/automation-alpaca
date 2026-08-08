# WO-0151 RED pre-flight candidate manifest

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

## Candidate path set

| Path | SHA-256 |
|---|---|
| `work/review/REV-0058/WO-0151-RED-CONTRACT.md` | `2ae37d5d5bb90c85ad75a47699bebc45a0209331d4cd514a15add34b57084e84` |
| `work/review/REV-0058/request.md` | `2b4832100a66e9a82e83a2e8428b986519af081cf4696ed2e56fa2afd1d431dc` |

The manifest intentionally excludes itself from the candidate path hash list.
No application, test, lifecycle, ledger, PKL, ADR, or Git state is part of
this pre-flight freeze. A corrected candidate requires a new manifest rather
than overwriting this record.
