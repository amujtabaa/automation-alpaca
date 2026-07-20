# R2 consolidation Part A — Codex independent investigation

Date: 2026-07-16
Investigator: Codex independent seat
Branch: `consolidate/r2-canonical`
Work order: `WO-0106`
Compared base: `22617f4ccf28970d553d5cc65cbffdf42ea4b7cd`
Claude R2: `a6ab844a23dfc68d36a7fd8ae6e2b73f7a454f66`
Sol R2: `353ef1cc23b901b10cd394ea63e0683de7eeb6e7`
Overall status: **BLOCKED pending the decisions in §I and a Part B implementation**

This report was produced without reading another consolidation investigator's report,
their report commits, or PR review comments about their findings. Comparison branches
were read only in detached scratch worktrees. No Part B production change was made.

## Executive summary

Neither attempt is safe to land as submitted. The recommended canonical result is a
**bounded synthesis**: use Sol's aggregate, single-source obligation projection as the
semantic kernel, but do not cherry-pick the Sol branch wholesale. Make that projection
strictly implement the charter's ownership equivalence, use it at every order-minting
and release choke point, make SQLite queries symbol/lineage bounded and index-backed,
and retain Claude's injected-clock fix, governance trail, and fresh-eyes regression
pins. This aligns ownership with event truth and repairs pre-R2 drift without preserving
Claude's duplicated write-hook lifecycle or Sol's unbounded scans. [J2, J4]

The spec-derived oracle contains 61 dual-store cases. Claude passes 45 and fails 16;
the failures include three independently reproduced ways to mint a second 100-share
SELL beside a child that may still rest, missing startup repair, session rollover drift,
and a raw-row/event-truth split. Sol passes 57 and fails four: it treats a childless
pre-activation `APPROVED` envelope as a live delegation, and treats
`RECOVERY_NEEDS_REVIEW` as release even though venue exposure may remain. Those two Sol
behaviors are deliberate and documented, so they require human policy decisions rather
than silent test edits. [J2]

Sol's shipped performance gate is also red: on the realistic 10,002-event corpus its
lookup p95 scales 35.47× against a 3× limit, startup scales 42.13× against a 12× limit,
and query plans contain full scans of envelopes, events, and recoveries. One hundred
lookups at the measured p95 consume about 11.1 seconds of the 15-second default poll
cadence. The same corpus on Claude's indexed stored-status read takes one query and
0.073 ms p95, but Claude has no R2 startup repair and therefore cannot be selected for
speed alone. [J4]

Merge order recommendation: PR #8 is already merged. Rebase and independently re-review
PR #7 on current `master`, land it first, then build the canonical R2 in a new stacked PR
from the post-PR7 master. Current master and PR #7 have four textual store conflicts and
substantial semantic overlap; letting R2 validate the final signal/store composition is
safer than making PR #7 reconcile over a newly changed ownership model. [J1, J6]

The three highest-value human decisions are: (1) approve the indexed projection
synthesis rather than either branch; (2) decide whether childless `APPROVED` envelopes
are live owners; and (3) decide whether `needs_review` may free an envelope-backed symbol.
Recommendations and alternatives are in §I. This is the mandatory hard stop before
Part B.

## §A — Topology, inventory, and freeze

### A1. Reconstructed topology

```text
80250e0 pre-consolidation master
├─ PR #8 lineage ... 22617f4 ... 38762a1
│  └─ merged on master as 2aa377a
├─ PR #7 signal-seat lineage -> fc81951 (open)
└─ 22617f4 shared R2 base
   ├─ Claude R2 -> ba1cea7 -> a6ab844
   └─ Sol R2 -> 353ef1c
```

| Status | Observation |
|---|---|
| VERIFIED | Claude and Sol have the exact merge base `22617f4`; base-to-head counts are `0/6` and `0/1`. |
| VERIFIED | Claude changes 25 files, +2,194/-205. Sol changes 26 files, +10,853/-389. |
| VERIFIED | `master=2aa377a`; PR #8 is merged and its former source branch is deleted remotely. The charter's earlier “PR #8 open” topology is stale. |
| VERIFIED | PR #7 remains open at `fc81951`; `master...PR7 = 97/47`. |
| VERIFIED | Freeze refs are immutable and match their recorded targets: master `80250e0`, PR8 base `22617f4`, Claude `ba1cea7`, Sol `353ef1c`. |
| VERIFIED | Git and the GitHub connector exposed the same 13 remote branch names at inventory time. |
| VERIFIED | No third R2 implementation exists in discoverable refs, worktrees, stash, tags, or repo-root bundles. Local `codex/r2-lifecycle-link=006760d` and `codex/rev-0022=93209c2` are ancestors, not competing R2 heads. |
| NEEDS-INPUT | A human-held or unpushed bundle outside the repository cannot be disproved. |

Evidence: [J1].

