---
type: Review Result
audit_id: AUDIT-0002
reviewer_model: GPT-5 Codex
status: COMPLETE
verdict: ACCEPT-WITH-CHANGES
pinned_sha: 9add18946380a0dab333263a19549d69c408a552
date: 2026-07-20
---

# AUDIT-0002 — prior-work verification audit

No P0 live-safety defect was reproduced. The current application gate is green,
the sampled safety properties held in both stores, and three sampled historical
pins turned red under runtime-only mutations. The audit found ten P1 record,
test-contract, backlog, and review-integrity defects. This is a findings-only
result: no source, test, ADR, invariant, PKL, queue, active-work, or CI file was
changed.

Detailed command output is in [`evidence.md`](evidence.md); the packet-local
probes are reproducible and write no application state.

## Gate and scope

- Branch anchor: `9add18946380a0dab333263a19549d69c408a552`, after the
  separate WO-0116 hygiene commit.
- `88833e3d..master` contains no `app/**`, `tests/**`, or `cockpit/**` change.
- Credential-name check: all four supported Alpaca key/secret variables absent.
- Baseline: `ruff` PASS; `mypy app/` PASS (64 files); import-linter PASS (6/0);
  3,873 tests collected; full pytest exit 0 (11 skipped, 1 expected xfail).
- Lane-A edits: `work/review/AUDIT-0002-priorwork/**` only.
- No venue call, credential, real database, source mutation, or repo-root pytest
  scratch directory was used.

## Findings

### AUD2-F001 — P1 — completed W3 work is invisible to the disposition checker

**File:line.**
`work/completed/keep/WO-0016-envelope-entity-events-persistence/WO-0016-envelope-entity-events-persistence.md:4,9`;
`WO-0017-envelope-approval-and-precedence/WO-0017-envelope-approval-and-precedence.md:4,9`;
`WO-0018-pure-sellside-policy/WO-0018-pure-sellside-policy.md:4,9`;
`WO-0019-engine-seam-envelope-execution/WO-0019-engine-seam-envelope-execution.md:4,9`;
`WO-0019a-broker-adapter-replace-seam/WO-0019a-broker-adapter-replace-seam.md:4,10`;
`WO-0020-tick-wiring-and-cockpit/WO-0020-tick-wiring-and-cockpit.md:4,9`;
`WO-0021-envelope-chaos-catalog/WO-0021-envelope-chaos-catalog.md:4,9`;
`WO-0024-staged-order-preemption-fix/WO-0024.md:4,9`;
`WO-0025-multileg-lifecycle-and-fill-bridge/WO-0025.md:4,9`;
`WO-0026-reduce-only-enforcement/WO-0026.md:4,9`;
`WO-0027-supersession-order-adoption/WO-0027.md:4,10`;
`WO-0028-test-integrity-and-memory-atomicity/WO-0028.md:4,11`;
`WO-0030-interface-lift/WO-0030.md:4,9`; and
`WO-0031-trail-bar-data-integrity/WO-0031.md:4,10`.

**Evidence.** All fourteen records are physically filed under `work/completed`,
have a `fable-done.md` or equivalent close-out, and have `DISPOSED` ledger rows
(`work/ledger.jsonl:34-52`), but their own status is still DRAFT, gate-awaiting,
or `APPROVED ... DONE`. Thirteen carry `disposition: []`.
`.ai-os/scripts/check_work_order_disposition.py:26,108-109` checks only recognized
completed statuses, so the fresh command returned `DISPOSITION CHECK PASSED`.

**Why it matters.** A green governance gate currently does not mean every item
filed as completed has a canonical status/disposition. That makes lifecycle
queries and hygiene sweeps undercount historical gated work and can falsely
authorize cleanup or reuse of an ID.

**What resolves it.** In a separate hygiene WO, reconcile each header from its
ledger + close-out evidence without rewriting historical bodies, then make the
checker fail when a file under `work/completed/**` has a noncompleted status or
empty required disposition. Candidate title: **Normalize W3 completion headers
and make the disposition checker folder-aware**.

### AUD2-F002 — P1 — INV-051 and INV-052 have no failure-capable repository pin

**File:line.** `docs/INVARIANTS.md:394-412`.

**Evidence.** INV-051 says “no dedicated test”; INV-052 says “structural.” The
claim-link scan found zero test references for both. A fresh AST sample found no
`await` nested under `async with self._lock` in either store, so current code
supports the rules, but no maintained test would necessarily fail on a future
reentrant public call or broker/network await under the lock.

