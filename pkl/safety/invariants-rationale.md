---
type: Project Rule
title: Safety Invariants — Rationale
status: active
authority: high
owner: Ameen
last_verified: 2026-07-07
tags: [safety, invariants, trading]
source_refs: [docs/SPINE_EXECUTION_ARCHITECTURE_v2.md, docs/adr/ADR-001-overfill-quarantine.md, docs/adr/ADR-002-timeout-quarantine.md, docs/adr/ADR-003-manual-flatten-halted-reducing.md]
supersedes: []
superseded_by: null
---

# Safety Invariants — Rationale

## Summary

The 11 invariants and safety rails live **verbatim in `CLAUDE.md`** so they are always in agent context — deliberately not one indirection away. This page holds the *why*, so the shim stays short.

## Rules / facts

- The normative text is `CLAUDE.md` "Safety core". This page never overrides it; on any divergence, `CLAUDE.md` wins and this page gets fixed.
- Why each cluster exists:
  - **Paper-only / live-disabled (inv 1–2):** the beta's blast radius must be zero real dollars. Live paths aren't "unused"; they're absent-by-config so an agent cannot accidentally enable them.
  - **Backend as truth, thin UI (inv 3–7):** a browser client that owns state or talks to the broker is an unauditable second writer. All mutation flows through one reviewable engine.
  - **Submitted ≠ filled; only fills move positions (inv 8–9):** the classic execution bug is counting intent as reality. Structural inability of `SUBMITTED`/`ACCEPTED` to change quantity makes the bug unrepresentable.
  - **Kill switch gates intent (inv 10):** halting must cut new risk at the front door, not race the pipeline.
  - **Quarantine over rejection (rails; ADR-001/002):** broker reality (overfills, ambiguous timeouts) must be recorded even when unwelcome — hiding it corrupts positions. Deterministic `client_order_id` makes reconciliation possible; blind resubmit makes duplicates possible.
  - **Manual flatten routing (ADR-003):** an emergency control that bypasses risk checks and logging is itself a hazard; the override exists but is explicit and audited.
  - **Fail-fast market data:** garbage quotes driving sizing is a silent capital risk; halting is the safe failure mode.
- Human-gated surfaces (order submission, cancel/replace, kill switch, flatten, mode config, migrations, event-log truth, deletions of tests/docs/ADRs) exist because LLM auto-approval hooks optimize for flow, and flow is the wrong objective on these surfaces.

## Rationale

Safety rules survive by being cheap to obey and expensive to miss. Keeping them always-on in the shim, with rationale here, optimizes both.

## Applies to

- Everything.

## Related pages

- `CLAUDE.md` (normative text)
- `pkl/architecture/architecture-map.md`

## Change log

- 2026-07-07: Created.
