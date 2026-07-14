# PROC-0001 — Working-practices sweep (result packet)

**Run provenance:** workflow `wf_7f8d0773-aac` — 26 agents (6 sonnet audit lenses, sonnet
refuters with default-refute bias, opus synthesis), 0 errors, 1.09M subagent tokens, ~22 min.
Yield: 3 confirmed changes from a larger raw set; 16 practices explicitly
HELD as good. Raw per-agent returns in the workflow journal.

**Verification note (fresh, by the synthesizer):** the INV coverage gap reproduces —
`comm -23` of INV-IDs defined in docs/INVARIANTS.md vs INV-IDs ever cited under work/review/
returns **INV-078, INV-079, INV-080, INV-085** — all envelope safety invariants, none ever
independently re-probed by a review packet. Recorded as a standing input to the NEXT
review packet (Phase B reconciliation) per plan item 3. CORRECTION (orchestrator, same day):
once this packet itself was written, the naive `comm -23` scan reads CLEAN — because this
file MENTIONS the four IDs. That is the self-citation trap; the plan's own wording ("fresh-
probe line, not a mention") is the real bar, and the four IDs still lack fresh probes. The
gate check must therefore grep for probe evidence, not bare citations — requirement now
embedded in REV-0023/phase-b-reconciliation.md.

---

All four load-bearing facts verified against the repo: the INV gap (`INV-078/079/080/085` never referenced in `work/review/`), both git-checkout incident quotes verbatim, the v3.1 test-framing amendment, and the R4 mutation-sweep rule location. Synthesis follows.

---

# Alpaca Spine v2 — Working-Practices Improvement Plan

Scope: process, not code. Question answered for each change: *what earlier miss would this have caught, and what does it cost forever after.* Three changes, ranked by misses-prevented ÷ ongoing-cost. All three fit on one page and touch only files that already exist.

## The through-line

Two of the three failures this repo actually logged share one root cause: **a lesson was learned locally and never promoted to a standing surface, so it had to be re-learned.** The git-checkout wipe recurred *verbatim 11 WOs apart* (WO-0017 → WO-0028) because its fix lived in one closing file. Four safety invariants added as REV-0023 remediation have *never been independently re-probed* because nothing forces the check. The plan's spine is: **make the transfer structural, not memory-dependent.**

---

## 1. Carry-forward incidents into the running state file — *trivial cost, broadest coverage*

**Miss it prevents.** The single highest-confidence recurrence in the record. The wipe was recorded only inside each WO's own `fable-done.md`, invisible to the next WO.

- `work/completed/keep/WO-0017-envelope-approval-and-precedence/fable-done.md`: *"One toolchain slip during the mutation check: a reflexive `git checkout app/store/sqlite.py` reverted the uncommitted WO changes…"*
- 11 WOs later, `work/completed/keep/WO-0028-test-integrity-and-memory-atomicity/fable-done.md`: *"Repeat of the WO-0017 git-checkout incident… Root cause: same as last time — reflexive `git checkout` on a file carrying uncommitted work."*
- `work/active/W3-STATE.md:74` — the `deferred log` section holds only design deferrals (`intent→ORDERED linkage`, container-shim note) — it has no slot for "things that will bite the next WO mechanically." (Verified: line 86 already carries one toolchain note, but under *deferred log*, and the git-checkout class never reached it.)

**Exact edit.**
1. Add a permanent (never-pruned) top-level field to `work/active/W3-STATE.md`:
   ```
   toolchain-incidents (must-read before any destructive git op):
     - WO-0017/WO-0028: reflexive `git checkout <file>` wipes UNCOMMITTED WO work.
       Commit or stash before any mutation run; restore only committed code.
   ```
2. Add one line to the Fable DONE-block close-out step (`.ai-os/core/13_SESSION_LENGTH_AND_CONTEXT_HYGIENE.md` hygiene checklist): *"If this WO's `fable-done.md` has an `## Incidents (visible)` section, copy it verbatim into `W3-STATE.md`'s `toolchain-incidents` field before merge."*