**Why it matters.** Both rules protect the single-writer/store liveness boundary.
A regression can deadlock the process or serialize all state access behind venue
latency while every named CI pin remains green. This fails the charter's explicit
real/passing/failure-capable pin requirement.

**What resolves it.** Add bounded-time dual-store deadlock probes plus a
failure-capable structural/spy check that distinguishes local store helpers from
broker/network awaits. Mutation-prove each check. Candidate title: **Pin store
lock non-reentrancy and off-lock venue IO**.

### AUD2-F003 — P1 — accepted safety text still says REV-0033 is pending

**File:line.** `docs/adr/ADR-002-timeout-quarantine.md:19,64`;
`docs/adr/ADR-003-manual-flatten-halted-reducing.md:21,36-37`;
`docs/adr/ADR-008-order-status-event-provenance.md:77`;
`docs/INVARIANTS.md:127,146,422,535,686`.

**Evidence.** These accepted ADR and INV-001..089 blocks label WO-0113 behavior
“pending REV-0033 independent review.” REV-0033 is dispositioned `RESOLVED` with
`ACCEPT-WITH-CHANGES` at `work/review/REV-0033/disposition.md:4-5,75-81`.
This is a mechanical gate-state check only; WO-0113 semantics were not
self-adjudicated by this Codex seat.

**Why it matters.** The canonical safety contract falsely presents deployed
branch behavior as unreviewed. A later implementer cannot tell whether the text
is normative, provisional, or forbidden to rely on.

**What resolves it.** Append an accurate REV-0033 disposition note to the cited
blocks, preserving their decision history and linking the accepted amendments.
Candidate title: **Close stale REV-0033 labels in accepted safety records**.

### AUD2-F004 — P1 — ADR-006/007 current-state claims lag stronger live gates

**File:line.** `docs/adr/ADR-006-import-boundaries.md:25-27,67-72,95-108`;
`docs/adr/ADR-007-mypy-typecheck-gate.md:26-30,37-49`;
`.importlinter:182-184`; `pyproject.toml:54,67-78`.

**Evidence.** ADR-006's amended current-state text says five contracts; the
fresh gate reports six and `.importlinter` includes the W3 pure-sellside
contract. ADR-007 still describes sixteen grandfathered `ignore_errors`
modules, the resulting blind spot, and `warn_unused_ignores` as future work;
the live config says the punch-list is fully burned down and already sets
`warn_unused_ignores = true`. `mypy app/` is green across all 64 app files.

**Why it matters.** The implementation is stronger, not weaker, but ADRs are the
declared architecture. Stale limits obscure which gate is normative and make a
future weakening look consistent with the written decision.

**What resolves it.** Add dated ADR amendments recording contract 6 and the
completed mypy ratchet; retain the original baseline as history. Also remove the
contradictory “consider flipping” config comment. Candidate title: **Reconcile
ADR-006/007 with completed import and type ratchets**.

### AUD2-F005 — P1 — WO-0029 is a mixed stale umbrella, not an executable re-cut

**File:line.** `work/queue/WO-0029-envelope-eventing-terminal-semantics.md:3-5,19-53`.

**Evidence.** The umbrella leaves SPEC-05 and SPEC-09 unmarked at lines 21-25,
but they landed in WO-0029A (`33945c0`/merge `d1d2e4b`) and are recorded in
ADR-010 and INV-082/085. SPEC-10 and SPEC-08 are correctly marked DONE. CC-06
was subsumed by WO-0030. CC-04 (envelope replay/read-model parity), SPEC-06/07,
and CC-05's truthful `replaces_used` projection remain open; current cockpit
still reads the stored field while enforcement derives history.

**Why it matters.** Activating the umbrella as written would mix already-landed
human-gated decisions with distinct remaining replay, cancel-convergence,
eventing, and read-model work. Scope and approval boundaries are not executable.

**What resolves it.** Planning seat re-cuts only the verified-open classes into
scoped WOs, marks completed/subsumed rows historically, and keeps ADR/event-log
changes behind explicit gates. Candidate titles: **Envelope disposition cancel
convergence**, **Envelope action/replay parity**, and **Single-source replace
budget projection**.

### AUD2-F006 — P1 — queued W3/W4 launch records assert superseded state

**File:line.** `work/queue/W3-README.md:5-42`;
`work/queue/W3-KICKOFF-PROMPT.md:20-81`;
`work/queue/W4-SEED-NOTES.md:37-40,51-58`.

