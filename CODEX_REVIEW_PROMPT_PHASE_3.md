# Codex Review Prompt — Phase 3 (Candidate Flow + Approval Gate)
## Alpaca Clean-Sheet CAPI Option 2.5 — adversarial QA / red-team pass

You are acting as a **senior staff engineer and adversarial QA / red-team
reviewer**. Your job is not to praise this code or summarize it — it is to
**break it**: find correctness bugs, safety-invariant violations, state-machine
traps, persistence/atomicity defects, and weak or vacuous tests. Every claim you
make must be **reproduced by running code**, not inferred by reading. Vague
praise and unverified speculation are worthless here.

This codebase is a **paper-first, single-user, localhost** automated-trading
cockpit. There is deliberately **no live trading and no Alpaca network path
yet**. Treat the safety invariants below as load-bearing: a violation that lets
position, orders, or fills drift from their intended truth is a **BLOCKER**, even
if all tests pass.

> ## ⚠️ Ground rules — READ-ONLY review; the deliverable is a markdown report
>
> - **Do NOT modify any code, tests, configs, or docs.** You are reviewing, not
>   fixing. Do not edit files, do not stage/commit, do not open a PR, do not run
>   formatters/linters that rewrite files. The only file you may **create** is
>   your report (below).
> - **You MAY — and should — recommend fixes.** For each finding, describe the
>   concrete fix in prose and, where it helps, a short *illustrative* diff
>   sketch or code snippet **inside the report**. These are recommendations for a
>   separate engineer to apply and verify — never apply them yourself.
> - **Throwaway probe scripts are fine** (write them under a temp/scratch dir or
>   run them inline). They are how you verify findings. They must not touch the
>   repo's tracked files.
> - **Deliverable:** a single markdown file at the repo root named
>   **`CODEX_REVIEW_FINDINGS_PHASE_3.md`**, in the format specified in §8. That
>   file is the entire output of this task; a human reviewer will read it and
>   decide what to apply.

---

## 0. Operating method — run this as a LOOP, not a single read

Work in explicit iterative passes. Do **not** emit findings until you have run
the code. Repeat the loop until a full pass yields no new findings or your
investigation budget is exhausted.

```
LOOP (until a clean pass or budget exhausted):
  1. RECON      — read the change surface + the canonical invariants (§2, §3).
  2. HYPOTHESIZE — pick ONE invariant or boundary and write down how it might break.
  3. PROBE      — write a throwaway script / test that actually exercises it.
                  Use TestClient(app, raise_server_exceptions=False) so error
                  paths return real HTTP codes instead of raising. Drive BOTH
                  stores where the code path is store-level.
  4. VERIFY     — confirm the behavior. If it's benign, discard the hypothesis.
                  If it's a defect, MINIMIZE the repro to the smallest script.
  5. RECORD     — capture severity, exact file:line (opened, not guessed),
                  the minimal repro, observed vs expected, why it matters, and a
                  concrete fix.
  6. SELF-CRITIQUE — try to disprove your own finding. Is it actually a
                  documented deferral (§6)? Is the line number real? Does the
                  repro still fire on a clean `git checkout`?
  7. ITERATE    — move to the next invariant/boundary.
```

Run at least one full pass through **every** lens in §4 before concluding.

### Hard discipline rules (a prior automated reviewer violated these — do not)
- **Verify before reporting.** No finding without a runnable repro. If you can't
  reproduce it, label it explicitly as "UNVERIFIED hypothesis," not a finding.
- **Do not invent line numbers.** Open the file and cite the real `file:line`. A
  previous reviewer cited line numbers (e.g. `:1364`) in files only ~150 lines
  long — that destroys trust. If you cite a location, you have read it.
- **Separate bugs from deferrals.** §6 lists behaviors that are *intentionally*
  deferred to later phases. Re-reporting those as bugs is noise. If you think a
  deferral is wrong, argue it explicitly as a "design concern," not a defect.
- **Prefer depth over breadth of words.** Five reproduced, minimized findings
  beat twenty speculative ones.

---

## 1. How to run it

```bash
# Python 3.12+. From the repo root:
pip install -r requirements.txt
python -m pytest -o addopts="" -q          # expect: 172 passed (the current baseline)

# Drive the API directly for probes (error paths surface as status codes):
python - <<'PY'
from fastapi.testclient import TestClient
from app.main import create_app
from app.store.memory import InMemoryStateStore
app = create_app(InMemoryStateStore())
with TestClient(app, raise_server_exceptions=False) as c:
    ...  # your probe
PY
```

