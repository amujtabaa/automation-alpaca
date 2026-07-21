---
type: Review Result
rev_id: REV-0034
title: "ADR-009 Signal Seat remediation + current-tree spec reconciliation — independent verdict"
reviewer: "Claude (independent; builder Codex)"
reviewer_seat: Claude
target_work_order: WO-0127
commit_range: origin/master..31d133d
frozen_semantic_range_reviewed: c90a7ae..8a76a29
review_target_ref: origin/codex/ultra-beta-batch (HEAD 31d133d)
human_gated_surfaces: [ADR-text, order-submission-design, auth-transport-design, event-log-design, schema-design]
date: 2026-07-21
verdict: ACCEPT-WITH-CHANGES
---

# REV-0034 — Independent review of the ADR-009 remediation amendment (WO-0127)

## Verdict

**ACCEPT-WITH-CHANGES.**

The F-001..F-004 remediation is **genuine in substance**. Re-derived from the current tree (not
the builder's claims), amendments A-1..A-4 faithfully close each REV-0022 BLOCK finding per the
reconciliation plan §3 "Master action" column, the exposure rewrite consumes the INV-090
obligation projection exactly as plan §9 requires (no reintroduced parallel derivation), D-SIG-7's
multi-exit relaxation is declined, D-SIG-3's transport narrowing and Funnel-negative-test are
present, ADR-013 is a correctly gated Proposed seed, and every governance-hygiene rail holds
(status stays Proposed, no colliding archive REV ids, no `ADR-009-ACCEPTED` ledger import,
INVARIANTS touched only by a non-normative cross-reference, downstream WOs stay draft). **Zero
`app/**` or `tests/**` files are touched in WO-0127's lane.** This clears the G1 gate that lets
Signal Seat R4-R7 proceed, **contingent on the two required changes below.**

The changes are docs-accuracy, not design or safety defects, so they do not warrant a BLOCK; but
they must be applied before Ameen flips ADR-009 Proposed→Accepted, so a clean ACCEPT is not
appropriate either:

- **C-1 (P2, required):** Every `app/**:line` and `docs/INVARIANTS.md:line` citation in the
  amended ADR-009 and specs is **stale on the assigned review target (HEAD 31d133d)**. They
  resolve exactly at the WO-0127 lane tip `8a76a29` (upper bound of the packet's frozen range
  `c90a7ae..8a76a29`) but drift on the integrated HEAD because later same-batch app commits
  (WO-0114/0124/0126) grew `app/store/core.py` +670 lines. Re-baseline the citations — or convert
  to symbol-anchored form (the symbols are stable and correct) — against the tree ADR-009 actually
  merges onto. Detail in Finding F-A.
- **C-2 (P3, required):** Reconcile the review-range provenance. The packet frontmatter says
  `commit_range: c90a7ae..8a76a29`, but the WO's own Fable evidence cites a "semantic head
  `7fa9985`" and target `d32dfb1..7fa9985` that is **unresolvable in the repo** (orphaned by the
  `8815d85` "remap integrated lane commit ids" rebase). The packet's stated rule — "the dispatching
  integrator must replace the frontmatter range with the exact equivalent integrated range" — must
  be honored before the disposition relies on a range. Detail in Finding F-B.

Nothing in the never-reviewed clause set (A-1 clause 6 / D-1a, final A-4, the two locked A-3
clauses, the D-SIG-7 outcome) is asserted-closed without substance; all are explicitly flagged to
the reviewer in `work/review/REV-0034/request.md`, and the ADR keeps them Proposed / "re-review
owed" rather than claiming closure.

---

## Findings

### F-A (P2, required change C-1) — ADR/spec source anchors are stale on the review-target HEAD

**Where:** `docs/adr/ADR-009-signal-seat-boundary.md:47,127-130,202-203,207,251`;
`docs/spec/signal-seat/05-conversion.md:75`; `docs/spec/signal-seat/04-auth-and-api.md:85`;
and the INVARIANTS anchors referenced from the reconciliation plan / specs.

**Why it matters:** The plan §3 ("all anchors refreshed to current file:line") and the WO's own
acceptance criterion #4 ("anchor-verification greps pasted for every refreshed citation") make
anchor accuracy an explicit deliverable. On the ref I was assigned to review
(`origin/codex/ultra-beta-batch`, HEAD `31d133d`), the deliverable is not met — the citations point
at the wrong lines. Independently verified (`git show <ref>:<file> | sed -n`):

