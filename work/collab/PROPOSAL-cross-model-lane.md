# PROPOSAL — codify the cross-model collaboration lane into the AI Project OS

Status: **ACCEPTED 2026-07-12** — installed as `.ai-os/core/16_CROSS_MODEL_BUILD.md` (v1.0). He asked on 2026-07-12 whether the SOL-0001 system should be
refined into `.ai-os/` and then deferred the decision "until the work comes back." It is back —
this is the prepared codification, distilled from what the pilot actually exercised. If
approved, this text becomes `.ai-os/core/16_CROSS_MODEL_BUILD.md` (sibling of
15_CROSS_MODEL_REVIEW.md) plus a template; nothing is installed until approved.

## What the pilot validated (keep)

1. **Frozen-contract seam.** A rival implementation competes behind an EXACT frozen function
   contract (signature + return taxonomy + purity rules), never behind "the same feature".
   Everything else — internals, tests, memos — is the competitor's own. The seam survived a
   full remediation wave on our side precisely because the signature never moved.
2. **Sandbox drop-zone.** All rival work lands under `work/collab/<PACKET-ID>/**` — never in
   `app/` or `tests/`. Consolidation into the product is a SEPARATE, Fable-gated step owned by
   the resident seat after crosswise review.
3. **Review-before-design sequencing.** The rival seat finishes any in-flight independent
   REVIEW before receiving the build packet (contamination ordering — the reviewer must not
   review code shaped by its own design ideas).
4. **Crosswise review.** Each seat adversarially reviews the other's deliverables with the
   SAME evidence discipline (fresh pasted output, mutation-checks on the rival's tests). No
   seat's self-assessment is ever the only assessment (CLAUDE.md review core, unchanged).
5. **Empirical arbiter.** Mechanism-quality disputes are settled by a shared harness + metric
   set fixed BEFORE either side sees results (W4 five-metric scorer), not by argument.

## What the pilot exposed (add as rules)

6. **Baseline pinning + drift ledger.** The packet pins the SHA the rival codes against; the
   resident seat maintains a DRIFT TABLE (contract-relevant changes landing after the pin —
   e.g. validate_action's new rails, the predicate fix) that the intake review walks item by
   item. Without it, a rival can faithfully reproduce a since-fixed bug.
7. **Delivery is a push, not a screenshot.** The packet names the exact branch the rival's
   operator pushes to (`collab/<packet-id>`); intake starts only at a reachable commit.
8. **Intake checklist ships WITH the packet** (SOL-0001's was written after the fact; next
   time it goes in the kickoff so the rival knows the gates in advance).

## Human gates (unchanged, restated)

Consolidation into `app/` is ordinary gated work: work order, Fable, independent review per the
CLAUDE.md matrix. The lane changes WHO generates candidate designs, never who approves them.