### A2. Inventory and changed surfaces

Claude is store-only for production (`app/store/{core,memory,sqlite}.py`) and carries the
WO/W3/ledger/REV-0028 governance plane. Sol changes the same store core plus
`app/monitoring.py` and `app/reconciliation.py`, adds large hostile/assurance/performance
suites, and carries no `work/**` delta. Seventeen paths overlap, including all three
store implementation files, ADR-010, INVARIANTS, eleven existing tests, and the
same-named R2 lifecycle test. [J1, J6]

## §B — Conformance oracle and results

### B1. Formal property

For every symbol and every point in an envelope-backed exit's lifetime, exactly one
dedup-blocking owner exists **iff** a non-terminal exit obligation exists: an
`ACTIVE/FROZEN` envelope, a staged handoff not safely preempted, or any child/recovery
whose venue fate remains unresolved. A releasing terminal frees the owner only after
the last obligation becomes terminal. Session close, rollover, restart, reprice,
quarantine, supersession, flatten, kill/resume, and monitoring convergence may create
neither zero owners beside possible exposure nor two independently actionable owners.

The oracle is `tests/r2_conformance_oracle.py`. It deliberately has no default `test_`
prefix while the consolidation branch remains pre-R2; Part B must invoke the exact file
explicitly. It uses only public behavior for assertions. Limited private row mutation is
used to construct pre-R2 and reverse-stale persistence shapes that public R2 ingress is
supposed to repair or interpret. [J2]

### B2. Coverage of the property

| Family | Boundary exercised |
|---|---|
| Binding | unknown/mismatched owner, activation normalization, generic activation, exclusive legacy driver |
| Lifecycle | every releasing terminal, supersession, session close, pre-activation `APPROVED` |
| Exposure | submitting/submitted/partial/cancel-pending/quarantine, masked predecessor, terminal envelope plus live child |
| Consumers | protection dedup, legacy dispatch, flatten, emergency reduce, session close, monitoring convergence |
| Truth | fill-only quantity movement, dedupe, immutable bounds, event truth over stale row, reverse startup repair |
| Treadmill | date rollover, stale claim, below-floor/phantom print, deviation suspect, kill/resume, reprice |

### B3. Differential result

| Attempt | Status | Result | Decisive classes |
|---|---|---:|---|
| Claude `a6ab844` | BLOCKED | 45 passed / 16 failed | local cancel after claim releases owner; terminal-envelope/live-child flatten, close, and legacy dispatch; rollover session drift; no startup repair; raw row overrides event truth; `needs_review` release |
| Sol `353ef1c` | BLOCKED | 57 passed / 4 failed | childless `APPROVED` envelope survives close; `needs_review` releases possible venue exposure |

Claude's most serious failure is a predicate split. Its terminal hook correctly retains
the intent when a `BREACHED` envelope still has a `SUBMITTED` child, but flatten,
session-close sparing, and legacy-dispatch exclusion consult only
`LIVE_ENVELOPE_STATUSES={ACTIVE,FROZEN}`. Both stores then reproduced a second 100-share
SELL beside the first possibly-live child. Relevant lines: memory `962-971`,
`1097-1127`, `1799-1809`, `3278-3294`; SQLite `1846-1869`, `2010-2043`,
`2857-2867`, `4714-4735`. [J2, J3]

Sol's four failures are policy conflicts, not accidental store drift:

- `app/store/core.py:769-770,1046-1053` deliberately makes `APPROVED` delegating.
  ADR-010 and Sol's INV-090 say the same. This contradicts the charter's narrower
  `ACTIVE/FROZEN or possibly-live child` equivalence and the accepted ADR-010
  pre-activation escape rationale.
- `app/store/core.py:1416-1420` deliberately excludes a `needs_review` recovery from
  retention. Existing INV-032 also says only `needs_review` frees the symbol. For an
  envelope child with a broker id, that may admit a replacement beside unresolved
  venue exposure.

Both are NEEDS-INPUT and appear in §I. The oracle must not be edited to adopt either
answer without recorded ratification. [J2]

## §C — Per-attempt characterization and obligations

### C1. Claude: evented terminal propagation

Mechanism: keep the backing intent stored `APPROVED` while owned; at envelope and child
terminal write choke points, write `APPROVED -> EXPIRED`; define live envelopes as
`ACTIVE/FROZEN`; scan every child to avoid the masked-predecessor defect. Activation
validates existence/symbol/status and the legacy driver is blocked while a live
envelope exists. [J3]

