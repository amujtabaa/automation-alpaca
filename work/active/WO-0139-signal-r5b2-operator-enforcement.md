---
type: Work Order
title: "Signal Seat R5b-2 — operator enforcement, route-authorization matrix, principal-bound audit, cockpit credential plumbing"
status: ACTIVE
work_order_id: WO-0139
wave: signal-seat reconciliation ladder, step R5 (split; R5b-2 = operator enforcement surface)
model_tier: strong (LOCAL Codex — human-gated auth surface; operator-lockout + audit-attribution risk)
predecessors: [WO-0138 (R5b-1 producer ingest — MUST be merged and REV-0042 dispositioned first)]
successors: [WO-0104 refresh (R6 rails), R7a/R7b (conversion), D-2a joint enablement]
review: "REV-0043 required (human-gated: authorization enforcement + event-log actor truth + cockpit credentials)"
wargame: "FULL per .ai-os/core/18 — M1/M2/M3/M4a/M4b COMPLETE (rev-2 applied 15 M4b findings incl. 4 P0)"
round: "Round 2 of 4 — runs ALONE (highest filter risk; R6's prerequisite)"
filter_risk: HIGH
---

# WO-0139 — Signal Seat R5b-2: the operator enforcement surface

> **rev-2 (2026-07-25).** An M4b refutation pass produced **15 findings, 4 of them P0**, and the
> planning seat verified every P0 against code before applying. rev-1's route-matrix design was
> **circular and would have shipped green while proving nothing about route existence** — the same
> inert-pin class REV-0041 caught, at the scale of the matrix protecting every route. See §M4b.

R5a made `create_app` refuse to **construct**. R5b-1 added one **authenticated producer input path**.
R5b-2 makes **every sensitive request fail without the operator credential**, binds the **audit actor
to the authenticated principal**, installs the **route-authorization matrix** so no future route ships
unclassified or silently unmounted, and plumbs the cockpit credential **in the same change** so the
operator is never locked out of the kill switch.

**Two crown jewels:** (1) *who authorized a real order* must not be caller-controlled;
(2) the operator must never lose access to the kill switch / manual flatten (invariant 11).

## Scope boundary

**IN:** operator-key authentication + **http-middleware** deny-by-default enforcement
(`app/api/deps.py`, `app/main.py`); authenticated-principal stamping; `get_actor` precedence;
**migration of the two direct-header actor routes**; `GET /api/signals`; the route-authorization
matrix in **its own new test module**; auto-docs classification; `cockpit/api_client.py`
`X-Operator-Key` plumbing; `.env.example` credential documentation; completion of the truncated
crown-jewel audit test.

**OUT:** rails enforcement and `POST /api/producers/{id}/release` (R6); approve/reject and conversion
(R7); **`/api/producers` read — DEFERRED, not implementer judgment** (D-R5b2-15); the spec-04
required-present **completeness** obligation for R6/R7 routes (D-2a joint proof); schema/migration;
event-log *vocabulary* changes; flag enablement.

## GAP ownership

R5a closed GAP-04; R5b-1 closed GAP-06 and the API half of GAP-05. **R5b-2 closes GAP-01 and
GAP-02 in full** (D-R5b2-3). The **cockpit half of GAP-05** is assigned to **R7** with the signal
panel (spec `04 §3:168-174`) — not left unowned. GAP-03 joint-enablement; GAP-08 → R6; GAP-09 → R7.

---

