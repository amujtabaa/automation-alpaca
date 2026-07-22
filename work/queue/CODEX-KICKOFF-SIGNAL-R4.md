# Codex kickoff — Signal Seat R4 (+ WO-0135 lineage record) (local, strongest model)

> Operator launch prompt, drafted by the planning seat 2026-07-22. Paste into a FRESH local
> Codex session at the repo root — no pre-steps needed: the session syncs itself (Setup
> step 0) and fail-closes if preconditions aren't met. Decision block below is PRE-CHECKED
> with the planning seat's recommendations: pasting it unedited RATIFIES them; edit any
> line to override. **One gate is deliberately NOT pre-asked:** the `signal_records` schema
> approval (Lane A) — Codex will HARD-STOP mid-session and present the exact DDL for your
> explicit approval (plan §10 item 9). Stay reachable for that moment or expect the session
> to end BLOCKED on the sqlite slice. **Lane B (WO-0135) has no such gate** — its design is
> fully pre-ratified and it ends at REVIEW.

---

Codex, you are the implementer seat in `automation-alpaca`, running TWO disjoint gated WOs
this session:

- **Lane A — WO-0134 — Signal Seat R4 (model + store integration)**, the first implementation
  rung of the signal-seat ladder now that ADR-009 is Accepted and G1 is clear. Human-gated
  **schema/migration** surface (the `signal_records` DDL). Ends at REVIEW → REV-0039.
- **Lane B — WO-0135 — malformed-lineage needs-review record (REV-0037 P2-1)**, a durable
  deduped recovery record for stranded corrupt cancel lineages. Human-gated **event-log-truth**
  surface, but reuse-based (no new vocabulary/table → no mid-session gate). Ends at REVIEW →
  REV-0040. Footprint is `app/monitoring.py` + tests — **disjoint from Lane A's file set**, so
  the lanes need no serialization and may run in either order or (with isolated
  agents/worktrees) concurrently.

Read `AGENTS.md`, then the `CLAUDE.md` safety core — both bind on everything. Then read BOTH
contracts IN FULL before their first commits:
`work/queue/WO-0134-signal-model-store-integration.md` (Lane A — the test-pinned symbol table,
the exact seams, THE SCHEMA GATE) and
`work/queue/WO-0135-malformed-lineage-needs-review-record.md` (Lane B — the pre-ratified reuse
design and its war-game table). Fable v3 throughout: GATE before building, red-first TDD,
fresh pasted evidence, FIX blocks with root cause. No completion claims without evidence.

## Setup — YOU sync first, verify, then work

- **Step 0 (execute yourself; do not assume the operator pre-pulled):**
  `git status --short` (tree must be clean — if not, STOP and report; never stash blindly)
  → `git fetch origin` → confirm master ancestry with
  `git merge-base --is-ancestor b253036 origin/master && echo ANCESTRY-OK` (must print
  ANCESTRY-OK; the tip itself will be NEWER than `b253036` because the planning branch
  merged — that is expected) → `git checkout -b codex/signal-r4-store origin/master`.
