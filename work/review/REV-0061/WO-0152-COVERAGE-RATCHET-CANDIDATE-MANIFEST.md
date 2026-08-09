# WO-0152 coverage-ratchet candidate manifest

Frozen: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

Base HEAD: `ae626f56fb05c09b312a7383326ebbf9ba584cd3`

## Exact candidate files

| SHA-256 | Path |
| --- | --- |
| `ca9ae7f4338827884fe128408c2d98567c48f1779a652157852ca5e92624f5da` | `.ai-os/scripts/check_coverage_ratchet.py` |
| `7988019febd0f21d8d3485775100657ec6a009c54750e279e67562fe1e1a5105` | `tests/test_coverage_ratchet.py` |
| `79f826b9a209d587460d7eb5dfe80ef76691cf255f7a2032d4406289616564c5` | `.github/workflows/ci.yml` |
| `68f75b21e744ed9c06b68822b5cb29238ab5268fa76afd2239a2b81b3517b71e` | `pyproject.toml` |
| `c046519bf15e87fb2b63f438d2dc9c65baffe51c4625255fe0297cfbdc231360` | `tests/execution_core/test_acquisition_stateful.py` |
| `578aaf44b1d7e8150f6f4f17427f29cf8514e354d9046b108d7b7cdb34935826` | `work/active/WO-0152-reset-kernel-e3-generation-conformance.md` |
| `e423ce0a2a8034fbe1ee51b2694dae544916dd64ceb73773f0886dc7fdc5596c` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-SEMANTICS-AMENDMENT.md` |
| `7a6062ce48b8a2d573309521cb9f64810cd7e6646bfb8b5a537266f52b3a64f9` | `work/review/REV-0061/request.md` |

The reviewer-owned `work/review/REV-0061/result.md` is deliberately absent
from this table and must be the review seat's only candidate write.

## Retained local measurement evidence

The complete pre-correction repository coverage JSON is retained unstaged at
`coverage-e3.json`, SHA-256
`3c3c009a35304ae7a6a6893a3b931762eb333c019d9c4ea45db6fdaa1a342eed`,
2,454,729 bytes. It is evidence for the arithmetic only, not a source or
publication candidate. The reviewer may re-derive its totals but must not edit,
stage, delete, or reclassify it as exact-head CI.

All pytest temp trees, earlier coverage JSON files, the frozen historical
REV-0058/REV-0060 raw manifests, and all other retained untracked artifacts are
excluded from this candidate and must remain unchanged.

## Freeze rule

Any byte change to a listed candidate file invalidates this manifest and
requires a replacement manifest and fresh independent review. The candidate is
acceptable only with P0=0 and P1=0. This freeze authorizes no commit, push,
closeout, runtime work, database work, network activity, M2, merge, PR,
deletion, cleanup, force-push, or rebase by the independent seat.
