---
type: Review Request
rev_id: REV-0005
campaign_id: CAMPAIGN-0001
packet: ENGINE
container_group: G-E (runtime engine)
packet_lens: adversarial red-team (primary) + concurrency/async + observability (secondary clusters)
status: AWAITING_REVIEW
targets: [G-E-engine]
human_gated_surfaces: [order-submission, cancel-replace, kill-switch, manual-flatten]
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [safety-core #8, safety-core #9, safety-core #10, INV-001, INV-020, INV-021, INV-022, INV-023, INV-024, INV-050, INV-051, INV-052, INV-034, INV-075, "spine INV-1..9"]
adr_in_scope: [ADR-001, ADR-002, ADR-003]
created: 2026-07-10
---

# Review Request REV-0005 — Runtime engine (execution core), adversarial red-team

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes no correctness claims — code beats the atlas, and if they
disagree that is itself a finding). You have the full repo at the frozen SHA.

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/monitoring.py` (2158 LOC) — the background loop; the **only writer** of order/fill/position
  state (the single-writer heart).
- `app/reconciliation.py` (357 LOC) — the *pure* reconciliation planner the loop drives.

**Owned by other packets (follow leads freely into them):** these have a deep-coverage owner
elsewhere, so you need not audit them exhaustively — but **do not assume their contract holds**.
If the engine *relies* on a behavior these modules don't actually guarantee, re-derive that
behavior from their code and report the reliance as **your** finding; and any defect you spot
inside them while chasing an engine lead is a finding wherever it lives.
- store planners / `claim_order_for_submission` → REV-0006 (STORE-SPEC).
- the broker adapter (timeout/error contract) → REV-0011 (BROKER).
- event projection / `project_order_status` → REV-0007 (EVENTS).

## What you're reviewing
`monitoring.py` is the runtime engine: an async loop that drives **submit → poll → reconcile →
protect → flatten**, and the single place order/fill/position state is mutated. It is the
highest-risk container in the codebase — a race, a dropped `await`, a mis-sequenced check, or a
missed quarantine here can **double-submit an order, mutate position quantity off a non-fill, or
emit new order intent after the kill switch**. `reconciliation.py` is the pure planner it uses to
diff local vs broker state under a query budget.

Run for context:
`git diff b600101~1..b600101 -- app/monitoring.py app/reconciliation.py` (or just read them at `b600101`).

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
- **Loop + lock/await structure:** `monitoring_loop` (`app/monitoring.py:435`), `run_monitoring_tick`
  (:536), `run_startup_reconcile` (:481), `on_stream_reconnect` (:502). Map **every `await`
  suspension point**: what invariant could another scheduled task (a protection tick, a manual
  flatten, a reconnect) violate across that suspension? Note INV-052 (no broker call under the
  store lock) — trace whether any broker call happens while the lock is held.
- **Submit path & the double-submit guard:** the submit sweep (search `_submit_pending`) and its
  use of the store claim gate. Confirm the engine cannot re-enter submit for an order the event
  log already shows as SUBMITTED — this is the REV-0001 F-001 class; verify it holds **from the
  engine side**, independent of the store's own guard.
- **Ambiguous / timeout → quarantine (ADR-002):** the ambiguous-submit branch (~`:700-725`, where
  `store.quarantine_timed_out_order` is called at `:718`, with the "next tick would blind-resubmit"
  reasoning at `:703`) and the ambiguous **re-drive** branch (~`:896-911`). Then
  `_resolve_timeout_quarantine` (`:952`) — the targeted **READ-ONLY** venue query that resolves a
  quarantine via the deterministic `client_order_id`. Trace: is there **any** path (submit sweep,
  stale re-drive, reconnect, startup) that resubmits or re-drives an order that may already be
  live at the venue?
- **Reconciliation keying:** `plan_reconciliation` (`app/reconciliation.py:204`) matches broker
  reports to local orders by `client_order_id == order.id` (`:219`, `by_client_id` at `:227`), under
  `ReconcileQueryBudget` (`:69`). Trace how an inferred fill / external order / position mismatch
  flows back into the loop and into state.
- **Kill-switch placement:** the trading-state gate (`kill_switched = session.trading_state is
  TradingState.HALTED`, `:301`, used at `:310`; and in `cancel_open_buys` at `:221`). Relative to
  **new-order-intent emission** across the strategy/protection/flatten paths.
- **Position mutation sites:** every place a fill reaches position quantity — confirm against
  INV-001 / safety-core #9 that ONLY fill events move quantity and SUBMITTED/ACCEPTED structurally
  cannot.
- **INV-034 flatten interaction** — the atlas discloses this as tracked-but-unfixed; confirm the
  *current* engine-side behavior, do not assume the tracker is complete.

## Probe checklist (find the failure, or prove it cannot exist — symmetric challenges)
**RED-TEAM / SAFETY**
1. Construct an interleaving where two loop activities act on the same order across an `await`
   (e.g. a protection tick + a manual flatten, or two tick iterations). Does any ordering
   **double-submit, double-cancel, or mutate quantity off a non-fill**? Show the interleaving, or
   argue why the lock discipline makes it impossible.
2. Force an ambiguous broker submit (per REV-0011's documented adapter timeout contract). Show the
   order lands in `TIMEOUT_QUARANTINE` and is **never blind-redriven** by any sweep. **Find a path
   that escapes quarantine and resubmits**, or prove none exists across submit / stale-redrive /
   reconnect / startup.
3. Trip the kill switch mid-tick. Prove **no new order intent** is emitted afterward on any in-flight
   path (strategy, protection, flatten). Find a path where intent leaks past a `HALTED` state.
4. Broker-authoritative overfill (ADR-001): a recorded fill drives a long position negative. Show it
   is recorded and quarantined (not hidden, not rejected), and that autonomous trading halts.

**CONCURRENCY / ASYNC**
5. Audit lock scope vs `await`: is any invariant checked *before* an `await` and acted on *after*,
   with no re-check (a TOCTOU)? Is task cancellation on shutdown safe mid-write (no partial mutation)?
6. Is `reconciliation.ReconcileQueryBudget` accounting safe under out-of-order/concurrent calls, so a
   race cannot over-spend the venue query budget?

**OBSERVABILITY**
7. Does **every** state mutation co-emit its lifecycle + audit event with the **actor** threaded?
   (REV-0002 F-002 was a dropped actor on a flatten event.) Find a mutation with no audit trail, or
   an audit event with a wrong/missing actor.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the CODE against the invariant **statements** in `docs/INVARIANTS.md` (INV-001, INV-020..024,
INV-050/051/052, INV-034, INV-075) and the `CLAUDE.md` safety core (#8 submitted≠filled, #9 only
fills change qty, #10 kill switch blocks intent), plus the spine `INV-1..9` in
`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5`. **Do not** validate against the pinning tests — per
X-002, a test can assert the very bug it should catch; re-derive "what must always hold" from the
invariant text and probe the code directly.

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro** (a probe script, a `pytest -k`, or a shell
  command) **plus its pasted output**, dual-store where relevant (memory + sqlite). A finding with
  no repro is marked **"unverified concern"** and **cannot gate**.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran**. A bare
  "looks fine / LGTM" with no probe log is a **rejected review** for that area — show your work on
  clean code too.
- If the code contradicts the Atlas or a disclosed known-item, that disagreement is itself a
  finding (≥ P1).

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** and fill it: the
findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters | Proposed fix`),
an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and whether **G-E's foundation
gate may clear**. State plainly anything you could not verify (e.g. real-broker timing you can't
exercise). Do **not** edit `request.md`; do **not** push code fixes.
