# REV-0029 — builder disposition (IN PROGRESS, 2026-07-18)

> **Verdict acknowledged: BLOCK — and it is correct.** Every finding was independently re-verified
> against the source by the builder before this disposition; none is disputed. Three real
> execution-safety classes (P0-1/2/3) survived all six in-process lenses — one lens affirmatively
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

## Gate state

BLOCK stands. Re-review (REV-0030 or a REV-0029 second round, reviewer's choice) required after
the remediation WO lands. No PR, no merge, nothing beta-relevant relies on this trunk meanwhile.
