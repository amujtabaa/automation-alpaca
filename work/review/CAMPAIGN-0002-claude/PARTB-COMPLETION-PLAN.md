# Part B completion run — goal prompt (RATIFIED 2026-07-17: D1–D8 all as recommended — see RATIFICATION-partb-completion.md)

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

- P1: **DONE 2026-07-17.** Reseed = one setup-only hunk in `_seed_long` (terminalize establishing
  BUY, citing D1). Evidence: `git diff --numstat` → `10 0` (additions-only ⇒ every assertion
  byte-identical by construction). At HEAD: 10 former failures green; exactly the 4 P-reds remain
  (`pre_activation…session_close`, `needs_review…retains_owner` × both stores). Dual-baseline:
  identical 4-only signature with the reseeded oracle overlaid on parent `15c2dd6` (worktree run,
  pasted in session log) ⇒ the reseed smuggled no Option-B-dependent behavior.
- P2: **DONE 2026-07-17.** Both properties implemented via three composed-once projection
  predicates (`retains_intent_strict` / widened `retains_intent` / `retains_across_close`) +
  exposed facts; both stores' close paths spare on `retains_across_close` and sweep bare
  pre-activation APPROVED envelopes → EXPIRED atomically (characterization proved the sweep is
  MANDATORY — the reconcile restore would otherwise resurrect the closed owner); restore/promote +
  conflict sweep re-keyed to strict (hold-vs-resurrect asymmetry; inert escalated lineages don't
  evict live mandates). Empirical P-B posture: complete sell-side quarantine of the escalated
  symbol (flatten blocked, new delegation refused, replacement dedups to retained owner) —
  TIMEOUT_QUARANTINE-style fail-closed. 12 new pins (`test_wo0036_r2_close_and_recovery_ownership.py`,
  both stores); hostile pin 1973 amended per D2 (retention instead of release, dedup instead of
  fresh replacement — cited). `close_session` ABC docstring gap (§G.3) fixed. **Codex oracle now
  fully green: 61 passed / 0 failed** (was 14 red at run start). Full suite: **3053 / 0 failures /
  0 errors / 12 skipped**. Parked: PD-1 (needs-review reconciliation release valve —
  `BLOCKED-DECISIONS.md`). Adversarial lenses (event-log truth; projection consumers) ran
  post-suite; findings, if any, folded as follow-ups in this phase's addendum.
- P3: **DONE 2026-07-17.** P3a `spared_sell_intents` close counter (planner param + payload; both
  stores count the spared branch; sequenced after P2). P3b granular
  `deferred_to_live_envelope_child` audit reason (planner flag set at both stores' exact
  child-substitution points; direct-protection reason unchanged). P3c: independent 23-test
  coverage mapping of the Claude-attempt lifecycle suite → 20 COVERED (ratified divergences
  absorbed as notes; masked-predecessor class mapped across five choke points), 3 GAPS — all
  missing pins with conforming trunk behavior (probe-verified) — ported (`ordered` owner-binding
  param; ghost-owner direct-ingress refusal at the APPROVED edge; second-mandate-refused-while-
  FROZEN, kill-switch-free). Lens follow-ups landed same-phase: exact-payload close pin fixed
  (the one HEAD red, found by the event-log-truth lens), A-1 cross-store sweep-stream parity pin
  added, D-1 docstring scoping. Phase gate: **full suite 3058 / 0 / 0 / 12**.
- P4: **DONE 2026-07-17 — measured, named finding; NO regression from this run.** Both gates
  (script-contract runs, quiet box): every STRUCTURAL criterion green (constant 15 selects/call
  across scales; all queries indexed; zero unrelated full scans; startup query growth 9.18× ≤ 12×;
  projection peak 300 KiB ≤ 2 MiB). Two WALL-CLOCK ratios miss marginally and reproducibly:
  runtime p95 large/small 3.35–3.77× (limit 3×), startup elapsed 12.87–13.15× (limit 12×).
  **Baseline at pre-run parent `15c2dd6`: FAILS the same two, worse-or-equal (3.783× / 15.42×)**
  ⇒ pre-existing, not introduced by P1–P3 (startup elapsed measurably improved this run). Per the
  gate's own contract, recorded as a named finding for REV-0029 + a candidate separately-approved
  perf work order (operator batch); no speculative mid-run optimization.
