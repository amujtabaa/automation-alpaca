# Independent static preflight result — WO-0152 E3 R2-R1

Review date: 2026-08-07  
Review seat: independent Codex review seat  
Mode: static-only exact-candidate preflight  
Branch: `codex/arch-reset-2026-07-r1`  
Review base / candidate HEAD: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`  
Manifest: `work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R1-MANIFEST.md`  
Manifest SHA-256: `d51393c7862fea52367851d0b1a81e6481a9997aad516508a47a596bc90f649d`

## Outcome

The R2-R1 packet preserves the first R2 candidate as unaccepted evidence, preserves the
root-correct R2 semantic/static controls, keeps implementation authority `NOT_GRANTED`, and does
not broaden the candidate into test, production, runtime, database, broker, CI, or coverage work.
It does **not**, however, completely replace the stale activation reference across the current
authoritative PKL. One current, nonhistorical goals clause still requires exact R2 `ACCEPT`, even
though R2 was stopped without `result-r2.md`. The candidate therefore cannot activate WO-0152.

Activation disposition: **STOP — WO-0152 remains DRAFT/preflight-only.**

## Exact-candidate and hash verification

All observations in this section were made before creating this reviewer-owned result.

- `git rev-parse --abbrev-ref HEAD` returned `codex/arch-reset-2026-07-r1`.
- `git rev-parse HEAD` returned `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`; the required
  review-base object resolves as a commit.
- The manifest's independently computed SHA-256 was
  `d51393c7862fea52367851d0b1a81e6481a9997aad516508a47a596bc90f649d`, exactly the
  expected value.
- I parsed all 50 manifest hash rows and independently recomputed each listed file's SHA-256:
  **50/50 matched; 0 missing; 0 mismatched**.
- The frozen R2-R1 input hashes matched exactly:

| Input | Recomputed SHA-256 |
| --- | --- |
| `WO-0152-RED-R2-R1-REMEDIATION-DISPOSITION.md` | `3db2520002754ea995d079ead1faf92df0a6e2ab00ff3c6bc3a48d65364403bb` |
| `WO-0152-RED-CONTRACT-R2-R1.md` | `4dd085ddfd57f05973fde85ef9de6ba9ba936e047b955dc2e93986b9a5b205e9` |
| `request-r2-r1.md` | `2f3d1c7a2345754bf375641c460bc4141e74a3fd61c048f2ecd686be8a1b679f` |
| `work/queue/WO-0152-reset-kernel-e3-generation-conformance.md` | `ed0b862b29867bd4e68e74259990ec4e4abf6036b0689776aabc152cf3ade151` |
| `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` | `a65120ecbfd9048e338c08d5ef163f64d418e0a3c1e88db25f91e4182e5a4e56` |
| `pkl/project/goals.md` | `505fe72d1d6def3561097a06bfa8764a40200674c1db9165de8a4d3883c7f265` |
| `pkl/architecture/architecture-map.md` | `4a7159dfdddb55adf7b989cc980a10c32638164bfe868320c5bcf3cbf084a234` |
| `pkl/log.md` | `e3bf468d9b84ad52046d4a250c2acb1ede6eea52de5fdf5da6cde0e64d4f85d4` |
| `work/ledger.jsonl` | `c84eede7a54e927116b2e476062fe87ce8e0146537a010a8b8aed7ee7fcc6c86` |

- The retained first-R2 records also matched their frozen hashes:

| Retained R2 record | Recomputed SHA-256 |
| --- | --- |
| `WO-0152-RED-R2-SIBLING-HISTORY-REMEDIATION-DISPOSITION.md` | `b34fb933538ccb4e6ef6a0f2e14ff6f1299da3819ada1ded52b5c64540ef36b4` |
| `WO-0152-RED-CONTRACT-R2.md` | `99e70f48f3ebeb823ef4c9ad344bb4b48ccab831501cec5a20dbcdcbec7c3b9f` |
| `WO-0152-RED-CANDIDATE-R2-MANIFEST.md` | `5bf3c529e703a8fef4e243750697a1669afda3801f8cc6d7bfc726ecab9596ba` |
| `request-r2.md` | `e8e9ccf55d2756bf2cb39912b8ae6590434a0fc5432ed961e6283a8b734f03bc` |

- Before reviewer output, all three required absent paths were absent:
  `tests/execution_core/test_acquisition_stateful.py`,
  `work/review/REV-0059/result-r2.md`, and
  `work/review/REV-0059/result-r2-r1.md`.
- The initial exact status contained 8 tracked modifications and 25 untracked files, with 0 staged
  paths. Every status path was a manifest row except the R2-R1 manifest itself, whose identity and
  hash are pinned above. No production source or existing test path was modified.
- The tracked diff was 8 files, 516 insertions, and 78 deletions. The modified files were only the
  ratification, two current PKL pages plus the PKL log, WO-0151 retained evidence, the append-only
  ledger, the WO-0152 draft, and a REV-0058 closeout record.
- `git diff --check a2b84abc1914517cf591f27fb88f0b20b2a47ef7 --` returned exit 0 with no
  output.

## Static re-derivation and affirmative proof

### Retained evidence and activation ordering

- R0, R1, R1 remediation 01, R1-R1, and first-R2 records remain present at their manifest-pinned
  hashes. No prior request, contract, manifest, disposition, or result was rewritten or removed.
- The first R2 packet is accurately described by the R2-R1 contract, current WO, ratification,
  latest PKL log entry, and latest ledger row as stopped before independent verdict. The absence of
  `result-r2.md` agrees with that description; no acceptance was invented.
- The current WO at lines 45-50 and 249-251, and ratification at lines 378-390, require a fresh
  exact R2-R1 `ACCEPT` with P0=0/P1=0 before test-only activation. The latest ledger row 163 and
  PKL log lines 390-396 carry the same ordering. Earlier packet results cannot satisfy those exact
  clauses.
- The retained exact-head #741 evidence remains functional/static success with 5,934 tests on each
  supported Python job, 11 skips and 1 xfail, and a coverage-only failure at 91.34% against the
  unchanged 93% threshold. R2-R1 neither declares that gate passed nor closes WO-0151/WO-0152;
  paired E2/E3 unchanged 93% exact-head closeout remains required.

### Preserved R2 semantic and static bounds

- The frozen R2 contract remains hash-identical and controlling. R2-R1 expressly replaces only
  the activation condition; it does not edit the six-step public sibling lifecycle, fixture shape,
  pre-install guards, one literal copied `venue` installation, post-install pure bootstrap
  assertion, or negative static controls.
- Static source re-derivation confirms that the prescribed chain is constructible through existing
  public surfaces: generic `CreateBrokerEffect`/`ClaimEffect` dispatch in
  `app/execution_core/authority.py` (including lines 7689-7834, 9302-9407, and 9717-9762), the
  existing public generic BUY create/claim example in `tests/execution_core/test_authority.py`
  (lines 2466-2553), and the ACK/discovery/zero-quantity NEEDS_REVIEW/canonical BUY-fill sequence
  in `tests/execution_core/test_acquisition.py` (lines 386-495).
- The unbound bootstrap path is statically present in `app/execution_core/authority.py` lines
  4029-4110 and the exact same-account venue-source binding path in
  `app/execution_core/venue.py` lines 13796-13880. The target generic BUY remains refused after the
  currentness/bootstrap reservation (`app/execution_core/authority.py` lines 7736-7753).
- ACK and venue status observations retain zero position delta; only the first-occurrence canonical
  fill/revision fact changes quantity. The R2 plan therefore does not weaken submitted-not-filled,
  canonical-execution-fact, paper-only, UI/broker, kill-switch, or single-writer boundaries.
- No production/API change is statically required to express the R2 test. The future test remains
  limited to `tests/execution_core/test_acquisition_stateful.py`; that file is still absent and no
  test implementation is in this candidate.

### Scope and lifecycle

- The WO remains `DRAFT`; `implementation_authority` remains `NOT_GRANTED`.
- The machine-readable R2-R1 scope remains documentation/preflight-only. There is no production or
  existing-test delta, no `INV-*` addition/amendment, and no authority for test implementation,
  production/API, database/SQL/DDL, runtime, broker/network, credentials, CI workflow, M2, merge,
  deletion, cleanup, force-push, or rebase work.
- The replacement is compatible with ADR-020, ADR-021, ADR-023, the safety core, and the bounded
  coverage-order amendment. The defect below is a lifecycle-document consistency defect, not a
  need for production capability.

## Finding

### [P1] Current authoritative PKL still gates activation on the stopped R2 review

- **Location:** `pkl/project/goals.md:69-71` (controlling conflict), corroborated by the stale
  current-tense R2 posture in `pkl/architecture/architecture-map.md:71-73`.
- **Requirement:** R2-R1 must completely replace the stale future activation condition. Only a
  fresh review of the exact R2-R1 manifest returning `ACCEPT` with P0=0/P1=0 may activate E3;
  first R2 has no result and cannot activate WO-0152.
- **Evidence — reproduced-live read-only static inspection:** The top summary in
  `pkl/project/goals.md:40-44` correctly names fresh R2-R1 acceptance, but the active section
  titled `Current R2 ratification posture` later says WO-0152 "remains inactive until exact R2
  `ACCEPT` at P0=0/P1=0." The architecture map's corresponding current section still says that
  WO-0152 remains DRAFT "while R2 corrects" the P1. That is not an append-only historical record.
  It conflicts with the current WO, R2-R1 contract, ratification, latest log, and latest ledger row,
  all of which say first R2 was stopped without a result and only exact R2-R1 acceptance can
  activate.
- **Impact:** The authoritative PKL contains two different current activation predicates. The
  exact-R2 predicate is impossible under the retained evidence and could be read either to block
  lawful R2-R1 activation indefinitely or to invite an earlier/stopped packet to be treated as an
  acceptance basis. This fails the requested complete stale-reference correction and makes an
  `ACCEPT` verdict unsafe even though no implementation authority has yet been granted.
- **Smallest complete resolution:** Update only the nonhistorical current-posture clauses—at
  minimum `pkl/project/goals.md:69-71`, and align
  `pkl/architecture/architecture-map.md:71-73`—to state that first R2 was stopped with
  `result-r2.md` absent and that only exact R2-R1 `result-r2-r1.md` `ACCEPT` at P0=0/P1=0 can
  activate the already bounded test-only work. Preserve the chronological R2 log, ledger, and
  change-log entries as retained evidence. Recompute the changed PKL hashes, freeze a replacement
  immutable manifest/request, and repeat this static preflight.

## Bottom-up disproof and reconciled non-findings

- I first traced the public source transitions and existing tests from the terminal bootstrap
  refusal back through canonical fill, zero-delta status, discovery, ACK, and generic create/claim.
  I found no hidden need for private mutation, a history scan, an extra fixture, or production/API
  capability. This disproves treating the earlier sibling-history constructibility P1 as still
  unresolved by the frozen R2 semantic plan.
- I searched current WO, ratification, PKL, log, ledger, and packet paths for R0/R1/R2 activation
  predicates and for claims of implementation/closeout. The stale current goals predicate above
  survived that pass. The correctly superseded historical goals change-log entry and ledger row
  162 were not findings: their immediately later records retain and supersede them, as required by
  append-only provenance.
- I attempted to disprove the P1 by relying on the correct top-level R2-R1 summaries and later
  provenance entries. That failed because the conflicting sentence is under an equally current,
  authority-bearing section and declares no precedence or historical status.
- I found no P0: the delta does not touch a human-gated implementation surface, violate a safety
  invariant, invent green execution evidence, or claim activation/completion.
- I found no separate P2. The architecture-map wording is part of the same incomplete root
  correction, not an independent defect class.

## Evidence limits

This review intentionally used only read-only static file, source, hash, Git status/diff, and
whitespace inspection. I did **not** run tests, test collection, database-capable fixtures,
SQL/DDL, application/runtime commands, network, broker, credential, CI, or coverage commands. I
did not inspect or mutate broker/database state. Dynamic constructibility, runtime behavior, CI
results, and coverage were therefore not re-executed; cited #741 and coverage values are retained
frozen evidence only. No file was edited by this seat except this result.

Verdict: ACCEPT-WITH-CHANGES  
P0: 0  
P1: 1  
P2: 0  
Unverified: dynamic execution, tests, database/SQL/DDL, runtime, network/broker/credentials, CI,
and coverage — all prohibited by this static-only gate.
