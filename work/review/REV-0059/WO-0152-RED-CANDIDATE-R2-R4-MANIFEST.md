# WO-0152 E3 R2-R4 mandate-schedule candidate manifest

Status: FROZEN FOR INDEPENDENT PREFLIGHT ONLY  
Date: 2026-08-07  
Branch: codex/arch-reset-2026-07-r1  
Review base HEAD: e35ff07c42675646cc7a13f1949f80fdf108e516  
Work order: WO-0152  
Packet: REV-0059

## Authority and replacement boundary

This manifest freezes only R2-R4's fixed 32-mandate schedule correction for
the active WO-0152 test-only E3 work order. The user explicitly authorized
this re-gate and in-flight root correction under every standing safety
exclusion. R2-R4 replaces only the nonconstructible approved-mandate fixture
rule: a fixed A/B/C-only configuration and one private mint call with no
authorized repetition cannot produce distinct sealed bindings or the required
valid 32-generation trace.

The accepted R2-R3 composite remains retained historical authority for every
other fixture, boundedness tripwire, provenance, and safety restriction. This
manifest grants no production/API/runtime/database/broker/credential/network
or operational capability. It is static-only; no E3 source expansion is
authorized by this candidate.

## Retained R2-R3 chain

| Path | SHA-256 |
| --- | --- |
| work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R3-MANIFEST.md | ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6 |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R3.md | 881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936 |
| work/review/REV-0059/result-r2-r3.md | 8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59 |
| work/review/REV-0059/activation-disposition.md | 2ef88891b3e303833d93d36cd50a99132b24e6b8b994c822fcfa65b8ebf976b3 |

The R2-R3 manifest transitively freezes the retained R0 through R2-R2 chain.
Those artifacts, including absent `result-r2.md` and `result-r2-r2.md`, remain
unaltered and are not re-adjudicated by this candidate.

## Frozen governing context

| Path | SHA-256 |
| --- | --- |
| AGENTS.md | d68a54d8abd3d3592eb0815838d9456eb8b3a2954f6e5fd7533180a96c62d840 |
| CLAUDE.md | f4f4586b4fef74a012cba391dc066d1418e1c741881da2a84649ed1d1f024eae |
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf |
| app/execution_core/__init__.py | 63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85 |
| app/execution_core/acquisition.py | 3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7 |
| app/execution_core/authority.py | eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19 |
| app/execution_core/protection.py | 1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e |
| app/execution_core/venue.py | 0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f |
| app/execution_core/fills.py | 50832e3849aa3d3be888dd400a646dca04180dcf885aecabdecac0b3dbab6666 |

## Candidate and current-record inputs

| Path | SHA-256 |
| --- | --- |
| work/review/REV-0059/WO-0152-RED-R2-R4-MANDATE-SCHEDULE-REMEDIATION-DISPOSITION.md | 162e4c8e029fd4cffd791a7f4ce7f73f2c459bca6b0a3818f73e84dab1b82a4a |
| work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R4.md | f2a59f1c4197aac851249a136d0a3a1761c7e365f4f34468acb842dc18e5866e |
| work/review/REV-0059/request-r2-r4.md | 638c1c16b14f653be15d07992312b147c8c79a6405ac31e868670cb453643238 |
| work/active/WO-0152-reset-kernel-e3-generation-conformance.md | 82a06446b2d0dfb19efa4c994d0a77fabb78b7e26f8a81a6243158c262ab4a36 |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | 59a0e342f0017e1959c36c3337cf41c0cbc516d35e835c67a9ceefd28562f11b |
| pkl/project/goals.md | 47d5933f0fbc6fd06d847ce475d783d1bce13fa5d856f7b78d2e62d1d4562d9b |
| pkl/architecture/architecture-map.md | f64884754a6063eebbaf51054af576c813c6b512b8e308c33dcfe376ac21b28d |
| pkl/log.md | 90d85d446efbe37ed5070ebdbba32a0e5eed080563c60ba557db1e48865ac280 |
| work/ledger.jsonl | b38d659497e71ee1d5e687f3146ecd9b05ee378ff308faf60d28942c145278f2 |

## Isolated partial-test baseline

`tests/execution_core/test_acquisition_stateful.py` exists as the sole
pre-existing untracked local test draft, SHA-256
`e10e623230744f4a4c43cbc11cc0850562f32e8ee64286efb5ef0ba2ff3d6b79`.
It is not a R2-R4 candidate input or acceptance claim. It must remain
byte-identical through this documentation-only preflight; the reviewer may
inventory it only to confirm isolation and retained R2-R3 scope.

## Exact candidate state

- Tracked modifications are limited to the active WO-0152 current re-gate,
  ratification/provenance, PKL current posture/log, and append-only ledger.
- New candidate artifacts are limited to this manifest, the R2-R4 disposition,
  contract, and request.
- `work/review/REV-0059/result-r2-r4.md` is absent and reserved for the
  independent reviewer.
- No source is staged. `git diff --check` is clean.
- The preflight is static only. Tests, database-capable fixtures, SQL/DDL,
  network, broker, credentials, runtime, CI, and coverage commands are
  prohibited.

## Acceptance rule

Only an independent exact `ACCEPT` with P0=0/P1=0 permits further E3 test
implementation under R2-R4. A P0/P1 preserves the partial baseline unchanged
and returns the smallest root correction. R2-R4 does not waive the paired
E2/E3 unchanged 93% exact-head Python 3.11/3.12 closeout.
