# AUDIT-0003 addendum 01 — wave-2 research: registry, constitution, branches, spec drift

- **Date:** 2026-07-28
- **Trigger:** operator — "Ratify all four (P-1, P-2, P-4, P-6) and land them. Could you
  research further?"
- **Method:** four parallel fresh-context analysts over ground wave 1 did not cover: the
  invariant registry (`docs/INVARIANTS.md`); the AI-OS constitution vs. observed practice
  (`.ai-os/core/*` + templates); the three-branch topology at gate-clear time; and living-doc
  drift on the signal seat vs. HEAD code. Synthesized and every landed change verified by the
  Claude seat (Opus 5). Items marked **DONE** shipped with this addendum; **Q-items** extend the
  AUDIT-0003 ratification queue and await explicit operator ratification.
- **Authoring note:** an earlier draft of this file was produced by a research subagent that
  deviated from its read-only instruction and was left truncated; it was discarded unread-into-repo
  and this document was authored fresh from the four completed reports.

## W-1 — Invariant registry census (prices P-14)

55 entries, all carrying `*Pinned by:*`; 61 cited test files, **every one exists at HEAD**.
Exactly two non-resolving pin names — and one was worse than stale: `INV-082` cited
`test_structural_disagreement_is_also_divergence`, which exists nowhere, and whose *name asserts
the opposite* of the entry's own WO-0029A amendment. The real test,
`test_structural_disagreement_is_a_stale_refusal` (`tests/test_wo0019_engine_seam.py:293`),
asserts stale-refusal-not-divergence. A round-3 reviewer trusting that registry line would have
reached a wrong freeze-behaviour conclusion. `INV-085`'s pin was cited under its pre-rename name.
**DONE (`f159149`):** both citations repaired with dated notes.

Remaining registry weaknesses, ranked: `INV-051` (lock reentrancy = whole-process deadlock; zero
tests), `INV-052` (broker IO under the store lock; "structural" prose only — an AST scan for
`await`-on-adapter-inside-lock is feasible and absent), `INV-060`'s universal kill-switch claim
outrunning its three named scenario pins, `INV-030`'s unverifiable "model-level validator tests"
citation. The census prices P-14 concretely: landing debt is near zero (2 sentinel entries, 1
vague citation, now 0 broken names), and the check's real payoff is its same-commit-touch clause —
an INV text change must touch its named enforcement or carry a dated no-op sentinel — which is
exactly what would have caught the INV-082 drift mechanically. **Q-14 (revised):** P-14 is cheap;
recommend ratifying it as its own small work order.

## W-2 — Constitution vs. case law: the problem is placement, not content

Nine rules already existed on paper whose violations produced AUDIT-0003's findings. The
result→disposition→ledger ordering was already "Critical" in `15_CROSS_MODEL_REVIEW.md:45-51` when
REV-0022's acceptance raced its unpushed result; a WO size budget already existed
(`13_SESSION_LENGTH:53`, "1-3 pages") when the 1,067-line and 87 KB work orders were ratified; the
PROC-0001 incident carry-forward was mandated into an *instance* (`13:192-198`) and died when that
state file retired; the INV probe obligation names its own failure mode (`15:63-72`) but ships no
checker. The through-line, in the analyst's words: **every rule that bit had reached either
`ci.yml` or a template a seat actually instantiates; every rule that failed lived as prose in a
core file or an instance.** The constitution's problem is placement, not content — which is
precisely why the four just-ratified controls were placed in templates and CI gates rather than
prose.

Contradictions worth fixing (none blocking): **C1** two "canonical" Fable v3 texts disagree on the
evidence grammar (`06_FABLE:31,63-66` has `phase:`/`BLOCKED`; `templates/fable-core-v3.md:31-34`
and `.claude/skills/fable/SKILL.md:28` drop them) — whatever `check_fable_done.py` parses, at least
one dialect fails it; **C2** two verdict vocabularies (`review-checklist.md:44` says
`APPROVE|REQUEST-CHANGES|BLOCK`; the packet protocol says `ACCEPT|ACCEPT-WITH-CHANGES|BLOCK`);
**C4** `12_WORK_ORDER_RETENTION:41-49` still models a *periodic* disposition pass, contradicting the
repo's atomic close-out rule. **DONE (this addendum):** removed the phantom `audit_harness/` row
from the repo primer (the directory does not exist; replay/parity live in `tests/*parity*.py`).
**Q-A:** reconcile C1/C2/C4 and finally wire `check_fable_done.py` into CI — folds into P-13.

## W-3 — Branch topology at gate-clear (integration-risk map)

