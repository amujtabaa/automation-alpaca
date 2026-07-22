---
type: Review Result
rev_id: REV-0039
reviewer: "Claude (independent seat; implementer Codex)"
commit_range: 9d60b74dcc3ef5d5dcc2a09899dd7395dbf2a6dc..b87d464cdf189e345b688a01cfbc9c18f8bc9d05
branch: codex/signal-r4-store (reviewed at 58b4296; semantic head b87d464)
verdict: ACCEPT-WITH-CHANGES
date: 2026-07-22
---

# REV-0039 — independent review of WO-0134 (Signal Seat R4 model + store integration)

Environment: pinned Python 3.12.3 venv from `harness/bootstrap.py` (`.venv`), cloud
container (Linux), ruff 0.15.20 / mypy 2.2.0 / pytest 9.1.1 / hypothesis 6.156.4 per
`constraints.txt`. All pytest scratch under an isolated OS-temp basetemp; all probes are
throwaway scripts outside the repo; every mutation restored to the exact baseline blob
hash before this file was written (`git hash-object` compare + `git status --porcelain`
clean except this file). Implementer claims were treated as claims and reproduced, not
trusted.

Setup verification: checkout is detached at `58b4296` = tip of `origin/codex/signal-r4-store`;
`git diff --stat b87d464..HEAD -- app/ tests/` is **empty** (the post-head commits are
work/-only, as claimed). Commit `249f9be` and the WO-0135 record were excluded from this
semantic review per the request. The three staged test blobs at HEAD are
`a4de2669…`/`9513d50e…`/`a3ed1b5d…` and are **independently confirmed byte-identical to
`origin/codex/signal-tests-staging`** (`git ls-tree` on the staging ref, not just the
recorded hashes).

## Schema-gate DDL comparison (request §4 — any deviation is P0)

- The committed `signal_records` DDL (`app/store/sqlite.py:422-455`) is **token-identical**
  (normalized whitespace) to the archive-shape reference the approval names
  (`origin/archive/claude-wo-0001-install-checks-2x5ys8:app/store/sqlite.py` ~:353-383):
  same 26 columns, same declared types, same NOT NULL set
  {producer_id, signal_id, status, symbol, direction, received_at, thesis, provenance,
  payload_hash, created_at, updated_at}, `id TEXT PRIMARY KEY`, inline
  `UNIQUE (producer_id, signal_id)`, `provenance … DEFAULT '{}'`, and exactly the two
  approved indexes `idx_signal_records_status` / `idx_signal_records_symbol`. Byte
  differences vs the archive are column-alignment whitespace and the leading comment only.
- Field-by-field vs `docs/spec/signal-seat/01-schema.md §2`: every spec field is present
  with the correct affinity and nullability; nullable freshness fields are exactly
  `issued_at`/`ttl_seconds`/`expires_at`; `received_at` NOT NULL; `raw_fields` nullable;
  no extra column, no missing column.
- The `_migrate` guard (`app/store/sqlite.py:1041-1101`) is exactly the approved package's
  two components: an exact name→(type, notnull, pk) column-shape dict compare that refuses
  startup on ANY mismatch, and a `pragma_index_info`-derived unique-key check requiring
  `("producer_id", "signal_id")` in declared order.
- Only commit `b87d464` touches `app/store/sqlite.py` in the whole range, and it follows
  the approval-record commit `6947966` — the gate ordering holds in history, not just in
  prose.

**No deviation from the approved package found. No P0.**

## Gate battery reproduced (fresh, this environment)

- Focused Signal R4 suite (3 staged + 2 additive files): **66 passed** (matches claim).
- Full suite `pytest -p no:cacheprovider -q`: **4,275 nodes; 4,263 passed / 11 skipped /
  1 xfailed; exit 0** (counts re-derived from progress glyphs; matches the claimed 4,275
  collected/exit 0). Run twice; both exit 0 (first run completed before any mutation).
- `ruff check .` → All checks passed. `mypy app/` → Success, 70 files.
  `lint-imports` → 6 contracts kept / 0 broken.
- Canonical R2 oracle `pytest -q tests/r2_conformance_oracle.py` → **61 passed**;
  `tests/r2_conformance_oracle.py` is untouched in the range (not in the diffstat) — no
  oracle-content change. `pytest -q tests/test_wo0113_repair_scaling.py` → **13 passed**.
