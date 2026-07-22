# Design-Time War-Game — Planning-Seat Pre-Ratification Protocol (v1.0 — ADOPTED)

> **Status: ADOPTED — ratified by Ameen 2026-07-22.** Binding on the planning seat. Recorded in
> `work/ledger.jsonl` (`PROTOCOL-WARGAME-18`). Claude adapter: `.claude/skills/wargame`
> (invoke by name or on any gated/novel-surface decision block). Ratification boxes 1–3 accepted;
> box 4 (`trace_consumers.py` WO) deferred to operator discretion — not authorized in this
> ratification.

Provenance: the WO-0135 miss (2026-07-22). The planning seat pre-ratified decision **D-ML-1..5**
(reuse the `SUBMIT_RECOVERY_NEEDS_REVIEW` ledger for a synthetic malformed-lineage record). The
create side was traced against code and held; the **release** side (`D-ML-5`: "resolved via the
operator's reconcile") was asserted from ADR-012's *prose* and never traced to code. The design was
unsound: `reconcile_submit_recovery` requires a non-empty broker id, a real order, trustworthy
lineage, and a durable claim occurrence — none of which a synthetic record can hold
(`app/models.py:1038`; `app/store/core.py:2998-3001`). Independent review (REV-0040) also found a
**second** unsoundness the war-game never reached: the synthetic record would have permanently
poisoned the symbol's SELL-exposure rails, disabling `flatten_position` for that symbol forever —
because nobody enumerated who *reads* a `SubmitRecoveryRecord`. The GATE caught it and the session
ended BLOCKED, exactly as designed — this protocol exists to catch it one stage earlier, at
ratification, where it costs minutes instead of a launched session.

## Where this sits

This is the **design-time** counterpart to `17_INTERNAL_ADVERSARIAL_REVIEW.md` (implementation-time)
and `15_CROSS_MODEL_REVIEW.md` (post-build independent review). Those attack built code. This
attacks a **decision block / kickoff before it is ratified**, when no code exists yet. It is a
planning-seat obligation. Its output feeds the Fable `fable_gate` `assumptions` and `blast_radius`
fields (`06_FABLE_V3_EXECUTION_PROTOCOL.md`) and the kickoff's pre-checked decision block.

## The two failure classes this exists to prevent

Every mature analysis discipline splits into these two directions; neither alone is sufficient (the
FMEA-vs-FTA lesson). The WO-0135 war-game ran one well and skipped the other.

- **Class 1 — untraced-claim ratification (epistemic).** A design claim is pre-checked with the
  confidence of a verified fact when it was only *inherited from a document* or *assumed*. Cure:
  assumption discipline (M1) + lifecycle totality (M2).
- **Class 2 — unenumerated consumers (topological).** A design writes a new artifact without
  enumerating who *reads* it, so it silently joins existing control loops. Cure: consumer inventory
  + control-action sweep (M3).

M4 (a prospective-hindsight brief plus a fresh-context refutation pass) is the backstop that catches
whatever M1–M3 miss.

## When this runs (scope gate — proportionality is mandatory)

This repo prizes bounded discipline; do not turn this into ceremony. The **scope gate** decides how
much protocol a design earns:

- **FULL war-game (M1–M4)** — a design that meets ANY of: (a) touches a human-gated surface
  (order/cancel/kill/flatten, schema/migration, event-log truth, ADR text, test/doc deletion);
  (b) creates or repurposes a **stateful artifact** (record, event type, status, flag, durable
  field); or (c) **reuses an existing mechanism for a new purpose** — the highest-risk shape,
  because the mechanism's guards were written for the old purpose (the D-ML-1 pattern).
- **LIGHT (M1 only)** — every other decision block: label assumptions, nothing more.
- **NONE** — trivial mechanical or doc-only work with no decision block.

If unsure, treat it as FULL — the same rule the repo already applies to gated surfaces.

## M1 — Assumption ledger on the decision block

Every decision-block line and every load-bearing design claim carries one label:

- `TRACED(file:line)` — verified against current code or accepted text **now**, anchor cited.
- `INHERITED(source)` — carried from a named prior ratified decision; cite it (a ratified decision
  is not re-litigated, but it must be named, not merely felt).
- `ASSUMED` — believed, not verified.

**The load-bearing rule: no `ASSUMED` line may be pre-checked in a FULL-scope decision block.** An
`ASSUMED` item is resolved one of two ways before ratification: traced (promote to `TRACED`), or
converted into an **explicit named mid-session GATE** for the implementer — never left to the
generic gate to catch. `D-ML-5` was `ASSUMED`; this rule forces tracing it (which finds
`models.py:1038`) or naming it a gate.

Trace each assumption with the Key Assumptions Check questions — in particular the one that would
have caught D-ML-5: **"Could this have been true in the past but not now?"** (ADR-012's
occurrence-scoped hardening is exactly a case where an old reuse pattern silently stopped working.)
Also: "Why am I confident?", "What would have to be true for this to be false?", "If it's wrong, how
much of the design collapses?"

## M2 — Lifecycle totality trace

For any stateful artifact the design creates or repurposes, trace **birth → every transition →
every terminal**, and for **each edge** name the writer that can drive it, each with a code anchor.
A lifecycle with any un-anchored edge is not ratifiable. This is Design-by-Contract applied to a
state machine: each transition has preconditions the design's inputs must satisfy — enumerate them
and prove they hold. D-ML-5 anchored birth and dedup but never the release edge; the release edge's
writer had preconditions a synthetic record could never meet.

## M3 — Consumer inventory + control-action sweep

For every row/event/record/field the design writes, enumerate **every reader** before ratification.
Classify each: **unaffected / affected / unknown**. Every `unknown` must be resolved to a code
anchor before ratification — an unknown reader is an unexploded finding (REV-0040 F1). For each
`affected` reader, run the four control-action questions (STPA's UCA taxonomy) against the new
artifact:

1. Is a needed action now **not** taken (or a needed guard now skipped)?
2. Is an action taken that **worsens** safety (a rail now fires that should not)?
3. Wrong **timing/order** (the reader sees the artifact before/after it should)?
4. **Stopped too soon / applied too long** (the artifact persists past its meaning, e.g. an
   unreleasable record blocking a rail forever — the F1 failure)?

The enumeration may be mechanized by `trace_consumers.py` (see Tooling) but the classification is
judgment, never automated away.

## M4 — Pre-ratification refutation pass

Two steps, in order. Both are FULL-scope only.

**M4a — Prospective-hindsight brief (the planning seat, inline, before spending an agent).** Frame
the design as *already failed*, not *possibly failing*: "assume this design shipped and caused an
incident — from the code, explain how it happened." Write the failure narrative in the past tense
and enumerate the causes. The grammatical shift is the technique (Klein's premortem): imagining a
failure that *has occurred* rather than one that *might* measurably surfaces more real causes than
"what could go wrong." Each cause it names becomes an M1 assumption to trace, an M2 edge to anchor,
or an M3 reader to classify — so M4a also seeds and sharpens the M4b brief. Keep it to the planning
seat's own pass; it is inline reasoning, not an agent, and not group facilitation (see "does NOT
import"). This is the standalone home of prospective hindsight — do not let it stay buried as a
framing inside M4b.

**M4b — Fresh-context refutation agent.** Spawn a **fresh-context adversarial agent** whose brief is
to **REFUTE the decision block from code** — not to build, not to improve, to disprove. Give it
M1–M3 plus the M4a failure narrative as its checklist, and the decision block as the target. This is
the repo's own cross-model / internal-adversarial mechanism moved **one stage earlier**: the two REV
agents found the WO-0135 defects in minutes because they carried a refutation brief and had no
drafting bias. The gap was never a missing technique — it was running that pass *after*
implementation instead of *before* ratification.

A FULL design is ratifiable only after M4a's causes and M4b's findings each resolve to a `TRACED`
resolution or a named gate — none left un-resolved.

## Integration

- The labels (M1) live **in the decision block itself**, so paste-ratification ratifies labeled
  claims, not bare assertions.
- M2/M3 outputs live in the WO's context packet (the lifecycle trace and consumer inventory become
  part of the contract the implementer and the eventual REV packet inherit).
- All of it flows into `fable_gate.assumptions` / `fable_gate.blast_radius` — this protocol is how
  those fields get populated honestly at planning time rather than backfilled at build time.
- A design that clears a FULL war-game still gets its normal downstream gates (mid-session GATEs,
  `17` internal review, `15` cross-model review). This is the **first** net, never the only one —
  the same doctrine as "in-process validation never counts as independent review."

## What this deliberately does NOT import (calibration)

The source disciplines carry ceremony built for large human teams and regulators. Importing it here
would be cargo-cult rigor — the opposite of what the repo values. Explicitly rejected:

- **Full STPA hazard-log / causal-scenario documentation.** We take STPA's control-structure
  enumeration (M3) and its four-UCA taxonomy; we do not maintain a standing hazard log.
- **FTA probability quantification.** We are not certifying to a regulator; numeric failure
  probabilities are false precision here.
- **Premortem group facilitation** (independent writing, round-robin, no-seniors-present) — but
  NOT its cognitive core. We keep prospective hindsight (M4a); we drop the group ritual. That ritual
  exists to manufacture candor in human groups; a single planning seat plus a fresh-context
  refutation agent already has the adversarial property without the facilitation scaffolding.
- **A "war-game engine" tool.** The leverage is checklist discipline plus adversarial fresh
  context. Machinery beyond the small `trace_consumers.py` helper would be false rigor.

## Tooling (optional, separate item — not required to adopt this protocol)

`trace_consumers.py` in the existing `.ai-os/scripts/` AST-checker family: given a symbol/entity,
emit every reader and writer with `file:line`, mechanizing the M3 enumeration (the change-impact
dependency-graph idea). It complements M3's judgment; it does not replace it. Spec and build it under
its own bounded WO if ratified.

## Ratification record (Ameen, 2026-07-22)

- [x] Adopt this protocol as `.ai-os/core/18` (design-time war-game), binding on the planning seat.
- [x] Adopt the scope gate (FULL / LIGHT / NONE) as written; FULL is mandatory for gated surfaces,
      new/repurposed stateful artifacts, and mechanism-reuse designs.
- [x] Adopt M1's load-bearing rule: **no `ASSUMED` line pre-checked in a FULL decision block.**
- [ ] **Deferred (not authorized in this ratification):** `trace_consumers.py` as a separate bounded
      WO. M3 works without it (manual enumeration); authorize later if the manual pass proves costly.

Adopted: status line flipped, `work/ledger.jsonl` line `PROTOCOL-WARGAME-18` appended, Claude
adapter `.claude/skills/wargame` added (mirrors the `fable` adapter). A future amendment to this
protocol ships as its own change with its own ledger line; this document is now canonical.
