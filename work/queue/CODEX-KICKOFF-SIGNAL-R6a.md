# Codex kickoff — Signal Seat R6a: the rails store surface (LOCAL, strongest model)

> Operator launch prompt, drafted by the planning seat 2026-07-26. Paste into a FRESH **local** Codex
> session at the repo root, strongest model, full effort. **Stage 1 of 5 — runs ALONE**; its REV-0044
> must disposition before R6b or R7a start.
>
> **You are NOT being asked to ratify anything.** Unlike previous rungs, `WO-0104a` is **already
> operator-ratified** (`status: READY`, `ratified: 2026-07-26`). Its M1 block survived a FULL
> `.ai-os/core/18` war-game with **five M4b passes that produced 7 P0s**, every one verified against
> code by the planning seat before correction. Read it as a settled contract.

---

Codex, you are the implementer seat building **WO-0104a — Signal Seat R6a**, the rails store surface.
Read `AGENTS.md`, the `CLAUDE.md` safety core, then
**`work/queue/WO-0104a-signal-rails-store-surface.md` IN FULL** — it is your contract (the two
human-gated stops, M1 decision block D-R6a-1..17, M2 lifecycle totality, M3 consumer inventory, M4a,
the 24 verified BUILD HAZARDS, the §M4b records for passes 3–5, the gate battery, stop conditions).
Fable v3: GATE, red-first, fresh pasted evidence, FIX blocks with root cause. No completion claims
without evidence.

## Authorized defensive scope (read first)

**Authorized defensive engineering on the operator's own local, paper-only trading application, in the
operator's own repository.** The task is bounded resource accounting inside a local store: a per-producer
allowance that does not refill, a paced-arrival allowance that does, and the durable bookkeeping that
makes both survive a restart. There is **no external target, no network probing, no credential access,
no live trading, no persistence objective.**

**Reporting convention.** Report at the **defect level**: cause · impact · affected local files · fix ·
pass/fail evidence. Do **not** write reusable bypass procedures or payloads in code, comments, commit
messages, or the review request. Do **not** run an open-ended "try to break it" pass — the independent
**REV-0044 Claude seat is the sanctioned adversarial net.**

**Use this vocabulary:** *paced-arrival accounting* · *budget-exhaustion accounting defect* ·
*refill-accounting defect* · *non-atomic transaction boundary* · *incorrect type acceptance* ·
*double-debit defect*. **Avoid:** "flood attack", "DoS test", "exhaust the server", "starve the
producer". Same engineering content, far lower false-positive risk. If a filter interruption occurs,
your fixes are probably already applied: resume and give a **defect-level re-report**, never a re-run.

## What R6a is — and what it deliberately is NOT

R4 landed the signal model and store. R5a made `create_app` refuse to construct. R5b-1 added the
authenticated producer ingest path; R5b-2 made every sensitive request fail without the operator
credential. **R6a lands everything below HTTP for the rails** — so `app/store/**` is complete in one
rung, under one review packet and one migration.

**IN:** the durable rail row behind the gated DDL (log-derived columns **and** the token-bucket columns);
the producer-rail projector **and its `app/events/replay.py` registration**; epoch identity; the
**budget** debit inside `ingest_signal`; the **rate** check-and-debit primitive plus its breach opener;
`release_producer`; the snapshot-free transition-event builder; the 7th ingest outcome with its
record-free 403 branch; the `_atomic()` extension; six stale doc claims; `pkl/` + `work/` close-out.

**NOT IN (R6b):** `app/signals_rails_impl.py` · the provider / `check_ingest` / `SignalRails` /
`is_conforming_rails` / **`app/facade/signal_rails.py` and its `RailsDecision`** · `app/api/deps.py` ·
the in-memory rejected-counter holder · the §3 sweeps in `app/monitoring.py` · `/api/producers` and the
release **route** · the cockpit control · `signal_rate_limit_per_hour` / `signal_rate_burst` +
`.env.example` · the launcher positive control · **the step-2 rails call site itself.**