- **Precondition guard (fail closed — ALL must hold, else STOP and report which failed):**
  1. Both `work/queue/WO-0134-signal-model-store-integration.md` and
     `work/queue/WO-0135-malformed-lineage-needs-review-record.md` exist on your new branch.
     If either is missing, the planning branch
     (`claude/signal-r4-kickoff-planning-354qc0`) has not merged to master yet — STOP; the
     operator must merge it first.
  2. `docs/adr/ADR-009-signal-seat-boundary.md` shows **Status: Accepted** (2026-07-21) and
     `docs/adr/ADR-012-submit-recovery-operator-release.md` shows **Accepted** (2026-07-22 —
     Lane B's operator-reconcile terminal depends on it).
  3. The staging corpus is reachable:
     `git show origin/codex/signal-tests-staging:tests/test_signal_ingest_store.py | head -3`
     returns content.
  4. Neither `work/review/REV-0039/` (Lane A) nor `work/review/REV-0040/` (Lane B) exists
     (namespaces free).
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
- [x] D-R4-6 **Property-based corpus:** add `tests/test_signal_ingest_properties.py`
      (hypothesis, already pinned — no new dependency, no ADR) with the three tiers the WO
      specifies: planner invariants (A-3 exactness, skew boundaries, dedupe injectivity,
      echo-vs-conflict), outcome totality over the six constants, and metamorphic
      fold/replay equivalence — **PURE seams only, sync** (never drive async store methods
      under hypothesis; the house property idiom is sync-over-pure, and store round-trip
      parity is already example-pinned by the staged corpus). House idiom per
      `tests/test_wo0018_sellside_properties.py`; additive alongside the staged corpus,
      never a substitute; at least one property proven RED-capable via a mutation.
- **NOT pre-checked and NOT pre-checkable — THE SCHEMA GATE (Lane A only):** the fresh
  `signal_records` schema approval happens mid-session with the actual DDL in front of the
  operator (WO-0134 "THE SCHEMA GATE" section is the binding procedure). This block does NOT
  authorize any `app/store/sqlite.py` commit.

**Lane B (WO-0135 malformed-lineage record) — pre-ratified design:**

- [x] D-ML-1 **Mechanism = reuse.** Emit the durable record via the existing
      `store.create_submit_recovery(...)` seam at `app/monitoring.py:1502` — reusing the
      `SUBMIT_RECOVERY_NEEDS_REVIEW` event + `SubmitRecoveryRecord` ledger. **No new
      `ExecutionEventType`, no new table, no migration** → no mid-session gate. If reuse
      proves unsound at GATE, STOP and escalate (do NOT patch `app/store/**` or add a type).
- [x] D-ML-2 **Dedup identity** = `(local_order_id="lineage:<envelope.id>", broker_order_id="")`;
      pre-check `list_submit_recoveries()` (all statuses) for that pair and **skip create if
      any record exists in any status** — this is what makes it "one deduped needs_review" and
      what prevents the post-reconcile `RecoveryTransitionError` (war-game Hazard 2).
- [x] D-ML-3 **Scope fields = immutable envelope values only** (`symbol`, `side` SELL,
      `quantity=qty_ceiling`, `limit_price=None`, `client_order_id=envelope.id`,
      `session_id=None`) so the idempotent replay's `same_scope` always holds even as
      `remaining_quantity` drifts (Hazard 1). `remaining_quantity` + the ambiguity sets go in
      `extra_payload` only.
- [x] D-ML-4 **Reason code** = the string literal `"envelope_lineage_malformed"` kept in
      `app/monitoring.py` (NOT a new `app/models.py` constant) — keeps Lane B disjoint from
      Lane A's `models.py` edits.
- [x] D-ML-5 **Lifecycle** = resolves only via the operator's HUMAN_ATTESTED reconcile →
      `RECOVERY_OPERATOR_RECONCILED` (ADR-012, Accepted); the WO never re-flags a lineage the
      operator already dispositioned.
- [x] D-ML-6 **Log-quieting (bounded/optional)** = downgrade the `:1502` per-tick warning to
      first-detection-only; if it complicates the change, keep the warning and note it — never
      expand scope for it.

Already ratified, binding, never re-asked: ADR-009 A-3 constants (expires_at formula, ttl
[30, 86400], skew +30s/−24h, persisted-never-re-derived); D-SIG-1..9; D-SIG-7 in
particular — no multi-exit relaxation anywhere in R4 planning logic; injective
`(producer_id, signal_id)` dedupe; `payload_hash` conflict = audit-only, never a status
change. WO-0135 keeps the corrupt-lineage path **fail-closed** exactly as today (no venue
call, no guessed target) — the record is additive visibility only.

## Continuity across pauses and compaction

1. **FIRST commit** (with WO activation — set BOTH WOs' status → ACTIVE, move BOTH to
   `work/active/`): create `work/active/SIGNAL-R4-STATE.md` containing (a) this decision block
   **as pasted** — verbatim, including any operator edits; the pasted block is authoritative
   over the repo copy of this file — and (b) a two-lane scoreboard: lane → slice → status →
   commits → notes. Lane A rows: models.py / base.py / core.py planner / memory.py / SCHEMA
   GATE / sqlite.py / projector+replay / green evidence / REV-0039 staging. Lane B rows:
   monitoring.py escalation / idempotency+post-reconcile+scope pins / green evidence /
   REV-0040 staging.
2. Update the scoreboard at every slice boundary. WIP checkpoint commits are allowed
   (clearly marked) so no more than a few minutes of work is ever unrecoverable —
   intermediate red on this branch is acceptable; the final state must be green.
3. **After ANY pause, resume, or compaction:** re-read, in order —
   `work/queue/CODEX-KICKOFF-SIGNAL-R4.md` (this contract) →
   `work/active/SIGNAL-R4-STATE.md` (where you are) → the active lane's WO file (what you're
   doing). Verify with `git log`/`git status`, never with conversation memory.
