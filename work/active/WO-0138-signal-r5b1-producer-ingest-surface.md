---
type: Work Order
title: "Signal Seat R5b-1 — producer ingest surface (typed signal facade + POST /api/signals + producer-key auth)"
status: REVIEW
work_order_id: WO-0138
wave: signal-seat reconciliation ladder, step R5 (split; R5b-1 = producer ingest surface)
model_tier: strong (LOCAL Codex — human-gated auth surface)
predecessors: [WO-0134 (R4 model+store), WO-0137 (R5a construction-time foundation — MUST be merged first), WO-0136 (threat model)]
successors: [WO-0139 (R5b-2 operator enforcement + route matrix + cockpit), R6 WO-0104 (rails), R7 (conversion)]
review: "REV-0042 required (human-gated surface: producer authentication + ingest event truth)"
wargame: "FULL per .ai-os/core/18 — M1 + M2 + M3 + M4a + M4b COMPLETE (rev-2 applied 12 M4b findings)"
---

# WO-0138 — Signal Seat R5b-1: the producer ingest surface

> **rev-2 (2026-07-25).** rev-1 scoped all of R5b as one WO. An M4b refutation pass **refuted 8 of 14
> decision lines** and produced two P0 findings, both living in the operator-enforcement half. The
> planning seat verified every blocking finding directly against code before acting. R5b is now
> **split**, and this WO is the **additive producer half** only. See §M4b for what changed and why.

R5a made `create_app` **refuse to construct** without a sanctioned launch capability, valid config,
and conforming rails. **R5b-1 adds the first authenticated external input path**: the typed signal
facade and `POST /api/signals`, authenticated by producer key, with identity bound server-side.

**R5b-1 is purely additive** — one new flag-gated route plus a new facade. It changes the behavior of
**zero** existing routes. Everything that changes existing-route behavior is **WO-0139 (R5b-2)**.

## Scope boundary

> **rev-3 (2026-07-25) — re-scoped to INGEST-ONLY** after Codex's NEEDS-INPUT stop, per
> `work/queue/SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md`. rev-2 deferred `GET /api/signals` to R5b-2 but
> kept the **read-side** facade corpus here; that corpus depends on `effective_signal_status`, which
> WO-0139 already owns, so the read half was split across two rungs. It is now reunited in R5b-2.

**IN (R5b-1) — the ingest write path only:**
- `app/facade/signal_*` — the typed `StoreBackedSignalFacade` (**absent on master**), **write/ingest
  surface only** + protocols mirroring the existing facade command/query split.
- `app/api/routes_signals.py` — **`POST /api/signals` only** (producer-only).
- `app/api/deps.py` — the **producer-key** authentication dependency + server-side identity binding,
  **plus** recognizing the operator credential as a distinct type **solely** to return the wrong-role
  **403 on `POST /api/signals`** (D1-D3 authorization; spec `04 §1`). No operator enforcement
  anywhere else, no middleware, no principal stamping.
- **`app/api/schemas.py` — signal DTOs ONLY** (`SignalProposal` + any ingest response view).
  `01-schema.md:6` places `SignalProposal` there; rev-2's IN list omitted the path, which made the
  contract unbuildable. Do not touch existing schemas; follow the `ResponseSafeFloat` conventions.
- Ingest-time **dead-on-arrival** expiry (`expires_at ≤ received_at` ⇒ `SIGNAL_EXPIRED`,
  `detected_by:"ingest"`) — a write on the write path, unaffected by the D5 read question.
- `.importlinter` contract-5 `routes_signals` line (same change).
- The staged **ingest** subset of `test_signal_routes.py` — only cases whose assertions terminate at
  the **HTTP response or the event log**.

**OUT — moved to WO-0139 (R5b-2) by the rev-3 re-scope:** the **entire**
`tests/test_signal_facade_reads.py` corpus · facade `list_signals`/`get_signal` ·
`effective_signal_status` · the injected read clock · **lazy-expiry semantics and the D5 event-log-truth
decision** · any ingest test that reads back through `GET /api/signals` (e.g. staged `:231`).
**Do not rewrite such an assertion to avoid the GET — moving it is correct; rewriting it is
test-weakening.**

