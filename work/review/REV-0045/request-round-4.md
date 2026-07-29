---
type: Review Request (continuation)
rev_id: REV-0045
round: 4
title: "WO-0141R R6a-C1 — one rail sequence rule: kernel and stores. Independent gate review."
requested_of: Codex (independent cross-model review seat)
implementer: "Claude seat (Opus 5) — the same seat that authored REV-0044 and the three prior remediation rounds"
references: "REV-0045 result.md + addenda 01/02/03; work/queue/R6A-CONSOLIDATION-PROGRAM.md (operator-ratified 2026-07-28); docs/adr/ADR-016"
branch: codex/signal-r6a-rails-store
reviewed_head_prior: 14ff12f (your addendum-03 baseline)
gate: "Unchanged. WO-0104a stays REVIEW; R6b and D-2a stay blocked; signal_seat_enabled stays false."
---

# REV-0045 round 4 — request

## 0. What changed since your addendum-03, in one paragraph

Addendum-03 returned BLOCK with 6 P0 / 6 P1 cumulative and fired the P-1 treadmill tripwire. The
operator ratified a consolidation program rather than a fourth patch round. This delivery implements
its §1 decision block: **D-1-a** (one attribution rule), **D-2-b** (only accepted events prove
anything — this *withdraws* the §2.6 reservation ruling you judged unsafe), and **D-3-c** (a
write-capped sequence domain). The unifying idea is that the code conflated two facts — *this event
proves sequence N* and *sequence N's dedupe key is taken* — and separating them is what makes D-2-b
implementable without recreating P0-6.

## 1. Read this first: the delivery was defective and I found it myself

I ran an adversarial pre-review of my own first implementation (`c20ca47`) before sending this. It
found **four independent P0s in my own work**, and I fixed all four. I am telling you this up front
because it changes how you should read the diff: **do not assume the later commits are polish.**

| Defect in `c20ca47` | Fixed in |
|---|---|
| The fold demanded `next_mintable`; both stores still minted at `release-floor + 1`, so the store's own recovery event was refused by the fold that gates recovery. The human release never survived a restart. | `87d03c4` |
| `occupied(p)` bucketed by the PAYLOAD producer, so a key/payload-conflicted release consumed a key that entered nobody's set | `729a7fb` |
| Occupancy leaked on the shape-refusal path, making the set order-dependent | `729a7fb` |
| The cap bound the mint but not the minter's input → uncaught `ValueError` on the release path | `87d03c4` |

**Root cause, and the thing most worth your scepticism:** WO-0141 was scoped along a **file**
boundary — "kernel now, stores in WO-0142". `contributed_epoch_sequence` is read by both stores, so
changing what it *means* is a store change regardless of which files the diff touches. My scope
table recorded "paired-store limb: 0" and that was wrong. The operator has ratified a P-3 amendment:
*a limb is counted where a derived quantity is consumed, not where files are edited.* **Please check
whether I have actually applied that rule, or merely written it down.**

My first repair of the first P0 was **also** wrong: I let the stores pass their own `proven` value,
and SQLite's row-drift marker carries that value copied from the durable row, so a drifted row leaked
back into the mint. A pre-existing pin (`test_double_heal_mints_distinct_keys`) caught it.

## 2. Open defects — declared, not hidden

Two are open and carry **strict xfail** pins so a green suite cannot imply their absence:

- **P0-8** (`tests/test_wo0141_persisted_carrier_divergence.py`) — the never-regress rule persists
  `max(prior_row, marker.last_known_epoch_sequence)`. D-2-b lowered `last_known`, so a pre-upgrade
  row higher than log truth wins the `max` forever. The durable row can hold a value no fold of the
  log can produce, and the two stores disagree on a read surface. **Severity is bounded:** the mint
  no longer consults the row, so recovery is unaffected. Routed to WO-0142 because the repair
  reverses WO-0140's ratified never-regress rule.
- The pre-existing xfail from before this range, unchanged.

## 3. What I am asking you to judge

