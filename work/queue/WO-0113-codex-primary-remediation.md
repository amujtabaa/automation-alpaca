---
type: Work Order
title: Codex primary-seat engagement — review the prior seat's WO-0111/WO-0112, remediate all findings, close the recurring gap classes, reach merge-readiness
status: QUEUED
work_order_id: WO-0113
wave: R2 consolidation campaign (CAMPAIGN-0002), merge-readiness (Codex primary seat)
model_tier: strong
risk: high
disposition: []
owner: Ameen
implementer_seat: Codex (primary implementation seat — durable operator decision, 2026-07-19)
review_seat: Claude or human (independent — NOT the implementer; REV-0033)
created: 2026-07-19
supersedes: the "findings only / do not push code" instruction inside work/review/REV-0031/request.md and work/review/REV-0032/request.md — under this WO the same seat records findings first, then implements the fixes
gated_surface: order submission/claim, candidate dispatch, manual flatten, autonomous protection exit, emergency-reduce authorization, envelope stage/terminal cleanup, recovery/event-log truth
---

# Work Order: WO-0113 — Codex primary-seat remediation to merge-readiness

> **Context for the implementer.** This repository is a **paper-trading simulator** — a FastAPI +
> SQLite / in-memory engine that models the lifecycle of stock orders (create → submit → fill →
> position) against a broker **paper** sandbox. There is no live trading, no real funds, and no
> network, credential, or authentication surface. "Safety" here means order-lifecycle **correctness
> invariants** (a submitted order is not a fill; only fill events change position quantity; one exit
> per symbol; a buy and an exit sell for one symbol are never both working at the venue). Every task
> below is ordinary defensive correctness engineering: confirm or refute a suspected bug with
> evidence, fix what is real, and pin it with a test that provably fails without the fix.

## Goal

The operator has moved the **primary implementation (coding) seat to Codex** — durably, not per-WO.
Rationale: across four review rounds (REV-0029 rounds 1–2, and three automated PR-review rounds on
PR #9), the reviewing seat repeatedly found real correctness gaps in or adjacent to the prior
implementer seat's work — a treadmill of per-instance fixes each followed by a sibling gap. This WO
ends the treadmill in four phases:

- **A.** Independently review the prior seat's two most recent change sets (WO-0111, WO-0112) via
  the queued packets REV-0031 and REV-0032.
- **B.** Remediate every confirmed finding — from Phase A, and from any automated PR review of
  subsequent commits — and resolve the two design choices queued for operator ratification.
- **C.** Run the **recurring-gap-class sweep** (§Phase C below): verify each cross-cutting
  correctness property at every choke point, both stores, so the remaining sibling gaps are closed
  **by property**, not instance-by-instance.
- **D.** Bring `consolidate/r2-canonical` to merge-ready with fresh evidence, queue the independent
  review of your own changes (REV-0033), deliver the batched operator questions, and ship close-out.
  **The merge itself remains the operator's action.**

## Seat model (read first)

- **Implementer:** Codex. You write the code and the tests, commit, and push to
  `consolidate/r2-canonical` only.
- **Phase A is a genuine independent review**: the WO-0111/WO-0112 deltas were implemented by the
  Claude seat, so your review of them is cross-model by construction. Deposit `result.md` in each
  packet folder before changing the code they cover.
- **Your own implementation is never self-certified.** When Phases B–C are done, queue
  `work/review/REV-0033/` (request.md describing your change set and how to verify it) for the
  independent seat (Claude or human). In-process validation never counts as independent review.
- **Human-gated surfaces** (listed in the frontmatter) are touched throughout. The operator has
  **authorized this engagement** — the review, the remediation, and the sweep. That authorization
  does **not** pre-approve semantic policy changes on gated surfaces (see the Operator decision
  queue) and does not pre-approve the merge.

## State at handoff (2026-07-19)

- Branch `consolidate/r2-canonical` at **`194343c`**, in sync with origin; **CI green** (4/4 jobs);
  PR #9 open against `master` (base `2aa377a`), mergeable. Local full gate reproduced green at the
  same commit (full suite, both spec oracles, hardening gates, scaling gate, AI-OS hygiene).
- Recent history (all by the prior implementer seat, all gated green at push):
  - `4d607da` **WO-0111** — two automated-review findings on the WO-0109 code: monitoring's
    single-envelope lineage projection disowned a supersession successor's order (fills would skip
    `record_envelope_fill`); the emergency-reduce authorization refused re-authorization while its
    grant was still active, stranding the documented retry path. Record:
    `work/completed/WO-0111-pr9-review-round2-followups.md`.
  - `ba6be70` — queued REV-0031 (review packet for WO-0111).
  - `194343c` **WO-0112** — three automated-review findings, all pre-existing gaps: the exit-preempt
    stand-down missed already-dispatched CREATED buy orders (position re-grow after an exit, §5.3);
    `open_protection_exit` minted a sell while a same-symbol buy was venue-uncertain (wedge or
    mis-size); memory skipped the terminal-envelope late-fill cleanup that SQLite runs (store-parity
    divergence). Record: `work/completed/WO-0112-pr9-review-round3-followups.md`, plus the queued
    REV-0032 packet.