**Evidence.** W3 is merged, ADR-010 is Accepted, and WO-0022 is now explicitly
SUPERSEDED, yet the queue still contains a from-scratch W3 branch launcher and
merge-gate plan. W4 notes say ADR-010 acceptance is still owed and preserve the
`record_envelope_fill(price=None)` poison as open, although INV-089 and WO-0033
closed it. Some W4 research seeds remain useful, but the gate/debt state is not
current.

**Why it matters.** A fresh session following queue order can restart a finished
wave, branch from obsolete ancestry, or plan around already-closed defects.

**What resolves it.** Human chooses the Lane-H deletion batch for the two W3
launch-only files, and a small planning refresh separates still-useful W4 seeds
from closed debt. Candidate title: **Retire W3 launchers and refresh W4 seed
premises**.

### AUD2-F007 — P1 — finished WO-0102 work exists only on a stranded archive line

**File:line.** `work/queue/WO-0102-signal-ingestion-endpoint.md:16-18`;
`work/queue/WO-0103-signal-approval-surface.md:16-19`;
`work/queue/WO-0104-signal-rails.md:16-18`.

**Evidence.** `archive/claude-wo-0001-install-checks-2x5ys8` at `fc81951` has
47 commits not reachable from master and an 8,556-insertion, 60-file signal-seat
implementation/review stack. Master has no `SignalRecord`, `SignalProposal`,
`SIGNAL_RECEIVED`, `routes_signals`, or `signal_seat_enabled` implementation.
ADR-009 on master remains Proposed after REV-0022 BLOCK. Thus WO-0102's archive
completion does not satisfy WO-0103/0104 on the current tree.

**Why it matters.** Substantial reviewed work can be mistaken for shipped work,
or silently lost when downstream WOs are activated from master. It also touches
auth, schema/event truth, and command boundaries, so opportunistic cherry-picking
would bypass the intended gate chain.

**What resolves it.** Human disposition: either authorize a fresh reconciliation
plan against current master (with schema/auth/event-log gates and independent
review), or mark the archive implementation abandoned/superseded while retaining
provenance. Until then, WO-0102/0103/0104 remain CURRENT-BLOCKED. Candidate title:
**Reconcile or abandon the archived Signal Seat implementation**.

### AUD2-F008 — P1 — REV-0029/0030 has no authoritative closed disposition chain

**File:line.** `work/review/REV-0029/result-round2.md:12-34,359-370`;
`work/review/REV-0029/disposition.md:1,96-102`;
`work/review/REV-0030/result.md:8-18,55-66`;
`work/completed/keep/WO-0109-rev0029-round3-remediation.md:4,421-427`.

**Evidence.** REV-0029 round 2 ends BLOCK and its disposition remains titled
IN PROGRESS, explicitly requiring a recorded round-2 disposition. REV-0030 then
returns ACCEPT for WO-0109 but has no `disposition.md` or supersession marker.
WO-0109 therefore remains `status: REVIEW` even though it is physically under
completed and the later PR was merged.

**Why it matters.** There is no single authoritative record saying which BLOCK
findings were superseded, which review cleared the gate, and how WO-0109 closed.
Automation and humans can legitimately reach conflicting answers.

**What resolves it.** Author/operator records the final REV-0029 → WO-0109 →
REV-0030 chain in the correct packet(s), then closes WO-0109 without changing
historical review bodies. Candidate title: **Disposition the REV-0029/0030
round-3 closure chain**.

### AUD2-F009 — P1 — nine remediated W3 FINDING records still say OPEN

**File:line.** Line 3 of
`FINDING-W3-memory-atomic-envelope-rollback.md`,
`FINDING-W3-multileg-false-divergence-livelock.md`,
`FINDING-W3-redrive-revalidation-bypass.md`,
`FINDING-W3-reduce-only-unenforced.md`,
`FINDING-W3-refused-stale-tranche-latch.md`,
`FINDING-W3-staged-order-outlives-preemption.md`,
`FINDING-W3-supersession-exposure.md`,
`FINDING-W3-synthetic-fill-envelope-bypass.md`, and
`FINDING-W3-test-integrity.md` under `work/review/`.

**Evidence.** `work/review/REV-0023/phase-b-reconciliation.md:14-22` maps the
first eight classes to WO-0024..0028 as FIXED; WO-0031's close-out and INV-086
record the refused-stale latch fix. Full current tests pass, and the sampled
reduce-only pin turns red under mutation. The grouped lifecycle/eventing finding
and structural-hold finding remain legitimately open/partial and are not included.