## M1 — Assumption ledger / decision block (rev-2)

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`;
no `ASSUMED` line is pre-checked. **⟨Step-0⟩** marks a claim that must be re-verified against the
merged R5b-1 tree before building — R5b-1 was in flight when this was drafted.

- [x] **D-R5b2-1 HARD predecessor gate.** R5b-1 merged to master **and REV-0042 dispositioned**.
      Verify: `git ls-tree master app/api/routes_signals.py` returns a blob **and**
      `work/review/REV-0042/disposition.md` exists. Else **STOP**. Branch
      `codex/signal-r5b2-operator-auth` from the merged master.
      — TRACED(ratified round-2 gate; `disposition.md` is the REV-0039/40/41 convention).

- [x] **D-R5b2-2 Scope = request-time operator enforcement** (boundary above). No rails enforcement,
      no release action, no conversion. — INHERITED(sequencing plan C-1/C-2).

- [x] **D-R5b2-3 The route-authorization matrix — TWO independent assertions over a LITERAL required
      set.** rev-1 derived the required set from discovery ("the routes mounted at R5b-2"), which is
      **circular: a set derived from discovery can never detect absence.** Spec `04:98-100` forbids
      exactly that — required routes are "asserted to **EXIST** … a required route silently unmounted
      **FAILS** (**not merely 'classify whatever is mounted'**)". Compounding it: deny-by-default
      http-middleware returns **401 for unmatched paths**, so a negative sweep alone passes for path
      templates that do not exist. Therefore the matrix asserts **both** directions:
      1. **EXISTENCE:** `REQUIRED ⊆ discovered`, where `REQUIRED` is a **literal hardcoded list of
         `(method, path)` pairs** in the test module (never computed from the app). A silently
         unmounted required route FAILS.
      2. **RATCHET:** `discovered ⊆ CLASSIFIED`. Any mounted route absent from the classification
         table FAILS, so R6/R7 cannot ship an unclassified route.
      Plus: every classified sensitive route returns **401** with no credential and **403** with a
      wrong-role credential; `GET /api/health` is the only public route.
      **This closes GAP-02 in full** — its three clauses (`THREAT_MODEL_SIGNAL_SEAT.md:112`) are all
      scoped to *mounted* routes and all satisfiable here. What defers to the **D-2a joint proof** is
      the distinct **spec-04 required-present completeness** obligation for **R6's release** and
      **R7's approve/reject** routes (deferred by `03-rails.md:121-126`: "authored across the WOs, run
      green at the joint milestone"). Add each to `REQUIRED` as its rung lands.
      — TRACED(spec `04:96-107`; `03-rails.md:121-126`; threat model `:112`; M4b F-1/F-7).

- [x] **D-R5b2-4 Route discovery: flattener + `openapi` cross-check + a DERIVED bound.** A naive
      `for r in app.routes: r.path` is **fail-OPEN**: measured on fastapi 0.139.0 / starlette 1.3.1,
      `app.routes` = **4 `Route` + 8 `_IncludedRouter` with `path is None`** → **zero** `/api` routes
      discovered and every assertion passes vacuously. Required: a **documented recursive flattener**
      (recursing `_IncludedRouter.original_router.routes` and `Mount.routes`), cross-checked against
      `app.openapi()`.
      **The bound must be DERIVED, never hardcoded as a magic number:** the count is
      configuration-dependent (34 `/api` with dev routes, **33** with `enable_dev_routes=False`, and
      `config.py:530` defaults it to `not has_creds`) and grows as rungs land. Derive it from the same
      `Settings` the test builds — `tests/signal_seat_helpers.py::flag_on_settings` pins
      `enable_dev_routes=True` — and condition the dev-route row on `settings.enable_dev_routes`.
      **Note the auto-docs routes are `include_in_schema=False`, so they are invisible to the
      `openapi()` cross-check** and must be asserted separately (D-R5b2-9).
      — TRACED(planning-seat measurement; archive `tests/test_signal_routes.py:391-437` already does
      the flattener + a bound; M4b F-3a/F-6.)

- [x] **D-R5b2-5 The actor-consuming set is 16 routes — enumerated BY GREP, not by `get_actor` call
      sites.** Fixing `get_actor` alone is **insufficient**. **14** routes take
      `actor: str = Depends(get_actor)` (`routes_system.py:51`; `routes_watchlist.py:40,64`;
      `routes_candidates.py:55,79`; `routes_trading.py:103,128,304,360,379`; `routes_dev.py:32`;
      `routes_controls.py:37,48,59`) and **2 bypass it entirely** with
      `actor: str = Header(..., alias="X-Actor", min_length=1)`:
      **`routes_trading.py:220`** (`POST /api/order-recoveries/{recovery_id}/fills` — ingests a
      canonical **fill**, invariant 9) and **`:246`** (`.../reconcile` — the human reconciliation
      **attestation**). Corroborated by exactly **16** `command_facade.*` call sites in `app/api/`.
      **Both direct-header routes MUST migrate** to the principal-preferring path, each with its own
      regression. Confirmed clean: no actor arrives via a body field (`app/api/schemas.py` has none),
      no facade default (`app/facade/commands.py` requires `actor` on all 16 methods), no
      websocket/`Mount` path; `COMMAND_ACTOR_SYSTEM` (`app/store/base.py:409`) is engine-loop only.
      — TRACED(grep, planning-seat re-verified: 14 + 2 = 16; archive `REV-0027/result.md:17-27` F-1).

- [x] **D-R5b2-6 Producer exemption matches an exact `(method, path)` pair — never a prefix — and so
      does the public-health exemption.** The archive skipped enforcement on
      `path.startswith("/api/signals")`, wrongly exempting operator-only signal routes and never
      stamping the principal. Only **`POST /api/signals`** is producer-only; **`GET /api/signals` is
      operator-only**, so path-only matching would exempt it. The archive's public exemption is
      likewise `path in _PUBLIC_PATHS` (`main.py:78,267`) — tighten it to exact `(method, path)` so
      e.g. `POST /api/health` is not silently public. Required negatives: `GET /api/signals` with a
      producer key ⇒ 403, with none ⇒ 401. **⟨Step-0⟩** confirm R5b-1's actual mounted method/path.
      — TRACED(archive `REV-0027/result.md:17-27`; spec `04 §1a:90-91`; M4b F-15).

- [x] **D-R5b2-7 Enforcement covers sensitive READS; these five were missed by earlier enumerations:**
      **`GET /api/events`** (`routes_trading.py:329` — **the audit event log**, event-log-truth read
      exposure), `GET /api/protection`, `GET /api/sell-intents`, `GET /api/reconciliation`,
      `GET /api/operator/orders`. **`POST /api/session/close` is operator-only** — a mutating command,
      not a read. `GET /api/health` is the only public route.
      — TRACED(measured inventory; spec `04 §1a:81`).

- [x] **D-R5b2-8 GAP-01 — cockpit plumbing ships in the SAME change and MERGES headers.**
      `cockpit/api_client.py::_request` (`:28`) is the **only** outbound path (verified: `cockpit/` is
      3 files; sole `requests` use at `:31`; `cockpit/app.py` imports only `api_client`). Inject
      `X-Operator-Key` from the environment **merged with**, never replacing, per-call `headers=`. Two
      call sites pass `headers={"X-Actor": actor}` (`:165`,`:178`) and `X-Actor` is **required** at
      `routes_trading.py:220,246` — measured: a missing/blank header is a **422**, so a replacing
      implementation fails loudly on exactly the two migrated routes. The cockpit **must NOT import
      `app.config`** (import-linter contract 2): hardcode `"OPERATOR_API_KEY"`. **Prove no lockout:**
      kill switch, flatten, session controls, and sensitive reads all usable with the configured key
      (invariant 11).
      — TRACED(`cockpit/api_client.py:28,31,165,178`; `.importlinter` contract 2; GAP-01 `:111`, T-22).

- [x] **D-R5b2-9 Auto-docs coverage is NOT free — bind it to the layer that actually covers it.**
      rev-1 claimed deny-by-default gives operator-only docs automatically. **Refuted:** with
      FastAPI-**dependency** enforcement, `/openapi.json`, `/docs`, `/redoc`,
      `/docs/oauth2-redirect` return **200** (they are added by FastAPI itself, not via
      `include_router`). Only **http-middleware** enforcement 401s them. So either:
      (a) enforce in `@app.middleware("http")` — covers docs and unmatched paths; or
      (b) explicitly disable: `docs_url=/redoc_url=/openapi_url=None` under the flag (the archive's
      choice: `docs_on = not settings.signal_seat_enabled`, `main.py:224-232`).
      **Whichever you choose changes the total operation count**, so reconcile it with D-R5b2-4's
      derived bound. Spec `04:101-104` requires ABSENT-or-operator-only, **never public** — assert it.
      — TRACED(M4b F-3, measured; archive `main.py:224-232`).

- [x] **D-R5b2-10 `root_path` divergence — defense-in-depth, and do not import a private symbol.**
      Starlette 1.3.1 routes on `get_route_path(scope)` which **strips `root_path`**, while
      `request.url.path` does not (measured: `/prefix/api/signals` vs `/api/signals`). An exact-string
      exemption computed from `request.url.path` would stop matching behind a path prefix.
      **However** the sanctioned launcher `app/server.py::run()` (`:43-80`) never passes `root_path`
      to uvicorn, so this is **not reachable today** — treat it as defense-in-depth, not a live break.
      Compute the routed path **inline** (`p = scope["path"]`, minus `scope.get("root_path","")`);
      do **not** import `starlette._utils.get_route_path` (private, no `__all__`). Add a `root_path`
      regression.
      — TRACED(`starlette/_utils.py:96`; `app/server.py:43-80`; M4b F-10).

- [x] **D-R5b2-11 Complete the truncated crown-jewel audit test — with an EXACT-equality assertion
      against a DISTINCT principal.** Staging's `tests/test_signal_routes.py` ends **mid-comment
      (`# The forged X-Ac`) at byte 14628**; its last statement is
      `assert events, "no kill-switch audit event was written"`, so it **parses, collects, and passes
      while asserting nothing about the actor**. Two required properties:
      1. The recorded actor **equals** the composed principal-led form **exactly** — not merely
         `actor != forged`, which passes for `"operator:evil"` or `"evil:operator"`.
      2. **The principal must be a DISTINCT identifier.** The archive stamps
         `authenticated_actor = DEFAULT_ACTOR` (`main.py:281`), byte-identical to the flag-off default
         (`deps.py:23`) — which makes a flag-on authenticated event **indistinguishable** from an
         unauthenticated one. That is itself an *audit-attribution defect* on this WO's crown jewel.
         Stamp something distinguishable (e.g. an `operator:<key-id>` form) and assert it.
      — TRACED(staged byte count/EOF verified; archive `main.py:281` vs `deps.py:23`; M4b F-8).