**OUT — already deferred to WO-0139:** operator-key enforcement on any route other than the producer
403 above, principal stamping, `get_actor` precedence, the actor migration of the two recovery routes,
`GET /api/signals`, `/api/producers`, the mounted-route authorization matrix, auto-docs handling,
cockpit `X-Operator-Key` plumbing, `.env.example` credential documentation.

**OUT — later rungs:** R6 (WO-0104) real rails: ceiling/durable-budget/quarantine-opener/release and
the paced-flood proof. R7: approve/reject routes + atomic conversion (see D-R5b1-3). Schema/migration;
event-log truth changes; flag enablement.

**⚠ R5b-1 alone does NOT satisfy GAP-01 or GAP-02.** Under the flag, sensitive reads remain
unprotected until R5b-2 lands. This is safe only because **the flag stays OFF**: D-2a now requires
**R5b-1 + R5b-2 + R6 + R7** to close before any enablement. R5b-1 must never present itself as
completing the auth surface.

## GAP ownership

R5a closed **GAP-04**. **R5b-1 owns GAP-06** (producer identity binding) and the API-side half of
**GAP-05** (hostile producer text). **R5b-2 owns GAP-01 + GAP-02** and the cockpit half of GAP-05.
GAP-03 is joint-enablement. GAP-08 → R6, GAP-09 → R7, GAP-07 → ADR-013.

---

