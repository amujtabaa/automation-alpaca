# Part B completion run — goal prompt (DRAFT: awaiting D1–D8 ratification)

> **Purpose.** One ratification message from the operator, then an uninterrupted run that takes
> `consolidate/r2-canonical` from its current state (`54fd817`) to the point where **the only thing
> standing between the trunk and a master PR is the human-commissioned cross-model review**
> (REV-0029) and its disposition loop. Built-in adversarial checks (third-party clear-eyes lens)
> run at every phase. All human decisions are batched **up front** (§1); the standing rules (§3)
> make every anticipated mid-run stop either pre-authorized or parkable.

## §0 Endpoint (definition of done for this run)

1. Full §H.4 acceptance gate green, including the **reseeded Codex oracle** and both perf gates,
   with pasted evidence + UTC timestamps.
2. All four planes reconciled: code (grafts + properties), docs (ADR-010 amendment, INV-090,
   invariant re-verify, `close_session` docstring), planning (WO-0036 close-out crediting Sol,
   WO-0105/0107 states, REV-0028 supersession note), architecture (DOWNSTREAM-STATUS refreshed).
3. `work/review/REV-0029/request.md` authored + queued — scope: the entire Part B diff
   (`5d10c70..HEAD`), subsuming REV-0024's Option B scope — plus a draft PR body and a read-only
   master-divergence report. **No PR created; no merge; no oracle weakened.**
4. A final report to the operator: evidence table + anything parked in the R1 lane.

Degraded-endpoint variant (only if D2 = park): identical, except the Codex oracle stays red on the
4 pre-existing property failures, each carrying a recorded operator disposition instead of a fix.

## §1 Up-front decision batch (the ONLY human input this run needs)

