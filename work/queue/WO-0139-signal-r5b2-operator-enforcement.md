---
type: Work Order
title: "Signal Seat R5b-2 — operator enforcement, route-authorization ratchet, principal-bound audit, cockpit credential plumbing"
status: DRAFT
work_order_id: WO-0139
wave: signal-seat reconciliation ladder, step R5 (split; R5b-2 = operator enforcement surface)
model_tier: strong (LOCAL Codex — human-gated auth surface; operator-lockout + audit-attribution risk)
predecessors: [WO-0138 (R5b-1 producer ingest — MUST be merged and REV-0042 dispositioned first)]
successors: [WO-0104 refresh (R6 rails), R7a/R7b (conversion), D-2a joint enablement]
review: "REV-0043 required (human-gated: authorization enforcement + event-log actor truth + cockpit credentials)"
wargame: "FULL per .ai-os/core/18 — M1/M2/M3/M4a below; M4b dispatched (rev-2 folds findings)"
round: "Ratified round 2 of 4 — runs ALONE (highest filter risk; R6's prerequisite)"
filter_risk: HIGH
---

# WO-0139 — Signal Seat R5b-2: the operator enforcement surface

R5a made `create_app` refuse to **construct**. R5b-1 added one **authenticated producer input path**.
R5b-2 makes **every sensitive request fail without the operator credential**, binds the **audit actor to
the authenticated principal**, installs the **route-classification ratchet** so no future route can ship
unclassified, and plumbs the cockpit credential **in the same change** so the operator is never locked
out of the kill switch.

**Two crown jewels here:** (1) *who authorized a real order* must not be caller-controlled;
(2) the operator must never lose access to the kill switch / manual flatten (invariant 11).

## Scope boundary

**IN:** operator-key authentication dependency + deny-by-default enforcement in `app/api/deps.py` and
`app/main.py`; authenticated-principal stamping; `get_actor` precedence; **migration of the two
direct-header actor routes**; `GET /api/signals` (operator-only); the mounted-route classification
**ratchet** (scope per D-R5b2-3); auto-docs classification; `cockpit/api_client.py` `X-Operator-Key`
plumbing; `.env.example` credential documentation; completion of the truncated crown-jewel audit test.

**OUT:** R6 rails enforcement and `POST /api/producers/{id}/release` (R6 owns the release action;
`/api/producers` **read** may land here only if trivially derivable, else defer — see D-R5b2-3);
approve/reject routes and conversion (R7); the **complete** required-present matrix set (D-2a joint
proof); schema/migration; event-log *vocabulary* changes; flag enablement.

## GAP ownership

R5a closed GAP-04. R5b-1 closed GAP-06 and the API half of GAP-05. **R5b-2 closes GAP-01 in full and
the GAP-02 *ratchet* — not GAP-02 entire** (D-R5b2-3). GAP-03 is joint-enablement; GAP-08 → R6;
GAP-09 → R7; GAP-07 → ADR-013.

---