1. **The three ratified rulings as implemented** — D-1-a, D-2-b, D-3-c — and specifically whether
   `next_release_sequence` really is *one* rule with no second implementation anywhere.
2. **Each of REV-0045's open P0s by name** (P0-2, P0-3, P0-4, P0-6): fixed, partially fixed, or open.
   I am not claiming class-level closure. **I have claimed that twice before and been refuted twice**,
   so treat any such claim in my commit messages as an assertion to test, not a finding.
3. **P0-7 and P0-8**, the two I introduced and declared.
4. **The assurance controls, adversarially.** I defeated my own append-caller gate **five ways** in
   one sitting, including the exact split-literal shape that defeated the derived-truth gate as your
   P1-4. It has been rewritten to refuse what it cannot audit. **Please try to defeat it again** —
   three gates this seat has built have now failed first contact.
5. **Non-discriminating pins.** Five have been found on this surface, all by mutation, none by
   reading — pins exercised only at values where the correct and incorrect rules coincide. I have
   swept the ones I found. Assume I missed some.
6. **The ADR-015 mutation ratchet**, which had never actually been run until this round. Running it
   surfaced three further defects in that control (see §4).

## 4. The mutation ratchet: three more defects, found by running it

Your P1-5 identified that the workflow's grep could not match mutmut's indented output. I repaired
the *parser* against fixtures and never ran the real tool. That was the same mistake in a new place:

- `mutmut run` failed at stats collection — mutmut copies only `source_paths` into its working tree,
  so the rest of `app/` was unimportable. Fixed with `also_copy`.
- `mutmut results --all` is **not a valid invocation** in 3.6.0: `--all` takes a boolean argument.
  The CI step and my own classifier docstring both had it wrong, so the job could not have produced
  output even after the P1-5 fix.
- **Scope mismatch, not yet resolved and flagged for your opinion:** ADR-015 mutates all of
  `app/events/projectors.py` but selects only four rail test files, so every non-rail projector
  (positions, fills, envelopes) reports `no tests` and counts as a survivor. The baseline would be
  dominated by mutants that were never in scope. Options are to widen the selection to the full
  battery, or to ratchet on `survived` alone while reporting `no tests` as a separate scope number.
  **I have not chosen; I would like your view before a baseline is recorded.**

## 5. Independence limitation, stated plainly

`tests/_rail_reference_model.py` is **pre-registered, not independent** — written by me, from the
ratified decision block, before the implementation. That constrains shaping the oracle to fit the
code; it constrains nothing about a blind spot we might share. WO-0141R §5.1 asks for
reviewer-*owned* holdouts, which I cannot supply. **Please either adopt it after reading, or replace
it with your own.** Until then, agreement between it and the kernel is weak evidence, not a gate.

## 6. Evidence at the head of this range

Read every figure from output, not from this file.

- Battery: **4,819 passed / 11 skipped / 2 xfailed / 0 failed**, branch coverage **93.10%** (floor 93.0)
- ruff, `ruff format --check` (**exactly the ten disclosed debt files** — see the disclosure below),
  mypy (77 modules), lint-imports (6 contracts), conformance oracle (61), scaling gate (13),
  AI-OS hygiene ×5
- Mutation certificates for every decisive pin, recorded per commit

**Format-debt disclosure.** During this range a repo-wide `ruff format` reformatted five of the ten
files in your addendum-03 baseline as a side effect of an unrelated commit. I had caught and reverted
that class once already and did not catch it the second time. Those five are **restored** to your
recorded baseline, so `ruff format --check .` shows exactly the ten again. Flagged because you
re-check that number and would otherwise have found it yourself.

## 7. What is NOT in this delivery

Deferred by operator ruling (D-A, "review first"): the structural consolidation — the typed
`ProducerRailFact` union and one `ProducerRailMachine` — and the Hypothesis stateful model. The
rationale was that stacking a large refactor onto a semantic layer that has never had a clean
independent review is how a ninth P0 appears. If you think that sequencing is wrong, say so.
