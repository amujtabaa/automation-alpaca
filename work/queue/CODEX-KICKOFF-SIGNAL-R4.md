# Codex kickoff — Signal Seat R4: model + store integration (local, strongest model)

> Operator launch prompt, drafted by the planning seat 2026-07-22. Paste into a FRESH local
> Codex session at the repo root — no pre-steps needed: the session syncs itself (Setup
> step 0) and fail-closes if preconditions aren't met. Decision block below is PRE-CHECKED
> with the planning seat's recommendations: pasting it unedited RATIFIES them; edit any
> line to override. **One gate is deliberately NOT pre-asked:** the `signal_records` schema
> approval — Codex will HARD-STOP mid-session and present the exact DDL for your explicit
> approval (plan §10 item 9). Stay reachable for that moment or expect the session to end
> BLOCKED on the sqlite slice.

---

Codex, you are the implementer seat in `automation-alpaca`, executing **WO-0134 — Signal
Seat R4 (model + store integration)**, the first implementation rung of the signal-seat
ladder now that ADR-009 is Accepted and G1 is clear. Read `AGENTS.md`, then the `CLAUDE.md`
safety core — both bind on everything. Then read `work/queue/WO-0134-signal-model-store-integration.md`
IN FULL — it is your contract, including the test-pinned symbol table, the exact seams, and
THE SCHEMA GATE. Fable v3 throughout: GATE before building, red-first TDD, fresh pasted
evidence, FIX blocks with root cause. No completion claims without evidence.

## Setup — YOU sync first, verify, then work

- **Step 0 (execute yourself; do not assume the operator pre-pulled):**
  `git status --short` (tree must be clean — if not, STOP and report; never stash blindly)
  → `git fetch origin` → confirm `git log --oneline -1 origin/master` is `b253036` **or a
  descendant** → `git checkout -b codex/signal-r4-store origin/master`.
- **Precondition guard (fail closed — ALL must hold, else STOP and report which failed):**
  1. `work/queue/WO-0134-signal-model-store-integration.md` exists on your new branch. If
     missing, the planning branch (`claude/signal-r4-kickoff-planning-354qc0`) has not
     merged to master yet — STOP; the operator must merge it first.
  2. `docs/adr/ADR-009-signal-seat-boundary.md` shows **Status: Accepted** (2026-07-21).
  3. The staging corpus is reachable:
     `git show origin/codex/signal-tests-staging:tests/test_signal_ingest_store.py | head -3`
     returns content.
  4. `work/review/REV-0039/` does NOT exist (namespace free).
- Never push master. No PR unless asked. Paper-only; zero credentials/broker/live.
- Pytest scratch goes to OS temp (default basetemp) — never repo-root scratch dirs.
- Strongest local model, full reasoning effort — this WO touches a human-gated
  schema/migration surface and rebuilds store-core planning logic.

## Operator decision block (pre-checked = ratified on paste; edit to override)

