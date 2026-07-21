# Codex kickoff — ULTRA batch (local, 5.6 Sol, workflow orchestration)

> Operator launch prompt, drafted by the planning seat 2026-07-20. Paste into a FRESH local
> Codex session at the repo root with master current (`git pull origin master` first).
> Decision block below is PRE-CHECKED with the planning seat's recommendations: pasting it
> unedited RATIFIES them; edit any line to override. One question needs a value: D-BF-NOW.

---

Codex, you are the implementer seat in `automation-alpaca`, running the consolidated beta-prep
batch. Read `AGENTS.md`, then the `CLAUDE.md` safety core — both bind on everything. Fable v3
discipline: GATE before building, red-first TDD, fresh pasted evidence, FIX blocks with root
cause, close-out (status flip + disposition + ledger + file move) in the same commit as the
finishing work — CI enforces it. No completion claims without evidence. Use your workflow
orchestration for the parallel lanes; the ordering constraints below are hard.

## Setup

- Branch `codex/ultra-beta-batch` from current master. Never push master. No PR unless asked.
- Paper-only. Zero live trading. Alpaca credentials are needed by NO work order in this batch.
- Pytest scratch goes to OS temp (default basetemp) — never repo-root scratch dirs.
- Every WO's own file is its contract: read it fully before its first commit; activate it
  (status → ACTIVE, move to `work/active/`) as its first commit; close it out with the work —
  EXCEPT the four review-gated WOs (see Execution model), which end at `status: REVIEW`.

## Execution model (mode-adaptive)

- **Ultra/orchestrated:** Lanes 1+2 may run concurrently ONLY via isolated agents/worktrees.
  Serialize every WO pair sharing files: `docs/INVARIANTS.md` (WO-0121↔0127), `app/models.py`
  (WO-0114↔0126), `cockpit/**` (WO-0114↔0126), `app/events/**` (WO-0125↔0126). Every
  close-out appends `work/ledger.jsonl` — resolve append conflicts keep-both-lines. Lane 3
  items run serially.
- **Effort allocation (explicit):** WO-0114 runs at your MAXIMUM reasoning effort — it is the
  reason this session is local on your strongest model. If per-agent effort is configurable,
  pin Lane 1's agent(s) to the highest setting. **If it is not configurable, do NOT run Lane 2
  concurrently with Lane 1: complete WO-0114 alone, at full depth, then fan out** — sequencing
  is the effort control when knobs are absent. Elevated (not maximum) effort: WO-0127 (ADR
  semantic drafting) and WO-0124 (gated cancel surface). Lean is fine for the mechanical WOs:
  WO-0119/0120/0128/0129 porting and bookkeeping.
- **Extra High/single context:** run lanes as strict order — Lane 1 → Lane 2 (as listed) →
  Lane 3 → Lane 4 → Lane 5.
- **Review-gated WOs end the session at `status: REVIEW`** (in `work/active/`, packet staged),
  NOT closed: WO-0114 (stage REV-0035), WO-0121 (REV-0036), WO-0124 (REV-0037), WO-0127
  (REV-0034; the human ADR-text approval happens at the post-session merge review — do NOT
  stall mid-session waiting for it). All other WOs close out fully in-session.

## Continuity across pauses and compaction (long session — this WILL matter)

1. **FIRST commit of the session** (before any WO work): create `work/active/ULTRA-BATCH-STATE.md`
   containing (a) the operator's decision block **as pasted** — verbatim, including any edits
   and the D-BF-NOW value; the pasted block is authoritative over the repo copy of this file —
   and (b) a per-WO scoreboard table (WO → status → branch commits → notes). This file is the
   session's durable memory.
2. Update the scoreboard in every WO's activation commit and close-out commit. Mid-WO WIP
   checkpoint commits are allowed (clearly marked, within the WO's lane) so no more than a few
   minutes of work is ever unrecoverable.
3. **After ANY pause, resume, or context compaction:** before acting, re-read in order —
   `work/queue/CODEX-KICKOFF-ULTRA-BATCH.md` (this contract), `work/active/ULTRA-BATCH-STATE.md`
   (where you are), and the active WO's file (what you're doing). Verify with `git log`/`git
   status`, never with conversation memory (AGENTS.md rule 9).
4. Never re-derive a decision from memory: the state file's decision block is the ONLY
   ratification source mid-session. A WO the scoreboard shows closed is never reopened.
5. At session end, the state file's final scoreboard IS the per-WO status-table deliverable;
   move it out of `work/active/` into the close-out report location as your last commit.

## Operator decision block (pre-checked = ratified on paste; edit to override)

- [x] D-SIG-2: ADR-009 re-review = one fresh packet **REV-0034**; reviewer = the CLAUDE seat
      (cross-model rule) — you STAGE the request; the review runs out-of-session.
- [x] D-SIG-3: transport vocabulary = `loopback` default + `tailnet_serve`; **Funnel/public
      exposure forbidden** as a spec-level negative test.
- [x] D-SIG-4: revive the construction-time bind guard + `python -m app` launcher regardless
      of topology.
- [x] D-SIG-5: flag-ON makes ALL sensitive reads operator-key-gated; cockpit key plumbing
      ships in the same change as any enforcement flip (no lockout window).
- [x] D-SIG-6: interim key custody = env-injected static keys, multi-key overlap rotation.
- [x] D-SIG-7: **DECLINE** the archive's multi-exit/single-flight relaxation — signal
      conversion conforms to INV-087 single-mandate + existing single-flight, unchanged.
- [x] D-SIG-8: v1 signal conversion mints the SAME Candidate/SellIntent objects the cockpit
      does; downstream execution identical to manual flow; no new execution lane.
