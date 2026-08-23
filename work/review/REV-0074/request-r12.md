# REV-0074 R12 — persisted-document and capability closure review

Write findings only. This is a documentation/static review. Do not edit source, tests, DDL,
planning, request files, prior result files, or the implementation worktree. Do not commit, push,
access SQLite, create a database, invoke runtime composition, use credentials, or make network,
broker, or order calls.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R9 implementation-review findings: `work/review/REV-0075/result-r9-design.md`,
  `result-r9-preflight.md`, and `result-r9-test-critic.md`
- R12 amendment parent: `fd9ff209d6d816aefd442484c842bba22dba85fc`
- Exact R12 candidate: `78f96af9f2597fe981f3b760f72923c5e331e379`
- Candidate tree: `c3fe51651d906707934f78c66107c9dca10a9969`
- Amendment diff: `fd9ff209d6d816aefd442484c842bba22dba85fc..78f96af9f2597fe981f3b760f72923c5e331e379`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. The three R9 findings named above and this request.
3. The active WO and frozen contract, especially existing sections 3--8 and R12.
4. The exact candidate diff and `git diff --check`.
5. `schema.py`, `records.py`, `repository.py`, `checkpoint_codec.py`, and `operations.py` only as
   needed to test each contract claim against accepted M2-I2/I3 structure. Do not run SQLite.

## Required adversarial lenses

1. Check whether the immutable payload-history / mutable current-head relationship has a complete
   root constraint. In particular, verify that a normal child foreign key would make historical
   payloads invalid on head advance, and that the proposed reverse-edge trigger plus write order
   closes the serving-head-without-payload gap without mutating history.
2. Check all six schema families for an exact ordered record/SQL-column contract, nullability,
   primary/unique keys, composite foreign-key parents, insert/update/delete rules, and lifecycle
   ownership. Identify any missing or impossible parent/child relationship before source or DDL
   authoring.
3. Check kinds `0x02`--`0x05`, their canonical arrays, digest derivations, and cross-record
   redundancies. Look for circular digest dependencies, self-authentication, malformed
   nullable-reference rules, or an outbox snapshot that could be decoupled from its immutable
   effect/claim.
4. Check the durable-input primary identity and decoded-operation binding. It must refuse arbitrary
   bytes, wrong coordinate/domain/version/identity combinations, and the only legal null venue
   session must remain exact `ObserveVenueStatus`.
5. Check that receipt/outcome and outbox remain non-authoritative: no receipt-as-state shortcut,
   no external-success state, and no direct currentness/economic/closure authority.
6. Compare the R12 capability matrix against every current repository mutator. Flag omitted,
   misclassified, or impossible test-support paths, direct setup leakage into `app/`, and any
   conflict with the unit-of-work-only future runtime boundary.
7. Check scope: R12 must be documentation-only, add only the declared test-support path, preserve
   the independent REV-0075 implementation review and changed-DDL human gate, and add no runtime,
   network, broker, order, promotion, merge, or M3 authority.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No source, test, DDL, or SQLite work implementing R12 is permitted until a fresh R12 verdict
accepts exact candidate `78f96af9f2597fe981f3b760f72923c5e331e379` with `P0=0/P1=0`. The
normal REV-0075 implementation review and changed-DDL human gate remain independent.
