---
type: Review Request
rev_id: REV-0024
title: ADR-009 re-review — REV-0022 BLOCK remediation (amendments A-1..A-4)
status: QUEUED   # flip to AWAITING_REVIEW at dispatch; re-freeze commit_range if the branch merges first
targets: [ADR-009 (amendments A-1..A-4), docs/spec/signal-seat/**, WO-0102..0104 gating text]
human_gated_surfaces: [order-submission]
prior_packet: REV-0022 (verdict BLOCK, four P1s — this packet exists to verify their closure)
commit_range: ad87a10   # frozen remediation SHA on claude/wo-0001-install-checks-2x5ys8 (REV-0023 is the envelope line's packet; 0024 is next free)
created: 2026-07-14
---

# Review Request REV-0024 — did the A-1..A-4 amendments close F-001..F-004?

## Your role
You are the **independent review seat** — same protocol as REV-0022 (`AGENTS.md` "## Review
guidelines", `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`): re-derive from the repo,
findings only, do not push fixes. This is a **re-review**: your primary question is narrow —
**does each amendment actually close its finding, as binding decision text an implementer cannot
lawyer around?** Regressions or new holes the amendments introduce are in scope; re-litigating
parts of ADR-009 you already passed is not (but is not forbidden if you find something real).

## What changed since your BLOCK (frozen `25590a7` → this range)
- `docs/adr/ADR-009-signal-seat-boundary.md` — new section **"Amendments — REV-0022 remediation"**
  (A-1 transport/credential boundary + route-authorization matrix; A-2 atomic conversion command +
  Option E considered/recorded; A-3 server-owned expiry formula + executable exposure-aware
  risk-reducing predicate; A-4 normative ingest order + epoch-bounded audit). Four clauses in the
  body now point at their amendments instead of the superseded text.
- `docs/spec/signal-seat/00..06` — reconciled to the amendments (02§3 expiry formula, 03§4 epoch
  bound + ingest order, 04§1 transport/key-lifecycle/route matrix, 05§1/§3a atomic command +
  exposure-aware predicate; `PRODUCER_INGEST_REJECTED` removed from the event vocabulary).
- `work/queue/WO-0102..0104` — required-behavior text tightened to carry the amendment test
  contracts (route matrix at the mounted app; crash-injection/interleaving suite; constant
  event-row flood tests; A-3 property tests).
- Governance context (not under re-review, provided for the timeline): your BLOCK was ingested
  2026-07-14, the interim acceptance was rescinded, and the constructed PR#5 record was
  superseded (`work/review/REV-0022/`).

## Questions to answer
1. **F-001 closed?** Does A-1 pin the trust boundary tightly enough — transport policy with
   fail-fast, key lifecycle, principal-derived actor, and the reads-included route matrix? Is any
   sensitive surface still reachable without the operator credential when the flag is on? Is the
   flag-off posture (unchanged localhost no-auth) an acceptable, clearly-bounded state?
2. **F-002 closed?** Is the A-2 atomic command specified strictly enough that a consumed approval
   without an intent (or vice versa) is unconstructible in BOTH stores — including the memory
   `_atomic` snapshot requirement and the no-await rule? Is the required crash/race test matrix
   complete? Is the Option E analysis honest, and is deferring it defensible at beta volume?
3. **F-003 closed?** Is the expiry formula + skew + restart behavior fully server-owned with only
   numeric tuning left to config? Does the exposure-aware risk-reducing predicate (position −
   outstanding committed sell exposure, under the A-2 lock) define its inputs precisely enough to
   implement without further design, and does it preserve the recorded INV-7 asymmetry decision?
4. **F-004 closed?** Is the epoch-bounded audit genuinely finite under indefinite hostility
   (constant events per epoch, counter outside the log, nothing periodic)? Is the normative
   ingest order (auth → rails → 64 KiB-capped body read → parse) sufficient against
   pre-validation resource abuse?
5. **Coherence:** do the amendments contradict each other, the unamended ADR body, the spec, or
   the as-built code they cite? (e.g. A-2's no-await rule vs the existing facade patterns it must
   replace; A-1's matrix vs the cockpit plumbing requirement.)

## Where to look
- `docs/adr/ADR-009-signal-seat-boundary.md` §Amendments (the review target).
- `work/review/REV-0022/result.md` — your own findings, the closure criteria.
- `docs/spec/signal-seat/01..06` — the reconciled contract (implementability check).
- `app/api/deps.py`, `app/main.py`, `app/facade/store_backed.py`, `app/store/memory.py::_atomic`
  — the as-built seams the amendments constrain.
- `work/queue/WO-0102..0104` — whether the test contracts actually carry the amendments.

## Verdict vocabulary
`ACCEPT` | `ACCEPT-WITH-CHANGES` (enumerate) | `BLOCK` (enumerate). Write findings to
`work/review/REV-0024/result.md`; Ameen dispositions in `disposition.md`. An ACCEPT/
ACCEPT-WITH-CHANGES here clears the gate REV-0022 closed: ADR-009 may then be marked Accepted by
Ameen and WO-0102..0104 unfreeze per their sequencing.