## M1 — Assumption ledger / decision block (rev-2, post-M4b)

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`;
no `ASSUMED` line is pre-checked (`.ai-os/core/18`).

- [x] **D-R5b1-1 HARD predecessor gate — R5a must be MERGED first.** R5a is **not** on master at
      drafting time: `git merge-base --is-ancestor origin/codex/signal-r5a-foundation origin/master`
      → NO, and `app/launch_guard.py`, `app/__main__.py`, `app/facade/signal_rails.py`, and every
      `signal_*` config field are absent from master. **Verify before starting:**
      `git ls-tree master app/launch_guard.py` must return a blob, else STOP.
      Branch `codex/signal-r5b1-producer-ingest` from the merged master.
      — TRACED(M4b F10, re-verified by the planning seat).

- [x] **D-R5b1-2 Corpus, and it is INCOMPLETE — completing it is authorized.** *(rev-3: import the
      **ingest subset ONLY**; `tests/test_signal_facade_reads.py` moved to R5b-2 in full. Where the
      original repair list said "6 sites", the authorized repair is a **PREDICATE — every
      `ingest_signal(` call site missing the required `received_at=` kwarg** — because the live count
      is 8, not 6. Counting was the defect; do not encode a number.)* Pull from
      `origin/codex/signal-tests-staging`: the **producer/ingest subset** of
      `tests/test_signal_routes.py`. The staged
      `test_signal_routes.py` is **truncated at byte 14628, ending mid-comment (`# The forged X-Ac`)**
      inside `test_operator_command_audit_actor_is_principal_not_forged_x_actor` — it parses,
      collects, and **PASSES without asserting anything about the actor**. That test is R5b-2's
      (operator audit), so R5b-1 does **not** import it; R5b-1 imports only the producer/ingest cases
      and must **not** treat the truncated file as a trustworthy floor. Authorized mechanical repairs
      to the imported cases (additions, never weakenings):
      1. add the required `received_at=` kwarg to `store.ingest_signal(...)` calls (6 sites) —
         required keyword-only on master (`app/store/base.py:1332`);
      2. correct `SIGNAL_REPLAYED` to import from `app.store.core` (`:5587`), not `app.models`.
      — TRACED(M4b F4/F5, both re-verified: byte count + EOF text; `base.py:1332`; `core.py:5587`).

- [x] **D-R5b1-3 Approve/reject are NOT R5b's — they are R7's.** Accepted lifecycle rule **A2**:
      "`SIGNAL_APPROVED` is written **only if** the conversion succeeds in the same store operation…
      **There is no 'approved-but-unconverted' state**", and **A1** makes APPROVED a latching
      terminal. R7 owns conversion. So any R5b approve stub either violates A2 (writing a terminal
      R7 could never convert) or returns an undocumented status. Spec `04:71` independently assigns
      the approval/release-route negative tests to **WO-0103/0104, not WO-0102**. Therefore R5b-1
      mounts **`POST /api/signals` only**; approve/reject are mounted by R7 and `/api/producers` by
      R6/R5b-2. The R5b-2 matrix's "unclassified route ⇒ FAILURE" rule then **forces** R7/R6 to
      classify them when they mount them — the ratchet doing its job.
      — TRACED(`docs/spec/signal-seat/02-lifecycle.md:18-26`; `04-auth-and-api.md:71`; M4b F3).

- [x] **D-R5b1-4 Producer identity is server-side only (GAP-06).** `producer_id` derives from the
      presented key via the config map, server-side, always. Unknown key → **401 with NO event
      append** (unattributable). A body `producer_id` mismatching the key-derived identity is rejected
      **before** any namespace accounting; dedupe / rate / budget / quarantine / audit keys are all
      keyed by the authenticated producer namespace.
      — TRACED(spec `04 §1` Rules `:53-56`; threat model GAP-06 `:116`; archive
      `app/api/deps.py:140-176 resolve_producer_id`; staged `test_identity_binding_*`).

- [x] **D-R5b1-5 Body-blind auth ordering (A-4) — empirically verified, not assumed.** The handler
      MUST NOT declare a Pydantic body parameter: for body-model routes FastAPI reads the body
      **before** dependencies can reject. Measured on the pinned versions (fastapi 0.139.0 /
      starlette 1.3.1): a body-model route's call sequence is `[BODY_READ, STREAM, BODY_READ, AUTH]`
      while a raw-`Request` route's is `[AUTH]` only. So: raw `Request`, auth as a dependency with no
      body access, then stream the body under a **64 KiB cap** and validate `SignalProposal`
      manually.
      — TRACED(spec `04 §2:120-125`; M4b F-verification of `fastapi/routing.py::get_request_handler`).

- [x] **D-R5b1-6 The 64 KiB cap returns 413, and that is a RECORDED spec conflict.** The staged
      `test_body_over_64kib_rejected` asserts **413**; the accepted spec `04 §2` response table
      (`:132-141`) documents 201/200/400/401/403/409/422/429 and **not 413**. Resolution: keep 413
      (correct HTTP semantics, and the corpus is right) and **add it to the spec §2 fragment in the
      same change**, flagged for REV-0042 as a spec amendment. Do not silently diverge, and do not
      weaken the test to a documented status.
      — TRACED(spec `04 §2:127-141`; staged test; M4b F7).

- [x] **D-R5b1-7 R5b-N1 is ALREADY CLOSED by R5a — reduced to a regression pin.** REV-0041 recorded a
      carry-forward requiring R5b to re-derive a trusted `dict` at the auth seam, reasoning that a
      hostile custom `Mapping` could diverge between `.items()` (validation) and `.get()`/`in`
      (authentication). **That premise is stale:** R5a's `Settings.__post_init__` runs on **every**
      construction — including direct injection — and for any `Mapping` does
      `MappingProxyType(dict(self.signal_producer_keys))`, i.e. copies into a plain `dict` before
      wrapping; `validate_signal_seat_settings` rejects any non-`Mapping`. No hostile `Mapping`
      survives to request time. R5b-1's obligation is therefore only a **regression pin** asserting
      the normalized container type at the request-time lookup (defect class *incorrect type
      acceptance*) — not a re-derivation.
      — TRACED(R5a `app/config.py:301-317` + `:449`, re-verified by the planning seat; supersedes
      REV-0041 `result.md` R5b-N1).

- [x] **D-R5b1-8 GAP-05, API half only.** `thesis`/`provenance` are hostile text: preserved
      **verbatim** for audit, never interpreted; validation and error paths must not echo credential
      material. The **cockpit** rendering half is deferred with the signal panel — no cockpit signal
      panel exists at R5b (spec `04 §3` assigns it to WO-0103/0104), so there is nothing to harden
      here yet; R5b-2/R7 owns it.
      — TRACED(threat model GAP-05 `:115`; spec `04 §3:168-174`; M4b F-note on D-R5b-10).

- [x] **D-R5b1-9 Import-boundary contract 5, same change.** Add `app.api.routes_signals` to contract-5
      `source_modules`; the route reaches the backend **only** through the typed signal facade (never
      `app.store`/`app.events`, never the `get_store` dependency). Contract 5 is a ratchet
      (`unmatched_ignore_imports_alerting = error`) and its `ignore_imports` is **OMITTED, not
      empty** — writing `ignore_imports =` breaks the build. Contract 6 (sell-side purity) stays green.
      — TRACED(`.importlinter:133-138,165-169`; spec `04 §2:112-118`; M4b F12).

- [x] **D-R5b1-10 Dual-store parity, and 6 staged cases are R4 pins not R5b criteria.** The staged
      `test_signal_facade_reads.py` uses the `any_store` fixture (real `["memory","sqlite"]`
      parameterization, `tests/conftest.py:28-49`) for lazy TTL expiry on read, list
      reclassification/filtering, and the no-mutation-on-read property — all mandatory on **both**
      stores. Six further cases in that file (`…nulls_out_of_domain_advisory…`,
      `…normalizes_symbol_and_validates_direction`, `…hash_uses_normalized_symbol…`,
      `…escapes_surrogate_text…`, `…rejects_non_ascii_symbol…`,
      `test_creation_event_carries_top_level_identity`) exercise the **R4 store**, not the R5b facade:
      carry them forward as R4 regression pins and do **not** treat an R4 store failure as an R5b
      defect. — TRACED(M4b F5; `conftest.py:28-49`).

- [x] **D-R5b1-11 Flag stays OFF; flag-off byte-equivalent (GAP-03, D-2a).** Routers not mounted when
      off (404); the existing localhost no-auth posture is unchanged; **no existing test may need
      editing**; `harness/bootstrap.py` (`:117` `pytest --collect-only` imports `app.main` flag-off)
      stays green. R5b-1 must not make the seat independently enable-able. **Specifically:** if the
      archive's `get_actor` variant is ported at all, its unconditional non-printable-character
      stripping of `X-Actor` is a **flag-independent behavior change** — either scope it under the
      flag or leave `get_actor` untouched (preferred in R5b-1; it is R5b-2's file).
      — INHERITED(D-2a) + TRACED(M4b build-hazard 6; `harness/bootstrap.py:117`).

- [x] **D-R5b1-12 Rails = the permissive fake via the test seam ONLY.** `PermissiveSignalRails`
      satisfies the rails-**presence** guard so the ingest route is testable without R6. It stays
      unselectable from production config/environment (A-4), under the explicit in-process
      test-authority discipline REV-0041 established. Production selecting a permissive/stub rails
      must **refuse**, never expose `POST /api/signals`. Rails **enforcement** (429/ceiling/budget) is
      R6's; R5b-1 wires the seam and honors an existing quarantine state (403) only.
      — TRACED(staged `tests/signal_seat_helpers.py:31-35`; R5a `app/main.py:105-110`
      `is_conforming_rails`; GAP-03).

---

## M2 — Lifecycle totality (R5b-1 scope)

**Ingest-reachable signal outcomes** (the record + transitions landed in R4; R5b-1 must drive only
these sanctioned edges):

| Ingest outcome | State written | Rule |
|---|---|---|
| valid, fresh | `RECEIVED` (201) | the only "live" ingest edge |
| validation failure | `SIGNAL_QUARANTINED` (422) | recorded, never hidden |
| stale / TTL at ingest | recorded terminal (expired) at ingest | freshness quarantine, not lax coercion |
| identical replay (same `payload_hash`) | **no new state** (200) | idempotent |
| same `(producer_id, signal_id)`, different payload | **no state change** (409) | duplicate-conflict, audit-only event |
| unparseable body | **no event** (400) | pre-validation reject |
| body > 64 KiB | **no event** (413) | cap enforced during streaming, before full read |
| unknown producer key | **no event** (401) | unattributable — the D-R5b1-4 precondition |
| producer already quarantined | boundary reject (403), coalesced audit | R6 owns the opener; R5b-1 honors the state |

**Precondition proof required:** no ingest path may append an event before the producer identity is
resolved from the key. (Note: rev-1's principal-lifecycle trace moves to WO-0139 with operator auth.)

---

## M3 — Consumer inventory (R5b-1 scope)

| Consumer | Class | Control-action finding |
|---|---|---|
| Signal store `ingest_signal` (`app/store/base.py:1332`, memory + sqlite) | **affected** | `received_at` is required keyword-only — omitting it is a `TypeError`, not a soft default. D-R5b1-2. |
| `.importlinter` contracts 5 & 6 | **affected** | Ratchet: a direct route→store edge fails the build. D-R5b1-9. |
| Producer-key map lookup at the auth seam | **affected** | Already normalized by R5a's `__post_init__`; pin it. D-R5b1-7. |
| Existing 34 `/api` routes | **unaffected (must prove)** | R5b-1 mounts one new route and changes no existing behavior. Flag-off 404. D-R5b1-11. |
| `harness/bootstrap.py:117` + the full existing suite | **unaffected (must prove)** | No existing test may need editing. D-R5b1-11. |
| `get_actor` and every actor-consuming route | **NOT TOUCHED in R5b-1** | Deliberately deferred — see the WO-0139 register (the two recovery routes are an F-1-class hole). |
| Cockpit | **unaffected** | No cockpit change in R5b-1; the panel and plumbing are WO-0139/R7. |

---

## M4a — Prospective hindsight (R5b-1 scope; "it shipped and caused an incident")

1. *"An unauthenticated caller made us parse a huge body."* → D-R5b1-5/6 (raw `Request`, 64 KiB, 413).
2. *"An event was attributed to an unknown key."* → D-R5b1-4 (401, no event append).
3. *"A producer spoofed another producer's namespace via the body."* → D-R5b1-4 (server-side binding,
   mismatch rejected before accounting).
4. *"The route reached the store directly and bypassed the facade."* → D-R5b1-9 (contract-5 ratchet).
5. *"A replay created a second record."* / *"A changed payload mutated the original."* → M2 replay /
   conflict edges (200 / 409, no mutation).
6. *"Beta broke because flag-off changed."* → D-R5b1-11 (byte-equivalence; no existing test edits).
7. *"The seat served ingest with a permissive fake rails."* → D-R5b1-12.
8. *"We shipped an approved-but-unconverted signal R7 could never convert."* → D-R5b1-3 (approve is
   not R5b's at all).
9. *"The corpus was green but proved nothing."* → D-R5b1-2 (truncated file not imported as a floor).

---

## §M4b — Refutation record (what changed in rev-2 and why)

A fresh-context M4b agent attacked rev-1's 14-line block; the planning seat **independently verified
every blocking finding against code** before acting. Two P0s, both in the operator-enforcement half —
which is why R5b is now split.

| # | Finding | Verified | Action |
|---|---|---|---|
| **F1 (P0)** | The route-introspection matrix would be **fail-OPEN**. On pinned fastapi 0.139.0/starlette 1.3.1, `app.routes` = 4 doc `Route`s + **8 `_IncludedRouter` with `path is None`**; naive introspection discovers **0** `/api` routes, so "unclassified ⇒ FAILURE" passes vacuously over an empty set. The archive matrix test was authored against a flat pre-1.0 `app.routes` — the classic "true in the past, not now" case. | **YES** — planning seat measured: `{'Route': 4, '_IncludedRouter': 8}`, 8 with `path is None`, 0 naive `/api` paths | → **WO-0139**, with the corrected design + the measured inventory (below) |
| **F2 (P0/P1)** | `app/api/routes_trading.py:220` (`POST /api/order-recoveries/{id}/fills` — ingests a canonical **fill**, invariant 9) and `:246` (`…/reconcile` — the human **attestation**) take `actor: str = Header(..., alias="X-Actor")` and **never call `get_actor`**, so principal stamping + `get_actor` precedence would leave the two most audit-critical actors caller-controlled. rev-1's M2 asserted the **wrong precondition**. | **YES** — verified both signatures; `get_actor` call count in that range = **0** | → **WO-0139**; M2's read edge must enumerate actor-consuming routes **by grep, not by `get_actor` call sites** |
| **F3 (P1)** | Approve cannot be a stub: rule **A2** forbids approved-but-unconverted and **A1** makes APPROVED latching; spec `04:71` assigns approval-route negative tests to WO-0103/0104. | **YES** — `02-lifecycle.md:18-26`, `04:71` | **D-R5b1-3**: approve/reject dropped from R5b entirely → R7 |
| **F4 (P1)** | Staged `test_signal_routes.py` is **truncated at the crown-jewel assertion** → false green on the unforgeable-audit invariant. | **YES** — 14628 bytes, EOF at `# The forged X-Ac` | **D-R5b1-2**: not a trustworthy floor; that test is R5b-2's and must be completed there |
| **F5 (P1)** | Staged facade-reads **does not run**: `ingest_signal` called without required `received_at`; `SIGNAL_REPLAYED` imported from the wrong module; 6 cases are R4 store tests. | **YES** — `base.py:1332`; `core.py:5587` | **D-R5b1-2/-10**: two authorized mechanical repairs + R4-pin classification |
| **F6 (P2)** | **R5b-N1's premise is stale** — R5a's `__post_init__` already normalizes any `Mapping` to a plain-dict-backed proxy on every construction. REV-0041 reasoned only about `load_settings()`. | **YES** — R5a `config.py:301-317`, `:449` | **D-R5b1-7**: reduced to a regression pin; supersedes the REV-0041 carry-forward |
| **F7 (P2)** | `413` is asserted by the corpus but absent from the accepted spec response table — an unrecorded conflict. | **YES** — `04 §2:132-141` | **D-R5b1-6**: conflict recorded; spec amendment in the same change, flagged for REV-0042 |
| **F8 (P2)** | rev-1's route enumeration omitted `/api/events` (**the audit event log**), `/api/protection`, `/api/sell-intents`, `/api/reconciliation`, `/api/operator/orders`; and the claimed "silent `X-Actor` drop" is actually a loud **422** (both cited call sites make the header required). | **YES** — `routes_trading.py:329` for `/api/events`; measured 34-route table | → **WO-0139** register, with the measured inventory and the corrected failure mode |
| **F9 (P2)** | The matrix as specified would **execute destructive commands** (kill-switch, flatten, emergency-reduce, session/close) and be order-dependent; "behave" was undefined. | **YES** — all four are in the measured table | → **WO-0139**: "behave" = **auth outcome only**, fresh app per case |
| **F10 (P3)** | rev-1's "helpers already on master post-R5a" was **false at drafting** — R5a is unmerged. | **YES** | **D-R5b1-1**: hard predecessor gate |
| **F11 (P3)** | `.env.example` documents **none** of the credential fields, though the repo primer makes it the complete config template — GAP-01's "operator with the configured key" has no documented way to configure it. | Accepted | → **WO-0139** close-out |
| **F12 (P3)** | contract-5 `ignore_imports` is **omitted**, not empty; writing `ignore_imports =` breaks the build. | **YES** — `.importlinter:165-169` | **D-R5b1-9** wording |

**Lines that survived M4b unchanged:** rev-1 D-R5b-2 (scope), -11 (flag off), -12 (rails fake), -14
(named gate → superseded by the split). D-R5b1-5's core claim was **strengthened** — M4b verified the
auth-before-body ordering empirically against the pinned versions rather than accepting it.

**The split decision, reversed on evidence.** rev-1 declined the R5b-1/R5b-2 split, reasoning that the
staged corpus is one file spanning both halves and fragmenting it invites partial-corpus confusion.
**That reason no longer holds:** the file is truncated and requires authorized completion anyway (F4),
so it was never a clean atomic floor. Both P0s (F1, F2) and F3/F8/F9/F11 live in the operator half,
which needs its own M2/M3 for a 34-route matrix and two event-truth actor migrations. Splitting is now
the better-supported choice.

---

## ⚠ BUILD HAZARDS (verified — these bite a verbatim archive port)

1. **`build_flag_on_app` signature changed under the corpus's feet.** R5a added a **required**
   keyword-only `test_authority` and raises unless it is the **private** module sentinel
   `_IN_PROCESS_TEST_AUTHORITY`. Staged `test_signal_routes.py:53` and `:360` call it **without** it
   → both fail. Every ported call site must import the private sentinel.
2. **Archive imports absent on master:** archive `app/api/deps.py:15` is
   `from app.facade.signals import SignalFacade, StoreBackedSignalFacade` — **that module is what you
   are building**. `effective_signal_status` exists **nowhere** in the repo (R5b must author it);
   `classify_signal_freshness` is at `app/store/core.py:5806`, not `app.models`; `SIGNAL_REPLAYED` is
   at `app/store/core.py:5587`.
3. **`received_at` is required keyword-only** (`app/store/base.py:1332`) — the staged corpus omits it
   in 6 places.
4. **`root_path` / middleware path divergence (for WO-0139, noted here so it is not lost):** starlette
   1.3.1 routes on `get_route_path(scope)`, which **strips `root_path`**, while `request.url.path`
   does not. Under `tailnet_serve` with a path prefix, an exact-string exemption on `request.url.path`
   stops matching what the router matched. Fail-closed in direction (producer gets 401) but a real
   correctness break — middleware must use the same helper the router uses.
5. **Cockpit must not import `app.config`** for an env-var name — contract 2 forbids `cockpit → app`;
   hardcode the string (WO-0139).

## Measured mounted-route inventory (planning seat, flattened + openapi cross-checked)

**38 operations = 34 `/api` + 4 auto-docs.** The flattener (recursing `_IncludedRouter.original_router`
and `Mount.routes`) discovers **34** `/api` operations, exactly matching `app.openapi()`'s 34 — the
cross-check WO-0139's matrix must assert, with a **positive lower bound** so a discovery regression
turns the test RED instead of silently green.

Sensitive reads that rev-1's enumeration missed: `GET /api/events` (**audit event log**),
`GET /api/protection`, `GET /api/sell-intents`, `GET /api/reconciliation`, `GET /api/operator/orders`.
Destructive commands the matrix must never actually execute: `POST /api/session/close`,
`POST /api/controls/kill-switch`, `POST /api/positions/{symbol}/emergency-reduce`,
`POST /api/positions/{symbol}/flatten`.

---

## Required behavior (Fable v3)

- [ ] **GATE** (`fable_gate`): restate goal / scope / done-when / blast-radius before building.
- [ ] **Predecessor check** — R5a merged (D-R5b1-1), else STOP.
- [ ] **Corpus red-first** — import the producer/ingest + facade-read cases with the two authorized
      mechanical repairs; prove RED before implementing.
- [ ] **Typed signal facade** (`StoreBackedSignalFacade` + protocols) — `test_signal_facade_reads.py`
      green on **both** stores.
- [ ] **`POST /api/signals`** — body-blind (raw `Request`), producer-key auth dependency, server-side
      identity binding, 64 KiB cap → 413, manual `SignalProposal` validation, the full M2 outcome table.
- [ ] **Spec §2 amendment** adding 413, flagged for REV-0042 (D-R5b1-6).
- [ ] **Regression pin** for the normalized producer-map container type at the auth seam (D-R5b1-7).
- [ ] **`.importlinter` contract-5** `routes_signals` line, same change; contracts 5 & 6 green.
- [ ] **Flag-off non-regression** — route absent (404), zero existing-test edits, bootstrap green.
- [ ] **FIX blocks** with root cause for every defect; fresh pasted evidence.

## Gate battery (fresh, pasted)

`ruff check .` · `ruff format --check` (R5b-1-owned files; the 10 inherited baseline files stay
grandfathered) · `mypy app/` · `lint-imports` · the R5b-1 corpus + full suite · `python -m pytest -q
tests/r2_conformance_oracle.py` (CI invocation) · `pytest -q tests/test_wo0113_repair_scaling.py` ·
`python harness/bootstrap.py`.

## Stop conditions

Stop and report — never self-authorize — on: any accepted-text conflict beyond D-R5b1-6's recorded
413 resolution; any need to weaken a staged assertion; a staged-test edit beyond the two authorized
mechanical repairs; anything that would make the flag independently enable-able; any operator-auth,
`get_actor`, cockpit, or existing-route behavior change (that is **WO-0139**); any schema/migration or
event-log truth change; a P0-equivalent hole in accepted text.

## Close-out expectations

Human-gated surface ⇒ **REV-0042 packet required**; the gate clears only on a dispositioned
`ACCEPT`/`ACCEPT-WITH-CHANGES`. Close-out ships in the finishing commit: status flip, disposition
`[RESULT_SUMMARY_KEPT, PKL_UPDATED]` (signal-seat PKL R5b-1 changelog), a `work/ledger.jsonl` line,
file move out of `work/active/`, `check_work_order_disposition.py` + `check_ledger.py` green. The
REV-0042 request must carry the spec-§2-413 amendment for explicit review.

---

## WO-0139 (R5b-2) hand-off register — deferred, nothing lost

To be drafted with its **own FULL war-game** (M1–M4b) before that session; F1/F2/F9 mean it needs its
own M2/M3, not an inherited one.

1. **Operator-key enforcement across every sensitive route, reads included** (GAP-01) + the 401/403
   distinction + credential-presence startup guard interaction.
2. **The fail-closed mounted-route authorization matrix** (GAP-02) — F1-corrected: a documented
   recursive flattener **plus** `app.openapi()` cross-check, a **positive lower bound** assertion, and
   "behave" defined as **auth outcome only** (`401` none, `401` invalid, `403` valid-producer-key,
   `status_code not in (401,403)` operator-key) with a **fresh app per parameterized case** so no
   destructive command executes (F9). `POST /api/session/close` classified operator-only.
   `GET /api/events` named explicitly as event-log-truth read exposure.
3. **Principal stamping + `get_actor` precedence**, and the **F2 migration**: `routes_trading.py:220`
   and `:246` must stop reading a caller-controlled `X-Actor` for fill ingestion and the
   reconciliation attestation. Flag-off behavior must stay byte-equivalent (no principal ⇒ existing
   fallback). M2's read edge = actor-consuming routes enumerated **by grep**.
4. **Complete the truncated crown-jewel test** (F4) — assert the recorded actor is the principal and
   not the forged value. Authorized addition.
5. **`GET /api/signals`** (operator-only) + **`/api/producers`** read.
6. **Auto-docs**: absent under the flag, or operator-only — never public. (M4b verified deny-by-default
   middleware makes `/openapi.json` operator-only for free, so disabling is not required.)
7. **Cockpit `X-Operator-Key` plumbing** in the same change (GAP-01/T-22, no lockout window) —
   `cockpit/api_client.py:28` merges rather than replaces per-call `headers=`; note the two existing
   sites make `X-Actor` **required**, so a drop is a loud 422 (F8). Must not import `app.config` (F5
   hazard 5).
8. **`root_path` middleware-path divergence** (hazard 4).
9. **`.env.example`** credential documentation (F11).
10. **Cockpit half of GAP-05** if the signal panel lands here rather than R7.
