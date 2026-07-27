# WO-0140 implementation state — R6a-R truth-model remediation

## Seat and authority record

- **Implementer: Claude (planning seat), by explicit operator seat swap (Ameen, 2026-07-27).**
  Ratification and swap recorded in WO-0140 rev-3 frontmatter at `cb00ed7` on the planning branch.
- **Gate-clearing review: Codex-owned REV-0045** referencing REV-0044. The implementer authored
  REV-0044 and therefore cannot clear its own gate; no seat reviews its own work. All in-loop
  refutation passes run by the implementer are defect filters, **not** independent review.
- **Execution-preference override, recorded:** `.claude/rules/repo-primer.md` routes gated-surface
  work to the local strongest model. This is a cloud seat implementing a gated surface at the
  operator's explicit direction ("Both: Ratify and confirmed seat swap. Work until this goal is
  achieved at high quality."). Overridden knowingly, not silently.
- Contract: `work/queue/WO-0140-r6a-truth-model-remediation.md` rev-3 (ratified). Base: `b48235e`.
- Discipline: Fable v3 — GATE, red-first, pasted evidence, FIX blocks with root cause, mutation
  checks on every decisive pin. Stop conditions and the closed test-edit list per rev-3.

## Slice scoreboard

| Slice | Contents | Status |
|---|---|---|
| 0 | Step-0 premise re-verification on the implementation checkout | **VERIFIED** — P6/P7/P9 anchors re-read; full fold call-site map: sqlite `:671,:1548,:1626,:8004,:8118,:8145,:8178`; memory `:298,:5746,:5890,:5922,:5944` |
| 1 | Legacy corpora (from `6955208`) + R-1 RED pins | in progress |
| 2 | Tolerant wrapper + poisoned marker + drift-poisoning + `poisoned_producers` parity | pending |
| 3 | Bounded fold (release-exclusive, state-conditional seed) + O(1) anchor + incremental debit | pending |
| 4 | Three-state release + zero-width/no-epoch rules + never-regress carrier | pending |
| 5 | Constants → models.py; read-structural/write-capped (fold + row validator); cap-pin re-home | pending |
| 6 | R-8..R-12 mechanical; stale-cache pin re-pin (authorized list) | pending |
| 7 | Mutation-check sweep (every decisive pin RED→GREEN) + full gate battery | pending |
| 8 | Spec/ADR/pkl refresh + REV-0045 request staging for Codex | pending |

## Evidence log

- 2026-07-27: seat swap + ratification recorded; branch `codex/signal-r6a-rails-store` checked out
  clean at `b48235e`; Step-0 anchors re-verified (this file's scoreboard row 0).
