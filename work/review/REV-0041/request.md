---
type: Review Request
rev_id: REV-0041
title: "WO-0137 — Signal Seat R5a composition-root foundation"
status: STAGED
dispatch_state: READY_FOR_INDEPENDENT_REVIEW
reviewer_seat: Claude
targets: [WO-0137, ADR-009, signal-seat-r5a]
human_gated_surfaces: [auth-launcher, transport-bind]
review_base_sha: 47a0d9f4e8bba5abc0feff3d029b04c8ace82dd3
head_sha: d78e54fda6a780546cd6892078b209f9ae33438f
commit_range: 47a0d9f4e8bba5abc0feff3d029b04c8ace82dd3..d78e54fda6a780546cd6892078b209f9ae33438f
branch: codex/signal-r5a-foundation
created: 2026-07-23
---

# REV-0041 — independent review of Signal Seat R5a

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, the `CLAUDE.md` safety core, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request,
the accepted ADR/spec targets below, and the frozen semantic range. Re-derive the named
properties from code and fresh local evidence.

Create only `work/review/REV-0041/result.md`. Do not edit this request, source, tests, work-order
or state files, ADR/spec text, ledger, or another packet. Produce findings only. Report each
finding at the defect level: defect class, cause, impact, affected local files, what resolves it,
and independent pass/fail evidence. Include `file:line` anchors. End with exactly one verdict:
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, and list anything not independently verified.

This is authorized defensive assurance of the operator's local paper-trading application. There
is no external target, credential access, live trading, persistence, or network-probing objective.
Keep launch/capability adversarial work bounded to the named defect classes below. Do not include
reusable bypass procedures, exploit payloads, or attack recipes in `result.md`.

## Frozen range and human authority

Review:

`47a0d9f4e8bba5abc0feff3d029b04c8ace82dd3..d78e54fda6a780546cd6892078b209f9ae33438f`

Curated commits:

- `7d378dd` — activate WO-0137;
- `6aee970` — import the staged R5a RED corpus;
- `58ceb32` — add Signal Seat settings validation;
- `3e6e3ed` — add the backend-owned launcher boundary;
- `b985174` — add the rails Protocol seam;
- `c968d26` — add ordered `create_app` construction guards;
- `3dadec4` — document the sanctioned enabled-seat launch;
- `5d04d6f` — align capability bind types;
- `a410546` — harden capability identity and one-use handling;
- `4bb1bfb` — record the pre-resume gate blockers;
- `d78e54f` — apply the operator-authorized QA completion controls.

Authority is ADR-009 A-1/A-4, `docs/spec/signal-seat/04-auth-and-api.md` section 1, WO-0137,
and the operator's direct 2026-07-23 Part B/D1–D3 disposition recorded in the WO and
`SIGNAL-R5a-STATE.md`. The referenced queue disposition file was absent at the confirmed base
and fetched branch; do not infer additional authority from a nonexistent artifact.

The feature flag remains OFF. This packet authorizes review, not enablement, merge, close-out,
or beta reliance.

## Named defect closures to verify

| Defect class | Cause | Impact | Affected local files | Implemented control | Author evidence |
|---|---|---|---|---|---|
| incorrect type acceptance — launch/capability | Non-exact trust-boundary types could reach recognizers | An illegitimate subtype could satisfy a construction precondition | `app/launch_guard.py`, `tests/test_signal_seat_launch_guard.py` | Exact built-in host/UDS and exact capability type checks | Named subtype rejection test passes |
| identity-validation defect | Issuance membership did not by itself prove exact object identity | A nonidentical authority object could be treated as issued | `app/launch_guard.py`, guard regression | ID-keyed weak registry plus exact identity comparison | Identity mismatch regression passes |
| non-atomic one-use validation | Validation and retirement were separable | Concurrent construction could consume one authority more than once | `app/launch_guard.py`, `app/main.py`, guard regression | One lock covers validate-and-retire | Sixteen concurrent consumers yield exactly one success; three consecutive runs pass |
| incorrect type acceptance — credential config | Three credential positions used subclass-admitting validation | Direct injection could violate D-R5a-4's exact-string contract | `app/config.py`, `tests/test_signal_seat_config.py` | Exact built-in `str` checks for operator key, producer key, and producer id | All three RED-first cases pass after the fix |
| capability reacquisition via importable factory | Test construction supplied authority on a zero-argument path | Test-only wiring could be selected without explicit in-process authorization | `tests/signal_seat_helpers.py`, guard regression | Exact explicit in-process test authority | Factory, bare-load, and direct zero-argument selection all reject |
| launcher child-environment isolation defect | The staged harness replaced required platform environment state | Child startup failed before repository import and masked the intended proof | `tests/test_signal_seat_launcher.py` | Sanitized inherited base, scoped deletions, explicit staged overrides, timeout | Raw launcher corpus passes 9/9 |

