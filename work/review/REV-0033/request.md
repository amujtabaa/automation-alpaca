---
type: Review Request
rev_id: REV-0033
title: WO-0113 — root-cause closure, accepted-submit ownership, event truth, and merge-readiness review
status: AWAITING_REVIEW
targets: [WO-0113]
human_gated_surfaces:
  - order submission, claim, accepted-ack ownership, cancel, and replace
  - candidate dispatch and exit preemption
  - manual flatten, emergency-reduce capability, and protection exit
  - execution-envelope stage, fill attribution, cleanup, and terminal ownership
  - recovery ownership, reconciliation gating, event-log truth, and overfill quarantine
review_base_sha: 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab
head_sha: "9a7af3b08a2d050e324a862d59548ff2da747c48"
commit_range: 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48
branch: consolidate/r2-canonical
pr: 9
pr_base_branch: master
pr_base_sha_at_freeze: "2aa377a35d35e85be120cf90cdb6c5bd85a8d546"
merge_base_at_freeze: "2aa377a35d35e85be120cf90cdb6c5bd85a8d546"
created: 2026-07-19
---

# REV-0033 — independent review of WO-0113

## Context and safety contract

This is an internal correctness review of an Alpaca **paper-trading simulator**. No live trading,
real funds, credentials, authentication, or new network surface is in scope.

The always-on rules remain:

- paper only;
- FastAPI/backend store is source of truth;
- Streamlit never calls Alpaca and owns no execution state;
- submitted is not filled;
- only canonical fill facts change position quantity;
- kill/`HALTED` blocks new intent except the explicit audited emergency-reduce capability;
- one single-writer engine owns execution decisions.

The operator authorized implementation on `consolidate/r2-canonical`, but did **not** authorize a
merge. Do not merge or push fixes.

## Reviewer role — spec first, no inherited trust

You are the independent review seat, not the implementer. Re-derive behavior from the frozen range.
Do not trust the implementer's rationale, counts, in-process agents, automated review, or green
claims. Use this authority order:

1. `CLAUDE.md` safety core.
2. Accepted ADRs and `docs/INVARIANTS.md`.
3. Final WO-0113 and its operator-ratified decisions.
4. Source and tests as evidence of what happens.
5. Implementer commentary only as navigation.

If code/tests contradict an accepted ADR or invariant, the code is defective. Do not reinterpret
the contract to match it.

Create only `work/review/REV-0033/result.md`. Do not edit this request and do not create the
disposition. Each finding must include `file:line`, a concrete failing sequence, why it matters,
and what resolves it. End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, plus anything not
verified.

## Frozen review range

```powershell
git rev-parse 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab
git rev-parse 9a7af3b08a2d050e324a862d59548ff2da747c48
git diff --stat 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48
git diff --name-status 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48
git diff --check 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48
git diff 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48
```

Review the entire range, not only the final commit. Frozen range size: **86 paths, 21,655
insertions, 1,321 deletions**.

## Changed-file and hazard summary

Production changes span:

- broker contract/adapters: `app/broker/adapter.py`, `alpaca_paper.py`, `mock.py`, `sim.py`;
- orchestration: `app/monitoring.py`, `app/reconciliation.py`, `app/facade/store_backed.py`;
- shared policy/models/projectors: `app/policy.py`, `app/models.py`,
  `app/events/projectors.py`, `app/config.py`;
- store contract/planners/twins: `app/store/base.py`, `core.py`, `memory.py`, `sqlite.py`.

Authoritative documentation changes include `docs/INVARIANTS.md`, ADR-001/002/003/008/010,
operator/review/migration documentation, and PKL testing/review/migration/safety pages.

Primary hazard classes:

1. REV-0031/0032 remediation: exit epoch, safe local cancel, late-fill cleanup, emergency
   capability, and append-only attribution repair.
2. Accepted-submit producer completeness: ordinary submit, stale redrive, direct SELL, envelope
   submit, and envelope replace must retain durable ownership after venue acceptance.
