# Phase-gate ADR drafts — beta → live capital

- **Status:** DRAFTS, unratified. These are proposals for operator ratification; none self-executes and
  none binds until accepted and landed under `docs/adr/`.
- **Numbering:** next free id is **ADR-016** (`ADR-011` is reserved for the W4 entry-envelope seed per
  `work/queue/W4-SEED-NOTES.md:17-19`).
- **Origin:** WARGAME-ROADMAP hazard 4, re-cut per the hazard register.

## The ratification precondition nobody has asked for yet

**The terminal state of this roadmap is not currently a ratified project goal.** Three artifacts say so:

- `pkl/project/goals.md` (authority: high, status: active): *"Beta target: usable, feature-rich,
  **paper-only** trading platform. Live trading remains disabled by config."*
- `CLAUDE.md` safety core rules 1–2: *"No live trading in beta — `PAPER` or `LIVE_SHADOW` only"* and
  *"Alpaca Paper only for beta."*
- No artifact in the repo sequences past D-2a. `docs/REARCHITECTURE_ROADMAP.md` ends at Phase 6
  (migration); the ratified `SIGNAL-SEAT-R5b-TO-D2a-SEQUENCING-PLAN.md` ends at signal-seat enablement.
  The phrase "live capital" appears in exactly one file: the war-game kickoff.

So **ADR-016 through ADR-019 cannot be ratified as a group without first amending the goals page and the
safety core.** That amendment is itself a human-gated surface (ADR text) and is the correct first
decision, not a formality to be swept in with the technical gates. It is listed as **P-0** in the
sequencing proposal.

This is not an obstacle the drafts try to route around. Stating it is the point: a roadmap whose
destination contradicts the repo's highest-authority goal statement is exactly the kind of obligation
that would otherwise live only in an agent's working memory.

## Why the ladder has four transitions and the kickoff named three

`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md:337` ratifies a five-rung ladder:

```
PAPER → LIVE_SHADOW → LIVE_MICRO → LIVE_CONTROLLED → LIVE_PROD
```

That is **four** transitions; the kickoff names three gates (beta→shadow, shadow→small-capital,
small→full). The drafts below reconcile this by giving `LIVE_CONTROLLED` and `LIVE_PROD` **one ADR with
two distinct evidence sets** rather than inventing a fourth gate the kickoff did not ask for — but this
is a judgement call and is flagged as an explicit operator decision in ADR-019.

Separately, `SPINE §14` describes `LIVE_SHADOW` itself as *"emulated→released, log-only"* — two states
inside one rung. ADR-016 must decide whether emulated→released is separately gated; the draft proposes
that it is, because "released" is the first moment a real order reaches a real venue.

## Evidence-ratchet form

Every gate below is written in the same five-part shape, chosen so that a weak run produces a loud
refusal rather than a soft judgement:

1. **Entry** — what must be true to *enter* the phase.
2. **Evidence** — named, machine-checkable artifacts. An evidence item that cannot be evaluated by a
   script is not evidence; it is an opinion, and it belongs in §5 instead.
3. **Exit** — what must hold to promote out.
4. **Ratchet** — what can never loosen afterwards. Ratchets only tighten; loosening one is a new ADR.
5. **What this gate does NOT prove** — the residual, stated in the ADR itself so that a later reader
   cannot mistake a cleared gate for a broader guarantee. **This section is mandatory.** Its absence in
   the seed control is what made "promote at N clean sessions" sound like a safety property.

---

# ADR-016 (draft) — `LIVE_SHADOW` execution mode: architecture and producer independence

**This is not a gate. It is the prerequisite that makes gates possible.**

## Context

`LIVE_SHADOW` has zero code substrate. Verified: `app/config.py`'s `Settings` (`:176-304`) declares no
execution-mode field; the only mode-adjacent knob is `broker_adapter` validated to
`{auto, mock, alpaca}` (`:220-221, 585-589`); `app/broker/factory.py:24-64` constructs only
`MockBrokerAdapter` or `AlpacaPaperAdapter`. `CLAUDE.md:27` cites `LIVE_SHADOW` as an acceptance
criterion as though it were operative.

The architecture document already names the failure mode this ADR exists to prevent —
`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md:320-321`: *"determinism holds inside the seam… Real Alpaca and
real wall-clock are outside it — **live-shadow soak against paper is a separate activity; don't
conflate.**"* That warning is prose and nothing enforces it.