- **Queued review packets (Phase A inputs):**
  - `work/review/REV-0031/request.md` — WO-0111, range `7194f02..4d607da`.
  - `work/review/REV-0032/request.md` — WO-0112, range `ba6be70..194343c`.
  - Both say "produce findings only; do not push code." **Superseded by this WO**: record the
    findings first (the packet result is the durable record), then implement the fixes yourself.
- **Operator decision queue (pending ratification, batch — do not block):** see §below.
- **Parked, out of scope:** PD-1 (needs-review reconciliation release valve) is a post-merge WO;
  paper-broker backfill verification is a pre-beta task. Do not pull them in.

## Operating discipline (Fable, every cluster — identical to WO-0109)

1. **Red first.** Write the failing test(s) before the fix. Each new safety pin must pass a
   **guard-removal (mutation) check**: delete or neuter the guarded branch and show the pin turns
   **red**; restore **by editing back in place** (never `git checkout` over uncommitted work) and
   show green. Record the mutation result in the commit message.
2. **Both stores.** Every state/order/fill/recovery/claim behavior is pinned on **both**
   `InMemoryStateStore` and `SqliteStateStore` (the `any_store` fixture), and any store change lands
   in both implementations in the same commit.
3. **Full gate per commit:** `ruff check .` · `ruff format --check .` · `mypy app/` · `lint-imports`
   · `pytest -q` (both stores) · the two spec oracles (`tests/r2_conformance_oracle.py`,
   `tests/test_r2_conformance_oracle_claude.py`) · `tests/test_review_hardening_gates.py` ·
   `python -m tests.performance.r2_scaling_gate` · the AI-OS hygiene scripts
   (`.ai-os/scripts/check_*`), including the scope check against this WO.
4. **Injected clock / deterministic IDs / no unseeded randomness** in engine logic (repo rule).
5. **Never weaken a test to make code pass.** Fix the code or flag the conflict. Amending a test
   whose pinned behavior a fix legitimately changes requires an in-body citation of the finding and
   preservation (or strengthening) of the test's real invariant.
6. **Close-out ships with the work:** the commit that finishes a cluster updates this WO's progress
   log and flips any doc/INV/ADR/PKL claim the fix changes, in the same commit.
7. **Conflict rule:** if code, docs, and ADRs disagree on a gated surface, stop and record the
   decision gap in the Operator decision queue — do not silently pick a side.

## Scope (allowed_paths)

