# WO-0152 coverage-ratchet candidate R1 manifest

Frozen: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

Base HEAD: `ae626f56fb05c09b312a7383326ebbf9ba584cd3`

## Exact replacement candidate

| SHA-256 | Path |
| --- | --- |
| `ca9ae7f4338827884fe128408c2d98567c48f1779a652157852ca5e92624f5da` | `.ai-os/scripts/check_coverage_ratchet.py` |
| `153a2e032e5107a811476e41497c16127e685db8880be6df1c63706423f434dd` | `tests/test_coverage_ratchet.py` |
| `79f826b9a209d587460d7eb5dfe80ef76691cf255f7a2032d4406289616564c5` | `.github/workflows/ci.yml` |
| `16649fac7dd39c5258eddcc9c2f0a7d80c3903c31f8ea2b21bcdf355a71a1c95` | `pyproject.toml` |
| `c046519bf15e87fb2b63f438d2dc9c65baffe51c4625255fe0297cfbdc231360` | `tests/execution_core/test_acquisition_stateful.py` |
| `0c0e5fa571b2eb61b301d6db0d670826bc9ed3559f366d19631164a3d20eaa2f` | `work/active/WO-0152-reset-kernel-e3-generation-conformance.md` |
| `e423ce0a2a8034fbe1ee51b2694dae544916dd64ceb73773f0886dc7fdc5596c` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-SEMANTICS-AMENDMENT.md` |
| `734f66b34de4a78d9c2f3b8e15e5dae0d11c794d4c76b7acfe6e2426d592a35b` | `work/review/REV-0061/WO-0152-COVERAGE-RATCHET-REMEDIATION-01-DISPOSITION.md` |
| `ceca70bbf572701b81d200e739d354766291fae2499e32b925b4452d9070bbe7` | `work/review/REV-0061/request-r1.md` |
| `6d33708046fc7e3ec726b725817b1db9db3e8461f306bf51a1fae5ff29f111dc` | `work/review/REV-0061/result.md` |

The reviewer-owned `work/review/REV-0061/result-r1.md` is absent from the table
and must be the focused recheck seat's only write.

## Retained predecessor and evidence

The original manifest, request, and result remain immutable. The retained
coverage JSON remains unstaged at SHA-256
`3c3c009a35304ae7a6a6893a3b931762eb333c019d9c4ea45db6fdaa1a342eed`
and is arithmetic evidence only. All temp trees, earlier coverage JSON, and
historical REV-0058/REV-0060 raw artifacts remain excluded and unchanged.

## R1 delta

Relative to the first candidate, only `tests/test_coverage_ratchet.py`,
`pyproject.toml`, the active work order, and the new remediation/recheck packet
changed. The validator, workflow, E3 behavior proof, and amendment did not.

Any byte change to a listed file invalidates this manifest. Acceptance requires
P0=0 and P1=0. The independent seat may not edit the candidate, commit, push,
perform runtime/database/broker/network work, implement M2, merge, create a PR,
delete, clean up, force-push, or rebase.