- Adjacent parity suites `test_phase6b_readmodel_parity.py` +
  `test_wo0125_envelope_replay_parity.py` → **113 passed**.
- `git diff --check 9d60b74..b87d464` names exactly the three staged blobs' trailing blank
  line at EOF and nothing else (matches claim).

## Ruff-exception reconciliation (operator-requested extra item)

Under the **pinned** ruff 0.15.20, `ruff format --check .` fails on exactly **10 files**:
the three staged Signal blobs plus seven files
(`app/recorder/__init__.py`, `app/recorder/models.py`, `app/recorder/store.py`,
`harness/bootstrap.py`, `tests/test_tape_recorder.py`,
`tests/test_wo0114_pd1_release_valve.py`,
`work/review/AUDIT-0002-priorwork/probe_review_integrity.py`). I verified all seven are
**byte-identical to `origin/master`** (`git diff --stat origin/master --` on the seven is
empty). The apparent paradox ("master CI green but byte-identical files fail ruff")
resolves without version drift: **CI runs only `ruff check .`
(`.github/workflows/ci.yml:36-39`) — `ruff format --check` is not a CI gate at all.** So
the seven findings are real pre-existing format debt under the pinned toolchain, invisible
to CI, and the bounded exception is **not moot — it is real, correctly scoped, and exact**:
the 10-file set equals 3 staged + 7 baseline precisely, there is **no eighth baseline
finding**, and **no implementation-owned non-staged file fails** (all nine implementation
files pass). The disposition record should state that the exception stands on its own
merits under the pinned ruff, independent of CI, and that closing the debt permanently
would require either normalizing the seven files or adding `ruff format --check` to CI as
the separate work the operator already named.

## Fresh disproof probes (all my own scripts, scratchpad-only)

1. **Echo → conflict → echo (both stores; SQLite closed/reopened between every step):**
   exactly 1 record, 1 `SIGNAL_RECEIVED`, 1 `SIGNAL_DUPLICATE_CONFLICT`; both echoes
   write-free (event count stable); original record byte-stable (status RECEIVED, original
   thesis/hash); repeated identical conflict coalesced to one event even across reopen
   (dedupe key `signal_conflict:<producer><signal><new_hash>` is INV-5-deduped in both
   stores). PASS.
2. **A-3 boundaries:** server cap 1 s dominates producer ttl 86400 (`expires = received+1s`);
   `expires_at == received_at` exactly → DOA `SIGNAL_EXPIRED` (inclusive `<=`);
   `received_at + 1µs` → RECEIVED; future skew admitted at exactly +30 s, quarantined
   `issued_at_future` at +30 s +1 µs; stale quarantined `issued_at_stale` at −24 h −1 µs
   (at exactly −24 h with max ttl the deadline degenerates to DOA — spec-consistent);
   ttl 29/86401 quarantine `ttl_out_of_range` with ttl+expires nulled and raw offender kept,
   ttl 30/86400 admitted. Persisted deadlines survive close/reopen byte-identically, the
   event log is byte-stable across restart, and `project_signal_records` takes **no clock
   parameter at all** — a later wall-clock change structurally cannot re-derive the
   deadline. PASS.
3. **Fault injection:** SQLite — failure after the event insert, and separately after
   BOTH inserts (pre-COMMIT): zero partial truth in-process AND after restart from the
   file; the store is not wedged afterwards. Memory — exception after the event append,
   and after both writes (inside `_atomic`): snapshot restores signal dict AND event log;
   both stores replay clean afterwards. PASS.