4. The state file's schema-gate row records the operator's approval VERBATIM once given.
   A scoreboard row marked done is never silently redone.

## The work — Lane A: WO-0134 (the WO file is the full contract)

Recommended slice order — the schema-gate package goes FIRST because the operator who just
launched this session is still at the keyboard; approval then overlaps all the store work
instead of stalling after it:

1. **Red first:** pull the three R4 test files from staging
   (`git checkout origin/codex/signal-tests-staging -- <the three paths>`); paste red
   collection evidence (today they die on the missing `app.store.core` signal constants).
2. **Present THE SCHEMA GATE package IMMEDIATELY** — the DDL is fully derivable from
   `01-schema.md §2` + the archive reference alone and does not depend on any of your
   implementation. Package = exact DDL + `_migrate` hunk; field-by-field cross-check vs
   `01-schema.md §2` incl. the REV-0025-F nullability rationale; deviation list vs the
   archive DDL at
   `origin/archive/claude-wo-0001-install-checks-2x5ys8:app/store/sqlite.py` ~:353-383.
   **HARD STOP on the sqlite slice — wait for explicit operator approval.** Proceed with
   steps 3-4 (which never touch sqlite.py) while waiting; commit NOTHING touching
   sqlite.py before the approval lands.
3. **models.py** vocabulary (purely additive; re-derive the
   `EMERGENCY_REDUCE_OVERRIDE_RESOLVED` anchor, models.py:458 today) → **base.py**
   (`SignalIngestResult` + ABC trio; safe — the WO's pre-verified facts confirm no third
   `StateStore` subclass exists) → **core.py** pure planner at the post-envelope EOF
   seam (constants, sanitizers, A-3 formula, dedupe/echo/conflict, DOA expiry,
   `cycle_budget_limit` carriage; injected clock only).
4. **memory.py** integration inside `_atomic` (:494 today; snapshot/rollback covers the
   signal state; event + record co-write is one atomic op) → after approval, **sqlite.py**
   (DDL + `_migrate` + methods through `_insert_execution_event`, one transaction).
5. **projectors.py** `project_signal_records` (after `PositionProjector`, :731 today;
   per-record fold; `SIGNAL_DUPLICATE_CONFLICT` excluded; forward-compat per the staged
   test) + **replay.py** registration in the SAME change.
6. **Green + evidence:** three files green both stores; the D-R4-6 property corpus
   (`tests/test_signal_ingest_properties.py`, pure seams, sync) green with its
   RED-capability mutation pasted; totality-file partial evidence (stage temporarily → collect → paste →
   delete before committing); full gate battery (`ruff check .`, `ruff format --check .`,
   `mypy app/`, `lint-imports`, `pytest -q`, `python tests/r2_conformance_oracle.py`,
   `pytest -q tests/test_wo0113_repair_scaling.py`) with fresh pasted output. T1.3-style
   producer/consumer pins for any new safety payload field beyond the staged pins.
7. **Stage `work/review/REV-0039/request.md`** for the Claude seat (cross-model rule):
   scope, commit list, the schema-gate approval record, evidence index, and the
   never-reviewed items called out (planner rewrite vs archive design, `_atomic`
   integration, replay-parity registration). Flip WO-0134 to `status: REVIEW` (it stays in
   `work/active/`). **Do NOT close it, do NOT write a ledger line, do NOT merge.**

## The work — Lane B: WO-0135 (the WO file is the full contract; disjoint from Lane A)

The design is fully pre-ratified (D-ML-1..6) — **no mid-session gate**. Order:

1. **GATE (read-only):** confirm the reuse contract holds — a synthetic
   `local_order_id="lineage:<id>"` with no order row + `broker_order_id=""` +
   `RECOVERY_NEEDS_REVIEW` passes the scope-match guard, drives the WO-0132-hardened
   `claim_occurrence is None` path deterministically on BOTH stores, and dedups per tick. If
   any of that fails, **STOP and escalate** — do not patch `app/store/**` or add an event type.