```yaml
allowed_paths:
  - work/queue/WO-0113-codex-primary-remediation.md
  - work/active/WO-0113-codex-primary-remediation.md    # move here on start
  - work/completed/keep/WO-0113-codex-primary-remediation.md  # required close-out move
  - work/review/REV-0031/**
  - work/review/REV-0032/**
  - work/review/REV-0033/**                             # your implementation's review packet
  - work/ledger.jsonl
  - tests/**
  - app/monitoring.py
  - app/reconciliation.py
  - app/transitions.py
  - app/policy.py
  - app/store/core.py
  - app/store/base.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/models.py
  - docs/INVARIANTS.md
  - docs/adr/**
  - pkl/**
```

```yaml
forbidden_paths:
  - Any push/rebase/merge of a branch other than consolidate/r2-canonical.
  - Any merge of PR #9 (operator action).
  - .agents/**, .codex/**  (the CI contamination guard fails the build if either is tracked).
```

If remediation or the sweep identifies a necessary change outside this list, add the specific file
with a one-line flagged justification in this WO's scope section — do not silently widen.

## Phase A — independent review of the prior seat's WO-0111 and WO-0112

Work the two queued packets exactly as written (their per-finding "closure by property" questions
and fresh probes), with one supersession: after depositing each `result.md`, you fix what you
confirmed rather than handing back.

- `work/review/REV-0031/request.md` — WO-0111 (`git diff 7194f02..4d607da`): the monitoring
  supersession-attribution change and the emergency-reduce re-authorization change.
- `work/review/REV-0032/request.md` — WO-0112 (`git diff ba6be70..194343c`): the exit-preempt
  CREATED-buy stand-down, the protection-open fail-closed gate, and the late-fill terminal-cleanup
  parity change.

For each packet: per-finding evidence (`file:line`, a concrete failing sequence for anything you
refute or confirm), the packet's fresh probes actually run (record harness + outcome), and a verdict
(`ACCEPT` / `ACCEPT-WITH-CHANGES` / `BLOCK`) — the verdict describes the prior seat's change set as
it stands; your own follow-on fixes then land under Phase B. You are free to conclude a prior fix is
wrong in shape and replace it (with citation and preserved-or-stronger pins), not just patch around
it.

## Phase B — remediation

1. Every finding your Phase-A review confirms.
2. Every finding any automated PR review raises on commits you push (triage each: fix what is real,
   refute with pasted evidence what is not — a written refutation in this WO's progress log is the
   record).
3. The two design choices in the Operator decision queue: evaluate each on the merits, implement
   your recommended shape if it differs, and put the final recommendation (with rationale and
   evidence) in the queue for the operator's ratification.

## Phase C — the recurring-gap-class sweep (the point of this WO)

Four review rounds produced the same **shapes** of gap repeatedly. Close each shape by property.
For every class: enumerate the full surface, verify each cell, pin anything found (red-first,
guard-removal-checked, both stores), and record the completed matrix — including explicit "N/A
because…" cells — in this WO's progress log. An unexamined cell is an open item, not a pass.

- **C1 — Choke-point × property matrix (the "symmetric twin" class).** Guards have repeatedly landed
  at one choke point but not its siblings (flatten handled CREATED buys; envelope-stage/protection
  did not; the exit predicate counted sell orders but not open sell recoveries; declared recovery
  scope but not referenced-order scope). Build the matrix explicitly: choke points = candidate
  dispatch, order mint, submission claim, envelope stage, envelope final claim, manual flatten,
  autonomous protection open, emergency-reduce, cancel paths, recovery ingress, recovery
  resolution, session close. Properties = cross-side exposure (both directions), recovery-aware
  exposure (declared AND referenced scope), candidate/CREATED-order stand-down, single-flight /
  one-active-per-symbol, session/halt gating, quarantine blocking. Verify every cell on both stores.
- **C2 — Store decision-structure parity.** WO-0112 F2 was a branch-condition divergence between
  memory and SQLite (cleanup keyed on the transition in one store, on stored status in the other).
  For every write-path method with a memory/SQLite twin, compare the **decision structure** (branch
  conditions, cleanup triggers, event writes, rollback semantics), not just test outcomes. Pin any
  divergence-prone spot with a parity test that constructs the distinguishing state.
