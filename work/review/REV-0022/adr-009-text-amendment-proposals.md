# PROPOSAL (not applied) — ADR-009 text amendments for the two Phase A contradictions

Status: DRAFT wording for the human gate / WO-0029(A). The ADR itself is untouched — these are
prepared texts so the gate decision is a yes/no, not a drafting session. (The §5 predicate and
§3/§6 amendments shipped with WO-0025/0027 per their approved charters; the two below CHANGE
decided semantics, so they wait for explicit approval.)

## 1. SPEC-05 — FROZEN + ceiling-overfill must terminate BREACHED, never COMPLETED

Proposed §2/§3 text:

> **Amendment (WO-0029):** a broker-authoritative overfill of `qty_ceiling` is a BREACH in every
> state that can receive a fill. The §3 machine gains the edge `FROZEN → BREACHED`, taken
> atomically when a fill drives `remaining` past 0 while FROZEN (payload keeps the overfill
> facts; ADR-001 order-level quarantine unchanged). The resume path can then never auto-COMPLETE
> a ceiling-violated mandate — resume from FROZEN requires `remaining ≥ 0` reached WITHOUT
> overfill. H2's "hard rails are never clamped" reading is restored: the clamp-to-zero remains a
> bookkeeping floor, but the STATUS records the violation.

Code impact: transitions.py edge, plan_envelope_fill FROZEN branch, resume path guard, both
stores, tests. Replaces the current silently-chosen third option (clamp + flag + COMPLETED).

## 2. SPEC-09 — §5 "write-time rejection ⇒ software defect" is over-broad

Proposed §5 text (extends the WO-0025 predicate amendment):

> **Amendment (WO-0029):** a write-time rejection means the plan's facts went stale OR the
> validators disagree. The seam distinguishes them: a rejection whose rail re-evaluates as
> VIOLATED against the state the plan saw (same inputs → different verdict) is a DEFECT
> (`ENVELOPE_PLAN_DIVERGENCE`, freeze, P1 tripwire); a rejection whose rail only fails against
> CURRENT state (a fill, TTL lapse, phase flip, or position change landed in between) is a
> BENIGN STALE-PLAN REFUSAL — evented distinctly (`envelope_action` outcome=refused_stale, no
> freeze; the policy replans next tick). Operator alarm calibration keys on the defect event
> only.

Code impact: stage seam divergence classification (core.py), a new refused_stale event payload
(NO new event type needed), monitoring surfacing, INV-082 wording, tests. The repo's own pinned
chaos test (`test_partial_fill_between_plan_and_write_hits_the_qty_rail`) becomes the benign
case's pin.

## Sequencing note

Both belong to WO-0029(A) (terminal-state semantics) per the umbrella draft; neither blocks the
other. SPEC-05 is the safety-posture one (a violated mandate currently ends in the SUCCESS
state); SPEC-09 is signal hygiene (made more visible now that WO-0025 removed the false-positive
flood).