## Decision (proposed)

1. **A `LIVE_SHADOW` soak compares two independently produced sides.** The ADR must name both producers
   at `file:line` rigor, to the standard ADR-009 set for the signal seat. Alpaca sells no live-shadow
   product, so what constitutes the second side is a genuine design question this ADR must answer, not
   assume.
2. **Producer independence is enforced in code, not documentation.** The comparator refuses to run when
   both sides derive from the same producer. **A committed negative fixture proves the refusal** — it
   constructs a same-producer comparison and asserts it is rejected. Without this fixture the mode is
   not built, regardless of how much code exists.
3. **`emulated` and `released` are separately gated.** `released` is the first moment a real order
   reaches a real venue and must not be reachable by the same config change that enables `emulated`.
4. **The divergence record is a new durable artifact and ships with full coverage.** It cannot reuse
   `work/ledger.jsonl`, whose schema (`{id, title, status, disposition, commit, date, reason}`) is a
   human-authored work-order log, structurally unrelated to a machine-classified runtime record. Per
   AUDIT-0003 P-11, a new durable event type ships with projector/replay/parity coverage **in the same
   work order**.
5. **The divergence taxonomy is code, not judgement.** Classes A/B/C are defined as predicates over the
   record, evaluated by a checker. A class assigned by a human or an agent at read time is exactly the
   motivated reasoning hazard 4 names.

## What this ADR does NOT prove

It does not make any promotion decision. It makes promotion decisions *possible* to state in checkable
terms. Ratifying ADR-017 before ADR-016 lands would bind a gate to a mode that does not exist — which is
the M4a N1 failure narrative, arriving through the ratification process itself.

---

# ADR-017 (draft) — Gate 1: `PAPER` → `LIVE_SHADOW`

## Entry

- ADR-016 landed, including its producer-independence negative fixture.
- P-0 ratified: `pkl/project/goals.md` and the CLAUDE.md safety core amended to admit a live-adjacent
  destination.
- Signal-seat D-2a milestone closed, or explicitly carved out with a recorded operator waiver.

## Evidence (each item must be evaluable by a script)

| # | Evidence | Checkable by |
|---|---|---|
| E1 | The producer-independence fixture is green and the comparator refuses same-producer input | pytest |
| E2 | Every `XA-*` register row of class `CONTRADICTED` is either fixed or carries a dated operator waiver | the XA join checker |
| E3 | The two fail-open branches are closed: the 422 duplicate/terminal collision (XA-04/05) and the 404⟹never-landed inference (XA-01/02) | pytest + XA join |
| E4 | `app.store` is in `.importlinter` Contract 3, and the INV-052 no-`await`-under-lock AST check is green with its negative fixture | `lint-imports` + pytest |
| E5 | Kill-switch behaviour is asserted by at least one `@invariant()` on the existing `RuleBasedStateMachine` | pytest |
| E6 | Every capital limit in `app/config.py` names an INV, or carries an explicit `NO-CONTROL` sentinel row | the coverage checker |
| E7 | `.ai-os/scripts/tests/` runs in CI, and `check_fable_done.py` / `check_work_order_scope.py` / `check_mcp_spec.py` are invoked | CI |

## Exit

All of E1–E7 green on one commit, with the SHA recorded. **No soak requirement at this gate** — there is
nothing to soak until the mode exists; a soak belongs to ADR-018.

## Ratchet

E2–E7 never loosen. A later phase may add evidence items; removing one is a new ADR with its own review
packet.

## What this gate does NOT prove

That the system trades correctly with real money. It proves the *instrument* for finding that out is
built and honest. Every `ASSUMED` register row remains assumed.

---

# ADR-018 (draft) — Gate 2: `LIVE_SHADOW` → `LIVE_MICRO` (small capital)

This is the gate where logic becomes money, and the only one where a soak is meaningful.

## Entry

ADR-017 cleared, and `released` (not merely `emulated`) has been running.

## Evidence

