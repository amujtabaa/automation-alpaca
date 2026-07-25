# Codex kickoff — Signal Seat R5b-1: producer ingest surface (LOCAL, strongest model)

> Operator launch prompt, drafted by the planning seat 2026-07-25. Paste into a FRESH **local** Codex
> session at the repo root, strongest model, full effort. R5b-1 is a human-gated auth surface (first
> authenticated external input path) → strongest local model.
>
> The decision block below is the **M1 assumption ledger** of a FULL `.ai-os/core/18` war-game whose
> **M4b refutation pass refuted 8 of rev-1's 14 lines**, including two P0 findings. The planning seat
> verified every blocking finding directly against code, then **split R5b** and rewrote the block.
> Pasting it unedited RATIFIES rev-2.

---

Codex, you are the implementer seat building **WO-0138 — Signal Seat R5b-1**, the producer ingest
surface. Read `AGENTS.md`, the `CLAUDE.md` safety core, then
**`work/queue/WO-0138-signal-r5b1-producer-ingest-surface.md` IN FULL** — it is your contract (M1
decision block, M2 ingest-outcome table, M3 consumer inventory, the §M4b refutation record, the
verified BUILD HAZARDS, allowed/forbidden paths, stop conditions). Fable v3: GATE, red-first, fresh
pasted evidence, FIX blocks with root cause. No completion claims without evidence.

## Authorized defensive scope (read first)

This is **authorized defensive engineering on the operator's own local, paper-only trading
application, in the operator's own repository.** The task is to make the app's local API require a
local producer credential before it accepts a trade *suggestion*, and to bind that suggestion's
identity server-side so one local producer process cannot impersonate another. There is **no external
target, no network probing, no credential access, no live trading, no persistence objective**.

**Reporting convention for this surface:** name the defect class, express each control as a local
regression test, and report at the defect level — cause · impact · affected local files · fix ·
pass/fail evidence. Do **not** write reusable bypass procedures or exploit payloads in code, comments,
commit messages, or the review request. Known defect-class vocabulary: *incorrect type acceptance*,
*identity-validation defect*, *non-atomic one-use validation*, *capability reacquisition via importable
factory*. **Do not run an open-ended "try to break it" adversarial-discovery pass** — the independent
**REV-0042 Claude-seat review is the sanctioned adversarial net** for this surface.

## What R5b-1 is, and what it deliberately is NOT

R5a made `create_app` **refuse to construct** without a launch capability, valid config, and
conforming rails. **R5b-1 adds one authenticated route and one facade — nothing else.**

**IN:** the typed `StoreBackedSignalFacade` (absent on master) + protocols; `app/api/routes_signals.py`
with **`POST /api/signals` ONLY**; the **producer-key** auth dependency + server-side identity binding
in `app/api/deps.py`; the `.importlinter` contract-5 line; the staged producer/ingest + facade-read
corpus.

**NOT IN — this is WO-0139 (R5b-2), do not build it:** operator-key enforcement on any route,
principal stamping, `get_actor` changes, the recovery-route actor migration, `GET /api/signals`,
`/api/producers`, the mounted-route authorization matrix, auto-docs handling, cockpit plumbing,
`.env.example`. **NOT IN — later rungs:** R6 rails enforcement (429/ceiling/budget/release), R7
approve/reject + conversion.

**⚠ R5b-1 alone does NOT satisfy GAP-01 or GAP-02.** Under the flag, sensitive reads stay unprotected
until R5b-2. That is safe only because **the flag stays OFF** — D-2a now needs R5b-1 + R5b-2 + R6 + R7.
Never present R5b-1 as completing the auth surface.

## Setup — verify the predecessor gate FIRST, then work

- **Step 0 (execute yourself):**
  1. `git status --short` — clean, else STOP.
  2. `git fetch origin`.
  3. **HARD GATE:** `git ls-tree master app/launch_guard.py` must return a blob. R5a was **unmerged**
     when this WO was drafted; if this returns nothing, **STOP** — the operator must merge R5a
     (`codex/signal-r5a-foundation`) and the planning branch first. Do not branch from an R5a-less
     master; the corpus will not run.
  4. `git checkout -b codex/signal-r5b1-producer-ingest origin/master`.
  5. `git fetch origin codex/signal-tests-staging archive/claude-wo-0001-install-checks-2x5ys8` (the
     staged corpus, and the archive design reference you read but never port verbatim).
