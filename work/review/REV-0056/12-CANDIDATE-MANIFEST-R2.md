# REV-0056 candidate manifest R2

Status: **FROZEN CANDIDATE INDEX — DRAFT ONLY — NOT RATIFIED**

This is the final exact preflight candidate. It supersedes the unreviewed R1 manifest
11-CANDIDATE-MANIFEST-R1.md (SHA-256
d6f6b2561220f3749a3d5204eed1870a7bbfa78f3a611e270556476b9e91a3da) because R2 makes the
bounded-state rule explicit: the SymbolAcquisitionController contains no retired-generation
collection; retired lineage exists only in separate direct-indexed GenerationRegistry records.
The prior manifests remain retained evidence and must not be used for review.

Candidate scope: the nine numbered architecture documents 00 through 08 in this directory. The
ratification-request draft, any independent-review request/result, and manifests are supporting
packet artifacts and are not part of the architecture candidate body set.

| File | SHA-256 |
|---|---|
| 00-RECOVERY-AND-FABLE-GATE.md | f14d873fbc0bb121d695bebdff0f305eaff70e0ae13ab6de69983b19267a0a29 |
| 01-OPTION-MATRIX-AND-DECISION.md | e90705b6f087719d11c2cd6f25eade96473c5196949e3ef487066d590f05b4a8 |
| 02-COMPLEXITY-LEDGER.md | a7283bc4e3a9d9e0008b57560a28625c6403a6ab8fdbd96e37e5fd632d7afb02 |
| 03-PROPOSED-ADR-020-R2.md | f6cf6f7996d1a778ea687f9f58402ab37ec0cf50ff0837bc3746e751ddac2ae3 |
| 04-PROPOSED-ADR-021-R2.md | 5964344609d429de60c0e75ec28e2e403f78709579c8773a10b609ae63265b99 |
| 05-SUPERSESSION-AND-RECONCILIATION-MAP.md | 5e2517926ea9e85388b387f83774fcf0929a5dd0086d40b7f5313880e4b7ae94 |
| 06-PROPOSED-M1-SPLIT-AND-M2-M8-IMPLICATIONS.md | f18c37ee35977fbcb10ee6041a096cc6f9edb521aee3e88d5352c4d6fff51a1a |
| 07-DRAFT-DOWNSTREAM-RECONCILIATION.md | 862e72ad5bb6cd67b2afd4bc332020c9708b2038d73780ba5395d6ec2cdd8414 |
| 08-CRITICAL-STATIC-PREFLIGHT-PLAN.md | aec444dc7c552b5525387094bb1b3ddc8a8a7940636ad82b66bcc79f0b5552aa |

Freeze rule: an independent reviewer must review these exact bytes. A candidate document change
invalidates this R2 manifest and requires a successor manifest and focused re-preflight. A
preflight acceptance does not ratify the candidate or authorize implementation.

