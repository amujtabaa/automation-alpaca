---
type: Work Order
title: "Signal Seat R5b — request-time auth surface (signal facade + producer ingest route + operator enforcement + route matrix + cockpit plumbing)"
status: DRAFT
work_order_id: WO-0138
wave: signal-seat reconciliation ladder, step R5 (split; R5b = request-time auth surface)
model_tier: strong (LOCAL Codex — human-gated auth surface; operator-lockout + approval-audit risk)
predecessors: [WO-0134 (R4 model+store), WO-0137 (R5a construction-time foundation), WO-0136 (threat model)]
successors: [R6 WO-0104 (real rails provider), R7 (conversion)]
review: "REV-0042 required (human-gated surface: request-time auth, approval audit, cockpit credential plumbing)"
wargame: "FULL per .ai-os/core/18 — M1 ledger + M2 lifecycle + M3 consumers + M4a/M4b (this document)"
---

# WO-0138 — Signal Seat R5b: the request-time auth surface

R5a made `create_app` **refuse to construct** without a sanctioned launch capability, valid config,
and conforming rails. R5b makes a **request fail auth**: the typed signal facade, the producer ingest
route, operator enforcement across every sensitive route (reads included), the fail-closed mounted-route
authorization matrix, and the cockpit credential plumbing that keeps the operator from being locked out.

**The crown jewel this WO protects:** a signal NEVER executes without human approval, and the
**approval audit must be unforgeable** — who authorized a real order cannot be caller-controlled.

## Scope boundary

**IN (R5b):** `app/facade/signal_*` typed facade (`StoreBackedSignalFacade` — absent on master),
`app/api/routes_signals.py`, `app/api/deps.py` auth dependencies, operator-enforcement middleware,
the full mounted-route authorization matrix, auto-docs disablement, `cockpit/api_client.py`
`X-Operator-Key` plumbing, `.importlinter` contract-5 `routes_signals` line.

**OUT:** R6 (WO-0104) real rails provider — ceiling/durable-budget/quarantine-opener/release
enforcement and the paced-flood proof; R7 conversion (approve → order intent); schema/migration;
event-log truth changes; flag enablement (D-2a).

**Shared seams:** `app/main.py::create_app` (R5a landed the skeleton + three construction guards;
R5b extends it with routers/middleware), `app/config.py` (R5a owns; R5b consumes the credential
fields).

## GAP ownership inherited from WO-0136 (threat model)

R5a closed **GAP-04**. R5b owns **GAP-01, GAP-02, GAP-05, GAP-06**; **GAP-03** is joint-enablement
(R5b must not make the flag independently enable-able). GAP-08 → R6, GAP-09 → R7, GAP-07 → ADR-013.

---

