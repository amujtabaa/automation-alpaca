# Codex kickoff — R4 pin-fix (REV-0039 F1/F2; tests-only, no gates)

> Operator launch prompt, drafted by the planning seat 2026-07-22. Paste into a FRESH local
> Codex session at the repo root. Small session: two tests-only changes closing REV-0039's
> ACCEPT-WITH-CHANGES required items. No mid-session gates, no new WO, no decisions beyond
> the pre-checked block.

---

Codex, you are the implementer seat closing the two required changes from the REV-0039
independent review (ACCEPT-WITH-CHANGES) of WO-0134. Both are **tests only — zero source
edits**. Read `AGENTS.md`, the `CLAUDE.md` safety core, then
`work/review/REV-0039/result.md` findings **F1** and **F2** in the reviewer's own words,
and `work/active/WO-0134-signal-model-store-integration.md` (still the binding contract;
it stays `status: REVIEW`). Fable v3: red-first, fresh pasted evidence, no completion
claims without evidence.

## Setup — sync first, fail closed

- **Step 0:** `git status --short` clean (else STOP) → `git fetch origin` →
  `git checkout codex/signal-r4-store` → `git pull --ff-only origin codex/signal-r4-store`.
- **Precondition guard:** `work/review/REV-0039/result.md` (verdict ACCEPT-WITH-CHANGES),
  `work/review/REV-0040/result.md`, and this kickoff file all exist on the branch — they
  are the planning-seat deposit. Any missing → the pull did not land it → STOP and report.
- Never push master. No PR. Paper-only. Pytest scratch in OS temp, never repo-root.

## Decision block (pre-checked = ratified on paste; edit to override)

- [x] D-PIN-1: the pins land under WO-0134's existing scope (`tests/**` allowed path) —
      **no new WO, no ledger line**; WO-0134 remains `status: REVIEW`; REV-0039's
      disposition stays open until the Claude seat re-verifies both reviewer mutations
      turn RED against the new pins.
- [x] D-PIN-2: **zero source edits authorized.** If either pin cannot be written without
      touching `app/**`, STOP and report — that would falsify the reviewer's tests-only
      framing and is a finding, not scope to absorb.
- [x] D-PIN-3: F3–F6 are R5 planning inputs — explicitly NOT this session. Do not touch
      the hypothesis strategies (F3), the projector's never-born no-op (F4), the memory
      snapshot depth (F5), or the sanitizer/hash scope (F6).

## The work

1. **F1 — aggregate replay-parity signals pins** (REV-0039 result.md F1; both parts):
   (a) extend `test_compare_read_models_detects_divergence`
   (`tests/test_phase6b_readmodel_parity.py`) with a `signals` perturbation — a
   `replace(base, signals={…})` case asserting `ok is False` AND that the describing
   detail names the diverging signal;
   (b) add one aggregate parity test that **ingests a real signal on BOTH stores** and
   asserts `verify_dual_store_readmodel_parity(...).ok` AND a non-empty `.signals` on the
   projection — killing the equal-but-both-empty false positive the reviewer named.
2. **F2 — memory `_atomic` signal-rollback pin:** a memory-store twin of
   `test_signal_event_and_record_rollback_together` — inject a failure mid-ingest
   (monkeypatch the event append or an equivalent post-write seam), assert
   `get_signal(...)` is `None` AND `get_execution_events()` is empty afterwards, AND that
   a subsequent clean ingest succeeds (store not wedged).
3. **Red-first proof against the reviewer's exact surviving mutations — this is the
   acceptance bar:**
   - **M7a:** temporarily remove `signals=project_signal_records(materialized)` from
     `project_read_models` (`app/events/replay.py:195`) → BOTH new F1 pins must turn RED.
     Restore byte-exact.
   - **M4a:** temporarily remove the `self._signals = saved_signals` restore line from
     memory `_atomic` (`app/store/memory.py:555` today) → the F2 pin must turn RED.
     Restore byte-exact.
   - Paste RED and restored-GREEN output for each; `git diff -- app/` must be EMPTY in the
     finishing state (verify and paste).
4. **Full battery green, fresh output:** `ruff check .`, `ruff format --check .` (the
   bounded 10-file exception stands — your new/changed test files must introduce NO new
   formatting finding), `mypy app/`, `lint-imports`, `pytest -q`,
   `python -m pytest -q tests/r2_conformance_oracle.py`,
   `pytest -q tests/test_wo0113_repair_scaling.py`.
5. Update the `work/active/SIGNAL-R4-STATE.md` scoreboard (add a pin-fix row with commit
   ids) and append the evidence to WO-0134's Fable record. WO stays `REVIEW`. Push the
   branch. Nothing merged, no ledger line, no disposition edit (the reviewer owns
   `result.md`; the disposition is appended by the Claude seat after re-verification).

## NOT in this session

- The REV-0039 mutation re-verification and disposition (Claude seat, after).
- WO-0134 close-out/merge; anything WO-0135; R5/R6/R7; WO-0136.
- Any `app/**` change whatsoever.