| Obligation | Status | Finding |
|---|---|---|
| Current happy-path parity | VERIFIED | Memory and SQLite mirror event ordering and atomic release hooks; focused/full native suites are green. |
| Core ownership equivalence | BLOCKED | Three consumers ignore releasing-terminal lineages with live children and can double-sell. |
| Migration safety | BLOCKED | `initialize()` contains no R2 reprojection; an `ACTIVE` envelope beside an `EXPIRED` owner reopens ownerless and permits a new driver. |
| Event truth | BLOCKED | Child-retention scans raw `Order.status`; a stale `CANCELED` row overrides a projected `SUBMITTED` event state. |
| Session identity | BLOCKED | Staging after date rollover defaults to the new current session rather than the envelope's approved session. |
| Local claim uncertainty | BLOCKED | A local `SUBMITTING -> CANCELED` can release the R2 owner even though a raced broker submission may still succeed. |
| No second stored truth | BLOCKED | Envelope/child obligation is duplicated into stored `SellIntent.status`; the restart and stale-row probes demonstrate persistent divergence. |
| Governance | VERIFIED | Claude carries ADR/INV/W3/WO/ledger/REV-0028 artifacts, but REV-0028 remains awaiting independent review. |

The attempt's own lifecycle suite creates a terminal envelope plus resting child but
does not cross that state with flatten, close, or legacy dispatch, explaining the
green native suite. [J3]

### C2. Sol: aggregate delegation projection

Mechanism: derive ownership from the complete envelope lineage, child events/orders,
claim/recovery state, and legacy direct-order state; use the projection at consumers;
reproject stored compatibility status in both directions during startup. Sol adds broad
memory/SQLite parity, fault-injection, hostile closure, and scaling tests. [J2, J5]

| Obligation | Status | Finding |
|---|---|---|
| Core ownership equivalence | NEEDS-INPUT | Mechanism closes Claude's consumer gaps but uses broader `APPROVED` and narrower `needs_review` semantics than the charter. |
| Parity | VERIFIED | The 274 focused cases and the 61-case oracle show symmetric memory/SQLite behavior; full native suite is green. |
| Migration safety | VERIFIED | Both drift directions are repaired by startup reprojection in the oracle. |
| Event truth | VERIFIED | Reverse-stale order-column and newest-owner adversarial cases pass. |
| Performance | BLOCKED | Global scans and repeated lineage reconstruction fail the shipped scale budget. |
| No second stored truth | NEEDS-INPUT | Reads prefer projection, but startup writes derived compatibility status back into `SellIntent.status`; architecture must state whether that field is cache, projection, or authority. |
| Fixture fidelity | UNVERIFIED | Several refixtured tests mutate private `activated_at` row fields and bypass event/time consistency. |
| Governance | BLOCKED | No planning-plane closeout, ledger entry, W3 update, or independent R2 packet ships with the code. |

### C3. Proof-sketch conclusion

A write-hook proof is not closed unless every future consumer shares the same exact
outstanding-obligation predicate; Claude demonstrates how a correct release hook can be
undone elsewhere. A projection proof is structurally stronger because activation,
release, dedup, flatten, close, and dispatch consume one relation. It is still only
sound if (a) its state set is ratified, (b) all facts are event-authoritative, (c) every
consumer calls it, and (d) its query plan is bounded. Sol discharges (b) and most of
(c), but not (a) or (d). [J2-J4]

## §D — Performance

The measured budget follows the shipped Sol gate: realistic-over-small lookup p95
`<=3x`, no unrelated full scan, query count independent of unrelated scale, startup
elapsed/select growth for 10× facts `<=12x`, and standalone projection peak `<=2 MiB`.
The operational envelope is the 15-second default poll cadence. [J4]

| Metric | Claude on same seeded corpus | Sol shipped gate |
|---|---:|---:|
| realistic events | 10,002 | 10,002 |
| lookup p95 | 0.0729 ms | 111.2117 ms |
| lookup small p95 | 0.1291 ms | 3.1355 ms |
| lookup ratio | 0.565× | 35.47× — BLOCKED |
| SELECTs per lookup | 1 | 42 |
| unrelated full scans | none | envelopes, events, recoveries — BLOCKED |
| realistic startup | 430.8 ms / 7 SELECTs | 5,176.4 ms / 3,359 SELECTs |
| startup ratio | 19.78× — BLOCKED | 42.13× — BLOCKED |
| projection peak | not applicable; no projector | 312,152 bytes |

Claude's fast lookup is not a correctness win: it reads the stored status that the
oracle proves can be wrong, and its absence of R2 startup repair explains the much
smaller startup work. The canonical implementation must retain projection semantics
while achieving an indexed lookup near Claude's query shape. [J2, J4]

Part B performance design recommendation:

1. Add symbol/lineage-bounded indexes for envelope state, envelope-action events, and
   recovery lookup; eliminate global envelope/event/recovery scans.
2. Query only the target symbol and reachable lineage/order ids.
3. If a derived in-memory cache is needed, make it non-authoritative, update it at the
   single writer, rebuild/verify it from event truth on startup, and never persist it as
   an independent lifecycle truth.