| Citation in ADR/spec | Content at frozen `8a76a29` (correct) | Content at HEAD `31d133d` (stale) | Actual location at HEAD |
|---|---|---|---|
| `store_backed.py:786-789` (split-await `gate.approve`/`create_order_for_candidate`) | `await gate.approve(candidate_id)` | `raise ConflictError("session is closed…")` | line **869** |
| `core.py:887` (candidate planner) | `def plan_create_order_for_candidate(` | `raising ``error``.` | (relocated) |
| `core.py:981-998` (candidate sizing reads) | `qty = candidate.suggested_quantity` | `"order_intent_blocked_quarantine",` | line **993** |
| `core.py:1401` (`project_envelope_obligation`) | `def project_envelope_obligation(` | comment line | line **1474** |
| `routes_trading.py:289,299,318` (envelope routes) | `@router.get("/envelopes", response_model=list[ExecutionEnvelope])` | `@router.get("/orders/{order_id}", …)` | line **346**, and `response_model` renamed `ExecutionEnvelope`→`EnvelopeView` |
| `INVARIANTS.md:829/891/978` (INV-087/090/091) | INV-087 / INV-090 / INV-091 headers | BREACHED-chain / oversell / WIDENED-predicate body text | (relocated) |

**Mechanism (not builder fault, but still must-fix):** `app/store/core.py` went 4894→5564 lines
between `8a76a29` and `31d133d` via later same-batch commits — WO-0114 (`759eff0`, `ffd818b`),
WO-0126 (`108874f`), WO-0124 (`e7ea5fd`, `ffac1b3`, `138e389`). WO-0127's docs lane landed first
with anchors correct-at-the-time; batch integration then shifted the code beneath them. The cited
**symbols all still exist** at HEAD (found by grep: `gate.approve`→869, `project_envelope_obligation`
→1474, `RECOVERY_OPEN_STATUSES`→893, `/envelopes`→346), so this is navigational staleness, not
fabrication or a design defect.

**Deeper reason it must be fixed regardless:** these anchors point at `app/**` code owned by *other*
batch WOs, which is **not** part of WO-0127's merge to master. When ADR-009's docs land on master,
the app tree is different again (master merge-base `3b8c840` has neither the 4894- nor 5564-line
core.py). The citations therefore must be re-verified against whatever tree the ADR finally
accompanies.

**Resolution:** Re-baseline all `app/**:line` and `INVARIANTS.md:line` citations to the merge tree,
or (preferred, drift-proof) cite by stable symbol name with line as a hint. Note two citations
that do **not** drift and need no change: `app/models.py:893` (`RECOVERY_OPEN_STATUSES`) and
`app/api/routes_system.py:48` (`POST /api/session/close`) — both resolve identically at `8a76a29`
and `31d133d`.

### F-B (P3, required change C-2) — Dangling review-range provenance (`7fa9985`)

