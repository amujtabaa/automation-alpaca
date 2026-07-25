---
type: Work State
work_order_id: WO-0138
status: CLOSED
branch: codex/signal-r5b1-producer-ingest
updated: 2026-07-25
---

# Signal R5b-1 state

## Continuity

After any pause or compaction, re-read in order:

1. The operator kickoff.
2. This state file.
3. `work/completed/keep/WO-0138-signal-r5b1-producer-ingest-surface.md`.

Then verify the live branch and worktree with `git log` and `git status`; do not reconstruct state
from conversation memory.

## Fable gate

```yaml
fable_gate:
  goal: "Ship the authenticated, server-identity-bound POST /api/signals ingest path only."
  assumptions:
    - "The operator ratified the NEEDS-INPUT disposition and rev-3 ingest-only scope."
    - "All read-side facade methods, lazy expiry, GET /api/signals, and test_signal_facade_reads.py are R5b-2."
    - "Operator-key recognition is allowed only for wrong-role 403 on the producer POST."
    - "app/api/schemas.py is allowed only for additive signal DTOs."
    - "The feature flag remains OFF; permissive rails remain test-authority-only."
  approach: "Import only response/event-log-terminating ingest tests, prove RED, implement the minimal write facade/auth/route/schema slices, run the complete gate battery, stage REV-0042, and push only the delivery branch."
  out_of_scope:
    - "Signal read methods/routes, lazy-expiry behavior, operator middleware/principal/get_actor, cockpit, GET/list/approve/reject/release."
    - "R6 rails enforcement, R7 conversion, DB schema/migration, event-log truth changes, flag enablement."
  done_when:
    - "The ingest corpus passes without weakened assertions."
    - "Body-blind auth, 64 KiB cap, identity binding, full ingest M2 outcomes, 413 spec amendment, and import boundary are proven."
    - "Flag-off behavior and all named gates pass with fresh evidence."
    - "WO is REVIEW, REV-0042 request exists, branch is pushed; no PR/result/ledger/completion move."
  blast_radius: "Additive signal DTOs, write-only facade, producer auth dependency, one flag-gated POST route, one spec row, one import-linter line, ingest tests, and lifecycle artifacts; zero existing-route behavior change."
```

## Rev-3 controlling disposition

The operator ratified
`work/queue/SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md` after commit `5402ed7`.
Master merge `ae87354` was pulled and merged into this branch. The rev-3 scope in the active WO
supersedes the historical pasted rev-2 ledger below wherever they differ:

- R5b-1 is **ingest-only**.
- Do not import `tests/test_signal_facade_reads.py`.
- Move every ingest test that reads through `GET /api/signals` to R5b-2 without rewriting it.
- Recognize the operator key only to return wrong-role 403 on `POST /api/signals`.
- `app/api/schemas.py` is allowed for additive signal DTOs only.
- Lazy expiry and its event-log-truth decision are entirely R5b-2; ingest-time dead-on-arrival
  remains R5b-1.

## Decision block (M1 war-game ledger, rev-2 post-M4b; pre-checked = ratified on paste; edit to override)

Every line is `TRACED` or `INHERITED`; anchors are in the WO. **No `ASSUMED` line is pre-checked.**

- [x] **D-R5b1-1 HARD predecessor gate — R5a merged first** (Step 0.3). Branch from the merged master.
- [x] **D-R5b1-2 Corpus, and it is INCOMPLETE.** Pull the **producer/ingest subset** of
      `tests/test_signal_routes.py` + all of `tests/test_signal_facade_reads.py` from
      `origin/codex/signal-tests-staging`. The staged route file is **truncated at byte 14628, ending
      mid-comment (`# The forged X-Ac`)** inside
      `test_operator_command_audit_actor_is_principal_not_forged_x_actor` — it parses, collects, and
      **PASSES while asserting nothing about the actor**. That test is **R5b-2's**; do NOT import it
      and do NOT treat the file as a trustworthy floor. **Two authorized mechanical repairs**
      (additions, never weakenings) to the cases you do import: (1) add the required `received_at=`
      kwarg to the 6 `store.ingest_signal(...)` call sites (`app/store/base.py:1332`); (2) import
      `SIGNAL_REPLAYED` from `app.store.core` (`:5587`), not `app.models`.
