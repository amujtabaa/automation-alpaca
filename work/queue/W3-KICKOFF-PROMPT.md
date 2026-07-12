# W3 KICKOFF — paste this whole file as the first message of a fresh Claude Code session

You are the implementation seat for the W3 Execution Envelope wave in `amujtabaa/automation-alpaca`.
Fable v3 is in force (`.claude/skills/fable`; canonical `.ai-os/templates/fable-core-v3.md`).
CLAUDE.md's safety core binds inside every task. This prompt is your standing work authorization
("campaign order") for the whole wave; it does not waive any gate listed under HUMAN CHECKPOINTS.

## Operating agreement (ratified by the human pasting this prompt)

- The wave plan (`work/queue/W3-README.md` + WO-0016..0022 + `docs/adr/ADR-010-execution-envelope.md`)
  is the pre-approved plan of record. Wave-level planning does not need re-approval.
- **Non-gated WOs (0018, 0020, 0021): proceed end-to-end without pausing**, under full Fable
  discipline (gate block, TDD, pasted evidence, done block, disposition + ledger entry each).
- **Gated WOs (0016 migration, 0017 kill/flatten precedence, 0019 submission/cancel-replace):
  post the FABLE gate block and the exact planned diff surface, then STOP and wait** for explicit
  approval in-chat before writing production code. Never auto-approve; `cf-approve` stays
  deny-by-default.
- Any conflict between this prompt and CLAUDE.md → CLAUDE.md wins; stop and say so.

## Bootstrap (Step 0 — do this first, paste evidence for each)

1. `git status && git log --oneline -3` — confirm clean tree; confirm you are on the current dev
   tip (`claude/fable-mode-os-install-1dlyk8` or its merged successor). If dirty or ambiguous: STOP.
2. Locate the planning drop: either its files are already at repo root (check for
   `START_HERE.md` + `docs/adr/ADR-010-execution-envelope.md`) or the human placed
   `lase-envelope-wave-W3.zip` at repo root (`unzip -o` it, then remove the zip). Neither
   present: ask the human.
3. `git checkout -b feat/execution-envelope && git add docs work && git commit -m "W3: ADR-010 (Proposed) + WO-0016..0022 planning drop"`
   — the pinned in-repo spec, first commit on the integration branch.
4. Baseline gate on this tip: `ruff check . && ruff format --check . && mypy && lint-imports && pytest -q`
   — paste the tail. Red baseline: STOP, NEEDS-INPUT.
5. **Anchor re-verification** (the WOs were drafted from a 2026-07-11 snapshot): for each WO,
   confirm its named files/functions exist at tip (`plan_flatten_position`, approval gate ABC,
   `SELL_INTENT_TRANSITIONS`, MarketSnapshot shape, ENG-001 atomic exit-open). Divergences: list
   them, amend the WO's context packet in a commit, note it in the state file. Do not silently adapt.
6. Create `work/active/W3-STATE.md` (template at bottom). This file is the session's memory:
   update it after every WO disposition and re-read it plus `W3-README.md` first after ANY context
   compaction — trust the artifact over recollection.

## Execution loop (per W3-README sequencing)

For each WO in order 0016 → (0017 ∥ 0018) → 0019 → 0020 → 0021:

1. `git checkout -b feat/execution-envelope/wo-00XX feat/execution-envelope`
2. Read ONLY the WO's context packet (for WO-0018 this includes
   `pkl/architecture/sellside-research-notes.md`). Post the FABLE gate block restating goal/done_when.
3. Gated WO → STOP for approval (see agreement). Non-gated → proceed.
4. TDD per Fable; respect allowed/forbidden paths as hard scope; out-of-scope observations go to
   the state file's deferred log, never fixed.
5. Close: fable_done block with pasted evidence, full gate green
   (`ruff && ruff format --check && mypy && lint-imports && pytest -q`), disposition + ledger
   entry, merge the WO branch back to `feat/execution-envelope`, delete the WO branch, update
   W3-STATE.md, move the WO file queue→completed.
6. Context hygiene: after merging each WO, `/clear` (or equivalent) and re-enter via
   W3-STATE.md + the next WO. Do not carry implementation context across WOs — WO-0022 Phase A
   requires reviewers that did not author what they review.

**0017 ∥ 0018 fan-out:** if running in one session, do them sequentially (0018 first — no gate
wait). If the human has set up two worktrees per W3-README, 0018 runs there; never let 0018 touch
`app/models.py`, and its test files must be new files named per-WO.

**WO-0019 tripwire:** before its gate, verify the broker adapter exposes a usable replace/edit
call (cf. `work/review/FINDING-alpaca-adapter-wrong-sdk-method.md`). Absent → NEEDS-INPUT, stop
that WO; do not widen into `app/broker/**`.

## WO-0022 — adversarial phase (after 0016..0021 dispositioned)

Phase A: spawn the four critic subagents (spec-attacker, interleaving-attacker, test-critic,
completeness-critic) per WO-0022, **inlining its H1–H11 block verbatim in every agent prompt** —
subagents do not load CLAUDE.md. Each agent gets a fresh context and the pinned tip SHA. Compile
`work/review/REV-00XX/phase-a.md`. Findings → FINDING files + draft follow-up WOs; fix nothing.

Phase B: pin the tip SHA into `work/review/W3-codex-review-prompt.md`, then STOP — hand to the
human to run Codex on the authoritative env. Do not proceed past this point.

## HUMAN CHECKPOINTS (the complete list — everything else is yours)

- T1 WO-0016 gate approval (schema migration)
- T2 WO-0017 gate approval (kill-switch / flatten precedence)
- T3 WO-0019 gate approval (order submission / cancel-replace seam)
- T4 WO-0022 Phase B: human runs Codex, returns the verdict for reconciliation
- T5 ADR-010 Accepted mark + merge decision (never yours)
- Any NEEDS-INPUT / BLOCKED / circuit-breaker (3 failed fixes) / anchor divergence on a safety
  surface

At every checkpoint: post exactly what you need decided, the options, and your recommendation,
then stop. If the session must end mid-wave, write the Fable handoff (done-with-commits /
in-flight-exact-next-step / open decisions / deferred log) into W3-STATE.md.

## W3-STATE.md template

```
# W3 state — updated <ts>, tip <sha>
approved-agreement: this kickoff prompt, pasted <date>
completed: [WO-0016: <sha>, disposition, ...]
in-flight: <WO id, exact next step>
awaiting: <checkpoint id or none>
anchor-divergences: []
deferred log (out-of-scope observations): []
open decisions: []
```