3. Exact ownership identity: canonical IDs, exact local/broker pairs, multiple distinct accepted
   legs, and cross-representation broker-id exclusivity.
4. Managed venue correlation: persisted rendered scope must authenticate submit/replace ACKs,
   direct status, targeted lookup, and mass reports across restart/session boundaries.
5. Fill/quarantine truth and consumer completeness: broker-authoritative overfill is recorded and
   explicitly quarantined even when position remains positive; LOCAL/SYNTHETIC excess rejects;
   changed source-fill economics conflict. One lock-held `FILL` + explicit `QUARANTINED`
   projection must feed public listing, candidate-origin BUY order mint, and final BUY submission
   claim in both stores and after SQLite restart.
6. Monitoring/reconciliation fail-closed behavior: driver state, query budget, inferred fills,
   repair checkpoints, poison, cancellation, and restart.
7. Memory/SQLite decision-structure parity and bounded steady-state repair.

## Final automated-review finding already remediated

Automated review of `5ae2c75c1c4700364cf2c7337c9d05c876479b19` confirmed one P1. SQLite's
autonomous BUY order-mint and final submission-claim gates independently queried only `FILL` facts
before invoking the shared quarantine projector. A positive-position order overfill can be
represented by an explicit `QUARANTINED` fact without a negative position fold, so SQLite's public
quarantine list and memory blocked the symbol while those two SQLite gates still permitted risk.

Commit `9a7af3b08a2d050e324a862d59548ff2da747c48` routes public listing,
candidate-origin BUY order mint, and final BUY claim through one lock-held projection in each store;
SQLite selects both `FILL` and `QUARANTINED`, including after reopen. Red-first evidence was
**2 failed / 2 passed**, with only SQLite unsafe. Restored dual-store/restart evidence is **5/5**.
Independent admission and claim mutations each failed only their SQLite node; reducing the shared
reader to FILL-only failed all **3** SQLite list/gate/restart consumers.

GitHub Actions run **#482** passed on the exact SHA for Python 3.11 and 3.12. The final automated
review response, comment `5018668794`, explicitly reviewed `9a7af3b08a` and reported no major
issues. Treat both as evidence to verify, not independent certification for REV-0033.

## Operator-ratified decisions

| Decision | Ratification | Required semantics |
|---|---|---|
| CREATED BUY targeting | RATIFIED YES | Stand down every recovery-free, event-projected `CREATED` BUY regardless of cached fill progress; broker id, open recovery, or accepted-submit fallback prevents local cancel. |
| Protection deferral | RATIFIED YES | Venue-uncertain BUY returns audited `None`, creates no SELL artifact, and replans later. |
| Append-only attribution | RATIFIED YES | One globally deduped, non-position-folding marker may apply one immutable canonical fill to one uniquely validated envelope; never rewrite or double-fold the fill. |
| Emergency capability | RATIFIED YES | Reuse one fully revalidated symbol/session capability; only the explicit emergency path consumes it; ordinary flatten remains denied while Halted. |
| Accepted-submit fallback | RATIFIED YES | If normal state and recovery ownership both fail after acceptance, append exact durable `UNKNOWN_RECONCILE_REQUIRED` truth that blocks unsafe work until deterministic repair. |

Verify implementation stays within these semantics; ratification is not evidence that it does.

## Added or amended invariants — required fresh probes

Each row requires a **new reviewer scenario**, not merely a rerun of the authored pin. Record the
actual harness and outcome in `result.md`.