- [x] **D-R5b1-3 Approve/reject are R7's, NOT yours.** Accepted rule **A2** — `SIGNAL_APPROVED` is
      written **only if** conversion succeeds in the same store operation; **there is no
      approved-but-unconverted state** — and **A1** makes APPROVED latching. R7 owns conversion, so any
      approve stub either violates A2 or returns an undocumented status. Spec `04:71` independently
      assigns approval-route negative tests to WO-0103/0104. **Mount `POST /api/signals` only.**
- [x] **D-R5b1-4 Producer identity is server-side ONLY.** `producer_id` derives from the presented key
      via the config map, server-side, always. Unknown key → **401 with NO event append**
      (unattributable). A body `producer_id` mismatching the key-derived identity is rejected **before**
      any namespace accounting; every dedupe/rate/budget/quarantine/audit key uses the authenticated
      producer namespace.
- [x] **D-R5b1-5 Body-blind auth ordering (A-4) — empirically verified.** Do **NOT** declare a Pydantic
      body parameter: for body-model routes FastAPI reads the body **before** dependencies can reject
      (measured on pinned fastapi 0.139.0/starlette 1.3.1: body-model sequence
      `[BODY_READ, STREAM, BODY_READ, AUTH]` vs raw-`Request` `[AUTH]` only). Use the raw `Request`,
      auth as a dependency with no body access, then stream under a **64 KiB cap** and validate
      `SignalProposal` manually.
- [x] **D-R5b1-6 The cap returns 413 — a RECORDED spec conflict you must resolve, not hide.** The staged
      test asserts **413**; the accepted spec `04 §2` table documents 201/200/400/401/403/409/422/429
      and **not 413**. Keep 413 (correct semantics; the corpus is right) and **add it to the spec §2
      fragment in the same change**, flagged for REV-0042 as a spec amendment. Do not weaken the test.
- [x] **D-R5b1-7 R5b-N1 is ALREADY CLOSED by R5a — regression pin only.** REV-0041 asked R5b to
      re-derive a trusted `dict` at the auth seam. That premise is **stale**: R5a's
      `Settings.__post_init__` (`app/config.py:301-317`) copies any `Mapping` into a plain `dict` then
      wraps it, on **every** construction including direct injection, and `:449` rejects non-`Mapping`.
      Your obligation is only a **regression pin** asserting the normalized container type at the
      request-time lookup (*incorrect type acceptance*). Do not build a re-derivation.
- [x] **D-R5b1-8 GAP-05, API half only.** `thesis`/`provenance` preserved **verbatim** for audit, never
      interpreted; validation/error paths must not echo credential material. No cockpit signal panel
      exists yet (spec `04 §3` → WO-0103/0104), so there is nothing to harden client-side here.
- [x] **D-R5b1-9 Import-boundary contract 5, SAME change.** Add `app.api.routes_signals` to contract-5
      `source_modules`; reach the backend **only** through the typed signal facade (never `app.store`/
      `app.events`, never `get_store`). `ignore_imports` is **OMITTED, not empty** — writing
      `ignore_imports =` breaks the build. Contract 6 stays green.
- [x] **D-R5b1-10 Dual-store parity; 6 staged cases are R4 pins, not your criteria.** `any_store`
      really parameterizes `["memory","sqlite"]` (`tests/conftest.py:28-49`) — lazy TTL expiry on read,
      list reclassification/filtering, and no-mutation-on-read are mandatory on **both**. The six
      store-level cases in that file exercise the **R4 store**; carry them forward as R4 regression
      pins and do not treat an R4 failure as an R5b defect.
- [x] **D-R5b1-11 Flag stays OFF; flag-off byte-equivalent.** Route not mounted when off (404);
      existing localhost no-auth posture unchanged; **no existing test may need editing**;
      `harness/bootstrap.py` green. Leave `get_actor` **untouched** — it is R5b-2's file, and the
      archive variant's unconditional `X-Actor` character stripping is a flag-independent behavior
      change.
