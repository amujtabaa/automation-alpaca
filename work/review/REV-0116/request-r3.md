---
type: Review
review_id: REV-0116
work_order_id: WO-0169
review_mode: same-seat correction-only static verification
status: REVIEW
authoritative_candidate: 47306fe81fb9f279e6190f00ae5241eef7f9203a
---

# REV-0116 R3 — verify the accepted compact-cutover ordering correction

Return to the R2 review seat and verify only its one accepted P1, the directly caused regressions,
and whether the correction remains minimal. Do not restart predecessor or broad WO-0169 review,
edit files, commit, push, open SQLite, create a database, install DDL, run held suites, or implement
source.

## Exact binding

- Repository/branch: `automation-alpaca` /
  `codex/m2-wo0169-startup-cold-recovery-r1`.
- R2 reviewed candidate: `54f9474b9277a4c69272df3c402e64e8058b4ac5`, tree
  `3d14c2d40ab4594e0fc3383dd96ed8afa930b975`.
- Corrected candidate: `47306fe81fb9f279e6190f00ae5241eef7f9203a`, tree
  `448cc6aabce8674e5e77f9b26521fc1894b222f6`.
- Corrected active-WO blob: `73e835944d516a5a38e8c1e9fa0f51091cdd53af`; file SHA-256
  `759b3d386ce4aeca3c5e9f6292be14a570af68d4cc6a34f204eb4319639a389f`.
- R2 result blob: `7670e04f466b99e9751511fb8d44648a3e17a541`; SHA-256
  `a17876c18da25638da0b03dda80f73ba789702c48a38165c7352fda7f55b8beb`.
- DDL remains inherited and unchanged at 190,705 bytes / SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

## Finite verification

1. Confirm compact construction now commits and rereads cold-invalidated C1 before the first
   M2-I4 reconciliation operation, so compact owners never authenticate against C0.
2. Confirm every applied reconciliation operation consumes the latest admitted context and returns
   its successor normally through the existing M2-I4 boundary.
3. Confirm the same private cold-invalidation transition is a valid final pre-source barrier:
   exact replay/no head advance when invalidation remained current, or one committed+reread
   successor if reconciliation changed relevant state.
4. Confirm rollback, ambiguous initial commit, applied checkpoint-changing recovery,
   source-refusal/retry reload, and no-extra-advance controls are now explicitly required.
5. Confirm the correction does not add a second mutation path, public operation, DDL/table, replay
   store, callback/framework, adapter, or broader scope.

Report only an incomplete/bypassable correction or regression caused by this exact amendment. End:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1. Return the complete proposed contents of `result-r3.md`; do not
modify prior review artifacts.