**Why #1.** Trivial and catches *any* future incident class, not just this one — it converts every honestly-logged slip (a practice the audit found is working) into a standing warning for the next agent, at the cost of one copy-paste at a fixed checklist step.

---

## 2. Commit-before-mutate rule into the mutation protocol — *trivial cost, hardens the exact recurrence*

**Miss it prevents.** Same incident, closed from the other side. WO-0028 *already* fixed the working practice mid-WO (*"everything is committed BEFORE any mutation run"*) — but that fix lived in WO-0028's local narrative, not in the doc that defines the mutation sweep, so a third occurrence stays possible.

- `.ai-os/core/17_INTERNAL_ADVERSARIAL_REVIEW.md:50` defines **R4 — Discovery mutation sweep**; the restore-via-`git checkout` step is exactly where the wipe happens, and the doc says nothing about tree-cleanliness first.

**Exact edit.** Append one sentence to R4 (and its R6 companion) in `17_INTERNAL_ADVERSARIAL_REVIEW.md`:
> Before any mutation is applied, the working tree must be clean (`git status --porcelain` empty) — commit or stash first. Mutation scripts restore via `git checkout` only ever on committed code.

**Why paired with #1, not merged.** #1 propagates the *warning*; #2 writes the *prevention rule* into the one procedure where the failure fires. Belt-and-suspenders on the only failure this repo logged twice, for two one-line edits.

---

## 3. Force fresh independent review of newly-added invariants — *moderate cost, highest stakes*

**Miss it prevents.** The SOL-0001-shaped miss: `work/collab/SOL-0001/findings.md` + `incumbent-findings-triage.md` show two P0s surviving four internal critics on already-reviewed code. The analogous latent gap today:

- `comm -23` of INV-IDs *defined* in `docs/INVARIANTS.md` against INV-IDs *ever cited* across `work/review/` (41 files, 35 `REV-*` dirs) returns **INV-078, INV-079, INV-080, INV-085** — all execution-envelope safety invariants (bounds immutability, terminal-freeze, breach-never-completes) added by WO-0016/WO-0017/WO-0029A as REV-0023 Phase A remediation. **None has ever been cited by a review packet.** Each has only its own pinning test passing — the same "critic never attacked it" shape as SOL-F-002/F-003.
- `CLAUDE.md` requires independent review to gate *"human-gated safety surfaces… before any beta-relevant milestone relies on them"* — but nothing checks that a *new* invariant was re-probed vs. merely self-pinned. Posture is *cleanup → full-repo audit → beta roadmap*, so beta is about to rely on exactly these.

**Exact edit.**
1. Review-packet template (`work/review/REV-*/`, protocol `.ai-os/core/15_CROSS_MODEL_REVIEW.md`): add a required line — *"List every `INV-*` added or amended since the last review milestone; confirm each has ≥1 fresh-probe line in THIS packet (not a rerun of its own pinning test)."*
2. Before any beta-relevant milestone, run as a review-gate blocker:
   ```
   comm -23 <(grep -oE 'INV-[0-9]+' docs/INVARIANTS.md | sort -u) \
            <(grep -rhoE 'INV-[0-9]+' work/review | sort -u)
   ```
   A non-empty result blocks the gate for *those IDs specifically*.

**Why #3 not #1.** Highest stakes (safety invariants a beta will lean on) but moderate ongoing cost — it adds a recurring per-milestone check and a packet-template obligation — so its ratio sits below the two trivial edits. Do it before the beta milestone, not this week's WO.

---

## Do-not-add list (refuted / bloat — recorded so they aren't re-proposed)

