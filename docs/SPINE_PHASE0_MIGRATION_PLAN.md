# Spine v2 Phase 0 — Migration Plan / Recommended Phase 1 Scope

Companion to `docs/SPINE_PHASE0_INVENTORY.md` (the dependency map and ADR
conflict evidence this plan is based on). This document does not implement
anything — it recommends scope for the next phase and records open
questions for the planning seat / independent reviewer.

---

## Recommended Phase 1 scope

A pre-authored handoff for this exact next phase already exists —
`prompts/CLAUDE_CODE_PHASE_1_FACADE_SEAM.md` — and this plan endorses its
scope rather than proposing a different one: **facade seam only, zero
execution-behavior migration.**

Concretely, in order:

1. **Complete the facade package.** This Phase 0 pass added
   `app/facade/{__init__,protocols,commands,queries,errors}.py` as inert
   `Protocol` skeletons. Phase 1 adds `app/facade/http_mapping.py` (the
   domain-error -> HTTP-status mapping ADR-005 requires) and FastAPI
   dependency providers for the facade (mirroring `app/api/deps.py`'s
   existing `get_store`/`get_broker_adapter` pattern).
2. **Pick ONE low-risk read-only route and wrap it in `ExecutionQueryFacade`.**
   Candidate: `GET /api/positions` — no side effects, output shape is
   already stable, and it's the query every other facade method will need
   to reuse (position derivation). A concrete facade implementation should
   *call the existing `StateStore.list_positions()` unchanged* — Phase 1 is
   explicitly "wrap, don't migrate."
3. **Pick ONE low-risk command route and wrap it in `ExecutionCommandFacade`.**
   Candidate: `POST /api/controls/pause-buys` (or `resume-buys`) — a single
   boolean flip, no session/kill-switch/order-state interaction, easiest to
   prove behavior-identical. **Do NOT start with `flatten` or
   `kill-switch`** — both are exactly the flows §3.1/§3.4 in the inventory
   flag as ADR-conflicted; wrapping either now risks the wrapper quietly
   encoding today's D-P2 semantics as the new "official" contract before a
   deliberate decision is made to migrate them (Phase 3 scope, not Phase 1).
4. **Add characterization + boundary tests for the migrated route(s).**
   Prove behavior is byte-for-byte unchanged (same status codes, same
   response shape, same store calls happening under the hood) — not just
   "the facade compiles."
5. **Document remaining direct dependencies.** After migrating the two
   routes above, the inventory in `docs/SPINE_PHASE0_INVENTORY.md` §1 will
   have exactly 24 routes still calling `app.store` directly — Phase 1's own
   report should restate the count, not silently let it go unstated.
6. **Run the full suite + both harness scripts** before closing Phase 1, per
   the same discipline this Phase 0 pass followed.
7. **Stop.** Per `prompts/CLAUDE_CODE_PHASE_1_FACADE_SEAM.md`'s explicit
   stop condition: no event-log-as-truth implementation, no order/fill/
   position semantics rewrite, no timeout/overfill-quarantine behavior, no
   manual-flatten policy change, no adapter behavior change — even though
   §3.1–§3.4 of the inventory make those conflicts very visible and
   tempting to "just fix while I'm in there."

## Why not start with `flatten` or `kill-switch`

Both are the two most-visible ADR conflicts (§3.1/§3.4) and therefore the
most tempting routes to "wrap and fix at the same time." Resist this
specifically because:

- Phase 1's own stop condition forbids a manual-flatten policy change or a
  kill-switch/`TradingState` change — wrapping these commands *without*
  migrating their semantics would freeze today's D-P2 behavior as the
  facade's "official" contract, which then has to be un-frozen later
  instead of being decided once, deliberately, in Phase 3.
- A behavior-preserving wrap of an ADR-conflicted flow is easy to write
  incorrectly (silently keep the exact bypass logic) or incompletely
  (silently narrow it) without anyone noticing, because the facade seam
  itself has no tests asserting what *should* change later — that's what
  Phase 3's own characterization + migration tests are for.
- The two low-risk candidates above (`list_positions`, `pause_buys`/
  `resume_buys`) prove the facade seam mechanics (DI wiring, HTTP mapping,
  behavior-equivalence testing) without touching anything ADR-conflicted,
  which is exactly what "prove the seam, not the migration" should look
  like.

## Migration-matrix cross-reference

No row in `docs/MIGRATION_MATRIX.md` changes status as a result of this
Phase 0 pass or the recommended Phase 1 scope above — `API routes` stays
`legacy_truth -> facade-backed` (Phase 1 begins the transition for two
routes only, not the whole matrix row) until Phase 5's boundary enforcement
makes it definitionally complete.

## Open decisions / risks to carry into Phase 1 and beyond

1. **ADR-005's "only the concrete Alpaca adapter imports `alpaca-py`"
   wording vs. the market-data stream's separate lazy import
   (§2 of the inventory).** Not urgent, but should be resolved in an ADR
   amendment or Phase-5 import-linter config before enforcement lands, or
   the linter will flag a known-acceptable pattern as a violation.
2. **The severity ordering of the four ADR conflicts (manual flatten >
   stale-submitting redrive > kill-switch model > overfill handling)** is
   this session's assessment, not an accepted decision — the independent
   review (`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`) should
   confirm or revise it before Phase 3 sequencing is locked in.
3. **No "Execution Engine" module boundary exists yet** (inventory §4) —
   Phase 1's facade wrapping will initially call directly into
   `app.store`/`app.monitoring`, same as the routes do today, just through
   one more indirection layer. Phase 2/3 will need to decide whether the
   Execution Engine is a genuinely new module or a renamed/restructured
   `app.store.core` + `app.monitoring` — not decided here, flagged for
   Phase 2 planning.
4. **`docs/SPINE_PHASE0_INVENTORY.md`'s "Nuance" notes are load-bearing
   for a reviewer.** Each of the three MEDIUM/HIGH ADR conflicts has a
   real, working safety mechanism today (bounded redrive attempts,
   needs_review escalation, single asyncio-lock serialization) — a review
   that reads only the "CONFLICT" headline without the nuance could
   over-rotate into treating this codebase as unsafe today, when the gap is
   specifically "doesn't match the *new* target model," not "has no
   safeguard at all."

## Stop condition

This Phase 0 pass stops here. No Phase 1 facade wiring, no route migration,
no event schema, no `TradingState`/quarantine behavior change was
implemented in this session — confirmed by `docs/SPINE_PHASE0_INVENTORY.md`
§5's file list (additive-only) and §7's risk assessment.
