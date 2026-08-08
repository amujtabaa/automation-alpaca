# Independent WO-0151 R13-R1 records-only activation review result

Review posture: independent, static, records-only, and review-only. I reviewed
the exact candidate frozen by
`WO-0151-R13-R1-ACTIVATION-DELTA-MANIFEST.md`. I did not run application
tests, coverage, runtime, database/SQL/DDL, broker/network, or CI work. I did
not stage, commit, or publish any path.

## Finding

### [P1] Conditional regression-suite edits exceed the exact five-path activation boundary

- Location: `work/review/REV-0060/WO-0151-R13-R1-ACTIVATION-DISPOSITION.md:53`
- Requirement: `request-r13-r1-activation.md:29` limits the second commit to
  exact publication-SHA substitution plus activation of the ratified five-path
  R13 source/test scope. `WO-0151-R13-R1-ACTIVATION-DELTA-MANIFEST.md:70`
  freezes exactly three application paths and two test paths for that boundary.
- Evidence: reproduced-live static inspection. The disposition correctly says
  the second commit may change only the seven current records and lists the
  five frozen source/test paths at lines 45-52. However, the same colon-led
  activation list then adds directly necessary records and authority, venue,
  and protection regression suites, expressly allowing suite edits for a
  genuine in-scope root defect at lines 53-55. Those additional test paths are
  outside the activation request's exact five-path boundary and are not pinned
  as frozen source/test rows in this activation manifest. The current copies of
  `test_authority.py`, `test_venue_recovery.py`, and `test_protection.py` still
  match the earlier semantic-manifest pins, so this is a prospective scope
  escape rather than a current byte drift.
- Impact: after reconciliation, an implementer can read the disposition as
  authority to edit additional regression suites without a replacement exact
  activation allowlist and fresh review. That makes the requested five-path
  scope bypassable.
- Resolution: either make all regression suites outside the five frozen paths
  execution-only/read-only evidence, or replace the activation request,
  disposition, and manifest with one consistent exact path set and obtain a
  fresh independent activation review.

## Reproduced evidence

- Branch/base/index: branch `codex/arch-reset-2026-07-r1`, `HEAD`, review base,
  and merge base all equal `051c758ce8b89985aa13cb1240e2fff64f5efac6`;
  base-to-HEAD counts are `0/0`; the index was empty; the reviewer result was
  absent before creation.
- Manifest integrity: all 31 listed paths existed and matched their exact
  SHA-256 values. The ratified contract, clean semantic manifest, and semantic
  result matched `240fc0e1...3c90`, `c05cddbc...9222`, and
  `71b7ff74...d1a5` respectively.
- Current records: the seven-record delta records exact semantic ratification
  while retaining activation pending, source/test authority ungranted,
  WO-0151 effective `REVIEW`, and no detector, coverage, external-CI, M1, or
  closeout success claim.
- Retained evidence: both original format-blocked manifests matched their
  exact retained hashes, remained untracked and unstaged, and retained only
  their recorded two-space Markdown hard breaks at lines 6 and 5. The original
  activation disposition/request/result also matched their retained pins and
  remained untracked and excluded.
- First publication allowlist: 19 unique paths -- seven current records, eight
  clean semantic packet paths, the clean activation disposition/manifest/
  request, and this reviewer result. It contains zero `app/`, `tests/`,
  `.github/`, ADR-body, runtime, database, or operational paths. The sole
  tracked path outside those seven records is the explicitly excluded frozen
  detector.
- E3 boundary: WO-0152 remains `ACTIVE` with implementation `PAUSED`. The
  detector and freeze record matched
  `c89dc011...718` and `d83257b7...9fb`, the detector remained unstaged, and
  the unchanged paired exact-head Python 3.11/3.12 gate at 93% plus all safety
  exclusions remain mandatory.
- Whitespace: ordinary and cached `git diff --check` returned exit 0. Direct
  trailing-whitespace scans and untracked-safe no-index checks found zero
  diagnostics across all 11 existing clean untracked publication artifacts.
- Static governance: the exact 19-path publication allowlist passed the
  work-order scope validator; disposition, ledger, and PKL validators also
  returned exit 0 without staging the candidate.

## Disproof and limits

The commit-order language does prevent source/test edits inside the second
commit itself, so the finding is not P0. I also tested whether the extra suite
wording could be execution-only; the explicit phrase "with edits" prevents
that narrower reading. No P2 issue remains after deduplication.

Application behavior, tests, coverage, runtime, database, network, CI, and
external publication remain intentionally unverified under this review's
records-only restrictions. This result does not authorize either publication
step while the P1 remains unresolved, and it does not authorize R13
implementation.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