4. Keep the shipped gate and add a 100-symbol monitoring-path p95 assertion. Any index
   or schema change is STOP-FOR-HUMAN.

## §E — Cross-verification and adversarial review

### E1. Cross-run matrix

| Source suite -> target | Status | Result and adjudication |
|---|---|---|
| Claude lifecycle -> Sol, exact | UNVERIFIED | 4/46 passed before adaptation; most failures were invalid fixtures because Sol requires owner session and quantity agreement. |
| Claude lifecycle -> Sol, minimal fixture adaptation | VERIFIED | 28/46 passed. The remaining 18 are exception taxonomy, audit reason strings, earlier safe rejection, or missing diagnostic payload fields—not contrary ownership behavior. |
| Claude masked-predecessor C7/C8 -> Sol | VERIFIED | 4/4 passed. Live-child flatten behavior also deferred correctly; only the audit reason string differed. |
| Sol portable parity-adversarial -> Claude | BLOCKED | 3/14 passed, 11 failed; exposed terminal-sibling activation/staging, flat-position manager loss, reverse-stale event truth, malformed-owner mutation, and memory newest-selection drift. |
| Sol lifecycle/assurance -> Claude, exact collection | BLOCKED | Cannot collect because Claude has no `project_envelope_obligation` / `EnvelopeObligationProjection`. |
| Sol hostile closure -> Claude, exact collection | BLOCKED | Cannot collect because Claude lacks Sol-private monitoring/recovery helpers. Neutral public oracle and the portable parity module provide mechanism-independent reproductions. |
| Sol performance corpus -> Claude | VERIFIED | Adapted only the absent standalone projection measurement; public runtime/startup calls and seeded dataset were unchanged. Results are in §D. |

No cross-suite assertion was weakened in a pushed artifact. Adapted files remained
untracked inside scratch worktrees. [J3, J4]

### E2. Disclosed Claude probes against Sol

| Probe | Status | Sol result |
|---|---|---|
| Option A+ / keep intent approved while owned | NEEDS-INPUT | Sol represents the delegation through projection and compatibility status, but also treats pre-activation `APPROVED` as owned; §I-2 decides the boundary. |
| R6 per-tick recovery redrive | VERIFIED | Sol's monitoring/recovery integration and hostile suites cover claim occurrence, open recovery, late resolution, and sibling-isolated convergence. |
| Monitoring newest-wins cancel convergence | VERIFIED | Neutral oracle converges a staged replacement plus live predecessor across repeated ticks; Claude C7/C8 pins pass on Sol. |
| HALTED emergency reduce with resting child | VERIFIED | Both stores defer to the existing child and mint no second order (`.. [100%]` on each attempt). |

### E3. Native gates

| Attempt | Status | Evidence |
|---|---|---|
| Claude | VERIFIED | ruff, ruff-format, mypy, import-linter, focused tests, and full pytest exit 0; full run occurred after the known tape anchor. |
| Claude coverage invocation | BLOCKED | 94.92% measured, but one Streamlit AppTest timed out at 3 seconds; isolated rerun passed. Invocation itself is not green. |
| Sol | VERIFIED | ruff lint, mypy, import-linter, 274 focused tests, and 2,980-test full suite exit 0 (5 skipped, 1 expected xfail). |
| Sol format | BLOCKED | Two files would reformat; characterized as inherited from the shared base, but the candidate gate remains red. |
| Sol coverage invocation | UNVERIFIED | 93.57% measured; the same Streamlit test timed out, then passed three isolated reruns. |

Evidence: [J5].

## §F — Mechanism decision

| Criterion | Claude evented propagation | Sol projection |
|---|---|---|
| Correctness closure | BLOCKED by predicate splits | NEEDS-INPUT on two explicit semantics |
| Memory/SQLite parity | current paths mirror, migration absent | broad parity and startup repair |
| Hot-path performance | excellent but reads stale-able stored truth | BLOCKED by global scans |
| Blast radius | smaller | much larger, including monitoring/reconciliation |
| Pre-R2 migration | BLOCKED | VERIFIED |
| Single-source/event-truth alignment | weak: stored status plus write hooks | strong if compatibility status is demoted from authority |
| Maintainability | easy locally, hard global proof | central proof surface, must be query-bounded |

**Recommendation: select an indexed Sol-style projection synthesis. Do not select or
cherry-pick either branch wholesale.** [J2-J4]

Required graft/repair list:

- From Sol: aggregate lineage projection, all consumer integrations, two-way startup
  repair, memory/SQLite differential assurance, hostile closure, recovery occurrence
  logic, and scaling harness.
- From Claude: injected-clock activation fixture/fix at `a6ab844`, governance and
  REV-0028 provenance as historical attempt evidence, masked-predecessor fresh-eyes
  pins, and concise activation/exclusive-driver audit expectations.