The "three-branch" split is really two lines: the planning branch
`claude/signal-r4-kickoff-planning-354qc0` is **fully contained in master** (0 ahead), so master is
the only integration source. Working branch vs `origin/master` (`6d59374`): merge-base `6955208`,
**zero file-level overlap** (`comm -12` of both changed-file sets is empty). The split was
artefactual: the REV-0044 result + addendum-01 and the WO-0140 queue file existed only on master,
while this branch's REV-0045 packet and state file reference them — dangling cross-branch
references. **DONE (this addendum):** merged `origin/master` into the working branch
(conflict-free), reuniting REV-0044's request (here) with its result + addendum-01 (from master)
and bringing the WO-0140 file on-branch.

Three integration hazards recorded for the eventual gate-clear close-out, none yet actionable
because the gate is still BLOCK:

1. **Round-3 review head.** Four commits post-date the round-2 review head and sit on gated
   surfaces (ADR-014, ADR-015, the CI gates, this doc set). A clearing REV-0045 addendum-03 must
   state its reviewed head explicitly, or those changes merge on self-review only — a gap the rev-3
   ratification could not anticipate because ADR-014/015 post-date it.
2. **WO-0104a is the orphan risk.** WO-0140's close-out text closes WO-0140 atomically but is silent
   on WO-0104a, whose REV-0044 gating items (R-1/R-2) were the entire point. **REV-0044
   addendum-01's operator-database caveat on R-1** ("not live against the operator's database") lives
   only in the newly-merged file and must be explicitly discharged at WO-0104a close-out or it
   vanishes into `work/completed/` unexamined. Two ledger lines are owed, not one.
3. **Vocabulary grep-miss.** Post-merge, the live `work/queue/WO-0140` file names the pre-ADR-014
   identifiers that no longer exist in code. A reviewer verifying its closed test-edit list by grep
   finds nothing and could wrongly conclude the ratified pins were dropped. The close-out disposition
   must cite the ADR-014 mapping table; once WO-0140 moves to `work/completed/` it is legitimately
   historical.

## W-4 — Living-doc drift on the signal seat (six MUST-FIX, all landed)

The next independent review reads these documents against HEAD code; stale claims generate false
findings and cost reviewer trust. Six statements would have led a reviewer to a wrong conclusion —
all corrected in this addendum's doc commit:

1. `02-lifecycle.md:54` — `PRODUCER_QUARANTINED` payload was described loosely; now enumerates the
   CLOSED exact field set and the exact-next `epoch_sequence` chain rule.
2. `02-lifecycle.md:55` — release row now states every dedupe key is parsed and producer-bound
   (not only heals), the exact-next (not merely higher) rule, and the total-inverse decoder over
   separator-bearing ids.
3. `02-lifecycle.md §4` — added the strict/tolerant duality, the never-persisted
   `InvalidProjectionMarker`, the single-source `contributed_epoch_sequence` rule, and the durable
   sink guard; the section previously described only the strict pure fold, from which a reviewer
   would conclude an unfoldable history must halt the store (HEAD deliberately opens).
4. `04-auth-and-api.md:162` — release responses now cover the three-state reality (200 = close OR
   no-epoch heal; 409 = healthy mid-cycle incl. drift repaired-and-retained).
5. `03-rails.md §5` — the canonical release section gained the three-state log-classified release.
6. `THREAT_MODEL_SIGNAL_SEAT.md §7` — GAP-01..06 annotated SATISFIED (R5a/R5b, REV-0041/42/43),
   GAP-08 PARTIALLY SATISFIED (R6a store surface; R6b remainder), so delivered controls no longer
   read as unbuilt.

Cosmetic, also landed: pkl `last_verified` → 2026-07-28; pkl changelog reordered (07-26 now
precedes 07-27); the markers/heal/single-source facts promoted from the pkl changelog into its
Rules bullet. Vocabulary is otherwise clean — no living signal-seat doc still uses the pre-ADR-014
identifiers.

**Q-B (undocumented behavior, not yet placed):** four load-bearing semantics exist in code with no
living-doc home beyond what this addendum added — the total-inverse decoder key format
(`producer_release:{len}:{pid}|{len}:{seq}`) belongs in `01-schema.md §3`; and the threat model
could gain rows (T-25/T-26) for the now-controlled degenerate-log-content and write-free-refusal
classes REV-0045 audited. Deferred to a spec-refresh work order rather than expanded here.

## Net

Wave 2 landed six MUST-FIX doc corrections, two stale INV citations, one phantom primer row, and
the master merge that de-orphans the REV-0044 artifacts — all mechanical, no behavior change, full
hygiene sweep green. It added no code. The queue gains Q-14 (P-14 is cheap — ratify), Q-A (protocol
reconciliation, folds into P-13), and Q-B (a spec-refresh WO for undocumented decoder/threat-model
detail). Gate state unchanged: REV-0045 Codex-owned, R-1/R-2 open, D-2a OFF, R6b blocked. The
integration-risk map (W-3) is the operative artifact for whenever the gate does clear.
