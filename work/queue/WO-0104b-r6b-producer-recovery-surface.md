---
type: Work Order
title: "R6b — the human recovery surface: /api/producers, the release route, cockpit control"
status: DRAFT
work_order_id: WO-0104b
parent: WO-0104a (REVIEW)
branch: TBD — not started
model_tier: strong (LOCAL — human-gated recovery surface, browser-first invariant)
review: "Codex-owned REV packet."
filter_risk: MED
---

# WO-0104b — R6b: the human recovery surface

> **Why this file exists at all.** R6b was referenced as the destination for every deferred
> recovery surface — and as the thing that unblocks the enable gate — while no such file existed.
> An independent merge-readiness assessment named it: carry-forwards routed to a work order that
> does not exist are carry-forwards with nowhere to go.

## What it must deliver

The producer rail's only recovery from an invalid-projection marker is the human release. R6a
builds that recovery in the store; **R6b is what lets a human reach it.** Without it the rail is a
recovery mechanism with no operator interface — safety invariant 11 (browser-first) unmet, and the
ratified claim that release is the single human recovery false in practice.

1. `/api/producers` — operator-authenticated read of rail state, including invalid-projection
   markers, so an operator can SEE a marked producer.
2. The release route — operator-authenticated, routed through session control, risk checks, the
   event log and the single-writer engine, exactly as every other human-gated surface is.
3. The cockpit control — a browser path, not raw-API-only. This is the invariant-11 obligation
   ADR-009 records and R6a explicitly does not discharge.
4. Producer sweeps and rate settings (WO-0104a's own deferred list).

## The gate this WO opens

`app/config.py:SIGNAL_SEAT_HUMAN_RECOVERY_AVAILABLE` is `False`, and
`app/server.py:enable_gate_refusal` refuses to serve with `signal_seat_enabled` on while it stays
that way (**INV-100**). R6b flips it — **in the same change that ships items 1-3**, with the
tripwire test in `tests/test_signal_seat_launch_guard.py` deleted alongside, carrying the evidence
that the route and the control actually landed.

**It must never be flipped to make a suite pass.** That constant is the only thing standing between
a merged-but-unusable recovery path and an operator discovering it the hard way.

## Prerequisites

WO-0141R and WO-0142 cleared by independent review. R6b consumes rail truth; building the interface
on semantics that are still moving would repeat the sequencing error D-4 was ratified to avoid.
