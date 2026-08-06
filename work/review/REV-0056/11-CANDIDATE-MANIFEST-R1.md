# REV-0056 candidate manifest R1

Status: **FROZEN CANDIDATE INDEX — DRAFT ONLY — NOT RATIFIED**

This is the corrected exact candidate. It supersedes the initial unreviewed manifest
10-CANDIDATE-MANIFEST.md (SHA-256 af1d3b6789816a3d8679e283091cca6a2251d67fdda51db65a00f436e427c9e3)
because R1 makes the ADR-023 overlay explicit: every successor uses a distinct
MarketStreamGenerationId and fresh normal protection state only after its predecessor state is
non-serving. The initial manifest remains retained evidence and must not be used for review.

Candidate scope: the nine numbered architecture documents 00 through 08 in this directory. The
ratification-request draft, any independent-review request/result, and manifests are supporting
packet artifacts and are not part of the architecture candidate body set.

| File | SHA-256 |
|---|---|
| 00-RECOVERY-AND-FABLE-GATE.md | f14d873fbc0bb121d695bebdff0f305eaff70e0ae13ab6de69983b19267a0a29 |
| 01-OPTION-MATRIX-AND-DECISION.md | a3130896efd3d2b425e079ddeed24435cadf58f1002b07dfcba4737d2ac5259e |
| 02-COMPLEXITY-LEDGER.md | b24d7942aac421b32a20b77310b14dcb131adf6fdd28b506cce22e28cce0953e |
| 03-PROPOSED-ADR-020-R2.md | 3aca7c30ff73dc79c827b3def299d4b99b4a6ac056362154885a7a45381dfa9e |
| 04-PROPOSED-ADR-021-R2.md | 5964344609d429de60c0e75ec28e2e403f78709579c8773a10b609ae63265b99 |
| 05-SUPERSESSION-AND-RECONCILIATION-MAP.md | 5e2517926ea9e85388b387f83774fcf0929a5dd0086d40b7f5313880e4b7ae94 |
| 06-PROPOSED-M1-SPLIT-AND-M2-M8-IMPLICATIONS.md | f18c37ee35977fbcb10ee6041a096cc6f9edb521aee3e88d5352c4d6fff51a1a |
| 07-DRAFT-DOWNSTREAM-RECONCILIATION.md | 862e72ad5bb6cd67b2afd4bc332020c9708b2038d73780ba5395d6ec2cdd8414 |
| 08-CRITICAL-STATIC-PREFLIGHT-PLAN.md | aec444dc7c552b5525387094bb1b3ddc8a8a7940636ad82b66bcc79f0b5552aa |

Freeze rule: an independent reviewer must review these exact bytes. A candidate document change
invalidates this R1 manifest and requires a successor manifest and focused re-preflight. A
preflight acceptance does not ratify the candidate or authorize implementation.

