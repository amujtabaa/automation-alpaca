# Codex kickoff — Signal Seat R5b-2: operator enforcement surface (LOCAL, strongest model)

> Operator launch prompt, drafted by the planning seat 2026-07-25. Paste into a FRESH **local** Codex
> session at the repo root, strongest model, full effort. **Round 2 of 4 — runs ALONE.**
>
> The decision block below is the M1 assumption ledger of a FULL `.ai-os/core/18` war-game whose
> **M4b pass produced 15 findings including 4 P0** — among them a route matrix that would have shipped
> green while proving nothing about route existence. Every P0 was verified against code by the planning
> seat before correction. Pasting this unedited RATIFIES rev-2.

---

Codex, you are the implementer seat building **WO-0139 — Signal Seat R5b-2**, the operator enforcement
surface. Read `AGENTS.md`, the `CLAUDE.md` safety core, then
**`work/queue/WO-0139-signal-r5b2-operator-enforcement.md` IN FULL** — it is your contract (M1
decision block D-R5b2-1..17, the M2 principal lifecycle, the M3 consumer inventory, the §M4b record,
the verified BUILD HAZARDS, the measured route inventory, the Step-0 list, stop conditions). Fable v3:
GATE, red-first, fresh pasted evidence, FIX blocks with root cause. No completion claims without
evidence.

## Authorized defensive scope (read first)

**Authorized defensive engineering on the operator's own local, paper-only trading application, in the
operator's own repository.** The task is to require a local operator credential before the app serves
sensitive data or accepts commands, and to bind the audit actor to that credential so a recorded
"who authorized this" cannot be supplied by the caller. There is **no external target, no network
probing, no credential access, no live trading, no persistence objective.**

**Reporting convention — this is the highest filter-risk rung in the ladder.** Report at the **defect
level**: cause · impact · affected local files · fix · pass/fail evidence. Do **not** write reusable
bypass procedures or payloads in code, comments, commit messages, or the review request. Do **not** run
an open-ended "try to break it" pass on the enforcement layer — the independent **REV-0043 Claude seat
is the sanctioned adversarial net.**

**Use this vocabulary:** *missing-authorization coverage* (a route reachable without the required
credential) · *unauthorized-role acceptance* (a credential accepted on the wrong route class) ·
*audit-attribution defect* (a recorded actor that is not the authenticated principal) · *incorrect type
acceptance* · *non-atomic transaction boundary*.
**Avoid:** "bypass auth", "forge the actor", "escalate privileges", "impersonate the operator" — the
same engineering content, far lower false-positive risk. If a filter interruption occurs, your fixes
are probably already applied: resume and give a **defect-level re-report**, never a re-run.

## What R5b-2 is — and what it deliberately is NOT

R5a made `create_app` refuse to **construct**. R5b-1 added one authenticated **producer** input path.
**R5b-2 makes every sensitive request fail without the operator credential.**

**IN:** operator-key auth + **http-middleware** deny-by-default (`app/api/deps.py`, `app/main.py`);
authenticated-principal stamping with a **distinct** identifier; `get_actor` precedence; **migration of
the two direct-header actor routes**; `GET /api/signals` (incl. authoring `effective_signal_status`);
the route-authorization matrix **in its own new test module**; auto-docs classification; cockpit
`X-Operator-Key` plumbing; `.env.example`; completion of the truncated crown-jewel audit test.

**NOT IN:** rails enforcement and `POST /api/producers/{id}/release` (**R6**); `/api/producers` read
(**DEFERRED to R6** — D-R5b2-15, not your judgment call); approve/reject and conversion (**R7**);
schema/migration; event-log **vocabulary** changes; enabling the flag.

## Setup — the HARD gate first

