---
type: Work State
work_order_id: WO-0138
status: ACTIVE
branch: codex/signal-r5b1-producer-ingest
updated: 2026-07-25
---

# Signal R5b-1 state

## Continuity

After any pause or compaction, re-read in order:

1. The operator kickoff.
2. This state file.
3. `work/active/WO-0138-signal-r5b1-producer-ingest-surface.md`.

Then verify the live branch and worktree with `git log` and `git status`; do not reconstruct state
from conversation memory.

## Fable gate

```yaml
fable_gate:
  goal: "Add the first authenticated producer-ingest route and typed signal facade, with server-bound producer identity."
  assumptions:
    - "The pasted rev-2 decision block is ratified; no ASSUMED lines remain."
    - "R5a is merged: the required launch_guard blob gate passed on refreshed master."
    - "Only the staged producer/ingest subset plus facade-read corpus is authoritative here, with exactly the two named mechanical repairs."
    - "The feature flag remains OFF; permissive rails remain test-authority-only."
    - "413 is the one pre-authorized accepted-text amendment and must be reviewed explicitly."
  approach: "Activate WO/state first, then run each facade/auth/route slice RED to GREEN, update evidence at every boundary, run the complete gate battery, stage REV-0042, and push only the delivery branch."
  out_of_scope:
    - "Operator authentication, get_actor/principal changes, existing-route behavior, route matrix, docs gating, cockpit, GET/list/approve/reject/release."
    - "R6 rails enforcement, R7 conversion, schema/migration, event-log truth changes, flag enablement."
  done_when:
    - "Dual-store facade and producer-ingest corpus pass without weakened assertions."
    - "Body-blind auth, 64 KiB cap, identity binding, full M2 outcomes, 413 spec amendment, and import boundary are proven."
    - "Flag-off behavior and all named gates pass with fresh evidence."
    - "WO is REVIEW, REV-0042 request exists, branch is pushed; no PR/result/ledger/completion move."
  blast_radius: "Additive route/facade/auth dependency plus one spec row, one import-linter line, staged tests, WO/state/review artifacts; zero existing-route behavior change."
```

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
| Facade | PENDING | — |
| Ingest route | PENDING | — |
| Producer auth + identity binding | PENDING | — |
| Spec 413 amendment | PENDING | — |
| Contract 5 | PENDING | — |
| Flag-off non-regression | PENDING | — |
| Green gate evidence | PENDING | — |
| REV-0042 staging | PENDING | — |

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