## M1 — Assumption ledger / decision block

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` (verified
against code/accepted text now) or `INHERITED` (from a named prior ratified decision). Per
`.ai-os/core/18`, **no `ASSUMED` line is pre-checked** in a FULL war-game block.

- [x] **D-R5b-1 Branch & corpus.** Branch `codex/signal-r5b-auth` from master (after R5a merges).
      Pull the R5b staged slices from `origin/codex/signal-tests-staging`: `test_signal_routes.py`
      (24 cases) and `test_signal_facade_reads.py` (dual-store `any_store` async reads). Reuse the
      existing `tests/signal_seat_helpers.py` seam that R5a hardened.
      — TRACED(`git ls-tree origin/codex/signal-tests-staging tests/` lists both; `signal_seat_helpers.py`
      already on master post-R5a with explicit-test-authority gating).

- [x] **D-R5b-2 Scope = request-time auth** (the boundary above). R5b does NOT implement rails
      enforcement or conversion. — INHERITED(WO-0137 §Scope boundary; spec `04-auth-and-api.md` §3).

- [x] **D-R5b-3 ⚠ The staged corpus is a FLOOR, not the ceiling — R5b MUST additionally land the
      FULL reads-included route-introspection matrix.** The staged file's own docstring defers "The
      FULL reads-included matrix + paced-flood … to the joint WO-0102+0104 milestone", but **GAP-02
      is R5-owned** and spec `04 §1a` is normative and fail-closed. Split the deferred bundle: the
      **paced-flood** genuinely needs R6's durable refill/budget and stays deferred; the **matrix is
      pure auth classification and needs no rails**, so it lands here. R5b adds a parameterized test
      that introspects the **real mounted app's route table** and asserts, for {none, invalid,
      producer-key, operator-key} × every mounted route: required-present sensitive routes EXIST and
      behave; **`POST /api/session/close` is operator-only (a mutating command, not a read)**;
      auto-docs routes are ABSENT (disabled option) or present-and-operator-only, never public; and
      **any mounted route absent from the classification is a test FAILURE**.
      — TRACED(staged docstring `tests/test_signal_routes.py:6-8 @ staging`; threat model GAP-02
      `docs/THREAT_MODEL_SIGNAL_SEAT.md:112` + T-23 `:73`; spec `04-auth-and-api.md:73-108`).

- [x] **D-R5b-4 ⚠ REV-0027 F-1 must not recur — the approval-audit hole.** The archive middleware
      skipped operator enforcement on `path.startswith("/api/signals")`. That is correct ONLY for the
      producer `POST /api/signals`; it wrongly exempted the operator-only
      `POST /api/signals/{producer}/{signal}/approve|reject` AND never stamped
      `request.state.authenticated_actor`, so `get_actor` fell back to the caller-controlled `X-Actor`
      — making "who authorized a real order" **spoofable**. R5b therefore: (a) matches the producer
      exemption on the **exact route**, never a path prefix; (b) enforces operator auth on
      approve/reject; (c) **stamps the authenticated principal** on every authenticated request; and
      (d) `get_actor` **prefers the authenticated principal**, treating `X-Actor` as a subordinate
      audit label only. Required negative tests: a prefix-style bypass attempt on approve/reject is
      401/403, and an `X-Actor` header cannot override the recorded principal.
      — TRACED(archive `work/review/REV-0027/result.md:17-27 @ origin/archive/claude-wo-0001-install-checks-2x5ys8`;
      spec `04 §1` "Actor identity derives from the authenticated principal", `:45-46,:67-69`).

- [x] **D-R5b-5 Producer identity binding is server-side only (GAP-06).** `producer_id` derives from
      the presented key via the config map, server-side, always. Unknown key → **401 with NO event
      append** (unattributable). A body `producer_id` that mismatches the key-derived identity is
      rejected **before** any namespace accounting (dedupe/rate/budget/quarantine/audit keys are all
      keyed by the authenticated producer namespace).
      — TRACED(spec `04 §1` Rules `:53-56`; threat model GAP-06 `:116`; staged
      `test_identity_binding_mismatch_rejected` / `test_identity_binding_matching_ignored`).

- [x] **D-R5b-6 Body-blind auth ordering (A-4).** `POST /api/signals` MUST NOT declare a Pydantic
      body parameter — FastAPI would read the body for body-model routes **before** auth/rails
      dependencies can reject, defeating the normative ordering. The handler takes the raw `Request`;
      auth + rails run as dependencies with no body access; the handler then streams the body under a
      **64 KiB cap** and validates `SignalProposal` manually. The OpenAPI fragment documents the wire
      contract; the binding is manual.
      — TRACED(spec `04 §2` ingest body-handling constraint `:120-125`; staged
      `test_body_over_64kib_rejected`, `test_unparseable_body_is_400_no_event`).

- [x] **D-R5b-7 R5b-N1 — producer key map is an exact `dict` at the auth seam.** R5a validates the
      map as a `Mapping` container with exact-`str` keys/values. A directly-injected hostile custom
      `Mapping` could present `.items()` differently from the request-time `.get()`/`in` lookup that
      authenticates `X-Producer-Key`. R5b re-derives a trusted plain `dict` (or requires exact `dict`)
      at the auth seam, with a regression test for the *incorrect type acceptance* defect class.
      — INHERITED(REV-0041 `result.md` R5b-N1 + `result-addendum-01.md`).

- [x] **D-R5b-8 GAP-01 — operator enforcement and cockpit plumbing ship in the SAME change, and the
      plumbing must not clobber per-call headers.** Enforcement covers **every sensitive route,
      reads included** (positions/orders/sessions/watchlist/candidates/review/marketdata/signals-list/
      producers + all mutating commands). `cockpit/api_client.py::_request` (`:28`) is the single
      choke point and must inject `X-Operator-Key` from its env **merged with**, not replacing,
      per-call `headers=` — two existing call sites pass `headers={"X-Actor": actor}` (`:165`, `:178`)
      and a naive override would silently drop the audit label. Prove kill switch, manual flatten,
      session controls, and sensitive reads all remain usable for an operator with the configured key
      (no lockout window — invariant 11).
      — TRACED(`cockpit/api_client.py:28,165,178`; spec `04 §1` operator-enforcement bullet `:57-69`;
      threat model GAP-01 `:111` + T-22 `:72`).

- [x] **D-R5b-9 Import-boundary contract 5 in the same change.** Add `app.api.routes_signals` to
      contract 5 `source_modules`; the route reaches the backend **only** through the typed signal
      facade (never `app.store`/`app.events`, never the `get_store` dependency). Contract 5 is a
      **ratchet** (`unmatched_ignore_imports_alerting = error`, empty `ignore_imports`) — it may only
      tighten. Contract 6 (sell-side policy purity) must stay green.
      — TRACED(`.importlinter` contract-5 design note; spec `04 §2` `:112-118`).

- [x] **D-R5b-10 GAP-05 — producer text is hostile display text.** `thesis`/`provenance` render as
      **untrusted text only** — never executable/unsafe HTML or markdown in the cockpit; audit content
      preserved **verbatim**; validation/display errors must not leak credential material.
      — TRACED(threat model GAP-05 `:115` + T-12 `:62`).

- [x] **D-R5b-11 Flag stays OFF; R5b must not make the seat independently enable-able (GAP-03,
      D-2a).** Flag-off behavior stays byte-equivalent to today (routers not mounted → 404; existing
      localhost no-auth posture unchanged). The joint enablement gate stays R5+R6+R7.
      — INHERITED(D-2a joint enablement; threat model GAP-03 `:113`).

- [x] **D-R5b-12 Rails = the permissive fake via the test seam ONLY.** `PermissiveSignalRails`
      satisfies the rails-**presence** guard so routes can be tested without R6. It must remain
      unselectable from production config/environment (A-4), under the same explicit-in-process
      test-authority discipline REV-0041 established for the flag-on helper. Production selecting a
      permissive/stub rails must **refuse** rather than expose `POST /api/signals`.
      — TRACED(staged `tests/signal_seat_helpers.py:31-35 @ staging`; REV-0041 D2 outcome; GAP-03).

- [x] **D-R5b-13 Dual-store parity for facade reads.** The staged `test_signal_facade_reads.py` uses
      the `any_store` fixture (lazy TTL expiry on read, list reclassification/filtering, and the
      no-mutation-on-read property). Both in-memory and SQLite paths are mandatory.
      — TRACED(staged `test_signal_facade_reads.py` `any_store` async cases; CLAUDE.md dual-store rule).

- [x] **D-R5b-14 NAMED mid-session GATE before the operator-enforcement flip.** The producer/facade
      half is additive (new routes, flag-gated). The operator-enforcement half changes behavior on
      **every existing sensitive route** and carries the lockout risk (T-22). Stop after the
      producer/ingest half is green and report the mounted-route inventory + the planned
      classification **before** wiring enforcement. This is the one human checkpoint inside the
      session. — TRACED(`.ai-os/core/18` M1 named-gate rule; threat model T-22 `:72`).

**Operator override to consider (not pre-checked):** split R5b into two WOs — R5b-1 (facade +
producer route) and R5b-2 (operator flip + matrix + cockpit). Not pre-selected because the staged
acceptance corpus is a **single file spanning both halves**, and fragmenting it mid-file invites the
partial-corpus confusion R5a hit. D-R5b-14's named GATE buys the same human checkpoint without
splitting the contract. Flip this if you prefer two smaller sessions.

---

## M2 — Lifecycle totality

**Artifact A — the authenticated principal (per-request, non-durable).**

| Edge | Driver | Anchor / requirement |
|---|---|---|
| birth | operator/producer auth dependency or middleware, on credential validation | must stamp `request.state.authenticated_actor` (or equivalent) — the F-1 miss |
| read | `get_actor` and every route that writes an actor into an event payload | principal **wins**; `X-Actor` is a subordinate label |
| terminal (authorized) | response returned; state discarded with the request scope | no cross-request carryover |
| terminal (rejected) | 401 (no/unknown credential) or 403 (wrong role) **before** handler body | no event append on 401 (unattributable) |

Precondition proof required: no route may read an actor for an event payload on a path where the
principal was never stamped. A route that can reach an event append without a stamped principal is
an F-1 recurrence and is not ratifiable.

**Artifact B — signal record states reachable AT INGEST** (the record/lifecycle itself landed in R4;
R5b must drive only sanctioned edges):

| Ingest outcome | State written | Rule |
|---|---|---|
| valid, fresh | `RECEIVED` (201) | the only "live" ingest edge |
| validation failure | `SIGNAL_QUARANTINED` (422) | recorded, not hidden |
| stale/TTL at ingest | recorded terminal (expired) at ingest | freshness quarantine, not lax coercion |
| identical replay (same `payload_hash`) | **no new state** (200) | idempotent |
| same `(producer_id, signal_id)`, different payload | **no state change** (409) | duplicate-conflict |
| unparseable body | **no event** (400) | pre-validation reject |
| unknown producer key | **no event** (401) | unattributable |
| producer quarantined | boundary reject (403), coalesced audit | R6 owns the *opener*; R5b honors the state |
| over ceiling/rate | boundary reject (429), coalesced audit | **R6 enforces**; R5b wires the seam only |

— TRACED(spec `04 §2` response table `:127-162`; staged quarantine/replay/conflict cases).

---

## M3 — Consumer inventory + control-action sweep

| Consumer of what R5b writes/changes | Class | Control-action finding |
|---|---|---|
| `get_actor` + every event-payload actor field | **affected** | (1) *needed guard skipped*: if the principal isn't stamped, audit silently degrades to caller-controlled `X-Actor` → **F-1 recurrence**. D-R5b-4. |
| `cockpit/api_client.py` call sites passing `headers={"X-Actor": …}` (`:165`,`:178`) | **affected** | (2) *action worsens safety*: replacing rather than merging headers drops the audit label. D-R5b-8. |
| Cockpit kill-switch / flatten / session controls (invariant 11) | **affected** | (3) *wrong order*: if enforcement lands before plumbing, the operator is locked out of the kill switch. Same-change requirement. D-R5b-8. |
| Every existing mounted sensitive route | **affected** | (1): a route omitted from the matrix ships unauthenticated. Unclassified route ⇒ test FAILURE. D-R5b-3. |
| `POST /api/session/close` | **affected** | (1): mis-classified as a read, it would expire candidates / cancel CREATED orders / close the session unauthenticated. Operator-only. D-R5b-3. |
| `/openapi.json`, `/docs`, `/redoc`, `/docs/oauth2-redirect` | **affected** | (1): schema enumeration. Disabled under the flag, or operator-only; never public. D-R5b-3. |
| Future R6/R7 routes | **unknown → resolved** | (4) *applied too long / stopped too soon*: the matrix must fail on any **later** unclassified route, so R6/R7 cannot ship one unauthenticated. D-R5b-3. |
| Producer-key map lookup at the auth seam | **affected** | (1): a hostile `Mapping` diverging between `.items()` validation and `.get()` authentication. D-R5b-7. |
| Existing test suite + `harness/bootstrap.py:117` (`pytest --collect-only` imports `app.main` flag-off) | **unaffected (must prove)** | Flag-off must stay byte-equivalent; existing localhost no-auth tests must not need edits. D-R5b-11. |
| `.importlinter` contracts 5 & 6 | **affected** | Ratchet: contract 5 gains `routes_signals`; a direct route→store edge fails the build. D-R5b-9. |
| Cockpit signal panel rendering `thesis`/`provenance` | **affected** | (2): rendering producer text as HTML/markdown lets a producer trick the operator into approving. Untrusted text only. D-R5b-10. |

---

## M4a — Prospective-hindsight brief (this design *already failed*; how?)

1. **"The operator couldn't hit the kill switch."** Enforcement flipped; cockpit sent no key → 401 on
   every control. → D-R5b-8 (same-change plumbing + usability proof).
2. **"The approval audit named the wrong actor."** `/api/signals` prefix-skip left approve/reject
   unstamped; `get_actor` fell back to `X-Actor`. → D-R5b-4 (exact-route exemption + principal
   precedence + negative tests).
3. **"A later route shipped unauthenticated."** R6 added a route nobody classified. → D-R5b-3
   (unclassified ⇒ FAILURE).
4. **"Someone closed the session without a credential."** `POST /api/session/close` classified as a
   read. → D-R5b-3.
5. **"A producer enumerated our positions."** A sensitive **read** wasn't covered because enforcement
   only guarded mutations. → D-R5b-8 (reads included).
6. **"An unauthenticated caller made us parse a 10 MB body."** A Pydantic body param read the body
   before auth. → D-R5b-6 (raw `Request` + 64 KiB cap).
7. **"The operator approved a spoofed thesis."** Producer text rendered as active markup. → D-R5b-10.
8. **"The audit label vanished from every cockpit command."** Header injection replaced `X-Actor`. →
   D-R5b-8.
9. **"The seat went live without real rails."** A permissive fake was selectable in production. →
   D-R5b-12 + GAP-03.
10. **"Ingest attributed events to an unknown key."** An event was appended before identity resolved.
    → D-R5b-5 (401, no event).

All ten resolve to a `TRACED` decision line or the named D-R5b-14 gate. **M4b must attempt to refute
this block from code before ratification** (see the kickoff's dispatch note; findings fold back here).

---

## Required behavior (Fable v3)

- [ ] **GATE** (`fable_gate`): restate goal / scope / done-when / blast-radius before building.
- [ ] **Corpus red-first:** import the staged R5b slices; prove RED before implementing.
- [ ] **Typed signal facade** (`StoreBackedSignalFacade` + protocols mirroring the existing facade
      command/query split) — turn `test_signal_facade_reads.py` green on **both** stores.
- [ ] **`app/api/routes_signals.py`** — producer ingest (body-blind, 64 KiB, manual validation),
      operator list/approve/reject stubs per spec §2, producers list/release seam.
- [ ] **`app/api/deps.py`** auth dependencies + operator-enforcement (exact-route producer exemption,
      principal stamping, 401/403 distinction).
- [ ] **`get_actor` precedence** — authenticated principal over `X-Actor`, with negative tests.
- [ ] **FULL reads-included mounted-route authorization matrix** (D-R5b-3) incl. session-close and
      auto-docs handling; unclassified route ⇒ failure.
- [ ] **Cockpit plumbing** — `_request` merges `X-Operator-Key` without clobbering per-call headers;
      operator usability proof for kill switch / flatten / session / reads.
- [ ] **`.importlinter` contract-5** `routes_signals` line, same change; contracts 5 & 6 green.
- [ ] **Flag-off non-regression** — routers absent (404), existing tests unmodified,
      `harness/bootstrap.py` green.
- [ ] **FIX blocks** with root cause for every defect; evidence pasted fresh.

## Gate battery (all fresh, pasted)

`ruff check .` · `ruff format --check` (R5b-owned files; the 10 inherited baseline files stay
grandfathered) · `mypy app/` · `lint-imports` · the R5b corpus + full suite · `python -m pytest -q
tests/r2_conformance_oracle.py` (CI invocation) · `pytest -q tests/test_wo0113_repair_scaling.py` ·
`python harness/bootstrap.py`.

## Stop conditions

Stop and report — do not self-authorize — on: any accepted-text conflict (spec/ADR vs staged corpus)
beyond D-R5b-3's recorded resolution; any need to weaken a staged assertion; a required staged-test
edit beyond the authorized set; any change that would make the flag independently enable-able; any
schema/migration or event-log truth change; a P0-equivalent hole in accepted text.

## Close-out expectations

Human-gated surface ⇒ **REV-0042 packet required**; the review gate clears only on a dispositioned
`ACCEPT`/`ACCEPT-WITH-CHANGES`. Close-out ships in the finishing commit: status flip, disposition
`[RESULT_SUMMARY_KEPT, PKL_UPDATED]` (signal-seat PKL R5b changelog), `work/ledger.jsonl` line, file
move out of `work/active/`, plus `check_work_order_disposition.py` + `check_ledger.py` green.
D-2a unchanged: the flag flips only when R5b **and** R6 **and** R7 have closed.
