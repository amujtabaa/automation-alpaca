# AGENTS.md

For Codex and coding agents once implementation begins.

## Project
Alpaca Clean-Sheet CAPI Option 2.5.

## Rules
The non-negotiable rules are canonical in `docs/01_ARCHITECTURE.md`
("Non-Negotiable Rules"). Follow them. In short: paper only, no live trading, no
real credentials, no Alpaca calls from Streamlit, Streamlit stays thin, backend
owns truth, submitted ≠ filled, only fills mutate position, kill switch blocks
order intent, unit tests are IO-free, integration tests are env-gated, and do
not add Webull/IBKR/TradersPost/Dash/React/TradingView unless explicitly
requested.

## Persistence (now in scope)
A local SQLite store **is** part of beta, accessed only through the `StateStore`
interface, with an in-memory implementation for tests. Data persists across
restarts and days. See `docs/02_DATA_AND_PERSISTENCE.md`. (This supersedes any
earlier "no database" guidance.)

## Approval Gate (build as pluggable, even in beta)
When implementing candidate approve/reject (Phase 3), build it behind a gate
interface with one mode in beta — human-in-the-loop. A future automatic mode
(Auto-Sell, then Auto-Buy) attaches to this same interface later. Do not wire
approval directly to UI button handlers in a way that would require
restructuring the candidate state machine to add automation. See
`docs/01_ARCHITECTURE.md`, "Future Architecture."

## Data Model: Candidate ≠ Order
Candidate status stops at `ordered` (pending/approved/rejected/expired/
ordered). Broker-execution states (`submitted`, `partially_filled`, `filled`,
`canceled`, `rejected`) belong to the Order, not the Candidate — do not add
them to the candidate's status field. See `docs/02_DATA_AND_PERSISTENCE.md`.

## Git Workflow
One feature branch per phase, off `master`, with incremental commits per
logical unit rather than one commit at the end. Run the full test suite
before merging. A self-review is not a substitute for an independent one —
significant findings should get a fresh read of the diff before merging to
`master`, not just self-adjudication by whichever agent wrote the code.

## Stack
Python 3.12+, FastAPI, Pydantic v2, SQLite (via `StateStore`), Streamlit,
pytest.

## Definition of Done
- tests pass (unit tests IO-free),
- safety invariants preserved,
- persistence rules honored,
- docs updated,
- no live trading path exists,
- Streamlit remains a thin client.
