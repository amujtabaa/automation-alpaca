---
type: Review Request
rev_id: REV-0013
campaign_id: CAMPAIGN-0001
packet: FACADE-API
container_group: G-I (facade + API + root)
packet_lens: adversarial red-team (primary) + architecture/boundary (secondary cluster)
status: AWAITING_REVIEW
targets: [G-I-facade-api, ADR-005]
human_gated_surfaces: [order-submission, cancel-replace, kill-switch, manual-flatten, live-shadow-config]
# ^ This container is the HTTP boundary that EXPOSES the human-gated commands. A
#   gap here (a gated op reachable without its guard, a route mutating state
#   outside the facade, an actor dropped before the audit event, an error path
#   that escapes as a raw 500) exposes a gated surface even though the command's
#   internals are owned by another packet. That exposure is your finding.
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [INV-074, INV-070, INV-052, INV-060, INV-061, INV-025, INV-010, INV-033, INV-034, INV-036, INV-040, INV-041, "safety-core #4 (thin client)", "safety-core #5 (UI never calls Alpaca)", "safety-core #7 (all important logic in backend)", "spine INV-1..9"]
adr_in_scope: [ADR-005, ADR-003, ADR-002, ADR-006]
# ADR-005 = API facade boundary + "command endpoints require auth/actor audit" +
#   "routes must not directly mutate stores / call broker / call monitoring";
# ADR-003 = manual-flatten vs emergency-reduce (Halted-deny / scoped override);
# ADR-002 = timeout-quarantine (a quarantined order is NOT manually cancelable);
# ADR-006 = the api→facade import direction (facade owns its return DTOs).
created: 2026-07-10
---

# Review Request REV-0013 — Facade + API + root (the HTTP boundary), adversarial red-team

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes **zero correctness claims** — code beats the atlas, and if they
disagree that is itself a finding). You have the full repo at the frozen SHA.

