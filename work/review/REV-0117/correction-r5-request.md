# REV-0117 R5 finite correction verification — WO-0169 venue recovery

Date: 2026-08-29

Status: **CORRECTION-ONLY REVIEW REQUIRED**

## Exact binding

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Authorized remediation base: `5bd3473f5d4f34316935369acb5d38e31f1bcee1`.
- Original R4 implementation candidate: `636c2329ad5a0f90cc316782bee9542016e53e16`.
- R4 request-only commit: `ba21782b016a36704011439866b06f4829b221ef`.
- Exact R5 correction candidate: `fe59068d9129d417d0d9c85e4a9b53e0bd97d995`.
- Candidate tree: `a92dc7fb91ceb349323eee92a9e677fc03769279`.
- Correction delta: `ba21782b016a36704011439866b06f4829b221ef..fe59068d9129d417d0d9c85e4a9b53e0bd97d995`.
- Effective implementation range: `5bd3473f5d4f34316935369acb5d38e31f1bcee1..fe59068d9129d417d0d9c85e4a9b53e0bd97d995`.
- `unit_of_work.py` SHA-256:
  `03788a738d7a80964a87bc8a93a574264676a407d7ed1df7e00d7b243a60f315`.
- Pure UOW test SHA-256:
  `4e16a2e697cb25535d561f993481d36515b1ab930c78213cb48441b3ec715329`.
- Active work-order SHA-256:
  `594652b3b2aba72022e85ff581873fd5c2a1e41a5d0477a1acfc5a1d216b63e5`.
- Preserved R4 result SHA-256:
  `ecdc2b6fa5c7813b1ef6833c281b9c9de2092a192dfb27c4efe00cecfa8bf77f`.

The request file itself is a later documentation-only commit and is outside the reviewed
candidate tree.

## Accepted R4 finding and bounded correction

R4 returned one P1: the two original controls could pass if checkpoint projection regressed to
`prepared.selection_proof`. The correction replaces the completion stub with the real
`_complete_claimed_input` / `_store_successor_checkpoint` path, supplies authentic distinct
predecessor and post-write proofs, and makes both projection and storage assert identity with the
fresh proof. The separate no-delta control also reissues a distinct fresh proof and remains
failure-capable if an unchanged payload reaches storage.

The stronger integrated control exposed the earlier refusal in the same authentic held scenario:
the dormant acquisition owner has no market cursor before protection is active, but venue recovery
required one before it could persist `DISPATCH_CLAIMED -> ACKNOWLEDGED`. The correction permits an
absent cursor only on the venue route while `protection is None`; every other caller retains the
default exact-one requirement. The active-owner negative mutation removes its cursor and must
still receive `acquisition market cursor is not singular`.

## Evidence available to reproduce

No SQLite-bearing or held test is authorized. The three direct controls pass. The same
source-confirmed pure six-file command passes all 550 tests. Ruff check/format, mypy over all 99
application files, install/version/ledger/PKL, work-order scope, and correction-range whitespace
checks on authored implementation/governance content pass. The preserved reviewer result retains
its original Markdown hard-break spaces unchanged.

Protected identities are unchanged from R4:

- `SCHEMA_DDL`: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- Held-test blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

## Finite review request

Verify only:

1. the accepted R4 stale-proof mutation gap is closed by distinct proof-sensitive controls;
2. the newly exposed missing-cursor correction is limited to dormant venue recovery and retains
   exact-one cursor enforcement for active protection and all unchanged callers;
3. neither correction weakens transaction atomicity, checkpoint no-op refusal, or fail-closed
   behavior; and
4. scope and protected identities did not drift.

Do not reopen unrelated accepted WO-0169 design. Run only the three direct controls or the recorded
six-file pure slice if useful. Do not import or execute SQLite, create a database, or run the held
test. Return findings only, with exact P0/P1/P2 counts and `BLOCK`, `ACCEPT-WITH-CHANGES`, or
`ACCEPT`. The reviewer-owned result path is `work/review/REV-0117/result-r5.md`.
