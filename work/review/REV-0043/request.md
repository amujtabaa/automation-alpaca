---
type: Review Request
rev_id: REV-0043
title: "WO-0139 — Signal Seat R5b-2 operator enforcement and principal-bound audit truth"
status: STAGED
dispatch_state: READY_FOR_INDEPENDENT_REVIEW
reviewer_seat: Claude
targets: [WO-0139, ADR-009, signal-seat-r5b2]
human_gated_surfaces: [operator-authorization, audit-actor-truth, event-log-read-truth, cockpit-credentials]
review_base_sha: fa087deb56bc58fa627e26a54de6e1bc39a27169
head_sha: 10d2bce1fc11591a1994b1be891fef231df52fb5
commit_range: fa087deb56bc58fa627e26a54de6e1bc39a27169..10d2bce1fc11591a1994b1be891fef231df52fb5
branch: codex/signal-r5b2-operator-auth
created: 2026-07-25
---

# REV-0043 — independent review of Signal Seat R5b-2

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, the `CLAUDE.md` safety core, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request,
WO-0139, its state file, ADR-009, and the accepted Signal Seat spec/threat-model targets listed
below. Re-derive the named properties from the frozen range and fresh local evidence.

Create only `work/review/REV-0043/result.md`. Do not edit this request, source, tests, work-order or
state files, accepted specs, ledger, or another packet. Produce findings only. Each finding must
state defect class, cause, impact, affected `file:line`, what resolves it, and independent pass/fail
evidence. End with exactly one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, and list
anything not independently verified.

This is authorized defensive assurance of the operator's local paper-trading application. There is
no live-trading, external-target, credential-access, persistence, or network-probing objective.
Report at defect level. Do not include reusable evasion instructions, credential material, or
attack recipes.

## Frozen range and authority

Review:

`fa087deb56bc58fa627e26a54de6e1bc39a27169..10d2bce1fc11591a1994b1be891fef231df52fb5`

Curated delivery commits:

- `a748c01` — activate WO-0139 and create the mandatory continuity/evidence state;
- `75e328a` — implement operator enforcement, signal reads, cockpit plumbing, accepted lifecycle
  amendment, and the RED/GREEN corpus;
- `10d2bce` — preserve the two recovery routes' required `X-Actor` compatibility while retaining
  authenticated-principal attribution.

Authority order is current code/tests, accepted ADR-009 and `docs/spec/signal-seat/`, WO-0139's
ratified rev-2/rev-3 decision block, then this request. The feature flag remains OFF. This packet
authorizes review only, not enablement, rails/release/conversion work, merge, PR, completion, or
ledger mutation.

## Boundary to police

R5b-2 owns:

- flag-scoped request-time operator enforcement over every mounted sensitive HTTP operation;
- exact public `GET /api/health` and producer-only `POST /api/signals` classification;
- 401 missing/unknown versus 403 valid-wrong-role outcomes;
- a distinct authenticated operator principal and principal-preferring actor composition;
- migration of the two direct recovery actor routes, with the required label contract preserved;
- mutation-free `GET /api/signals` projections and injected read time;
- explicit absence of all four auto-doc endpoints while the flag is on;
- cockpit `X-Operator-Key` injection/merge;
- safe `.env.example` placeholders;
- the ratified mutation-free-read amendment to `02-lifecycle.md`.

Out of scope and required to remain absent: R6 rails enforcement, producer release,
`GET /api/producers`, R7 signal approve/reject or conversion, schema/migration, new event types,
feature enablement, live trading, result/disposition, completion move, ledger entry, merge, and PR.

## Named defect closures to verify

