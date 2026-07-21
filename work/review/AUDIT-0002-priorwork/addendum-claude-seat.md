---
type: Review Result (addendum)
audit_id: AUDIT-0002
addendum: claude-seat-deferred-items
reviewer_model: Claude (independent seat; targets built by Codex)
status: COMPLETE
verdict: ACCEPT-WITH-CHANGES
anchor_sha: a58298c
date: 2026-07-20
---

# AUDIT-0002 — Claude-seat addendum: the DEFERRED items

AUDIT-0002 (Codex seat) deferred three items to the other seat because Codex could not
adjudicate its own build/review: **WO-0106** and **WO-0113** (Codex-built), and **re-scoring
the REV-0029 verdicts** (Codex-authored). This addendum closes those deferrals. Two independent
Claude-seat auditors ran findings-only against master `a58298c`; **no repo file was created,
edited, or committed by either auditor** — the findings below are transcribed by the planning
seat into this packet. Both ran fresh test execution + in-process mutation checks (Python
3.11.15, deps installed per CI's `requirements.txt -c constraints.txt`; basetemp in scratchpad,
never the repo root).

## Bottom line

**No live-safety P0.** Every deferred target's substance holds on current master, verified by
fresh runs and mutation checks — including an independent re-derivation of Codex's REV-0029
verdicts, which re-confirm as accurate by property, not merely by instance. Seven additional
P1/low/info findings, all record-truth drift of the same family as AUDIT-0002's ten.

## Part 1 — WO-0106 / WO-0113 verification

| Target | Verdict | Fresh execution |
|---|---|---|
| WO-0113 (primary remediation) | reached-master VERIFIED; optional-not-implemented items accurately recorded; **1 finding (C001)** | 190 packet tests ran green; lineage `194343c..9a7af3b`→`f027752`→`cdb7dd9` all ancestors of merge `88833e3d` |
| WO-0106 (Part A consolidation) | all claims VERIFIED; **1 finding (C002)** | 61/61 conformance-oracle cases ran green; delivered report byte-identical on master; freeze refs byte-exact |

### AUD2-C001 — P1 — WO-0113 completion record frozen at `status: REVIEW` after its gate cleared
`work/completed/keep/WO-0113-codex-primary-remediation.md:4` still says `status: REVIEW` though
REV-0033 is RESOLVED (`cdb7dd9`) and PR #9 merged (`88833e3d`) — both themselves ledgered
(rows 64/65) while row 63 still reads REVIEW. The disposition checker's `COMPLETED` set omits
REVIEW, so a completed-folder file at REVIEW is invisible to every failure branch (fresh run
returned PASSED). Same false-green class as AUD2-F001/F008; postdates the audit window, deferred
to this seat. **Resolves:** flip to a completed status + closure ledger row citing REV-0033
RESOLVED + merge, folded into the AUD2-F001 folder-aware-checker WO.

### AUD2-C002 — P1 — the WO-0106 61-case conformance oracle is not run by CI
`tests/r2_conformance_oracle.py` has no `test_` prefix (deliberate, pre-R2), so CI's single
`pytest` invocation (`.github/workflows/ci.yml:96`) never collects its 61 cases (full-suite
collection = 3,873, excludes them). Healthy today (ran 61/61 green), but the primary WO-0106
deliverable — the spec oracle both seats treat as a per-commit gate — can silently regress
while CI stays green; the no-collect rationale expired when R2 merged. **Resolves:** add
`python -m pytest -q tests/r2_conformance_oracle.py` as an explicit CI step, or `test_`-prefix
the file. Cheapest high-value fix in the batch.

## Part 2 — REV-0029 verdict re-derivation (independent)

Every REV-0029 round-1 finding's claimed closure **re-derives as accurate on master by
property** — enforcing rail + pinning test cited for each, with four in-process mutation checks
flipping exactly the expected pins red (P0-1 both stores; P0-2/P0-3/P0-4 memory-side, sqlite
isolation confirmed):

| Finding | Verdict | Finding | Verdict |
|---|---|---|---|
| P0-1 flatten vs venue-uncertain BUY | VERIFIED (both-store mutation) | P1-1 monitoring lineage universe | VERIFIED |
| P0-2 cross-side claim rail (Policy B) | VERIFIED (mutation) | P1-2 parity comparator fidelity | VERIFIED |
| P0-3 needs_review submission lanes (Policy A) | VERIFIED (mutation) | P1-3 performance | VERIFIED (record trail; gate not run per instruction) |
| P0-4 hold-vs-resurrect pin now live | VERIFIED (mutation) | P0-5 AppTest timeout ×5 sites | VERIFIED (static + green run) |

**The cross-model review machine checks out end to end:** Codex caught the three P0 execution
classes, the Claude seat independently re-confirms their closure holds on master. No claimed
rail or pin was found absent, inert, or misdescribed.

### Additional findings (record-truth, none safety)

- **AUD2-C101 (low)** — a stale "inert sibling pin" shape + misleading comment survives in
  `tests/test_wo0108_rev0029_remediation.py:268-319`; the honest, reason-asserting,
  mutation-proven pin exists at `tests/test_wo0109_round3_remediation.py:366-393` (WO-0109's
  accepted remedy was add-honest-pins, not amend-old). Fix/delete the stale fixture in hygiene.
- **AUD2-C102 (medium)** — confirms AUD2-F008 **and extends it one link**: WO-0113's
  `status: REVIEW` (= C001) is the same gap-class as REV-0029/REV-0030/WO-0109, one step later
  in the chain.
- **AUD2-C103 (low)** — the WO-0108 `SUPERSEDED` relabel now on master via this merge; before
  it, master's copy said ACTIVE. (Resolved by the same merge that lands this addendum.)
- **AUD2-C104 (info)** — builder commit `9d366f5` edited the reviewer's `REV-0029/result.md`
  (2 disclosed vocabulary substitutions; diffed — no finding/verdict/evidence/SHA changed). The
  packet protocol should state whether a reviewed party may edit a reviewer-owned artifact.
- **AUD2-C105 (info)** — WO-0110's independent-review record lives only in PR #9 reviewer
  threads + ledger + close-out, not a `REV-*` packet.

### F008 remediation — drafted closure records (proposals, not yet written)

The second auditor reconstructed the full authoritative chain (REV-0029 r1 BLOCK → WO-0108 →
r2 BLOCK → WO-0109 → REV-0030 ACCEPT → WO-0110/0111/0112 → WO-0113 → REV-0033 RESOLVED → merge
`88833e3d`) and drafted the two missing artifacts F008 requires: a round-2/round-3 closure
section for `REV-0029/disposition.md` and a new `REV-0030/disposition.md`. Both drafts are
retained in the remediation-batch planning note (each stamps its own retrospective-recording
date, so no record pretends to be contemporaneous). They land through the F008 hygiene WO with
operator sign-off, per the close-out rule — not improvised here.

## Deferrals now closed

WO-0106 ✅, WO-0113 ✅, REV-0029 verdict re-score ✅. Remaining AUDIT-0002 Tier-0 exclusion
(ADR-010 / INV-090+ deep semantics) stays out of scope — it was not a deferral, and nothing in
this addendum supplies a cross-tier lead to reopen it.