- [x] **D-R5b1-12 Rails = the permissive fake via the test seam ONLY.** It satisfies the rails-
      **presence** guard so ingest is testable without R6; it stays unselectable from production
      config/environment (A-4), under the explicit in-process test-authority discipline REV-0041
      established. Rails **enforcement** (429/ceiling/budget) is R6's; you wire the seam and honor an
      existing quarantine state (403) only.

## Slice scoreboard

| Slice | Status | Evidence |
|---|---|---|
| Activation / predecessor gate | GREEN | Clean worktree; refreshed origin; `launch_guard.py` blob present; branch created from `origin/master`. |
| Read facade | MOVED TO R5b-2 | Entire facade-read corpus, list/get methods, read clock, effective status, and lazy expiry moved by rev-3. |
| Ingest route | GREEN | 49 response/event-log-terminating ingest tests pass; no GET signal route or read facade imported. |
| Producer auth + identity binding | GREEN | Producer-map identity, wrong-role 403, no-event rejects, and zero-read auth/rails probes pass. |
| Spec 413 amendment | GREEN | `04-auth-and-api.md` now records 413 + no event for the 64 KiB cap. |
| Contract 5 | GREEN | `routes_signals` added; 6 kept / 0 broken. |
| Flag-off non-regression | GREEN | Route-off 404 pin, full 4,377-test run, and bootstrap collection all pass. |
| Green gate evidence | GREEN | Complete post-F-1 WO battery passed with fresh terminal evidence. |
| REV-0042 | ACCEPT — GATE CLEARED | Initial BLOCK preserved; addendum 01 independently accepted the F-1 remediation and pins at `472de42`. |
| Close-out | CLOSED | Disposition RESOLVED; result summary kept; PKL and append-only ledger updated; files moved to `work/completed/keep/`. |

## Historical stop record — RESOLVED by rev-3

The operator disposition resolves all five items below. They remain here as the durable reason for
the ingest-only re-scope and must not be re-opened or silently pulled back into R5b-1.

No production or test corpus file was imported or edited. The bounded read-only corpus/design pass
found accepted-text conflicts beyond D-R5b1-6's pre-authorized 413 amendment:

1. `tests/test_signal_facade_reads.py` on staging commit `24d3746` has **8** raw-store
   `ingest_signal` calls missing the required keyword-only `received_at`, at lines
   52, 235, 261, 269, 292, 293, 302, and 320. The ratified decision block authorizes 6.
   Minimal repair needs 7 source insertion points because lines 292/293 share `common`.
2. The staged producer/ingest tests for distinct malformed identities, identical malformed replay,
   and unparseable-body/no-event prove their postconditions through operator-authenticated
   `GET /api/signals`. R5b-1 explicitly forbids mounting that R5b-2 route. Replacing those
   observations with direct store checks would edit staged tests beyond the authorized repairs;
   omitting them would make the promised producer/ingest subset and M2 proof incomplete.
3. The staged producer-auth test requires a valid operator key on `POST /api/signals` to return 403,
   while the R5b-1 scope defers operator-key enforcement on any route. A producer-only extraction
   would require splitting/editing that staged test.
4. `SignalProposal` is absent on current master. Accepted
   `docs/spec/signal-seat/01-schema.md` requires it in `app/api/schemas.py`, but that file is absent
   from the literal R5b-1 IN list. Defining the model inside `routes_signals.py` would diverge from
   accepted text; editing the mandated schema file needs an explicit scope correction.
5. Accepted `docs/spec/signal-seat/02-lifecycle.md` says `SIGNAL_EXPIRED` is emitted for
   lazy-expiry and names `detected_by: "read"`, while WO-0138 and the staged dual-store tests require
   lazy reads to return an effective EXPIRED copy **without mutating durable state**. Appending the
   named lifecycle event on read would mutate event-log truth; suppressing it silently chooses one
   side of an accepted-text conflict.

Planning/operator decisions needed before RED:

- Correct the authorized `received_at` repair count to all 8 raw-store calls.
- Authorize direct-store observation equivalents for the three mixed ingest tests, or define a
  different complete R5b-1 corpus that does not mount GET.
