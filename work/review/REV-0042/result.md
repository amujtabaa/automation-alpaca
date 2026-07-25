---
type: Review Result
rev_id: REV-0042
title: "WO-0138 — Signal Seat R5b-1 producer ingest surface"
reviewer_seat: Claude (independent review seat; implementer was Codex)
review_head_sha: 23603ed
branch: codex/signal-r5b1-producer-ingest
human_gated_surfaces: [producer-authentication, ingest-event-truth]
verdict: BLOCK
reviewed: 2026-07-25
---

# REV-0042 — result

## Method

Two independent passes, both against the branch rather than the report:

1. **Review-seat direct** — fresh POSIX run of the corpus and full suite; two red-green control
   mutations; structural verification of the A-4 ordering and the no-event boundary; scope-boundary
   audit of every changed file; flag-off route-table measurement.
2. **Fresh-context adversarial pass** — 32-mutant battery against the corpus, a 1500-case ingest-body
   fuzz, and store-level record-diff probes. (A first attempt died on a server-side API error after
   only reaching the import-contract check; it was re-dispatched.)

**Every finding below that changes the verdict was reproduced by the review seat directly**, not
accepted from the adversarial pass. One of its P1 findings did **not** reproduce as a live defect and
is downgraded accordingly.

Defensive assurance of the operator's own local paper-only application. Defect-level reporting; no
exploit narration. The feature flag remains OFF.

## Verdict

**BLOCK** — on **F-1** alone. Everything else this review targeted holds, much of it strongly.

---

## F-1 (P0, CONFIRMED BY DIRECT REPRODUCTION) — producer-reachable unhandled `OverflowError` with no record and no event

**Defect class:** unbounded input at a trust boundary → unhandled exception; loss of outcome totality
and audit attributability.

**Reproduced by the review seat** against the branch, using the corpus's own fixture wiring:

```
body:   issued_at="9999-12-31T23:59:59+00:00", ttl_seconds=300  (all other fields valid)
result: OverflowError: date value out of range
events: 0
```

**Cause.** `expires_at` is computed as
`min(received_at + …, issued_at + timedelta(seconds=ttl_seconds))` **before** the future-skew test, so
any `issued_at` within `ttl_seconds` of `datetime.max` overflows. Reachable on **both** the valid path
and the validation-failure path (`app/api/routes_signals.py:240,258` → `app/facade/signals.py:57` →
`app/store/core.py:5838`, `:6006`).

**Impact.** `docs/spec/signal-seat/02-lifecycle.md:94` mandates that `issued_at > received_at + 30s`
produce a recorded `SIGNAL_QUARANTINED("issued_at_future")`. Actual behavior is an unhandled exception
(HTTP 500 in production) writing **nothing** — no record, no event, nothing attributable to the
producer. That voids WO-0138 §M2's outcome-totality claim and puts an un-audited, producer-reachable
crash on **the repository's first authenticated external input path** — precisely the class GAP-06
exists to prevent. A 1500-case body fuzz found 40 5xx responses, **all** of this single class and no
other.