- Synthesis: strict ratified state semantics; event-projected child status; the same
  predicate for activation, stage, dedup, legacy dispatch, flatten, close, release, and
  restart; immutable approved session identity; bounded/indexed SQLite reads; one true
  ADR/INV narrative.

## §G — Deconfliction

### G1. Namespace and renumber registry

| Identifier/path | Status | Canonical resolution |
|---|---|---|
| ADR-009 | VERIFIED | Historical execution-envelope ADR was renamed to ADR-010; ADR-009 now belongs to signal-seat. Do not merge the old `collab/sol-0001` filename. |
| WO-0016 / WO-0100 | VERIFIED | Historical ADR-007/mypy tail was renumbered to WO-0100; current WO-0016 belongs to ExecutionEnvelope. |
| REV-0022 | VERIFIED | Formal result is canonical; the constructed PR5 record is explicitly superseded. The collab commit-message occurrence is not a packet claim. |
| REV-0023 | VERIFIED | PR7's result blob is byte-identical inherited evidence, not a second claim. |
| REV-0024..0027 | VERIFIED | Signal-seat owns these packets; REV-0026 is withdrawn. |
| Claude R2 REV-0024 -> REV-0028 | VERIFIED | Renumber is complete; no stale R2 REV-0024 reference remains. REV-0028 is attempt evidence, not the final consolidated review. |
| INV-090 | NEEDS-INPUT | Both attempts claim it with incompatible lifecycle definitions. Part B must write one synthesized statement after §I ratification. |
| ADR-010 §8 | NEEDS-INPUT | Base, Claude, and Sol have different blobs. Part B must write one amendment history that records the selected mechanism and ratification. |
| `test_wo0036_r2_lifecycle_link.py` | NEEDS-INPUT | Same filename, different suites. Merge behavior coverage into one canonical file; retain hostile/assurance modules with unambiguous names. |
| Final consolidated REV | NEEDS-INPUT | At inventory time REV-0029 is next free; re-scan every ref immediately before claiming it. |

Evidence: [J6].

### G2. Four-plane drift

| Plane | Status | Finding / merged-text plan |
|---|---|---|
| Code | VERIFIED | Claude changes store only; Sol also changes monitoring/reconciliation. Canonical code uses only the narrow Sol integration needed by the shared projector and convergence. |
| Planning | BLOCKED | WO-0036 is queue/DRAFT on the old feature tip, active/in-progress on base/master/Sol, and review on Claude. Sol ships no work-state delta. Consolidated closeout must be one post-ratification record. |
| Documentation | BLOCKED | Claude has the fuller governance story; Sol has competing ADR/INV text only. Spine and PKL are unchanged on all tips, so Part B must explicitly update or record no-impact. |
| Tests | NEEDS-INPUT | Both own the same lifecycle filename and use different fixtures. Merge public behavior; eliminate private clock-row mutation in favor of injected time. |

`docs/INVARIANTS.md` still cites nonexistent
`tests/test_phase7_routes.py::test_flatten_works_under_kill_switch`; the actual test is
`test_flatten_denied_under_kill_switch_then_emergency_reduce_works`. Correct this in
Part B documentation. The expected `rules/ai-os-rules.yaml` file is absent, so its
disposition vocabulary could not be independently checked; current templates and
existing ledger conventions were used. [J6]

### G3. Architecture and merge order

| Status | Finding |
|---|---|
| VERIFIED | `lint-imports` keeps all six contracts on each attempt; Sol's new monitoring/reconciliation imports remain store-core facing and do not introduce broker/UI inversion. |
| VERIFIED | `check_ledger`, `check_work_order_disposition`, and `check_pkl` pass on master, Claude, and Sol tips. |
| VERIFIED | WO-0036 scope permits Sol's monitoring/reconciliation paths. |
| VERIFIED | Current master + PR7 has textual conflicts in `app/models.py`, `app/store/base.py`, `app/store/core.py`, and `app/store/sqlite.py`; `app/store/memory.py` also overlaps semantically. |
| VERIFIED | Current master conflicts with Claude R2 in three test fixtures and with Sol R2 in three test files. |
| NEEDS-INPUT | Land/review PR7 first, then base R2 on post-PR7 master. Reversing the order makes PR7 reconcile over a safety-critical new ownership model. |

Evidence: [J6].

## §H — Consolidation program

Part B remains inactive until §I is recorded in-repo.

1. **Ratification — STOP-FOR-HUMAN.** Record the selected answers from §I in WO-0106
   or its approved Part B successor.
2. **Lineage convergence — STOP-FOR-HUMAN.** Rebase PR7 on `2aa377a`, resolve the four
   store conflicts, run its independent review, and let the human merge. Refresh the
   canonical R2 base from post-PR7 master; preserve this report/oracle as provenance.