- [x] **D-R5b2-12 `.env.example` documents the credential surface.** It currently documents **none**
      of `SIGNAL_SEAT_ENABLED`, `OPERATOR_API_KEY`, `SIGNAL_PRODUCER_KEYS` (grep: zero hits),
      violating the primer's "safe, complete configuration template" contract the moment the flag is
      real. Add all three with **blank/placeholder values**; never commit real credentials.
      — TRACED(`.env.example` grep; repo primer §Environment Variables).

- [x] **D-R5b2-13 Flag stays OFF; flag-off byte-equivalent — INCLUDING the `X-Actor` sanitization
      carve-out.** With the flag off: enforcement inert, existing localhost no-auth posture unchanged,
      **no existing test edited**, `harness/bootstrap.py` green. **The trap rev-1 dropped:** the
      archive `get_actor` applies `"".join(ch for ch in raw_label if ch.isprintable())` to `X-Actor`
      **unconditionally** (archive `deps.py:121-125`), whereas master returns the stripped header
      verbatim (`deps.py:87-89`). That is a **flag-independent behavior change** and **no existing
      test covers control characters**, so the specified gate battery cannot detect it. Therefore:
      scope the sanitization **under the flag**, and add a **flag-off regression asserting `get_actor`
      returns a control-character `X-Actor` unchanged**. (`load_settings()` reads the flag from the
      environment, `config.py:535-536` — there is no source-level guard, so flag-off must be tested
      explicitly.)
      — TRACED(archive `deps.py:121-125` verified; master `deps.py:87-89`; M4b F-4; WO-0138:164-167).