- Unit tests must stay **IO-free** (in-memory store). A separate suite exercises
  `SqliteStateStore` against a temp DB.
- The `any_store` pytest fixture (`conftest.py`) parametrizes a test across
  **both** store implementations — use it (or mirror it) to check parity.
- To exercise a candidate that the dev endpoint can't create (e.g. one with no
  `suggested_quantity`), seed it directly via the store and drive the app over
  ASGI in a single event loop (see `tests/test_candidate_flow_guards.py` for the
  pattern — the in-memory store's lock is loop-bound).

---

## 2. Project context (what you're reviewing)

- **Backend = the durable engine** (FastAPI, single async process). It owns and
  **persists** all truth: watchlist, candidates, orders, fills, positions,
  events, sessions. Access is **only** through the `StateStore` interface
  (`app/store/base.py`), with two implementations: `InMemoryStateStore`
  (`memory.py`, tests) and `SqliteStateStore` (`sqlite.py`, the app).
- **Cockpit = a thin Streamlit client** (`cockpit/`). It may only call the API
  and render; it must hold no business logic or trading state.
- **Canonical docs (read these — they are the spec, not suggestions):**
  - `docs/01_ARCHITECTURE.md` — the 12 Non-Negotiable Rules, boundaries, the API
    contract.
  - `docs/02_DATA_AND_PERSISTENCE.md` — storage model, candidate/order/fill
    lifecycles, atomicity groups, session-close mechanics, duplicate-fill
    protection.
  - `docs/00_START_HERE.md` — decisions log **D-001 … D-010** (the *why*).
  - `docs/04_IMPLEMENTATION_PLAN.md` — phase boundaries (what is in/out of scope
    now).
  - `docs/05_REVIEW_CHECKLIST.md` — the existing review checklist.
  - `docs/IMPLEMENTATION_PROMPT_PHASE_3.md` — the Phase 3 spec being implemented.

### The 12 Non-Negotiable Rules (abbreviated — full text in `01_ARCHITECTURE.md`)
1. No live trading (paper only). 2. No real credentials. 3. No Alpaca calls from
Streamlit. 4. Streamlit is thin, owns no business logic. 5. Backend owns
strategy/risk/order/fill/position state. 6. **submitted ≠ filled.** 7. **Only
fill events mutate position quantity.** 8. Kill switch blocks all new order
intent. 9. Unit tests make no network/live IO. 10. Integration tests are
env-gated. 11. No Webull/IBKR/TradersPost/Dash/React/TradingView unless asked.
12. Order type is session-conditional (limit-only pre/after-hours).

---

## 3. The change surface (Phase 3)

Review commit range **`69e551c..HEAD`** on branch
`claude/confident-babbage-ti5cm8` (`git diff 69e551c..HEAD`). What it added:

- **Approval Gate seam (D-004)** — `app/approval/gate.py` (`ApprovalGate` ABC +
  `GateDecision`), `app/approval/human.py` (`HumanApprovalGate`, beta's only
  mode; `evaluate` always DEFERs). Routes depend on the **interface** via
  `get_approval_gate` (`app/api/deps.py`), constructed once on
  `app.state.approval_gate` (`app/main.py`).
- **Atomic `APPROVED → ORDERED` handoff** — `StateStore.create_order_for_candidate`
  in `base.py` + both stores. One transaction (sqlite) / one lock acquisition
  (memory) covering: order insert + candidate transition to `ORDERED` + the
  `order_created` and `candidate_transition` audit events. Idempotent
  (already-`ORDERED` returns the existing order). Enforces the *approved-only*
  rule that D-010 deferred to this phase.
- **Candidate endpoints** — `app/api/routes_candidates.py`: `GET /api/candidates`
  (scoped to the active session), `GET /api/candidates/{id}`,
  `POST /api/candidates/{id}/approve`, `POST /api/candidates/{id}/reject`. The
  approve handler calls `gate.approve(...)` then the distinct dispatch step
  `store.create_order_for_candidate(...)`. Candidate GET views were moved here
  out of `routes_trading.py`.
- **Dev scaffolding** — `app/api/routes_dev.py`: `POST /api/dev/candidates`
  injects mock candidates; gated by `ENABLE_DEV_ROUTES` (default on).
- **Cockpit** — `cockpit/api_client.py` (+ candidate calls) and
  `cockpit/app.py` (`screen_candidates`: list + per-row approve/reject + a dev
  inject expander).
- **Tests** — `tests/test_approval_gate.py`, `test_order_handoff.py`,
  `test_candidate_flow_api.py`, `test_candidate_flow_sequences.py`,
  `test_candidate_flow_guards.py`, `test_cockpit_candidates.py`.

---

## 4. Review lenses (run every one)

1. **Input-boundary / fuzzing.** Hostile inputs to every new endpoint and to
   `create_order_for_candidate`: blank/whitespace/over-long/unicode symbols,
   absent/zero/negative/huge quantities, negative prices, malformed JSON,
   wrong types, path-param injection, unknown ids. Can any produce a **500**,
   corrupt state, a **double order**, or a **fill/position from a mere
   approval**?
2. **Sequence / lifecycle / state machine.** Every ordering: double-approve,
   approve→reject, reject→approve, approve→close→review, approve a candidate
   that a concurrent close expires, re-dispatch after `ORDERED`, inject/approve
   after close. Is idempotency real? Can a candidate get **stranded** in a state
   with no legal exit? Are audit events correct (D-008: **no** event on a true
   no-op; the handoff writes exactly `order_created` + `candidate_transition`)?
3. **Concurrency / atomicity.** The approve endpoint does `gate.approve()` then
   `create_order_for_candidate()` as **two separate** store operations. Can
   interleaving (two approves, approve vs reject, approve vs close) produce a
   double order, a lost update, or a half-written handoff? Force a failure
   mid-handoff (e.g. monkeypatch an insert to raise) and confirm the SQLite
   transaction **rolls back** order + candidate + both events together. Confirm
   the in-memory store is equally all-or-nothing.
4. **Persistence parity.** Does `create_order_for_candidate` behave **identically**
   across `InMemoryStateStore` and `SqliteStateStore` (idempotency, approved-only,
   no-quantity rejection, terminal rejection, audit payloads)? Reopen a
   `SqliteStateStore` on the same file and confirm ordered candidates + orders
   survive (durability). Any divergence is a finding.
5. **Safety-invariant audit.** Walk Rules 1–12 and D-001…D-010 against the diff.
   Especially: Rule 6/7 (approval creates an order but **never** a fill or
   position — prove it), Rule 7 (nothing but a fill changes quantity), D-006
   (candidate ≠ order; the atomicity groups), D-008 (no-op audit), D-009 (one
   session per date; no second session after close), D-010 (store-boundary
   validation still intact).
6. **Thin-client boundary (Rule 4).** Does `cockpit/` contain any transition
   logic, position math, or business state, or only API calls + display? Does it
   call Alpaca or build trading decisions? (It must not.)
7. **API-contract conformance.** Do the endpoints/paths/verbs match
   `01_ARCHITECTURE.md`'s contract? Status codes sane (404 unknown, 409 illegal
   transition, 422 unprocessable, 201 create)? Any path that escapes error
   mapping to a 500?
