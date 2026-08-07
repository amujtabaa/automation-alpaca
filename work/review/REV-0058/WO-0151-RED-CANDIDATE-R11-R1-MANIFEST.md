# WO-0151 RED pre-flight candidate R11 R1 manifest

Status: **documentation-only R11 R1 freeze; not a ratification or implementation record**

Review base commit: 7c96e6b29c39652d66c6cf41d9896974dbec5f53
Branch: codex/arch-reset-2026-07-r1

R11 R1 is the exact purpose-separated-intent correction to the immutable
R2-R11 composite. Current application/test files are read-only feasibility
context, not implementation acceptance. This manifest grants no
implementation, activation, runtime, persistence, database, broker, network,
merge, deletion, or later-work-order authority.

## Authority bodies

| Path | SHA-256 |
|---|---|
| docs/adr/ADR-020-current-state-execution-kernel.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 |
| docs/adr/ADR-021-position-protection-liquidity-execution.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c |
| docs/adr/ADR-023-bounded-market-occurrence-authority.md | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf |
| work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | 6c93048e8e8e52f32fecdd4b88c1969115c5164a8cf89e078f828717bff82d46 |

## Retained evidence

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0058/WO-0151-RED-CANDIDATE-R10-MANIFEST.md | f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b | pins the ratified R2-R10 composite and prior accepted evidence |
| work/review/REV-0058/result-r10.md | dd91f3a1403658cf116767c534ad080daf47acc23458e899c6431db290d6c431 | accepted R10 independent pre-flight result |
| work/review/REV-0058/WO-0151-RED-CANDIDATE-R11-MANIFEST.md | 31c29c6340de064af23bc64e430e46514b771a7e1b27145707e53be5837177cc | initial R11 freeze, retained only |
| work/review/REV-0058/request-r11.md | 9a34f85deab2608a60013d414f98e4ff2135a9e3c3ad4600221b5cbd28b9eee0 | initial R11 request, retained only |
| work/review/REV-0058/result-r11.md | cafe0132e7e549e4c20fc94a677f21ab8febbbdd36e5f10b1d6e76188a47b5c6 | BLOCK P0=0/P1=1/P2=0; retained negative evidence with disclosed search-scope contamination |

## Exact R11 R1 review set

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
| work/review/REV-0058/WO-0151-RED-CONTRACT-R10.md | 081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3 |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R11.md | 00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d |
| work/review/REV-0058/WO-0151-RED-CONTRACT-R11-R1.md | d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9 |
| work/review/REV-0058/request-r11-r1.md | f7639703c5c919c1f6e12d4e33ccb410062d76a8e89ef12a5bb67bb24374e91f |

## Read-only feasibility context

| Path | SHA-256 |
|---|---|
| app/execution_core/__init__.py | fbce9dabfc8fa3ab8b52312b0d825154e1fda335c76e6a04a1a403e3652934d0 |
| app/execution_core/acquisition.py | 55a8f906b27064d55c69ee688d5d8b00ef2cb94a1361d15e5ac8e17454678b9f |
| app/execution_core/authority.py | eb7955aad86491ee76115b140dfb54be5d8c9ab092a041fa0df5f3daf3c5c22b |
| app/execution_core/identity.py | 8f4b8472fe1de766cd3eea38472dae97ce9766ac0d93c79553eccee382f1781a |
| app/execution_core/protection.py | 28ce1652dcdb18b353c6c4a3c0c1c8e6eaa5bba26c6ec2b81b077ccb1e23cdb0 |
| app/execution_core/venue.py | f95ac0aba10facd992ed4066543b35ef9c63ec075ecfd1a76e391feed01aab9e |
| tests/execution_core/test_acquisition.py | 6e80c90530be520977535623ca89fd99eb886c4ec36d604068b18f6c554f0197 |
| tests/execution_core/test_authority.py | cf97137e321bb773dc884f207daf4287eaeb9b5d492786277168ed8d77a3f87a |
| tests/execution_core/test_import_boundary.py | 69677b01b98df3bab6e571c5fa04c4534aee97c1db5914d6c4279d7f3c368b66 |
| tests/execution_core/test_protection.py | f7e6854477ab75b6462ca5be125d8d41703cdaa151ff6cf671d02fc1bbb0bfed |
| tests/execution_core/test_venue_ownership.py | 63d6f7b04803b7e08c857b1ff9131e5bf8d792a2de2611998ef7d9677a6da754 |

The manifest intentionally excludes itself, the future R11 R1 review result,
and `WO-0151-R11-CONSTRUCTIBILITY-NOTES.md`. The notes are author working
material and are excluded to preserve specification-first review. The reviewer
must derive the R11 R1 result before consulting retained `result-r11.md`. Any
change to a listed candidate or feasibility-context file requires a new exact
freeze and focused review.