- [x] **D-R5b2-14 Dual-store parity for the actor migration — with an app per store.** The two
      migrated routes write **event truth**. Their actor-provenance regressions run on **both** stores.
      Note `any_store` lives at **`conftest.py:29`** (repo root — there is **no** `tests/conftest.py`)
      and yields a **raw store**, not an app; an HTTP-level actor-provenance test must **construct an
      app per store variant**. — TRACED(`conftest.py:29`; M4b F-9).

- [x] **D-R5b2-15 `/api/producers` read is DEFERRED — not implementer judgment.** rev-1 said "only if
      trivially derivable", which is not ratifiable on a human-gated auth surface. `app/store/base.py`
      exposes only `ingest_signal`/`get_signal`/`list_signals` (`:1315-1356`) — there is **no producer
      accessor**, and only `PRODUCER_QUARANTINED` exists in `app/models.py:483`. The read lands with
      **R6**, which owns producer state. Add it to `REQUIRED` then.
      — TRACED(`app/store/base.py:1315-1356`; `app/models.py:483`; M4b F-13).

- [x] **D-R5b2-16 `GET /api/signals` is NOT a one-liner — and R5b-2 now owns the WHOLE read half.**
      It needs `effective_signal_status` — which **exists nowhere in the repo** (verified) — plus an
      **injected clock** (lazy TTL reclassification on read) and facade `list_signals`/`get_signal`
      (archive `facade/signals.py:47,129`). No bare `datetime.now()`.
      **rev-3 addition (from the R5b-1 NEEDS-INPUT disposition):** R5b-2 also inherits **the entire
      `tests/test_signal_facade_reads.py` corpus**, the facade read methods, and any ingest test that
      reads back through `GET /api/signals` (staged `:231`). The authorized mechanical repair on that
      corpus is a **PREDICATE — every `ingest_signal(` call site missing the required `received_at=`
      kwarg** (live count 8, not the 6 originally written; do not encode a number) — plus the
      `SIGNAL_REPLAYED` import path fix (`app.store.core:5587`).
      — TRACED(repo-wide grep: absent; M4b F-12; `SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md` D1/D2/D5).