**Why it matters.** The standalone findings are the direct search surface for
known defects. False OPEN labels make resolved safety bugs indistinguishable
from current hazards and can duplicate remediation.

**What resolves it.** Append resolution/disposition blocks naming the exact WO,
pin, and review evidence; preserve the original finding text. Candidate title:
**Reconcile remediated W3 standalone finding statuses**.

### AUD2-F010 — P1 — two older packets violate mechanical request/verdict metadata consistency

**File:line.** `.ai-os/core/15_CROSS_MODEL_REVIEW.md:23-25,36-39`;
`work/review/REV-0019/result.md:1-12`;
`work/review/REV-0019/disposition.md:1-13`;
`work/review/REV-0023/disposition.md:9-15`.

**Evidence.** REV-0019's authoritative result front matter says ACCEPT, while
its disposition front matter still says `verdict_received: ACCEPT-WITH-CHANGES`;
the prose addendum explains the overwritten rerun but mechanical metadata does
not. REV-0023 has result + disposition but no `request.md`; its disposition says
the result was ingested after a branch mix-up. REV-0024's explicit
`SUPERSEDED.md` is a correct negative control.

**Why it matters.** The packet protocol's request/result/disposition triad and
verdict match are machine-readable chain-of-custody. Prose-only exceptions make
integrity checks branch on oral history.

**What resolves it.** Correct REV-0019's current front-matter verdict while
retaining its original body, and add a retained request/provenance marker for
REV-0023 that accurately records the actual dispatch. Candidate title: **Repair
legacy review packet metadata without rewriting verdict history**.

## Tier outcomes

### Tier 1 — FINDINGS(1)

All 35 physical completed artifacts in the WO-0001..WO-0035 window were
inventoried. Every explicit `tests/...` citation resolves and collects; the full
current suite passes. Bare-filename close-outs were reconciled against collected
tests and fresh gates. Spot mutations killed the WO-0007b projector, WO-0026
reduce-only, and WO-0032 single-mandate properties.

| Targets | Current verdict |
|---|---|
| WO-0001..0006, WO-0007a/b, WO-0008..0015 | VERIFIED — current refs/gates hold; WO-0007b mutation killed |
| WO-0016..0021 (including WO-0019a) | VERIFIED behavior; governance header defect AUD2-F001 |
| WO-0022 | SUPERSEDED — executed review trail retained |
| WO-0024..0028 | VERIFIED behavior; governance header defect AUD2-F001; WO-0026 mutation killed |
| WO-0030..0031 | VERIFIED behavior; governance header defect AUD2-F001 |
| WO-0032..0035 | VERIFIED — current refs/gates hold; WO-0032 observable-property mutation killed |

The historical WO-0021 “full gate green” claim was already honestly corrected
by `WO-0028/fable-done.md:65-67`; it is not re-reported as a new finding.

### Tier 2 — FINDINGS(3)

| Target group | Result |
|---|---|
| ADR-001 | VERIFIED by current pins + fresh fill identity/position probe |
| ADR-002, ADR-003, ADR-008 | Core pins collect/pass; stale REV-0033 labels are AUD2-F003; WO-0113 semantic re-score deferred |
| ADR-004, ADR-005 | VERIFIED by current event/replay and facade/import corpus |
| ADR-006, ADR-007 | Live gates are stronger but written current-state is stale: AUD2-F004 |
| ADR-009 | CURRENT-BLOCKED: Proposed, REV-0022 BLOCK, no implementation on master |
| INV-001..004 | Refs collect/pass; fresh INV-003/004 probe held both stores |
| INV-010..011 | Refs collect/pass |
| INV-020..025 and INV-075 | Refs collect/pass; fresh INV-025 held; INV-075 mutation killed |
| INV-030..038 | Refs collect/pass |
| INV-040..041 | Refs collect/pass |
| INV-050..052 | INV-050 passes; INV-051/052 pin gap is AUD2-F002 |
| INV-060..061 | Fresh dual-store probes held; REV-0033 label drift is AUD2-F003 |
| INV-070..074 | Six import contracts pass; INV-074's bare name resolves to `test_import_boundaries.py:79` |
| INV-076..089 | Refs collect/pass; fresh INV-087/089 held; sampled INV-084/087 pins killed mutations |

### Tier 3 — FINDINGS(3)