| Invariant | Fresh independent probe |
|---|---|
| INV-002 | Hold 200 AAPL shares and retain a pre-existing candidate-origin BUY in `CREATED`. Record a broker-authoritative 75-share fill against a 50-share SELL order, leaving position positive at 125 but requiring explicit order-overfill quarantine. On both stores require raw `FILL`, one durable `QUARANTINED`, public quarantine listing, refusal of a newly approved candidate's BUY mint, and refusal of the pre-existing BUY's final claim. Close/reopen SQLite and repeat all three consumers. Run the excess as LOCAL/SYNTHETIC and require zero mutation. |
| INV-003 | Persist one fill, reopen SQLite, replay the same source id exactly, then reuse it with only price changed. Require one fill/FILL, unchanged position/order/envelope, and durable conflict rather than duplicate success. |
| INV-004 | Give one order broker-authoritative cumulative fills above immutable quantity, including observations through two accepted venue identities. Require raw sum and position to retain full venue truth, `Order.filled_quantity` to cap, and later delta calculation not to report excess again. |
| INV-021 | Mint a BUY within limit, then insert accepted-submit/recovery exposure after mint but before final claim. Require lock-held final claim to recompute exposure and refuse without entering `SUBMITTING`; prove an order carrying its own broker/fallback identity cannot reclaim itself. |
| INV-022 | On envelope replace acceptance, fail `SUBMITTED`, ordinary acceptance audit, and recovery ownership in sequence, then restart immediately. Require exact fallback ownership, no later venue call, and deterministic repair. |
| INV-023 | Use a stale `SUBMITTING` protective MARKET order outside regular hours with no usable price. Cross restart while repeatedly unpriceable and require durable capped attempts, zero venue calls, and eventual needs-review ownership rather than infinite deferral. |
| INV-060 | Create a Halted-session emergency capability, prove ordinary flatten cannot consume it, then roll store session during the emergency facade's broker await. Require no cross-session intent/order/resolution and no authority downgrade. |
| INV-076 | Append two previously unattributed fills for one envelope. Repair the first, poison the second marker/fill reference or remaining chain, restart, and require each canonical fill to fold position once, only the valid prefix to affect envelope, and checkpoint not to pass poison. |
| INV-081 | Open executable exit, attempt a newly admitted candidate and dispatch an already-approved candidate, fill exit, then retry both. Require refusal/expiry to remain terminal and position not to regrow; only a genuinely new post-convergence candidate may admit. |
| INV-091 | Represent two distinct broker acceptances for one local order across order/recovery/fallback forms, restart SQLite, resolve independently, and require exact-pair coalescing, additive distinct-leg exposure, one-time fill allocation, and cross-local collision rejection. |
| INV-092 | Construct event-projected `CREATED` with stale raw `SUBMITTING` and attach an accepted fallback. Exercise direct cancel, terminal cleanup, and session close; each retains until resolution, after which common local-cancel proof may cancel once. |
| INV-093 | Cancel candidate dispatch after approval while guarded cleanup also raises. Require original `CancelledError`, visible stranded approval, then fault removal and retry producing at most one linked order. |
| INV-094 | Hide an accepted direct SELL behind locally terminal order plus fallback/recovery truth. Require BUY admission/final claim blocked, same-side SELL single-flight occupied, and release only after authoritative terminal resolution. |
| INV-095 | Persist protective MARKET rendered as extended-hours LIMIT, restart in regular hours, and exercise status, targeted lookup, mass report, and replace. Require original scope replay; mismatched client/broker id, advanced fields, fractional fill level, or predecessor fails closed. |

## Durable fields/events — producer/consumer audit

| State/event | Legitimate producers | Required consumers | Must not consume as |
|---|---|---|---|
| `VENUE_ORDER_SCOPE` / `VenueOrderScope` | Managed ordinary submit and envelope submit/replace, after durable claim and before venue call | Adapter submit/replace, direct status, targeted query, mass reconciliation, recovery/adoption, restart loader | Position truth, lifecycle transition, or permission to relax owner scope |
| Accepted-submit `UNKNOWN_RECONCILE_REQUIRED` reason `accepted_submit_unpersisted` | Every accepted-ack finalizer when normal state/recovery cannot persist | Cross-side rails, same-side single-flight, final claim, safe-local-cancel exclusion, CAPI, cadence/startup/reconnect repair, restart indexes | `SUBMITTED`, `FILLED`, position, or permission for another venue call |
| `ENVELOPE_FILL_ATTRIBUTED` | `record_envelope_fill` only for existing uniquely validated canonical fill | Remaining-chain validation, monitoring repair/replay, checkpoint processing | A second `FILL`, position/order quantity, or rewrite of fill |
| `ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT` | Entirely validated attribution tail | Bounded tail selection and restart resume | Repair evidence or reason to skip poison |
| `SUBMIT_ACCEPTANCE_REPAIR_CHECKPOINT` | Entirely repaired accepted-submit tail | Bounded accepted-fact selection and restart resume | Ownership or reason to pass malformed evidence |
| `STALE_SUBMITTING_REDRIVE_STARTED` | Priceable stale redrive immediately before venue call | Durable attempt accounting and audit | Acceptance or lifecycle status |
| Explicit `QUARANTINED` | Broker-authoritative order/envelope overfill containment, atomically with raw canonical truth | One shared lock-held projection used by public listing, `create_order_for_candidate`, and final BUY claim on both stores; SQLite reopen must retain all consumers | Lifecycle status, synthetic fill, position quantity, or release of venue truth |