- [x] **D-R5b2-18 ✅ RATIFIED 2026-07-25 (Ameen): MUTATION-FREE READS — lazy reads vs `SIGNAL_EXPIRED`
      (event-log truth).**
      Accepted `02-lifecycle.md:47` defines `SIGNAL_EXPIRED` as emitted by "sweep, **lazy-expiry**, or
      dead-on-arrival at ingest" with an accepted payload value **`detected_by: "read"`**, and `:97`
      says "TTL lapse … EXPIRED (**lazy** + sweep, rule A4)". The staged corpus asserts the opposite:
      `test_list_signals_lazy_expiry_does_not_mutate_store` (`:112`). **A read that appends a durable
      event is an event-log-truth question on a human-gated surface — it is not the implementer's
      call.** Planning-seat recommendation: **mutation-free reads** — reclassify via a pure
      `effective_signal_status(record, now)`; the durable `SIGNAL_EXPIRED` comes from the sweep, from
      ingest (dead-on-arrival), or atomically inside the A-2 conversion command. Rationale:
      single-writer discipline (a producer-facing GET must not become a writer); write amplification on
      a hostile-input surface; `effective_signal_status` is already the designed derivation; and rule
      A3 holds either way because conversion re-checks TTL atomically.
      **RATIFIED OUTCOME (operator, 2026-07-25): mutation-free reads.** Reads reclassify via a pure
      `effective_signal_status(record, now)` and append **nothing**; the durable `SIGNAL_EXPIRED` is
      written by the sweep, at ingest (dead-on-arrival, `detected_by:"ingest"`), or atomically inside
      the A-2 conversion command. The staged pin
      `test_list_signals_lazy_expiry_does_not_mutate_store` is therefore **correct and load-bearing** —
      never weaken it.
      **Required amendment shipping WITH this rung:** `docs/spec/signal-seat/02-lifecycle.md` — state
      that lazy expiry is **projection-level reclassification**, and remove `"read"` from
      `detected_by` (or redefine it as sweep-attributed). This is an **event-log-truth change on a
      human-gated surface**: it ships in the same change, is called out explicitly in the REV-0043
      request, and the reviewer verifies the amended text against the implementation. Do **not** ship
      the code without the amendment, or the spec and behavior diverge silently.
      — TRACED(`02-lifecycle.md:47,97`; staged `test_signal_facade_reads.py:112`; disposition D5;
      operator ratification 2026-07-25).

- [x] **D-R5b2-17 Matrix lives in its OWN test module — a planning-seat reoptimization.**
      `tests/test_signal_routes.py` is the shared target of R5b-1, R5b-2, R6 **and** R7; four rungs
      editing one file guarantees collisions. Put the authorization matrix and its `REQUIRED`/
      `CLASSIFIED` constants in a **new dedicated module** (e.g.
      `tests/test_route_authorization_matrix.py`) so R6/R7 extend a small focused file instead of
      merging into the large one. The crown-jewel audit test (D-R5b2-11) stays with the signal-route
      corpus. — TRACED(M4b H-6).

---

## M2 — Lifecycle totality: the authenticated principal

| Edge | Driver | Requirement |
|---|---|---|
| **birth** | operator auth + http-middleware, on credential validation | stamp a **distinct** principal (not `DEFAULT_ACTOR`) — D-R5b2-11 |
| **read (14 routes)** | `Depends(get_actor)` | principal wins; `X-Actor` subordinate label |
| **read (2 routes)** | `routes_trading.py:220`,`:246` — direct required Header | **MUST migrate**; they bypass `get_actor` today |
| **terminal (authorized)** | response returned; state dies with the request scope | no cross-request carryover |
| **terminal (401)** | no/unknown credential (also unmatched paths under middleware) | before the handler body; no event append |
| **terminal (403)** | valid credential, wrong role | distinct from 401; required negative |
| **flag-off** | no principal stamped | `DEFAULT_ACTOR`/`X-Actor` exactly as today, **including no sanitization** (D-R5b2-13) |

**Precondition proof (twice corrected).** Not "no route reads an actor where the principal was
unstamped" (WO-0138's version — the principal *is* stamped), and not merely "reads through the
principal-preferring path": **every route that writes an actor into an event payload must read it
through the principal-preferring path, AND the stamped principal must be distinguishable from the
flag-off default.** Otherwise the invariant is satisfiable while proving nothing (M4b F-8). The route
set comes from **grep** (16 routes), not from `get_actor` call sites.

---

## M3 — Consumer inventory + control-action sweep