| # | Decision | Recommendation |
|---|---|---|
| **D1** | Authorize **setup-only reseed** of the 10 Option-B-induced Codex-oracle failures (terminalize establishing buys / route flatten through the cancel-and-retry the real caller performs). Recorded as a spec-change ratification; assertion lines stay byte-identical; dual-baseline proof required (§3-R4). | **YES** — facade behavior is unchanged; the seeds predate the ratified BUYS_OPEN store contract |
| **D2** | Authorize **TDD implementation of both pre-existing Codex-oracle properties**: **P-A** a pre-activation (APPROVED, never-activated) envelope must not spare its owner across session close; **P-B** an unresolved `needs_review` submit-recovery must retain the owner after envelope terminal. Escape hatch: if characterization shows either exceeds the bounded seams (close-time sparing predicate; unresolved-child predicate + projection index), it is **parked**, not built. | **YES with park hatch** — both are safety-tightening and match the ratified mechanism's own seams |
| **D3** | Authorize the **F.2 grafts**: `spared_sell_intents` close-event counter; granular `deferred_to_live_envelope_child` audit reason; masked-predecessor pin reconciliation (23-vs-14 delta, port-or-disposition each). Code fixes only where a ported pin exposes a semantics-preserving gap; else park. | **YES** |
| **D4** | **Consolidate reviews**: REV-0029 becomes the single independent packet for all of Part B (it formally subsumes REV-0024's Option B scope and records REV-0028 as superseded). One cross-model review of the final state, commissioned by you after this run. | **YES** — avoids reviewing a surface mid-churn and halves your review workload |
| **D5** | **Defer backfill verification** (H.1 step 7) to post-merge / pre-beta-reliance (needs real paper data unavailable here; it gates production reliance, not the merge). | **DEFER** |
| **D6** | Resolve H.1 step 6 (merge R2 test files) as **named coexistence** — Sol's trio + the lifecycle-link pins + both oracles all live on the trunk; physically merging files is churn with no behavioral value. | **COEXISTENCE** |
| **D7** | Pre-approve **conditional scope widening** of Part B allowed_paths to `app/models.py` / `app/transitions.py` ONLY if a graft/property mechanically requires it (flagged in the commit + outcome log). Expected unused. | **YES** |
| **D8** | Ratify the **standing no-stop rule** (§3-R1): adversarial-check findings that are test-only or semantics-preserving get fixed and folded into REV-0029's scope; anything requiring a NEW semantic choice is parked to `BLOCKED-DECISIONS.md` and batched to you at the end. No mid-run approval requests outside D1–D7's envelopes. Human-gated actions outside those envelopes (kill switch, live modes, deletions of tests/docs/ADRs, schema migration) remain hard stops as always. | **YES** |

## §2 Phases (each ends: full native gate + scope + hygiene + commit + push)

**P1 — Codex-oracle reconciliation** *(needs D1)*. Reseed the 10; every edit cites D1.
*Adversarial check:* independent lens verifies (a) assertion lines byte-identical (diff audit),
(b) dual-baseline: reseeded scenarios green at BOTH the pre-Option-B parent `15c2dd6` and HEAD —
proving the reseed smuggled no behavior.

**P2 — The two properties** *(needs D2; before P3a)*. Characterize (read-only) → TDD with the
oracle reds as the failing tests → implement in the identified seams, both stores, replay/parity
expanded same-change; new named pins added to the trunk suites; `close_session` docstring corrected
here (it under-describes exactly this behavior).
*Adversarial check:* event-log-truth lens (replay + dual-store parity + startup re-projection
interplay) and a projection-index lens (P-B adds recovery records as an input dimension to the
indexed projection — verify invalidation correctness).

**P3 — F.2 grafts** *(needs D3; P3a after P2 so the counter counts FINAL sparing semantics)*.
P3a counter; P3b granular audit reason (+ update the pins that assert the old string on the
envelope-child path); P3c pin reconciliation with per-test disposition (port / covered-elsewhere /
inapplicable-to-mechanism).
*Adversarial check:* test-integrity lens — no weakened pins, grafts additive, dispositions honest.

**P4 — Perf gates** *(verification, likely no build)*. Both gates already exist on trunk
(`tests/performance/`). They are **script-style by design** (`python -m
tests.performance.r2_scaling_gate` / `..._claude_ported`, exit-code contract; their own header:
"an explicit gate rather than an ordinary pytest module"), so P4/P6 run them exactly that way and
record the emitted metrics. If red → non-semantic optimization only; a semantic fix would park (D8).
*Adversarial check:* confirm the gate actually exercises the indexed projection (not a stale
target), and record N-scaling numbers.

**P5 — Governance docs**. ADR-010 inline dated amendment (the *synthesized* mechanism: projection
core + indexed implementation + Option B + grafts); INV-090; re-verify INV-032/036/080/081/087
against final code (audit note); DOWNSTREAM-STATUS refresh.
*Adversarial check:* docs-vs-code conformance lens — every claim maps to a file:line or test name.

**P6 — §H.4 acceptance gate, full run**. In order, pasted: (1) my oracle — hash-verified
UNMODIFIED; (2) Sol trio + lifecycle pins + new-property pins; (3) reseeded Codex oracle; (4) perf
gates; (5) full native gate + coverage ≥93% + multi-seed lifecycle soak; UTC stamps clear of the
documented 09:41 flake window.

**P7 — Close-out bookkeeping**. WO-0036 → CLOSED, archived to `work/completed/keep/`, ledger row
**crediting Sol's contribution** (Sol shipped zero `work/` artifacts); WO-0105 → REVIEW;
WO-0107 stays REVIEW; REV-0028 supersession recorded (packet exists only on the attempt branch);
WO-0106 (Codex investigator's) left untouched — flagged to operator.

**P8 — Review packet + PR prep + capstone check**. REV-0029 request.md (scope `5d10c70..HEAD`;
subsumes REV-0024; instructs the treadmill-sibling-class walk **by property, not instance** — the
charter's fresh-eyes-on-merged-diff requirement is delegated to this packet, satisfying "different
reviewer than the builder"); draft PR body saved in the packet; read-only master divergence check
(`fetch` + `merge-tree`, NO rebase); final operator report.
*Capstone adversarial check:* 3-lens in-process panel (concurrency, behavior-preservation,
test-integrity) + a **completeness critic** ("what's missing vs H.1–H.4?") over the FULL Part B
diff. In-process panels NEVER count as the independent review — REV-0029 stays outstanding by design.

## §3 Standing rules

- **R1 (park lane).** New defect found → test-only or semantics-preserving fix: do it, log it, fold
  into REV-0029 scope. New *semantic choice* → `BLOCKED-DECISIONS.md`, keep other lanes moving,
  batch at the end. Gated surfaces outside D1–D7: hard stop, always.
- **R2 (per-phase gate).** `ruff` + `ruff format --check` + `mypy` + `lint-imports` + full pytest +
  scope checker + AI-OS hygiene, then commit + push. No phase leaves the tree dirty.
- **R3 (review layering).** In-process adversarial panels ≠ independent review. The endpoint
  deliberately leaves REV-0029 outstanding.
- **R4 (oracle discipline).** Codex-oracle edits: setup-only; assertions byte-identical; dual-
  baseline (green at `15c2dd6` AND HEAD); each edit cites D1. My own oracle: never edited (hash
  check in P6). "Never weaken a test" governs everything else.
- **R5 (evidence).** Every phase's outcome log carries pasted command output (Fable discipline).
- **R6 (reordering).** P1, P4, P5-prep, P3c are parallelizable with P2; only P3a strictly follows
  P2; P6–P8 are sequential at the end. A parked P2 does not stall P3–P8.

## §4 Anticipated friction register → built-in resolution

| # | Friction | Resolution |
|---|---|---|
| F1 | Editing the Codex oracle violates charter §3 without authority | D1 ratification + R4 discipline |
| F2 | Sparing semantics are an operator choice (H.2's anticipated STOP) | D2 decides it now, up front |
| F3 | P-B touches the indexed projection's input set | Named in D2's bounded-seam definition; index lens in P2 |
| F4 | Audit-reason graft churns the flatten surface REV-0024 was queued for | D4 consolidates to one final-state review |
| F5 | A graft needs `models.py`/`transitions.py` (outside WO scope) | D7 conditional widening |
| F6 | Perf gates long-running or red | Background run; non-semantic-optimization lane; park if semantic |
| F7 | Hypothesis soak flakes on new branches | Multi-seed soak + the deterministic-reachability pattern already landed |
| F8 | A ported masked-predecessor pin comes up RED (real gap) | R1 lane: fix if semantics-preserving, else park |
| F9 | Master moves / conflicts during the run | Read-only divergence check in P8; no mid-review rebase |
| F10 | Stop-hook nags on uncommitted state | R2 commit-per-phase |
| F11 | WO-0106 belongs to the other investigator | Untouched; flagged in P7 |
| F12 | Coverage floor (93%) regression from new branches | Coverage runs inside every phase gate |

## §5 Plan self-review (red-team of this prompt — revisions already applied)

1. **Dead-wait eliminated:** v1 held the audit-reason graft "until REV-0024 clears" — but the
   endpoint means REV-0024 never clears mid-run. Revised: D4 consolidates both packets; the
   reviewer sees one final state.
2. **Stale work deleted:** v1 scheduled Theme D and a perf-gate port as build items; recon proved
   both already on the trunk. Converted to verification/evidence items (P4, P6).
3. **Order dependency caught:** v1 ran the sparing counter (P3a) before the sparing-semantics
   change (P2) — the counter would have been built against semantics about to change. Reordered.
4. **Oracle-edit hazard hardened:** reseeding could smuggle behavior. Added R4's dual-baseline +
   byte-identical-assertions proof, checked adversarially in P1.
5. **Scope-explosion hatch:** P2 could balloon (session-close truth). D2's park hatch degrades the
   endpoint gracefully instead of stalling the run or tempting an unauthorized shortcut.
6. **PR creation excluded on purpose:** H.2 sequences PR assembly AFTER review ACCEPT; the run
   prepares everything and creates nothing.
7. **Docs after code:** ADR/INV text describes what actually shipped, avoiding a second re-write.
8. **Decision load minimized:** 8 decisions, each with a recommendation, answerable in one message
   ("ratify all as recommended" or itemized deviations).

## §6 Outcome log (filled during the run)

- P1: —
- P2: —
- P3: —
- P4: —
- P5: —
- P6: —
- P7: —
- P8: —
- Parked (R1 lane): —