3. **RED gate.** Run `tests/r2_conformance_oracle.py` unchanged and demonstrate the
   ratified expected failures before implementation. An oracle change is a spec change
   and returns to the human.
4. **Canonical semantic kernel.** In `app/store/core.py`, define one projection over
   live envelope, terminal lineage with possible child/recovery, staged intent, and
   direct legacy obligation. Apply the ratified `APPROVED` and `needs_review` rules.
5. **Dual-store integration.** In memory and SQLite, use that projection for every
   activation/stage/release/dedup/dispatch/flatten/close/restart choke point. Project
   order status from events; bind children to the envelope's approved session. Add
   two-way pre-R2 repair without making stored compatibility status authoritative.
6. **Performance/schema — STOP-FOR-HUMAN.** Add the minimum indexes/bounded queries
   needed to pass §D. A schema/index migration is human-gated even when data-preserving.
7. **Monitoring/reconciliation.** Port only the Sol recovery redrive, terminal-fact,
   and cancel-convergence changes required by the projector. Defer unrelated rework.
8. **Tests.** Merge both lifecycle suites, preserve Sol hostile/assurance/parity and
   Claude masked-predecessor/clock pins, replace private clock-row fixture mutation,
   and add the 61-case oracle plus scale gate to explicit acceptance commands.
9. **Four-plane closeout.** Write one ADR-010 §8/history, one INV-090, corrected test
   pins, WO-0036/W3/ledger/PKL disposition, and one consolidated review request.
10. **Acceptance.** Run the oracle, both hostile suites, scale gate, ruff, ruff-format,
    mypy, import-linter, full pytest, coverage floor, hygiene/scope checks, and a fresh
    adversarial class-closure pass at a UTC time after the tape anchor.
11. **Independent review — STOP-FOR-HUMAN.** Claim the next free REV only after a full
    ref scan. A different model must return ACCEPT or ACCEPT-WITH-CHANGES under the repo
    review contract.
12. **New stacked PR — STOP-FOR-HUMAN.** Open from post-PR7 master. The human merges.

### H1. Acceptance commands

```powershell
ruff check .
ruff format --check .
mypy app/
lint-imports
python -m pytest -q tests/r2_conformance_oracle.py --basetemp=.pytest-tmp/r2-oracle
python -m pytest -q <claude-and-sol-r2-suites> --basetemp=.pytest-tmp/r2-hostile
python -m tests.performance.r2_scaling_gate
python -m pytest -q --basetemp=.pytest-tmp/full
python -m pytest -q --cov=app --cov-branch --cov-fail-under=93 --basetemp=.pytest-tmp/coverage
python .ai-os/scripts/check_ledger.py
python .ai-os/scripts/check_work_order_disposition.py
python .ai-os/scripts/check_pkl.py
git diff --name-only <base>...HEAD | python .ai-os/scripts/check_work_order_scope.py <active-work-order>
```

### H2. Risk and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Projection semantics admit zero/two owners | unchanged oracle + hostile cross-suite | revert stacked R2 PR; freeze refs remain available |
| SQLite tail latency/starvation | scale/query-plan gate before review | revert index/query commit; no broker/UI change |
| Pre-R2 migration corrupts owner status | copy-on-open fixture, transaction rollback, replay parity | restore pre-migration DB backup and revert migration commit |
| Memory/SQLite drift | stepwise normalized event/state parity | revert last store integration commit |
| PR7 semantic overwrite | land/review PR7 first, build R2 after | reset stacked PR base; never rewrite shared PR |
| Governance collision | re-scan all refs before claiming ids | renumber unpublished packet before review |

Rollback anchors: `origin/freeze/20260715-master-preconsolidation=80250e0`,
`...-pr8-head=22617f4`, `...-r2-claude=ba1cea7`, and
`...-r2-sol=353ef1c`. [J1]

## §I — Batched human decisions

Please ratify each item explicitly; silence does not activate Part B.

1. **Canonical mechanism**
   - A: indexed single-source projection synthesis.
   - B: repair Claude's evented write-hook mechanism.
   - **Recommendation: A.** It centralizes the proof, closes migration and consumer
     predicate splits, and can recover performance with bounded queries. [J2-J4]

2. **Does a childless pre-activation `APPROVED` envelope retain the owner?**
   - A: no; only `ACTIVE/FROZEN`, staged handoff, or possible venue exposure retains.
   - B: yes; Sol's broader delegation starts at `APPROVED`.
   - **Recommendation: A.** It matches the charter and ADR-010's pre-activation escape
     rationale and avoids an indefinitely parked symbol. [J2]

3. **Does `RECOVERY_NEEDS_REVIEW` free an envelope-backed symbol?**
   - A: retain until authoritative venue terminal/absence, or an explicit human
     terminal attestation is recorded.
   - B: free immediately, preserving legacy INV-032 behavior.
   - **Recommendation: A.** “Needs review” is not proof that a broker SELL is absent;
     protection availability must not create double exposure. Scope the changed rule
     to envelope-backed/possibly-live orders if legacy behavior must remain. [J2]