## M1 — Assumption ledger / decision block

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`;
no `ASSUMED` line is pre-checked. Lines marked **⟨verify-at-Step-0⟩** depend on R5b-1's actual output
and must be re-verified against the merged tree rather than trusted from drafting time.

- [x] **D-R5b2-1 HARD predecessor gate.** R5b-1 merged to master **and REV-0042 dispositioned**
      `ACCEPT`/`ACCEPT-WITH-CHANGES`. Verify: `git ls-tree master app/api/routes_signals.py` returns a
      blob **and** `work/review/REV-0042/disposition.md` exists. Else **STOP**. Branch
      `codex/signal-r5b2-operator-auth` from the merged master.
      — TRACED(round-2 gate, `SIGNAL-SEAT-R5b-TO-D2a-SEQUENCING-PLAN.md` §RATIFIED sequence).

- [x] **D-R5b2-2 Scope = request-time operator enforcement** (the boundary above). R5b-2 implements no
      rails enforcement, no conversion, no release action.
      — INHERITED(sequencing plan C-1/C-2; WO-0138 §WO-0139 hand-off register).

- [x] **D-R5b2-3 ⚠ GAP-02 is a THREE-RUNG artifact — R5b-2 closes the RATCHET, not GAP-02 entire.**
      Spec `04:100-104` requires required-present routes "asserted to **EXIST** — a required route
      silently unmounted **FAILS**", and its classification table lists `GET /api/signals`,
      **approve/reject**, and `/api/producers*` among required operator-only routes. approve/reject are
      **R7's** and release is **R6's**, and `03-rails.md:121-126` states the matrix is "**authored
      across the WOs, run green at the joint milestone** — never against a half-railed or
      conversion-less app." **Therefore R5b-2 must prove exactly these four properties and must NOT
      record GAP-02 as closed:**
      1. **Ratchet:** any mounted route not present in the classification table ⇒ test **FAILURE**.
      2. **No sensitive route reachable unauthenticated:** every mounted `/api` route except
         `GET /api/health` returns 401 with no credential and 403 with a wrong-role credential.
      3. **Positive discovery lower bound** (D-R5b2-4).
      4. **Required-present set = the routes mounted AT R5b-2**, with an explicit in-test comment
         naming approve/reject (R7) and release (R6) as *deferred* members of the final set.
      "Required-present complete" is recorded as a **D-2a joint-proof obligation**, not an R5b-2
      deliverable. Recording GAP-02 closed here would repeat the REV-0041 inert-pin failure at the
      scale of the matrix protecting all 34 routes.
      — TRACED(spec `04-auth-and-api.md:96-107`, table `:77-93`; `03-rails.md:121-126`).

- [x] **D-R5b2-4 Route discovery MUST be flattener + `openapi` cross-check + positive lower bound.** A
      naive `for r in app.routes: r.path` is **fail-OPEN** on the pinned stack: measured on
      fastapi 0.139.0 / starlette 1.3.1, `app.routes` = **4 `Route` + 8 `_IncludedRouter` with
      `path is None`**, so a naive walk discovers **ZERO** `/api` routes and every classification
      assertion passes vacuously. Required: a **documented recursive flattener** (recursing
      `_IncludedRouter.original_router.routes` and `Mount.routes`), cross-checked against
      `app.openapi()`, plus a **positive lower bound** so a discovery regression turns the test **RED**
      instead of silently green. Planning-seat measurement: flattener finds **34** `/api` operations ==
      `app.openapi()`'s **34**; 38 total including 4 auto-docs.
      **Reference implementation exists** — the archive `tests/test_signal_routes.py` (**1021 lines**;
      staging's is the truncated 374) already recurses `original_router` (`:403-410`) and already
      asserts `checked > 20` (`:437`). Reuse that approach. **Its actual gap, which R5b-2 must not
      inherit:** it asserts only *unauthenticated ⇒ 401* and never the required-present **existence**
      obligation of `04:100-104`.
      — TRACED(planning-seat measurement; `archive:tests/test_signal_routes.py:391-437`).
      *(Corrects WO-0138 §M4b, which wrongly attributed a flat-`app.routes` premise to the archive
      test; the conclusion held, the attribution did not.)*

- [x] **D-R5b2-5 ⚠ The actor-consuming set is 15 routes — enumerated BY GREP, not by `get_actor` call
      sites.** Fixing `get_actor` alone is **insufficient**: 13 routes take
      `actor: str = Depends(get_actor)` (`routes_candidates.py:55,79`, `routes_controls.py:37,48,59`,
      `routes_dev.py:32`, `routes_system.py:51`, `routes_trading.py:103,128,304,360,379`,
      `routes_watchlist.py:40,64`) but **2 bypass it entirely** with
      `actor: str = Header(..., alias="X-Actor", min_length=1)`:
      **`routes_trading.py:220`** (`POST /api/order-recoveries/{id}/fills` — ingests a canonical
      **fill**, invariant 9) and **`:246`** (`.../reconcile` — the human reconciliation
      **attestation**). Those are the two most audit-critical actors in the repo and principal stamping
      would not touch them. **Both MUST migrate** to the principal-preferring dependency, each with its
      own regression test. `get_actor` gains principal precedence: authenticated principal wins;
      `X-Actor` becomes a subordinate label. **Flag-off byte-equivalence:** with no principal stamped,
      behavior falls back to today's `DEFAULT_ACTOR`/`X-Actor` semantics (`deps.py:77-89`) unchanged.
      — TRACED(grep enumeration above; archive `REV-0027/result.md:17-27` F-1; spec `04 §1:45-46`).

- [x] **D-R5b2-6 Producer exemption matches an exact `(method, path)` pair — never a path prefix.**
      Archive `app/main.py` skipped enforcement on `path.startswith("/api/signals")`, which correctly
      exempted the producer POST but wrongly exempted operator-only signal routes and never stamped the
      principal. Only **`POST /api/signals`** is producer-only; **`GET /api/signals` is operator-only**,
      so path-only matching would exempt it. Required negative tests: `GET /api/signals` with a
      producer key ⇒ 403; with no credential ⇒ 401. **⟨verify-at-Step-0⟩** confirm R5b-1's actual
      mounted path/method for the producer route before writing the exemption.
      — TRACED(archive `REV-0027/result.md:17-27`; spec `04 §1a:90-91`).

- [x] **D-R5b2-7 Enforcement covers sensitive READS, and these five were missed by earlier
      enumerations:** `GET /api/events` (**the audit event log — event-log-truth read exposure**),
      `GET /api/protection`, `GET /api/sell-intents`, `GET /api/reconciliation`,
      `GET /api/operator/orders`. Also **`POST /api/session/close` is operator-only** — a mutating
      command (expires candidates, cancels CREATED orders, snapshots positions, closes the session),
      explicitly not a read. `GET /api/health` is the **only** public route.
      — TRACED(measured inventory below; `routes_trading.py:329` for `/api/events`; spec `04 §1a:81`).

- [x] **D-R5b2-8 GAP-01 — cockpit plumbing ships in the SAME change and MERGES headers.**
      `cockpit/api_client.py::_request` (`:28`) is the single outbound choke point (verified: the only
      `requests` usage; `cockpit/app.py` goes only through `api_client`). It must inject
      `X-Operator-Key` from its environment **merged with**, never replacing, per-call `headers=`. Two
      call sites pass `headers={"X-Actor": actor}` (`:165`, `:178`) and `X-Actor` is **required**
      (`min_length=1`) at `routes_trading.py:220,246` — so a replacing implementation is a **loud 422**,
      not a silent drop. The cockpit **must NOT import `app.config`** (import-linter contract 2 forbids
      `cockpit → app`): hardcode the env name `"OPERATOR_API_KEY"`. **Prove no lockout window:** kill
      switch, manual flatten, session controls, and sensitive reads all usable for an operator with the
      configured key (invariant 11).
      — TRACED(`cockpit/api_client.py:28,165,178`; `.importlinter` contract 2; threat model GAP-01
      `:111`, T-22 `:72`).

- [x] **D-R5b2-9 Auto-docs: operator-only is available for free; disabling is optional.**
      Deny-by-default enforcement makes `/openapi.json`, `/docs`, `/redoc`,
      `/docs/oauth2-redirect` return 401 without the operator key, which satisfies spec `04:101-104`
      ("ABSENT under the disabled option, OR present-and-operator-only — **never** required to exist and
      **never** public"). Take either option; classify and test whichever you take.
      — TRACED(spec `04 §1a:101-104`; M4b verification that deny-by-default covers `/openapi.json`).

- [x] **D-R5b2-10 ⚠ Middleware MUST use the same path helper the router uses.** Starlette 1.3.1 routes
      on `get_route_path(scope)`, which **strips `root_path`**; `request.url.path` does **not**. Under
      `tailnet_serve` behind a path prefix, an exact-string exemption computed from `request.url.path`
      stops matching what the router matched. The failure direction is fail-closed (the producer gets
      401) but it is a real correctness break. Use the router's helper, and add a `root_path` regression
      test.
      — TRACED(starlette 1.3.1 routing behavior; ADR-009 A-1 `tailnet_serve`).

- [x] **D-R5b2-11 Complete the truncated crown-jewel audit test (authorized ADDITION).** Staging's
      `tests/test_signal_routes.py` ends **mid-comment (`# The forged X-Ac`) at byte 14628** inside
      `test_operator_command_audit_actor_is_principal_not_forged_x_actor`; its last executable statement
      is `assert events, "no kill-switch audit event was written"`, so it **parses, collects, and passes
      while asserting nothing about the actor**. R5b-2 completes it: the recorded event actor **is the
      authenticated principal** and **is not** the forged `X-Actor` value. Use the archive's 1021-line
      file as reference. This is an addition, never a weakening.
      — TRACED(staged file byte count + EOF text, planning-seat verified).