| Defect class | Cause | Impact | Implemented control | Primary files |
|---|---|---|---|---|
| missing-authorization coverage | R5b-1 authenticated only producer ingest | Sensitive reads/commands could execute without an operator credential | Flag-scoped deny-by-default middleware and literal role matrix | `app/main.py:77`, `app/main.py:209`, `tests/test_route_authorization_matrix.py:24` |
| unauthorized-role acceptance | Path-only or prefix classification could grant the wrong role | Producer credential could reach operator-only signal reads or a near-path request | Exact `(method, routed_path)` sets, full-map role checks, near-path/root-path controls | `app/main.py:77`, `app/api/deps.py:62`, `tests/test_route_authorization_matrix.py:290` |
| incomplete route ratchet | Runtime discovery can be vacuous or omit schema-hidden/non-API routes | A future mounted route could ship unclassified or a required route could disappear | Recursive wrapper/Mount flattener, literal `REQUIRED`, both subset assertions, exact OpenAPI cross-check | `tests/test_route_authorization_matrix.py:99`, `tests/test_route_authorization_matrix.py:183` |
| audit-attribution defect | Caller `X-Actor` previously had no authenticated principal | Event truth could not distinguish authenticated authorization from a caller label | Distinct `operator:authenticated` request principal; optional printable suffix; exact equality pins | `app/api/deps.py:204`, `app/main.py:222`, `tests/test_signal_routes.py:903` |
| event-writing actor inconsistency | Two recovery routes bypassed the shared actor dependency | Canonical fill/reconciliation truth recorded only the raw label | Required-label wrapper delegates into principal composition; memory/SQLite HTTP proof | `app/api/deps.py:231`, `app/api/routes_trading.py:221`, `tests/test_recovery_actor_provenance.py:73` |
| operator-lockout risk | Backend enforcement without cockpit credentials would reject the operator UI | Kill switch, flatten, session controls, and sensitive reads could become unusable | Single request seam merges the env credential, preserves other headers, and owns case-insensitive precedence | `cockpit/api_client.py:28`, `tests/test_cockpit_operator_header.py` |
| stale read projection | Stored RECEIVED can outlive its TTL before the future durable sweep | Operator read could present an expired thesis as actionable | Pure effective status, injected clock, list/get filtering, copied results | `app/facade/signals.py:31`, `app/facade/signals.py:109`, `app/api/routes_signals.py:208` |
| event-log read mutation | Lazy expiry implemented as a write would make a GET an event writer | Read traffic could append durable truth and violate the ratified single-writer choice | Before/after event equality for list and get in both stores | `tests/test_signal_facade_reads.py` |
| schema exposure | FastAPI auto-docs are outside router dependencies | Schema/UI endpoints could remain public | Docs/openapi/redoc disabled under the flag and explicitly asserted absent | `app/main.py:195`, `tests/test_route_authorization_matrix.py:253` |
| flag-off compatibility regression | Common actor dependency makes labels optional and sanitization can leak outside the flag | Existing localhost API behavior could change while Signal Seat is disabled | Principal-gated sanitization plus narrow required-label wrapper; inherited suite pin | `app/api/deps.py:204`, `app/api/deps.py:231`, `tests/test_wo0114_pd1_release_valve.py` |

For each row, establish that the regression is behaviorally tied to the control. Temporary local
mutations are allowed for failure-capable verification, but restore the tree before writing
`result.md` and report only the pin's pass/fail behavior at defect level.

## Critical properties to re-derive

1. With the flag on, recursive discovery finds **36 mounted HTTP operations**, exactly equal to
   OpenAPI: one public operation, one producer-only operation, and the remaining classified
   operator/dev operations. The four auto-doc paths are absent.
2. `REQUIRED` is literal and independent of discovery. `REQUIRED <= discovered` detects a missing
   required route; `discovered <= CLASSIFIED` covers every mounted HTTP operation, including
   schema-hidden and non-`/api` additions.
3. Only exact `GET /api/health` is public and exact `POST /api/signals` is producer-only. Method,
   near-path, unmatched-path, and `root_path` variants retain deny-by-default behavior.
4. Every operator-classified route has four fresh-app cases: none 401, unknown 401, valid producer
   403, valid operator reaches downstream handling. Producer ingest has the symmetric role cases.
5. Both producer credential helpers traverse the complete normalized producer-key map for early,
   middle, late, and no-match inputs. Non-ASCII credential text fails as an ordinary invalid
   credential rather than an internal error.
6. All 16 event-writing actor consumers now use principal-preferring resolution. The two recovery
   routes still require `X-Actor`; their fill and reconciliation facts persist exact
   `operator:authenticated:desk-3` on both stores.
7. With no optional label, an authenticated command records exact `operator:authenticated`.
   With the flag off, internal control characters in an existing actor label remain unchanged.
8. Cockpit header injection copies rather than mutates caller headers, preserves `X-Actor`, removes
   a case-variant caller operator-key value when the environment key exists, and makes critical
   controls/sensitive reads use the same credential seam.
9. `GET /api/signals` defaults to effective RECEIVED, supports status/symbol/producer filters, maps
   bad filters cleanly, and returns mutation-free copied projections. `get_signal`, `list_signals`,
   replay echo, and conflict echo all use the injected effective-time rule.
10. The full flag-off suite remains green. Existing docs remain enabled flag-off, existing
    localhost requests remain unauthenticated, and missing recovery `X-Actor` still returns 422.
11. No R6/R7 functionality or enablement appears in the range. Alpaca Paper-only, submitted is not
    filled, fill-only position mutation, backend truth ownership, and single-writer execution remain
    unchanged.

## Explicit accepted-text amendment for review

WO-0139 D-R5b2-18 records the operator's 2026-07-25 ratification of mutation-free lazy reads.
`docs/spec/signal-seat/02-lifecycle.md:33`, `:51`, and `:109` now say:

