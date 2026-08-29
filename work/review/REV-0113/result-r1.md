# REV-0113 R1 — Independent correction verification

No open findings. The original REV-0113 P1 is resolved at the executable-contract level.

## Verified identity and scope

- Repository remote: `https://github.com/amujtabaa/automation-alpaca.git`; branch: `codex/m2-wo0168-atomic-uow-r1`.
- Original contract candidate `9485256811e633578c0059afe15b160c4555d8b6` (tree `f31bed27f8041550f78c81f6dc502e8b28bf523f`) is an ancestor of the accepted finding-preservation parent `cb30fa4eeab193597936c79022e61ab5813b3427`.
- Correction candidate `088b8bc5ea0bf37c7a40a266c8941fd3ccf907b2` has exact parent `cb30fa4eeab193597936c79022e61ab5813b3427` and tree `949dba2d3892486020071f4be9dda9c6d843b259`.
- The correction diff changes only `work/active/WO-0168-m2-i4-atomic-unit-of-work-effects.md` (32 additions, 4 deletions); `git diff --check` passed. No source, test, DDL, or companion-contract file is in the correction diff.
- The candidate work-order SHA-256 is `223157502b228ea25224f507340e9c3b11fbb5d0791f0db508f9498880885a63`; the original REV-0113 result SHA-256 is `838ee22d61707e1eeb6f35af247778052729c7d2d1a172fc2f3b0f92c35d7413`.

## Correction verification

- `FR-1` now requires direct-proof authentication of every operation-keyed omitted member that the selected reducer can read before reduction. The correction requires one exact, sealed, operation-keyed observation proof before an owner reducer reads a deliberately omitted checkpoint member; the UOW may derive it only from the selected current row and retained durable-input/semantic-key evidence.
- For `BeginManualFlatten` and `AdvanceManualFlatten`, the proof partitions the targeted manual identity into `ACTIVE_CURRENT`, `RETAINED_TERMINAL`, or `ABSENT`. These cases respectively bind the checkpoint-represented active row, retained input plus terminal outcome with no active row, or the proven absence of both evidence classes.
- The shared authority kernel may consult only that proof for the targeted flatten ID. An unbound `_manual_by_id` entry is expressly non-authoritative and cannot alter disposition, reason, writes, or successor context. This prevents the exact payload-equal omitted-map behavior reproduced in the original P1.
- The public owner API and UOW route must delegate to the same shared kernel, so the correction does not leave a public-owner bypass or introduce a second reducer engine.
- The authority-proof slice mandates the two original payload-equal counterexamples as failure-capable RED controls: an added omitted row must neither change fresh `BeginManualFlatten` from its clean result nor make fresh `AdvanceManualFlatten` apply. Its required mutants also fail if the kernel reads the raw map, accepts only a semantic digest without retained bytes/outcome, or treats terminal state as active.
- The correction expressly forbids historical-map serialization, caller mappings/callbacks/assertions, generic callback/registry/`Any` dispatch, and caller-provided write plans. It changes no DDL.

## Evidence limits

This was the packet-required static correction review of the exact contract diff. No implementation exists at the correction candidate, and no SQLite/database/DDL/held-suite, credentials, broker/network, or order activity was performed.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: Runtime implementation and prohibited database/DDL/held-suite behavior were outside this correction-only static review.