4. **Merge order**
   - A: rebase/review/land PR7, then build R2 from post-PR7 master.
   - B: land R2 first and make PR7 reconcile over it.
   - **Recommendation: A.** The final R2 gate should validate the final store/signal
     composition. [J1, J6]

5. **PR topology**
   - A: new stacked R2 PR.
   - B: attempt to fold into PR8.
   - **Recommendation: A.** PR8 is already merged; folding is no longer possible.
     [J1]

6. **Sol monitoring/reconciliation scope**
   - A: port only projector-required recovery and convergence changes with tests.
   - B: land the full Sol monitoring/reconciliation rewrite.
   - **Recommendation: A.** It preserves the needed safety behavior while reducing
     review surface and PR7 collision risk. [J1, J3]

7. **Performance implementation**
   - A: data-preserving indexes + bounded queries, with an optional non-authoritative
     in-memory replay cache.
   - B: accept global projection scans.
   - **Recommendation: A.** Sol's own gate rejects B by a wide margin. Index/schema
     work remains STOP-FOR-HUMAN. [J4]

8. **Namespace package**
   - A: synthesize one ADR-010 §8 and INV-090; merge the colliding lifecycle test;
     retain REV-0028 as Claude-attempt provenance; claim the next free consolidated
     REV after re-scan (currently REV-0029).
   - B: select one attempt's identifiers/text wholesale.
   - **Recommendation: A.** Neither attempt's normative text matches the recommended
     synthesis. [J6]

## §J — Evidence appendix

### J1. Environment, refs, and live topology

```text
Python 3.12.13
ruff 0.15.20
mypy 2.2.0
import-linter 2.13
pytest 9.1.1

origin/master                                    2aa377a35d35e85be120cf90cdb6c5bd85a8d546
origin/claude/wo-0001-install-checks-2x5ys8     fc819517be64b10ecf831a9a6abd4fe6f9100e2f
shared base                                      22617f4ccf28970d553d5cc65cbffdf42ea4b7cd
Claude R2                                        a6ab844a23dfc68d36a7fd8ae6e2b73f7a454f66
Sol R2                                           353ef1cc23b901b10cd394ea63e0683de7eeb6e7

git rev-list --left-right --count 22617f4...Claude   0  6
git rev-list --left-right --count 22617f4...Sol      0  1
git rev-list --left-right --count master...PR7        97 47
git merge-base 22617f4 Claude                       22617f4...
git merge-base 22617f4 Sol                          22617f4...

git diff --shortstat 22617f4 Claude
25 files changed, 2194 insertions(+), 205 deletions(-)
git diff --shortstat 22617f4 Sol
26 files changed, 10853 insertions(+), 389 deletions(-)

origin/freeze/20260715-master-preconsolidation 80250e0...
origin/freeze/20260715-pr8-head                22617f4...
origin/freeze/20260715-r2-claude               ba1cea7...
origin/freeze/20260715-r2-sol                  353ef1c...
```

GitHub connector inventory at 2026-07-16:

```text
PR #8: merged 2026-07-16T10:40:55Z; merge commit 2aa377a
PR #7: open; head fc81951; base master
13 connector branches == 13 non-symbolic origin branches
```

### J2. Neutral oracle

Commands, from detached candidate worktrees:

```powershell
python -m pytest -q tests/r2_conformance_oracle.py --basetemp=<unique-local-dir>
```

Claude decisive summary:

```text
45 passed, 16 failed
failed classes (each memory + SQLite):
- local SUBMITTING cancel releases owner
- terminal envelope + live child: flatten, session close, legacy dispatch
- rollover child session
- RECOVERY_NEEDS_REVIEW retention
- startup repair both directions
- event truth over reverse-stale raw order status
```

Direct Claude consumer probes:

```text
memory terminal_env breached child submitted flatten created deferred False orders_delta 1 old_intent expired
sqlite terminal_env breached child submitted flatten created deferred False orders_delta 1 old_intent expired
memory ... child submitted intent_after_close expired fresh True spared 0
sqlite ... child submitted intent_after_close expired fresh True spared 0
memory ... resting_child submitted legacy_second created 100 intent ordered
sqlite ... resting_child submitted legacy_second created 100 intent ordered
```

Sol decisive summary:

```text
57 passed, 4 failed
failed classes (each memory + SQLite):
- pre-activation APPROVED envelope survives session close
- RECOVERY_NEEDS_REVIEW releases possible exposure
```

Sol public APPROVED repro:

```text
memory {'envelope': 'approved', 'action_children': 0, 'active_owner': True, 'owner_after_close': 'approved'}
sqlite {'envelope': 'approved', 'action_children': 0, 'active_owner': True, 'owner_after_close': 'approved'}
```

