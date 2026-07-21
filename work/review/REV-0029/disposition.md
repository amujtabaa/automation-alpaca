# REV-0029 — builder disposition (RESOLVED; closure recorded retrospectively 2026-07-20)

> **Verdict acknowledged: BLOCK — and it is correct.** Every finding was independently re-verified
> against the source by the builder before this disposition; none is disputed. Three real
> order-execution correctness classes (P0-1/2/3) survived all six in-process lenses — one lens affirmatively
> mis-verified P0-1 as "convergence" and another mis-read the P0-3 gating code (OBS-2) — which is
> precisely the failure mode the independent-review gate exists to catch. The merge gate stays
> CLOSED until the remediation WO lands and re-review returns ACCEPT.

## Branch hygiene note (reviewer-side, resolved)

The reviewer's final commit `06abd3f` ("rev") accidentally `git add`-ed its session's untracked
agent-tooling library (403 files, ~92k lines under `.agents/`+`.codex/`) onto the branch. Verified
pure contamination (zero non-tooling changes; all review artifacts already present at `abfbae9`).
Dropped via operator-approved `reset --hard abfbae9` + force-with-lease push; `.gitignore` now
guards both trees. No review content was lost.

## Disposition by finding

| Finding | Disposition | Status |
|---|---|---|
| **P0-1** flatten mints beside `CANCEL_PENDING`/venue-uncertain BUY | **ACCEPTED** — builder re-verified: `CANCEL_PENDING→FILLED` is a live edge and outside `OPEN_BUY_STATUSES`; the in-process "convergence" claim was wrong | → remediation WO |
| **P0-2** approved-Candidate handoff / no cross-side claim rail | **ACCEPTED** — builder re-verified: candidate dispatch has no same-symbol exit check | → remediation WO (carries a policy sub-question for the operator) |
| **P0-3** needs_review does not gate stage/claim; direct scans UNRESOLVED-only | **ACCEPTED** — builder re-verified: `needs_review_child_order_ids` consumed by zero rails; OBS-2 was false | → remediation WO (carries THE posture question for the operator) |
| **P0-4** inert hold-vs-resurrect pin | **FIXED** (this commit): pin now drives `initialize()` (guaranteed per-owner reconcile), no blanket except, asserts zero `envelope_delegation_restored` events. **Mutation-proven**: strict→widened restore keying flips it RED; reverted, green | ✅ closed |
| **P0-5** CI-form coverage claim not reproducible (AppTest 3s flake) | **FIXED** (this commit): `default_timeout=30` on all FIVE AppTest call sites (the named one + 4 same-class siblings), stays hang-sensitive; 31/31 green under the exact failing mode (`--cov` instrumentation). Baseline debt, not an R2 regression — as the reviewer noted | ✅ closed |
| **P1-1** monitoring's narrower lineage universe | **ACCEPTED** | → remediation WO |
| **P1-2** lossy close-parity pin | **FIXED** (this commit): comparison upgraded to canonicalized FULL model dumps (payloads, reasons, actors, identity relations, quantities, prices, source/authority; ids mapped in first-appearance order, timestamps collapsed, sequences kept verbatim). The retry/restart + rollback-injection extension rides with the remediation WO | ✅ core closed |
| **P1-3** perf: structural sound, wall-clock red, stress convex | **ACCEPTED as ACCEPT-WITH-CHANGES-shaped**: dedicated perf WO stays in the operator batch; no re-budget, no silent green | → perf WO (batched) |
| Docs falsified by P0-1/2/3 (ADR-010 §3/§4, INV-090, INV-081, PD-1 premise, plan OBS-2) | **CORRECTED** (this commit): each site carries a dated `Correction 2026-07-18 (REV-0029 …)` marking the gap as an OPEN DEFECT under remediation — accurate current-state description, no silent rewrite of the record | ✅ closed |
| PD-1 assessment (valve sketch constraints: no synthetic fills; human provenance vocabulary missing) | **ACCEPTED** — folded into PD-1 as a dated correction; constraints bind the future valve design | ✅ recorded |
| Oracle-legitimacy, close-implementation, human-gate/scope audits (green findings) | Noted with thanks — the D1 reseed, P-A sweep, and authorization chain stand as reviewed | — |

## The remediation WO (draft scope — operator ruling needed on two embedded policies)

One scoped work order (next free id), TDD, both stores, own REV re-review before the merge gate
re-opens:

