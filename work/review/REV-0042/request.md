---
type: Review Request
rev_id: REV-0042
title: "WO-0138 rev-3 — Signal Seat R5b-1 producer ingest surface"
status: STAGED
dispatch_state: READY_FOR_INDEPENDENT_REVIEW
reviewer_seat: Claude
targets: [WO-0138, ADR-009, signal-seat-r5b1]
human_gated_surfaces: [producer-authentication, signal-ingest-event-truth]
review_base_sha: ae87354f3ca82439df227830747d3df9b9cab506
head_sha: f5aaf7a0bd4055161018bdb80c1caaa41caf7293
commit_range: ae87354f3ca82439df227830747d3df9b9cab506..f5aaf7a0bd4055161018bdb80c1caaa41caf7293
branch: codex/signal-r5b1-producer-ingest
created: 2026-07-25
---

# REV-0042 — independent review of Signal Seat R5b-1

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, the `CLAUDE.md` safety core, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request,
WO-0138 rev-3, its disposition, and the accepted ADR/spec targets below. Re-derive the named
properties from the frozen range and fresh local evidence.

Create only `work/review/REV-0042/result.md`. Do not edit this request, source, tests, work-order
or state files, ADR/spec text, ledger, WO-0139, or another packet. Produce findings only. Each
finding must state defect class, cause, impact, affected `file:line`, what resolves it, and
independent pass/fail evidence. End with exactly one verdict: `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`, and list anything not independently verified.

This is authorized defensive assurance of the operator's local paper-trading application. There
is no live-trading, external-target, credential-access, persistence, or network-probing objective.
Do not include reusable bypass instructions, exploit payloads, or attack recipes.

## Frozen range and authority

Review:

`ae87354f3ca82439df227830747d3df9b9cab506..f5aaf7a0bd4055161018bdb80c1caaa41caf7293`

Curated delivery commits:

- `a7580da` — resume R5b-1 under the operator-ratified rev-3 scope;
- `40d48ea` — stage the ingest-only RED corpus;
- `e3d2360` — implement and verify the producer ingest surface.
- `f5aaf7a` — enforce the narrower producer wire-symbol domain and strengthen body-boundary proofs.

The earlier activation and NEEDS-INPUT history remains visible in the branch but is superseded by
the operator's disposition in `work/queue/SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md` and WO-0138
rev-3. The controlling authority is ADR-009 A-1/A-3/A-4, the accepted
`docs/spec/signal-seat/` pages, WO-0138 rev-3, and that direct operator disposition.

The feature flag remains OFF. This packet authorizes review only, not enablement, merge, PR,
completion, ledger mutation, or beta reliance.

## Rev-3 boundary to police

R5b-1 is **ingest-only**:

- one flag-gated `POST /api/signals`;
- producer-key authentication and server-derived producer identity;
- recognizing a valid operator credential only to return wrong-role 403 on that POST;
- a write-only typed signal facade;
- manual `SignalProposal` validation and an ingest response DTO;
- ingest-time dead-on-arrival expiry;
- the 64 KiB cap and the contract-5 route ratchet.

The following are deliberately absent and belong to R5b-2 or later: `GET /api/signals`, facade
list/get methods, effective/lazy read expiry, a read clock, operator middleware or enforcement on
any other route, principal stamping, `get_actor` changes, cockpit work, approve/reject/release,
real R6 rails, R7 conversion, schema/migration, event-log truth changes, and flag enablement.
`tests/test_signal_facade_reads.py` must remain absent. WO-0139 must be unchanged.

## Named defect closures to verify

| Defect class | Cause | Impact | Implemented control | Primary files |
|---|---|---|---|---|
| missing trust-boundary surface | R5a intentionally ended before producer ingest | Every flag-on producer POST returned 404 | Flag-gated POST + typed DTO/facade composition | `app/main.py`, `app/api/routes_signals.py`, `app/facade/signal_commands.py`, `app/facade/signals.py` |
| identity-validation defect | A body identity could be mistaken for authority | Cross-producer namespace spoof/accounting | Full-map constant-time credential lookup; body mismatch rejects before facade/accounting | `app/api/deps.py`, route tests |
| incorrect type acceptance | Default Pydantic coercion and the broader shared symbol normalizer can admit values outside the producer wire contract | Malformed timestamps, TTLs, advisory values, or ASCII digit/hyphen symbols could appear valid | Strict/manual `SignalProposal`, plus the signal-specific `[A-Z.]+` domain; attributable failures become recorded quarantines | `app/api/schemas.py`, `app/api/routes_signals.py` |
| body-before-auth ordering | A declared body model is consumed before dependencies | Unknown or quarantined producers could force body processing | Raw `Request`; auth → rails dependencies → capped stream → parse | route/dependency code and ASGI receive probes |
| unbounded-body defect | An admitted producer body could be read without a hard cap | Memory/CPU pressure before validation | Content-Length and streamed 64 KiB enforcement, HTTP 413, no event | route and response/event-log tests |
| incomplete lifecycle totality | HTTP-only success assertions can miss durable writes | Replay writes, conflict mutation, or missing terminal facts could ship | Event-log assertions for all R5b-1 M2 outcomes | `tests/test_signal_routes.py` |
| malformed-identity collision | A shared sentinel conflates distinct malformed bodies | Attributable facts can disappear as false replays/conflicts | Content-addressed synthetic IDs outside the valid wire-ID alphabet | route and event-log test |
| incorrect type acceptance — producer map | REV-0041's request-time hostile-Mapping premise became stale after R5a normalization | Rebuilding trust logic would duplicate/diverge from config validation | Request-path regression pin proves immutable copied `MappingProxyType` lookup | config behavior + route test |
| normative/API mismatch | Accepted response table omitted the required 413 | Code and accepted wire contract would diverge | Explicit authorized 413/no-event row | `docs/spec/signal-seat/04-auth-and-api.md` |
| layering regression | A new route could bypass the facade | HTTP code could reach event/store truth directly | Contract 5 includes `app.api.routes_signals`; 6/6 contracts kept | `.importlinter`, route imports |

