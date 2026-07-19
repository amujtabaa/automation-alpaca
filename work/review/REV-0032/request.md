---
type: Review Request
rev_id: REV-0032
title: WO-0112 — three round-3 PR #9 follow-ups (exit-preempt CREATED-buy stand-down, protection fail-closed, late-fill cleanup parity)
status: AWAITING_REVIEW
targets: [WO-0112]
human_gated_surfaces:
  - exit-preempt order cancellation (envelope stage / protection / flatten)
  - autonomous protection exit (open_protection_exit)
  - envelope terminal cleanup on a late fill
commit_range: ba6be70..HEAD
branch: consolidate/r2-canonical
created: 2026-07-18
---

> **Context — what this review is.** Internal software-correctness review of a **paper-trading
> simulator** (Alpaca Spine v2): a FastAPI + SQLite / in-memory order-lifecycle engine that runs only
> against a broker *paper* sandbox. No live trading, no real funds, no network / credential /
> authentication surface in scope. "Safety" here means order-lifecycle **correctness invariants** — a
> submitted order is not a fill; only fill events change a position's quantity; at most one exit per
> symbol reaches the venue; a BUY and an exit SELL for one symbol never both reach the venue (§5.3).
> Ordinary defensive QA: confirm three correctness fixes hold by property, and look for a
> counterexample. Findings only; do not push code.
>
> **Domain glossary (bookkeeping terms, not security terms).**
> - *Candidate* — a proposed BUY; PENDING/APPROVED → (dispatch) → ORDERED with a linked BUY order.
> - *Exit-preempt / stand-down* — when an exit is opened, same-symbol buys are neutralized so they
>   cannot re-grow the position being closed.
> - *CREATED order* — minted locally but never submitted to the venue (pre-claim).
> - *MAY_EXECUTE_ORDER_STATUSES* — the non-terminal statuses in which an order may reach the venue
>   (NON_TERMINAL minus CREATED); the cross-side rail keys on it.
> - *FLATTEN_BLOCKING_BUY_STATUSES* — the full non-terminal BUY set (includes CREATED) flatten fails
>   closed on.
> - *Protection exit* — an autonomous PROTECTION_FLOOR SELL opened when price breaches a floor.
> - *Envelope* — the row tracking a symbol's exit obligation; a *late fill* is a broker fill arriving
>   after the envelope is already terminal.

## Your role

