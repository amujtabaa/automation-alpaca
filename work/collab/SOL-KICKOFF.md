# SOL-KICKOFF — cross-model collaboration packet (GPT-5.6 Sol / Codex seat)

**Status:** authorized by Ameen 2026-07-12 (in-chat). This packet defines the GENERATIVE
collaboration lane for the second model — distinct from, and strictly AFTER, the independent
review role the same seat may currently be performing.

## 0. Sequencing — read this first

If you are mid-review of this repository (a `work/review/REV-*` packet or the W3 review prompt):
**complete that review and deposit its `result.md` verdict BEFORE opening any task below.**
Rationale, stated so you can honor its intent and not just its letter: your review's value is its
independence. The moment you design your own competing policy, you will read the incumbent's
design through the lens of your own choices — bank the uncontaminated verdict first. Do not
revise your review afterward except to correct factual errors, and note any such correction as
post-collaboration.

## 1. What this lane is

Ameen runs a dual-model bench: Claude (implementation seat, Fable v3 discipline) and you. The goal
is both models' best independent work on the HARDEST modules — starting with the LASE sell-side
policy (WO-0018) and the chaos/scenario catalog (WO-0021) — then empirical deconfliction and
consolidation. You are not editing the mainline; you are producing a complete rival body of work
behind a frozen contract, plus critique. The W4 replay harness (pessimistic fill model,
five-metric scorer) is the arbiter between designs; consolidation merges the best mechanisms
per regime through the normal gated pipeline, cross-reviewed (you review Claude's merges;
Claude adversarially reviews your mechanisms before adoption).

## 2. Ground rules (hard)

1. **Workspace isolation.** All your deliverables live under `work/collab/SOL-0001/`. You never
   modify `app/**`, `tests/**`, `docs/**`, `.importlinter`, or CI. If you have repo write access,
   work on a branch named `collab/sol-0001` only.
2. **Gated surfaces are out of bounds for code**: order submission, cancel/replace, kill switch,
   manual flatten, schema/migrations, event-log truth, stores, broker adapters. Ideas about them
   are welcome — as FINDING-style notes (D4 below), never as implementation.
3. **Mechanisms transfer, parameters do not** (`pkl/architecture/sellside-research-notes.md`,
   the extraction rule). Propose mechanisms with rationale and sources; mark every numeric
   constant as a harness-tunable default, not a claim.
4. **Evidence discipline.** Any behavioral claim about your own code ships with the command and
   pasted decisive output. A test that cannot fail is a defect (X-002 anti-pattern — see
   `docs/INVARIANTS.md` preamble).
5. **No live trading anything.** Paper/simulated data only; no network calls in tests.

## 3. The frozen contract your policy must honor

Interface (see `app/sellside/policy.py`, `app/sellside/types.py` at the pinned tip):

```python
decide(envelope: ExecutionEnvelope,
       snapshots: Sequence[MarketSnapshot],   # session-anchored tape; snapshots[-1] is current
       *, now: datetime,                      # injected clock — the ONLY time source
       history: Sequence[ExecutionEvent],     # this envelope's prior events (accounting source)
) -> PlannedAction | NoAction | BreachSignal | ExhaustedSignal | ExpiredSignal | StaleDataSignal
```

Non-negotiables (the same suite the incumbent passes; your variant must too):

- **Purity**: no IO, no global state, no `datetime.now()`/`time.time()`/`utcnow()` anywhere;
  deterministic for fixed inputs.
- **Hard rails breach, never clamp**: floor price, qty ceiling (remaining decremented by deduped
  fills only), cooldown floor, cancel/replace budget, max outstanding = 1, TTL, allowed session
  phases, side=SELL, reduce-only. `validate_action` (same module) is THE rail check — your
  policy must pass its own plans through it; the engine re-runs it at write time (D-3).
- **Soft bounds clamp AND report** (`ClampNote`): trail range (ATR multiples — note the field
  semantics: `envelope.trail_distance_min/max` are ATR MULTIPLES under WO-0018-final),
  participation cap, aggressiveness set.
- **Fail closed on bad data**: stale/None/NaN/±inf/nonpositive/crossed snapshot ⇒
  `StaleDataSignal` with the envelope's disposition. Bad data never drives sizing or submission.
- **Working-stop monotonicity**: the effective stop for the life of the envelope is
  non-decreasing across regime switches, derivable purely from the tape (no hidden state).
- **Trail floor**: no step's candidate stop sits closer to the reference than
  `trail_distance_min × ATR(step)`.
- **Accounting from history only**: cooldown/budget/tranche state derives from the passed
  `ExecutionEvent` history, never internal mutable state.

Conformance = the hypothesis property suite in `tests/test_wo0018_sellside_properties.py` and
the invariant tests in `tests/test_wo0018_sellside_{policy,regime,hygiene}.py`, run against your
module in a scratch checkout (Claude will run this verbatim during consolidation; you should too
and paste the output).

## 4. Safety invariants (inline, verbatim — the W3 review block)

```
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
```

## 5. Context packet (read in this order; do not range wider)

1. `docs/adr/ADR-009-execution-envelope.md` (as amended in-repo — the drop copies are stale)
2. `pkl/architecture/sellside-research-notes.md` (mechanism research; authoritative)
3. `work/completed/keep/WO-0018-pure-sellside-policy/` (the WO + fable-done)
4. `work/queue/WO-0021-envelope-chaos-catalog.md` (regime scenario tapes)
5. `app/sellside/` — the incumbent, all 9 modules (~1100 lines)
6. `docs/INVARIANTS.md` INV-076..081 + preamble
7. `work/queue/W4-SEED-NOTES.md` — harness scoring spec (five metrics) — context only;
   W4 work itself is NOT authorized in this packet either.

## 6. Deliverables (all under `work/collab/SOL-0001/`, with a `MANIFEST.md`)

- **D1 — `design-memo.md` (required).** Two parts. (a) Critique of the incumbent
  `app/sellside/`: where its regime classifier, trail mapping, tranche logic, or detector
  design will underperform or misbehave on thin extended-hours tape — concrete scenarios, not
  vibes. (b) Your alternative design: mechanisms, precedence, failure-mode analysis, sources.
- **D2 — `impl/sol_policy.py` + `impl/test_sol_policy.py` (strongly desired).** A complete
  drop-in `decide()` conforming to §3, plus your own unit/property tests. Pure Python 3.11+,
  imports restricted to stdlib + `app.models` + `app.marketdata.service` + `app.sellside.types`
  + `app.sellside.policy.validate_action` (reuse the shared validator — do not fork it) +
  `hypothesis`/`pytest` in tests. Paste your conformance-suite run output in the manifest.
- **D3 — `tapes.md` (required).** Adversarial/scenario tape designs beyond WO-0021's six:
  snapshot-sequence specs (deterministic generators, no randomness without a seed) that you
  believe break the incumbent and/or showcase your design, each annotated with the expected
  five-metric signature per policy. These seed the W4 bake-off corpus.
- **D4 — `findings.md` (as needed).** Anything you found about gated surfaces / the engine /
  ADR-009 itself that is outside your lane: FINDING-style notes (file:line, why it matters,
  what resolves it). These route into the human-gated pipeline.

## 7. What happens to your work

Claude runs your D2 through the conformance suite and both policies through the shared tape
corpus under the W4 harness when it lands; grading is per regime bucket on the five metrics
(exit efficiency, MAE, Ulcer index, post-exit downside avoided, upside captured vs available).
Consolidation takes the best mechanism per regime into the mainline as gated work orders —
authored by one seat, reviewed by the other. Credit and provenance stay attached via this
packet's paths and the ledger.