HALTED emergency-reduce probe on each attempt:

```text
.. [100%]
.. [100%]
```

### J3. Cross-verification

```text
Claude suite on Sol, exact:                 4 passed / 42 failed (fixture incompatibility)
Claude suite on Sol, fixture adapted:      28 passed / 18 failed
Claude C7+C8 masked predecessor on Sol:     4 passed
Sol parity-adversarial exact on Claude:     3 passed / 11 failed
Sol lifecycle+assurance on Claude:          collection BLOCKED (projection symbols absent)
Sol hostile closure on Claude:              collection BLOCKED (_record_recovery_terminal_fact absent)
```

Representative exact collection errors:

```text
ImportError: cannot import name 'project_envelope_obligation' from 'app.store.core'
ImportError: cannot import name 'EnvelopeObligationProjection' from 'app.store.core'
ImportError: cannot import name '_record_recovery_terminal_fact' from 'app.monitoring'
```

### J4. Performance

Sol shipped command:

```powershell
python -m tests.performance.r2_scaling_gate
```

Decisive output:

```json
{
  "realistic": {
    "events": 10002,
    "runtime_p95_ms": 111.2117,
    "selects_per_call": 42,
    "startup_elapsed_ms": 5176.4394,
    "startup_selects": 3359,
    "unrelated_full_scans": ["execution_envelopes", "execution_events", "submit_recoveries"]
  },
  "ratios": {
    "runtime_p95_large_over_small": 35.4686,
    "startup_elapsed_large_over_small": 42.1349,
    "startup_select_large_over_small": 8.6350
  },
  "passed": false
}
```

Claude adapted same corpus/public calls:

```json
{
  "realistic": {
    "events": 10002,
    "runtime_p95_ms": 0.0729,
    "selects_per_call": 1,
    "startup_elapsed_ms": 430.7934,
    "startup_selects": 7,
    "unrelated_full_scans": []
  },
  "ratios": {
    "runtime_p95_large_over_small": 0.5647,
    "startup_elapsed_large_over_small": 19.7792,
    "startup_select_large_over_small": 1.0
  },
  "passed": false
}
```

### J5. Native and coverage gates

Claude `a6ab844`:

```text
ruff check .                         All checks passed
ruff format --check .                230 files already formatted
mypy app/                            Success: no issues found in 64 source files
lint-imports                         6 kept, 0 broken
focused R2/envelope suites           exit 0
pytest -q                            exit 0 in 272.6s
coverage                             94.92%; invocation exit 1 on one 3s Streamlit timeout
isolated timed-out test              passed
```

Sol `353ef1c`:

```text
ruff check .                         All checks passed
ruff format --check .                2 inherited files would reformat
mypy app/                            Success
lint-imports                         6 kept, 0 broken
four focused R2 suites               274 passed
pytest -q                            2,980 collected; exit 0; 5 skipped; 1 xfail
coverage                             93.57%; invocation exit 1 on same 3s Streamlit timeout
isolated timed-out test              3/3 passed
```

The current host `python` was 3.14.5 and was not used for authoritative gates. All
reported gates used the clean Python 3.12.13 virtual environment with exact constraints.

### J6. Deconfliction and hygiene commands

```text
git for-each-ref; git merge-base; git rev-list --left-right --count
git diff --name-status/--stat; git ls-tree; scoped git grep
git merge-tree master PR7
git merge-tree master Claude-R2
git merge-tree master Sol-R2
python scripts/check_ledger.py
python scripts/check_work_order_disposition.py
python scripts/check_pkl.py
python scripts/check_work_order_scope.py <WO-0036> <changed-file-list>
lint-imports
```

Decisive outputs:

```text
ledger/disposition/PKL: exit 0 on master, Claude, Sol
WO scope: exit 0 on Claude and Sol diffs
import contracts: 6 kept, 0 broken on both attempts
master+PR7 textual conflicts: app/models.py, app/store/base.py,
  app/store/core.py, app/store/sqlite.py
master+Claude textual conflicts: three test fixtures
master+Sol textual conflicts: three test files
```

### J7. Verification limits

| Status | Limit |
|---|---|
| NEEDS-INPUT | External/unpushed human artifacts are outside Git/GitHub inventory. |
| BLOCKED | Neither attempt passes the complete oracle + performance + governance gate. |
| BLOCKED | The coverage-gated command is not green on either attempt despite percentages above 93%; the common timeout did not reproduce in isolation. |
| UNVERIFIED | No Part B consolidated candidate exists, so its full gate, review verdict, and merge-tree cannot yet be verified. |
| VERIFIED | Part A stopped without production R2 implementation, PR mutation, or human-gated schema/order-path change. |

## Part A hard stop

The report and oracle are the complete Codex Part A output. Part B is not authorized
until the human records §I ratification in-repo.