| Item | Verdict | Evidence |
|---|---|---|
| WO-0022 | SUPERSEDED | Hygiene note points to executed REV-0023 and later campaigns |
| WO-0029 | STALE | Mixed completed/open umbrella; needs re-cut (AUD2-F005) |
| WO-0102 | CURRENT-BLOCKED | ADR-009/REV-0022 gate still open on master; archive implementation is stranded (AUD2-F007) |
| WO-0103 | CURRENT-BLOCKED | Depends on current-tree WO-0102 and its own human/review gates |
| WO-0104 | CURRENT-BLOCKED | Depends on current-tree WO-0102; producer release remains human-gated |
| W3-README / W3-KICKOFF | STALE | Finished-wave launch artifacts still in queue (AUD2-F006) |
| W4-SEED-NOTES | STALE | Useful seeds mixed with false gate/debt claims (AUD2-F006) |
| `archive/claude-wo-0001-install-checks-2x5ys8` | STALE / STRANDED | 47 commits unique to archive; no signal implementation on master |
| `archive/collab-sol-0001` | SUPERSEDED / RE-LANDED | Original deliverables imported by `9c151eb`; four blobs identical, policy amended |

### Tier 4 — FINDINGS(3)

All 25 `REV-*` directories and all 13 standalone `FINDING-*` files were
mechanically inventoried. Complete triads and the explicit REV-0024 supersession
held. Exceptions are AUD2-F008 (REV-0029/0030 closure), AUD2-F009 (stale OPEN
findings), and AUD2-F010 (legacy packet metadata).

## Deferred and could not verify

- `WO-0106` and `WO-0113`: **DEFERRED — other-seat audit required** (Codex-built).
- Re-scoring Codex's REV-0029 verdicts: **DEFERRED — other-seat audit required**.
  Only mechanical packet existence/closure was checked.
- ADR-010 and INV-090+ semantics: Tier 0, excluded except where a queue or packet
  record supplied a concrete cross-tier mechanical lead.
- The full suite proves every collected test passed; only three representative
  properties received fresh mutation checks. The audit does not claim all 3,873
  tests were independently mutation-proven.
- No Alpaca paper sandbox or real-paper DB was used or needed. Venue behavior and
  Lane-B data characterization remain outside this audit.
- Archive analysis used the clone's `origin/archive/*` tracking refs. Blob/graph
  conclusions are exact for those refs; live remote freshness is not part of the
  semantic verdict.

## Remediation / NEEDS-INPUT batch for the planning seat

1. Authorize normalization + checker hardening for AUD2-F001.
2. Cut the lock-liveness pin WO for AUD2-F002.
3. Authorize nonsemantic safety-doc review-label close-out for AUD2-F003.
4. Cut dated ADR-006/007 ratchet amendments for AUD2-F004.
5. Re-cut WO-0029's verified-open debt only (AUD2-F005).
6. Decide the Lane-H deletion batch for W3 launchers and refresh W4 notes
   (AUD2-F006).
7. Decide reconcile-vs-abandon for the 47-commit Signal Seat archive
   (AUD2-F007); do not treat it as master-complete meanwhile.
8. Record the authoritative REV-0029/0030 and WO-0109 close-out (AUD2-F008).
9. Append dispositions to the nine remediated standalone findings (AUD2-F009).
10. Repair REV-0019/0023 mechanical metadata (AUD2-F010).

## Fable close-out

```yaml
fable:
  task: AUDIT-0002 prior-work findings-only audit
  gate:
    scope: MET
    credentials_absent: MET
    baseline_green: MET
    independent_seat_exclusions: MET
  fix:
    - symptom: initial pytest could not scan the protected Windows temp root
      root_cause: sandbox ACL, not a test or application failure
      action: reran with OS-temp access and cache provider disabled
      result: full suite exit 0; no repo scratch created
    - symptom: first close-scope command named a nonexistent check_scope.py
      root_cause: incorrect checker filename
      action: enumerated the canonical scripts and ran check_work_order_scope.py with the staged file list
      result: SCOPE CHECK PASSED
  done:
    tiers_covered: [1, 2, 3, 4]
    findings: {P0: 0, P1: 10}
    packet_only_scope: VERIFIED
    status: VERIFIED
    meaning: audit executed per charter; repository is not asserted finding-free
  disposition: [RESULT_SUMMARY_KEPT]
```

## Verdict

**ACCEPT-WITH-CHANGES.** No current live-safety P0 was reproduced, so no
immediate stop-the-line escalation is warranted. The ten P1 findings must be
dispositioned before the repository's prior-work ledger, backlog, and review
packets can be treated as a fully trustworthy beta-prep control surface.

Anything not verified is listed above; no remediation was applied in this
packet.