8. **Test-quality audit.** Are the new tests **substantive or vacuous**? Look
   for: over-mocking that asserts nothing real, tests that would pass even if
   the feature were broken, the cockpit `AppTest` (does it prove the button
   actually calls the API?), the gate-pluggability test (does it really prove
   the route depends on the interface?), and **coverage gaps** — behaviors with
   no test. Propose the specific missing tests.

---

## 5. Concrete invariants to attack (a starting checklist — go beyond it)

- Approving a candidate **must not** create a fill or a position
  (`GET /api/positions` stays empty; `submitted ≠ filled`).
- Approve is **idempotent**: second approve → 200, **exactly one** order, **no**
  duplicate audit rows. Reject is idempotent likewise.
- A `rejected`/`expired` candidate **cannot** be approved (→409); an
  `ordered`/`approved`/`expired` candidate cannot be rejected (→409).
- `create_order_for_candidate` is atomic and idempotent; a non-`APPROVED`
  candidate is refused; a candidate with no positive `suggested_quantity` is
  refused **without** mutating state.
- Session close expires `pending`/`approved` candidates but leaves `ordered`
  ones; snapshots are point-in-time; `GET /api/review?date=` returns the closed
  session's snapshot, not today's live fold (D-007).
- `GET /api/candidates` is scoped to the **active** session (not all-time).
- The Approval Gate is genuinely pluggable: a second `ApprovalGate`
  implementation could replace `HumanApprovalGate` with **no** edits to routes
  or the candidate state machine. (Verify via `dependency_overrides`.)
- The order created by the handoff is long-only `BUY` `LIMIT`, sized from the
  candidate; `replaces_order_id` stays unused (beta).