| Consumer | Class | Control-action finding |
|---|---|---|
| The 2 direct-header actor routes | **affected — the F2 hole** | (1) *needed guard skipped*: canonical-fill and attestation actors stay caller-controlled unless migrated. |
| The 14 `Depends(get_actor)` routes | **affected** | (3) *wrong order*: principal must win; and (2) sanitization must not leak to flag-off. |
| `cockpit/api_client.py:165,178` | **affected** | (2): replacing headers ⇒ **422** on the two migrated routes. Merge. |
| Cockpit kill switch / flatten / session | **affected** | (3): enforcement before plumbing = operator lockout (T-22). |
| All mounted `/api` operations | **affected** | (1): unclassified ⇒ ships unauthenticated. Ratchet. |
| **Absent** required routes | **affected — rev-1's blind spot** | (1): a silently unmounted required route is undetectable without the literal `REQUIRED` list, and deny-by-default 401s unmatched paths so the negative sweep cannot catch it either. |
| `GET /api/events` | **affected — event-log truth** | (1): the audit log itself readable without a credential. |
| Auto-docs routes | **affected** | (1): schema enumeration — and `include_in_schema=False` hides them from the openapi cross-check. |
| Destructive commands (kill-switch, flatten, emergency-reduce, session/close) | **affected — matrix hazard** | (2)/(3): a matrix that *exercises* them would engage the kill switch and close the session, and later cases would 409 by ordering. **"Behave" = auth outcome only** (`401` none, `401` invalid, `403` wrong-role, `not in (401,403)` operator-key) with a **fresh app per parameterized case**. |
| Future R6/R7 routes | **unknown → resolved** | (4): the ratchet fails on any later unclassified route; `REQUIRED` grows per rung. |
| Existing suite + `harness/bootstrap.py:117` | **unaffected (must prove)** | Verified: zero tests assert route counts, openapi snapshots, or middleware order; flag-on tests never issue HTTP. Control-char coverage is the one real gap (D-R5b2-13). |
| `.importlinter` contracts 2 & 5 | **affected** | Cockpit must not import `app.*`. **Contract 5 already gains `routes_signals` from R5b-1 — do not re-add.** |

---

## M4a — Prospective hindsight

1. *"Operator couldn't hit the kill switch."* → D-R5b2-8.
2. *"A fill was attributed to a forged actor."* → D-R5b2-5 (the 2-route migration).
3. *"The matrix was green and discovered nothing."* → D-R5b2-4.
4. *"A required route was silently unmounted and nothing failed."* → D-R5b2-3 item 1.
5. *"A flag-on audit event was indistinguishable from an unauthenticated one."* → D-R5b2-11.
6. *"`/openapi.json` was public."* → D-R5b2-9.
7. *"R6 shipped release unauthenticated."* → D-R5b2-3 ratchet.
8. *"Session closed with no credential."* / *"Producer read the audit log."* → D-R5b2-7.
9. *"Running the matrix engaged the kill switch."* → M3 destructive row.
10. *"Cockpit commands lost their audit label."* → D-R5b2-8.
11. *"Beta's `X-Actor` silently changed."* → D-R5b2-13.
12. *"Operator had no documented way to set the key."* → D-R5b2-12.

---

## ⚠ BUILD HAZARDS (M4b-verified)

1. **H-1, highest — the crown-jewel test cannot run as staged.** Every `build_flag_on_app(...)` call
   site in both reference corpora (archive `tests/test_signal_routes.py:53,360,417,489,505,521`;
   staging `:53,~360`) **omits the now-required keyword-only `test_authority`** that R5a added
   (`tests/signal_seat_helpers.py:53-66`, gated on the **private** `_IN_PROCESS_TEST_AUTHORITY`
   sentinel). Import the private sentinel at every ported call site.
2. **H-2** — archive `app/api/deps.py:15` imports `from app.facade.signals import SignalFacade,
   StoreBackedSignalFacade`; **R5b-1 creates that module**. **⟨Step-0⟩** confirm its actual exports.
3. **H-3** — archive `get_actor` uses `request: Request = None  # type: ignore[assignment]`, but
   `pyproject.toml:54` sets `warn_unused_ignores = true` and the ADR-007 grandfather list is **fully
   burned down** (`:72-77`). Use `Optional[Request] = None` instead. Existing direct call
   `tests/test_phase6_facade_foundations.py:108` uses `get_actor(x_actor=header)` — the keyword form
   must keep working.
4. **H-4 — middleware order.** `starlette/applications.py:101` inserts at index 0, so
   **last-registered runs outermost**. Master has **zero** middleware in `create_app`; R5b-2 adds the
   first. If the archive's `_fail_closed_launch_guard` is also ported, the operator middleware would
   wrap it and a credential-free request on an unsanctioned app returns 401 instead of the intended
   503. Order deliberately and test it.
5. **H-5** — deny-by-default 401s **unmatched** paths. Good posture, but it removes the negative
   sweep's ability to detect a wrong path template; only D-R5b2-3 item 1 restores it.
6. **H-6** — R5b-1 collision: both WOs edit `app/api/deps.py` and `app/main.py`. Resolved for tests
   by D-R5b2-17.
7. **H-7** — the 10 grandfathered `ruff format` files are `app/recorder/*`, `harness/bootstrap.py`,
   5 tests and one review probe — **not** `deps.py`/`main.py`/`api_client.py`. Your files must be
   formatted.

