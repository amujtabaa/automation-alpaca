---
type: Review Result
rev_id: REV-0036
title: Safety-record label reconciliation for REV-0033 and completed import/mypy ratchets
reviewer: "Claude (independent; builder Codex)"
reviewer_seat: Claude
builder_seat: Codex
work_order: WO-0121
commit_range: origin/master..31d133d
semantic_range_reviewed: b03c0e9..07f7159 (WO-0121 doc edits isolated in 07f7159; staged by 36538e8)
human_gated_surfaces: [accepted-ADR-text, invariant-record-text, event-log-truth-records]
date: 2026-07-21
verdict: ACCEPT
---

# Review Result REV-0036 — nonsemantic safety-record reconciliation (WO-0121)

## Verdict

**ACCEPT.**

WO-0121 is an annotation-only reconciliation of the accepted safety contract. Every edit is a
dated, additive record that makes the written record MATCH already-shipped, already-reviewed
behavior. I re-derived every record claim from the current tree and ran the live gates myself.
Zero semantic change is present: no decision, rail, threshold, invariant meaning, import contract,
or mypy configuration *value* is altered. The one non-additive edit is a single deletion of a stale
`pyproject.toml` comment (F004), which is authorized by the WO's corrected allowed-path list and
leaves every configuration value untouched. No blocking or change-required findings.

This ACCEPT clears the independent cross-model review gate for the annotation-only change only. It
does **not** self-clear the human disposition, and no beta milestone may rely on these corrected
labels until the operator dispositions WO-0121.

## Scope and isolation note

The assigned batch range `origin/master..31d133d` is the whole ULTRA batch (many lanes: WO-0114,
WO-0118, WO-0120, WO-0124, WO-0127, …). WO-0121's own footprint is isolated in three commits —
`b03c0e9` (activate/rename, work/ only), `07f7159` (the substantive doc + pyproject edit), and
`36538e8` (stage REV-0036, work/ only). All review claims below are anchored to `07f7159`, which is
exactly the frozen semantic range `b03c0e9..07f7159` the request.md froze. I reviewed the WO-0121
lane in isolation; later same-file edits by other lanes (e.g. WO-0124 on INVARIANTS.md) are out of
scope for REV-0036 and carry their own packets.

**Union of all three WO-0121 commits touches only:** `docs/INVARIANTS.md` (+40),
`docs/adr/ADR-002` (+5), `ADR-003` (+5), `ADR-006` (+9), `ADR-007` (+12), `ADR-008` (+5),
`pyproject.toml` (−1, comment), `work/active/ULTRA-BATCH-STATE.md`, the WO-0121 file, and
`work/review/REV-0036/request.md`. **Zero `app/`, `tests/`, or `.github/` paths.** No P1 scope
violation.

## Findings

No BLOCK or ACCEPT-WITH-CHANGES findings. Three informational notes (no change required):