Enumerate every executable producer and consumer. Comments, enum declarations, serializers, and
test-only constructors do not count.

## Accepted-submit producer matrix

| Producer | Normal adoption | Adoption fails, recovery succeeds | Audit succeeds, recovery fails | Audit fails, recovery fails | Immediate restart | Replay |
|---|---|---|---|---|---|---|
| Ordinary first submit | Required | Required | Exact fallback | Exact fallback | No second venue call | Idempotent |
| Stale `SUBMITTING` redrive | Required | Required | Exact fallback | Exact fallback | Durable attempt/owner | Idempotent |
| Direct SELL submit | Required | Required | Exact fallback | Exact fallback | Same/cross-side rails closed | Idempotent |
| Envelope initial submit | Required | Required | Exact fallback | Exact fallback | Envelope owner retained | Idempotent |
| Envelope replace/reprice | Required with predecessor | Required | Exact fallback | Exact fallback | Old/new identities distinct | Idempotent |

Also test blank/whitespace/malformed acknowledgment identity, cancellation during venue await,
conflicting fallback dedupe ownership, multiple concrete legs for one local order, and one broker id
under another local owner.

## Choke-point matrix

| Choke point | Cross-side exposure | Recovery/fallback ownership | Stand-down/cleanup | Control/quarantine |
|---|---|---|---|---|
| Candidate admission, candidate-to-order mint, and final dispatch | BUY blocked by executable SELL | Direct/envelope SELL recovery and fallback count | Dispatch-lost race expires | Both negative-position history and explicit positive-position `QUARANTINED` block autonomous BUY mint after restart |
| Direct SELL mint/dispatch | SELL blocked by executable BUY | Declared/referenced BUY recovery, broker-owned CREATED, fallback count | Safely local BUY epoch closes atomically | Halted denied |
| Final submission claim | Both directions rechecked | Own/sibling recovery and broker/fallback identity block blind reclaim | CAS decides raced cleanup | Candidate-origin BUY claim consumes same FILL+QUARANTINED projection under lock and blocks `symbol_quarantined` |
| Envelope stage/final claim | BUY exposure prevents stale SELL | Recovery, needs-review, fallback, owner lineage retained | Safe CREATED siblings only | Halted/budget/lineage ambiguity fail closed |
| Protection open | BUY uncertainty defers with no SELL | Recovery/fallback included | Safe proposal/CREATED epoch closes only on success | Halted denied; quarantine does not categorically block safe reduction |
| Ordinary flatten | BUY uncertainty blocks | Recovery/fallback included | Safe BUY work only | Halted denied even with ambient grant |
| Emergency reduce | Same reduce-only rails | Capability exact current session | Failure leaves one reusable grant | Explicit capability only; resolution atomic |
| Local cancel/terminal cleanup/session close | Never cancel uncertain work | Broker id/recovery/fallback prevents local cancel | Projection-first, source-excluding, one owner reconcile | Injected clock and rollback retained |
| Recovery/repair/startup | No new work minted | Exact identity across restart | Adoption/resolution without resubmit | REDUCING commits before repair/venue work |
| Fill ingestion/attribution | Fill only changes quantity | Exact order/envelope identity | Source and sibling distinguished | Broker excess recorded+quarantined; synthetic excess rejected |
| Status/targeted/mass reconciliation | Exact request/response scope | Broker id authoritative; id-less fallback bounded | No foreign mutation | Invalid correlation/budget keeps REDUCING |