## Measured mounted-route inventory (flattener + `openapi` cross-checked, pre-R5b-1)

**34 `/api` operations + 4 auto-docs = 38** with `enable_dev_routes=True`; **33** `/api` without.
**Post-R5b-1 this becomes 35/39** — re-derive at Step 0, never copy this number.
Exact templates (rev-1 wrote `{id}` for six of these — fatal if copied into `REQUIRED`):

`DELETE /api/watchlist/{symbol}` · `GET /api/candidates` · `GET /api/candidates/{candidate_id}` ·
`GET /api/envelopes` · **`GET /api/events`** · `GET /api/health` *(public)* ·
`GET /api/marketdata/snapshots` · `GET /api/operator/orders` · `GET /api/order-recoveries` ·
`GET /api/orders` · `GET /api/orders/{order_id}` · `GET /api/positions` ·
`GET /api/positions/{symbol}` · `GET /api/protection` · `GET /api/reconciliation` ·
`GET /api/review` · `GET /api/sell-intents` · `GET /api/session` · `GET /api/watchlist` ·
`POST /api/candidates/{candidate_id}/approve` · `POST /api/candidates/{candidate_id}/reject` ·
`POST /api/controls/kill-switch` · `POST /api/controls/pause-buys` ·
`POST /api/controls/resume-buys` · `POST /api/dev/candidates` *(dev-gated)* ·
`POST /api/envelopes/approve` · `POST /api/envelopes/{envelope_id}/cancel` ·
`POST /api/order-recoveries/{recovery_id}/fills` ·
`POST /api/order-recoveries/{recovery_id}/reconcile` · `POST /api/orders/{order_id}/cancel` ·
`POST /api/positions/{symbol}/emergency-reduce` · `POST /api/positions/{symbol}/flatten` ·
`POST /api/session/close` · `POST /api/watchlist` · + R5b-1's signal routes.

Deferred `REQUIRED` members: **`POST /api/producers/{producer_id}/release` + `/api/producers` (R6)**,
**approve/reject (R7)**.

## Step-0 verification list (⟨Step-0⟩ items, all must be reported before building)

1. R5b-1's actual mounted method/path for the producer route (D-R5b2-6).
2. Whether R5b-1 authored facade `list_signals`/`get_signal` (D-R5b2-16).
3. Whether R5b-1 left `get_actor` untouched (WO-0138 expressed a *preference*, not a guarantee).
4. Whether `operator_key_valid`/`producer_key_valid` already exist in `deps.py`.
5. Whether R5b-1 disabled auto-docs (WO-0138 said no — confirm, it changes the count).
6. `app/facade/signals.py`'s actual exports (H-2).
7. The re-derived operation count under `flag_on_settings` (D-R5b2-4).

## Required behavior (Fable v3)

- [ ] **GATE** + predecessor check (D-R5b2-1), else STOP. Report the Step-0 list.
- [ ] Operator-key auth + **http-middleware** deny-by-default; 401/403 distinction.
- [ ] Principal stamping (**distinct** identifier) + `get_actor` precedence + **the 2-route
      migration**, dual-store with an app per store.
- [ ] Flag-off control-character regression for `get_actor` (D-R5b2-13).
- [ ] `GET /api/signals` incl. authoring `effective_signal_status` + injected clock.
- [ ] The matrix in its own module: literal `REQUIRED` + both subset assertions + derived bound +
      auth-outcome-only + fresh app per case.
- [ ] Auto-docs: middleware coverage **or** explicit disablement; assert never public.
- [ ] `root_path` defense-in-depth regression (inline path computation).
- [ ] Cockpit `X-Operator-Key` **merge** + no-lockout usability proof.
- [ ] Complete the crown-jewel audit test with exact-equality on a distinct principal.
- [ ] `.env.example` credential documentation.
- [ ] Flag-off non-regression: zero existing-test edits, bootstrap green.
- [ ] FIX blocks with root cause; fresh pasted evidence.

## Gate battery (fresh, pasted)

`ruff check .` · `ruff format --check` on R5b-2-owned files (the 10 inherited stay grandfathered) ·
`mypy app/` · `lint-imports` (contracts 2 and 5 green) · the R5b-2 corpus + full suite ·
`python -m pytest -q tests/r2_conformance_oracle.py` · `pytest -q tests/test_wo0113_repair_scaling.py`
· `python harness/bootstrap.py`.

## Stop conditions

Any accepted-text conflict not already recorded here · any need to weaken an existing assertion · any
rails enforcement, release action, approve/reject, or conversion work · anything making the flag
independently enable-able · any schema/migration or event-log **vocabulary** change · a P0-equivalent
hole in accepted text.