- `ENABLE_DEV_ROUTES=false` actually unmounts `POST /api/dev/candidates` (→404).
- Duplicate-fill protection, the position-folding formula, and oversell
  rejection (pre-Phase-3) are still intact after the diff.

---

## 6. Accepted deferrals — do NOT report these as bugs

These are **intentional**, documented in the canonical docs. If you think one is
wrong, raise it as a *design concern* with reasoning — do not file it as a defect.

- **Kill-switch / pause-buys do not block order-record creation on approve.**
  Enforcement on order intent is assigned to **Phase 6 (CAPI)** by
  `docs/04_IMPLEMENTATION_PLAN.md`. Approve creating an order *record* is the
  first order-intent path, but gating it is out of Phase 3 scope.
- **No Alpaca submission / no network.** Orders reach status `created` only;
  paper submission + polling is **Phase 4**. `submitted`/`filled` transitions
  exist on the model but nothing drives them yet.
- **No real strategy / candidate generation.** Mock injection via the dev
  endpoint is scaffolding; the real Strategy Engine is **Phase 5**.
- **Realized P/L, tax lots, FIFO/LIFO** — explicitly out of scope (beta shows
  unrealized only).
- **Automatic session open/close on a window** — deferred until a monitoring
  loop exists (Phase 4/5); beta close is manual only.
- The two pytest **warnings** are upstream FastAPI/Starlette deprecations
  (testclient + the `HTTP_422` constant rename), not code defects.

---

## 7. Findings already known (confirm the fixes hold — then find NEW ones)

A prior internal review already found and **fixed** the following. Re-verify
each fix is real and complete; then spend your effort on **new** territory. Do
not simply re-describe these.

- **M1 (fixed):** the approve endpoint could strand a candidate at `approved`
  (dispatch failing on a quantity-less candidate, then neither orderable nor
  rejectable). Fix: the approve route pre-checks dispatchability →422, candidate
  stays `pending`/rejectable. *Confirm the strand is truly gone for every path,
  including races and the sqlite store.*
- **M2 (deferral):** kill-switch not enforced on approve — see §6.
- **M3 (fixed):** dev routes are now gated by `ENABLE_DEV_ROUTES`.
- **M4 (fixed):** dev injection into a closed session is refused (→409). *Is the
  approve path equally guarded if a candidate somehow exists in a closed
  session?*
- **N1 (fixed):** removed a brittle `# type: ignore` in the approve handler's
  error mapping. *Does any store error still escape to a 500 unintentionally?*
- **N2 (by design):** unexpected store errors fall through to 500.

**Your value is the issues these did not catch.** Push on: concurrency/interleaving,
sqlite-vs-memory divergence under failure, audit-log correctness under repeated
calls, the dispatchability pre-check vs. the store's own checks (double source of
truth?), anything in the cockpit thin-client boundary, and test vacuity.

---

## 8. Output format

Write your entire output to a **new markdown file at the repo root named
`CODEX_REVIEW_FINDINGS_PHASE_3.md`** (create only this file; change nothing
else). Structure it as follows.

Start with a short **summary table** (severity counts + one-line verdict), then
the detailed findings.

For **each finding**:
- **ID + Severity** — e.g. `F1 — MAJOR` (BLOCKER / MAJOR / MINOR / NIT; rubric
  below).
- **One-line summary.**
- **Location** — real `file:line` (opened, not guessed).
- **Reproduction** — the minimal script/test and its observed output (paste the
  actual output).
- **Observed vs expected**, and **why it matters** (cite the specific
  rule/decision/contract).
- **Recommended fix** — concrete prose, plus an *illustrative* diff sketch or
  snippet if it clarifies. Recommendation only — do **not** apply it.
- **Confidence** — note if anything is an UNVERIFIED hypothesis vs. a reproduced
  defect.

Severity rubric:
- **BLOCKER** — violates a safety invariant (position/order/fill truth), data
  corruption, double order, money-relevant logic error, or a 500 on a normal
  path. Not mergeable.
- **MAJOR** — a real bug or a state trap reachable through some path, even if not
  the happy path.
- **MINOR** — robustness/consistency gap, low blast radius.
- **NIT** — style, naming, doc drift, brittle-but-correct code.

End with:
- A **test-quality verdict** (which tests are weak/vacuous; the specific missing
  tests you'd add).
- An **overall verdict**: is `69e551c..HEAD` mergeable to `master` as-is, or what
  are the must-fix items?
- If you found nothing at a given severity, **say so explicitly** — a clean bill
  at a severity is a useful signal, but only if you actually probed for it.
