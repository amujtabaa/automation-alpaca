# Consolidation Campaign — Deconflict the Fragmented R2 (SellIntent↔Envelope) Work Into One Canonical, Verified Trunk

> **Run this in a fresh session on `amujtabaa/automation-alpaca`.** It is a **two-part charter**:
> **PART A — Investigate & decide** (read-only on all shared branches; produces a decision package + a spec-derived conformance oracle, both committed to the consolidation branch). **PART B — Execute the consolidation** on that same branch — activates **ONLY after the human ratifies Part A's §I decisions**, and ends in a review-gated PR toward `master`. The hard stop between the parts is not ceremony: the merge touches human-gated trading surfaces.
>
> Part A is ideally run by BOTH a strong Claude and a strong Codex/Sol session in parallel, with the human reconciling the two reports. **Why cross-model is mandatory:** one implementation under comparison was authored by Claude, the other by Codex/Sol — an implementation's author is a biased judge of it (the Claude attempt shipped with a real masked-predecessor bug that only a fresh-eyes pass caught). Every claim in either part is backed by pasted command output — no unverified assertions, ever.

---

## 0a. Session, environment & branch setup (do this first, verbatim)

- **Environment bootstrap** (fresh containers have no deps): `python3.12 -m venv ~/venv && ~/venv/bin/pip install -r requirements.txt -c constraints.txt && ~/venv/bin/pip install -c constraints.txt pytest pytest-cov ruff mypy import-linter anyio`. The repo gate is `ruff check . && ruff format --check . && mypy app/ && lint-imports && pytest -q` (CI adds `--cov=app --cov-branch`, floor 93%); toolchain pins live in `constraints.txt` (see `work/active/W3-STATE.md` "Gate/toolchain reference").
- **The consolidation branch is your ONLY writable ref — and it already exists.** `git fetch --all --prune && git checkout consolidate/r2-canonical` (seeded 2026-07-16 at `22617f4`, the shared base of both R2 attempts and the head of PR #8; this charter is committed at its root as `CONSOLIDATION-CHARTER.md`). Everything you produce — the Part A report, the conformance oracle suite, and (after ratification) the Part B build — commits and pushes HERE. Never push to, rebase, or merge any other branch; comparisons of other branches happen in local scratch worktrees (`git worktree add`).
- **Freeze refs (rollback anchors, never move them):** `freeze/20260715-master-preconsolidation` (`80250e0`), `freeze/20260715-pr8-head` (`22617f4`), `freeze/20260715-r2-claude` (`ba1cea7`), `freeze/20260715-r2-sol` (`353ef1c`). NOTE: branch tips may have moved past their freeze points since (the Claude R2 branch gained at least `a6ab844`, a test-clock guard fix) — always investigate the LIVE tips and treat the freeze refs as the recorded baseline.
- **Known in-flight item at seeding time (verify current state before relying on this):** PR #8's head is CI-red solely from pre-existing tape-clock test bombs (fixture-only defect F-3 + a `utcnow()` TTL-guard sibling; proven by CI history — same commit green 07:36 UTC 07-15, red 09:41 UTC 07-16). A verified 4-file test-only port that makes the head fully green exists and was offered to the human; PR #8's merge into `master` may therefore have happened before you read this, or may still be pending. `git log origin/master` + the PR state are the truth — update the topology map in §1 accordingly.
- **Charter yourself a work order.** Per the repo's operating system (`CLAUDE.md`: no work order → don't freelance), your FIRST commit drafts a consolidation work order (next free `WO-*` id from `work/ledger.jsonl` across ALL branches — verify; ids are claimed per-branch) using `.ai-os/templates/work-order.md`: scope = this charter, allowed_paths = the four planes' files + `tests/**` + the consolidation artifacts, done-when = the Part A/§H acceptance gate, status DRAFT → mark ACTIVE only when the human approves it. Part B's status flips ride the same close-out rule as all other work ("close-out ships with the work").
- **Read the safety core first**: `CLAUDE.md` (invariants, human-gated surfaces, conflict rule) binds every action in both parts. `PAPER` only; nothing here may create live order flow.
- **Artifacts live in-repo**: the Part A report at `work/review/<your-REV-or-consolidation-id>/`, the conformance oracle under `tests/` (clearly named, e.g. `tests/test_r2_conformance_oracle.py`), so the branch is self-documenting for the eventual independent reviewer.

