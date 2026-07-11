---
type: Work Order
title: Codify the cross-model collaboration lane into the AI OS (v1, piloting via SOL-0001)
status: DRAFT — awaiting human approval (touches .ai-os/**, the vendored OS package)
work_order_id: WO-0023
wave: W3 (process; parallel-safe with all remaining W3 WOs — no app/** overlap)
model_tier: standard
risk: low (docs/templates only; no code, no gated surfaces)
disposition: []
owner: Ameen (owns the OS package; protocol changes are his call)
created: 2026-07-12
---

# Work Order: Cross-model collaboration protocol → AI OS

## Why

The SOL-0001 lane (work/collab/SOL-KICKOFF.md, authorized 2026-07-12) was assembled ad hoc from
first principles + the existing review protocol. It worked because the ingredients existed
(frozen contract, conformance suite, inline invariant block, packet provenance). Future lanes
should not depend on a session re-deriving those rules — and the rules that made it SAFE
(sequencing, workspace isolation, gated-surface exclusion) are exactly the kind that silently
erode when reconstructed from memory. Distill-after-use is the OS's own §12 rule.

## Goal

A sibling page to `.ai-os/core/15_CROSS_MODEL_REVIEW.md`:

- `.ai-os/core/16_CROSS_MODEL_COLLAB.md` — the protocol (v1, status: PILOTING via SOL-0001;
  finalized only after the pilot's close-out folds its lessons in).
- `.ai-os/templates/collab-packet.md` — SOL-KICKOFF generalized into a fill-in template.
- `work/collab/README.md` — thin pointer + directory conventions.
- One-line references from CLAUDE.md §Review and AGENTS.md so both adapters know the lane exists
  (adapter shims only; no protocol text duplicated).

## Protocol content (v1 — distilled from the SOL-0001 design decisions)

1. **Lanes taxonomy.** reviewer (page 15, unchanged) · critic-panel (WO-0022 Phase A shape) ·
   rival-implementer (new) · tape/scenario-designer (new). One seat may hold several lanes but
   only in the mandated order.
2. **Contamination-sequencing rule (named, load-bearing):** a seat holding the reviewer lane
   banks its verdict BEFORE opening any generative lane; post-collaboration review edits are
   factual-correction-only and labeled. Rationale recorded in the page, not just the rule.
3. **Contract-freeze precondition:** a rival-implementer lane opens only against (a) a frozen
   interface, (b) a runnable conformance suite the incumbent passes, (c) an inlined invariant
   block (packets never reference files the model won't read). If any is missing, the FIRST
   work order is to create them — no contract, no lane.
4. **Workspace + safety:** all collab output under `work/collab/<PACKET-ID>/` (or branch
   `collab/<packet-id>`); never `app/**`/`tests/**`/CI; gated surfaces excluded from collab
   code categorically — those ideas route as FINDINGs into the human-gated pipeline.
5. **Empirical arbiter named up front:** every rival lane declares its bake-off harness +
   metrics in the packet BEFORE work starts (for LASE: the W4 replay harness, five metrics,
   per-regime buckets). Deconfliction is measurement; consolidation takes best-mechanism-per-
   bucket; "mechanisms transfer, parameters do not."
6. **Crosswise consolidation:** merges authored by one seat, adversarially reviewed by the
   other; no seat's self-review is ever the only review (unchanged CLAUDE.md rule, extended
   to N models).
7. **Provenance + disposition:** packets carry MANIFEST + evidence-pasting discipline (X-002
   clause); close with a ledger entry and a disposition from {ADOPTED, PARTIALLY_ADOPTED,
   REJECTED, SUPERSEDED} naming which mechanisms moved into the mainline and under which WO.

## Allowed paths

```yaml
allowed_paths:
  - .ai-os/core/16_CROSS_MODEL_COLLAB.md   # new file only
  - .ai-os/templates/collab-packet.md      # new file only
  - .ai-os/AI_OS_MANIFEST.yaml             # register the two new files, nothing else
  - work/collab/README.md
  - CLAUDE.md                              # one-sentence reference in §Review only
  - AGENTS.md                              # one-sentence reference only
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - .ai-os/core/15_CROSS_MODEL_REVIEW.md   # the review protocol is NOT edited by this WO
  - .github/workflows/**
```

## Done-when

- [ ] Page 16 exists, marked v1/PILOTING, cross-linked with page 15; template renders a complete
      packet when filled (verified by diffing a filled copy against SOL-KICKOFF.md).
- [ ] CLAUDE.md/AGENTS.md each gained exactly one referencing sentence; `git diff --stat`
      confirms no other lines moved.
- [ ] Gate green (docs-only, but the full gate runs anyway).
- [ ] A follow-up checklist item is queued for the SOL-0001 close-out: "fold pilot lessons into
      page 16 and clear the PILOTING mark" (that finalization is a separate, future approval).

## Notes

- Timing: parallel-safe now, or after WO-0022 — Ameen's choice. Recommendation: land v1 now
  while the design rationale is fresh; finalize at pilot close-out.