- **N1 (informational) — commit-range bookkeeping.** My frontmatter `commit_range` is the assigned
  batch integration range `origin/master..31d133d`; the substantive WO-0121 edits live entirely in
  `07f7159`. The WO evidence block's `eab9e57..64886f9` SHAs are pre-integration and are NOT FOUND
  on the branch — exactly the rewrite the request.md pre-authorized ("If integration rewrites those
  commits, the dispatching integrator must replace the frontmatter range…"). The integrated
  equivalent `b03c0e9..07f7159` in request.md is accurate. Nothing to fix.
- **N2 (informational) — cite line-drift at branch HEAD.** request.md's INVARIANTS cites are
  frozen-range-relative (valid at `07f7159`). The first five still resolve at HEAD
  (143/162/452/565/722); the last three drifted (1084→1155, 1108→1179, 1145→1216) because later
  lanes inserted content above them. This is expected batch line-drift, not a WO-0121 defect. If
  the human wants the disposition to be copy-pasteable against HEAD, it may note the cites are
  relative to the frozen review range.
- **N3 (informational) — ADR-007 "WO-0012" attribution.** The ADR-007 current-state record credits
  the mypy punch-list burn-down to "WO-0012". I did not independently audit WO-0012's history, but
  the attribution faithfully mirrors the pre-existing `pyproject.toml` comment
  (`# Grandfather punch-list (ADR-007): FULLY BURNED DOWN (WO-0012).`), so it introduces no new
  claim beyond what the live config already records. The load-bearing current-state facts (no app
  `ignore_errors` override, whole `app/` checked, `warn_unused_ignores = true`, 64-file clean) I
  verified directly.

## Per-site confirmation table (each cited F003/F004 site)

Anchors verified at frozen commit `07f7159`. "REV-0033 pair" = the note states verdict
**ACCEPT-WITH-CHANGES** + disposition **RESOLVED**, matching
`work/review/REV-0033/disposition.md:4-5` (`verdict_received: ACCEPT-WITH-CHANGES`,
`disposition_status: RESOLVED`) and its gate line ("**REV-0033 disposition: RESOLVED.**").

| # | Finding | Cited site (frozen) | What it records | Additive? | Pending text preserved? | Verified |
|---|---------|---------------------|-----------------|-----------|-------------------------|----------|
| 1 | F003 | `ADR-002-timeout-quarantine.md:66` | REV-0033 pair; links disposition | + only | Yes (verbatim above note) | ✅ |
| 2 | F003 | `ADR-003-manual-flatten-halted-reducing.md:39` | REV-0033 pair; links disposition | + only | Yes | ✅ |
| 3 | F003 | `ADR-008-order-status-event-provenance.md:79` | REV-0033 pair; "pending REV-0033" heading kept | + only | Yes (heading retained) | ✅ |
| 4 | F003 | `INVARIANTS.md:143` (INV-021) | REV-0033 pair; "changes no invariant meaning" | + only | Yes | ✅ |
| 5 | F003 | `INVARIANTS.md:162` (INV-022) | REV-0033 pair | + only | Yes | ✅ |
| 6 | F003 | `INVARIANTS.md:452` (INV-060) | REV-0033 pair | + only | Yes | ✅ |
| 7 | F003 | `INVARIANTS.md:565` (INV-076) | REV-0033 pair | + only | Yes | ✅ |
| 8 | F003 | `INVARIANTS.md:722` (INV-081) | REV-0033 pair | + only | Yes | ✅ |
| 9 | F003 (current-tree expansion) | `INVARIANTS.md:1084` (INV-091) | REV-0033 pair | + only | Yes | ✅ |
| 10 | F003 (current-tree expansion) | `INVARIANTS.md:1108` (INV-092) | REV-0033 pair | + only | Yes | ✅ |
| 11 | F003 (current-tree expansion) | `INVARIANTS.md:1145` (INV-094) | REV-0033 pair | + only | Yes | ✅ |
| 12 | F004 | `ADR-006-import-boundaries.md:110` | 6 live contracts (5 + `sellside-is-a-pure-policy`); "6 kept, 0 broken"; original 5-contract baseline retained | append only | Yes (baseline kept) | ✅ |
| 13 | F004 | `ADR-007-mypy-typecheck-gate.md:52` | punch-list fully burned down, no app `ignore_errors`, whole `app/` checked, `warn_unused_ignores=true`, `mypy app/` clean 64 files; baseline/limitation history retained | append only | Yes (baseline kept) | ✅ |
| 14 | F004 | `pyproject.toml` (−1) | deletes only the stale `# Next ADR-007 step: consider flipping warn_unused_ignores = true.` comment | single deletion | n/a | ✅ |

Total: 11 closure records (3 ADR + 8 INV) + 2 current-state records (ADR-006/007) + 1 comment
deletion = matches the WO's 11/11 + F004 contract.

## Required disproof attempts (from request.md §"Invariant accounting")

1. **Additive-only, byte-for-byte.** Commit `07f7159`'s docs diff is pure `+` additions with
   unchanged context lines — no `-` lines and no context rewrites in any of the six documents.
   `pyproject.toml` has exactly `0 insertions, 1 deletion` (the stale comment). Removing the
   inserted blocks reproduces the pre-WO documents. **Disproof failed → additive-only holds.**
2. **Orphan / over-claiming pending labels.** Every `WO-0113`/`pending REV-0033` label in the five
   target documents carries a nearby dated closure note, and every note states exactly the
   canonical **ACCEPT-WITH-CHANGES / RESOLVED** pair — none claims a stronger verdict (e.g. plain
   "ACCEPT" or "all findings fixed"). **Could not find a counterexample.**
3. **Import contract count.** `.importlinter` has six `[importlinter:contract:*]` headers at lines
   33/51/66/95/134/182 (exactly the request.md cite); the sixth is `sellside-is-a-pure-policy`. I
   ran `lint-imports --no-cache` on the branch: **6 kept, 0 broken** (exit 0). **Six-kept claim
   confirmed, not disproven.**
4. **App type-check burn-down.** No `ignore_errors = true` override exists anywhere in
   `pyproject.toml` (the only `ignore_errors` token is inside descriptive prose at line 76). The
   sole mypy override is `numpy.*/pandas.*/pyarrow.*` `follow_imports = "skip"`. I ran `mypy app/`:
   **Success: no issues found in 64 source files** (exit 0). **Whole-app green claim confirmed.**
5. **pyproject value delta.** Diff vs pre-WO head shows exactly one deleted stale comment and zero
   setting/value changes. `warn_unused_ignores = true` remains live at line 54 (flipped 2026-07-11,
   pre-WO-0121). **Exactly one comment deletion, no value change — confirmed.**
6. **Out-of-authorization mutation search.** No `app/`, `tests/`, `.github/`, threshold, event
   name, invariant definition, or altered historical sentence appears in any WO-0121 commit.
   **None found.**

## Questions to answer (request.md §"Questions")

1. **Do closure notes state exactly what REV-0033 proves and preserve history?** Yes — canonical
   ACCEPT-WITH-CHANGES/RESOLVED pair, disposition linked, prior pending text retained verbatim.
2. **Are the three extra invariant annotations (INV-091/092/094) legitimate same-class closure?**
   Yes — identical stale `WO-0113 pending REV-0033` labels, same record-only note, no rule/rationale
   /pin changed. Same class, not scope creep.
3. **Do ADR-006/007 distinguish historical baseline from stronger current gate?** Yes — both append
   a dated "current-state record" section and explicitly retain the original adoption baseline as
   history; both disclaim any policy/boundary/value change and defer beta reliance to REV-0036.
4. **Was the pyproject correction limited to the one comment?** Yes — one deletion, the
   contradictory "consider flipping" comment; value line untouched.
5. **Can any annotation be read as changing an invariant / authorizing behavior / self-clearing the
   review gate?** No — each note carries an explicit "changes no invariant meaning / behavior /
   decision" disclaimer, and ADR-006/007 records explicitly state they "remain review-gated by
   REV-0036 before beta reliance."

## Ran vs. read

**Ran (fresh, on `origin/codex/ultra-beta-batch` @ 31d133d):**
- `lint-imports --no-cache` → `Analyzed 92 files, 449 dependencies. … Contracts: 6 kept, 0 broken.` (exit 0)
- `mypy app/` (mypy 2.2.0, constraint-pinned; config `python_version="3.11"`) → `Success: no issues found in 64 source files` (exit 0)
- `git show 07f7159 -- <docs> pyproject.toml` → inspected every hunk (additive-only confirmed)
- `git diff --stat b03c0e9~1..07f7159` and per-commit stats → union scope (docs+pyproject+work/ only)
- Static count of `.importlinter` contract headers (6 at 33/51/66/95/134/182) and `grep ignore_errors` (none as a setting)
- Anchor resolution of every request.md cite at `07f7159`; HEAD drift check

**Read (relied on recorded evidence / source of truth):**
- `work/review/REV-0033/disposition.md` — authoritative ACCEPT-WITH-CHANGES / RESOLVED state (frontmatter + gate line)
- `work/review/AUDIT-0002-priorwork/report.md` F003/F004 — original stale-label locations and resolution guidance
- WO-0121 file Fable evidence, `CLAUDE.md`, `AGENTS.md` review section, request.md

**Environment caveat:** Executed under system Python 3.11.15 (repo runtime pins 3.12), with the
constraint-pinned `mypy==2.2.0` and `import-linter 2.13`, all app deps importable. The mypy config
itself targets `python_version = "3.11"`, so results are directly comparable; my fresh numbers
(64 files clean, 6/6 contracts) match the branch's own recorded evidence and REV-0033's independent
run exactly.

## Could not verify (non-blocking)

- **Full `pytest -q` suite (3,873 tests).** Not run here. WO-0121 changes zero executable code
  (documentation prose + one config *comment*), so no test outcome can move; I rely on the branch's
  recorded `3861 passed / 11 skipped / 1 xfailed` and the structural impossibility of a doc/comment
  edit changing behavior. `ruff`/PKL/ledger/disposition/scope governance checks likewise read from
  branch evidence.
- **WO-0012 historical attribution (N3).** Confirmed consistent with the live pyproject comment;
  not independently re-audited (out of scope — the annotation mirrors an existing record).
- **HEAD line-drift of 3 INVARIANTS cites (N2).** Verified at the frozen review commit `07f7159`
  (all cites resolve); at HEAD three shifted due to unrelated later lanes.

## Disposition gate

Every cited F003/F004 site is an accurate, dated, additive record that matches already-shipped,
independently-reviewed behavior; the one config edit is a single stale-comment deletion with no
value change; scope is docs + comment + work/ only. **REV-0036 verdict: ACCEPT.** Human disposition
of WO-0121 and any beta reliance remain outstanding by design.
