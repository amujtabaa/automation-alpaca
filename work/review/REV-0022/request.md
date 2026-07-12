---
type: Review Request
rev_id: REV-0022
title: ADR-009 Signal Seat boundary — acceptance review (ADR amendment class)
status: QUEUED   # flip to AWAITING_REVIEW and freeze commit_range when dispatched
targets: [ADR-009]
human_gated_surfaces: [order-submission]   # via the WO-0103 conversion gate the ADR authorizes
commit_range: SET-ON-DISPATCH   # freeze to the repo SHA the reviewer will read; docs-only review
created: 2026-07-11
---

# Review Request REV-0022 — ADR-009: Signal Seat boundary (design review, pre-acceptance)

## Your role
You are the **independent review seat** — a different model from the author, on purpose. Read
`AGENTS.md` ("## Review guidelines") and `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md` and
follow them: re-derive from the repo, don't rubber-stamp, **findings only — do not push fixes**.
This is a **design/ADR review** — there is no implementation diff to audit; the question is whether
the *decision* is sound and its safety argument holds against this repo as-built.

## What you're reviewing
`docs/adr/ADR-009-signal-seat-boundary.md` (DRAFT/PROPOSED): admit external agentic signal
producers (exemplar: HKUDS Vibe-Trading) as **untrusted advisors** behind an authenticated HTTP
contract — signal proposals become order intents **only** through per-signal human approval (trust
level L0), with lifecycle provenance in the event log and quarantine rails (TTL/staleness,
rate-limit → producer quarantine). Your verdict gates acceptance; the implementation bundle
(`work/queue/WO-0101..0104`, all status draft) stays frozen until you and the human clear it.

## Questions to answer (at minimum)
1. **Invariant preservation.** The ADR maps CLAUDE.md invariants 1–11 and spine §5 INV-1..9
   (mapping drafted by the implementer seat on install — treat it as a claim, not a fact). Does any
   mapping row overclaim? In particular: does "approval emits a normal order intent, from that
   point no special status" actually hold against the as-built intent path
   (`app/approval/`, `app/facade/commands.py`, kill-switch/`TradingState` gates)?
2. **Human-gate integrity.** Approval = order-submission trigger, a human-gated surface. Is L0 as
   specified actually per-signal human approval with no batch/auto path? Are the L1/L2 escape
   hatches adequately fenced (each requires a superseding ADR + independent review)?
3. **Rails sufficiency.** TTL/staleness, dedupe on producer-generated `signal_id`, per-producer
   rate limits with producer-level quarantine, kill-switch/Halted/Reducing interaction table —
   any missing failure mode for an adversarial or malfunctioning producer (e.g. id-collision
   games, clock skew on `issued_at`, quarantine-release races, event-log flooding)? Also verify
   the recorded **INV-7 asymmetry decision** (ADR-009 invariant table, Ameen 2026-07-11): a false
   "not-risk-reducing" classification silently blocks a protective exit with no downstream
   backstop — does the ADR's remedy (classification conservative toward convertibility, risk gate
   as binding check, operator-visible blocks, manual-flatten fallback) actually close that hole?
4. **Boundary hygiene.** Zero producer code in-repo, OpenAPI-only coupling, no new dependencies —
   consistent with the pinned stack, `.importlinter` contracts, and ADR-005/006 seams? Does the
   Streamlit approval panel spec keep contract 2 (cockpit imports no `app.*`) satisfiable?
5. **Options analysis.** Are rejected options B–D fairly characterized, or is there a stronger
   alternative the ADR should have considered?

## Where to look (curated pointers)
- `docs/adr/ADR-009-signal-seat-boundary.md` — the decision under review (incl. install note).
- `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` §0, §5 — invariants the mapping claims to preserve.
- `CLAUDE.md` — safety core, human-gated surfaces, review policy binding this ADR.
- `work/queue/WO-0101..0104-*.md` — the gated implementation plan the ADR authorizes; check the
  plan cannot outrun the decision (scopes, forbidden paths, escalation notes).
- `app/approval/`, `app/facade/commands.py`, `app/protection.py`, `app/transitions.py` — the
  existing intent/approval/kill-switch path the conversion gate must reuse unchanged.
- `.importlinter` — the five boundary contracts the new surface must not weaken.
- `docs/adr/ADR-001/002/003/008` — quarantine + provenance precedents the ADR extends to signals.

## Out of scope
- WO-0101..0104 execution quality (they are drafts; reviewing their future diffs is a later packet).
- L1/L2 trust-ladder design (explicitly deferred to superseding ADRs).

## Verdict vocabulary
`ACCEPT` | `ACCEPT-WITH-CHANGES` (enumerate required changes) | `BLOCK` (enumerate findings with
severity). Write findings to `work/review/REV-0022/result.md`; the human dispositions in
`disposition.md` per `.ai-os/core/15_CROSS_MODEL_REVIEW.md`.