- Decide whether wrong-role operator-key detection on the producer route belongs in R5b-1.
- Add `app/api/schemas.py` to the allowed scope.
- Amend/reconcile the lazy-read `SIGNAL_EXPIRED` event wording versus the no-mutation-on-read
  contract.

```yaml
fable_done:
  task: "WO-0138 Signal R5b-1 implementation"
  done_when_results:
    - "NOT_MET: corpus import cannot be completed within the ratified edit boundary"
    - "NOT_MET: production implementation intentionally not started"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "staging facade AST: 8 raw-store calls omit received_at"
    - "staging route source: 3 ingest tests depend on GET /api/signals"
    - "accepted schema path and lazy-expiry event text checked directly"
  status: NEEDS-INPUT
```

## Evidence log

### 2026-07-25 — activation

```yaml
- evidence:
    command: "git status --short"
    result: PASS
    decisive_output: "empty output"
- evidence:
    command: "git fetch origin"
    result: PASS
    decisive_output: "exit 0"
- evidence:
    command: "git ls-tree master app/launch_guard.py"
    result: PASS
    decisive_output: "100644 blob 8834d8a2ab1dbdd743de452987afe442d6c13be5 app/launch_guard.py"
- evidence:
    command: "git checkout -b codex/signal-r5b1-producer-ingest origin/master"
    result: PASS
    decisive_output: "branch created and tracking origin/master"
- evidence:
    command: "git fetch origin codex/signal-tests-staging archive/claude-wo-0001-install-checks-2x5ys8"
    result: PASS
    decisive_output: "both named refs fetched"
```

### 2026-07-25 — corpus preflight stop

```yaml
- evidence:
    command: "AST inventory of origin/codex/signal-tests-staging:tests/test_signal_facade_reads.py"
    result: FAIL
    decisive_output: "RAW_STORE_MISSING=8 at lines 52,235,261,269,292,293,302,320; contract says 6"
- evidence:
    command: "source inventory of staged tests/test_signal_routes.py"
    result: FAIL
    decisive_output: "3 producer/ingest tests require deferred GET /api/signals; producer auth test mixes operator-key behavior"
- evidence:
    command: "rg class SignalProposal in app plus docs/spec/signal-seat/01-schema.md"
    result: FAIL
    decisive_output: "model absent; accepted path app/api/schemas.py is outside literal IN list"
- evidence:
    command: "cross-check docs/spec/signal-seat/02-lifecycle.md:31-47 against staged facade no-mutation assertions"
    result: FAIL
    decisive_output: "accepted event row includes lazy read, while WO/tests require read-only effective status"
```

### 2026-07-25 — rev-3 resume

```yaml
- evidence:
    command: "git pull --ff-only origin master"
    result: PASS
    decisive_output: "Already up to date at ae87354"
- evidence:
    command: "git merge --no-edit master"
    result: PASS
    decisive_output: "rev-3 disposition and amended WO merged into delivery branch"
- evidence:
    command: "re-read active WO-0138 rev-3 and SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md"
    result: PASS
    decisive_output: "ingest-only scope ratified; prior NEEDS-INPUT resolved"
```

### 2026-07-25 — ingest corpus RED

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_routes.py --basetemp <OS temp> -p no:cacheprovider"
    result: FAIL
    decisive_output: "1 passed, 14 failed; every flag-on ingest assertion received 404 from the absent route"
```

### 2026-07-25 — ingest implementation and M2 GREEN

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_routes.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "38 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m ruff check ."
    result: PASS
    decisive_output: "All checks passed"
- evidence:
    command: ".venv/Scripts/python.exe -m ruff format --check <R5b-1-owned Python files>"
    result: PASS
    decisive_output: "7 files already formatted"
- evidence:
    command: ".venv/Scripts/python.exe -m mypy app/"
    result: PASS
    decisive_output: "Success: no issues found in 77 source files"
- evidence:
    command: ".venv/Scripts/lint-imports.exe"
    result: PASS
    decisive_output: "Contracts: 6 kept, 0 broken"
```

