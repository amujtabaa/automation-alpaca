# ADR-014 — Neutral vocabulary for derived refusal markers

- **Status:** Accepted (operator ratification, Ameen, 2026-07-28 — "You can perform the
  rename and process changes")
- **Date:** 2026-07-28
- **Deciders:** Operator (human gate); Claude seat (proposal); Codex seat (independent
  recommendation in the REV-0045 round-2 session)

## Context

The signal-seat rails used security-flavored shorthand for plain accounting mechanics:
`poisoned` / `PoisonedProducerMarker` / `poisoned_producers()` for a derived, in-memory
refusal marker; "forged" for a deliberately invalid test fixture; "unauthorized cycle
reset" for a state transition the ratified model does not permit.

The terms were accurate to intent but carried a real, recurring cost:

1. **Independent review stalls.** Two separate cross-model review sessions (the REV-0045
   round-2 launch and its continuation) tripped automated content-safety classification —
   not because of what the code does, but because the vocabulary plus adversarial review
   imperatives ("attempt X that clears Y") pattern-match to offensive tooling. Each stall
   cost reviewer time and risked losing a session mid-review. The reviewer seat itself
   recommended the rename.
2. **Legibility.** "Poisoned" was never about tainted data — the marker records that one
   producer's rail history cannot be folded and is refused write-free pending human
   release. `InvalidProjectionMarker` says that; `poisoned` requires the reader to be told.

The term had previously been kept deliberately (REV-0045 `request.md`, "Vocabulary and
framing") because it was load-bearing API and renaming mid-review would diverge code from
operator-ratified text. Both reasons expired: the review round completed, and this ADR is
the ratified bridge.

## Decision

Rename the derived-refusal vocabulary on the signal-seat surface. Mapping:

| Former | Now |
|---|---|
| `PoisonedProducerMarker` | `InvalidProjectionMarker` |
| `poisoned_producers()` (store method) | `invalid_projection_markers()` |
| `_poisoned_producers` (store attr) | `_invalid_projection_markers` |
| `poisoned_at` (tolerant-fold local) | `invalid_at` |
| `ReadModelProjection.poisoned_producers` | `ReadModelProjection.invalid_projection_markers` |
| prose "poisoned producer" | "invalid-projection producer" |
| prose "poisons / un-poisons" | "invalidates / clears its marker" |
| "forged" / "zero-width forgery" (R6a surface) | "deliberately invalid fixture" / "zero-width false claim" |
| "unauthorized cycle reset" | "unratified cycle reset" |

## Scope boundaries

- **Durable truth is untouched.** No event payload, dedupe key, database column, or any
  other persisted value ever contained the renamed terms (verified by survey before the
  rename); replay identity is unaffected. This is a code/prose rename with zero behavior
  change, gated by the full battery.
- **Historical artifacts are not rewritten.** Review packets (`work/review/**`), work
  orders, the ledger, evidence logs, and archived docs keep their original vocabulary —
  they are records of what was said. This ADR is the bridge: where ratified text
  (WO-0140, REV-0045) says "poisoned," the code now says "invalid-projection," and this
  mapping is the ratified equivalence.
- **Unrelated generic prose stays.** "Poison" as ordinary English in other subsystems
  (dedup-set poisoning in atomicity tests, poisoned market prints in sell-side docs,
  `cost_basis` poisoning in INVARIANTS.md) is not this API and is not renamed. The
  conformance oracle's local `poisoned` variable (a corrupted tape fixture) likewise
  stays.
- Pre-R6a test vocabulary ("forged" in `test_wo0113_*`) is out of this change's scope;
  a follow-up may neutralize it under this ADR without further ratification.

## Consequences

- Future review packets can describe this surface without per-prompt vocabulary
  disclaimers, and the standing "Vocabulary and framing" section of review requests
  shrinks to the historical terms only.
- Greps for the old names find only history. Anyone reading a pre-2026-07-28 packet
  should consult the mapping table above.
