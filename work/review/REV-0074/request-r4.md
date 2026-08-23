# REV-0074 R4 — fresh operation-wire amendment review

Write only `result-r4.md`. This is a documentation/static review; do not edit source, planning,
request, or prior result files.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Accepted authority base: WO-0167 closeout
  `0777fab62598f85ce189f40eb1a69319791282c2`, tree
  `1db6fe831fc7d7785d032c224072b131cd5643e9`
- Prior accepted R3 candidate: `bd8024e35301d96bf22a4e44606fa78cb2e07488`, tree
  `3f76e66906a42eaf12d0a7d7f22dfddcd676af59`
- R4 amendment parent: `2c0a58fee31ca13766151fb6fbfd4b3e0bf51ca6`
- Exact R4 candidate: `78eb37a3cfc347cf4b31aa16da275c427e8614b2`
- Candidate tree: `c03e599b26ca4061ae36a04be48d271d147eedc2`
- Amendment diff: `2c0a58fee31ca13766151fb6fbfd4b3e0bf51ca6..78eb37a3cfc347cf4b31aa16da275c427e8614b2`

## Read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0074/result-r3.md` and this request.
3. `work/active/WO-0168a-m2-i3-5-runtime-state-checkpoint.md`.
4. The complete frozen contract, with particular attention to sections 2.1, 2.3, 2.3.1, 2.5, 5,
   and 8.
5. At the accepted predecessor head, only the exact owner definitions necessary to test the wire
   table: `fills.py`, `venue.py`, `recovery.py`, `authority.py`, `acquisition.py`, `protection.py`,
   `identity.py`, `values.py`, and `durable_codec.py`.

## Required adversarial review lenses

1. Reproduce the exact candidate/tree/range. Confirm that R3 left the now-recorded wire ambiguity
   open rather than claiming this future detail already existed.
2. Try to construct two byte-distinct operation encodings that still satisfy the amended table.
   Attack the top array, domain pair, coordinate tags, every aggregate tag, every enum owner tag,
   M1-atom versus string substitution, direct-Fraction form, bytes/absence rules, and each
   domain-to-payload closure.
3. Verify every table row against its owning constructor fields. In particular, check the declared
   derived-field exclusions, `DualMandateBinding` hydration route, market occurrence identity,
   M1 durable-atom coverage, and the absence of a generic reflection/registry/pickle fallback.
4. Attack `VenueOperationCoordinates.session_id is None`: determine whether exact
   `ObserveVenueStatus` is the right and sufficiently bounded exception, and whether the amendment
   prevents missing-session evidence from becoming authority or a defaulted session.
5. Recheck the original finite union, semantic-key rules, no-second-engine requirement, exact scope,
   DDL human gate, and all forbidden runtime/database/network/broker/order activity. This review
   authorizes none of them.
6. Identify any contract conflict that would require a different design rather than a local patch.

## Result contract

Write findings only in `work/review/REV-0074/result-r4.md`. Each finding must state severity,
file/line, mechanism, impact, and the smallest complete root correction. End with exactly one
verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`), P0/P1/P2 counts, and unverified items.

No operation document codec, acquisition hydration seam, source test for those features, changed
DDL installation, SQLite test, configured or in-memory database, runtime composition, credential,
network, broker, order, migration, promotion, or master merge may proceed until a fresh R4 verdict
accepts this exact candidate with P0=0/P1=0.