For every row, confirm the named regression is behaviorally tied to its control. A temporary local
mutation may be used to show the pin turns red, but restore the tree before writing `result.md` and
report only the pass/fail result—not a reusable mutation or bypass recipe. The timing-sensitive
one-use control requires at least three consecutive green runs.

## Construction and scope properties

Re-derive these additional R5a properties:

1. With the flag on, `create_app` applies launch authority, validated credential/config, and
   conforming rails guards in the specified order before returning an app.
2. The module-level `app` name is absent under the flag, so the unsupported bare server load fails
   before a listener opens; the exact pre-bind diagnostic remains pinned for both lifespan modes.
3. The sanctioned launcher revalidates a loopback/UDS bind under both allowed transport policies;
   non-private binds exit nonzero with the A-1 reason.
4. Flag off preserves the existing construction and bootstrap path.
5. The R5a helper cannot supply flag-on construction without exact explicit in-process test
   authority, while authorized local tests still construct.
6. `app/facade/signal_rails.py` remains a seam only. The real provider is R6; no permissive test
   provider is production-selectable.
7. The range contains no R5b middleware/routes/deps/schemas/cockpit/`.importlinter` expansion, no R6
   provider, no R7 conversion, no schema/event-log change, and no flag enablement.

Archive REV-0027 found A-1 launch/bind, credential role separation, exact settings validation,
rails presence/conformance, and flag-off behavior sound. Reverify those properties independently.
REV-0027 F-1 (request-time operator principal binding), F-2 (quarantine normalization), and F-3
(malformed identity namespace) belong to later R5b/R7 surfaces; report any appearance here as scope
leakage rather than absorbing or fixing it in R5a.

## D1/D2/D3 disposition boundary

- D1 changes only launcher-test environment plumbing and `_run` timeout. All bind, UDS, exit-code,
  no-listener, and exact diagnostic assertions/scenarios must remain semantically unchanged.
- D2 changes the test helper and its legitimate callers, plus local rejection coverage. It does not
  create a production authority path.
- D3 formats/checks the eleven R5a-owned Python paths only. Repository-wide Ruff diagnosis must name
  exactly the ten inherited baseline files recorded in `SIGNAL-R5a-STATE.md`; none may be edited.
  A separate formatter-cleanup WO remains unnumbered follow-up work.
- The R2 oracle content is unchanged and runs through the CI module invocation.

No `INV-*` definition was added or amended in this range.

## Author evidence to reproduce skeptically

- Raw config/launcher/guard corpus: 50 passed; launcher subset: 9/9.
- R5a plus import-boundary corpus: 56 passed.
- Named exact-type/identity/one-use controls: 6 passed; the one-use control also passed three
  consecutive isolated runs.
- `ruff check .`: `All checks passed!`
- R5a Ruff format check: `11 files already formatted`.
- `mypy app/`: `Success: no issues found in 74 source files`.
- `lint-imports`: 6 kept, 0 broken.
- CI-form R2 oracle: 61 passed.
- Repair scaling: 13 passed.
- `python harness/bootstrap.py`: exit 0; 4,327 tests collected on the flag-off path.
- Additional full pytest non-regression: 4,327 collected, progress reached 100%, exit 0.
- `git diff --check`: pass; implementation commit changes only five authorized files.

Use normal OS temporary space for pytest. Restricted-sandbox attempts that cannot access the
Windows pytest temp root are environment failures, not passing evidence; reproduce the exact
commands in an environment where fixtures can run.

## Curated targets and exclusions

Implementation: `app/config.py`, `app/launch_guard.py`, `app/server.py`, `app/__main__.py`,
`app/main.py`, and `app/facade/signal_rails.py`.

Regressions: `tests/test_signal_seat_config.py`, `tests/test_signal_seat_launcher.py`,
`tests/test_signal_seat_launch_guard.py`, `tests/signal_seat_helpers.py`, and
`tests/test_import_boundaries.py`.

State/contract: `work/active/WO-0137-signal-r5a-composition-root-foundation.md` and
`work/active/SIGNAL-R5a-STATE.md`.

Out of scope: R5b request-time auth/routes/middleware/deps/schemas/facade/cockpit work, R6 rails
provider, R7 conversion, schema/migration, event-log truth, broker/live behavior, real credential
material/access, ledger, merge, PR, close-out, and fixes by the reviewer.

## Expected output

Write findings only to `work/review/REV-0041/result.md`, followed by one verdict. `BLOCK` any safety
invariant breach, enabled construction without exact fresh one-use authority, non-private enabled
bind, selectable unauthorized factory, weakened or inert decisive regression, unapproved scope
expansion, or completion evidence that cannot be reproduced.