**Required fix (inside R5b-1's allowed paths).** Bound `issued_at` on the wire: add a range check to
`_issued_at_must_be_timezone_aware` (`app/api/schemas.py:198-203`) and mirror it in
`_safe_optional_issued_at` (`app/api/routes_signals.py:147-165`), rejecting any UTC-normalized
`issued_at` outside `[datetime.min + 1d, datetime.max − SIGNAL_TTL_MAX_SECONDS]`. That yields a
recorded, attributable 422 quarantine with no crash. **Red-first**: the regression must fail before the
fix.

**Planning-seat note on the alternative.** A store-side fix (move the skew test above the arithmetic
and clamp the addition) would preserve the exact `issued_at_future` taxonomy and return 201, which is
semantically closer to the spec — but it edits `app/store/core.py`, outside R5b-1's IN list, and
WO-0138's stop conditions require escalation rather than self-authorization. **Take the wire-bound fix
now**; the taxonomy nicety for absurd dates can ride with R5b-2 or R6 if wanted. The safety property —
recorded, attributable, no crash — is fully restored by the in-scope fix.

## F-2 (P1) — `signal_id` wire domain is unpinned, and the malformed-identity namespace argument rests on it

`app/api/routes_signals.py:181-183` argues that a colon is outside the valid wire-id alphabet, so the
content-addressed `malformed:<hash>` identity cannot collide with a producer-supplied id. That property
is enforced solely by the `signal_id` pattern (`app/api/schemas.py:163`) and `_WIRE_SIGNAL_ID_RE`
(`:37`) — and **relaxing the pattern leaves all 38 tests green**. Current behavior is correct (both
`malformed:deadbeef` and a 65-character id are 422 today); the guard is simply unheld.

*Impact if it regresses:* a producer could pre-claim a quarantine key, converting a would-be recorded
`SIGNAL_QUARANTINED` into an audit-only `SIGNAL_DUPLICATE_CONFLICT` — different fold targets on a seam
R6's accounting depends on. **Fix:** two assertions (`malformed:deadbeef` → 422; 65-char id → 422). No
production change.

## F-3 (P1 → downgraded: test-coverage gap, NOT a live defect)

The adversarial pass reported the `symbol` ASCII guard (`app/api/schemas.py:209-210`) as inert.
**The review seat probed the live behavior and it is correct:** `symbol="ıBM"` (dotless i) returns
**422**, not a homoglyph-substituted 201. So this is *not* a behavioral defect.

What is true is the **mutation-sensitivity** claim: both existing non-ASCII tests use characters
(`ＡＡＰＬ`, `Å`) that the symbol regex rejects *after* `.upper()`, so neither exercises `isascii()`.
The uncovered residual is Unicode whose `str.upper()` **is** ASCII (`ı→I`, `ﬁ→FI`, `ß→SS`). **Fix:**
retarget one of the two tests to `symbol="ıBM"`. One line; production code already correct.

## F-4 (P1) — `extra="forbid"` unpinned

`app/api/schemas.py:161`; mutation to `extra="allow"` survives all 38 tests. Because
`build_signal_proposal_payload` hashes only named fields, losing it would make two materially different
wire bodies hash identically — the second returning **200 replay** instead of 409, silently discarding
producer content. Current behavior is correct (unknown key → 422). **Fix:** one assertion.

## F-5 / F-6 / F-7 (P2) — three more unpinned validation guards

All currently behave correctly; none is held by a test.
- **F-5** bare-numeric-string `issued_at` (`schemas.py:192-195`): `"1752505200"` is a 422 today; the
  existing test sends a JSON *number*, a different control. Losing the guard silently coerces a Unix
  timestamp — the exact lax-coercion class the WO names.
- **F-6** `allow_inf_nan=False` (`:179`): `json.loads` accepts bare `Infinity`, which would become a
  201 with the price silently nulled. (`NaN` is incidentally caught by `gt=0`; `Infinity` is not.)
- **F-7** provenance caps (20 entries / 500 chars / UTF-8) and `thesis` `min_length=1` (`:182,219-230`)
  — four mutations, all survive. Also undocumented: `_safe_provenance`
  (`routes_signals.py:167-177`) applies **no** caps on the validation path, so a deliberately-invalid
  payload records an arbitrarily large provenance map (bounded only by the 64 KiB body cap). Defensible
  as "record hostile input verbatim", but neither stated nor tested.

## F-8 (P3, forward-looking to R7) — the 409 response returns the full original record

`routes_signals.py:195-200` returns `SignalRecordView` of the pre-existing record, and that view carries
`approved_by`, `converted_kind`, `converted_id` (`schemas.py:236-262`). Always null today. Once R7
mounts approve, a producer resubmitting a changed payload for an approved `signal_id` would learn the
operator actor label and the converted order id. **Recorded as an R7 register item.**

## F-9 (P3) — the 409 "original untouched" property is asserted only via `id` + `status`

Store-level probing confirms the record is genuinely byte-identical after a hostile conflicting resend
(`thesis`, `suggested_quantity`, `payload_hash` all preserved) — **production behavior holds** — but a
store-side regression rewriting non-status fields would keep the test green. **Fix:**
`assert conflict.json() == first.json()` (true today).

## F-10 (P3) — facade-seam nits, one worth recording

- `SignalIngestResult` now exists twice with the same name and different shapes
  (`app/facade/signal_commands.py:24-27` typed vs `app/store/base.py:329-339` `str`) — misimport hazard.
- `app/facade/signals.py:73-78` maps an unrecognized store outcome to `RuntimeError` → 500; fail-loud is
  defensible, but a future seventh outcome becomes an unhandled 500 rather than a typed refusal.
- **`app/api/schemas.py:32` adds an `app.api → app.store.base` edge** (`normalize_symbol`). Contract 5
  exempts `app.api.schemas` from `source_modules` and sets `allow_indirect_imports = True`, so
  `lint-imports` structurally cannot see the `routes_signals → schemas → app.store` chain. Spec `04 §2`
  ("the route never imports `app.store`") is satisfied **directly**, but now holds by exemption rather
  than by the ratchet. Recorded explicitly rather than left implicit.

## F-11 (P3) — the route corpus is memory-store only

Every case uses `InMemoryStateStore()`. Dual-store parity for `ingest_signal` exists at the store layer
(`tests/test_signal_ingest_store.py`, `any_store`), so this satisfies D-R5b1-10 — but no end-to-end case
drives the route's novel shapes (the 74-char `malformed:<sha256>` id, a 4000-char thesis, a ~64 KiB
provenance map) into SQLite. Parameterizing the `client` fixture over `["memory","sqlite"]` closes it
cheaply.

