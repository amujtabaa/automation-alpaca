# WARGAME-ROADMAP — kickoff (beta → live capital)

- **Status:** QUEUED — operator-directed 2026-07-28 ("brainstorm and war game the hardest
  development obstacles... from this current phase until production with live capital, so the
  development could be improved as a matter of process and not rely on a roll of the dice").
- **Seat:** planning seat, fresh session. Protocol: `.ai-os/core/18_WARGAME_PROTOCOL.md`,
  informed by AUDIT-0003 (as amended) + its addendum + the applied external round-2 audit.
- **Runs in parallel with:** Codex round-3 on REV-0045 (the critical path; this war-game is
  read-only planning work and must not touch code or gated surfaces).
- **Governing principle (ratify or amend in round 1):** *de-dicing means no obligation may live
  only in an agent's working memory — every one must exist as an artifact a mediocre run cannot
  skip and a good run cannot silently satisfy. A weak model run must produce a loud refusal,
  never a wrong merge.*

## Seed hazard map (from the 2026-07-28 operator session — attack, extend, price each row)

| # | Hazard | Why hard for AI seats | Seed control to develop |
|---|---|---|---|
| 1 | R7 conversion cross-product (approval × envelope × single-flight × kill-switch × dual-store × replay, atomic) | Largest product-space yet; S-1/S-2 amplification | Build WO-E effect-permit sink + kernel pattern BEFORE R7; reviewer-owned holdout authored before implementation (S-8) |
| 2 | Venue-truth asynchrony at live (fill-after-cancel, event ordering, duplicate deliveries, `client_order_id` uniqueness — flagged unverified in REV-0011, never probed) | Maximal S-8: every oracle encodes imagined broker behavior | **External-assumption register**: one row + probe + verified-against-recorded-reality bit per Alpaca belief; extend tape-recorder pattern to venue event streams; replay real paper-session corpora as fixtures |
| 3 | Calendar/clock reality (DST, half-days, halts, restart across session boundary) | Unvisited calendar cells | Calendar-generator dimension in obligation matrices for session-touching WOs |
| 4 | The shadow→live flip | Readiness-as-judgment invites motivated reasoning | Promotion gates as ADRs NOW: LIVE_SHADOW soak + **divergence ledger** (every mismatch classed + ledgered); promote at N clean sessions, zero class-A; standing automated kill-switch/flatten **fire drill** with recorded latency |
| 5 | Capital-critical invariants (position limits, max daily loss, kill latency) | Logic becomes money | INV registry tier where the full five-part meta-law is mandatory per row (enforcement + reviewer holdout + mutation certificate + negative fixture + currency); flag ships inside the P-14 build |
| 6 | Ops/incident reality (crash mid-submit, partition, outage, rate limits) | Prose runbooks decay (S-4) | **Tested runbooks**: recovery procedures as executable scripts with fixtures |
| 7 | Process rot across the months to live (the S-4 recursion on our own controls) | Every control decays | Control-manifest + closure checker; AUDIT-000N as standing per-phase-gate cadence |

## Tooling dispositions feeding this war-game (from the external audit round)

- **Hypothesis stateful (`RuleBasedStateMachine`)**: already installed; the priority adoption —
  operation-sequence generation against both stores vs a small reference model is the tool for
  the cells that kept escaping (epoch 2+, cross-side interleavings, restart mid-sequence).
- **Stryker**: not adoptable (no Python implementation); its mutant-state taxonomy IS adopted
  into the ADR-015 baseline acceptance model. mutmut stays the engine.
- **OPA/Conftest**: conventions only, per the external audit; bespoke Python checkers.

## Deliverables (each needs operator ratification before it binds)

1. `work/review/WARGAME-ROADMAP/` — hazard register: every row above attacked by fresh-context
   analysts (refute, extend, find the missing eighth row), each with its control priced.
2. The **external-assumption register** drafted (hazard 2) — highest-novelty artifact.
3. Phase-gate ADR drafts: beta→shadow, shadow→small-capital, small→full; evidence-ratchet form.
4. Sequencing proposal reconciling this with the standing queue (P-5, P-13, P-14, P-3 semantic
   scope budget, WO-A/B/C kernel program, WO-E permits) — one ordered build plan to live.

## Fresh-session bootstrap

Branch `codex/signal-r6a-rails-store`; read order: this file → `work/review/
AUDIT-0003-assurance-retrospective.md` (as amended) + `AUDIT-0003-addendum-01.md` →
`work/active/SIGNAL-R6aR-STATE.md` evidence log (top entries) → `.ai-os/core/18` + `17`.
Environment: `python harness/bootstrap.py` on a fresh container. Gate state at handoff:
REV-0045 Codex-owned/BLOCK, R-1/R-2 open, D-2a OFF, R6b blocked.
