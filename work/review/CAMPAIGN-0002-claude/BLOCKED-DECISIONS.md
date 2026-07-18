# Parked decisions — Part B completion run (R1 lane)

> Decisions the run surfaced that require a NEW semantic choice beyond the D1–D9 ratification
> envelopes (plan §3-R1). Each was parked with the surrounding work completed fail-closed; nothing
> here blocks the run's endpoint. Batched for the operator; REV-0029 should weigh in too.

## PD-1 — The needs-review reconciliation release valve (from P2 / P-B)

**Context.** P-B (ratified D2) now retains a symbol's owner intent while a lineage child has an
open `needs_review` submit-recovery (a stranded broker SELL that HAD fills — real untracked
exposure). Empirically (pinned in `tests/test_wo0036_r2_close_and_recovery_ownership.py`), the
resulting posture is a **complete sell-side quarantine** of the symbol: the retained owner is
projection-controlled (direct stand-down refused), manual flatten fails closed, a "replacement"
intent dedups to the retained owner, and a NEW envelope delegation is refused. This mirrors the
repo's standing ambiguity posture (TIMEOUT_QUARANTINE; "ambiguous broker truth never drives
sizing/submission").

**The gap.** `RECOVERY_TRANSITIONS` makes `needs_review` **terminal** — the machine can record
"a human must reconcile this" but has no vocabulary for "a human HAS reconciled it". The comments
promise it ("a needs_review record is done being worked; **a human resolves**", `models.py:863`;
"stays visible to the operator **until a human reconciles it**", `monitoring.py:2006`) — the
mechanism was never built. Until it exists, the quarantine releases only when the recovery record
leaves `needs_review`, which today is never.

**Decision needed.** Design + authorize the human reconciliation surface. Sketch (not built):
- A new terminal cleanup status (e.g. `RECOVERY_RECONCILED = "reconciled"`), legal transition
  `NEEDS_REVIEW → RECONCILED`, human-gated store API (actor-stamped, audited, co-writing a
  broker/human-authoritative execution event carrying what the human established — e.g. the
  reconciled fill quantity), after which the projection's `needs_review_child_order_ids` no longer
  includes the child and the whole quarantine lifts through the existing machinery (no further
  code needed — verified by how retention lifts in the pins when the status differs).
- Scope: `app/models.py` (vocabulary + transition — D7-style widening), `app/store/base.py` + both
  stores (API), tests both stores. A **human-gated surface** (event-log truth + operator control):
  its own scoped WO + independent review per CLAUDE.md.

**Why parked.** D2's seam was the retention predicate; a new human-facing control API with event
vocabulary is a fresh semantic design choice (what exactly does the human attest? does it ingest
fills?). Beta exposure is acceptable meanwhile: `needs_review` arises only from the hostile
stranded-submit path, the quarantine is fail-closed, and the BUY side / other symbols are
unaffected.

**Recommendation.** Approve the sketch as its own WO after this consolidation merges (or fold its
design review into REV-0029's disposition loop).

**Correction 2026-07-18 (REV-0029):** this memo's premise that the current posture is already a
"complete sell-side quarantine" was falsified by review finding P0-3 — two submission lanes
(stage/claim of a second envelope SELL; direct-SELL scans keyed `RECOVERY_UNRESOLVED`-only) reach
`SUBMITTING` beside a `needs_review` exposure. Closing those lanes is part of the REV-0029
remediation WO, *prior to* and independent of this parked release-valve design. The reviewer also
sharpened the valve's requirements (see `../REV-0029/result.md` "PD-1 assessment"): a status flip
must never act as a synthetic fill; discovered fills enter position truth only as deduplicated
FILL events; and the current `EventSource`/`EventAuthority` vocabulary has NO human-attested
value — mislabeling a human attestation as broker-authoritative is forbidden, so the design needs
an explicit human provenance addition. Fold those constraints into the sketch before approval.
