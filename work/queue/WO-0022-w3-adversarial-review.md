---
type: Work Order
title: W3 adversarial review — in-process critic agents + independent Codex gate (post WO-0016..0021)
status: DRAFT
work_order_id: WO-0022
wave: W3
model_tier: strong
risk: medium
disposition: []
owner: Ameen (gates the W3 merge; independent review is policy-mandatory for WO-0017/0019 + ADR-010)
created: 2026-07-11
---

# Work Order: W3 adversarial review (two-layer, per the CAMPAIGN-0001 design)

## Goal

After WO-0016..0021 are all dispositioned, run the two-layer adversarial pass that CAMPAIGN-0001
validated — (A) in-process critic **agents** with inlined criteria, then (B) independent Codex
review — against ADR-010 *and* its implementation, and gate the W3 merge on the outcome. This WO
produces review artifacts and FINDINGs only; fixes go to follow-up WOs.

## Preconditions

- WO-0016..0021 CLOSED with dispositions and ledger entries.
- Full gate green on the W3 branch tip: `ruff && mypy && lint-imports && pytest -q` (paste output).
- Branch state per `work/queue/W3-README.md` (single integration branch, pinned commit).

## Phase A — in-process critic agents (Claude Code)

Run as **subagents**, one per lens, against the pinned W3 tip. **Subagents do not load CLAUDE.md —
every agent prompt must inline the criteria below verbatim** (this is the known review-correctness
failure mode; do not reference files the agent won't read).

Inline block for every agent prompt:

```
Safety invariants under review (violation = finding, severity per impact):
H1  No venue action (submit/cancel/replace) can violate an envelope hard rail:
    floor price, qty ceiling (fills-only decrement), cooldown floor, replace budget,
    max outstanding=1, TTL, allowed session phases, side=SELL, reduce-only.
H2  Hard rails freeze (BREACHED/EXHAUSTED, terminal-pending-human); they are never clamped.
    Soft bounds (trail range, participation cap, aggressiveness) are clamped AND logged.
H3  Kill switch => all envelopes FROZEN before any further plan or write; HALTED/kill checks
    are atomic with durable writes (no await between), both stores.
H4  Manual flatten preempts: symbol's envelopes frozen/cancelled in the same atomic unit,
    BEFORE flatten proceeds; envelopes can never race, block, or outlive flatten.
H5  Write-time re-validation is independent of plan-time; disagreement => FROZEN +
    ENVELOPE_PLAN_DIVERGENCE event, zero venue calls.
H6  Stale/NaN/non-finite/crossed data => fail closed + the envelope's stale-data disposition;
    bad data never drives sizing or submission.
H7  Ambiguous/timeout broker response on any leg => TIMEOUT_QUARANTINE, deterministic
    client_order_id, never blind-resubmit; envelope pauses while quarantined.
H8  Only deduped fill events change position/remaining qty; acks never do.
H9  Amendment by supersession only; no two ACTIVE envelopes per intent at any instant.
H10 Every autonomous action is an ExecutionEvent with ADR-008 provenance + envelope_id;
    envelope state is replayable from the log; memory and sqlite stores agree.
H11 UI observes and issues intents only; alpaca-py only inside the adapter; single writer.
Verdict per finding: severity P0-P3, reproduction command, decisive output pasted.
```

Agent lenses (≥ one finding attempt each; "no findings" requires stating what was tried):

- [ ] **spec-attacker** — attack ADR-010 itself: under-specified edges (partial fill during
      FROZEN, supersession while an order rests, budget semantics across restart, DST/session
      boundary math), contradictions with ADR-001/002/003/008.
- [ ] **interleaving-attacker** — concurrency: enumerate await points in the approval unit and
      engine seam; try to construct a sequence violating H3/H4/H5/H9 (REV-0019-F-001 shape).
- [ ] **test-critic** — could each WO-0021 test ever fail? Weakened assertions, missing dual-store
      variants, hypothesis strategies that can't reach the edge, red-green not actually proven.
- [ ] **completeness-critic** — re-read every ACCEPT-shaped claim in the WO close-outs and hunt
      what it omits (the CAMPAIGN-0001 role that recovered W2-STALE/W2-SESS).

Output: `work/review/REV-00XX/phase-a.md` — findings table, reproduction evidence, and an explicit
list of claims Phase A could **not** falsify.

## Phase B — independent Codex review (the actual independent seat)

- [ ] Hand Codex the prompt at `work/review/W3-codex-review-prompt.md` + the pinned commit on the
      authoritative env (Python 3.12.13, clean single-commit checkout, per REV-0020/0021 practice).
- [ ] Scope: ADR-010 acceptance, WO-0017 + WO-0019 gated surfaces, and independent re-derivation
      of at least H1, H3, H4, H5 by running its own reproductions (not reading Phase A first;
      Phase A results are shared only after Codex's verdict, then reconciled).
- [ ] Verdict format per `AGENTS.md`: BLOCK / ACCEPT-WITH-CHANGES / ACCEPT, findings with repro.

## Close-out

- [ ] Reconcile A+B; every finding → FINDING file + follow-up WO or explicit human-accepted risk.
- [ ] Ledger entry (RESULT_SUMMARY_KEPT) naming: gates cleared, gates open, dual-confirmation
      status per finding.
- [ ] ADR-010 status flips to Accepted (or Amended) only on Ameen's mark after Phase B.
- [ ] Merge of the W3 branch is blocked until this WO is dispositioned.

## Allowed paths

```yaml
allowed_paths:
  - work/review/**
  - work/ledger.jsonl
  - docs/INVARIANTS.md   # tripwire registrations only
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - cockpit/**
  - tests/**             # fixes and new tests belong to follow-up WOs
  - .github/workflows/**
  - .ai-os/**
```

## Notes

- Fable FULL. Never review your own work while holding the context that produced it: Phase A
  agents get fresh contexts; the implementing session must not author the Phase A prompts' answers.
- Quality-engineer/self-review does not count as Phase B (CLAUDE.md review policy).