## Filter-safety clause (rung risk: **HIGH** — the highest in the ladder)

**Authorized defensive engineering on the operator's own local, paper-only application.** No external
target, no network probing, no credential access, no live trading, no persistence objective.

**Report at the defect level** — cause · impact · affected local files · fix · pass/fail evidence.
**Do not** write reusable bypass procedures or payloads in code, comments, commits, or the review
request. **Do not** run open-ended adversarial discovery on the enforcement layer; the independent
**REV-0043 Claude seat is the sanctioned adversarial net**.

**Use:** *missing-authorization coverage* · *unauthorized-role acceptance* · *audit-attribution
defect* · *incorrect type acceptance* · *non-atomic transaction boundary*.
**Avoid:** "bypass auth", "forge the actor", "escalate privileges", "impersonate the operator" — same
engineering content, far lower false-positive risk. On a filter interruption the fixes are likely
already applied: resume and request a **defect-level re-report**, never a re-run.

## Close-out expectations

Human-gated ⇒ set WO-0139 to **REVIEW** and stage `work/review/REV-0043/request.md` (defect-level,
named classes, no exploit narration). **State explicitly that GAP-01 and GAP-02 are closed and that
the deferred item is the spec-04 required-present completeness obligation for R6/R7 routes** — so the
reviewer can check the claim rather than infer it. Do **not** create `result.md`, touch the ledger,
move to completed, merge, open a PR, or enable the flag. Push `codex/signal-r5b2-operator-auth`.

## §M4b record — 15 findings, 4 P0 (all planning-seat verified before applying)

| # | Finding | Verified | Applied |
|---|---|---|---|
| **F-1 (P0)** | Required-present set derived from discovery is **circular** — cannot detect absence; spec `04:99` forbids exactly this; and deny-by-default 401s unmatched paths so the negative sweep can't catch it either | YES — spec wording exact | D-R5b2-3: literal `REQUIRED` + two subset assertions |
| **F-2 (P0)** | Counts wrong: **14** `Depends(get_actor)` not 13; **16** total not 15 (line list was right, arithmetic wrong) | YES — re-grepped: 14 | D-R5b2-5 corrected |
| **F-3 (P0)** | "Auto-docs operator-only for free" is implementation-dependent: dependency enforcement leaves them **200**; only middleware 401s them; archive chose explicit disablement | YES — archive `main.py:224-232` | D-R5b2-9 rewritten |
| **F-4 (P0)** | Archive `get_actor` strips non-printables from `X-Actor` **unconditionally** → flag-off behavior change, and **no existing test covers control chars** | YES — archive `deps.py:121-125` | D-R5b2-13 carve-out + regression |
| F-5 (P1) | Six path templates wrong (`{id}` vs `{candidate_id}`/`{envelope_id}`/`{recovery_id}`/`{order_id}`) — fatal if copied into `REQUIRED` | YES | inventory corrected |
| F-6 (P1) | Count is config-dependent (33/34) and becomes 35/39 post-R5b-1; a hardcoded bound is brittle | YES | D-R5b2-4 derives the bound |
| F-7 (P1) | GAP-02 **over-deferred and stranded** — its three clauses are all mounted-route-scoped and closable here; the deferred artifact is spec-04 completeness, a different thing | YES — threat model `:112` | D-R5b2-3 closes GAP-02; deferred item renamed |
| F-8 (P1) | `actor != forged` is not mutation-sensitive; archive principal == `DEFAULT_ACTOR` makes authenticated events indistinguishable | YES | D-R5b2-11 exact equality + distinct principal |
| F-9 (P2) | `tests/conftest.py` **does not exist**; `any_store` is `conftest.py:29` and yields a raw store | YES | D-R5b2-14 corrected |
| F-10 (P2) | `root_path` unreachable (`run()` never passes it); `get_route_path` is private | YES | D-R5b2-10 downgraded, inline computation |
| F-11 (P2) | Missing ⟨Step-0⟩ items | — | Step-0 list added (7 items) |
| F-12 (P2) | `GET /api/signals` needs `effective_signal_status`, absent repo-wide | YES | D-R5b2-16 |
| F-13 (P2) | `/api/producers` "if trivially derivable" not ratifiable; no producer accessor exists | YES | D-R5b2-15 DEFER |
| F-14 (P3) | Cockpit half of GAP-05 unowned | — | assigned to R7 |
| F-15 (P3) | Public-health exemption should also be exact `(method, path)` | YES | folded into D-R5b2-6 |

**Planning-seat reoptimization beyond M4b:** D-R5b2-17 moves the matrix into its own test module,
since `tests/test_signal_routes.py` would otherwise be edited by four consecutive rungs.
