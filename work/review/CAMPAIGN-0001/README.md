# CAMPAIGN-0001 — Whole-Codebase Cross-Model Review

A comprehensive, multi-lens, cross-model review of the entire codebase to certify a solid
foundation before beta/live. **Claude authors + synthesizes; Codex is the independent review
seat.** It reuses the standard review-packet protocol (`.ai-os/core/15_CROSS_MODEL_REVIEW.md`):
each packet is a `work/review/REV-NNNN/` folder — Claude writes `request.md`, Codex writes
`result.md`, Claude writes `disposition.md`.

- **Frozen base SHA:** `b600101` (all packets review this commit). **Env: Python 3.12.**
- **Shared context:** `work/review/CAMPAIGN-0001/ATLAS.md` — read it first; it is
  structure-only and makes no correctness claims.
- **Run shape:** foundation-first, sequential to start. Wave 1 (the safety-critical spine) is
  authored and run first; Claude synthesizes an interim "is the spine solid?" verdict; then
  Waves 2–3.

## How to run a packet (Codex)
1. Point a fresh Codex session at the repo on branch `review/campaign-0001` (frozen at `b600101`).
2. Give it the packet's `request.md`. It reads the Atlas + its scoped code, re-derives, probes.
3. It writes `result.md` in that same folder (from `.ai-os/templates/review-result.md`) —
   findings table + verdict (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`) + per-target gate — and
   pushes. It must NOT edit `request.md` or push code fixes.
4. Tell Claude "ingest REV-NNNN": Claude adversarially verifies every finding against the frozen
   code, writes `disposition.md`, updates the ledger, and folds it into the campaign synthesis.

## Roster
Lenses are **weighted** (each bites hardest somewhere), not a uniform matrix. `▣` = a holistic
spanning packet owns that concern.

| Wave | Packet | Group(s) | Primary lens (+ named clusters) | Status |
|---|---|---|---|---|
| **W1** | REV-0004 ATTACK-CHAIN | spans G-A…G-I | red-team, **cross-container** (each safety invariant end-to-end across layers) | **authored** |
| W1 | **REV-0005 ENGINE** *(sample)* | G-E | red-team + concurrency/async + observability | **authored** |
| W1 | REV-0006 STORE-SPEC | G-B | SWE + red-team | **authored** |
| W1 | REV-0007 EVENTS | G-D | **data-integrity** + red-team | **authored** |
| W1 | REV-0008 ARCH | all + G-J | architecture (holistic: 5 import contracts, seams, thin-client, coupling) | **authored** |
| **W2** | REV-0009 STORE-IMPL | G-C | SWE + red-team + perf (dual-store parity) | **authored** |
| W2 | REV-0010 KERNEL | G-A | red-team / correctness | **authored** |
| W2 | REV-0011 BROKER | G-G | red-team + config-safety (SDK confinement, paper-only) | **authored** |
| W2 | REV-0012 MARKETDATA | G-H | red-team (staleness / NaN / negative gating) | **authored** |
| W2 | REV-0013 FACADE-API | G-I | red-team + arch (human-gated endpoints, actor model, protocol drift) | **authored** |
| W2 | REV-0014 STRATEGY | G-F | SWE + red-team | **authored** |
| **W3** | REV-0015 UIUX | G-J | UI/UX (cockpit operator experience) | pending |
| W3 | REV-0016 QA | G-K/tests | QA (over-mock, X-002, parity/coverage gaps, determinism) | pending |
| W3 | REV-0017 GOV | G-K/gov+deps | governance-coherence + supply-chain | pending |
| **W4** | REV-0018 META-REVIEW *(optional)* | campaign | Codex reviews the campaign itself | pending |

**Wave-1 sequential order (N=1):** REV-0004 → REV-0005 → REV-0006 → REV-0007 → REV-0008.

## Synthesis + gate (Claude, per wave and at the end)
- Every finding is **verified against the frozen code** before it drives any change
  (CONFIRMED / PARTIAL / REFUTED / NEEDS-HUMAN — the REV-0001/0002 disposition bar).
- Findings are deduped + cross-composed across packets; prioritized P0 / P1 / P2.
- A **completeness critic** flags any in-scope area with neither a finding nor a null-result
  probe log as a coverage hole (re-issued, not passed).
- Output: `work/review/CAMPAIGN-0001/synthesis.md` — a container-group × lens **foundation-health
  scorecard** + a prioritized **remediation roadmap** (each confirmed P0/P1 → a gated work
  order; any remediation touching a human-gated surface re-enters a fresh REV packet).
- A packet's gate clears on `ACCEPT` / `ACCEPT-WITH-CHANGES` + its disposition.