- Never push master. No PR unless asked. Paper-only; zero credentials/broker/live. Pytest scratch in
  OS temp, never repo-root.

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

## ⚠ BUILD HAZARDS (verified — these bite a verbatim archive port)

1. **`build_flag_on_app` changed under the corpus's feet.** R5a added a **required** keyword-only
   `test_authority` that must be the **private** module sentinel `_IN_PROCESS_TEST_AUTHORITY`. Staged
   `test_signal_routes.py:53` and `:360` call it **without** it → both fail. Import the private
   sentinel at every ported call site.
2. **Archive imports that do not exist on master:** archive `app/api/deps.py:15` imports
   `app.facade.signals` — **that module is what you are building**. `effective_signal_status` exists
   **nowhere** (author it); `classify_signal_freshness` is `app/store/core.py:5806` (not `app.models`);
   `SIGNAL_REPLAYED` is `app/store/core.py:5587`.
3. **`received_at` is required keyword-only** (`app/store/base.py:1332`) — the staged corpus omits it
   in 6 places.
4. Read the archive `routes_signals.py`/`deps.py` as **design reference only**. Never port verbatim.

## Continuity across pauses and compaction

**FIRST commit** (with WO activation → ACTIVE, move to `work/active/`): create
`work/active/SIGNAL-R5b1-STATE.md` carrying (a) this decision block **verbatim as pasted**, (b) a
slice scoreboard (facade · ingest route · producer auth + identity binding · spec-413 amendment ·
contract-5 · flag-off non-regression · green evidence · REV-0042 staging), (c) an evidence log. Update
it at every slice boundary. After any pause/compaction re-read, in order: this kickoff → the state
file → the WO. Verify with `git log`/`git status`, never memory.

## Order of work (red-first each slice)

1. Predecessor gate + branch + corpus import with the two authorized repairs → prove RED.
2. `StoreBackedSignalFacade` + protocols → `test_signal_facade_reads.py` green on both stores.
3. Producer-key auth dependency + server-side identity binding (D-R5b1-4).
4. `POST /api/signals` body-blind handler: 64 KiB cap → 413, manual validation, the full M2 outcome
   table (201 / 200 replay / 409 conflict / 422 quarantine / 400 / 401-no-event / 403 quarantined).
5. Spec §2 413 amendment (D-R5b1-6) + the producer-map container regression pin (D-R5b1-7).
6. `.importlinter` contract-5 line; `lint-imports` green.
7. Flag-off non-regression: 404, zero existing-test edits, bootstrap green.

## Gate battery (fresh, pasted — all of it)

`ruff check .` · `ruff format --check` on your own files (the **10 inherited baseline files stay
grandfathered — do not reformat them**) · `mypy app/` · `lint-imports` · your corpus + the full suite ·
`python -m pytest -q tests/r2_conformance_oracle.py` (**CI's invocation** — the documented
`python tests/…` form fails on `ModuleNotFoundError: app`) · `pytest -q tests/test_wo0113_repair_scaling.py`
· `python harness/bootstrap.py`.

## Stop conditions — report, never self-authorize

Any accepted-text conflict beyond D-R5b1-6's recorded 413 resolution · any need to weaken a staged
assertion · a staged-test edit beyond the two authorized mechanical repairs · anything that would make
the flag independently enable-able · **any** operator-auth / `get_actor` / cockpit / existing-route
behavior change (that is WO-0139) · any schema/migration or event-log truth change · a P0-equivalent
hole in accepted text.

## Close-out

Human-gated ⇒ set WO-0138 to **REVIEW** and stage `work/review/REV-0042/request.md` (defect-level,
named defect classes, no exploit narration; **carry the spec-§2 413 amendment for explicit review**).
Do **NOT** create `result.md` (reviewer-owned), touch the ledger, move to completed, merge, open a PR,
or enable the flag. Push `codex/signal-r5b1-producer-ingest` to origin.

**Report in your final summary:** the delivery branch + SHA, a defect-class table for any defect you
fixed, the full pasted gate evidence, and anything you had to STOP on.