1. `git status --short` — clean, else STOP.
2. `git fetch origin`.
3. **HARD GATE — both must hold, else STOP and report:**
   - `git ls-tree master app/api/routes_signals.py` returns a blob (R5b-1 is merged), **and**
   - `work/review/REV-0042/disposition.md` exists (R5b-1's review is dispositioned).
   Do not start on an unmerged or unreviewed predecessor.
4. `git checkout -b codex/signal-r5b2-operator-auth origin/master`
5. `git fetch origin codex/signal-tests-staging archive/claude-wo-0001-install-checks-2x5ys8` — the
   staged corpus and the archive **design reference** (1021-line route test, `deps.py`, `main.py`).
   Read the archive; **never port it verbatim** (see BUILD HAZARDS).

Never push master. No PR unless asked. Paper-only; zero credentials/broker/live. Pytest scratch in OS
temp, never repo-root.

## Step 0 — report these SEVEN verifications before writing code

R5b-1 was still in flight when this WO was drafted, so these are marked ⟨Step-0⟩ rather than assumed.
Report each, and flag any divergence from the WO **before** building:

1. R5b-1's actual mounted method/path for the producer route.
2. Whether R5b-1 authored facade `list_signals`/`get_signal`.
3. Whether R5b-1 left `get_actor` untouched.
4. Whether `operator_key_valid`/`producer_key_valid` already exist in `deps.py`.
5. Whether R5b-1 disabled auto-docs (it changes the operation count).
6. `app/facade/signals.py`'s actual exports.
7. The **re-derived** operation count under `flag_on_settings` (pre-R5b-1 it was 34 `/api` + 4 docs;
   post-R5b-1 expect ~35/39 — **derive it, never copy a number**).

## Decision block (M1 ledger rev-2, post-M4b; pre-checked = ratified on paste; edit to override)

- [x] **D-R5b2-1 HARD predecessor gate** (Setup step 3).
- [x] **D-R5b2-2 Scope = request-time operator enforcement** (the boundary above).
- [x] **D-R5b2-3 The matrix asserts TWO independent directions over a LITERAL required set.** A set
      derived from discovery is **circular — it can never detect absence**, and spec `04:98-100`
      forbids exactly that ("asserted to **EXIST** … a required route silently unmounted **FAILS**, not
      merely 'classify whatever is mounted'"). Deny-by-default middleware also 401s **unmatched** paths,
      so a negative sweep alone passes for path templates that do not exist. Assert **both**:
      **(1) EXISTENCE** `REQUIRED ⊆ discovered`, where `REQUIRED` is a **literal hardcoded list of
      `(method, path)` pairs** in the test module, never computed from the app; **(2) RATCHET**
      `discovered ⊆ CLASSIFIED`, so any mounted-but-unclassified route FAILS. Plus 401 with no
      credential and 403 with a wrong-role credential on every sensitive route; `GET /api/health` is
      the only public one. **This closes GAP-01 and GAP-02 in full.** The deferred item is the distinct
      **spec-04 required-present completeness** obligation for R6's release and R7's approve/reject
      routes — add each to `REQUIRED` as its rung lands.
- [x] **D-R5b2-4 Discovery = recursive flattener + `openapi()` cross-check + a DERIVED bound.** A naive
      `for r in app.routes: r.path` is **fail-OPEN**: `app.routes` is 4 `Route` + **8 `_IncludedRouter`
      with `path is None`**, so it discovers **zero** `/api` routes and every assertion passes
      vacuously. Recurse `_IncludedRouter.original_router.routes` and `Mount.routes`. **Derive the
      bound** from the same `Settings` the test builds (`flag_on_settings` pins
      `enable_dev_routes=True`) — the count is config-dependent (33 vs 34) and grows per rung; never
      hardcode a magic number. Auto-docs routes are `include_in_schema=False` and therefore **invisible
      to the openapi cross-check** — assert them separately.
- [x] **D-R5b2-5 The actor-consuming set is 16 routes — by GREP, not by `get_actor` call sites.** **14**
      use `Depends(get_actor)`; **2 bypass it entirely** with
      `actor: str = Header(..., alias="X-Actor", min_length=1)` — `routes_trading.py:220`
      (`POST /api/order-recoveries/{recovery_id}/fills`, ingests a canonical **fill**, invariant 9) and
      `:246` (`.../reconcile`, the human **attestation**). **Both MUST migrate** to the
      principal-preferring path, each with its own regression. Fixing `get_actor` alone is insufficient.
- [x] **D-R5b2-6 Producer AND public exemptions match an exact `(method, path)` pair — never a prefix.**
      Only `POST /api/signals` is producer-only; **`GET /api/signals` is operator-only**, so path-only
      matching would exempt it. Tighten the public exemption the same way so `POST /api/health` is not
      silently public.
- [x] **D-R5b2-7 Enforcement covers sensitive READS**, including these five earlier enumerations missed:
      **`GET /api/events`** (the **audit event log**), `GET /api/protection`, `GET /api/sell-intents`,
      `GET /api/reconciliation`, `GET /api/operator/orders`. `POST /api/session/close` is
      **operator-only** — a mutating command, not a read.
- [x] **D-R5b2-8 Cockpit plumbing SAME change, and it MERGES headers.**
      `cockpit/api_client.py::_request` (`:28`) is the only outbound path. Inject `X-Operator-Key` from
      the environment **merged with**, never replacing, per-call `headers=` — two sites pass
      `headers={"X-Actor": actor}` (`:165`,`:178`) and `X-Actor` is **required** at the two migrated
      routes, so a replacing implementation is a loud **422**. **Do not import `app.config`**
      (import-linter contract 2) — hardcode `"OPERATOR_API_KEY"`. Prove **no lockout**: kill switch,
      flatten, session controls, and sensitive reads all usable with the configured key (invariant 11).
- [x] **D-R5b2-9 Auto-docs coverage is NOT free.** With FastAPI-**dependency** enforcement,
      `/openapi.json`, `/docs`, `/redoc`, `/docs/oauth2-redirect` return **200** — they are added by
      FastAPI itself, not via `include_router`. Only **http-middleware** enforcement 401s them. Either
      (a) enforce in `@app.middleware("http")`, or (b) explicitly set
      `docs_url=redoc_url=openapi_url=None` under the flag (the archive's choice). **Whichever you pick
      changes the operation count** — reconcile with D-R5b2-4. Spec requires ABSENT-or-operator-only,
      **never public**; assert it.
- [x] **D-R5b2-10 `root_path` divergence = defense-in-depth; no private imports.** Starlette routes on
      a path with `root_path` **stripped**, while `request.url.path` keeps it — so an exemption computed
      from `request.url.path` would stop matching behind a path prefix. Not reachable today
      (`app/server.py::run()` never passes `root_path`), so treat it as defense-in-depth. Compute the
      routed path **inline** from `scope["path"]` and `scope.get("root_path","")`; do **not** import
      `starlette._utils.get_route_path`. Add a `root_path` regression.
- [x] **D-R5b2-11 Complete the crown-jewel audit test with EXACT equality and a DISTINCT principal.**
      The staged file ends **mid-comment (`# The forged X-Ac`) at byte 14628**; its last statement is
      `assert events, …`, so it **passes while asserting nothing about the actor**. Require: (1) the
      recorded actor **equals** the composed principal-led form **exactly** — `actor != forged` is not
      mutation-sensitive (it passes for `"operator:evil"`); (2) the stamped principal is a **distinct**
      identifier — the archive stamps `DEFAULT_ACTOR`, byte-identical to the flag-off default, which
      makes an authenticated event indistinguishable from an unauthenticated one (an
      *audit-attribution defect* on this rung's own crown jewel).
- [x] **D-R5b2-12 `.env.example`** documents `SIGNAL_SEAT_ENABLED`, `OPERATOR_API_KEY`,
      `SIGNAL_PRODUCER_KEYS` (currently none of the three) with blank/placeholder values. Never commit
      real credentials.
- [x] **D-R5b2-13 Flag stays OFF; flag-off byte-equivalent — INCLUDING the `X-Actor` sanitization
      carve-out.** The archive `get_actor` strips non-printable characters from `X-Actor`
      **unconditionally**, while master returns the stripped header verbatim. That is a
      **flag-independent behavior change**, and **no existing test covers control characters**, so the
      gate battery cannot detect it. Scope the sanitization **under the flag** and add a **flag-off
      regression asserting `get_actor` returns a control-character `X-Actor` unchanged**. No existing
      test may need editing; `harness/bootstrap.py` stays green.
- [x] **D-R5b2-14 Dual-store parity with an app per store.** The two migrated routes write event truth;
      their actor-provenance regressions run on **both** stores. `any_store` is at **`conftest.py:29`**
      (repo root — there is **no** `tests/conftest.py`) and yields a **raw store**, so construct an app
      per store variant.
- [x] **D-R5b2-15 `/api/producers` read is DEFERRED to R6** — there is no producer accessor in
      `app/store/base.py`. Not implementer judgment.
- [x] **D-R5b2-16 `GET /api/signals` is not a one-liner** — it needs `effective_signal_status`, which
      **exists nowhere in the repo** (author it), an **injected clock** for lazy TTL reclassification
      (no bare `datetime.now()`), and the facade read methods.
- [x] **D-R5b2-17 The matrix lives in its OWN test module** (e.g.
      `tests/test_route_authorization_matrix.py`) with the `REQUIRED`/`CLASSIFIED` constants, because
      `tests/test_signal_routes.py` is otherwise edited by four consecutive rungs. The crown-jewel audit
      test stays with the signal-route corpus.

## ⚠ BUILD HAZARDS (verified — these bite a verbatim archive port)

1. **The crown-jewel test cannot run as staged.** Every `build_flag_on_app(...)` call site in both
   corpora (archive `:53,360,417,489,505,521`; staging `:53,~360`) **omits the now-required keyword-only
   `test_authority`** that R5a added, gated on the **private** `_IN_PROCESS_TEST_AUTHORITY` sentinel in
   `tests/signal_seat_helpers.py`. Import the private sentinel at every ported call site.
2. Archive `app/api/deps.py:15` imports `app.facade.signals` — **R5b-1 created that module**; confirm
   its real exports (Step 0 item 6).
3. Archive `get_actor` uses `request: Request = None  # type: ignore[assignment]`, but
   `warn_unused_ignores = true` and the ADR-007 grandfather list is **fully burned down**. Use
   `Optional[Request] = None`. The existing direct call
   `tests/test_phase6_facade_foundations.py:108` uses `get_actor(x_actor=header)` — the keyword form
   must keep working.
4. **Middleware order:** Starlette inserts at index 0, so **last-registered runs outermost**. Master has
   **zero** middleware in `create_app`; you add the first. If you also port the archive's fail-closed
   launch guard, the operator middleware would wrap it and a credential-free request on an unsanctioned
   app returns 401 instead of the intended 503. Order deliberately and test it.
5. Deny-by-default 401s **unmatched** paths — good posture, but it is why D-R5b2-3's literal `REQUIRED`
   list is mandatory.
6. The 10 grandfathered `ruff format` files are `app/recorder/*`, `harness/bootstrap.py`, five tests and
   one review probe — **not** `deps.py`/`main.py`/`api_client.py`. Your files must be formatted.

## Continuity across pauses and compaction

**FIRST commit** (with WO activation → ACTIVE, move to `work/active/`): create
`work/active/SIGNAL-R5b2-STATE.md` carrying (a) this decision block **verbatim as pasted**, (b) the
Step-0 report, (c) a slice scoreboard (operator auth + middleware · principal stamping + `get_actor`
precedence · the 2-route migration · `GET /api/signals` + `effective_signal_status` · matrix module ·
auto-docs · cockpit plumbing · crown-jewel test · `.env.example` · flag-off non-regression · green
evidence · REV-0043 staging), (d) an evidence log. Update at every slice boundary. After any
pause/compaction re-read, in order: this kickoff → the state file → the WO. Verify with
`git log`/`git status`, never memory.

## Order of work (red-first each slice)

1. Predecessor gate → branch → **Step-0 report** → corpus import → prove RED.
2. Operator-key auth dependency + http-middleware deny-by-default (401/403), exact-pair exemptions.
3. Principal stamping (distinct identifier) + `get_actor` precedence + the **2-route migration**
   (dual-store, app per store) + the flag-off control-character regression.
4. `GET /api/signals` + `effective_signal_status` + injected clock.
5. The matrix module: literal `REQUIRED` + both subset assertions + derived bound + auth-outcome-only +
   fresh app per case; auto-docs assertion; `root_path` regression.
6. Cockpit `X-Operator-Key` merge + the no-lockout usability proof.
7. Crown-jewel audit test completion; `.env.example`; flag-off non-regression sweep.

## Gate battery (fresh, pasted — all of it)

`ruff check .` · `ruff format --check` on your own files · `mypy app/` · `lint-imports` (contracts 2 and
5 green — **contract 5 already gained `routes_signals` from R5b-1; do not re-add**) · your corpus + the
full suite · `python -m pytest -q tests/r2_conformance_oracle.py` (**CI's invocation**) ·
`pytest -q tests/test_wo0113_repair_scaling.py` · `python harness/bootstrap.py`.

## Stop conditions — report, never self-authorize

Any accepted-text conflict not already recorded in the WO · any need to weaken an existing assertion ·
any rails enforcement, release action, approve/reject, or conversion work · anything making the flag
independently enable-able · any schema/migration or event-log **vocabulary** change · a P0-equivalent
hole in accepted text.

## Close-out

Set WO-0139 to **REVIEW** and stage `work/review/REV-0043/request.md` (defect-level, named classes, no
exploit narration). **State explicitly that GAP-01 and GAP-02 are closed, and that the deferred item is
the spec-04 required-present completeness obligation for R6/R7 routes** — so the reviewer checks the
claim rather than infers it. Do **NOT** create `result.md` (reviewer-owned), touch the ledger, move to
completed, merge, open a PR, or enable the flag. Push `codex/signal-r5b2-operator-auth`.

**Report in your final summary:** the Step-0 findings, the delivery branch + SHA, a defect-class table
for anything you fixed, the full pasted gate evidence, the re-derived operation count, and anything you
had to STOP on.
