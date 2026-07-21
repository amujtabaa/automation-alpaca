# AUDIT-0002 remediation batch — triage, scoped WOs, operator decisions

> Planning-seat artifact, 2026-07-20. Consolidates all AUDIT-0002 findings (Codex seat, 10 P1)
> **and** the Claude-seat addendum (7: C001/C002 P1, C101-C105 low/info) into a small set of
> executable WOs + a short operator-decision list. Anchor: master `a776a8f` (post-merge, packet
> + addendum landed). **No finding is a live-safety P0.** This note is not a WO; it dispositions
> with whichever WO consumes it last.

## Triage — 17 findings → 3 WOs + 3 operator decisions + 2 protocol notes

| Finding | Nature | Routed to |
|---|---|---|
| F001 completed W3 records still DRAFT; checker folder-blind | record + gate | **WO-0120** |
| F008 REV-0029/0030/WO-0109 closure chain missing | record | **WO-0120** (F008 drafts below) |
| F009 nine remediated W3 FINDING files say OPEN | record | **WO-0120** |
| F010 REV-0019/0023 packet metadata inconsistent | record | **WO-0120** |
| C001 WO-0113 frozen at `status: REVIEW` | record | **WO-0120** |
| C102 F008 extension (WO-0113 link) | record | **WO-0120** (subsumed by C001) |
| C103 WO-0108 SUPERSEDED relabel unmerged | record | ✅ RESOLVED by the branch merge (`34ccc3c`) |
| F003 stale "pending REV-0033" labels in accepted ADR/INV | **human-gated** doc | **WO-0121** |
| F004 ADR-006/007 lag stronger live gates | **human-gated** doc | **WO-0121** |
| F002 INV-051/052 no failure-capable pin | test coverage | **WO-0122** |
| C002 conformance oracle not run by CI | CI + test | **WO-0122** (quick win) |
| C101 stale inert-pin fixture + comment in test_wo0108 | test hygiene | **WO-0122** |
| F005 WO-0029 stale umbrella needs re-cut | planning re-cut | **Decision O-1** |
| F006 W3/W4 launchers stale; deletion batch | planning + delete | **Decision O-2** |
| F007 WO-0102 signal-seat stranded (47 commits) | **operator** | **Decision O-3** |
| C104 reviewed party edited reviewer artifact | protocol | **Note P-1** |
| C105 WO-0110 review outside `REV-*` packet form | protocol | **Note P-2** |

## Scoped WOs (drafted this batch)

- **WO-0120 — Complete the governance record + make the disposition checker folder-aware.**
  Pure bookkeeping (record flips, append-only dispositions, the two F008 closure records) in
  Phase 1; then Phase 2 hardens `check_work_order_disposition.py` so a completed-folder file at
  a non-completed status FAILS instead of hiding. Phase 2 changes CI gate behavior → operator
  awareness flagged in the WO. No app/test/ADR/INV surface.
- **WO-0121 — Reconcile accepted safety-doc labels with current state (HUMAN-GATED).**
  Dated, additive amendments only: close the stale "pending REV-0033" labels (F003) and record
  the completed import/mypy ratchets (F004). Edits accepted ADRs + INVARIANTS = human-gated
  surface → operator approval + independent review before reliance. Zero semantic change; every
  edit is a note that makes the record match already-shipped behavior.
- **WO-0122 — Close the CI/pin coverage gaps.** Add the conformance oracle to CI (C002, the
  cheapest high-value fix), author failure-capable INV-051/052 lock-liveness pins (F002),
  fix/delete the stale inert-pin fixture (C101). Touches `tests/**` + `.github/workflows/ci.yml`
  → the CI edit is additive (adds a gate, never loosens one); mutation-prove the new pins.

## Operator decisions (batched — needed before the routed work can be authorized)

- **O-1 (F005) — WO-0029 re-cut. RESOLVED 2026-07-20 (Ameen: yes).** Executed same day:
  WO-0029 → SUPERSEDED (moved to `work/completed/`), verified-open items re-cut as WO-0124
  (SPEC-06/07), WO-0125 (CC-04), WO-0126 (CC-05). Original text retained below as history:
  The umbrella mixes landed items (SPEC-05/08/09/10 done) with
  genuinely-open classes (CC-04 replay/read-model parity, SPEC-06/07 cancel-convergence, CC-05
  truthful `replaces_used` projection). **Recommend:** planning seat re-cuts ONLY the verified-
  open classes into 2-3 scoped WOs, marks the landed rows historically. Authorize the re-cut?
- **O-2 (F006) — W3/W4 launcher hygiene. RESOLVED 2026-07-20 (Ameen: yes).** Executed same
  day: both W3 launchers deleted (ledger row `W3-LAUNCHERS`); `W4-SEED-NOTES.md` gained a dated
  currency-correction block separating live seeds from closed debt. Original text retained:
  `W3-README` + `W3-KICKOFF-PROMPT` are finished-wave
  launchers safe to delete; `W4-SEED-NOTES` mixes useful research seeds with false gate/debt
  claims (ADR-010 accepted, INV-089 closed the price-poison it lists as open). **Recommend:**
  delete the two W3 launchers (ledger row), refresh W4 notes to separate live seeds from closed
  debt. Approve the deletion batch?