**NOT IN (later):** R7a/R7b conversion; D-2a. **The flag stays OFF. `app/server.py` is FORBIDDEN.**

## ⚠ The two human-gated stops — read before touching anything

- **Stop 2 — the `PRODUCER_QUARANTINED` payload — RESOLVED 2026-07-26 (Ameen).** The field list and the
  `breach_trigger ∈ {budget_exhausted, rate_breach}` vocabulary are ratified. You may append with that
  payload. **Any additional field or vocabulary value is a NEW stop** — an append-only log cannot be
  amended afterwards.
- **Stop 1 — the SQLite DDL — OPEN. This is the one approval stop left in the rung.** **STOP and present
  the proposed DDL with all six required items** (WO §HUMAN-GATED) before creating or altering any table
  or column. Do not read Stop 2's resolution as clearing Stop 1.

## Setup — the HARD gate first

1. `git status --short` — clean, else STOP.
2. `git fetch origin` — **mandatory and explicit.** A *local* `master` ref in this repo has been stale by
   **30 commits**. Base on `origin/master`, never local `master`.
3. **HARD GATE — use `git cat-file -e`, NOT `git ls-tree`.** Measured: `git ls-tree` **exits 0 with empty
   output** on a missing path, so a scripted `&&` chain reports success on a file that does not exist.
   (Earlier kickoffs in this repo used the `ls-tree` form — do not copy it.) Both must succeed, else STOP:
   ```
   git cat-file -e origin/master:tests/test_route_authorization_matrix.py
   git cat-file -e origin/master:work/review/REV-0043/disposition.md
   ```
4. `git checkout -b codex/signal-r6a-rails-store origin/master`
5. Confirm `app/signals_rails_impl.py` does **not** exist. R6a must not create it — that is what keeps
   `app/server.py` accurate through this rung.

## Step 0 — report these EIGHT verifications before writing code

Paste real command output for each. Several are premises the WO's P0 fixes rest on; if any comes back
different from what the WO states, **STOP and report** rather than adapting silently.

1. `git rev-parse origin/master` and `git rev-list --count master..origin/master` — record the SHA and
   the staleness delta you actually observed.
2. Both `git cat-file -e` probes above, plus their exit codes.
3. `_append_execution_event_unlocked` (`app/store/memory.py:5419`) and `_insert_execution_event`
   (`app/store/sqlite.py:7415`) — paste the signatures and the dedupe no-op branches
   (`memory.py:5433-5435`, `sqlite.py:7428-7437`). Confirm both **already return `ExecutionEvent`**, so
   D-R6a-4's identity discriminator needs **no signature change**.
4. Empirically confirm the discriminator on **both** stores: append an event, then append a fresh
   candidate carrying the **same** `dedupe_key`. Report `returned.id`, `returned.sequence`, and the log
   length. Expected: the no-op returns the **stored** event, so `sequence >= 1` on **both** paths and
   **only `id`** discriminates.
5. `app/store/memory.py:_atomic()` — report its line range and the **count of fields** in the snapshot
   block and the restore block. These must stay equal after your change (D-R6a-2).
6. `plan_signal_ingest` — paste its parameter list. Confirm it receives `cycle_budget_limit` but **no**
   consumed-count, epoch or quarantine input today, so the new required kwarg is genuinely new.
7. Baseline `pytest --cov=app --cov-branch` total percentage, so the ratchet delta is knowable
   (floor `fail_under = 93`, `pyproject.toml:38`).
8. Confirm `StateStore.ingest_signal`'s required params include `symbol`/`direction`/`thesis`/
   `provenance` — the structural proof that the rate primitive **cannot** live inside it (D-R6a-16.0).

## Decision block

Already ratified — do **not** re-ratify, and do not edit M1 lines. `WO-0104a` §M1 carries D-R6a-1..17 in
full with their TRACED citations. The four that most often get built wrong:

- **D-R6a-8 (P0)** — the gate is **`epoch_open OR consumed >= limit`**, never exhaustion alone. Option A
  gave the epoch a second opener, so those stopped being the same predicate. The ordinary rate breach
  opens an epoch at `consumed == 0`, because only attributable **rejections** debit the budget.
- **D-R6a-4 (P0)** — debit **and** opener are conditioned on the append having actually written, by
  **`stored.id == plan.event.id`**. `sequence` is **not** a valid predicate. The check is **two-sided**:
  a no-op on `plan.epoch_event`'s own append means the epoch was already open ⇒ **fail closed**.
- **D-R6a-3 (P0)** — the rail row has **two column classes**. Log-derived columns are rebuilt at
  `initialize()`; the **token-bucket columns are primary durable and must be PRESERVED, never rebuilt**
  (a same-hash replay debits the bucket and appends no event, so the log cannot reconstruct it).
- **D-R6a-16.4** — read-only on the reject path; on the **accept** path the fractional refill remainder
  must survive. Below one token interval per arrival, a truncating bucket refills **nothing at all**.

## ⚠ The two pins most likely to ship INERT — red-green is non-negotiable

This document has already produced two inert pins that a full suite passed while the control was
reverted (REV-0041's, and REV-0043's F-1). Two more are pre-identified. For **both**, revert the control,
paste the RED, restore, paste the GREEN:

1. **D-R6a-8 pin (iii)** — a rate-breach epoch at `consumed == 0`, then a novel-hash invalid submission ⇒
   **zero** new events, zero debit, still exactly **one** `PRODUCER_QUARANTINED` row. Mutation: weaken the
   gate to `consumed >= limit` ⇒ **must go RED**. That mutation is exactly the wrong build.
2. **D-R6a-16.4 carry pin** — the earlier "1.5× the token interval" pin was **measured inert** (correct
   and defective implementations are identical there). Use a **sub-cap bucket at sub-token-interval
   pacing**, plus bank-then-burst. Mutation: switch to truncate-and-advance ⇒ **must go RED**.

Mutation-checking is mandatory for every decisive pin (D-R6a-13), and **must** also cover the
record-free 403 branch (invisible to every static gate), the `_atomic()` restore fields, and the
`replay.py` registration — REV-0039 records that deleting the previous registration left the suite green.

## Existing tests — ZERO breakage expected, with a tripwire

Authorized edits are **only** `tests/test_signal_ingest_properties.py:79` (the `plan_signal_ingest`
kwarg) and `tests/test_signal_sqlite_schema.py` (the DDL). **Tripwire — if any of these seven sites needs
editing, you retyped `SignalIngestPlan.event` instead of adding `epoch_event`, and that is a STOP:**
`test_signal_ingest_properties.py:198,203,204,281,300,301,306`. (`result_record` **is** retyped to
Optional — that is the one sanctioned retype. `event` gets an additive sibling.) Any other existing-test
edit is a **STOP**: it means scope leaked into R6b's.

## Continuity across pauses and compaction

`work/active/SIGNAL-R6a-STATE.md` carrying (a) the ratification record and the two stops' status,
(b) your Step-0 report, (c) a slice scoreboard, (d) an evidence log. Update at every slice boundary.
After any pause/compaction re-read, in order: this kickoff → the state file → the WO. Verify with
`git log`/`git status`, never memory.

## Order of work (red-first each slice)

1. Gate → branch → **Step-0 report** → prove RED on the first slice.
2. **STOP: present the proposed DDL with all six items and WAIT.** Nothing durable is created before it.
3. Rail row + `_migrate` + R4-style startup guard + `tests/test_signal_sqlite_schema.py` +
   **`_atomic()` extension** (both halves, with the forced-exception rollback pin).
4. Producer-rail projector + **`replay.py` registration** + `initialize()`: class-(A) rebuild,
   class-(B) preservation. "Restart" per store — fresh `SqliteStateStore` over the same file; a second
   `initialize()` on the same memory instance.
