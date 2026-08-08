# WO-0151 R12 activation-delta disposition

Status: **PUBLISHED — R12 IMPLEMENTATION AUTHORITY GRANTED AT FROZEN PATHS**

## Semantic predecessor

- R12 contract SHA-256:
  `36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e`.
- R12 semantic candidate manifest SHA-256:
  `a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0`.
- Independent semantic result SHA-256:
  `0bd78212be49059fcc87ae02e23d08867c99944bf21ca1bf92af596612a99ac5`
  (`ACCEPT`, P0=0/P1=0/P2=0).

The semantic packet is immutable retained evidence. It accepts the root
correction but does not itself cover current-posture records written after its
freeze.

## Activation-delta target

`WO-0151-R12-ACTIVATION-DELTA-MANIFEST.md` freezes only the following current
status/provenance paths for a focused review:

- `work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md`;
- `work/active/WO-0152-reset-kernel-e3-generation-conformance.md`;
- `pkl/project/goals.md`;
- `pkl/architecture/architecture-map.md`;
- `pkl/log.md`;
- `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`;
- `work/ledger.jsonl`; and
- this disposition.

It may correct no semantic contract, source/test path, safety boundary, public
surface, or E3 pause. It must make the top-level WO-0151 implementation
authority explicitly historical R11/R11-R1 provenance rather than present R12
authority.

## Immutable Markdown hard-break check

The original semantic manifest and frozen E3 observation contain three
intentional Markdown hard breaks that are part of their already-reviewed exact
content. A full staged `git diff --check` may report only:

- `WO-0151-RED-CANDIDATE-R12-MANIFEST.md:5`;
- `work/review/REV-0059/evidence.md:3`; and
- `work/review/REV-0059/evidence.md:4`.

Their exact SHA-256 pins remain the authority; normalizing them would alter
frozen evidence. The activation-delta review must verify that the diagnostics
are exactly this set and that a diff check over every other staged path exits
cleanly. Any additional whitespace diagnostic blocks publication.

## Publication and exact-SHA reconciliation

The activation-delta manifest
`59ab3d16a4057fe2d3e763d5909ba1751ba0266453551ba07830b2c872bb68f4` and
independent result
`b8382a504c8bb9ac5456067e758a81ec42f9f546ed6194fae4f31b814378e28d`
returned `ACCEPT`, P0=0/P1=0/P2=0. Documentation-only activation commit
`a124b3cda866e2a5aaf99d4527e7b231dd4f675d` published the exact accepted
packet and was pushed normally. This record is the one manifest-permitted
exact-SHA reconciliation.

R12 may now change only `app/execution_core/acquisition.py`,
`tests/execution_core/test_acquisition.py`, and directly necessary current
WO/PKL/ledger/ratification/REV evidence records. The untracked E3 stateful
module remains frozen negative evidence only. No R12 source/test completion
claim is made here; red-first controls, static gates, focused independent
implementation acceptance, and later paired E2/E3 CI still remain required.

## Preserved boundaries

WO-0152 remains ACTIVE but paused under FR-08 until a focused independent R12
implementation acceptance. The public E3 detector must stay unchanged until
it is rerun as post-fix confirmation. The paired E2/E3 exact-head Python
3.11/3.12 93% closeout remains mandatory.

No runtime/public wiring, database/SQL/DDL, persistence, broker/network,
credentials, CI workflow, M2, merge, deletion, cleanup, force-push, or rebase
authority is activated.