## FIX blocks

### FIX-R5B1-01 — missing authenticated producer ingest surface

- **Root cause:** R5a intentionally stopped at construction controls; no producer route, API DTO,
  or typed write facade existed, so every flag-on ingest returned 404.
- **Impact:** no external proposal could be authenticated, identity-bound, or recorded.
- **Files:** `app/api/routes_signals.py`, `app/api/deps.py`, `app/api/schemas.py`,
  `app/facade/signal_commands.py`, `app/facade/signals.py`, `app/main.py`.
- **Fix:** add one flag-gated POST route, strict/manual DTO validation, server-derived producer
  identity, body-blind rails ordering, capped streaming, and a write-only facade.
- **Evidence:** RED `1 passed, 14 failed` (all flag-on 404) → GREEN `38 passed`.

### FIX-R5B1-02 — incomplete failure-path proof

- **Root cause:** the staged corpus's mixed read-back cases belonged to R5b-2, leaving R5b-1
  without independent event-log proof for all ingest outcomes and boundary rejects.
- **Impact:** a superficially green HTTP corpus could miss unwanted appends, body-before-auth
  reads, replay writes, or conflict mutation.
- **Files:** `tests/test_signal_routes.py`.
- **Fix:** add failure-capable event-log and ASGI receive-probe controls without importing or
  rewriting the moved GET-based tests.
- **Evidence:** M2 cases prove recorded validation/DOA expiry, write-free replay, audit-only
  conflict, no-event 400/401/403/413/mismatch, and zero body reads before auth/rails.

### FIX-R5B1-03 — undocumented oversized-body outcome

- **Root cause:** accepted API text omitted the staged corpus's required 413 response.
- **Impact:** implementation and normative response contract would diverge on the hostile-body cap.
- **Files:** `docs/spec/signal-seat/04-auth-and-api.md`.
- **Fix:** add the pre-authorized 413/no-event response row; carry it explicitly into REV-0042.
- **Evidence:** oversized-body response/event-log test passes; spec diff contains the 413 row.

### FIX-R5B1-04 — producer symbol wire-domain drift

- **Root cause:** the shared store normalizer intentionally accepts digits and hyphens, while the
  accepted SignalProposal wire contract is narrower (`[A-Z.]+`).
- **Impact:** producer proposals with `A1` or `BRK-B` were recorded as valid despite violating the
  signal-specific schema.
- **Files:** `app/api/schemas.py`, `tests/test_signal_routes.py`.
- **Fix:** enforce the signal-only wire alphabet after canonical uppercasing, without narrowing the
  shared store's domain.
- **Evidence:** RED `2 failed` (`201` instead of `422`) → GREEN route corpus `38 passed`.

### FIX-R5B1-05 — issued_at boundary overflow on producer ingest (REV-0042 F-1)

- **Defect level:** P0 — BLOCKING.
- **Defect class:** unbounded trust-boundary timestamp causing an unhandled exception, loss of
  outcome totality, and loss of audit attribution.
- **Root cause:** `expires_at` arithmetic preceded the future-skew test, so an accepted
  `issued_at` near `datetime.max` could overflow before the route received a typed ingest outcome.
  The validation-fallback helper admitted the same timestamp, exposing the same ordering defect on
  validation failures.
- **Impact:** an authenticated, parseable producer proposal could terminate without an HTTP outcome,
  signal record, or event.
- **Files:** `app/api/schemas.py`, `app/api/routes_signals.py`,
  `tests/test_signal_routes.py`.
- **Fix:** normalize `issued_at` to UTC and admit only the inclusive API wire range
  `[datetime.min + 1 day, datetime.max - 86400 seconds]`; apply the same predicate to the
  validation-fallback extractor so out-of-range values become `None` and are recorded as validation
  quarantines. The exact inclusive upper instant is normalized before existing freshness arithmetic.
  `app/store/core.py` remains untouched.
- **Evidence:** RED route corpus: 3 F-1 failures, all `OverflowError` (otherwise-valid,
  validation-fallback, and offset-form upper boundary) → GREEN route corpus: `49 passed`.