5. Budget debit: three fold exclusions, identity discriminator, two-sided opener suppression, epoch
   identity and epoch-scoped `PRODUCER_*` dedupe keys (`signal_conflict`/`signal_create` stay global).
6. The **gate** + in-store ordering (boundary rejection precedes idempotent replay) + the 7th outcome +
   Optional record through both layers + `_OUTCOME_STATUS` + the record-free 403 branch.
7. Rate primitive + verdict DTO (`@dataclass(frozen=True)` in `app/store/base.py`, **not**
   `RailsDecision`) + the three ratified caps as **public** constants + the
   `producer_quarantined_event(...)` builder with `epoch_start` as `.isoformat()`.
8. `release_producer(producer_id, *, actor, rejected_count, released_at)` — resets both rails, validated
   and capped count, injected clock.
9. The snapshot-free transition-event builder (distinct prefix, identity-only payload).
10. Six stale doc claims + `pkl/architecture/signal-seat.md` change-log entry + close-out.

## Gate battery (fresh, pasted — all of it)

`ruff check .` · `ruff format --check` on your own files · `mypy app/` · `lint-imports` ·
**`pytest --cov=app --cov-branch`** (CI's ratchet, floor 93 — new in this rung's battery, and the one
gate a zero-consumer primitive plus a record-free branch can trip) · your corpus + the full suite ·
`python -m pytest -q tests/r2_conformance_oracle.py` · `pytest -q tests/test_wo0113_repair_scaling.py` ·
`python harness/bootstrap.py` · all three hygiene scripts.

**Two gates cannot prove what they look like they prove.** The static gates cannot prove the record-free
403 branch — `mypy` returns Success because `model_validate` takes `Any`. And **`lint-imports` cannot
prove the `RailsDecision` prohibition** — `app.store` is a *source* module in none of the six contracts,
so `app.store → app.facade` passes green. Add a corpus grep assertion: no file under `app/store/` imports
`app.facade`.

## Stop conditions — report, never self-authorize

**Any DDL before Stop 1 approval** · any payload field or vocabulary value beyond Stop 2's ratified list ·
any existing-test edit beyond the two authorized · any edit to the seven `plan.event` read sites · any
provider / `check_ingest` / `is_conforming_rails` / `app/facade/signal_rails.py` / `deps.py` / sweep /
route / cockpit / counter-holder work · any `app/server.py` edit · any new **setting** (the three caps are
ratified; the two `Settings` fields are R6b's) · anything making the flag independently enable-able · any
accepted-text conflict not already recorded in the WO · a P0-equivalent hole in accepted text.

## Close-out

Set WO-0104a to **REVIEW** and stage `work/review/REV-0044/request.md` (defect-level, named classes, no
exploit narration). It **must** state: which GAP-08 clauses R6a closes and which remain R6b's; the
approved DDL including the nullable pinned-limit column, the bucket column types **and carry form**, the
truth-model partition, and the startup guard; the live-vs-replay agreement evidence **with the bucket
columns and `rejected_count` explicitly excluded from that claim**; the `01-schema.md:86-92` in-store
ordering evidence; and the `test_route_authorization_matrix.py:238-247` 403-overloading coupling **as a
two-rung item R6b inherits**.

**⚠ REV-0044 also owes the packet half of Stop 2.** The operator's ratification satisfies the
"operator ratification" half of `SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md:110-113`; the packet must carry
the `PRODUCER_QUARANTINED` payload as an **explicit review item** so the reviewer dispositions it rather
than inferring it was covered.

Do **NOT** create `result.md` (reviewer-owned), touch the ledger, move to completed, merge, open a PR, or
enable the flag. Push `codex/signal-r6a-rails-store`.

**Report in your final summary:** the Step-0 findings (all eight), the delivery branch + SHA, the
approved DDL as landed, a defect-class table for anything you fixed, the **red-green evidence for the two
pre-identified inert-pin risks**, the full pasted gate evidence including the coverage delta, and
anything you had to STOP on.
