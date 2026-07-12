---
type: Work Order
title: Multi-leg envelope lifecycle + synthetic-fill envelope bridge (F4+F5, paired by necessity)
status: DRAFT — awaiting human gate approval (order submission surface; event-log truth)
work_order_id: WO-0025
wave: W3 remediation (REV-0022 Phase A; blocks ADR-009 acceptance recommendation)
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-12
---

# Work Order: multi-order envelopes must complete; every fill must reach the envelope counter

**Pairing is mandatory:** F4's false-divergence freeze currently masks F5's venue leg. Fixing the
livelock alone converts the synthetic-fill bypass into a live oversell (200 sh vs 100 ceiling,
reproduced). One WO, one review.

## Context packet (authoritative)
- work/review/FINDING-W3-multileg-false-divergence-livelock.md (F4: SPEC-04 + CC-02)
- work/review/FINDING-W3-synthetic-fill-envelope-bypass.md (F5: CC-01)
- app/sellside/policy.py (has_working_order predicate, :222-224, :306-307)
- app/store/core.py plan_stage_envelope_action structural checks (:2836-2863)
- app/monitoring.py `_apply_inferred_fills` (:2184) vs stream bridge (:1851-1875)

## Scope
1. **Unify the working-order predicate (F4):** plan time derives "working order" from LIVE order
   state, not monotone event history; define the post-terminal-child SUBMIT path (tranche N+1,
   stop-triggered continuation). ENVELOPE_PLAN_DIVERGENCE regains its "software defect" meaning.
   ADR-009 amendment defining the predicate ships with the change.
2. **Record-first bridge for inferred fills (F5):** reconciliation-inferred fills on
   envelope-linked orders route through `record_envelope_fill` BEFORE `append_fill`, same
   canonical dedupe key as the stream path; envelope-attributed FILL event provenance.

## Allowed paths
```yaml
allowed_paths: [app/sellside/policy.py, app/store/core.py, app/store/memory.py, app/store/sqlite.py, app/monitoring.py, tests/**, docs/adr/ADR-009-execution-envelope.md, docs/INVARIANTS.md]
```

## Done-when
- [ ] decide→stage integration pins, both stores: tranche fills → second tranche stages and
      submits; stop-triggered continuation after full fill; disposition-cancel then re-entry.
      Zero false ENVELOPE_PLAN_DIVERGENCE events across all three.
- [ ] Resume after a genuine divergence still freezes (the tripwire still bites — mutation-check
      the unified predicate).
- [ ] Inferred-fill repro pinned strict: after a synthetic fill, envelope remaining decrements
      once; the 200-vs-100 venue sequence is unreachable; both stores; dedupe key parity with the
      stream path (replay a stream fill after an inferred fill of the same venue fill → one
      decrement total).
- [ ] ADR-009 amendment (working-order predicate + inferred-fill provenance) recorded; INV-082
      wording updated.
- [ ] Full gate green.