- [x] D-SIG-9: seed `docs/adr/ADR-013-external-ingress.md` (status: Proposed, draft only) —
      the Option-C architecture for TradingView/webhook producers: a thin public RECEIVER
      authenticates the webhook (HMAC/secret), normalizes, and forwards into the private path
      as a keyed producer; the trading API itself is never public. Prereqs named: D-HOST-1
      deployment ADR + acceptance review. (Operator intent: Option C "relatively soon.")
- [x] D-0124: envelope disposition cancels do NOT spend the cancel/replace budget (budget
      guards reprice aggression; wind-down is not reprice churn); `_BUDGET_ACTIONS` + ADR-010
      text aligned to that answer.
- [x] D-0126: the stored `replaces_used` field is REMOVED in favor of the single derived
      counter (not demoted-to-cache).
- [x] D-PROC: WO-0129's protocol policies — P-1: a reviewed party never edits a reviewer-owned
      result in place (separate disclosed addendum only); P-2: gated-surface changes get a
      tracked REV packet even when reviewed in PR threads. Execution-preference bullet is
      promoted into the repo primer.
- [ ] **D-BF-NOW (fill or leave unchecked):** run WO-0115 (real paper-DB backfill
      verification) in this session. Source DB path: `____________________`. If unchecked or
      blank, WO-0115 stays queued (NEEDS-INPUT posture, as ratified).

Already ratified, binding, not re-asked: D-PD1-1..4 (WO-0114 banner), D-SIG-1 = Option A
(localhost-only producer for beta), O-1/O-2/O-3 outcomes, D-BF-6/7. Deliberately deferred to
its own moment: the fresh `signal_records` schema approval (asked at R4 with real DDL).

## The work, by lane

**Lane 1 — SERIAL FIRST: WO-0114 (PD-1 release valve). MAXIMUM EFFORT (see Execution model —
if effort isn't per-agent configurable, run this lane alone to completion before any Lane 2
work starts).** The batch centerpiece and the reason this session is local on your strongest
model. Human-gated event-truth surface; full contract in the WO. On completion, STAGE
`work/review/REV-0035/request.md` for the Claude seat (your own validation never counts as
the independent review).

**Lane 2 — parallel from t=0 (disjoint from Lane 1):**
- WO-0127 — ADR-009 amendment + spec reconciliation + REV-0034 staging (docs/spec/queue only;
  governed by the decision block + reconciliation plan §3/§9/§10). Include the D-SIG-9
  ADR-013 seed here (same docs lane).
- WO-0129 — repo-primer fill + `.env.example` completion + P-1/P-2 protocol amendments (run
  its env-var sweep after WO-0123's config flag exists, or re-sweep at session end).
- WO-0119 — bootstrap (devcontainer + smoke script). WO-0123 — tape recorder (start the
  corpus clock; zero order flow, proven by spy test).
- WO-0120 — governance record-truth + folder-aware checker (Phase 1 records incl. the two
  F008 closure records drafted in `AUDIT-0002-REMEDIATION-BATCH.md`; Phase 2 checker ratchet).
- WO-0122 — CI/pin gaps (conformance oracle into CI is the quick win; INV-051/052 pins
  mutation-proven; stale fixture fix).
- WO-0121 — safety-doc label reconciliation (human-gated docs; annotations only; stage its
  review packet REV-0036).
- WO-0125 — envelope replay/parity (GATE first: implement only the verified residual gap).
- WO-0126 — single-source replace-budget counter (D-0126 answer applies).

**Lane 3 — AFTER Lane 1 lands (shared store files):**
- WO-0118 — perf closure, ALL phases now unblocked (Phase 1 measure → Phase 2 only if the
  stress data demands, Cluster-E constraints → Phase 3 budget). A new-index need is D9-gated:
  it becomes a NEEDS-INPUT line for the operator, never a stall and never landed unapproved.
- WO-0124 — disposition-cancel convergence (D-0124 answer applies; stage REV-0037).

**Lane 4 — after WO-0127's text stabilizes:** WO-0128 — signal test-corpus port onto
`codex/signal-tests-staging` (red by design; NEVER merged red; slice map produced). Pushing
that branch will show RED CI there — expected; state it in the close-out, never "fix" it by
weakening a test.

**Lane 5 — only if D-BF-NOW filled:** WO-0115 per its runbook (planning package §5): quiesce
app → SHA-256 the source → copies only → classify every write → second-open idempotency →
OBS-3 characterization report-only → verdict.

**NOT in this session:** the REV-0034/0035/0036 reviews themselves (Claude seat, after);
Signal Seat R4–R7 implementation (blocked on REV-0034 ACCEPT + schema approval); Entry
Envelope (post-Signal-Seat; corpus accrues via WO-0123 meanwhile).

## Cross-lane rules

1. Human-gated surfaces stop for explicit approval even mid-flow: order submission,
   cancel/replace, kill switch, flatten, event-log truth, schema/migration, ADR text,
   deletions of tests/docs. The decision block above IS the approval for exactly what it
   names — nothing more.
2. Separate commits per WO; never mix lanes in one commit. Ledger is append-only.
3. Batch every NEEDS-INPUT into one running list; never stall an unblocked lane on another
   lane's question. A confirmed P0 on a live safety surface interrupts to the operator
   immediately.
4. Evidence discipline: VERIFIED / UNVERIFIED / BLOCKED / NEEDS-INPUT only, fresh pasted
   output. Never weaken an existing test.
5. End-of-session deliverable: per-WO status table (with commit ids), the three staged review
   packets, the NEEDS-INPUT batch, branch pushed. Nothing merged.
