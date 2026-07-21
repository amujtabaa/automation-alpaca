---
type: Work Order
title: "Single-source replace-budget projection: one counter for enforcement AND display (CC-05 remainder, re-cut from WO-0029)"
status: DRAFT
work_order_id: WO-0126
wave: W3-debt closure (re-cut per O-1, AUDIT-0002 F005)
model_tier: mid
risk: low
disposition: []
owner: Ameen / implementer TBD
created: 2026-07-20
gated_surface: none (read-model truthfulness; enforcement semantics unchanged)
---

# Work Order: `replaces_used` shows the same truth it enforces

## Goal

Close WO-0029's verified-open CC-05 remainder: the cancel/replace budget count is derived from
ONE shared source — the `ENVELOPE_ACTION` event log — consumed by BOTH the policy enforcement
(`app.sellside.policy._replaces_used`) and the read/cockpit projection, so display and
enforcement cannot drift. No second stored writer (the "same truth derived twice" anti-pattern
AUDIT-0001 flagged); the stored `replaces_used` field either becomes derived-only or is removed.

## Context packet

- `work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md` (CC-05) +
  `work/completed/WO-0029-envelope-eventing-terminal-semantics.md` (superseded umbrella; the
  WO-0036 F5 partial: the false models.py comment is already fixed — the read-model is the gap)
- `work/review/AUDIT-0002-priorwork/report.md` F005
- `app/sellside/policy.py` (`_replaces_used` — the enforcement-side counter to share)
- `app/models.py` (the stored `replaces_used` field) + the cockpit envelope column
- `docs/adr/ADR-010-execution-envelope.md` §2/§5 (budget is a hard rail; refused_stale never counts)

## Allowed paths

```yaml
allowed_paths:
  - app/events/**            # the shared counter lives with the projections
  - app/sellside/policy.py   # consume the shared counter (behavior-preserving; pins prove it)
  - app/api/**               # read-model surface exposing the derived value
  - app/facade/**            # only if the read path routes through the facade queries
  - cockpit/**               # the column shows the derived truth
  - app/models.py            # ONLY if the stored field is removed/annotated (flag explicitly)
  - tests/**
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**             # no new stored writer — that is the anti-pattern this WO exists to prevent
  - app/monitoring.py
  - docs/adr/**
```

## Required behavior

- [ ] One pure shared counter over the `ENVELOPE_ACTION` log (respecting `refused_stale` never
      counting, per ADR-010 §5) consumed by BOTH enforcement and display.
- [ ] Enforcement behavior is UNCHANGED — pinned by the existing budget tests staying green plus
      a differential pin (old inline derivation vs shared counter agree across the action corpus).
- [ ] Cockpit/API show the derived value; the stored field cannot drift from it (removed, or
      demoted to a documented cache that nothing enforces from — decision recorded in the WO).
- [ ] Red-first for the read-model truth; both stores where the API reads differ.

## Acceptance criteria

- [ ] Zero drift possible between enforced and displayed budget (single derivation, pinned).
- [ ] Full gates green; Fable DONE with evidence; close-out + ledger with the work.

## Stop conditions

Stop if the shared counter would change any enforcement verdict on the existing corpus — that
means the old derivations disagreed, which is a FINDING to surface, not silently resolve.
Independent of Lane P (disjoint files); may run any time.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.