| # | Evidence | Checkable by |
|---|---|---|
| F1 | **N clean released sessions, zero class-A divergences** — with N ratified as a number *before* the soak begins, not chosen afterwards | the divergence checker |
| F2 | Every class-B and class-C divergence is recorded with its class, and the classifier is a predicate, not a judgement | the divergence checker |
| F3 | An **account-level maximum daily loss / drawdown control exists and is enforced**, or its absence is an explicitly ratified operator acceptance recorded in this ADR. *Corrected after M4b F2: a per-position hard stop-loss **does** exist and ships enabled by default (`app/protection.py:48`, `app/config.py:295`). What is absent is an account-level daily ceiling — established by a `daily_loss`/`max_daily`/`drawdown`/`daily_pnl` search, which is an account-level-daily search only. The per-position floor's named residuals are gap-through, a halted book, and non-evaluation on a stale feed (XA-13/XA-14)* | the capital-limit coverage checker |
| F4 | **Kill-switch and flatten fire drill with recorded latency**, reported as three separate intervals — (a) intent-block, (b) in-flight completion, (c) sweep — because they are three different quantities and only (a) is near zero | the drill harness |
| F5 | Money arithmetic: `fold_fills` property-tested against a `Decimal` reference over long randomized fill sequences | pytest |
| F6 | Schema migration on the capital-truth database is snapshot-protected and ledgered (`app/store/sqlite.py:616-620` currently runs `_migrate` unconditionally, including destructive rename-and-rebuild at `:1030-1033`, `:1220-1224`) | CI + a migration fixture |
| F7 | Post-incident evidence is complete: `ORDER_SUBMISSION_BLOCKED` dedupes on `(order_id, reason)`, so a kill-switch hold is always recorded | pytest |
| F8 | The store fails closed on I/O failure — `OperationalError` fault injection asserts `Reducing`/`Halted`, never silent loss | pytest |

## Exit

F1–F8 green, plus an operator ratification recording the **capital ceiling** for `LIVE_MICRO` as a number.

## Ratchet

The capital ceiling may only be raised by ADR-019. F3's answer, once given, is recorded permanently: if
max-daily-loss is accepted as absent, that acceptance is dated and must be re-ratified at ADR-019 rather
than inherited silently.

## What this gate does NOT prove

**F4's number does not transfer to live duress.** A single-operator drill cannot reproduce order-book
pressure or broker degradation; it measures a local-process round trip under artificial conditions. This
limitation is stated here so that no later reader treats a recorded latency as a bound. Nor does any
soak length prove anything about market regimes it did not encounter — N clean sessions in a calm tape
is evidence about calm tapes.

---

# ADR-019 (draft) — Gate 3: `LIVE_MICRO` → `LIVE_CONTROLLED` → `LIVE_PROD`

**Operator decision required:** whether these two transitions share one ADR with two evidence sets (as
drafted) or become separate ADRs. The kickoff named three gates; the ratified ladder has four
transitions.

## Entry

ADR-018 cleared and the `LIVE_MICRO` ceiling held for a ratified duration without a class-A divergence.

## Evidence — `LIVE_MICRO` → `LIVE_CONTROLLED`

| # | Evidence |
|---|---|
| G1 | Every `XA-*` row of class `ASSUMED` that reaches order submission, position quantity, or the kill switch is either verified against the venue, or carries a dated operator acceptance naming the residual |
| G2 | A market-calendar source exists; the three duplicate session classifiers are one; `tests/test_features.py:148-160` is inverted (a half-day is **not** `REGULAR`) |
| G3 | The `session_date` UTC-vs-Eastern decision is landed and every consumer enumerated |
| G4 | The control manifest exists and records **failure-capability with a last-RED date** per control, not existence |
| G5 | The mutation ratchet has a recorded baseline and `MAX_SURVIVORS` is a real number, not the `999` sentinel |

## Evidence — `LIVE_CONTROLLED` → `LIVE_PROD`

| # | Evidence |
|---|---|
| H1 | A full phase-gate audit (AUDIT-000N) has run against this phase, triggered by a mechanism rather than by memory |
| H2 | Every ratchet from ADR-017 and ADR-018 is still green — re-evaluated, not inherited |
| H3 | The residual list from every prior gate's §"What this does NOT prove" is re-read and each item either closed or re-accepted with a date |

## Ratchet

H2 is the ratchet-of-ratchets: promotion re-evaluates every prior gate rather than trusting that it
once passed. This is the direct answer to S-3 proof expiry — evidence is a statement about the code as
it stood that day.

## What this gate does NOT prove

Nothing about market regimes not encountered, counterparty behaviour under stress, or any `XA-*` row
still classed `ASSUMED` under G1's waiver path. A gate ADR is a floor, never a warrant.