---

# PART A — INVESTIGATE & DECIDE

## 0. Prime directive

Two independent AI attempts implemented the same structural change — **R2: the SellIntent↔Envelope lifecycle link (WO-0036)** — on the same base commit, and related work is scattered across two lineages and multiple branches/PRs. Produce a **decision-ready program** to converge all of it into a single canonical trunk state that is the **highest-quality, most reliable, and best-performing** result, with the "quarantine/treadmill" class of lifecycle-inconsistency bugs **provably closed at the root** (not symptom-patched) and every safety invariant preserved.

The output is a **written report + an ordered, human-gated execution plan** — not code changes. Treat `CLAUDE.md`'s safety core as binding. Statuses are `VERIFIED | UNVERIFIED | BLOCKED | NEEDS-INPUT` only; never fabricate a branch's contents, a test result, or an equivalence.

**The organizing idea:** you hold a rare *differential oracle* — two independent implementations of one spec on one base. Exploit it with a **spec-derived conformance suite** (§3), **formal correctness + parity obligations** (§4), and **measured performance** (§5). The spec is the oracle; neither implementation is.

---

## 1. Ground truth to VERIFY (reproduce every line; correct what is stale)

This map was drafted by one of the two authoring agents. **Confirm each claim with `git`/GitHub before relying on it**, and flag anything that has moved.