- **A standalone "process-gotchas" doc.** A doc nobody can hold in their head is itself a process failure. The incident-carry-forward belongs *in the state file the next agent already reads* (#1), not in a new file that goes stale. Rejected on the same principle the task states.
- **A per-WO independent cross-model review.** `CLAUDE.md` deliberately batches independent review at milestones, and `16_CROSS_MODEL_BUILD.md` + the SOL-0001 crosswise triage (drift-ledger caught `DRIFT-SVD-2`) show the milestone cadence *working*. #3 adds a targeted gate at the existing milestone boundary, not a new per-WO seat.
- **Rewriting the mutation-matrix format.** Already legible where run correctly — WO-0028 (14/14 KILLED, per-mutation counts) and WO-0024 (MC1 10 failures / MC2 2 failures) name exact kill counts, which is precisely what made the WO-0029A `-k`-no-op stand out. No change; the format is the reason anomalies surface.
- **A new "honesty" or self-audit norm.** The transparency norm is already working — every incident here was self-reported in `fable-done.md`, never discovered externally. The gap is *prevention/propagation*, not honesty. Adding an honesty rule would target a non-problem.
- **Duplicating the INV check inside CI.** Keep it a review-gate step, not a CI blocker — CI runs per-commit and would fire on every in-flight invariant mid-WO (noise); the check is meaningful only at the milestone boundary. `.importlinter`-style double-enforcement is right for import boundaries, wrong here.
- **Auto-committing before mutation runs (a hook).** Tempting but wrong: silent auto-commit would bury the WIP-vs-committed boundary the operator needs to see. The fix is a *tree-clean precondition* (#2), which makes the agent commit *intentionally* — not a hook that hides the state.

---

## Gate assignment

**Needs Ameen's gate (OS/template edits — human-gated per `CLAUDE.md` ClaudeFast rules):**
- #1 — the checklist line added to `.ai-os/core/13_SESSION_LENGTH_AND_CONTEXT_HYGIENE.md`.
- #2 — the R4/R6 rule added to `.ai-os/core/17_INTERNAL_ADVERSARIAL_REVIEW.md`.
- #3 — the review-packet template obligation + `.ai-os/core/15_CROSS_MODEL_REVIEW.md` step. (Touches the review gate for safety surfaces → gated by definition.)

**Implementation seat may apply under standing discipline (mechanical, no doc-semantics change):**
- #1 — adding the `toolchain-incidents` field to the live `work/active/W3-STATE.md` instance and back-filling the WO-0017/WO-0028 line.
- #3 — running the `comm -23` command as a standing check and reporting the four uncovered IDs into the next review packet.

All three doc edits are one-to-three lines each; the whole plan is the state-file field + two protocol sentences + one milestone check.

---

## Practices audited and HELD good (keep as-is)

- Incident notes in fable-done.md are written honestly when a slip is caught: WO-0017 ('One toolchain slip during the mutation check: a reflexive git checkout app/store/sqlite.py reverted the uncommitted WO changes') and WO-0029A ('the FIRST MC-2 run reported 0 failures because the nested-shell -k expression selected no tests -- re-run with explicit test ids before trusting it. Recorded so the matrix stays honest.') show the self-audit culture working after the fact -- keep this incident-note practice; it is the only reason these episodes are visible to this audit at all.
- The v3.1 test-framing amendment (fable-core-v3.md lines 64-81) is a real, dated, causally-grounded protocol update naming the SOL-0001 lesson with two concrete generalizable rules (invariant-frame rule, boundary-of-trust rule) rather than a vague 'be more careful'. This is the right shape for a protocol amendment and should be the template for new ones.
- Mutation-matrix discipline, once run correctly, is legible: WO-0028 ('Mutation matrix: 14/14 KILLED... each mutation applied to committed code, targeted scope run, git checkout restore') and WO-0024 ('MC1 redrive-refusal disabled -> 10 failures... MC2 memory sweep disabled -> 2 failures... per-store isolation intact') name exact failure counts per mutation rather than a bare pass/fail, which is what let the WO-0029A -k selector no-op stand out as an anomaly worth catching.
- Module-semantics attacker lens (17_INTERNAL_ADVERSARIAL_REVIEW.md, added v1.0 'by this document') is a direct, well-targeted fix for the exact SOL-0001 residual (SOL-F-002/F-003 survived four internal critics because 'no lens ever attacked the pure-math internals') — keep as-is, it names the failure mode it was built for.
- R7-R9 (tiering, per-agent budgets, fan-out sizing) read as calibrated against real friction (heartbeat rule R11 explicitly anticipates 'thorough LOOKS stuck on a 2-slot box') rather than generic advice — no gap found against the evidence read.
- Cross-model build's 8 rules (16_CROSS_MODEL_BUILD.md) plus the SOL-0001 crosswise triage show the frozen-contract-seam + drift-ledger + intake-checklist combination actually working: incumbent-findings-triage.md cites 'DRIFT-SVD-2 (from the crosswise run — OUR WO-0029A regression)' being caught, i.e. the drift ledger did its job. No change proposed here.
- The registry is genuinely used as a live oracle, not write-only: grep -rl "INV-" work/review hits 41 files across the large majority of the 35 REV-*/ dirs (e.g. work/review/REV-0023/phase-a.md, REV-0002/REV-0007/REV-0008/REV-0019 request+result+disposition triads, CAMPAIGN-0001/synthesis.md). Findings are explicitly framed against named IDs (e.g. INV-084's own docstring: 'the flipped P0 finding pin' -> tests/test_rev0023_phase_a_pins.py::test_PIN_F1_sell_against_zero_position_never_reaches_venue). Keep citing INV-IDs by number in every review packet.
- Most entries name an observable scope precisely instead of leaning on bare 'never'/'always': INV-070-074 name the exact modules/tests proving a transitive import property (INV-070 cites both a direct-proof test and a separate transitive-proof test), and INV-032 pins the single canonical function (app.store.core.sell_intent_is_active) rather than a vague behavioral claim. This precision is what let REV-0023 Phase A and the SOL-0001 crosswise intake (work/collab/SOL-0001/incumbent-findings-triage.md, row SOL-F-001 citing INV-084 directly) disagree productively about remediation status instead of talking past each other.
- Ledger discipline itself is solid: work/ledger.jsonl entries consistently record status/disposition/commit/reason with specific evidence (test counts, mutation kills, gate results) — e.g. WO-0026, WO-0024 entries — so the audit trail is legible and this doesn't need changing.
- When a WIP-wipe or gate-claim error was caught, it was recorded honestly in fable-done.md rather than suppressed (WO-0028: 'Repeat of the WO-0017 git-checkout incident' and 'WO-0021 gate-claim correction: baseline ruff check was RED at the merged tip f092ca7' are both self-reported, not discovered externally) — the transparency norm is working even though the prevention norm isn't.
- W3-STATE.md's per-WO 'completed' entries (git log -p, e.g. commit 15e6a81, 9fcd4dd) already carry rich carry-forward metadata per WO -- SHA, verdict, disposition, and a pointer to work/completed/keep/WO-000X-*/fable-done.md -- so a fresh session can locate primary evidence without re-deriving it. Keep this pattern.
- The 'anchor-divergences' and 'open decisions' sections of W3-STATE.md are already structurally separate from the narrative 'completed'/'in-flight' prose, and both are consistently updated commit-over-commit (visible across all 10 W3-STATE.md revisions in git log). This separation is working and should not be collapsed back into prose.
- The 'Gate/toolchain reference' section pinning exact tool versions (ruff 0.15.20 / mypy 2.2.0 / pytest 9.1.1 / import-linter 2.13 == constraints.txt) in W3-STATE.md is a good concrete anti-drift artifact and should be retained as-is.
- constraints.txt is already the right fix for dependency drift and is well-documented: its header explains the mypy 2.x + numpy 2.5 / Hypothesis drift incident, and CI already installs with `pip install -r requirements.txt -c constraints.txt` (.github/workflows/ci.yml). No change needed beyond making local/session installs consistent with CI (see P1).
- conftest.py / pyproject.toml already fix the sqlite ResourceWarning leak (F-008) and the Python 3.13 PytestUnraisableExceptionWarning wrapper (AIR-011) via `filterwarnings = ["error::ResourceWarning", "error::pytest.PytestUnraisableExceptionWarning"]` -- a real prior incident correctly promoted to a hard suite failure. Keep as-is.
- import-linter contracts (.importlinter) are enforced twice by design -- once as CI's `lint-imports` step and again inside tests/test_import_boundaries.py -- so the boundary gate survives even if the CI step definition is ever edited or removed; the file's own header states this is intentional. Keep the redundancy.
