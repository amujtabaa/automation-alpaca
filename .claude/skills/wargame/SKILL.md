---
name: wargame
description: Design-time war-game protocol (Claude adapter for .ai-os/core/18). Use as the PLANNING SEAT before ratifying a decision block or drafting a kickoff for any gated or novel-surface design — a human-gated surface (order/cancel/kill/flatten, schema/migration, event-log truth, ADR text, test/doc deletion), a new or repurposed stateful artifact (record/event/status/flag/durable field), or a REUSE of an existing mechanism for a new purpose. Also activates on "wargame" / "war-game". Runs BEFORE ratification, upstream of Fable's build gate (06), internal adversarial review (17), and cross-model review (15). Prevents ratifying untraced claims (Class 1) and unenumerated consumers (Class 2).
---

# War-Game — Claude Adapter (v1.0)

**Canonical protocol:** `.ai-os/core/18_WARGAME_PROTOCOL.md` (adopted 2026-07-22). This skill maps it
onto Claude Code planning-seat work; on any divergence the canonical file wins. Do not fork the
protocol text here.

**Activate:** any gated/novel-surface decision block or kickoff draft (see the scope gate), or
"wargame" / "war-game". **This is a planning-seat obligation, not an implementer skill** — it attacks
a *design before it is ratified*, when no code exists yet. **Deactivate:** "wargame off".

## Scope gate — decide FIRST (proportionality is mandatory)

- **FULL (M1–M4)** — the design meets ANY of: (a) touches a human-gated surface; (b) creates or
  repurposes a stateful artifact; (c) reuses an existing mechanism for a new purpose (highest risk —
  the mechanism's guards were written for the old purpose). **If unsure, treat as FULL.**
- **LIGHT (M1 only)** — every other decision block: label assumptions, nothing more.
- **NONE** — trivial mechanical or doc-only work with no decision block.

Do not run FULL machinery on LIGHT work — over-ritualizing trivial work is the exact failure this
protocol's "does NOT import" section rejects.

## The checklist

**M1 — Assumption ledger (LIGHT + FULL).** Label every decision-block line and load-bearing claim:
`TRACED(file:line)` (verified against code/accepted text now) · `INHERITED(source)` (from a named
prior ratified decision) · `ASSUMED` (believed, not verified). **Load-bearing rule: no `ASSUMED`
line may be pre-checked in a FULL decision block.** Resolve each `ASSUMED` by tracing it (→ `TRACED`)
or converting it to an explicit **named** mid-session GATE — never leave it to the generic gate.
Trace with the Key Assumptions questions, especially **"could this have been true in the past but
not now?"** (a mechanism hardened since — the D-ML-5 failure).

**M2 — Lifecycle totality trace (FULL).** For any stateful artifact created/repurposed: birth →
every transition → every terminal, and for EACH edge name the writer that drives it, each with a
code anchor. A lifecycle with any un-anchored edge is not ratifiable. Design-by-Contract on a state
machine: prove the design's inputs meet each transition's preconditions.

**M3 — Consumer inventory + control-action sweep (FULL).** Enumerate EVERY reader of each
row/event/record/field the design writes; classify unaffected / affected / unknown. Every `unknown`
must resolve to a code anchor before ratification. For each `affected` reader run the four
control-action questions: (1) needed action/guard now skipped? (2) an action taken that worsens
safety? (3) wrong timing/order? (4) stopped too soon / applied too long — e.g. an unreleasable
record blocking a rail forever (the REV-0040 F1 failure). Enumeration may use `trace_consumers.py`
if it exists; classification is always judgment.

**M4 — Pre-ratification refutation (FULL), two ordered steps:**
- **M4a — Prospective-hindsight brief (inline, planning seat, before spending an agent).** Frame the
  design as *already failed*, past tense: "assume this shipped and caused an incident — from the
  code, explain how it happened." Enumerate causes; each becomes an M1 assumption, M2 edge, or M3
  reader. Seeds and sharpens M4b.
- **M4b — Fresh-context refutation agent.** Spawn an adversarial subagent briefed to REFUTE the
  decision block from code (not build, not improve — disprove), carrying M1–M3 + the M4a narrative.

**Ratifiable only when** every M4a cause and M4b finding resolves to a `TRACED` fix or a named gate —
none left open.

## Output and integration

- M1 labels live **in the decision block itself**, so paste-ratification ratifies labeled claims.
- M2/M3 outputs live in the WO context packet (the implementer and the eventual REV packet inherit
  them).
- All of it populates `fable_gate.assumptions` / `fable_gate.blast_radius` (`06`) honestly at
  planning time rather than backfilled at build time.
- This is the **first** net, never the only one: a design that clears a FULL war-game still gets its
  mid-session GATEs, `17` internal adversarial review, and `15` cross-model review.

## Does NOT import (calibration)

Full STPA hazard logs · FTA probability math · premortem GROUP facilitation (M4a keeps the
prospective-hindsight core; the group ritual is dropped) · a "war-game engine" tool. See the
canonical §"What this deliberately does NOT import."

## Human commands honored

`wargame scope` (state FULL/LIGHT/NONE + why) · `wargame m1..m4` (run one mechanism) · `wargame
refute` (dispatch M4b) · `wargame status` · `wargame off`.