1. **P0-1:** split `CANCELLABLE_BUY_STATUSES` (= today's three) from
   `FLATTEN_BLOCKING_BUY_STATUSES` (+ `SUBMITTING`, `CANCEL_PENDING`, `TIMEOUT_QUARANTINE`); the
   store signals BUYS_OPEN while ANY blocking BUY is non-terminal; the facade's bounded retry
   fails closed (409) if ambiguity persists — never cancels ambiguous orders blindly. Pins: every
   non-terminal status, cancel/late-fill interleavings, bound, override survival.
2. **P0-2:** cross-side same-symbol rail at the FINAL claim in both stores (BUY blocked while an
   exit obligation may execute; SELL blocked while a BUY may execute) + close the Candidate
   handoff per the operator's ruling below. Pins: the approval-pause race, post-mint BUY creation,
   both claim orderings, manual + protection paths, full submission sweep.
3. **P0-3:** stage + final claim fail closed on same-lineage `needs_review_child_order_ids`;
   direct-SELL dispatch/claim scans widen to `RECOVERY_OPEN_STATUSES`, per the operator's posture
   ruling below. Pins: recovery present before stage AND appearing between stage and claim, both
   lanes, both stores.
4. **P1-1:** monitoring loads the same bounded identity universe as the store projector (parent /
   owner-correlation / order-owner / symbol), warns on ambiguity, cancels nothing unvalidated.
   Pins: correlation-keyed + order-owner-keyed hostile cases, both stores, restart.
5. **P1-2 extension:** close-parity scripts gain retry/restart + rollback injection.
6. Doc corrections flip from "OPEN DEFECT" to amended-and-closed wording as each lands.

> **RATIFIED (Ameen, 2026-07-18, via structured prompt): Policy A = (a) full submission
> quarantine; Policy B = (a) stand down + rails.** Both as recommended. The remediation WO
> (WO-0108) executes on these rulings.

**Policy question A (P0-3 — the needs_review sell-side posture).** Codex: authorizing a new SELL
claim beside known-untracked fills would need explicit ratification. Options: (a) full submission
quarantine — no new SELL stage/claim for the symbol while any needs_review exposure is open
(consistent with the ratified P-B retention + TIMEOUT_QUARANTINE posture; the PD-1 valve becomes
the release); (b) keep X-003-style freedom for fresh intents (requires new ratification + ADR
rewrite; sells beside unknown fills). **Builder recommends (a).**

**Policy question B (P0-2 — the approved-BUY-candidate handoff).** Options: (a) flatten/protection
atomically stand down PENDING/APPROVED same-symbol BUY candidates (audited), AND dispatch refuses
while an exit obligation exists, AND the claim rail backstops — belt-and-suspenders, mirrors
D-013a's close-time candidate expiry; (b) dispatch-refusal + claim rail only (candidates survive,
BUY resumes after the exit resolves). **Builder recommends (a)** — a human flattening a symbol
wants out; leaving an authorized BUY armed contradicts the command's intent.

## Round-2 update (2026-07-18 — WO-0108 remediation landed)

All round-1 BLOCK findings are now remediated on `consolidate/r2-canonical`, red-first pins on both
stores, full native gate + full suite green:

| Finding | Closure |
|---|---|
| P0-1 | ✅ WO-0108 step 1 (`3b8f0bd`) — `FLATTEN_BLOCKING_BUY_STATUSES` = full non-terminal set; facade fails closed on venue-uncertain BUYs |
| P0-2 | ✅ WO-0108 step 2 (`e4564ab`), Policy B — cross-side claim rail (`MAY_EXECUTE = NON_TERMINAL − {CREATED}`) + candidate stand-down + dispatch-refuse, both stores |
| P0-3 | ✅ WO-0108 step 3 (`a9c4960`), Policy A — stage + final-claim rails on `needs_review_child_order_ids`; direct-SELL scans widened to `RECOVERY_OPEN_STATUSES` |
| P0-4 | ✅ `321320c` (mutation-proven inert-pin fix) |
| P0-5 | ✅ `321320c` (AppTest `default_timeout=30` on all five sites) |
| P1-1 | ✅ WO-0108 step 4 (`188ed70`) — monitoring owner-scoped identity universe (parent + correlation + order-owner) |
| P1-2 | ✅ core `321320c` + variants WO-0108 step 5 (`37188a3`) — restart / retry / rollback-injection |
| P1-3 | → dedicated perf WO (batched; not a merge blocker per round 1) |
| Docs | ✅ ADR-010 §4 + INVARIANTS INV-090 self-cross / needs_review corrections flipped OPEN DEFECT → amended-and-closed as each fix landed |

New durable hardening from the post-mortem: `pkl/process/review-hardening.md` (Tier-1/2/3 rules) +
`tests/test_review_hardening_gates.py` (T1.1 enum-total + T1.3 producer/consumer, CI-blocking).

## Gate state

BLOCK stands until round-2 review ACCEPT. The round-2 request is queued at `request-round2.md`
(same-Codex second round, per ratification): it asks for closure BY PROPERTY, not by instance, and
carries the PROC-0001 fresh-probe obligation for the amended INVs. Merge gate reopens only on an
`ACCEPT` / `ACCEPT-WITH-CHANGES` verdict + a recorded round-2 disposition. No PR, no merge, nothing
beta-relevant relies on this trunk meanwhile. PD-1 stays parked (post-merge WO).

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
