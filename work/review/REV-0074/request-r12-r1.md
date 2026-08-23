# REV-0074 R12-R1 — corrected persisted-document contract review

Write findings only. This is a documentation/static review. Do not edit source, tests, DDL,
planning, request files, prior result files, or the implementation worktree. Do not commit, push,
access SQLite, create a database, invoke runtime composition, use credentials, or make network,
broker, or order calls.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Original R12 candidate: `78f96af9f2597fe981f3b760f72923c5e331e379`, tree
  `c3fe51651d906707934f78c66107c9dca10a9969`
- Preserved first-round findings: `result-r12-codec.md`, `result-r12-capability.md`, and
  `result-r12-relational.md`
- Exact corrected R12-R1 candidate: `a921caa0ed389b846f8063fc94dfdc6663b65fc2`
- Candidate tree: `d448fb1be2f629500b9b4cac53c25da8255bdab0`
- Remediation diff: `78f96af9f2597fe981f3b760f72923c5e331e379..a921caa0ed389b846f8063fc94dfdc6663b65fc2`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. This request, all three first-round R12 findings, and the R9 design/preflight findings.
3. The active WO and the frozen contract, especially R12 and R12-R1.
4. The exact remediation diff and `git diff --check`.
5. `schema.py`, `records.py`, `repository.py`, `checkpoint_codec.py`, and `operations.py` only as
   needed to challenge a claim against accepted structure. Do not run SQLite.

## Required adversarial lenses

1. Confirm the exact length fields are now bound to the bytes for all four document kinds and the
   outbox sequence is cryptographically bound to its kind-`0x05` snapshot.
2. Try to construct a receipt/outcome pair that selects the same input and technical state but
   differs in owner domain, disposition, result digest, or any nullable checkpoint member. The
   contract must require rejection at the relational boundary.
3. Try to attach an authority semantic key for application A to a durable input from application B;
   verify the required trigger checks both application generation and profile/scope ownership.
4. Evaluate the genesis bootstrap route for a real bootstrap cycle, an extra production setup-token
   route, partial baseline, missing head/payload constraint, or accidental new operation/runtime
   authority. It must remain UoW-owned, finite, zero-state, and blocked until full outer checkpoint
   rows exist.
5. Verify every scoped database-bearing persistence test can legally obtain its fixture capability,
   while `app/**` remains unable to import setup support. Compare every current repository mutator
   to the corrected matrix.
6. Recheck the immutable payload-history / mutable current-head relation, all six record families,
   and the no-receipt/no-outbox authority boundary. Identify any missing exact key, FK, null rule,
   trigger, or source/test path.
7. Confirm this remains documentation-only and preserves the independent REV-0075 implementation
   review plus exact changed-DDL human gate.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No source, test, DDL, or SQLite work implementing R12-R1 is permitted until a fresh verdict accepts
exact candidate `a921caa0ed389b846f8063fc94dfdc6663b65fc2` with `P0=0/P1=0`. The normal REV-0075
implementation review and changed-DDL human gate remain independent.
