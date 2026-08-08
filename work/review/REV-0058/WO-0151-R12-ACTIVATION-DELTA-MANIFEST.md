# WO-0151 R12 activation-delta candidate manifest

Status: **documentation-only activation-delta freeze; not R12 implementation or closeout**

Review base: `4e7e5807833acc604cf75231e2719078965e8ba6`
Branch: `codex/arch-reset-2026-07-r1`

## Immutable semantic predecessor

| Path | SHA-256 | Role |
|---|---|---|
| work/review/REV-0058/WO-0151-RED-CONTRACT-R12.md | 36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e | accepted R12 semantic contract |
| work/review/REV-0058/WO-0151-RED-CANDIDATE-R12-MANIFEST.md | a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0 | immutable semantic freeze |
| work/review/REV-0058/result-r12.md | 0bd78212be49059fcc87ae02e23d08867c99944bf21ca1bf92af596612a99ac5 | independent semantic ACCEPT |
| work/review/REV-0059/evidence.md | d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7 | frozen E3 FR-08 observation |
| tests/execution_core/test_acquisition_stateful.py | 1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22 | untracked frozen detector; not this candidate |
| app/execution_core/acquisition.py | 3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7 | unchanged R12 source context |
| tests/execution_core/test_acquisition.py | 2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb | unchanged R12 test context |

The original R12 manifest/result remain valid only for the semantic candidate
they froze. This new manifest independently covers the later, records-only
activation delta; it neither replaces nor reinterprets the semantic result.

## Exact activation-delta target

| Path | SHA-256 | Allowed purpose |
|---|---|---|
| work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md | b97c43351eb9e6ffd8d60625c3a5958f6451cf6ed37a9925dd3128db16be639c | unambiguous R12 lifecycle/authority gate |
| work/active/WO-0152-reset-kernel-e3-generation-conformance.md | fbcc6f39ad177ede12b68f7d9235332f10ef67fa7bf500ea92c27b1d891e3f7e | retain E3 pause and dependency |
| pkl/project/goals.md | 79c93d54e6737a39385079d0a9e694cfe003c9be7f09bb5d2c27a906def28356 | current posture only |
| pkl/architecture/architecture-map.md | d7a271b2b30a0099de954659b3dcf59de5ae68c5a7ad76932c7006862aef5cb5 | current architecture posture only |
| pkl/log.md | 16cf95853e4f0923670af9717f237b839eec53da099f35cfaf9204d40fb114b0 | append-only chronology |
| docs/adr/ARCH-RESET-2026-07-RATIFICATION.md | e83953e70129d9e8347e01d6058474db32401c59a2ecf2fdfc5e9c9d5d9b857d | append-only provenance only |
| work/ledger.jsonl | b57428fdf6cb49cd165bdc5f40f2d50afd38b659fd0ec2c7aa4c4d4ea185dac7 | append-only lifecycle record |
| work/review/REV-0058/r12-activation-disposition.md | 1a2e25b088c2da2b0d9f221d669329115d820d84d7088b45fe9753cb043cd049 | constrained activation/reconciliation rule |
| work/review/REV-0058/request-r12-activation-delta.md | 18327d0497f25443a3b4d354703b844917c18436b320f91fb0548a502a27fdb7 | independent review request |

## Candidate integrity and review boundary

- `result-r12-activation-delta.md` must be absent before the independent reviewer writes it.
- No tracked `app/`, `tests/`, CI, dependency, ADR-body, or runtime file may differ from the review base.
- The only untracked source remains the immutable E3 detector listed above; it is neither staged,
  changed, executed, nor used as activation-delta evidence.
- The delta may only clarify that the top-level WO-0151 implementation authority is historical
  R11/R11-R1 provenance and that R12 implementation remains ungranted until this review and its
  exact-SHA reconciliation complete.
- The contract, original R12 manifest/result, E3 evidence/detector, R12 allowed source/test paths,
  E3 FR-08 pause, unchanged paired 93% closeout, and all operational exclusions must remain exact.

## Immutable Markdown hard-break disposition

The following pre-existing, hash-pinned Markdown hard breaks are permitted to
be the complete output of full staged `git diff --check`:

1. `work/review/REV-0058/WO-0151-RED-CANDIDATE-R12-MANIFEST.md:5`;
2. `work/review/REV-0059/evidence.md:3`; and
3. `work/review/REV-0059/evidence.md:4`.

The reviewer must independently reproduce exactly that set and confirm a
diff-check over every other staged candidate path exits zero. Any additional
diagnostic, or a changed pin for either immutable file, blocks acceptance.

## Explicit post-review reconciliation allowance

After an exact `ACCEPT` at P0=0/P1=0, this manifest allows only one additional
documentation reconciliation after the first activation publication commit:

- replace the literal R12 activation placeholders in the WO-0151 header and
  `r12-activation-disposition.md` with that first commit SHA;
- change only `r12_status` and `r12_implementation_authority` from their exact
  pending forms to the frozen R12 implementation grant; and
- append that SHA and unchanged E3 pause to the ratification, three PKL records,
  and ledger.

It may not change any contract, source/test file, source/test scope, safety
boundary, existing result, E3 evidence/detector, coverage gate, or review
verdict. The constrained reconciliation must rerun scope, disposition, ledger,
PKL, and whitespace gates before R12 implementation begins. Any other change
to a listed target requires a replacement manifest and fresh review.

This manifest intentionally excludes itself and the future reviewer result.