Independent review seat, a different model from the author. Re-derive behavior from the diff and
current tests; do not rely on the author's reasoning or the in-process gate output. These three fixes
are PRE-EXISTING R2 gaps you surfaced on the PR #9 delta (`ba6be70`); the operator authorized the
fixes but **not** the merge, and specifically flagged the F1/F3 design choices below for ratification.
Clears the WO-0112 review gate only on your **ACCEPT / ACCEPT-WITH-CHANGES**. Create `result.md`:
each finding `file:line` + a concrete failing sequence + what resolves it. End with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`.

## What you are reviewing

```
git diff --stat ba6be70..HEAD
git diff ba6be70..HEAD
```

- **F3 (P1, §5.3 self-cross re-grow).** The exit-preempt stand-down only expired PENDING/APPROVED BUY
  candidates. A same-symbol BUY already dispatched to a **CREATED order under an ORDERED candidate**
  was neither stood down nor blocking to the exit (`MAY_EXECUTE` excludes CREATED), so after the exit
  SELL went terminal it could claim and re-grow the exited position. **Fix:** a new companion
  `_stand_down_symbol_created_buys_*` (`app/store/memory.py:2785`, `app/store/sqlite.py:4112`, called
  from the candidate stand-down at `memory.py:2783` / `sqlite.py:4110`) locally CANCELs same-symbol,
  `filled_quantity == 0` CREATED BUY orders in the exit's atomic unit — reusing the
  `_cancel_staged_envelope_orders_*` mechanism. The documented `MAY_EXECUTE` exclusion is left intact.
- **F1 (P1, protection wedge / mis-size).** `open_protection_exit` minted the SELL even when a
  same-symbol BUY may execute. **Fix:** fail closed (return `None`, audited `protection_open_deferred`)
  on a `MAY_EXECUTE` buy before minting (`app/store/memory.py:2414`, `app/store/sqlite.py:3759`).
- **F2 (P2, memory/SQLite parity).** A late fill on an already-terminal envelope skipped memory's
  terminal cleanup (nested under the transition-only branch) that SQLite runs unconditionally.
  **Fix:** memory keys the cleanup on `not ENVELOPE_TRANSITIONS.get(stored.status)`
  (`app/store/memory.py:1855`), mirroring `sqlite.py record_envelope_fill`.

## What to verify — closure by property (most important first)

1. **F3 completeness & safety of the local cancel.** Is cancelling a `filled_quantity == 0` CREATED
   BUY during exit-preempt always local-only (never a buy that reached the venue)? Enumerate the BUY
   statuses: does the fix leave every `MAY_EXECUTE` buy for the claim rail / F1 (not blind-cancel a
   venue-uncertain buy)? Does `filled_quantity == 0` correctly spare an establishing-BUY stub while
   still catching every re-grow-capable buy? Is there any same-symbol CREATED buy the stand-down now
   cancels that it should NOT (e.g., one belonging to a different, legitimate intent)?
2. **F3 both-store parity.** Do memory (`iterate self._orders`, project, filter) and SQLite
   (`WHERE symbol=? AND side=? AND status=created`, project, filter) select the SAME order set? Could
   SQLite's stored-status filter miss an order that projects to CREATED (or memory include one SQLite
   drops)? Same audit + execution-event shape on both?
3. **F3 no self-harm.** The stand-down runs inside envelope-stage, protection-open, AND flatten. Can
   it ever cancel the exit's OWN order, an envelope SELL child, or a same-symbol SELL? (It filters
   `side is BUY`.) For flatten (which already handled CREATED buys) is the added call redundant-but-
   harmless, or does it double-handle / double-audit anything?
4. **F1 correctness & coverage.** After F3 cancels CREATED buys, does F1's `MAY_EXECUTE` check catch
   exactly the venue-uncertain remainder? Is returning `None` a safe fail-closed (the monitoring loop
   re-attempts and re-sizes to the true position), and is the deferral audited (not silent)? Together
   do F1 (`MAY_EXECUTE` defer) + F3 (`CREATED` cancel) cover the full non-terminal BUY set like flatten
   — with no status double-counted or dropped?
5. **F2 exactly-once.** On a terminal transition (which used `reconcile_owner=False`), does the moved
   cleanup reconcile the owner exactly once — never twice, never zero? On a transition-less late fill
   does it now cancel a live CREATED child and reconcile? Is memory now byte-parity with SQLite here?
6. **Pin integrity (mutation).** For each pin, can the guarded branch be removed while the exact test
   turns red? (Author verified: neuter the F3 created-buy call — memory & SQLite; the F1 `buy_hit`
   gate — memory & SQLite; the F2 `stored.status` condition — memory.)
7. **Traceability & scope.** Every changed line attributable to WO-0112; no drift in the WO-0108/0109
   exit-preempt / claim-rail invariants, ADR-003/ADR-010, or the paper-only invariants.

## Fresh property probes

WO-0112 adds/amends no `INV-*` (correctness fixes to existing behavior), so PROC-0001 is N/A. Two
fresh end-to-end probes (new scenarios, not pin reruns) — record harness + outcome in `result.md`:

- **F3 (re-grow prevented end to end).** Held position + a same-symbol CREATED BUY under an ORDERED
  candidate → open an exit (envelope stage or protection) → drive the exit SELL to fill → attempt to
  claim/submit the (now-cancelled) BUY. Assert the BUY is terminal (CANCELED) and the position does
  NOT re-grow. Both stores.
- **F1 (defer then proceed).** Held position + a same-symbol SUBMITTING BUY → `open_protection_exit`
  returns `None` and mints no PROTECTION_FLOOR intent (audited deferral). Resolve the BUY to a broker
  terminal → next `open_protection_exit` mints the exit sized to the true position. Both stores.

## Verification commands (each green at HEAD)

```
ruff check .
ruff format --check .
mypy app/
lint-imports
pytest -q
pytest -q tests/r2_conformance_oracle.py
pytest -q tests/test_r2_conformance_oracle_claude.py
pytest -q tests/test_review_hardening_gates.py
pytest -q tests/test_wo0112_pr9_review_round3.py
python -m tests.performance.r2_scaling_gate
```

Author evidence — reproduce, don't accept: full suite green both stores (exit 0); `mypy app/` clean
(64 files); `lint-imports` 6 kept; both oracles + hardening gates green; scaling gate `passed: true`
(limits unchanged); AI-OS hygiene green; contamination guard clean. The three pins were red on the
pre-fix tree (F2 red on memory / green on SQLite — the parity divergence) and each fix was
mutation-verified (five guard-neutering mutations, each turning its exact pin red).
