# REV-0118 R6 — correction-only fresh-file result

Status: **FAILED; quarantined; no retry**

- Source: `a18924131e0e2534bbdf51fb9374dbdd5bac4c9f`, tree
  `c9ee080be59a4847e82258c615289da456c2f195`
- Flag-only proof branch: `codex/m2-wo0170-rev0118-correction-sqlite-r1`
- Unlock commit: `1793ec6296dc90a196f21e70449661bfbf93b880`, tree
  `8068f4f5f327f8e621b5ccc9fdee2071b0baf0e1`
- Result: six passed, one failed
- Passed: all fault-matrix claim, claim-erasure, acceptance/closure-gap, cursor-regression,
  and startup commit-fault cases
- Failed: target/stress boundedness setup before its first timed selection sample

The boundedness builder correctly created and committed a real runtime checkpoint for the new
hydration measurement. Its older selection-only probe still used the pre-checkpoint request whose
`expected_checkpoint` is `None`. The repository therefore correctly returned `CONFLICT` after the
checkpoint existed. No application or DDL defect was observed.

Canonical root correction `106fa7c4be39adc974af038264ed74d4349f19c7`, tree
`782fcbe39ec2df524bce1012b2d818979c670bd8`, returns the exact repository-issued resulting
checkpoint from setup and binds every selector sample to that head. The quarantined R6 branch and
its generated files are not predecessors.

The DDL remained 190,705 UTF-8 bytes at SHA-256
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; no migration,
configured/in-memory database, runtime, credential, broker/network activity, order, promotion, or
M3 implementation occurred.