- a read projects effective EXPIRED using an injected clock and appends nothing;
- durable `SIGNAL_EXPIRED` is written at ingest, by sweep, or at the atomic conversion write
  boundary;
- `detected_by:"read"` is removed; accepted durable origins are ingest/sweep/conversion.

Verify this amendment against the implementation and ensure no other event vocabulary or
human-gated normative behavior changed. No `INV-*` entry was added or amended in this range.

## GAP claim and deferred obligation

The author claims **GAP-01 is closed** by same-change cockpit credential plumbing and **GAP-02 is
closed** for all currently mounted routes by literal existence, full mounted-route classification,
role-outcome, and docs controls.

Do not conflate that claim with the deliberately deferred spec-04 **required-present completeness**
obligation for the future R6 producer release/read and R7 approve/reject routes. Those literal rows
must be added and proven at their joint milestone; they are not authorized in this range.

## Author evidence to reproduce skeptically

- Hard predecessor gate: `routes_signals.py` blob present on master and REV-0042 disposition
  present; branch created from `fa087deb`.
- Step 0: 35 `/api` operations plus four docs endpoints = 39 before R5b-2.
- Signal facade RED/GREEN: `16 failed, 14 passed` to `30 passed` across both stores.
- Authorization/read/matrix/cockpit targeted corpus: named gaps RED; then `218 passed`.
- Recovery actor migration: exact actor assertion RED in 4/4 memory/SQLite cases, then `4 passed`.
- Independent in-process corpus review found nine missing mutation/negative controls; strengthened
  final five-file R5b-2 corpus: `258 passed`.
- Cockpit case-insensitive credential precedence: `1 failed, 6 passed` RED; then green in the
  258-case corpus.
- First full suite found one real flag-off compatibility regression (missing recovery actor returned
  200 instead of inherited 422); focused repair batch `156 passed`.
- Final `ruff check .`: `All checks passed!`.
- Scoped `ruff format --check`: `12 files already formatted`.
- `mypy app/`: `Success: no issues found in 77 source files`.
- `lint-imports`: 6 kept, 0 broken.
- Final R5b-2 corpus: `258 passed`.
- Final full suite: 4,586 collected; 100%; exit 0 in 407 s; 4,574 passed, 11 skipped, 1 expected
  xfail marker.
- R2 conformance oracle: `61 passed`.
- WO-0113 repair-scaling gate: `13 passed`.
- `harness/bootstrap.py`: exit 0; dependencies already satisfied; Ruff/mypy/collection completed
  with 4,586 tests. Restricted-network pip retries were non-fatal.
- Final route inventory: 36 mounted; exact OpenAPI equality; four docs paths absent.
- `git diff --check`: empty.

Use normal OS temporary space for pytest and disable the cache provider. Treat environment-limited
network or temp-root failures as environment evidence, never as passing test evidence.

## Curated targets and exclusions

Implementation:

- `app/api/deps.py`
- `app/api/routes_signals.py`
- `app/api/routes_trading.py`
- `app/facade/signal_commands.py`
- `app/facade/signals.py`
- `app/main.py`
- `cockpit/api_client.py`
- `.env.example`
- `docs/spec/signal-seat/02-lifecycle.md`

Regressions:

- `tests/test_route_authorization_matrix.py`
- `tests/test_signal_routes.py`
- `tests/test_signal_facade_reads.py`
- `tests/test_recovery_actor_provenance.py`
- `tests/test_cockpit_operator_header.py`
- inherited flag-off and full-suite tests

State/authority:

- `work/active/WO-0139-signal-r5b2-operator-enforcement.md`
- `work/active/SIGNAL-R5b2-STATE.md`
- `docs/adr/ADR-009-signal-seat-boundary.md`
- `docs/spec/signal-seat/02-lifecycle.md`
- `docs/spec/signal-seat/03-rails.md`
- `docs/spec/signal-seat/04-auth-and-api.md`
- `docs/THREAT_MODEL_SIGNAL_SEAT.md`

Out of scope: real rails, producer release/read, signal approve/reject/conversion, schema/migration,
feature enablement, live trading, real credentials, result/disposition, ledger, completion move,
merge, PR, and fixes by the reviewer.

## Expected output

Write findings only to `work/review/REV-0043/result.md`, followed by one verdict. `BLOCK` any
safety-invariant breach, missing sensitive-route authorization, unauthorized-role acceptance,
caller-controlled principal truth, cockpit lockout of critical controls, read-path event mutation,
unclassified or silently absent required route, inert decisive regression, flag-off behavior
change, unauthorized accepted-text change, out-of-scope R6/R7 implementation, flag enablement, or
completion evidence that cannot be independently reproduced.