- [x] **D-R5b2-12 `.env.example` documents the credential surface.** It currently documents **none** of
      `SIGNAL_SEAT_ENABLED`, `OPERATOR_API_KEY`, `SIGNAL_PRODUCER_KEYS`, violating the repo primer's
      "safe, complete configuration template" contract the moment the flag is real. Add all three with
      **safe placeholder values and blank defaults**; never commit real credentials.
      — TRACED(`.env.example` grep: zero hits; repo primer §Environment Variables).

- [x] **D-R5b2-13 Flag stays OFF; flag-off byte-equivalent (GAP-03, D-2a).** With the flag off:
      enforcement is inert, the existing localhost no-auth posture is unchanged, **no existing test may
      need editing**, and `harness/bootstrap.py` stays green. Enforcement flips on **only** with
      `signal_seat_enabled=True`. Note `load_settings()` reads the flag from the **environment**
      (`config.py:535-536`) — there is no source-level guard, so the flag-off test must be explicit.
      — INHERITED(D-2a) + TRACED(`config.py:535-536`).

- [x] **D-R5b2-14 Dual-store parity for the actor migration.** The two migrated routes write **event
      truth** (a canonical fill; the reconciliation attestation). Their actor-provenance regressions run
      on **both** in-memory and SQLite stores per the CLAUDE.md dual-store rule.
      — TRACED(CLAUDE.md Testing; `tests/conftest.py:28-49` `any_store`).