---

## What holds (verified, much of it strongly)

| Property | Verdict | Evidence |
|---|---|---|
| **Ingest-only re-scope held** | ✅ | No `test_signal_facade_reads.py`; `@router.post("/signals")` is the **sole** decorator; `signals.py` exposes only `ingest_signal`; no `effective_signal_status`; no lazy expiry |
| `app/api/schemas.py` additive-only | ✅ | Only deletions are two consolidated import lines; no existing model altered |
| Operator credential bounded to the producer 403 (D3) | ✅ | `operator_key_valid` documented "only for producer-route role separation" |
| Spec amendment confined | ✅ | Exactly one line — the authorized 413 row |
| **A-4 body-blind ordering** | ✅ | Handler takes raw `Request`; auth/rails are a `Depends`; body read only inside the handler via a streaming reader |
| **401/400/413 → no event (GAP-06 unattributable invariant)** | ✅ **structurally** | Sole append site is `facade.ingest_signal` (`:235,:253`), strictly behind the identity dependency; `app/main.py` registers **no** middleware and **no** exception handlers, so no earlier log path exists. Probe: `http_receive_calls == 0` on a 65 KiB body |
| 200 replay write-free | ✅ | Record dump byte-identical pre/post; event list unchanged |
| 409 conflict — original untouched, audit-only, coalesced | ✅ | Hostile-overwrite probe: record byte-identical; `plan.record is None` |
| Outcome status mapping incl. the 201-vs-422 split | ✅ | Freshness quarantine → 201 is **spec-correct** (`04 §2`: 201 covers "recorded terminal: quarantined/expired at ingest"); validation → 422 |
| DOA → `SIGNAL_EXPIRED`, `detected_by:"ingest"` | ✅ | `core.py:5854-5862` |
| Manual validation not looser than `01-schema.md §1` | ✅ | Field-by-field equal or stricter on all 10 rows |
| Facade seam is a real typed seam | ✅ | `get_signal_facade` mirrors the existing composition-root pattern; no `get_store` dep |
| Identity binding decisively pinned | ✅ | **Review-seat red-green:** neutering `:223` turns **both** identity tests RED; restored → green |
| 64 KiB cap decisively pinned | ✅ | **Review-seat red-green:** raising the cap 100× turns `test_body_over_64kib_rejected` RED |
| Static gates | ✅ | ruff clean · mypy **77 files** clean · lint-imports **6 kept / 0 broken** |
| Full suite non-regression | ✅ | **Review-seat run: exit 0, zero failures, 100%** |
| Flag-off byte-equivalence | ✅ | **Measured:** `/api/signals` not mounted, 34 `/api` ops — identical to pre-R5b-1 |

**No test was weakened to make code pass.** The corpus is unusually strong where it aims — 20 of 32
mutations caught, including every status mapping, both identity-binding variants, the content-addressed
malformed identity, and the streaming cap. `test_boundary_rejections_append_no_event` is genuine and
mutation-sensitive, not inert.

## Required before ACCEPT

1. **F-1** — fix with a red-first proof (wire-bound `issued_at`, in-scope). **Blocking.**
2. **F-2, F-3, F-4** — three test additions; zero production change for F-3/F-4, one for F-2.
3. **F-5, F-6, F-7, F-9** — cheap pins; should ride along.
4. **F-8, F-10, F-11** — carried to the R5b-2 / R7 register, no action in this rung.

Re-review on the fix will be scoped to F-1's regression plus the added pins, not a full re-run.
