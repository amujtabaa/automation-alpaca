# WO-0151 R11 R1 implementation closeout

Status: **LOCALLY VERIFIED — EXTERNAL EXACT-HEAD CI PENDING**

WO-0151 implements the pure, deterministic, I/O-free E2 serial acquisition
controller under the ratified R2--R11-plus-R11-R1 composite.  The exact
remediation candidate is frozen by manifest SHA-256
`2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853`.
The final independent Sol recheck is SHA-256
`96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd`
and returned `ACCEPT`, P0=0/P1=0/P2=0.

## Public interface handoff

WO-0151 adds the following package-root acquisition surface while preserving
the existing E1 lineage readers:

- identity and binding: `AcquisitionMandateId`,
  `EmergencyRecoveryCompatibilityId`, `AcquisitionMandate`,
  `DualMandateBinding`, and `EmergencyRecoveryCompatibility`;
- aggregate values: `SymbolAcquisitionController`,
  `AcquisitionControllerState`, `AcquisitionControllerStatus`,
  `AcquisitionControllerTransition`, `AcquisitionControllerDisposition`,
  `AcquisitionRecoveryClass`, `AcquisitionEffectTerms`, and
  `AcquisitionOrderType`;
- aggregate transitions: `initialize_acquisition_controller`,
  `begin_acquisition_generation`, `reduce_acquisition_controller`,
  `rebase_acquisition_protection`, `create_acquisition_effect`,
  `claim_acquisition_effect`, `begin_acquisition_preemption`, and
  `create_acquisition_protection_exit`;
- authority-free reads and protection relations:
  `project_acquisition_controller`, `AcquisitionProtectionContext`,
  `AcquisitionProtectionRebaseKind`,
  `AcquisitionProtectionRebaseProjection`,
  `project_acquisition_protection_context`,
  `project_acquisition_protection_rebase`,
  `AcquisitionMixedRecoveryProof`, and
  `force_acquisition_mixed_recovery`.

Authority and venue owners retain their already-frozen public contexts,
admission/currentness receipts, effect/claim views, bootstrap/fact projections,
and refresh/apply entry points.  Private sealed relations remain module-owned;
none becomes caller-shaped authority.

## Implemented behavior

- One symbol-level controller owns deterministic A-to-B-to-C serial generation
  rollover with at most one LIVE generation and exact equal emergency-recovery
  compatibility.
- Genesis, successor admission, effect creation/claim, BUY preemption,
  protection exit, and final claim each revalidate the exact current authority
  pair and fail closed on stale or ambiguous input.
- Current and retired FILL/CORRECT/BUST facts update direct lineage and
  aggregate economics exactly once, including non-tail reconciliation and
  late-fact recovery.
- Neutral raw-protection catch-up is transport-only; semantic protection rebase
  is separately owner-authenticated and advances one controller head.
- Goal-independent `PREEMPT_BUY_ONLY` and goal-bearing protective SELL exit
  have disjoint protection-owned producers and one-cancel/single-flight caps.
- Bounded direct indexes and projections are used throughout; no audit-history
  scan or unbounded collection is a live decision input.

## Verification and review evidence

- Complete pure execution-core suite: 1,353 collected, 100%, exit code 0.
- Focused applied-fact matrix and named mutation controls: 17/17 passed.
- Thirteen named fail/restore mutations each turned its intended control RED;
  all temporary mutations were removed.
- Ruff lint, exact 11-path Ruff format, mypy over 87 application files, import
  boundaries (6/6 kept), work-order scope, ledger, PKL, disposition, and diff
  integrity all passed.
- Initial independent implementation result
  `84484417c9dce913e8280ec517883646bd3f557678d4ea482734e72f9d929aba`
  remains retained `ACCEPT-WITH-CHANGES` evidence.  Its single matrix/mutation
  P1 is explicitly closed by the final recheck; it is not an acceptance basis.
- The earlier local R2 attempt stopped at inaccessible pytest temporary-root
  setup before collection, fixture, SQL/DDL, database, or test-body execution.
  It is inadmissible as acceptance evidence and no conclusion relies on it.

## Resolved findings

The accepted remediation completes the current/retired
FILL/CORRECT/BUST matrix and retains executable mutation evidence.  The matrix
also exposed and resolved one owner-level defect: an authentic retired
non-tail BUST with no live successor BUY may omit fact-preemption and proceed
through ordinary canonical-fact registration.  An active successor BUY still
requires atomic fact-plus-preemption; stale, forked, or mismatched cases remain
refused.

## Deferred obligations

- Unchanged GitHub Actions Python 3.11 and 3.12 jobs must both pass on the exact
  closeout commit before WO-0151 is effectively CLOSED.
- WO-0152 E3 generated/stateful conformance remains DRAFT/inactive and requires
  its own activation gate.
- Persistence, runtime wiring, SQL/schema migration, broker adapter behavior,
  Paper activity, and all M2 work remain future separately authorized gates.
- Master landing and branch/worktree retirement remain outside this closeout.

This closeout adds no runtime, database, broker/network, credential, M2,
merge, deletion, cleanup, rebase, force-push, or later-work-order authority.

## Subsequent exact-head coverage outcome

Run #741, ID `31185454392`, on
`a2b84abc1914517cf591f27fb88f0b20b2a47ef7` supersedes only the statement
that the external result was pending. Both supported Python jobs completed the
functional/static gates and 5,934 tests, but failed the unchanged 93% coverage
gate at 91.34%. Under the separately authorized coverage-gate ordering
amendment, WO-0151 remains effectively `REVIEW` and its final gate is paired
E2/E3 exact-head CI. This retained closeout is not otherwise rewritten.