2. **Red-first:** a dual-store test driving a malformed lineage
   (`missing_order_ids`/`invalid_order_ids`/`missing_envelope_ids` populated) through
   convergence asserting a `RECOVERY_NEEDS_REVIEW` record + `SUBMIT_RECOVERY_NEEDS_REVIEW`
   event — RED then GREEN, pasted. Do not build lineage-corruption scaffolding from
   scratch: `tests/test_wo0036_r2_hostile_closure.py:620-622` already constructs exactly
   this (`_terminal_envelope("missing-owner")`, `_raw_insert_envelope`,
   `_raw_seed_live_child`) — reuse/adapt those helpers.
3. **Implement** the escalation at `app/monitoring.py:1502` exactly per the WO's pre-ratified
   block (immutable scope fields; `list_submit_recoveries` pre-check; first-detection warn).
4. **The three war-game pins** (all dual-store): idempotent dedup across ≥3 ticks (one record,
   one event); post-reconcile tick does not raise and does not re-create; scope-stability
   under a `remaining_quantity` change. Plus: fail-closed posture unchanged (zero venue calls),
   replay reconstructs the record, recovery loop never auto-acts on it.
5. **Gates green** (full battery, fresh output) + **stage `work/review/REV-0040/request.md`**
   for the Claude seat (reuse rationale + the two hazard pins + dual-store/replay evidence
   index). Flip WO-0135 to `status: REVIEW`. Do NOT close/merge/ledger it.

## Rules

1. Human-gated surfaces stop for explicit approval even mid-flow. In this session that is
   exactly ONE mid-session gate: the Lane A `signal_records` schema gate. (Lane B is
   event-log truth too, but its design is pre-ratified and it clears via the REV-0040 packet,
   not a mid-session stop.) The decision block above is the approval for exactly what it
   names — nothing more.
2. **Lane discipline:** keep the two lanes' commits separate (never mix a signal-store change
   and a monitoring.py change in one commit). The lanes are file-disjoint by design — if Lane
   B ever seems to need `app/store/**`, `app/models.py`, or `app/events/**`, that is a
   STOP-and-escalate finding (reuse unsound), not scope to absorb.
3. **Lane A forbidden paths:** `app/api/**`, `app/facade/**`, `app/config.py`, `app/main.py`,
   launcher trio, `cockpit/**`, `.importlinter`, `tests/signal_seat_helpers.py`,
   `docs/adr/**`, `docs/spec/**` — R5+ territory or accepted text. If green seems to require
   them, that's a finding to report.
4. Never weaken a test. Lane A's three ported files must remain byte-identical to their
   staging-branch versions (paste the diff evidence); Lane B never weakens a recovery/
   convergence test.
5. Evidence discipline: VERIFIED / UNVERIFIED / BLOCKED / NEEDS-INPUT only, fresh pasted
   output. Batch NEEDS-INPUT items; a confirmed P0 on a live safety surface interrupts to
   the operator immediately.
6. Ledger is append-only and untouched this session (both WOs are review-gated).
7. End-of-session deliverable: final two-lane state-file scoreboard (slice statuses + commit
   ids), REV-0039 **and** REV-0040 staged, the Lane A schema-gate approval (or BLOCKED
   report), NEEDS-INPUT batch, branch pushed. Nothing merged.

## NOT in this session

- The REV-0039 (Lane A) and REV-0040 (Lane B) reviews themselves (Claude seat, out-of-session,
  after).
- WO-0134 / WO-0135 close-out/merge (post-disposition, planning seat coordinates). Lane B's
  close-out later flips the REV-0037 P2-1 advisory line in
  `work/queue/REVIEW-REMEDIATION-BATCH.md`.
- R5 (endpoint/auth/launcher), R6 (rails), R7 (conversion) — later rungs; R5+R6+R7 share
  the joint D-2a enablement milestone.
- **WO-0136 (signal-endpoint threat model, R5-prep)** — doc-only, queued for a separate
  cloud/mid-tier session per the execution preference; do NOT absorb it here.
- The other two REV-0037/0035 advisory P2s (per-child escalation isolation; full 3.12 `--cov`
  run) — still recorded backlog, not this session.
- Anything touching the staging branch itself (`codex/signal-tests-staging` is live and
  never deleted or merged red).