### 2026-07-25 — full gate battery and review staging

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q <signal/store/launch batch> --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "136 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/r2_conformance_oracle.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "61 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_wo0113_repair_scaling.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "13 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "4,366 collected; 100%; exit 0; 11 skipped; 1 expected xfail; 353.9 s"
- evidence:
    command: ".venv/Scripts/python.exe harness/bootstrap.py"
    result: PASS
    decisive_output: "exit 0; Ruff/mypy/collection completed; 4,366 tests collected"
    note: "restricted-network pip retries were non-fatal because dependencies were already satisfied"
- evidence:
    command: "git diff --check"
    result: PASS
    decisive_output: "empty output"
```

An earlier pre-final full-suite orchestration attempt was terminated by its 120-second command
allowance and is not counted as evidence. The final-SHA run above completed normally.

### 2026-07-25 — REV-0042 F-1 remediation gate battery

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_routes.py --basetemp <OS temp> -p no:cacheprovider"
    result: FAIL
    decisive_output: "RED: 3 F-1 cases raised OverflowError; every F-2–F-7/F-9 pin held"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_routes.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "49 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m ruff check ."
    result: PASS
    decisive_output: "All checks passed"
- evidence:
    command: ".venv/Scripts/python.exe -m ruff format --check <R5b-1-owned Python files>"
    result: PASS
    decisive_output: "7 files already formatted"
- evidence:
    command: ".venv/Scripts/python.exe -m mypy app/"
    result: PASS
    decisive_output: "Success: no issues found in 77 source files"
- evidence:
    command: ".venv/Scripts/lint-imports.exe"
    result: PASS
    decisive_output: "Contracts: 6 kept, 0 broken"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q <signal/store/launch batch> --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "147 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/r2_conformance_oracle.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "61 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_wo0113_repair_scaling.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "13 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "4,377 collected; 100%; exit 0; 11 skipped; 1 expected xfail; 386.9 s"
- evidence:
    command: ".venv/Scripts/python.exe harness/bootstrap.py"
    result: PASS
    decisive_output: "exit 0; Ruff/mypy/collection completed; 4,377 tests collected"
    note: "restricted-network pip retries were non-fatal because dependencies were already satisfied"
- evidence:
    command: "git diff --check"
    result: PASS
    decisive_output: "empty output"
```

## Review handoff

- Frozen semantic base: `ae87354f3ca82439df227830747d3df9b9cab506`.
- Frozen implementation head: `f5aaf7a0bd4055161018bdb80c1caaa41caf7293`.
- Review request: `work/review/REV-0042/request.md`.
- Reviewer result: `work/review/REV-0042/result.md`, verdict **BLOCK** on F-1; preserved
  byte-for-byte from reviewer commit `41e1155`.
- Reviewer addendum: `work/review/REV-0042/result-addendum-01.md`, final verdict **ACCEPT** at
  `472de422c67cb14a9d0d21517031cdfe619e74b4`; review gate cleared.
- F-1 remediation head: `a92c8b86323d4ed1bd41a9e04a5bce675bcf226f`.
- Review disposition: `work/review/REV-0042/disposition.md`, RESOLVED.
- The explicitly reviewed 413/no-event response row remains accepted.
- Close-out includes the append-only ledger line, Signal Seat PKL changelog, and moves to
  `work/completed/keep/`; no merge, PR, flag enablement, or WO-0139 edit was performed.

```yaml
fable_done:
  task: "WO-0138 rev-3 Signal R5b-1 producer ingest implementation"
  done_when_results:
    - "MET: ingest-only corpus passes without importing or rewriting the moved GET/read corpus"
    - "MET: body-blind auth/rails, identity binding, 64 KiB cap, M2 outcomes, and ingest-time expiry proven"
    - "MET: 413 amendment and contract-5 ratchet applied"
    - "MET: complete gate battery passes with fresh evidence"
    - "MET: WO status REVIEW and REV-0042 request staged"
    - "MET: REV-0042 addendum 01 returned final ACCEPT and the close-out artifacts are atomic"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
    wo_0139_untouched: true
  status: CLOSED
```