- [x] D-R4-1 **Slice correction (supersedes the WO-0128 slice map's 4-file R4 row):** R4's
      green obligation is exactly the three store-pure files —
      `tests/test_signal_seat_models.py`, `tests/test_signal_ingest_store.py`,
      `tests/test_signal_projector_forward_compat.py` — on BOTH stores.
      `tests/test_signal_quarantine_totality.py` imports the R5-owned
      `tests/signal_seat_helpers.py` app seam and CANNOT go green in R4: land its R4-owned
      symbols (`SIGNAL_TTL_MIN_SECONDS`/`SIGNAL_TTL_MAX_SECONDS` in `app.store.core`;
      `_SYMBOL_RE` already exists at `app/store/base.py:74`), paste collection evidence
      that its ONLY remaining red is the missing R5 seam, and never commit that file on
      this branch.
- [x] D-R4-2 **Constant placement follows the staged corpus**, not the archive: the six
      ingest-outcome constants + two TTL constants are importable from `app.store.core`
      exactly as the tests pin (archive kept them in `models.py` — do not follow it there).
- [x] D-R4-3 **Replay-parity registration ships in the same change** as the projector:
      `ReadModelProjection` gains a defaulted signals field, `project_read_models` folds via
      `project_signal_records`, `_describe_read_model_diff` extended.
- [x] D-R4-4 **Archive citations convert to archive-ref provenance** — never bare
      REV-0024/REV-0025 ids on master (id collision, plan §2): cite as
      `archive REV-00xx @ origin/archive/claude-wo-0001-install-checks-2x5ys8`.
- [x] D-R4-5 **Branch:** `codex/signal-r4-store` from current master; the three test files
      are pulled from the staging branch, byte-identical, never weakened.
- **NOT pre-checked and NOT pre-checkable — THE SCHEMA GATE:** the fresh `signal_records`
  schema approval happens mid-session with the actual DDL in front of the operator
  (WO-0134 "THE SCHEMA GATE" section is the binding procedure). This block does NOT
  authorize any `app/store/sqlite.py` commit.

Already ratified, binding, never re-asked: ADR-009 A-3 constants (expires_at formula, ttl
[30, 86400], skew +30s/−24h, persisted-never-re-derived); D-SIG-1..9; D-SIG-7 in
particular — no multi-exit relaxation anywhere in R4 planning logic; injective
`(producer_id, signal_id)` dedupe; `payload_hash` conflict = audit-only, never a status
change.

## Continuity across pauses and compaction

1. **FIRST commit** (with WO activation — status → ACTIVE, move to `work/active/`): create
   `work/active/SIGNAL-R4-STATE.md` containing (a) this decision block **as pasted** —
   verbatim, including any operator edits; the pasted block is authoritative over the repo
   copy of this file — and (b) a scoreboard: slice → status → commits → notes (rows:
   models.py / base.py / core.py planner / memory.py / SCHEMA GATE / sqlite.py /
   projector+replay / green evidence / REV-0039 staging).
2. Update the scoreboard at every slice boundary. WIP checkpoint commits are allowed
   (clearly marked) so no more than a few minutes of work is ever unrecoverable —
   intermediate red on this branch is acceptable; the final state must be green.
3. **After ANY pause, resume, or compaction:** re-read, in order —
   `work/queue/CODEX-KICKOFF-SIGNAL-R4.md` (this contract) →
   `work/active/SIGNAL-R4-STATE.md` (where you are) → the WO file (what you're doing).
   Verify with `git log`/`git status`, never with conversation memory.
4. The state file's schema-gate row records the operator's approval VERBATIM once given.
   A scoreboard row marked done is never silently redone.

## The work (one WO; the WO file is the full contract)

Recommended slice order — sequenced so the schema gate stalls as little as possible:

1. **Red first:** pull the three R4 test files from staging
   (`git checkout origin/codex/signal-tests-staging -- <the three paths>`); paste red
   collection evidence (today they die on the missing `app.store.core` signal constants).
2. **models.py** vocabulary (purely additive; re-derive the
   `EMERGENCY_REDUCE_OVERRIDE_RESOLVED` anchor, models.py:458 today) → **base.py**
   (`SignalIngestResult` + ABC trio) → **core.py** pure planner at the post-envelope EOF
   seam (constants, sanitizers, A-3 formula, dedupe/echo/conflict, DOA expiry,
   `cycle_budget_limit` carriage; injected clock only).
3. **As soon as the DDL is final: present THE SCHEMA GATE package** (exact DDL + `_migrate`
   hunk; field-by-field cross-check vs `01-schema.md §2` incl. the REV-0025-F nullability
   rationale; deviation list vs the archive DDL at
   `origin/archive/claude-wo-0001-install-checks-2x5ys8:app/store/sqlite.py` ~:353-383).
   **HARD STOP — wait for explicit operator approval.** Continue memory-side work while
   waiting; commit NOTHING touching sqlite.py before the approval lands.
4. **memory.py** integration inside `_atomic` (:494 today; snapshot/rollback covers the
   signal state; event + record co-write is one atomic op) → after approval, **sqlite.py**
   (DDL + `_migrate` + methods through `_insert_execution_event`, one transaction).
5. **projectors.py** `project_signal_records` (after `PositionProjector`, :731 today;
   per-record fold; `SIGNAL_DUPLICATE_CONFLICT` excluded; forward-compat per the staged
   test) + **replay.py** registration in the SAME change.
6. **Green + evidence:** three files green both stores; totality-file partial evidence
   (stage temporarily → collect → paste → delete before committing); full gate battery
   (`ruff check .`, `ruff format --check .`, `mypy app/`, `lint-imports`, `pytest -q`,
   `python tests/r2_conformance_oracle.py`, `pytest -q tests/test_wo0113_repair_scaling.py`)
   with fresh pasted output. T1.3-style producer/consumer pins for any new safety payload
   field beyond the staged pins.
7. **Stage `work/review/REV-0039/request.md`** for the Claude seat (cross-model rule):
   scope, commit list, the schema-gate approval record, evidence index, and the
   never-reviewed items called out (planner rewrite vs archive design, `_atomic`
   integration, replay-parity registration). Flip the WO to `status: REVIEW` (it stays in
   `work/active/`). **Do NOT close it, do NOT write a ledger line, do NOT merge.**

## Rules

1. Human-gated surfaces stop for explicit approval even mid-flow. In this session that is
   exactly ONE thing: the `signal_records` schema gate. The decision block above is the
   approval for exactly what it names — nothing more.
2. `app/api/**`, `app/facade/**`, `app/config.py`, `app/main.py`, launcher trio,
   `cockpit/**`, `.importlinter`, `tests/signal_seat_helpers.py`, `docs/adr/**`,
   `docs/spec/**` are FORBIDDEN paths — R5+ territory or accepted text. If green seems to
   require them, that's a finding to report, not scope to absorb.
3. Never weaken a staged test. The three ported files must remain byte-identical to their
   staging-branch versions (paste the diff evidence).
4. Evidence discipline: VERIFIED / UNVERIFIED / BLOCKED / NEEDS-INPUT only, fresh pasted
   output. Batch NEEDS-INPUT items; a confirmed P0 on a live safety surface interrupts to
   the operator immediately.
5. Ledger is append-only and untouched this session (review-gated WO).
6. End-of-session deliverable: final state-file scoreboard (slice statuses + commit ids),
   REV-0039 staged, the schema-gate approval (or BLOCKED report), NEEDS-INPUT batch, branch
   pushed. Nothing merged.

## NOT in this session

- The REV-0039 review itself (Claude seat, out-of-session, after).
- WO-0134 close-out/merge (post-disposition, planning seat coordinates).
- R5 (endpoint/auth/launcher), R6 (rails), R7 (conversion) — later rungs; R5+R6+R7 share
  the joint D-2a enablement milestone.
- Anything touching the staging branch itself (`codex/signal-tests-staging` is live and
  never deleted or merged red).