This is the **HTTP-boundary packet**. `app/api/*` + `app/facade/*` + `app/main.py` are the thin
seam between the disposable UI and the durable engine: the FastAPI routes that expose the
**human-gated** operations (candidate approve/reject, manual cancel, kill switch, pause/resume,
manual flatten, emergency-reduce, session close, dev-inject), and the facade (`store_backed.py` +
the two `Protocol`s + the error→HTTP mapping) they route through per ADR-005. Your verdict answers
one question: **does every gated operation actually reach the store/engine through the guarded,
actor-audited, error-mapped facade seam — or is there a route that mutates state outside it, a
gated command whose operator actor is dropped before it reaches the audit event, a validation the
boundary skips, or an error path that escapes to the client as a raw 500?**

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/facade/store_backed.py` (975 LOC) — the concrete `StoreBackedQueryFacade` /
  `StoreBackedCommandFacade`: the store-error→facade-error translation, the actor threading, the
  re-run risk pre-checks, and the two facade→engine `cancel_open_buys` edges.
- `app/facade/{commands,queries}.py` — the two `Protocol` ports the routes depend on;
  `app/facade/{errors,http_mapping,dtos,protocols}.py` — the domain-error taxonomy, the
  status-code mapping, and the facade's own return DTOs.
- `app/api/*` — `deps.py` (the DI providers + `get_actor`) and every `routes_*.py`; `app/api/schemas.py`.
- `app/main.py` — the app factory / lifespan wiring (router mount, `enable_dev_routes` gate,
  collaborator construction, startup-reconcile ordering).

**Owned by other packets (follow leads freely into them; do not assume their contract holds):**
the *internal* logic of the store planners (`plan_flatten_position`, `plan_close_session`,
`create_order_for_candidate`, `transition_order`) → REV-0006 (STORE-SPEC) / REV-0009 (STORE-IMPL);
the single-writer engine (`cancel_open_buys`, the monitoring loop) → REV-0005 (ENGINE); the
cockpit that consumes these endpoints → REV-0015 (UIUX); the holistic import-contract structure →
REV-0008 (ARCH). You need not audit their internals exhaustively — but if the **boundary** relies
on a behavior those modules don't actually guarantee (e.g. that a store method records the actor
the facade hands it, or that a store error is one of the kinds the facade translates), re-derive
that behavior from their code and report the reliance as **your** finding.

## What you're reviewing
The ADR-005 facade boundary, as documented and as wired:
```
cockpit ──HTTP──▶ app.api.routes_* ──(Depends: get_*_facade)──▶ app.facade.store_backed ──▶ { app.store, app.broker(cancel_open_buys via app.monitoring), app.marketdata }
                        │                                              │
                        └── maps FacadeError → HTTPException            └── translates StoreError → FacadeError (by semantic kind)
                            (app.facade.http_mapping)                       (app.facade.errors / _facade_error_for)
```
ADR-005's decision: "routes may validate HTTP shape, authenticate, construct commands/queries,
call facades, and map domain errors to HTTP responses. Routes must not directly mutate stores,
call broker adapters, call monitoring helpers, or inspect engine internals." Its required tests
include **"command endpoints require auth/actor audit"** and **"quarantine/emergency states
surface through query DTOs."** Your job is to find where the *wired* boundary and that *intended*
boundary part ways.

Run for context (read at `b600101`, do not review a drifting HEAD):
`git diff b600101~1..b600101 -- app/facade/ app/api/ app/main.py`

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
- **The gated command routes (the surfaces).** Enumerate them and confirm each threads an `actor`
  and wraps its facade call: `POST /api/candidates/{id}/approve` (`routes_candidates.py:51`),
  `.../reject` (`:75`); `POST /api/orders/{order_id}/cancel` (`routes_trading.py:236`);
  `POST /api/positions/{symbol}/flatten` (`routes_trading.py:90`), `.../emergency-reduce`
  (`routes_trading.py:115`); `POST /api/controls/kill-switch` (`routes_controls.py:33`),
  `.../pause-buys` (`:45`), `.../resume-buys` (`:56`); `POST /api/session/close`
  (`routes_system.py:48`); `POST /api/watchlist` (`routes_watchlist.py:36`) /
  `DELETE /api/watchlist/{symbol}` (`:60`); `POST /api/dev/candidates` (`routes_dev.py:26`).
- **The actor resolver and its threading.** `get_actor` (`deps.py:77`) reads an optional
  `X-Actor` header, blank/whitespace → `DEFAULT_ACTOR = "operator"` (`deps.py:23`). Trace that
  `actor` from each route → its facade command → the store call → the **recorded audit event**.
  The store's gated mutators that DO take an `actor`: `set_kill_switch` (`store/base.py:1067`),
  `set_buys_paused` (`:1081`), `flatten_position` (`:569`, default `COMMAND_ACTOR_SYSTEM`),
  `authorize_emergency_reduce_override` (`:1133`, required). Compare that list against
  `close_session` (`store/base.py:1152` — signature `(self, session_id=None)`; the facade
  `close_session(*, actor: str)` at `store_backed.py:922` receives `actor` and calls
  `self._store.close_session()` at `:928`) and against `plan_close_session` (`store/core.py:2065`)
  and its `session_closed` close_event payload (`store/core.py:2138-2153`). Also the disclosed
  UC-002 path: the manual-cancel `_cancel_transition` (`store_backed.py:895`) → `transition_order`
  (`store/base.py:815`), whose event payload carries only `{from,to}`.
- **The store-error → facade-error translation (the 404/409/422/502 policy).**
  `_facade_error_for` (`store_backed.py:145`), the `_CONFLICT_STORE_ERRORS` /
  `_INVALID_INPUT_STORE_ERRORS` / `_APPROVE_MAPPED_ERRORS` tuples (`:117`, `:132`, `:136`), the
  `_translate_store_errors` context manager (`:161`), and `_normalize_or_422` (`:183`). Then the
  HTTP side: `facade_error_to_http` (`http_mapping.py:31`) and its **fallback → 500**
  (`http_mapping.py:70-73`). Note the taxonomy in `errors.py` (`FacadeError` `:14`; the four
  domain-outcome errors `:70-96`) and the explicit "an UNMAPPED store error is deliberately NOT
  wrapped — it propagates as a raw 500" comment (`errors.py:67-68`, `store_backed.py:166-167`).
- **The routes that DO NOT wrap their facade call** (no `try/except FacadeError`):
  `GET /api/protection` (`routes_trading.py:142`), `/api/orders` (`:172`), `/api/order-recoveries`
  (`:179`), `/api/operator/orders` (`:200`), `/api/events` (`:265`); `/api/candidates`
  (`routes_candidates.py:29`), `/api/watchlist` (`routes_watchlist.py:29`), `/api/session`
  (`routes_system.py:32`), `/api/marketdata/snapshots` (`routes_marketdata.py:26`), `/api/review`
  (`routes_review.py:28`). Cross-reference each against the facade method it calls: does that
  method have a raising path (a `RuntimeError` for an unwired collaborator at
  `store_backed.py:240/455/701/803/855/947`; a `normalize_symbol`/`_translate_store_errors` path;
  a bare store error) that would reach the client unmapped **today**, or only after a future change?
- **The manual-cancel command's guard ladder.** `cancel` (`store_backed.py:838`): the missing-broker
  `RuntimeError` (`:855`), the terminal-status 409 (`:859`), the **TIMEOUT_QUARANTINE refusal**
  (`:863`, ADR-002), the `CANCEL_PENDING` idempotent no-op (`:870`), the never-submitted local
  cancel (`:873`), and the broker-call-then-`cancel_pending` path with `BrokerError`/`Exception` →
  `BrokerGatewayError` (502) (`:882-893`).
- **The candidate-approve re-run risk pre-checks (drift surface).** `approve_candidate`
  (`store_backed.py:687`) re-runs `limit_price_reason` (`:718`), `order_intent_block_reason`
  (`:735`), and `risk_limit_reason` (`:746`) "for UX", then calls the AUTHORITATIVE
  `create_order_for_candidate` (`:761`) with revert-on-failure (`_APPROVE_MAPPED_ERRORS`, `:764`,
  `revert_candidate_approval` `:772`). Note the two `assert`s at `:744-745`.
- **The two facade→engine runtime edges.** `from app.monitoring import cancel_open_buys`
  (`store_backed.py:79`), called in `create_exit` (`:815`) and `emergency_reduce_override`
  (`:957`) — a best-effort broker call the docstrings claim runs "never under the store lock"
  (INV-052). Confirm both call sites obey that.
- **The typed ports vs the impl.** `ExecutionCommandFacade` (`commands.py:35`) and
  `ExecutionQueryFacade` (`queries.py:18`) type **every** method `-> Any` with `Any` params, and
  their module docstrings still say "**Every other method still raises `NotYetImplementedError`**"
  / "**Every other route still bypasses this facade entirely**" (`commands.py:10-19`,
  `queries.py:4-8`) — stale as of the P6 migration. Cross-check each `store_backed.py` method's
  name + keyword params against its Protocol declaration.
- **The wiring.** `main.py:67` `create_app`, the router mount (`:153-164`), the `enable_dev_routes`
  gate on `routes_dev` (`:162`), and `deps.py` DI providers (`get_query_facade` `:92`,
  `get_command_facade` `:118`, both `Depends(get_store)`), plus the unused
  `UNAUTHENTICATED_ACTOR = "unauthenticated"` constant (`store_backed.py:200`).
- **The oracles** (check code against THESE, not the pinning tests): `docs/INVARIANTS.md` —
  INV-074 (`:437`, routes reach backend only via facade), INV-070 (`:393`), INV-052 (`:351`),
  INV-060/061 (`:365`/`:376`, kill-switch + strict-bool controls), INV-025 (`:132`), INV-010
  (`:72`) / INV-033 (`:192`, no stranded APPROVED), INV-034/036 (`:203`/`:282`, flatten/deferral),
  INV-040/041 (`:300`/`:306`, correlation/audit); `docs/adr/ADR-005-api-facade-boundaries.md`
  (esp. "command endpoints require auth/actor audit" and "routes must not directly mutate stores /
  call broker / call monitoring"); ADR-003 (flatten vs emergency-reduce); ADR-002 (timeout
  quarantine); and CLAUDE.md safety core (#4 thin client, #5 UI never calls Alpaca, #7 all
  important logic in backend).

## Probe checklist (find the gap, or prove it cannot exist — symmetric challenges)
Every probe is symmetric: **exhibit the boundary gap, OR show the boundary holds and paste the
probe you ran.** Clean is a valid result — but a bare "LGTM" with no probe log is a rejected review
for that cluster.

**GATED-OP INTEGRITY**
1. Enumerate every state-mutating route in `app/api/*`. For each: is it reachable **only** through
   `get_command_facade`, or can any route path mutate store/broker/engine state outside the facade
   (a direct `request.app.state.store` reach, a broker call, a `monitoring` helper)? Construct the
   reach, or prove every mutation routes through the facade seam (ADR-005 / INV-074).
2. Is every gated command's HTTP response gated by a real precondition (auth/actor is an audit
   label, not a token — but the *validation* must hold)? Find a gated endpoint that skips a
   validation its old inline route enforced (a control value that isn't `StrictBool`, a ticker not
   normalized, a body field un-validated), or prove each gated route validates its input before any
   side effect. Cross-check `KillSwitchRequest`/`WatchlistCreate`/`MockCandidateCreate`
   (`schemas.py:44/31/59`) against INV-061 (strict bool) and the flatten/emergency `_normalize_or_422`.

**ACTOR / AUDIT**
3. Trace the `actor` for **every** gated command from `get_actor` (`deps.py:77`) through to the
   audit event the command writes. Find a command whose resolved actor is **dropped** before it
   reaches the recorded event (the facade accepts it but the store call omits it, or the store
   method has no parameter to receive it, or the event payload has no actor field), **or** prove
   every gated command threads its actor through to a recorded event. (Contrast the store mutators
   that thread `actor` — `set_kill_switch`/`set_buys_paused`/`flatten_position`/
   `authorize_emergency_reduce_override` — against `close_session`/`plan_close_session` and the
   `session_closed` event payload; and note the disclosed UC-002 `transition_order` path. UC-002 is
   a **known item — confirm/expand, don't re-file**; a *distinct* endpoint with the same class of
   gap is a fresh finding.)

**ERROR-MAPPING / RAW-500**
4. For **every** route, decide whether a domain-error path can reach the client **unmapped as a raw
   500 today** (not just "after a future facade change"). Two sub-probes: (a) an *unwrapped* read
   route (`protection_status`, `list_orders`, `operator_orders`, `list_events`, `list_candidates`,
   `review`, `session`, `snapshots`, …) whose facade method has a live raising path; (b) a *wrapped*
   route whose facade lets a **store** error escape untranslated — e.g. `create_exit` catches only
   `(FlattenBlockedError, InvalidOrderError)` (`store_backed.py:819`) while `flatten_position`'s
   create+approve+dispatch can raise other `StoreError` kinds (`SellIntentTransitionError`,
   `OrderIntentBlockedError`, …) that the route's `except FacadeError` does not catch. Exhibit an
   input that yields a raw 500 where a domain code (409/422) is correct, or prove no such path is
   reachable. (The disclosed "some read routes skip the error→HTTP wrap" is a **known item**; a
   *currently reachable* raw-500 is the distinct finding.)
5. Is the `_facade_error_for` semantic-kind mapping (`store_backed.py:145`) **complete and correct**
   over the store's error taxonomy? Is any store error the migrated routes can provoke absent from
   `_CONFLICT_STORE_ERRORS`/`_INVALID_INPUT_STORE_ERRORS`/`_APPROVE_MAPPED_ERRORS` (so it falls
   through to a 500), or mapped to the **wrong** status vs the un-migrated route it replaced? Diff
   the tuple contents against `app/store/base.py`'s `StoreError` subclasses.

**QUARANTINE / SAFETY SURFACING (ADR-002 / ADR-003)**
6. `cancel` refuses a `TIMEOUT_QUARANTINE` order with a 409 (`store_backed.py:863`, ADR-002). Find a
   status/ordering under which a possibly-live quarantined order is nonetheless cancelled (or
   locally marked terminal) through this endpoint, or prove the ladder (`:859-893`) blocks it on
   every branch. Separately: does `emergency_reduce_override` (`:930`) correctly refuse when NOT
   `Halted` / when an INV-3 quarantine blocks it / when flat (`:953-965`), and does `create_exit`
   deny while `Halted` (ADR-003)? Show a bypass, or prove the guard.
7. ADR-005 required test: "quarantine/emergency states surface through query DTOs." Do
   `list_external_orders`/`list_position_mismatches` (`store_backed.py:548`/`:574`) and
   `operator_orders`/`protection_status` faithfully surface every reconciliation/recovery/stall
   state, or can a needs-review fact be dropped/mis-classified at the read boundary? (Position truth
   is firewalled — Rule 7 — but the *surfacing* is this packet's.)

**DRIFT / DUPLICATION**
8. `approve_candidate` re-runs the store's authoritative risk predicates "for UX" (`:715-757`) then
   calls `create_order_for_candidate` (`:761`). Prove the pre-check and the authoritative check are
   provably identical for all inputs (same predicate, same risk_limits, no torn read across the
   `await`s at `:735/:750/:761`), **or** exhibit an input where the facade pre-check and the store's
   authoritative check disagree (a UX-vs-truth divergence, or a candidate stranded/reverted wrongly —
   INV-010/INV-033). (The re-run itself is a **disclosed known item**; a concrete divergence or a
   revert-on-failure hole is the distinct finding.)
9. Cross-check every `store_backed.py` method name + keyword params against its `Protocol`
   (`commands.py`/`queries.py`): any impl method **not** on the Protocol (an off-contract method a
   route could call), any Protocol method wired to a route but still raising `NotYetImplementedError`,
   or a signature drift the `Any`-typing hides. Flag the stale module docstrings
   (`commands.py:10-19` / `queries.py:4-8` "every other method still raises
   NotYetImplementedError") if they misdescribe the enforced surface. (Protocol-vs-impl drift and
   stale docstrings — ARCH-002 — are **known**; confirm/expand.)

## Independent-oracle hooks (check code against the STATEMENT / INTENT, not the pinning test — X-002)
- Check the code against the **invariant statements** in `docs/INVARIANTS.md` and the **ADR intent**
  (ADR-005 "command endpoints require auth/actor audit"; ADR-003 flatten-vs-emergency; ADR-002
  no-manual-cancel-of-quarantine) — **not** against `tests/test_phase1_facade_equivalence.py`,
  `tests/test_phase7_routes.py`, or the P6 route tests passing. Per X-002 a test can pin the very
  gap it should catch (a facade-equivalence test proves "same as the old route" — which preserves an
  old route's bug just as faithfully as its correctness).
- If the code contradicts the Atlas, an ADR, or a disclosed known-item, that disagreement is itself
  a finding (≥ P1) — including "the ADR requires actor audit on command endpoints; here is a command
  endpoint whose actor never reaches the audit event."
- **Known-items — confirm/expand, do NOT re-file as fresh P0/P1:** UC-002 (actor dropped on the
  cancel `transition_order`, in fix), ARCH-001 (Contract-5 route/facade `get_store` bypass — latent,
  no current route does it, in fix), ARCH-002 (stale facade docstrings), and the disclosed facade
  "re-runs the risk predicate / Protocol-vs-impl drift / some read routes skip the error→HTTP wrap."
  A **distinct** facade/api defect IS wanted (a *different* gated endpoint missing actor/validation;
  a *currently reachable* raw-500; a route reaching a store method directly).

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro plus its pasted output**. For this packet the
  natural harness is the FastAPI app driven in-process — `from fastapi.testclient import TestClient`
  over `app.main.create_app(store=InMemoryStateStore())` (the `httpx`-backed TestClient is
  available), issuing the actual HTTP request and asserting the status/body/recorded event; or a
  direct `await`-call of the facade method with a real/in-memory store; or a `grep`/AST query for a
  route→store reach. Dual-store where a store behavior is load-bearing (memory + sqlite). A finding
  with no repro is marked **"unverified concern"** and **cannot gate**.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran** (the request,
  the response code, the event query). A bare "boundary looks fine / LGTM" with no probe log is a
  **rejected review** for that cluster — show your work on clean routes too.
- Pin the environment (Python 3.12, frozen base `b600101`) in your result; mark any
  environment-dependent result as such.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** (`work/review/REV-0013/`)
and fill it: the findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters |
Proposed fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and an explicit
statement of **whether the G-I foundation gate may clear** (does every gated operation reach the
store/engine through the guarded, actor-audited, error-mapped facade seam, or is there an exposure
that must be closed first). State plainly anything you could not verify. Do **not** edit
`request.md`; do **not** push code fixes.