## Memory/SQLite decision-structure audit

Compare branch conditions, mutation order, rollback, deterministic iteration, and restart—not only
happy-path results—for:

1. candidate admission and dispatch expiry;
2. shared local CREATED cancel and session-close selection;
3. envelope stage and final claim;
4. terminal fill cleanup/source exclusion/one owner reconcile;
5. emergency grant reuse, checks, and atomic resolution;
6. fill append, replay, economic conflict, overfill quarantine, bounded scalar;
7. recovery exact-pair identity and cross-representation exclusivity;
8. accepted-fallback cache/index rollback and SQLite restart rebuild;
9. venue-scope serialization, owner authentication, and restart replay;
10. attribution/accepted-submit checkpoints, poison, and idle convergence;
11. shared quarantine projection: memory's complete log versus SQLite's selected `FILL` plus
    `QUARANTINED`, with identical public-list, candidate-order-mint, final-claim, and reopen use.

## Hostile scenarios

At minimum, independently exercise:

- all accepted-ACK combinations of local state, audit, and recovery failure;
- `asyncio.CancelledError` after a venue call may have started;
- blank SDK ids, padded aliases, duplicate client ids, cross-local broker-id collision;
- two accepted legs for one local order and aggregate fill allocation;
- restart between scope write and call, and between acceptance and ownership;
- poisoned venue scope, wrong owner/predecessor, advanced mismatch, fractional/non-finite mass fill;
- record-first fill followed by attribution failure, marker collision, foreign lineage, broken chain;
- positive-position broker overfill whose containment exists only as explicit `QUARANTINED`;
  prove list, candidate-origin BUY mint, and final BUY claim agree across stores and SQLite reopen;
- emergency grant retry, rollback, foreign session, natural rollover;
- exit preemption with candidate creation/dispatch race, recovery-owned projected-CREATED BUY,
  stale raw status, and terminal source cleanup;
- exhausted query budget and failed inferred-fill lookup/append;
- large unrelated UNKNOWN history and checkpoint poison with bounded indexed reads.

## Pin integrity / mutation requirements

Temporarily neuter representative guards and run exact distinguishing tests. Record mutation,
expected red, observed failure, in-place restoration, and restored green. Cover at least:

- accepted-submit fallback producer and its opposite-side/local-cancel consumers;
- exact broker-id ownership collision;
- venue-scope owner authentication and advanced mass materiality;
- attribution marker not folding position and checkpoint not passing poison;
- explicit broker-overfill quarantine;
- shared explicit-quarantine projection and its two autonomous-BUY gates: independently removing
  either SQLite consumer turns only its SQLite pin red; FILL-only shared reader breaks public list
  plus both restart gates;
- emergency capability isolation;
- exit-epoch admission/dispatch;
- source-excluding terminal cleanup with one reconciliation.

Do not use destructive checkout to restore mutations and do not commit review mutations.

## Exact verification commands

```powershell
$Py = (Resolve-Path .\.venv\Scripts\python.exe).Path
$Rev0033Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("automation-alpaca-rev0033-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Rev0033Temp | Out-Null

& $Py -m ruff check .
& $Py -m ruff format --check .
& $Py -m mypy app
& .\.venv\Scripts\lint-imports.exe
git diff --check 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48
```

Focused WO/quarantine corpus (**580 tests**):

```powershell
& $Py -m pytest -q `
  tests/test_wo0113_acceptance_identity.py `
  tests/test_wo0113_attribution_repair.py `
  tests/test_wo0113_capi_uncertainty.py `
  tests/test_wo0113_emergency_override.py `
  tests/test_wo0113_lifecycle_closure.py `
  tests/test_wo0113_monitoring_failclosed.py `
  tests/test_wo0113_primary_remediation.py `
  tests/test_wo0113_repair_scaling.py `
  tests/test_wo0113_safe_local_cancel.py `
  tests/test_wo0113_sell_boundary.py `
  tests/test_wo0113_store_parity.py `
  tests/test_wo0113_submit_acceptance_fallback.py `
  tests/test_spine_phase3b_overfill_quarantine.py `
  tests/test_spine_phase3c_timeout_quarantine.py `
  --basetemp (Join-Path $Rev0033Temp "focused")
