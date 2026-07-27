---
type: Review Result Addendum
rev_id: REV-0044
addendum: 01
title: "R-1 exposure resolved against the operator's live database — NOT AFFECTED"
reviewer_seat: Claude (independent review seat; implementer was Codex)
prior_verdict: ACCEPT-WITH-CHANGES
verdict: ACCEPT-WITH-CHANGES (unchanged)
severity_change: none
urgency_change: "R-1 downgraded from active data risk to latent trap"
reviewed: 2026-07-27
---

# REV-0044 addendum 01 — R-1 is not live against the operator's database

Reviewer-owned addendum; the original **ACCEPT-WITH-CHANGES** stands. New evidence supplied by the
operator on 2026-07-27, recorded because `result.md` §R-1 stated exposure as an open question and that
paragraph would otherwise go stale.

## Evidence

The operator ran the reviewer-supplied diagnostic against the configured durable store
(`ALPACA_DB_PATH`, default `./data/app.db`). Result: **NOT AFFECTED.**

The diagnostic was self-tested in both directions before being issued — it correctly flags the reviewer's
reproduction database (`'legacy-prod': 60 rejections, limits=[50] <-- OVER BUDGET`) and correctly clears a
missing file.

An earlier, broader command issued by the reviewer was mis-scoped — a recursive scan of the whole worktree
that returned ~9,000 lines of `.mypy_cache` and pytest temp `.db` files, exiting 1 on access-denied temp
directories. That output carried no signal about R-1: pytest scratch databases are created and destroyed
per run, which is itself part of why the suite is green while the defect exists. The reviewer's error, and
the narrower diagnostic replaced it.

## What this changes

**Urgency only.** R-1 is not an active data-loss risk. No existing operator data is in danger, and there is
no recovery step to perform. This is consistent with the reachability caveat already stated in `result.md`:
routes are flag-gated, `signal_seat_enabled` defaults false, and flag-on requires a provider that does not
exist after R6a, so a stock database holds no signal events.

## What this does NOT change

**The severity stays P1, and R-1 remains a gating item.** The grade was never a function of this particular
database. It rests on properties the evidence does not touch:

1. The failure is **fail-closed on an append-only log with no repair path** — the whole store, including
   order, fill, position and session truth, not just the seat.
2. It is **flag-independent**, so the usual "the flag is off" protection does not apply.
3. One trigger is **editing a config value** between two ingests — an ordinary act, not an adversarial one.
4. There is **no test for it at all**, and the suite cannot grow one incidentally because CI builds every
   database fresh.
5. Exposure begins the moment the seat is exercised. **R6b writes producer-level events, and D-2a is the
   joint enablement flip** — so today's clean result is a property of the current rung, not a durable one.

A latent trap that is unrepairable when sprung, on event-log truth, is still P1. The remedy is still owed
before R6b.

## Standing

**Verdict unchanged: ACCEPT-WITH-CHANGES.** R-1 and R-2 remain the gating pair, and both still resolve
through the single cache-versus-fold decision recorded in `result.md`. R-1's remediation may now be
scheduled as ordinary work rather than as an incident.
