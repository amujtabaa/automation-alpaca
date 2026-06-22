# CLAUDE.md

For Claude Code working in this repository.

## Canonical Rules and Data Model (auto-loaded every session)
@docs/01_ARCHITECTURE.md
@docs/02_DATA_AND_PERSISTENCE.md

These two are imported in full — don't restate or fork them elsewhere; if
anything below conflicts with them, they win. The other planning docs
(`docs/00_START_HERE.md`, `docs/03_UI_WORKFLOW.md`,
`docs/04_IMPLEMENTATION_PLAN.md`, `docs/05_REVIEW_CHECKLIST.md`) are not
auto-loaded, to keep this file's footprint small for tasks that don't need
them — read whichever one is relevant when starting a new phase, touching the
UI, or doing a review.

## Project Identity
Alpaca Clean-Sheet CAPI Option 2.5.

## Project Rule
FastAPI backend is the durable engine; it owns and persists truth. Streamlit is
a disposable thin cockpit.

## Never Do
- add live trading,
- add real credentials,
- put strategy/risk/order logic in Streamlit,
- call Alpaca from Streamlit,
- add Dash/React unless requested.

## Always Preserve
- backend-owned, persisted state (SQLite via the `StateStore` interface;
  in-memory implementation for tests — see `docs/02_DATA_AND_PERSISTENCE.md`),
- position derived from append-only fills,
- safe paper-first execution,
- testable modules with IO-free unit tests,
- the migration path from Streamlit to Dash,
- the Approval Gate as a pluggable interface (human-in-the-loop is beta's only
  mode; do not hardcode approval logic in a way that blocks a future automatic
  mode — see `docs/01_ARCHITECTURE.md`, "Future Architecture"),
- Candidate and Order as separate lifecycles (see `docs/02_DATA_AND_PERSISTENCE.md`,
  "Candidate Lifecycle, Order Lifecycle, and Fill").
