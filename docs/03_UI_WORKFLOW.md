# UI Workflow — Alpaca Clean-Sheet CAPI Option 2.5

Streamlit is a thin client (see `01_ARCHITECTURE.md`). Every screen reads fresh
from the backend; every action is a backend API call. No business state lives in
the UI.

## Primary User Workflow

1. Open browser cockpit.
2. Select Alpaca Paper mode.
3. Select session type: pre-market, after-hours, or regular hours.
4. Paste or upload watchlist symbols.
5. Click **Arm Watchlist**.
6. Backend begins monitoring (single background task).
7. UI displays candidates.
8. User reviews the signal explanation.
9. User approves or rejects each paper entry.
10. Backend submits the paper order.
11. Backend tracks order → submitted → fill → position (only fills mutate
    position).
12. Sell-side protection monitors the position.
13. User can flatten a position or hit the kill switch.
14. End-of-session review appears and is saved for later lookup.

## Streamlit Screens

### 1. Session Control
Alpaca Paper mode indicator, session selector, automation-mode selector, kill
switch, pause buys, resume buys.

### 2. Watchlist Input
Paste ticker list (CSV upload later), normalize symbols, show validation errors,
arm/disarm.

### 3. Candidate Monitor
Per candidate: symbol, strategy, reason/explanation, risk decision, suggested
size, current state (pending/approved/…), approve and reject buttons.

### 4. Position Monitor
Per position: symbol, quantity (derived from fills), average price, unrealized
P/L, protection mode, flatten button.

### 5. Daily Review
For the current or a **past session selected by date** (`/api/review?date=`):
candidates generated/approved/rejected, paper orders, fills, P/L, and rejection
reasons. History persists across days.

## Migration to Dash

Dash migration stays easy as long as Streamlit remains thin. Dash later calls
the same backend endpoints unchanged.