**Two lineages fork from `master` (`80250e0`):**
- **Signal-seat** → `master`; open **PR #7** (`claude/wo-0001-install-checks-2x5ys8`) — touches all four `app/store/*.py`.
- **Execution-envelope** → `feat/execution-envelope` (`c03bbae`, WO-0016..0035) → `claude/new-session-gu0z6y` (`22617f4`, WO-0036 clusters 1–4; open **PR #8**). **`22617f4` is the shared base of both R2 attempts.**

**The two R2 attempts (same base `22617f4`):**

| | Claude R2 (`claude/sellintent-envelope-linking-h2z7i7`, `5f33ad5`) | Sol R2 (`codex/r2-lifecycle-link-sol-impl`, `353ef1c`) |
|---|---|---|
| Shape | 4 commits, ~+1.9k lines, **store-only** (`app/store/{core,memory,sqlite}.py`) | 1 commit, ~+10.9k lines; store **+ `app/monitoring.py` + `app/reconciliation.py`** |
| Mechanism (VERIFY) | keep intent `APPROVED`-while-owned; **write** an `EXPIRED` transition at terminal write-choke-points; exclusive-driver guards; `LIVE = {ACTIVE, FROZEN}`. "Evented terminal propagation." | **delegation projection**: derive intent activeness from envelope lineage; `LIVE = {APPROVED, ACTIVE, FROZEN}`; **re-projects at startup** for pre-R2 data both directions. "Single-source projection." |
| Test corpus | one link suite (589 ln) + re-fixtured ~10 files + fresh-eyes masked-predecessor pins | link suite (559 ln) + **`test_wo0036_r2_hostile_closure.py` (3.4k ln)** + `_assurance` + `_parity_adversarial` + **`tests/performance/r2_scaling_gate.py`** |
| Governance | ADR-010 §8, INV-090, REV-0028 packet (renumbered from REV-0024), ledger/WO close-out | ADR-010 §8 (different text), INV-090 (different statement) |

**Confirmed hard collisions (enumerate exhaustively, don't assume this is complete):** both attempts add **INV-090** (different statements); both create **`tests/test_wo0036_r2_lifecycle_link.py`** (different content); both amend **ADR-010 §8**; both re-fixture the same ~10 envelope test files (compare the *fixturing strategies* — e.g. injected-clock activation vs Sol's approach — as a design signal). **Cross-lineage (RESOLVED 2026-07-15 — verify, don't re-litigate):** REV-0024 was double-claimed — the signal-seat lineage (PR #7 branch) holds `work/review/REV-0024/` for the ADR-009 re-review (REVIEWED, verdict BLOCK) and also claims REV-0025..0027, while the Claude R2 branch had independently minted its own REV-0024. The R2 packet was renumbered to **REV-0028** (commit `ba1cea7` on the Claude R2 branch; all references updated). Verify zero REV-0024 references remain on the R2 branch and that no OTHER id is similarly double-claimed. **Governance asymmetry:** Sol's commit contains **zero `work/` artifacts** — no WO close-out, no ledger entry, no REV packet (violates the repo's "close-out ships with the work" rule regardless of code quality). **Status drift:** `WO-0036` sits in `work/queue/` on `feat/execution-envelope` but `work/active/` (with differing statuses) on the three later branches.

**Also place:** `codex/rev-0022`, `collab/sol-0001` (verify it has NO R2 content), and any fork/ref discovered in §2.

Reproduce with `git fetch --all --prune`; `git for-each-ref refs/remotes`; `git merge-base`; `git rev-list --left-right --count`; `git diff --stat 22617f4 353ef1c` and `… 22617f4 <claude-r2>`.

---

## 2. Phase 0 — Freeze, inventory, do-no-harm

Before any comparison, establish safety and completeness:

- **Verify the freeze refs.** The four `freeze/*` branches (§0a) must still point at their recorded SHAs; if any live branch has moved past its freeze point, record the delta commits explicitly. You create only **local scratch worktrees/branches**; you never push, rebase, or merge anything shared.
- **Prove the inventory complete.** Enumerate every branch, remote, tag, PR (open+closed, incl. cross-fork heads), stash, worktree, bundle. Cross-check `git` against the GitHub API — a branch in one but not the other is a finding. Confirm both R2 attempts share base `22617f4`. If any *third* R2-adjacent artifact exists (another agent, an un-pushed local branch, a patch the human holds), mark `NEEDS-INPUT` and list exactly where you looked.
- **Topology diagram** (mermaid/ASCII): both lineages, fork points, the two R2 heads, the two PRs, the store-file collision surface.

→ **§A Topology, Inventory & Freeze-set** (with the completeness attestation).

---

## 3. Phase 1 — Author the spec-derived conformance oracle (the centerpiece)

Do NOT derive tests from either implementation. Derive them from the **spec sources**: `docs/adr/ADR-010-execution-envelope.md`, `docs/INVARIANTS.md`, `work/active/WO-0036-*`, and the AUDIT-0001 / treadmill charter. Produce an **implementation-independent behavioral conformance suite** (property-style, both stores) that encodes what R2 *must* guarantee, independent of how:

- **Core R2 property (state it formally, then test it):** for every symbol and at every point in an envelope-backed exit's life, *the intent is "active" (dedup-blocking) iff there exists a non-terminal exit obligation for that symbol* — i.e. a live (ACTIVE/FROZEN) envelope **or** a child order that may still rest at the venue. No boundary (session close, rollover, reprice, quarantine, supersession, flatten, kill/resume) may create a window where the symbol has zero owner but live exposure, or two owners.
- **Class-closure obligations:** one property per treadmill sibling — stale `SUBMITTING`; below-floor/phantom-print; date rollover; mid-reprice quarantine; deviation-suspect prints; claim/venue crash; session boundary; **masked predecessor** (staged CREATED replacement hiding a live predecessor); **resting child after a releasing terminal** (BREACHED/EXHAUSTED/REST_AT_FLOOR); **monitoring-side newest-wins convergence**.
- **Safety-rail obligations:** INV-1..9, INV-060, INV-077, INV-087, the ADR-010 rails, "submitted ≠ filled," "only deduped fills move quantity," single-writer, no-second-stored-derived-truth, envelope bounds immutable / amendment-by-supersession-only.

Run this suite against **both** implementations (in scratch worktrees). Report the result as a truth table: **union of failures = the true defect set; intersection of passes = the trustworthy shared core.** This is the backbone of every downstream judgment.

→ **§B Conformance Oracle & Results** (the suite, plus per-implementation pass/fail with pasted output).

---

## 4. Phase 2 — Characterize each attempt + discharge the formal obligations

For **each** attempt independently (mirror-image write-ups, so neither is seen only through the other's frame):

1. **Mechanism** — the exact choke points, the "live" predicate(s), how activation links + normalizes the backing intent, how terminal release happens, session-close handling, flatten deferral, exclusive-driver guard, and (Sol) the startup re-projection. State its invariant in one sentence.
2. **Correctness obligation** — check the mechanism against the §3 core property as a *proof sketch*: enumerate the state transitions that could violate it and show the code forecloses each. A gap here is a P0.
3. **Parity obligation** — argue `InMemoryStateStore` ≡ `SqliteStateStore` for the R2 surface: event order, payloads, projection-vs-stored reads, and (critically) the startup re-projection path. Name every drift risk; back with the parity tests.
4. **No-second-stored-truth** — confirm neither a stored counter/column nor a duplicated derived truth was added; judge projection-based and write-propagation-based designs each on its own terms.
5. **Governance + migration** — ADR/INV/REV/ledger completeness, and **pre-R2 data**: does it correctly handle intents already orphaned before the fix (Sol re-projects; what does Claude do)?
6. **Native gate** — run and paste `ruff && ruff format --check && mypy app/ && lint-imports && pytest -q` + the coverage-gated CI variant (floor 93%). **Run at a UTC time that would expose the known tape-clock time-of-day flake** (some tape-driven tests depend on injected-clock vs wall-clock activation) and note any test whose result depends on the current time.

→ **§C Per-Attempt Characterization + Obligation Discharge.**

---

## 5. Phase 3 — Performance under a budget (measured, not reasoned)

Both mechanisms scan the event log (`O(events)`) on hot paths (release, live-child, flatten) that run **inside the monitoring tick**; the event log grows unbounded across a trading day, so this is a live-reliability question, not a micro-optimization.

- Define a **per-tick latency budget** (state your assumption; e.g. the tick must stay well under its cadence with N symbols × M envelopes × a full-day event log).
- Run Sol's `tests/performance/r2_scaling_gate.py` against **both** implementations (port if needed); if it won't port, build an equivalent scaling harness. Measure wall-time growth vs event count for each hot path in each implementation.
- Judge: which mechanism is cheaper at scale, is either a tail-latency risk, and **should the synthesis introduce an indexed/memoized projection** (per-symbol live-child / live-envelope index) that neither attempt shipped? Recommend concretely.

→ **§D Performance Findings + budget verdict.**

---

## 6. Phase 4 — Adversarial cross-verification (each attempt as the other's skeptic)

- **Cross-run** each attempt's own suites onto the other (scratch worktrees, minimal fixture adaptation, never pushed). Run **Sol's 3.4k-line hostile-closure + perf suites against Claude's code**, and **Claude's fresh-eyes/masked-predecessor pins against Sol's code**. Every divergence is either a real bug in one or a legitimate design difference — adjudicate each with a minimal repro and say which implementation it argues for.
- Probe the four items Claude's REV-0028 packet ratified/disclosed (Option-A+ divergence; R6 per-tick re-drive; monitoring newest-wins convergence; HALTED emergency-reduce deferral) **against Sol's design** — does Sol close, contradict, or ignore each?
- For every candidate defect: concrete failing input → wrong output/exposure, which attempt has it, whether the other avoids it *structurally*. These are the **cross-pollination targets** for the synthesis.

→ **§E Cross-Verification Findings** (repro + severity + which design each argues for).

---

## 7. Phase 5 — Decide the mechanism (the load-bearing fork)

**Single-source projection (Sol)** vs **evented terminal propagation (Claude)** is the decision that shapes everything. Decide it explicitly, against stated criteria:

- Correctness (obligation discharged cleanly?), parity fidelity, performance-at-scale, minimality/blast-radius/reviewability, migration safety for pre-R2 data, alignment with "structural, single-source, no second stored truth," and long-term maintainability.
- Projection trades a derived write for broader read-path semantics + a startup re-projection; evented propagation is simpler/durable but writes a derived `EXPIRED` transition. Weigh both against the §3 property and the safety core.
- **Recommend one, or an explicit synthesis** — and be concrete, file by file, about what is kept, dropped, and grafted (e.g. "Sol's projection core + memoized index from §5 + Claude's masked-predecessor pins + Sol's hostile + perf suites + a single reconciled ADR §8/INV-090").

→ **§F Mechanism Decision** (criteria table + justified verdict + the graft list).

---

## 8. Phase 6 — Deconflict topology, namespaces & the four planes (code · planning · documentation · architecture)

This project's truth lives on four planes, and each has already drifted across branches. Audit each plane explicitly — a consolidation that merges only the code plane leaves the repo lying to its own reviewers.

**8a. Namespace & identifier deconfliction (planning plane).** Build the full collision/renumber registry across ALL branches, not just the two R2 attempts:
- Every `WO-*`, `ADR-*`, `INV-*`, `REV-*`, ledger id, and governance **filename** claimed by more than one branch, with the canonical resolution for each (single owner / renumber / merge-of-both). Known seeds to verify and extend: **REV-0024 double-claim — already resolved** (the Claude-R2 packet was renumbered to REV-0028 in `ba1cea7`; verify the resolution is complete and that the signal-seat lineage's REV-0024..0027 claims are the only remaining users); **INV-090 double-claim** (two different statements — still live); **ADR-010 §8** (two different amendment texts — still live); `test_wo0036_r2_lifecycle_link.py` (still live).
- Reconstruct the repo's **renumber history** (ADR-009→ADR-010 on the envelope branch; master's WO-0016→WO-0100; the two competing REV-0022 results, constructed-vs-formal) and confirm no stale references to pre-renumber ids survive on any branch tip (`git grep` each old id on each tip).
- **Ledger & work-state coherence:** diff `work/ledger.jsonl`, `work/active|queue|review|completed` across all tips. Flag: the same WO with different statuses on different branches (confirmed for WO-0036: `queue` on `feat/execution-envelope`, `active` elsewhere); entries whose `commit:` fields point at commits missing from the eventual trunk; completed orders parked in live folders (CI-enforced). Run the repo's own hygiene suite on each candidate consolidated state: `check_ledger`, `check_work_order_disposition`, `check_pkl`.
- **Sol's governance gap:** Sol's commit ships **no `work/` artifacts at all** (no WO close-out, ledger entry, or REV packet). Whatever mechanism wins, the consolidation must author the missing planning-plane record for the surviving change — per the repo's close-out rule — and say who reviews it.

**8b. Documentation-vs-code coherence (documentation plane).** The repo's own conflict rule: *docs/code/ADRs disagree → don't silently pick one; a safety-surface conflict is a recorded decision gap.* Apply it systematically:
- For each branch tip in play: diff the doc corpus (`docs/adr/*`, `docs/INVARIANTS.md`, `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` + spec docs, `pkl/**`, `work/active/W3-STATE.md`) against the SAME tip's code. Every claim naming behavior ("X refuses Y", "pinned by test Z", "enforced in both stores") gets spot-verified against that tip's code/tests; each mismatch is a finding with plane + severity.
- Produce a **doc-variant matrix**: for each governance-bearing file that differs across branches (ADR-010, INVARIANTS.md, W3-STATE.md, WO-0036, PKL pages), which variants exist, what each uniquely claims, and the merged text's source-of-truth per section. ADR amendment-history lines must end up telling ONE true story (including who ratified what, when — e.g. the Option-A+ ratification and Sol's competing §8 narrative cannot both stand as-is).
- Check **test-name pins in docs**: INVARIANTS "Pinned by:" entries and ADR pin references must name tests that actually exist and pass on the consolidated candidate.

**8c. Architecture-plane conformance.** The consolidated result must still satisfy the architecture, not just the tests:
- Layer/seam compliance: `lint-imports` on each attempt and on the consolidated candidate; verify Sol's `app/monitoring.py` + `app/reconciliation.py` rework stays within the approved seams (ui→api→facade→engine→adapter/store; `alpaca-py` only in the adapter; single-writer engine intact).
- Spine-spec fidelity: re-check INV-1..9 (`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5`) and the ADR-010 rails against BOTH mechanisms — especially whether Sol's startup re-projection respects "the event log is truth / positions derive only from deduped fills" and whether either mechanism introduces a second stored derived truth in architectural terms.
- WO scope compliance: run `check_work_order_scope` for the consolidated diff against WO-0036's `allowed_paths` (note Sol touches `app/reconciliation.py`, which IS in the WO's allowed paths — verify, don't assume).

**8d. Lineage collision & PR reconciliation:** the envelope (PR #8) and signal-seat (PR #7) lineages **both modify all four `app/store/*.py`**. Determine safe merge order into `master` (+`git merge-tree` evidence), the conflict surface, any post-merge rebase (PR #8's note recommends envelope-first), and how the consolidated R2 (currently beyond `22617f4`, in neither PR) reaches `master` — fold into #8 or a fresh stacked PR. Note that the REV-0024/REV-0028 id resolution (8a) is coupled to this ordering.

→ **§G Deconfliction Tables**: namespace/renumber registry · ledger/work-state drift table · doc-variant matrix with merged-text plan · doc-vs-code mismatch findings · architecture-conformance verdicts · lineage/merge-order + PR plan.

---

## 9. Phase 7 — The consolidation program (ordered, gated, reversible)

1. **Canonical R2 definition** — the mechanism verdict (§7) turned into a precise, file-by-file build spec for the single consolidated result.
2. **Convergence topology** — the exact branch/rebase/PR sequence to land it on `master` alongside both lineages, collision surface pre-identified. Mark every step touching a **human-gated surface** (order-intent lifecycle, session-close event truth, cancel/replace, flatten, schema, event-log truth) as **STOP-FOR-HUMAN**.
3. **Governance to produce** — the four planes, reconciled: one true ADR-010 §8 + amendment history; one canonical INV-090 (+ every renumber from §8a, including the REV-0024/REV-0028 resolution); one merged R2 test file; WO-0036 close-out **including the planning-plane record Sol's commit never shipped**; ledger/W3-STATE/PKL updates that pass the repo's hygiene checks; and **one REV packet for the consolidated gated change** requiring independent cross-model review before beta reliance.
4. **Acceptance gate for the consolidated result** — must pass the §3 conformance oracle, **both** attempts' hostile suites, the §5 performance budget, and the full native gate — run at a flake-exposing UTC time. Plus a required **adversarial fresh-eyes pass** on the merged diff (the discipline that caught the original masked-predecessor bug), asserting class-closure by property, not by instance.
5. **Risk register + rollback** — parity drift, tick tail-latency, pre-R2 migration, the four-store-file cross-lineage collision — each with mitigation + a concrete rollback (the `freeze/*` refs from §0a).
6. **Batched human decisions** — each as a crisp either/or with your recommendation + one-line reason (mechanism choice; merge order; PR-fold vs stacked; namespace resolutions; whether to also land Sol's monitoring/reconcile rework or defer it).

→ **§H Consolidation Program** + **§I Batched Human Decisions.**

---

## 10. Orchestration (how to actually run this at capability)

- **Fan out, then synthesize.** Run the phases with parallel independent workers where they're independent — e.g. one characterizer per attempt (§4), a dedicated oracle author (§3), a dedicated performance harness (§5), an adversary (§6) — then a **single synthesis seat** that no worker's self-assessment can override. Validate every sub-result yourself against the §3 oracle before trusting it.
- **Cross-model by construction.** If both a Claude and a Codex/Sol session run this charter, neither reads the other's report until its own is done; the human reconciles. Divergence between the two consolidation reports is itself a high-value signal about where the merge is genuinely uncertain.
- **Read-only on shared state.** The consolidation branch (§0a) is the sole writable ref; every other branch is compared in scratch worktrees only. Never push/rebase/merge a shared branch or mutate a PR; never weaken a test to make a comparison pass; isolate ambiguity into §I and keep the other threads moving.
- **Part A ends at a hard stop.** Commit the report + oracle to the consolidation branch, surface §I to the human, and WAIT. Do not begin Part B on your own judgment — the ratification is the human's, recorded in-repo (e.g. as the WO's approval note), not inferred from silence.

---

## 11. Part A report shape

Lead with a **½-page executive summary**: the recommended canonical R2 + mechanism, the merge order, and the top 3 human decisions. Then: **§A** Topology/Inventory/Freeze · **§B** Conformance Oracle & Results · **§C** Per-Attempt + Obligations · **§D** Performance · **§E** Cross-Verification · **§F** Mechanism Decision · **§G** Deconfliction · **§H** Consolidation Program · **§I** Human Decisions · **§J** Evidence Appendix (every command + decisive output). Every claim in §A–I traces to §J. Commit the report + oracle to the consolidation branch, present §I to the human, and **stop**.

---

# PART B — EXECUTE THE CONSOLIDATION (activates ONLY on the human's recorded ratification of §I)

Same session or a successor session on the same branch. Part B is ordinary gated engineering under the repo's Fable discipline (test-first, root-cause fixes, fresh pasted evidence, visible deviations) — the §H program is your work order body, the ratified §I decisions are its fixed parameters. Do not re-open decided questions; if execution reveals a decision was wrong, STOP and return it to the human with evidence.

**B1. Build the canonical R2** on the consolidation branch per the ratified §F graft list — file by file, keeping the winning mechanism, grafting the named assets from the other attempt (tests travel with the behaviors they pin), and implementing any synthesis items (e.g. the memoized live-index from §D) test-first against the conformance oracle. The oracle is the definition of done for behavior: **it may not be edited to pass** — a needed oracle change is a spec change and goes to the human.

**B2. Reconcile the four planes** per §G: one true ADR-010 §8 + amendment history; one canonical INV-090 (+ every ratified renumber); one merged R2 test file; the WO-0036 close-out including the planning-plane record the Sol commit never shipped; ledger/W3-STATE/PKL updates. The repo's hygiene suite (`check_ledger`, `check_work_order_disposition`, `check_pkl`, `check_work_order_scope`) must pass at every commit.

**B3. Run the full acceptance gate** from §H-4 and paste it: the conformance oracle, BOTH attempts' hostile/assurance suites, the performance budget from §D, the native gate + coverage floor — executed at a UTC time that would expose the known tape-clock flake — plus an **adversarial fresh-eyes pass on the merged diff** (walk every treadmill sibling class; assert closure by property, not instance). Any finding here is fixed test-first before proceeding.

**B4. Queue the independent review, then the PR** — both STOP-FOR-HUMAN:
- Author the REV packet for the consolidated gated change (next free id — verify across ALL branches; this campaign already collided once on REV-0024) with base/fix SHAs, invariant delta, probes, and the ratified decisions listed as verify-items. **The review gate clears only on an ACCEPT/ACCEPT-WITH-CHANGES disposition by a different model — never your own pass.**
- Only then assemble the PR toward `master` per the ratified merge order (mind the PR #7/#8 sequencing and the four-store-file collision surface), with the `freeze/*` refs from §0a as the rollback path. The human merges; you never do.

**B5. Close out with the work** (repo rule): WO status flip + disposition + ledger entry + file moves + every doc/PKL/ADR claim the consolidation invalidated, in the same push as the final change — "done but not dispositioned" is not done.
