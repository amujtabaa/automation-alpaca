# Codex kickoff — ULTRA-batch review remediation (local, strongest model)

> Paste into a FRESH local Codex session. FIRST: `git checkout codex/ultra-beta-batch &&
> git pull` — the planning seat pushed the four review results + these remediation WOs onto
> this branch. Work CONTINUES on `codex/ultra-beta-batch` (the remediation must sit on top of
> the batch code it fixes). Never push master. No PR.

---

Codex, you are the implementer seat, remediating the four independent Claude-seat reviews of
the ULTRA batch. Read `AGENTS.md`, `CLAUDE.md` safety core, and
`work/queue/REVIEW-REMEDIATION-BATCH.md` (the triage). Fable v3 throughout: GATE, red-first,
fresh pasted evidence, FIX root cause, close-out in the finishing commit. The four review
`result.md` files are already deposited in `work/review/REV-0034..0037/` — read each finding
from the reviewer's own words, not a summary.

## Continuity (this may compact)

FIRST commit: `work/active/REMEDIATION-STATE.md` with the per-WO scoreboard. Update it at every
WO boundary. After any pause/compaction re-read: this kickoff → the state file → the active WO
→ `git log`/`git status`. Never re-derive from memory.

## Setup

- Continue on `codex/ultra-beta-batch` (pulled current). One branch. Never push master.
- Paper-only; zero credentials/broker/live. Pytest scratch in OS temp, never repo-root.
- Strongest local model — two of these touch gated surfaces (release valve, event-log truth).

## The work (see each WO file for its full contract)

1. **WO-0130 — recorder retention + bootstrap venv (non-gated, do first, cheapest).** Fix
   `max_segments=1` unbounded growth (reject `<2` OR one-bounded-segment replacement) + the
   `harness/bootstrap.py` external-venv path; boundary tests red-first. Close out fully.
2. **WO-0132 — release-valve pin (REV-0035 P1-1 + P2-1).** Add the DIRECT `HUMAN_ATTESTED`
   `plan_append_fill` pin (overfill→REJECT, SELL-cross→REJECT, both stores) that turns RED under
   the `core.py:586` mutation; make the `claim_occurrence`-None branch conservative. Paste
   red→green→restored mutation evidence. Close out fully; the Claude seat re-verifies the
   mutation and appends the REV-0035 disposition out-of-session.
3. **WO-0131 — replay FSM legality (GATED event-truth).** Validate each replayed edge against
   `ENVELOPE_TRANSITIONS`; illegal edge → `ProjectionError`; exhaustive allowed/forbidden tests;
   full replay/parity/conformance corpus stays green. **End at `status: REVIEW`**, stage
   `work/review/REV-0038/request.md` for the Claude seat — do NOT close/merge it.
4. **WO-0133 — ADR-009 anchor re-baseline (REV-0034 C-1/C-2). RUN LAST** so `app/**` anchors
   settle after 0130/0132 shift `core.py`. Re-baseline/symbol-anchor the cited lines; reconcile
   the dangling `7fa9985` range to `c90a7ae..8a76a29`; ADR-009 stays **Proposed**. Close out fully.

## NOT in this session

- The REV-0035 pin re-verification and the REV-0038 replay review (Claude seat, after).
- Accepting ADR-012 / ADR-009 (operator gates).
- The advisory P2s (malformed-lineage `needs_review` record; per-child escalation; 3.12 full
  run) — recorded in the batch note as follow-ups, not this session.

## Rules

1. Human-gated surfaces stop for approval beyond what the WOs authorize. WO-0131 is gated →
   ends at REVIEW, never self-closes.
2. Separate commits per WO; ledger append-only; close-out ships with the finishing commit
   (except WO-0131, which ends at REVIEW).
3. Batch NEEDS-INPUT into one list; a confirmed P0 on a live surface interrupts to the operator
   immediately (e.g. if WO-0132 reveals `HUMAN_ATTESTED` overfill is NOT rejected today).
4. Never weaken an existing test. VERIFIED/UNVERIFIED/BLOCKED/NEEDS-INPUT only, fresh evidence.
5. End-of-session: state-file scoreboard, REV-0038 staged, NEEDS-INPUT batch, branch pushed.
   Nothing merged.