- P5: **DONE 2026-07-17** (pending conformance-lens verdict, folded below). ADR-010 gains three
  dated inline amendments describing the SYNTHESIZED mechanism: §3 (the shared projection + three
  predicates + P-A close sweep + P-B needs-review retention/quarantine + PD-1 pointer), §4 (the
  two fail-closed flatten pre-outcomes: BUYS_OPEN retry, needs-review refusal), §6 (three additive
  provenance surfaces: sweep `envelope_expired`, `spared_sell_intents`,
  `deferred_to_live_envelope_child`). INV-090 authored (the single-projection owner-lifecycle
  invariant, three keyings named, both oracles as pins). Re-verify of Sol's five in-place
  amendments vs final code: INV-032/036/080/087 HOLD verbatim; INV-081 gained a clarifying
  2026-07-17 addendum (the two pre-outcomes precede "takes over" without weakening it) + new pins.
- P6: (entry below, after the best-effort stress run completes)
- P7: **DONE 2026-07-17 (`4feb01d`).** WO-0036 → CLOSED `[RESULT_SUMMARY_KEPT, ADR_CREATED]`,
  archived to `work/completed/keep/` with the close-out section crediting **Sol's
  delegation-projection mechanism as canonical** (the planning-plane record Sol's commit never
  shipped); ledger row appended (validates; note: its `"commit"` field reads `HEAD` — the real
  SHA is `4feb01d`, recorded here since the ledger is append-only). WO-0105 → REVIEW. REV-0028
  recorded SUPERSEDED. WO-0106 (the Codex investigator's WO) verifiably untouched across the
  entire run (zero commits in range) — left to its owner, flagged in the operator report.
- P8: **DONE 2026-07-17 (`4feb01d` + this commit).** `REV-0029/request.md` authored — the single
  consolidated independent packet (scope `5d10c70..HEAD`, subsumes REV-0024 per D4, supersedes
  REV-0028; seven attack lenses led by the charter's treadmill-sibling-class walk, which
  delegates the fresh-eyes-on-merged-diff mandate to the independent reviewer). `PR-PREP.md`:
  read-only master divergence — master ahead by ONE content commit (`38762a1`, fixture-only);
  `merge-tree` conflicts in exactly 3 TEST files, zero production; mechanical resolution at PR
  time; NO rebase before the gate clears; draft PR body included; no PR created. Capstone
  checks: 4-seed lifecycle soak green; completeness critic returned **GAPS(8) — all
  recording/bookkeeping, zero code/test/governance defects** — every gap closed in this commit
  (this log, DOWNSTREAM-STATUS refresh, WO-0107 gate re-point, D7/D9/stress recordings, OBS
  summaries) or in the delivered operator report.
- Parked (R1 lane): **PD-1 only** — the needs-review reconciliation release valve
  (`BLOCKED-DECISIONS.md`; sketched as a WO-0108 candidate, human-gated). Operator batch also
  carries: the P4 perf follow-up WO candidate, and the WO-0106 not-mine-to-close flag.
- Decision-usage record (completeness gap 7): **D7 UNUSED** (`app/models.py`/`app/transitions.py`
  untouched — scope checker proves it); **D9 UNUSED** (zero `CREATE INDEX` statements added after
  its ratification; the step-1b indexes predate it). Both as predicted at ratification time.
- Lens observations recorded in-repo (completeness gap 8): **OBS-1** conflict-sweep middle gate
  keys widened while gates 1/3 are strict → a needs-review lineage coexisting with a working
  mandate makes the sweep SKIP the symbol (conservative, fail-closed; pre-R2 duplicates behind
  the live mandate stay unswept until the exposure resolves). **OBS-2** direct-path needs_review
  frees single-flight (X-003) while envelope-child needs-review quarantines — no gap: the direct
  second-sell hazard is separately blocked via `RECOVERY_OPEN_STATUSES` feeding the unresolved-
  direct-sell gates. **OBS-3** the P-A sweep is close-time only — legacy DBs whose sessions
  closed pre-P2 keep spared bare-APPROVED shapes until the (deferred, D5) backfill pass; no
  retro-sweep. **OBS-4** `envelope_owner_scope_reason` ignores intent status (pre-existing), so
  a stood-down owner can be the dedup target under needs-review retention — consistent with
  hold-without-resurrect. All four are REV-0029 reviewer context, none blocking.
