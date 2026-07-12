# Cross-Model Build Lane (v1.0)

Adopted 2026-07-12 (Ameen, in-chat approval of `work/collab/PROPOSAL-cross-model-lane.md`),
distilled from the SOL-0001 pilot (GPT Sol via Codex vs the resident Claude seat on the LASE
sell-side policy). Sibling of `15_CROSS_MODEL_REVIEW.md`: that file governs cross-model
REVIEW of finished work; this one governs cross-model BUILD — two models producing rival
implementations of the same component.

## Purpose

Get a second model's best independent design work on the hardest components, without letting
"two authors" degrade into merge chaos, contract drift, or review contamination.

## The eight rules

1. **Frozen-contract seam.** The rival competes behind an EXACT frozen function contract —
   signature, return taxonomy, purity rules (injected clock, no RNG/IO) — never behind "the
   same feature". Everything else (internals, tests, memos) is the competitor's own. The
   resident seat may remediate its side freely as long as the signature never moves.
2. **Sandbox drop-zone.** All rival work lands under `work/collab/<PACKET-ID>/**` — never in
   `app/` or `tests/`. Consolidation into the product is a separate, Fable-gated step owned by
   the resident seat after crosswise review.
3. **Review-before-design sequencing.** The rival seat finishes any in-flight independent
   REVIEW before receiving the build packet — a reviewer must not review code shaped by its
   own design ideas.
4. **Crosswise review.** Each seat adversarially reviews the other's deliverables with the
   same evidence discipline (fresh pasted output; mutation-check the rival's tests — a suite
   that survives its own mechanism's deletion is decorative). No seat's self-assessment is
   ever the only assessment.
5. **Empirical arbiter.** Mechanism-quality disputes are settled by a shared harness and a
   metric set fixed BEFORE either side sees results — never by argument.
6. **Baseline pinning + drift ledger.** The packet pins the SHA the rival codes against; the
   resident seat maintains a drift table (contract-relevant changes landing after the pin)
   that intake walks row by row. Without it, a rival can faithfully reproduce a since-fixed
   bug.
7. **Delivery is a push, not a screenshot.** The packet names the exact branch the rival's
   operator pushes to (`collab/<packet-id>`). Intake starts only at a reachable commit —
   work visible only in the rival's sandbox does not exist.
8. **Intake checklist ships WITH the packet.** The crosswise-review gates (provenance,
   conformance, drift, adversarial, synthesis) are written into the kickoff so the rival
   knows them in advance. Template: `work/collab/SOL-0001/INTAKE-CHECKLIST.md`.

## Human gates (unchanged)

Consolidation into `app/` is ordinary gated work: work order, Fable discipline, independent
review per the CLAUDE.md matrix. This lane changes WHO generates candidate designs, never who
approves them. The safety core binds every seat.

## Artifacts

- Kickoff packet: `work/collab/<PACKET-ID>/KICKOFF.md` (contract freeze, baseline SHA,
  deliverables list, delivery branch, intake checklist).
- Intake + crosswise review: `work/collab/<PACKET-ID>/CROSSWISE-REVIEW.md`.
- Consolidation memo + bake-off spec: outputs of the crosswise review; feed the harness wave.
- Ledger entries at packet open, intake, and disposition.