- **C3 — One-shot / consumable state lifecycle audit.** WO-0111's emergency-reduce wedge was a
  single-use grant stranded active by a fail-closed exit path. Enumerate every consumable or
  one-shot state (override grants, submission claims, single-flight rails, cancel/replace budgets,
  quarantine holds) and verify each has a defined, tested path out of **every** non-consuming exit
  (failure, deferral, restart) — no state that only a happy path can release.
- **C4 — Shared-projection scope audit.** WO-0111's monitoring bug fed owner-scoped inputs into a
  single-envelope projection. Audit every call site of the shared projections (store and monitoring)
  for scope mismatches between the selection universe and the projection target set.
- **C5 — Documented-exclusion compensating-control audit.** Several deliberate design exclusions
  (e.g. CREATED not in `MAY_EXECUTE_ORDER_STATUSES`) are safe only because a compensating control at
  another layer covers the excluded case. For each documented exclusion in `app/policy.py`,
  `app/store/core.py`, and the store comments: name the compensating control, verify it exists at
  every relevant choke point, and confirm it is pinned by a test that fails without it.

Where C1–C5 confirm a gap, fix it under Phase-B discipline. Where a cell is sound, the recorded
matrix row with its evidence is the deliverable.

## Phase D — merge-readiness and close-out

- Full gate green at the final HEAD (fresh pasted output for every command in Discipline §3).
- PR #9 CI green on the final push.
- `work/review/REV-0033/request.md` queued: your change-set summary, per-cluster verification
  instructions, and the same evidence standard the prior packets carry — for the independent seat.
- The Operator decision queue delivered as one batched list (this WO's section updated).
- Close-out ships with the work: progress log complete (including the C1–C5 matrices), WO moved to
  `work/completed/keep/`, ledger row appended, docs/INV/ADR/PKL claims current.
- **No merge of PR #9. No push to any other branch.**

## Operator decision queue (batch; deliver at close or when blocking)

1. **WO-0112 F3 targeting** — the exit-preempt CREATED-buy stand-down cancels only
   `filled_quantity == 0` CREATED buys (sparing establishing-order stubs whose shares are already
   folded). Endorse or propose an alternative, with evidence.
2. **WO-0112 F1 shape** — `open_protection_exit` defers (returns `None`, audited event, retried next
   tick) rather than raising, when a same-symbol buy is venue-uncertain. The trade: a briefly
   unprotected position vs. a wedged/mis-sized exit. Endorse or propose an alternative.
3. Anything new that Phases A–C surface which changes gated-surface semantics.

## Done-when

- [ ] REV-0031 and REV-0032 `result.md` deposited, per-finding evidence + verdicts; every confirmed
      finding remediated (or replaced with a better shape, cited).
- [ ] All automated PR-review findings on new commits triaged: fixed or refuted with evidence.
- [ ] C1–C5 sweeps executed; matrices with per-cell outcomes recorded in the progress log; every
      confirmed gap fixed with red-first, guard-removal-checked, dual-store pins.
- [ ] Full gate + both oracles + hardening gates + scaling gate + AI-OS hygiene green at final HEAD;
      PR #9 CI green.
- [ ] `work/review/REV-0033/` queued for the independent seat; no self-certification.
- [ ] Operator decision queue delivered as one batched list.
- [ ] Close-out shipped with the work (WO moved to completed/keep, ledger row, doc/INV/ADR/PKL flips).
- [ ] No merge performed; no branch other than `consolidate/r2-canonical` pushed.

## Progress log

- **QUEUED 2026-07-19** — drafted by the Claude seat at the operator's direction: the primary
  implementation seat moves to Codex durably; Claude's WO-0111/WO-0112 stand as pushed, gated work
  whose disposition now belongs to this WO's Phase-A review. Handoff point `194343c` verified: CI
  green (4/4), local full gate reproduced green. Awaiting Codex to move this WO to `work/active/`
  and begin Phase A.