---

## M2 — Lifecycle totality: the authenticated principal

| Edge | Driver | Requirement |
|---|---|---|
| **birth** | operator auth dependency / deny-by-default middleware, on credential validation | stamp the principal on request state — the REV-0027 F-1 miss |
| **read (13 routes)** | `Depends(get_actor)` | principal wins; `X-Actor` subordinate |
| **read (2 routes)** | `routes_trading.py:220`, `:246` — currently a **direct required Header** | **MUST migrate**; today they bypass `get_actor` entirely |
| **terminal (authorized)** | response returned; state discarded with the request scope | no cross-request carryover |
| **terminal (401)** | no/unknown credential | rejected **before** the handler body; no event append |
| **terminal (403)** | valid credential, wrong role | distinct from 401; required negative test |
| **flag-off** | no principal stamped | falls back to `DEFAULT_ACTOR` / `X-Actor` exactly as today (`deps.py:77-89`) |

**Precondition proof (corrected from WO-0138's mis-stated version):** the obligation is **not** "no
route reads an actor where the principal was unstamped" — the principal *is* stamped. It is: **every
route that writes an actor into an event payload must read it through the principal-preferring path**,
and that set is established **by grep** (15 routes, D-R5b2-5), not by `get_actor` call sites.

---

## M3 — Consumer inventory + control-action sweep

| Consumer | Class | Control-action finding |
|---|---|---|
| The 2 direct-header actor routes (`routes_trading.py:220,246`) | **affected — the F2 hole** | (1) *needed guard skipped*: canonical-fill and attestation actors stay caller-controlled unless migrated. |
| The 13 `Depends(get_actor)` routes | **affected** | (3) *wrong order*: principal must win over `X-Actor`, not merge ambiguously. |
| `cockpit/api_client.py:165,178` (`headers={"X-Actor": …}`) | **affected** | (2) *action worsens safety*: replacing headers ⇒ loud 422 on the two required-header routes. Merge. |
| Cockpit kill switch / flatten / session controls | **affected** | (3): enforcement before plumbing = operator lockout (T-22). Same change. |
| All 34 `/api` operations | **affected** | (1): any route omitted from classification ships unauthenticated. Ratchet. |
| `GET /api/events` | **affected — event-log truth** | (1): the audit log itself readable without a credential. |
| `POST /api/session/close` | **affected** | (1): mis-classified as a read ⇒ unauthenticated session close. |
| Auto-docs routes | **affected** | (1): schema enumeration. Operator-only or absent. |
| Future R6/R7 routes | **unknown → resolved by the ratchet** | (4): the ratchet fails on any later unclassified route, forcing R6/R7 to classify. |
| Destructive commands (kill-switch, flatten, emergency-reduce, session/close) | **affected — matrix hazard** | (2): a matrix that *exercises* operator-key × every route would engage the kill switch and close the session, and later cases would 409 by ordering. **"Behave" = auth outcome only** (`401` none, `401` invalid, `403` wrong-role, `status_code not in (401,403)` operator-key) with a **fresh app per parameterized case**. |
| Existing suite + `harness/bootstrap.py:117` | **unaffected (must prove)** | Flag-off byte-equivalence; zero existing-test edits. |
| `.importlinter` contract 2 | **affected** | Cockpit must not import `app.*` for the env name. |

---

## M4a — Prospective hindsight ("it shipped and caused an incident")

1. *"The operator couldn't hit the kill switch."* → D-R5b2-8 (same-change plumbing + usability proof).
2. *"A fill was attributed to a forged actor."* → D-R5b2-5 (the 2-route migration — the hole principal
   stamping alone leaves open).
3. *"The matrix was green and discovered nothing."* → D-R5b2-4 (flattener + lower bound).
4. *"R6 shipped `/api/producers/{id}/release` unauthenticated."* → D-R5b2-3 ratchet.
5. *"Someone closed the session with no credential."* → D-R5b2-7.
6. *"A producer read our positions / the audit log."* → D-R5b2-7 (reads included, `/api/events` named).
7. *"Running the matrix engaged the kill switch."* → M3 destructive-command row.
8. *"Every cockpit command lost its audit label."* → D-R5b2-8 (merge, not replace).
9. *"Behind the tailnet path prefix the producer exemption stopped matching."* → D-R5b2-10.
10. *"We recorded GAP-02 closed and D-2a trusted it."* → D-R5b2-3 (ratchet only; completeness → D-2a).
11. *"Beta broke because flag-off changed."* → D-R5b2-13.
12. *"The operator had no documented way to set the key."* → D-R5b2-12.

---

## Measured mounted-route inventory (planning seat: flattener + `openapi` cross-checked)

**38 operations = 34 `/api` + 4 auto-docs.** Public: `GET /api/health` only. Producer-only:
`POST /api/signals` **⟨verify-at-Step-0⟩**. Everything else operator-only:

`DELETE /api/watchlist/{symbol}` · `GET /api/candidates` · `GET /api/candidates/{candidate_id}` ·
`GET /api/envelopes` · **`GET /api/events`** · `GET /api/marketdata/snapshots` ·
`GET /api/operator/orders` · `GET /api/order-recoveries` · `GET /api/orders` ·
`GET /api/orders/{order_id}` · `GET /api/positions` · `GET /api/positions/{symbol}` ·
`GET /api/protection` · `GET /api/reconciliation` · `GET /api/review` · `GET /api/sell-intents` ·
`GET /api/session` · `GET /api/watchlist` · `POST /api/candidates/{id}/approve` ·
`POST /api/candidates/{id}/reject` · `POST /api/controls/kill-switch` · `POST /api/controls/pause-buys` ·
`POST /api/controls/resume-buys` · `POST /api/dev/candidates` · `POST /api/envelopes/approve` ·
`POST /api/envelopes/{id}/cancel` · `POST /api/order-recoveries/{id}/fills` ·
`POST /api/order-recoveries/{id}/reconcile` · `POST /api/orders/{id}/cancel` ·
`POST /api/positions/{symbol}/emergency-reduce` · `POST /api/positions/{symbol}/flatten` ·
`POST /api/session/close` · `POST /api/watchlist` · plus R5b-1's signal routes.

Deferred members of the final required-present set: **approve/reject (R7)**, **release (R6)**.

---

## Required behavior (Fable v3)

- [ ] **GATE** (`fable_gate`) + predecessor check (D-R5b2-1), else STOP.
- [ ] **⟨Step 0⟩** re-verify every `⟨verify-at-Step-0⟩` line against the merged R5b-1 tree; report any
      divergence from this WO before building.
- [ ] Operator-key auth dependency + deny-by-default enforcement; 401/403 distinction.
- [ ] Principal stamping + `get_actor` precedence + **the 2-route migration** (D-R5b2-5), dual-store.
- [ ] `GET /api/signals` operator-only; exact `(method, path)` producer exemption (D-R5b2-6).
- [ ] The classification **ratchet** test: flattener + `openapi` cross-check + positive lower bound +
      auth-outcome-only + fresh app per case (D-R5b2-3/-4).
- [ ] Auto-docs classified (D-R5b2-9); `root_path` regression (D-R5b2-10).
- [ ] Cockpit `X-Operator-Key` merge + no-lockout usability proof (D-R5b2-8).
- [ ] Complete the crown-jewel audit test (D-R5b2-11).
- [ ] `.env.example` credential documentation (D-R5b2-12).
- [ ] Flag-off non-regression: zero existing-test edits, bootstrap green (D-R5b2-13).
- [ ] FIX blocks with root cause; fresh pasted evidence.

## Gate battery (fresh, pasted)

`ruff check .` · `ruff format --check` on R5b-2-owned files (the 10 inherited baseline files stay
grandfathered) · `mypy app/` · `lint-imports` (contracts 2 and 5 green) · the R5b-2 corpus + full suite ·
`python -m pytest -q tests/r2_conformance_oracle.py` (CI's invocation) ·
`pytest -q tests/test_wo0113_repair_scaling.py` · `python harness/bootstrap.py`.

## Stop conditions

Any accepted-text conflict not already recorded here · any need to weaken an existing assertion · any
rails enforcement, release action, approve/reject, or conversion work (R6/R7) · anything making the flag
independently enable-able · any schema/migration or event-log **vocabulary** change · recording GAP-02
as closed · a P0-equivalent hole in accepted text.

## Filter-safety clause (rung risk: **HIGH** — the highest in the ladder)

This is **authorized defensive engineering on the operator's own local, paper-only application**. No
external target, no network probing, no credential access, no live trading, no persistence objective.

**Report at the defect level** — cause · impact · affected local files · fix · pass/fail evidence.
**Do not** write reusable bypass procedures or payloads in code, comments, commit messages, or the
review request. **Do not** run open-ended adversarial discovery on the enforcement layer; the
independent **REV-0043 Claude seat is the sanctioned adversarial net**.

**Use this vocabulary:** *missing-authorization coverage* (a route reachable without the required
credential) · *unauthorized-role acceptance* (a credential accepted on the wrong route class) ·
*audit-attribution defect* (a recorded actor that is not the authenticated principal) ·
*incorrect type acceptance* · *non-atomic transaction boundary*. **Avoid** "bypass auth", "forge the
actor", "escalate privileges", "impersonate the operator" — same engineering content, far lower
false-positive risk. If a filter interruption occurs, the fixes are likely already applied: resume and
request a **defect-level re-report**, never a re-run.

## Close-out expectations

Human-gated ⇒ set WO-0139 to **REVIEW** and stage `work/review/REV-0043/request.md` (defect-level,
named classes, no exploit narration; **carry the GAP-02-ratchet-vs-complete distinction explicitly** so
the reviewer verifies R5b-2 did not over-claim). Do **not** create `result.md`, touch the ledger, move to
completed, merge, open a PR, or enable the flag. Push `codex/signal-r5b2-operator-auth`.

**Round-2 note:** this rung runs **alone** (ratified). The next session is round 3 — R6 → ⟨named gate⟩
→ R7a — which requires this rung's REV-0043 dispositioned first.