```

```powershell
& $Py -m pytest -q tests/r2_conformance_oracle.py `
  --basetemp (Join-Path $Rev0033Temp "conformance-codex")
& $Py -m pytest -q tests/test_r2_conformance_oracle_claude.py `
  --basetemp (Join-Path $Rev0033Temp "conformance-claude")
& $Py -m pytest -q tests/test_review_hardening_gates.py `
  --basetemp (Join-Path $Rev0033Temp "hardening")

1..3 | ForEach-Object {
  & $Py -m tests.performance.r2_scaling_gate
  if ($LASTEXITCODE -ne 0) { throw "scaling run $_ failed" }
}

1..3 | ForEach-Object {
  & $Py -m pytest -q --basetemp (Join-Path $Rev0033Temp "full-$_")
  if ($LASTEXITCODE -ne 0) { throw "full-suite run $_ failed" }
}

& $Py -m pytest -q --cov=app --cov-branch --cov-report=term-missing `
  --basetemp (Join-Path $Rev0033Temp "coverage")
```

Record exact counts, skips/xfails, coverage, scaling ratios, exit codes, and environment limits.

## Author evidence to reproduce, not accept

- Frozen implementation SHA: `9a7af3b08a2d050e324a862d59548ff2da747c48`
- Frozen range: **86 paths; 21,655 insertions; 1,321 deletions**
- Focused: **580/580**; Phase-3b **27/27**; post-P1 cluster **274/274**
- Mutation: final P1 red **2 failed / 2 passed**; admission one SQLite red/one memory
  green; claim one SQLite red/one memory green; shared FILL-only projection **3/3 SQLite red**;
  restored **5/5**. Earlier representative mutations: mass **1/1**, scope owner **4/4**,
  record-first overfill **2/2**, quarantine poison **4/4**, ACK lifecycle **16/16**.
- Full suite: three consecutive unchanged-product-tree runs, each **3859 passed, 11 skipped,
  1 xfailed (3871 collected)**; XML times **336.551s, 379.071s, 385.331s**.
- Coverage: **93.50%** against **93.0%** floor; same zero-failure suite; **523.3s**.
- Conformance: Codex **61/61**; Claude **22 passed / 6 documented skips**.
- Hardening: **12/12**.
- Scaling: three `passed: true`; runtime **1.3107 / 0.8181 / 1.0266**; startup elapsed
  **9.4612 / 9.0201 / 8.8985**; startup selects **9.1022**.
- Static/hygiene: Ruff check+format **258 files**; mypy **64 files**; import-linter
  **6 kept / 0 broken**; scope and AI-OS checks green.
- Exact-head CI: GitHub Actions **#482 SUCCESS** on `9a7af3b08a2d050e324a862d59548ff2da747c48`.
- Automated final-head review: comment `5018668794`, reviewed `9a7af3b08a`, no major issues.

One post-success Hypothesis `StopTest` teardown diagnostic appeared after full run 3. It did not
alter the successful exit/result and did not reproduce in the isolated property test or coverage
rerun. Independently assess whether this is benign teardown output.

## Expected result lifecycle

Write `result.md` with `rev_id: REV-0033`, `status: COMPLETE`, independent reviewer identity, exact
range, date, and verdict. Produce findings only. The implementer/operator later creates
`disposition.md`; the reviewer must not pre-disposition findings. Neither `ACCEPT` nor
`ACCEPT-WITH-CHANGES` authorizes merging PR #9.

End with exactly one verdict: **BLOCK**, **ACCEPT-WITH-CHANGES**, or **ACCEPT**. State anything not
independently verified.