**Where:** `work/active/WO-0127-…md` Fable evidence ("self-contained against semantic head
`7fa9985`"; "REV-0034 targets `d32dfb1..7fa9985`") vs `work/review/REV-0034/request.md` frontmatter
(`commit_range: c90a7ae..8a76a29`).

**Why it matters:** `git cat-file -t 7fa9985` → *"Not a valid object name"*; `d32dfb1` likewise
does not appear in the batch log. The `8815d85` "batch: remap integrated lane commit ids" commit
rewrote lane ids (it edited `REV-0034/request.md` and `ULTRA-BATCH-STATE.md`), orphaning the
`7fa9985` reference the WO evidence still cites. The frozen range that *does* resolve and against
which the anchors are self-consistent is `c90a7ae..8a76a29` (both endpoints exist; `8a76a29` is an
ancestor of HEAD). The packet itself mandates the integrator update the range on any commit rewrite.

**Resolution:** Reconcile the WO evidence and the packet frontmatter to the one true integrated
range (`c90a7ae..8a76a29`), and drop/repoint the dangling `7fa9985`/`d32dfb1` references so the
disposition cites a resolvable range.

### F-C (informational, no change) — WO-0127 correctly parked at `status: REVIEW` in `work/active/`

`work/active/WO-0127-…md` is `status: REVIEW`, with no ledger row and no move to `work/completed/`.
This is **not** a "done-but-not-dispositioned" violation of the CLAUDE.md close-out rule — it is the
batch's explicit review-gated exception for a human-gated ADR change (WO acceptance criteria state
disposition/ledger/move are "deliberately deferred" until REV-0034 + Ameen's text approval).
Recorded for the disposition's awareness; no action.

---

## Per-finding F-001..F-004 remediation status

| REV-0022 finding | Amendment | Plan §3 "Master action" executed? | Substance verified (file:line) | Never-reviewed clause flagged in request.md? | Status |
|---|---|---|---|---|---|
| **F-001** transport/credential boundary (reads unauth; TLS/key-lifecycle unspecified) | **A-1** | Yes — `tailnet_serve` narrowing + Funnel-forbidden negative test; route matrix extended to envelope routes + `POST /api/session/close`; key lifecycle; construction-time launch capability | ADR `:105-196`; spec 04 `:11-12,81,85,107`; loopback default + fail-fast bind; `compare_digest`; N-key rotation; fail-closed reads-included matrix | Yes — A-1 clause 6 / D-1a (request.md "Never-reviewed" #1) | **REMEDIATED (design); re-review owed** |
| **F-002** approval→intent not atomic | **A-2** | Yes — adopted near-verbatim; forbidden split-await re-anchored | ADR `:200-238`; single lock/transaction, all-or-nothing, Option E recorded; forbids `store_backed.py` split-await | Joint-enablement flagged (#6); archive-CONFIRMED-CLOSED at REV-0024 | **REMEDIATED** |
| **F-003** freshness deferred + exposure predicate | **A-3** | Yes — formula/skew/atomic-recheck verbatim; exposure **rewritten onto the projection** | ADR `:240-280`; `expires_at=min(…)`, ±skew; `project_committed_sell_exposure` consumes `project_envelope_obligation`/`RECOVERY_OPEN_STATUSES`/INV-091; fail-closed; cross-consistency pin | Yes — two locked A-3 clauses (quantity-truth #3; single-mandate #4) | **REMEDIATED** |
| **F-004** unbounded rejected-count; no pre-parse limits | **A-4** | Yes — adopted; REV citations converted to archive-ref | ADR `:282-386`; auth→rails→64 KiB→parse; non-refilling budget [1,1000] cap 1000; linearizable debit; durable rail state; 1 `PRODUCER_QUARANTINED`/epoch; rails-presence guard | Yes — final A-4 (#2) | **REMEDIATED** |

All four are remediated in substance and remain Proposed pending this review + Ameen's approval.
None is asserted-closed without substance. This ACCEPT-WITH-CHANGES verdict clears the G1 gate for
R4-R7 once dispositioned and C-1/C-2 are applied.

### Point-by-point re-derivation (challenge results)

1. **Scope — PASS.** WO-0127 lane commits (`c90a7ae`, `ba2e358`, `8a76a29`, `961fa7e`) union to
   docs/pkl/work only; `git show --name-only` grep for `^(app|tests)/` → **NONE**. The batch's
   large `app/**`+`tests/**` diff belongs to other WOs (0113/0114/0118/0124/0125/0126…), not this
   lane. Forbidden-paths block in the WO lists `app/**`, `tests/**`, `cockpit/**`, `.github/**`. No
   P1 scope violation.
2. **Status Proposed — PASS.** ADR-009 `:3` = "**Proposed — remediation drafted 2026-07-20;
   REV-0034 pending.**" Action Items `:393-395` (flip / disposition / unfreeze) remain unchecked.
   Not flipped in-session.
3. **F-001..F-004 substance + never-reviewed flags — PASS.** Per the table above; request.md
   "Never-reviewed / explicitly high-risk clauses" enumerates all four (A-1 clause 6, final A-4,
   both locked A-3 clauses) plus D-SIG-7/8, joint enablement, ADR-013.
4. **A-3 derives from projection, not parallel sum — PASS (strong).** ADR `:249` "One shared
   committed-exposure projection, **no hand sum**"; `05-conversion.md:104` "**consumes** the INV-090
   obligation projection rather than deriving neighboring exposure"; `06-invariants.md:49` "consumes
   `project_envelope_obligation`; **it never creates a parallel delegation/retention definition**";
   INVARIANTS cross-ref echoes the same. Coalescing by immutable `(local_order_id, broker_order_id)`
   identity, `needs_review` at full recovery qty, fail-closed on ambiguity, cross-consistency pin
   with `_same_symbol_exit_may_execute`. INV-090 forbidden parallel-derivation pattern is **not**
   reintroduced. Internally consistent across ADR + 05 + 06 + INVARIANTS.
5. **D-SIG-7 multi-exit DECLINED — PASS.** ADR `:270-272` "no multi-exit relaxation … preserves the
   existing sell-intent single-flight rule and INV-087"; `05:36-37,145`; `06:48`. Matches the
   ratified DECLINE; the relaxed clause is not present.
6. **D-SIG-3 transport — PASS.** `tailnet_serve` + loopback default + Funnel-forbidden spec-level
   negative test (ADR `:105-116`; `04:11-12,107`). Option A producer is the v1 posture (banner
   `:20-24`). ADR-013 Option C is Proposed-draft-only, gated behind D-HOST-1 (ADR-013 Status +
   Prerequisites; prereq gates 1 & 5).
7. **Archive REV id collisions — PASS.** No `work/review/REV-002[4567]/` signal-seat dirs added
   (master's pre-existing `REV-0024/` is the WO-0107 Option-B flatten packet — verified by reading
   its `request.md`; not in the branch diff, untouched). Citations use "archive REV-0024/0025"
   provenance form with a disclaiming banner (ADR `:15-18`). `work/ledger.jsonl` grep for
   `ADR-009-ACCEPTED|SIGNAL-SEAT-SPEC-LOCK|WO-0102-SCHEMA-APPROVAL` and archive REV rows → **NONE
   imported**; no WO-0127 ledger row (correctly deferred).
8. **Anchors — FAIL at HEAD / PASS at frozen range.** See Finding F-A. This is the basis for the
   ACCEPT-WITH-CHANGES rather than clean ACCEPT.

**Supplementary confirmations:** `WO-0102/0103/0104` all `status: draft` (gated); `pkl/architecture/
signal-seat.md` `status: draft` / `authority: medium`; `docs/INVARIANTS.md` WO-0127 edit is a single
`### Proposed Signal Seat cross-reference (non-normative; WO-0127)` block that states "**without
adding, deleting, relaxing, or amending an invariant**" and "has no implementation authority" — zero
invariant-body edits in the WO-0127 lane. ADR-013 confines the public surface to a stateless
Receiver with zero execution authority and a never-public trading API.

---

## Ran vs. read

**Ran (independently executed against the branch — did not trust builder evidence):**
- `git diff --stat origin/master..origin/codex/ultra-beta-batch`; per-commit `git show --name-only`
  scope grep (confirmed zero `app/**`/`tests/**` in WO-0127 lane).
- `git log`, `git merge-base --is-ancestor`, `git cat-file -t` (established lane commits; proved
  `7fa9985`/`d32dfb1` unresolvable; `8a76a29` is an ancestor of HEAD).
- `git show <ref>:<path> | sed -n '<line>p'` for every anchor at three refs (`8a76a29`, `7fa9985`,
  `31d133d`) — the primary evidence for Finding F-A.
- `git show …:app/store/core.py | wc -l` at both refs (4894 vs 5564 — drift mechanism).
- `git ls-tree -r` (no colliding REV dirs); `git show …:work/ledger.jsonl | grep` (no forbidden
  import); `git diff … -- docs/INVARIANTS.md` (additive non-normative cross-ref).
- `grep` sweeps of ADR-009, ADR-013, specs 03/04/05/06, pkl page, WO-0102/0103/0104, REV-0022
  result/disposition, REV-0034 request, the kickoff decision block, and reconciliation plan §3/§4/§9/§10.

**Read (relied on as pasted, not re-executed):** the WO's PowerShell "semantic-contract probe", the
17 phase-3 checker tests, and the `check_work_order_scope.py`/`check_pkl.py`/`check_ledger.py`/
`check_fable_done.py` runs. I did not re-run these harnesses; instead I independently reproduced the
load-bearing claim (zero app/test in-lane; anchors) at the git level. **No test execution performed
— docs-only review, none required beyond confirming zero app/test diff.**

---

## Could-not-verify

- **Runtime behavior of A-1..A-4** (bind-refusal, atomic-conversion crash safety, budget
  linearizability/durability, flood-bound constancy): no implementation exists — the ADR is Proposed
  and WO-0102..0104 are draft. Correctly marked UNVERIFIED by design; the review is a design review.
- **The WO's checker-script passes** (`check_work_order_scope.py` etc.): not re-run in this
  environment; substituted an independent git-level scope proof.
- **`7fa9985` semantic head**: unresolvable object; could not verify the builder's evidence was
  captured against it. Verified against the actual resolvable lane tip `8a76a29` instead.
- **Anchor resolution against the eventual master merge tree**: cannot be verified now (master's
  `app/**` tree differs from both `8a76a29` and HEAD `31d133d`) — this is exactly why C-1 requires a
  re-baseline at merge time.