- **O-3 (F007) — the stranded Signal Seat (47 commits, `archive/claude-wo-0001-install-checks-2x5ys8`).**
  **RESOLVED 2026-07-20 (Ameen): path (a) — revive properly against current master.** The
  feature belongs in beta. "Properly" is a sequenced effort, NOT an immediate implementation:
  (1) **resolve the ADR-009 BLOCK first** — REV-0022 returned BLOCK on F-001..F-004; ADR-009 is
  still Proposed, and no implementation may rely on it until Accepted (human-gated + independent
  review); (2) **planning-seat reconciliation pass** — diff the 47 archived commits (which
  predate R2 / envelope / WO-0113) against today's tree, classify keep/rewrite/drop; (3) scoped
  implementation WOs with schema/auth/event-log gates, **sequenced AFTER Lane P (WO-0114)** — both
  edit `app/store/*` + `app/models.py`, so they must not run concurrently. WO-0102/0103/0104 stay
  CURRENT-BLOCKED until the ADR clears and the reconciliation plan lands. Step 2 is read-only and
  may proceed concurrently with Lane P/Session 2.

## Protocol notes (low; fold into `.ai-os/core/15_CROSS_MODEL_REVIEW.md` when convenient)

- **P-1 (C104):** state whether a reviewed party may edit a reviewer-owned `result.md` (the
  disclosed WO-0113 vocabulary substitutions were verified content-neutral, but the protocol is
  silent). Recommend: forbid, or require a separate disclosed addendum rather than in-place edit.
- **P-2 (C105):** WO-0110's review lived only in PR threads. Recommend: gated-surface changes
  get a tracked `REV-*` packet even when the review happens in a PR conversation.

## Sequencing

WO-0120 first (truthful records unblock everything and the checker prevents recurrence), then
WO-0122 (CI/pins, independent), then WO-0121 (needs the O-decisions settled only if they touch
the same ADR/INV lines — they don't, so WO-0121 can run in parallel once operator-approved).
The three O-decisions gate only their own routed planning; none blocks WO-0120/0121/0122.
All three WOs are `work/`-and-doc scoped except WO-0122's additive CI/test files — none touches
app execution code, so the whole batch is parallel-safe with the beta-feature roadmap.

---

## F008 closure records — DRAFT (land through WO-0120, not written elsewhere)

> Each stamps its own retrospective-recording date so no record pretends to be contemporaneous.
> Transcribed verbatim from the Claude-seat re-derivation auditor.

### DRAFT 1 — append to `work/review/REV-0029/disposition.md`

```markdown
## Round-2 verdict received + round-3 closure (recorded retrospectively per AUDIT-0002 F008)

**Round-2 verdict: BLOCK** (`result-round2.md`, pinned `70b5567`, diff `abfbae9..70b5567`) —
P0-1/P0-2/P0-3 still-open, P1-1 still-open, P1-2 instance-only, P1-3 red; P0-4/P0-5
closed-by-property; three new findings (NEW-P0-1 inert sibling pin, NEW-P1-1 substring T1.3
gate, NEW-P1-2 tracked `.agents/.codex` contamination). The "Round-2 update" table above
predates this verdict; it is retained unaltered as history.

**Round-2 disposition: ALL EIGHT FINDINGS ACCEPTED.** Independently re-verified by the Claude
seat's triage embedded in the WO-0109 draft (`7e59a9e`). NEW-P1-2 resolved immediately
(contamination removed `e0da97d`; CI guard `aba8052`). The rest remediated by **WO-0109**
(Clusters A-E: `5b4e742`, `1e14189`, `3f85656`, `d12596d`, `51dee57`; close-out `0236591`),
red-first, dual-store, mutation-verified per cluster.

**Round-3 review: REV-0030 — ACCEPT** (`REV-0030/result.md`, commit `cc79a7b`; reviewer Claude,
independent of the Codex implementer; range `7e59a9e..51dee57` at `0236591`). Zero findings.

**Gate state: CLEARED.** The REV-0029 merge gate (rounds 1+2 BLOCK) was cleared by the REV-0030
ACCEPT. Subsequent PR #9-head deltas were separately gated: WO-0110 (Codex PR-reviewer delta),
WO-0111 (REV-0031 → RESOLVED via WO-0113), WO-0112 (REV-0032 → RESOLVED via WO-0113), WO-0113
(REV-0033 → RESOLVED, `cdb7dd9`). Operator merged PR #9 at `88833e3d` (ledger PR-0009-MERGE).
**REV-0029 disposition status: RESOLVED.** No historical review body was altered by this closure.
```

### DRAFT 2 — new file `work/review/REV-0030/disposition.md`

```markdown
---
type: Review Disposition
rev_id: REV-0030
verdict_received: ACCEPT
disposition_status: RESOLVED
date: <fill at write>   # recorded retrospectively per AUDIT-0002 F008; verdict received 2026-07-18
remediated_by: none required
implementation_sha: "51dee57"   # reviewed WO-0109 range 7e59a9e..51dee57 at head 0236591
---

# Disposition — REV-0030

REV-0030 (reviewer: Claude, independent of the Codex implementer) reviewed the WO-0109 round-3
remediation (`7e59a9e..51dee57` at `0236591`) and returned **ACCEPT** with zero findings
(`result.md`, commit `cc79a7b`). Nothing to remediate; this disposition closes the packet loop
`.ai-os/core/15_CROSS_MODEL_REVIEW.md` requires.

## Gate effect
This ACCEPT cleared the REV-0029 merge gate (round-1 + round-2 BLOCK) from the review side. It
did not authorize the merge itself: later PR #9-head deltas were separately reviewed (WO-0110
via the Codex PR reviewer; WO-0111 via REV-0031; WO-0112 via REV-0032; WO-0113 via REV-0033,
all RESOLVED), and the operator merged at `88833e3d` (ledger PR-0009-MERGE).

**REV-0030 disposition: RESOLVED.** WO-0109's header status flip ships with the WO-0120 hygiene
change, not with this file.
```