For each row, establish that the regression is behaviorally tied to the control. Temporary local
mutations are allowed for failure-capable verification, but restore the tree before writing
`result.md` and report only the pin's pass/fail behavior, not a reusable bypass recipe.

## Critical properties to re-derive

1. Authentication and rails execute without a request-body receive. Missing/unknown producer
   credentials return 401; a valid operator credential on this producer route returns 403.
2. Producer identity always comes from `Settings.signal_producer_keys`. A matching compatibility
   body field is ignored; a mismatching string returns 422 before namespace accounting and without
   an event.
3. The normalized producer-key map is the R5a-owned immutable copy at request lookup. The route
   does not re-derive a second trust container.
4. Rails denial happens before body read. A quarantined producer returns 403 and records no ingest
   event. Malformed rails decisions fail closed.
5. The route never declares a Pydantic body parameter. Bodies over 64 KiB return 413 whether
   rejected by declared length or while streaming, before parse/validation, with no event.
6. Unparseable JSON returns 400/no event. Every parseable, authenticated validation failure is
   representable and recorded as terminal `SIGNAL_QUARANTINED`/422 without a secondary 500.
7. The six facade-owned outcomes map exhaustively: fresh/201, ingest-expired/201,
   freshness-quarantined/201, validation-quarantined/422, replay/200, conflict/409.
8. Ingest-time `expires_at <= received_at` writes `SIGNAL_EXPIRED` with
   `detected_by: "ingest"`. No lazy/read expiry behavior appears.
9. Identical replay is write-free. A changed payload on the same producer/signal identity appends
   only `SIGNAL_DUPLICATE_CONFLICT`, does not mutate the original record, and returns 409.
10. Hostile thesis/provenance text remains opaque and verbatim for valid UTF-8; invalid values
    cannot poison record creation or response serialization. Error paths do not echo credentials.
11. `SignalRecordView` follows the existing `ResponseSafeFloat` JSON convention.
12. Flag off leaves the route absent and existing localhost behavior unchanged. No existing route,
    `get_actor`, middleware, operator auth, or UI behavior changes.
13. `routes_signals` imports no store/events/policy/broker module and reaches writes only through
    `SignalCommandFacade`.

## Explicit spec amendment for review

WO-0138 D-R5b1-6 pre-authorized one accepted-text amendment: add HTTP **413** with **no event** to
the `POST /api/signals` response table for the 64 KiB cap. Verify that the implementation and
failure-capable test match the new row. Any other normative or event-log-truth change is
unauthorized and blocking.

No `INV-*` definition was added or amended in this range.

## Author evidence to reproduce skeptically

- RED ingest corpus: `1 passed, 14 failed`; every flag-on assertion received 404 from the absent
  route.
- Final R5b-1 response/event-log corpus: `38 passed`.
- Signal/store/launch regression batch: `136 passed`.
- `ruff check .`: `All checks passed!`.
- R5b-1 owned-file `ruff format --check`: `7 files already formatted`.
- `mypy app/`: `Success: no issues found in 77 source files`.
- `lint-imports`: 6 kept, 0 broken.
- CI-form R2 oracle: `61 passed`.
- Repair-scaling gate: `13 passed`.
- Full suite: 4,366 collected; progress reached 100%; exit 0 after 353.9 s, with 11 skips and one
  expected xfail shown in the terminal stream.
- `python harness/bootstrap.py`: exit 0; dependencies already satisfied; Ruff/mypy/collection
  completed and 4,366 tests collected. Restricted-network pip retry warnings were non-fatal.
- `git diff --check`: pass.

Use normal OS temporary space for pytest and disable the cache provider. Treat environment-limited
network or temp-root failures as environment evidence, never as passing test evidence.

## Curated targets and exclusions

Implementation:

- `app/api/deps.py`
- `app/api/routes_signals.py`
- `app/api/schemas.py`
- `app/facade/signal_commands.py`
- `app/facade/signals.py`
- `app/main.py`

Regressions and contracts:

- `tests/test_signal_routes.py`
- `.importlinter`
- `docs/spec/signal-seat/04-auth-and-api.md`

State/authority:

- `work/active/WO-0138-signal-r5b1-producer-ingest-surface.md`
- `work/active/SIGNAL-R5b1-STATE.md`
- `work/queue/SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md`

Out of scope: all R5b-2 read/operator work, WO-0139 edits, R6 rails implementation, R7 conversion,
cockpit, schema/migration, live trading, real credentials, flag enablement, ledger, completion move,
merge, PR, and fixes by the reviewer.

## Expected output

Write findings only to `work/review/REV-0042/result.md`, followed by one verdict. `BLOCK` any
safety-invariant breach, pre-auth body read, client-controlled producer namespace, no-event path
that appends, attributable parseable failure that disappears or 500s, replay write, conflict
mutation, unapproved scope expansion, inert decisive regression, unauthorized accepted-text
change, or completion evidence that cannot be independently reproduced.
