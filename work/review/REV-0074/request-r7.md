# REV-0074 R7 — owner-proof binding amendment review

Write findings only. This is a documentation/static review. Do not edit source, tests, DDL,
planning, request files, prior result files, or the implementation worktree. Do not commit, push,
access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Accepted R6 amendment candidate: `e3d6665d999bb46be37ca812ba41906191d963cf`, tree
  `e7cf739a00be650192ba572a5ce526063b8c3743`
- R7 amendment parent: `0db3fccdc8719d6766557443f59caa14f142e274`
- Exact R7 candidate: `b85e253f100571c9cd0456a062cc41d39b77dd0d`
- Candidate tree: `3e6c0b7db09d6283236d356da99e2c4509ef686b`
- Amendment diff: `0db3fccdc8719d6766557443f59caa14f142e274..b85e253f100571c9cd0456a062cc41d39b77dd0d`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0075/request-r1.md`, then this request.
3. `work/active/WO-0168a-m2-i3-5-runtime-state-checkpoint.md`.
4. `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md`,
   especially sections 4.1, 4.4, 5, 8, and 9.
5. The exact amendment diff and `git diff --check` only. Source may be inspected only to validate
   that the proposed proof boundaries are a minimal complete response to the recorded R1 findings.

## Required adversarial lenses

1. Confirm the execution amendment requires actual aggregate/current-row proof binding, not merely
   a digest or a caller-mintable wrapper. It must reject absent, substituted, stale, and
   cross-state proof slices without retaining maps or replaying history.
2. Confirm the protection amendment replaces the bare authority tuple with one typed, sealed proof
   that binds application/profile/scope/controller-currentness/live-generation selection to the
   authority row and rebuilt state. Identify any coordinate still left unbound.
3. Confirm the proposed root correction is no broader than needed: no new operation, schema family,
   persistence write authority, DDL execution, runtime composition, external call, or safety
   exception.
4. Confirm the amendment explicitly preserves the normal REV-0075 implementation review and any
   changed-DDL human gate.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No source or test change implementing the R7 proof boundary is permitted until a fresh R7 verdict
accepts this exact candidate with P0=0/P1=0. The normal REV-0075 implementation review and any
changed-DDL human gate remain independently required.
