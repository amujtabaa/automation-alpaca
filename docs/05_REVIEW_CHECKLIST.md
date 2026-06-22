# Review Checklist — Alpaca Clean-Sheet CAPI Option 2.5

Use when reviewing Codex or Claude Code output.

## Safety
- [ ] No live trading path.
- [ ] No real credentials; paper keys only, env-gated.
- [ ] No Alpaca calls from Streamlit.
- [ ] UI is a thin client; no business state in `st.session_state`.
- [ ] Backend owns and persists state.
- [ ] Order submission does not mutate position.
- [ ] Only fill events mutate position; position is derived from append-only fills.
- [ ] Kill switch blocks new order intent.
- [ ] Candidate approval/reject is idempotent.
- [ ] Rejected/expired candidate cannot be approved without an explicit transition.
- [ ] Approve/reject is implemented behind a pluggable Approval Gate interface,
      not hardcoded to UI-triggered human review only.
- [ ] Order types respect session policy: limit-only pre-market/after-hours;
      other broker order types permitted only during regular hours.
- [ ] Candidate status stays limited to proposal/review states (pending,
      approved, rejected, expired, ordered); broker-execution states
      (submitted, partially_filled, filled, canceled, rejected) live on the
      order, not the candidate.
- [ ] Fill table has a duplicate-protection key (`source_fill_id`, unique when
      present); duplicate fills are detected and logged via an audit event,
      not silently re-appended or silently dropped.
- [ ] Multi-row mutating operations are atomic: a SQL transaction in
      `SqliteStateStore`, the same lock in `InMemoryStateStore`.
- [ ] Derived position follows the average-cost folding formula in `02`; a
      sell that would take quantity negative is rejected as a data-integrity
      error, not treated as a short position.

## Persistence
- [ ] State accessed only through the `StateStore` interface.
- [ ] `InMemoryStateStore` and `SqliteStateStore` both implement it.
- [ ] Unit tests use the in-memory store and make no IO/network calls.
- [ ] Data survives a backend restart.
- [ ] History accumulates across days; past sessions queryable by date.
- [ ] "Outdated" is an explicit state transition (expiry/session close), never
      silent loss.
- [ ] "Deleted" is an explicit command; nothing deleted on restart/refresh.
- [ ] Fills table is append-only.

## Architecture
- [ ] FastAPI backend exists; single async process with lock-guarded state.
- [ ] Streamlit cockpit exists and is thin.
- [ ] Pydantic v2 models exist.
- [ ] Endpoints match the contract in `01_ARCHITECTURE.md`.
- [ ] Tests cover core state transitions.
- [ ] No Dash/React added.
- [ ] No microservices added.
- [ ] No second strategy added before the first works.

## UX
- [ ] User can input/arm/disarm a watchlist in the browser.
- [ ] User can approve/reject candidates.
- [ ] User can view positions and trigger flatten / kill switch.
- [ ] User can review past sessions by date.
- [ ] No command-line operation needed during normal use.

## Documentation
- [ ] README updated.
- [ ] AGENTS.md and CLAUDE.md present and consistent with `01_ARCHITECTURE.md`.
- [ ] Decisions log (`00_START_HERE.md`) updated when architecture changes.