4. **Schema guard, one wrong property at a time (12 variants):** `INT` affinity,
   REAL→TEXT affinity, dropped NOT NULL (thesis), added NOT NULL (issued_at), missing PK,
   PK on the wrong column, missing column, extra column, **reversed
   UNIQUE(signal_id, producer_id)**, single-column UNIQUE, absent UNIQUE, wider
   3-column UNIQUE — all 12 refuse startup deterministically with
   "signal_records schema mismatch", before any signal_records mutation, and refuse again
   on retry; the exact approved shape is accepted (positive control). PASS.
   (Note: the guard compares a name-keyed dict, so pure column *re-ordering* with
   identical per-column shapes would pass — harmless with named-column INSERT and
   by-name row mapping, and column order is not in the request's must-reject list.)
5. **Hostile projector streams:** mismatched `record_id` → ProjectionError; missing
   `record_id` → ProjectionError; missing/non-string identity → ProjectionError;
   snapshot-less `SIGNAL_RECEIVED` → ProjectionError; conflict-only birth → no phantom
   record; conflict after birth → original untouched; `PRODUCER_*` and non-signal events →
   no-ops; terminal-then-approved AND approved-then-rejected both latch. Two deliberate
   forward-compat behaviors classified (not fail-closed): (a) a transition whose valid
   string identity names a **never-born record** is silently skipped (see F4); (b) a
   second creation snapshot for the same identity overwrites the fold — unreachable from
   store-written logs because all three creation event types share the identity-scoped
   dedupe key `signal_create:<producer><signal>`, so a log can never contain two. PASS
   with classifications.
6. **Registration deletion:** removing `signals=project_signal_records(materialized)`
   from `project_read_models` leaves the full signal suite AND both aggregate parity
   suites green (179 tests) — **no parity test fails** → Finding F1.
7. **INV-1/INV-9 (request item 9):** with a real FILL-derived position (qty 7) on the book,
   drove every R4 outcome shape (received, echo, conflict, DOA-expired, freshness- and
   validation-quarantine) plus synthetic `PRODUCER_QUARANTINED`/`PRODUCER_RELEASED` through
   both stores: `PositionProjector` output and `list_positions()` unchanged before/after,
   deterministic on re-fold, and unchanged across SQLite restart+replay. PASS.
8. **Restart byte-equivalence:** full `SignalRecord` equality (all fields incl.
   raw_fields/provenance/unicode thesis) across SQLite close/reopen, plus
   fold == live rows after restart. PASS.

## Mutation pass (each applied to source, pin observed, exact bytes restored)

| # | Mutation | Result |
|---|---|---|
| M1 | A-3 `min` → `max` (`core.py::classify_signal_freshness`) | **RED — killed.** 4 property tests fail incl. `test_a3_deadline_formula_is_exact` and the cap-dominates property. |
| M2 | Dedupe encoding → naive `":".join(parts)` | **RED — killed** by the staged crafted-identity pin `test_dedupe_key_no_ambiguous_collision_across_signal_ids[memory/sqlite]`. NOTE: the Hypothesis property `test_signal_event_dedupe_encoding_is_injective` stayed GREEN under this mutation (random text does not find the crafted collision) → F3. |
| M3a | Different hash treated as replay (`if True:`) | **RED — killed** on both stores (conflict-audit, coalescing, malformed-distinct pins) + the echo/conflict property. |
| M3b | Conflict replaces the original row (plan returns a mutated record) | **RED — killed** on both stores (memory: original-untouched/replay pins; SQLite: UNIQUE violation surfaces) + property. |
| M4a | Remove `self._signals = saved_signals` from memory `_atomic` rollback | **SURVIVES — all 66 signal tests green** → Finding F2. (My probe 3 proves the *unmutated* code rolls back correctly; the gap is pin coverage, not behavior.) |
| M4b | Split SQLite event/record writes into two `_tx` blocks | **RED — killed** by `test_signal_event_and_record_rollback_together`. |
| M5a | Disable the column-shape mismatch raise | **RED — killed** (`test_signal_schema_guard_fails_closed[TEXT-…]`). |
| M5b | Disable the unique-key check | **RED — killed** (`…[INTEGER-False-missing UNIQUE…]`). |
| M6a | Fold `SIGNAL_DUPLICATE_CONFLICT` into the lifecycle (map to QUARANTINED + drop the exclusion) | **RED — killed** on both stores (`test_replay_reconstructs_records`). |
| M6b | Remove the terminal latch | **RED — killed** (`test_terminal_state_latches…` + `test_terminal_quarantine_not_overwritten…`). |
| M7a | Remove replay registration (`signals=` kwarg in `project_read_models`) | **SURVIVES — signal suite + both aggregate parity suites green (179 tests)** → Finding F1. |
| M7b | Remove the signals loop from `_describe_read_model_diff` | **SURVIVES (green)** — but behaviorally minor: `compare_read_models` gates on dataclass equality, so a signals-only divergence still fails parity with `ok=False`; only the human-readable detail goes silent. Folded into F1's resolution. |

Restoration proof: post-pass `git hash-object` of all five touched files equals the
pre-pass baseline exactly; `git status --porcelain` shows only this result file.

## Findings

### F1 (P2 — drives ACCEPT-WITH-CHANGES): aggregate replay registration is unpinned; request mutation "remove replay registration → aggregate parity must turn red" survives green
- **Where:** `app/events/replay.py:195` (registration), `app/events/replay.py:220-227`
  (diff describer); coverage gap in `tests/test_phase6b_readmodel_parity.py:199-220`
  (no `signals` perturbation) and in both parity test files (no signal ingest in any
  aggregate-parity script; `grep` finds zero tests driving signal events through
  `project_read_models`/`verify_dual_store_readmodel_parity`).
- **What:** deleting `signals=project_signal_records(materialized)` from
  `project_read_models` (the `signals` field then silently defaults to `{}`, so both
  stores "agree" on nothing) leaves every committed test green — 179 relevant tests, plus
  mypy (the default makes the omission type-valid). The WO's own claim — "dual-store
  read-model parity covers signal records from birth" — is enforced only at the direct
  `project_signal_records` seam; the aggregate seam that
  `verify_dual_store_readmodel_parity` and future runtime health checks actually consume
  is blind to signals.
- **Why it matters:** this is exactly the "persisted signal stream disappears from parity
  comparison" hole the request names in item 8, and the REV-0029 inert-pin class. A future
  refactor of `project_read_models` could drop signals from aggregate parity with a fully
  green suite.
- **Not a defect of the delivered change:** the registration and diff describer exist and
  are correct as shipped (probe-verified); the gap is failure-capability of the pins.
- **Resolves (tests only, no source change):** (a) add a `signals` perturbation to
  `test_compare_read_models_detects_divergence` (a one-line `replace(base, signals={…})`
  case asserting `ok is False` and a describing detail), and (b) at least one aggregate
  test that ingests a signal on both stores and asserts
  `verify_dual_store_readmodel_parity(...).ok` plus non-empty `proj.signals` (the
  equal-but-both-empty false positive is otherwise possible).

### F2 (P2): memory `_atomic` signal-state rollback is unpinned; request mutation "remove signal state from memory rollback" survives green
- **Where:** `app/store/memory.py:533` (snapshot) / `app/store/memory.py:555` (restore);
  coverage gap: `tests/test_signal_sqlite_schema.py:166` pins SQLite-side atomicity only,
  and no committed test injects a failure into memory signal ingest (`grep` over `tests/`
  finds no other `ingest_signal` caller).
- **What:** deleting the `self._signals = saved_signals` restore line leaves the entire
  66-test signal suite green. ADR-009 A-2 says explicitly "The memory store's `_atomic`
  snapshot MUST include signal state (the envelope branch's REV-0023 F7 showed what
  omission costs)" — the state IS included and my probe 3 proves rollback works in the
  unmutated code, but nothing committed would catch its removal.
- **Why it matters:** the R5/A-2 atomic conversion command will lean on this exact
  snapshot; an unpinned load-bearing rollback is the REV-0023-F7 failure mode waiting to
  recur silently.
- **Resolves (tests only):** a memory twin of
  `test_signal_event_and_record_rollback_together` — monkeypatch the event append (or the
  post-write seam) to raise mid-ingest and assert `get_signal` is None AND
  `get_execution_events()` is empty afterwards.

### F3 (P3): the injectivity Hypothesis property alone is not failure-capable for the separator-collision class
`tests/test_signal_ingest_properties.py:166-179` stayed green under the ':'-join mutation
(M2); the staged example pin `test_dedupe_key_no_ambiguous_collision_across_signal_ids` is
the load-bearing kill. Acceptable as-is (the decisive pin exists and killed the mutation on
both stores); optional hardening: bias the strategy toward parts containing ':' /
boundary-straddling composites so the property can find the collision itself.

### F4 (P3): a transition event naming a never-born record is a silent no-op
`app/events/projectors.py:855-857` (`existing is None → continue`, evaluated BEFORE the
`record_id` check). Probe-verified: a `SIGNAL_REJECTED`/`SIGNAL_EXPIRED` with well-formed
string identity for an unknown `(producer_id, signal_id)` disappears from replay. In a
store-written log this state implies log corruption (a creation event cannot be absent
while its transition exists — creation dedupe keys are identity-scoped), so this is a
defensible forward-compat choice rather than a live divergence path — but it is weaker
than the fail-fast posture the staged corpus pins for every other malformed-transition
shape (missing identity, non-string identity, mismatched record_id, snapshot-less
RECEIVED). Recommend the R5 WO either pins this as an explicit documented no-op or
promotes it to ProjectionError; today it is neither pinned nor documented.

### F5 (P3): memory signal snapshot is shallow; safe only under the replace-never-mutate discipline
`app/store/memory.py:533` — `saved_signals = dict(self._signals)` copies the dict, not the
records (unlike `sell_intents`' `model_copy(deep=True)`). Correct today because R4 code
only ever replaces whole records under a key, never mutates one in place, and every read
path returns `model_copy(deep=True)`. If R5 transition code ever mutates a stored
`SignalRecord` in place, rollback would silently fail to restore it. A one-line comment on
the snapshot (or deepening the copy) closes the trap; flagging so R5 inherits the
constraint knowingly.

### F6 (P3 — R5 seam contract, not an R4 defect): sanitizer placeholders + hash scope put the malformed-offender burden on the R5 caller
On the `validation_failed` path, `plan_signal_ingest` stores placeholder
`direction="buy"` for an invalid direction and `symbol="UNKNOWN"` for an unusable symbol
(`app/store/core.py:5878-5881`), and the echo/conflict `payload_hash` is computed over the
*sanitized* fields plus `raw_fields`. Consequently two malformed proposals differing only
in a raw offender that the R5 route does NOT copy into `raw_fields` would hash identical
and echo-collapse (the staged corpus pins the `issued_at` offender case; symbol/direction
offenders are unpinned because R4's store API cannot see the raw wire values). The R5
ingest route must put EVERY raw offending field into `raw_fields` — otherwise distinct
attributable facts are silently deduplicated. Record this as an explicit R5 requirement.

## Properties table (request §Authority and behavior)

| # | Property | Verdict | Anchor |
|---|---|---|---|
| 1 | `SignalRecord` fields/types/nullability re-derived from ADR-009 + 01-schema §2; quarantine nulls only issued_at/ttl_seconds/expires_at; received_at + raw offenders durable | VERIFIED | models.py:698-741 diff; staged models tests; probes 2/8 (restart-durable raw_fields) |
| 2 | A-3 exact: `min(received+cap, issued+ttl)`, ttl [30,86400], +30s/−24h skew, inclusive boundaries, persisted deadline, injected clock only; no rails/config defaults in R4 | VERIFIED | probe 2; property corpus; M1 killed; `server_max_ttl_seconds`/`cycle_budget_limit` are required caller kwargs (base.py:1325-1336); no wall-clock call in the range diff (grep clean; planner overrides `created_at`/`updated_at` with `received_at`) |
| 3 | `(producer_id, signal_id)` injective; identical content = write-free echo; different hash = exactly one audit conflict, original untouched | VERIFIED | probe 1; staged pins; M2/M3a/M3b killed; length-prefixed encoding core.py:5646-5656; SQLite UNIQUE probe 4 |
| 4 | Terminal-at-ingest emits ONE terminal event; attributable events carry record_id, persisted expires_at, cycle_budget_limit | VERIFIED | probes 1/2; staged DOA + quarantine pins; property `test_safety_payload_fields_reach_the_signal_projector`; SIGNAL_RECEIVED correctly carries no budget (not a rejection, 02-lifecycle §2) |
| 5 | Memory `_atomic` vs SQLite `_tx` ordering; any failure rolls back both sides; restart byte-equivalent | VERIFIED behavior (probe 3, probe 8) — but memory side UNPINNED (F2) | memory.py:5560-5610; sqlite.py:7606-7690; M4b killed |
| 6 | Committed DDL + `_migrate` guard vs approval record and accepted schema; malformed/missing-unique refuses startup; no alternate affinity/nullability/PK/index-order accepted | VERIFIED (12-variant probe 4; M5a/M5b killed; token-identical to archive shape) | sqlite.py:422-455, 1041-1101 |
| 7 | `project_signal_records` identity-fail-fast, record-scoped, terminal-latching, forward-compatible only where permitted; conflict never enters the fold | VERIFIED (probe 5; M6a/M6b killed) with two classified no-ops (F4 + duplicate-snapshot note) | projectors.py:828-889 |
| 8 | Aggregate replay includes signals and reports divergence; additive default preserves legacy callers without letting the stream disappear from parity | PARTIAL: registration + diff describer exist and work (probe-verified); legacy default safe; but the "cannot disappear from parity" half is REFUTED at the test layer — M7a survives green (F1) | replay.py:161, 195, 220-227 |
| 9 | INV-1/INV-9: no SIGNAL_*/PRODUCER_* fact alters positions, fresh ingest both stores, before/after replay | VERIFIED | probe 7; staged `test_signals_do_not_touch_position`; PositionProjector folds `is ExecutionEventType.FILL` only (projectors.py:775) |
| 10 | Scope: no staged-blob normalization (hashes exact vs staging ref), no schema beyond approval, no hidden wall clock, no R5/R6/R7 behavior; forbidden paths untouched; sqlite.py touched only after the approval commit | VERIFIED | diffstat (7 app files + 5 test files + work/); commit walk; grep |

Request "Questions to answer": (1) No — every malformed/stale/future/expired/echo/conflict
path yields exactly one outcome (totality property + probes), never replaces original
truth, and durable payloads survive restart. (2) No divergence found after
rollback/conflict/restart/replay (probes 1-3, 8; dual-store staged pins). (3) No — the
guard rejected all 12 malformed variants and accepted the exact approved shape.
(4) No — positions untouched (probe 7); aggregate-replay visibility is real but unpinned
(F1). (5) Yes for planner/store/schema/projector mutations (10 of 12 killed); no for the
two pins named in F1/F2. (6) Yes — range stays inside the approval and WO boundaries.
(7) The exception did not expand: staged hashes exact, all nine implementation-owned
non-staged files formatted, exactly seven baseline findings (no eighth), no semantic test
waived, oracle content unchanged (61 cases).

## Ran vs read

**Ran:** full suite twice (4,275 nodes, exit 0; glyph counts 4,263/11/1); focused signal
suite (66); adjacent parity suites (113); R2 oracle (61); repair scaling (13); ruff
check/format (pinned 0.15.20); mypy app/ (70 files); lint-imports (6/0); 8 probe scripts
(echo/conflict/echo, A-3 boundaries + restart, fault injection ×4, 12 schema-guard
variants + positive control + retry determinism, 11 hostile projector streams,
registration deletion, INV-1/INV-9 with live FILL position, restart byte-equivalence);
12 mutations with per-pin red/green observation and byte-exact restoration.

**Read:** CLAUDE.md safety core; `.ai-os/core/15_CROSS_MODEL_REVIEW.md`; REV-0039
request; WO-0134; SIGNAL-R4-STATE.md; ADR-009 (A-1..A-4); specs 01-schema/02-lifecycle;
the full range diff of all seven app files and five test files; archive DDL reference;
`.github/workflows/ci.yml`; `conftest.py` fixture; `_tx`/`_atomic`/
`_insert_execution_event`/`_append_execution_event_unlocked` internals.

## Not independently verified

1. **The in-session schema-gate presentation bytes.** The operator approval is recorded
   verbatim, its scope description matches the committed artifact, and the committed DDL is
   token-identical to the archive shape the approval names — but the literal package as
   presented in the Codex session is not reproduced anywhere in the repo, so
   "presented verbatim as committed" rests on the WO/state-file record, not on my own
   comparison.
2. The implementer's Windows-side command spellings and timings (`.venv\Scripts\...`,
   WinError 5 sandbox note); I reproduced the canonical invocations on Linux under the
   pinned 3.12 venv instead.
3. The temporary totality-file collection evidence (staging, collecting, deleting
   `tests/test_signal_quarantine_totality.py` in-session); I verified only that the file is
   absent from every commit in the range and from the worktree.
4. The exact identities of the 11 skips/1 xfail in the full suite (counts and glyphs only).
5. WO-0135 / commit `249f9be` content (explicitly excluded from this review's scope).

## Verdict

**ACCEPT-WITH-CHANGES.** The R4 implementation is correct, in scope, and faithful to the
approved schema package and the accepted A-3/dedupe/echo/conflict semantics: the DDL and
guard match the approval with zero deviation; both stores are atomic, restart-stable, and
replay-exact under fresh hostile probes; positions are structurally untouched; 10 of 12
mutations are killed by committed pins. Required changes (tests only, no source edit,
suitable for the disposition loop): **F1** — make the aggregate replay registration
failure-capable (signals perturbation in `test_compare_read_models_detects_divergence` +
one aggregate parity test that actually ingests a signal); **F2** — pin memory `_atomic`
signal rollback with a fault-injection twin of the SQLite atomicity test. F3-F6 are
recorded for the R5 planning inputs and need no R4 action. The bounded ruff exception is
confirmed real, exact, and non-expanding under the pinned toolchain (CI never runs
`ruff format --check`), and the canonical 61-case oracle invocation stands.
