# WO-0151 R11 R1 implementation acceptance result

Review posture: fresh independent, exact-candidate, functional-conformance review.

## Frozen target and authority verification

- Branch: `codex/arch-reset-2026-07-r1`
- Tracked parent / local HEAD: `b6cf1aadfd0aae27ada3262b854c2af30912c0d5`
- Candidate manifest: `WO-0151-R11-R1-IMPLEMENTATION-CANDIDATE-MANIFEST.md`
- Candidate-manifest SHA-256: `9d9a00bc9fa98e65fcd1d891f08ca860175c01b377d35049d0da6fa3b652e955`

The following authority pins were recalculated and matched the manifest exactly:

| Authority | Verified SHA-256 |
| --- | --- |
| `work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `9906f0eab6f2afac232b321ee188ac7f2b38dc6520d3357bf619df9dc8065c63` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md` | `00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R11-R1.md` | `d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9` |
| `work/review/REV-0058/WO-0151-RED-CANDIDATE-R11-R1-MANIFEST.md` | `e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8` |
| `work/review/REV-0058/result-r11-r1.md` | `c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b` |

ADR-020 R2, ADR-021 R2, ADR-023 R1, and the R2 through R10 RED-contract pins were also recalculated and matched their frozen values. The tracked candidate delta contained exactly the 11 manifest paths. Their hashes were rechecked immediately before this result was written:

| Path | Verified SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85` |
| `app/execution_core/acquisition.py` | `22326c338a6c5c0c3c6c3c98c24bcd3b95acb300eb064d168f1f060db3595985` |
| `app/execution_core/authority.py` | `5d9f22a77ba5e8ea38b126b2413f0c6a279c6a0a10e85d27d2358a4d2956d2c0` |
| `app/execution_core/identity.py` | `8f4b8472fe1de766cd3eea38472dae97ce9766ac0d93c79553eccee382f1781a` |
| `app/execution_core/protection.py` | `cfdee0230980728f31feb746ccc578b63596b47988abc2388b876184fc80c609` |
| `app/execution_core/venue.py` | `0729e4a7d8911dba8713fe3cd18d4467fefd2dc5d43df9b9cc1ebdc5b3c78e3f` |
| `tests/execution_core/test_acquisition.py` | `d158a568aea701ed6a7c2500fdc11f620b4fa6534d86e1dde1fa0011235323b9` |
| `tests/execution_core/test_authority.py` | `f7b51bf4e51adaea4707c1af0bb0008f30fc9aed3d4108e3406b632dc4ece791` |
| `tests/execution_core/test_import_boundary.py` | `f1bc1d82a62663e1ff4d8aebb09856e45db22d68d2fba2b36e6c78b1584511a4` |
| `tests/execution_core/test_protection.py` | `269ebeb2b1a5b87bec2685784843c78aab236179cbeb02a9fa8ccd0f80bbbffd` |
| `tests/execution_core/test_venue_ownership.py` | `63d6f7b04803b7e08c857b1ff9131e5bf8d792a2de2611998ef7d9677a6da754` |

## Fresh evidence

- `python -m pytest -q tests/execution_core -p no:cacheprovider`: **1,344 passed**.
- `python -m ruff check app/execution_core tests/execution_core`: passed.
- `python -m ruff format --check app/execution_core tests/execution_core`: 25 files already formatted.
- `python -m mypy app`: passed with no issues in 87 source files.
- `git diff --check HEAD --`: passed.
- Ledger, PKL, and work-order-disposition checks: passed.
- Exact tracked-path comparison against the manifest: passed.

No R2 or full-repository fixture was run in this review. No database-capable, broker, network, credential, runtime, or persistence path was invoked. The earlier environment-affected R2 setup failure recorded by the manifest was not used as evidence.

## Required disproof pass

1. **Serial admission — not disproved.** `begin_acquisition_generation` revalidates authentic current state, the exact live predecessor, flat/terminal conditions, current refresh, scoped bootstrap/admission, changed mandates/stream generation, equal recovery compatibility, and the ordinal bound before replacing one LIVE registry entry with its successor (`app/execution_core/acquisition.py:3842-4078`). A-to-B-to-C, compatibility refusal, and terminal-successor controls are present at `tests/execution_core/test_acquisition.py:1276`, `:1363`, and `:2958`.
2. **Canonical-fact totality — acceptance control disproved.** The reducer is fact-family-generic and applies through one authority transition, but the frozen tests do not cover the full ratified current/retired FILL/CORRECT/BUST matrix or its named mutation obligations. See P1 below.
3. **Retired-fact race — not disproved in inspected implementation.** Direct retired-generation routing, one currentness advance, bounded preemption, and stale-claim behavior are exercised at `tests/execution_core/test_acquisition.py:2983` and `:3068`; final claim performs fresh source revalidation in `claim_acquisition_effect` (`app/execution_core/acquisition.py:4874`).
4. **Protection rebase separation — not disproved.** Raw neutral reprojection and semantic rebase use distinct exact source types and validation routes, and neutral transport returns without an authority mutation (`app/execution_core/acquisition.py:4548-4752`). The owner-minted transport control is at `tests/execution_core/test_acquisition.py:1112` and the semantic-head control at `:646`.
5. **Cross-side intent separation — not disproved.** Protection owns distinct sealed preemption-only and goal-bearing exit intents (`app/execution_core/protection.py:1613-1838`). Current BUY cancellation and protective SELL are exercised independently at `tests/execution_core/test_acquisition.py:3203` and `:3259`, with producer separation at `tests/execution_core/test_protection.py:6752`.
6. **Structural boundary — not disproved.** The candidate is pure execution-core code/tests, the import-boundary suite passed, and the exact tracked delta has no runtime, persistence, SQL/DDL, broker/network, or UI path.
7. **Failure capability — disproved for the uncovered matrix and named mutations.** The complete pure suite is green, but the retained candidate does not demonstrate every R11/R11-R1 mutation would turn the corresponding control RED. See P1.

## Finding

### [P1] The ratified applied-fact matrix and named failure controls are incomplete

**Location:**

- `work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md:289-296`
- `work/review/REV-0058/WO-0151-RED-CONTRACT-R11-R1.md:186-205`
- `tests/execution_core/test_acquisition.py:2155-2663`
- `tests/execution_core/test_acquisition.py:2983-3068`

**Why it matters:** R11 requires current first/follow-on and retired FILL/CORRECT/BUST facts, with and without source reconciliation and with normal/abnormal protection outcomes, to prove one direct state/head update; it also requires independent mutations of the owner/currentness/cursor/terminal/intent/head/final-claim fences to turn the controls RED. The frozen E2 acquisition tests cover current FILL, current BUST, one non-tail BUST reconciliation case, retired FILL, and a retired-FILL preemption race. They contain no `BrokerTradeCorrectFact` route and no retired CORRECT/BUST route through the composite acquisition controller. The candidate also retains no executed named-mutation evidence for all of the specified fences. Protection-layer correction tests do not exercise the E2 controller/currentness/registry/lineage composition required here.

The implementation inspected is generic across the canonical fact family, so this is not a claim that a known production defect was reproduced. It is a failure-capable acceptance gap at a capital-sensitive exact-once boundary: a future or present route-specific error in correction/bust economics, retired-generation lineage, source reconciliation, or duplicate head registration could survive the frozen controls.

**What resolves it:** add focused E2 acquisition controls for current follow-on and retired `TRADE_CORRECT`/`TRADE_BUST` routes across ordinary and source-reconciliation dispositions and normal/conservative protection outcomes. Each must assert one registry-economics update, one controller/currentness/lineage head advance, replay inertness, and no ordinary BUY/SELL authority. Add and run the R11/R11-R1 named mutations for owner/currentness/cursor/terminal/intent/head/final-claim fences, then freeze and independently recheck only the corrected exact candidate.

## Unverified subsequent gates

- Repository-configured 93% full-repository branch-coverage gate.
- Unchanged exact-head GitHub Actions Python 3.11 and 3.12 jobs.
- Closeout WO/PKL/ledger/provenance/evidence reconciliation.

These were outside this pure-review boundary and cannot satisfy or erase the P1 above.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: **0**
- P1: **1**
- P2: **0**

WO-0151 is not accepted or closed by this result. The next review should be a focused exact-delta recheck of the resolved P1, not a new open-ended architecture review.
