# REV-0075 R2 — WO-0168a owner-proof remediation review

Return findings only. Do not edit source, tests, governance files, request files, or result files.
Do not commit, push, access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R1 finding record: `work/review/REV-0075/result-r1.md`
- Remediation parent: `7fa6c2a9c5ce63a3e40362c55f5919b1d88cd6db`, tree
  `86a84e84a5710827055609679e7cd0202131b0f3`
- Exact remediation candidate: `7ce59209f7ac673477a766e42ccd5b2a54406749`
- Candidate tree: `fb5d8278f1338ae0fd5d56a557308fb3dc9411bf`
- Review diff: `7fa6c2a9c5ce63a3e40362c55f5919b1d88cd6db..7ce59209f7ac673477a766e42ccd5b2a54406749`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0075/request-r1.md`, `result-r1.md`, and this request.
3. `work/review/REV-0074/result-r7.md`, the active WO, and contract sections 4.1, 4.4, 5, 8, and 9.
4. The exact review diff, then the changed source and tests.
5. Reproduce the focused pure evidence at the candidate only as needed; no SQLite activity is
   allowed. The author reports green: position/protection/import-boundary/fill-position/stateful
   suites, persistence-operation tests, ruff, mypy, and `git diff --check`.

## Required adversarial lenses

1. Re-derive whether `_M2ExecutionObservationProof` actually binds its current direct slice to the
   exact state/aggregate commitments, rejects forged, substituted, stale, and cross-state
   observations, and retains no history-shaped map or generic decoder.
2. Re-derive whether `_M2ProtectionAuthorityProof` binds all current selection coordinates—application
   generation, profiles, scope, controller head, live generation, authority row, session, stream,
   mandate, state commitment, version, and source—without a bare-tuple escape or a second engine.
3. Check behavior-level public-to-owner delegation and parity for BUY/SELL, correction, bust,
   metadata/fold mismatch, replay/conflict, and incoherent-snapshot behavior. Reject source-text-only
   evidence.
4. Look specifically for complexity that does not buy safety, weakened historical boundary tests,
   scope creep, mutable/caller-mintable proof bypasses, or any prohibited database/runtime/network
   activity.

## Result contract

Report each finding with P0/P1/P2 severity, file:line, mechanism, impact, and smallest complete
root correction. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`), P0/P1/P2
counts, and unverified items. This is a remediation review, not the final WO-0168a closure review.
