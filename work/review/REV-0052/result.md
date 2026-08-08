# WO-0149 corrected-specification final preflight result

Review target: `work/queue/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md`

Target SHA-256: `8257907E9DC0772D8E419696FA8A0B7BFB8BA13BCCD4E464814314CF9B275D47`

Activation base: `2462fb557172dd28a7475a763eca0b440c0298e3`

Review mode: static, findings-only; no tests, application code, SQL/DDL, database, broker, network,
or Git mutation was executed.

## Findings

### [P1] The activation gate requires a second same-candidate preflight that does not exist

- Location: `work/queue/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md:95`
- Requirement: The Fable gate must describe the documentation-only activation evidence path
  completely and consistently; this packet is the final exact-candidate preflight, and AC-05 at
  lines 423-424 requires one independent preflight with no unresolved P0/P1.
- Evidence: **static-reasoning**. The `done_when` test at line 97 requires two independent static
  planning preflights against the same frozen candidate. `REV-0051/result.md:5` reviewed SHA-256
  `A85192BDC18455FBE7D6E2EA6178DBAA76ABB14608987EB7B8F9F61BB782DBEF`, not this candidate.
  `REV-0052/request.md:7` and the fresh file hash identify this review as the only preflight of
  `8257907E9DC0772D8E419696FA8A0B7BFB8BA13BCCD4E464814314CF9B275D47`. The separate rerun that
  found the four repaired roots was not an `ACCEPT` of this corrected hash. Consequently even an
  otherwise accepting REV-0052 result would leave the candidate's own two-review `done_when`
  condition false.
- Concrete effect: WO-0149 cannot truthfully claim activation-complete after this designated final
  review without either starting an unnecessary additional review cycle or incorrectly counting a
  review of different bytes. That is a material internal contradiction in the activation gate, not
  an implementation defect.
- Smallest complete resolution: Replace the line-97 test with one fresh final independent static
  planning preflight (`REV-0052`) that returns `ACCEPT` with P0=0/P1=0 against the exact frozen
  candidate, consistent with AC-05 and the review request. Freeze the corrected hash and rerun this
  final preflight; do not satisfy the defect by counting `REV-0051` or adding a second redundant
  same-candidate review.

## Required disproof disposition

No additional finding survived the static disproof pass:

- FR-03 refuses caller-shaped exposure-increasing BUY `SUBMIT`/`REPLACE` at creation and final
  claim while preserving only a current-target-derived BUY `CANCEL` under its inherited safety
  route.
- FR-05 requires one atomic preemption/wait latch, safely-local stand-down, exactly one current BUY
  leg per sequenced cursor advance, and no SELL release until no next leg exists and every relevant
  parent is exactly `CLOSED`; `OPEN`, `INVALIDATED`, acknowledgement, and known-leg terminality do
  not release.
- The activation allowlist contains the promised current-status/ledger/PKL/review records. Its
  narrower prose forbids retained-evidence rewrites, permits only one append-only WO-0148 external-
  success addendum, and freezes every `activation_only_path` out of later implementation unless
  separately re-gated.
- The task-start marker and YAML gate otherwise match the Fable required-block grammar, preserve
  documentation-only activation, bar implementation until a separately recorded boundary, and
  require RED-first proof after that later authorization.
- FR-01 through FR-06 retain distinct immutable acquisition/protection authority, one registered
  composite head rechecked at creation and final claim, one-fold atomic first-fill integration,
  correction/bust and late-positive recovery under retained authority, bounded current-index
  decisions with no audit/private/test seam, an I/O-free pure reducer boundary, accepted ADR-020
  through ADR-023 authority, and explicit separation of activation from future implementation.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: External GitHub Actions run #693 was not independently queried because network activity is prohibited by this review packet.
