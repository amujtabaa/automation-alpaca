# REV-0056 candidate manifest R3

Status: **FROZEN CANDIDATE INDEX — DRAFT ONLY — NOT RATIFIED**

This is the exact final preflight candidate. It supersedes unreviewed R2 manifest
12-CANDIDATE-MANIFEST-R2.md (SHA-256
d321e42d7f4c01fa1fbbe25fbf6501a70d427ef6342fd34fc6aa777c4b526587) because R3 explicitly
pins EmergencyRecoveryCompatibility at controller genesis for the controller lifetime. A successor
therefore proves equality inductively with every retired generation and cannot silently replace
A's emergency authority. Prior manifests remain retained draft evidence and must not be used for
review.

Candidate scope: the nine numbered architecture documents 00 through 08 in this directory. The
ratification-request draft, any independent-review request/result, and manifests are supporting
packet artifacts and are not part of the architecture candidate body set.

| File | SHA-256 |
|---|---|
| 00-RECOVERY-AND-FABLE-GATE.md | f14d873fbc0bb121d695bebdff0f305eaff70e0ae13ab6de69983b19267a0a29 |
| 01-OPTION-MATRIX-AND-DECISION.md | 0f81c784e308f35981d032fbfc8b470e89ffd0d5b3e8cc5c94b4d372cd4c80a3 |
| 02-COMPLEXITY-LEDGER.md | 41cddadf7bf1ee1dc055f1354de8cba4858ad1576d6050bb070633f6b3b31a8f |
| 03-PROPOSED-ADR-020-R2.md | eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653 |
| 04-PROPOSED-ADR-021-R2.md | b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c |
| 05-SUPERSESSION-AND-RECONCILIATION-MAP.md | 0dae3c11ef99809677bf3aefd82faa9aa79d17e3cc35d1e8bc9678ddaf2b26ae |
| 06-PROPOSED-M1-SPLIT-AND-M2-M8-IMPLICATIONS.md | f18c37ee35977fbcb10ee6041a096cc6f9edb521aee3e88d5352c4d6fff51a1a |
| 07-DRAFT-DOWNSTREAM-RECONCILIATION.md | 73e51ada58ec490147099173bf0e25adaa0e483d9ba6156f58b15a14d3702f55 |
| 08-CRITICAL-STATIC-PREFLIGHT-PLAN.md | bf7cdd38d36e45d6ba759ba68480602c680c528d9415344dd2e1480e6c6cfc6e |

Freeze rule: an independent reviewer must review these exact bytes. A candidate document change
invalidates this R3 manifest and requires a successor manifest and focused re-preflight. A
preflight acceptance does not ratify the candidate or authorize implementation.

