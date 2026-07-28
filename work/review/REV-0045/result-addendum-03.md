---
surface: signal-seat-r6a-derived-sequence-truth
round: 3
type: Review Result Addendum
rev_id: REV-0045
addendum: 03
title: "WO-0140 R6a-R truth-model remediation: round-3 cumulative independent gate"
reviewer_model: OpenAI Codex (GPT-5)
reviewer_seat: Codex (independent cross-model review seat)
base_sha: b48235e
head_sha: 14ff12fbf4667a1a23969d28446818cc010292b9
verdict: BLOCK
delta_p0_count: 1
delta_p1_count: 3
cumulative_p0_count: 6
cumulative_p1_count: 6
date: 2026-07-28
---

# REV-0045 addendum 03 — **BLOCK**

Independent round-3 review of the full cumulative range
`b48235e..14ff12fbf4667a1a23969d28446818cc010292b9`. The exact reviewed
implementation head is **`14ff12fbf4667a1a23969d28446818cc010292b9`**.

The R6a gate does **not** clear. P0-2, P0-3, and P0-4 remain open at class
level. P0-5 is fixed. One new P0 and three new P1s were found:

- **P0-6:** a canonical release reservation at the maximum ratified sequence
  has no in-domain successor, so the human release path cannot recover either
  store.
- **P1-4:** the claimed single-source AST gate is evaded by a parallel
  derivation in a currently listed store while all three gate tests stay green.
- **P1-5:** the ADR-015 nightly mutation workflow counts no real `mutmut 3.6.0`
  result line, making its ratchet step unreachable.
- **P1-6:** the ledger provenance gate accepts a required-but-blank or null
  date together with `commit: "HEAD"`.

The green full battery establishes baseline health. It does not offset live
evidence that recovery can be permanently unavailable and that the same
append-only log produces different memory, SQLite, live, and replay outcomes.

## New findings

### P0-6 — a reservation at the maximum sequence is unrecoverable

- **Affected local files:** `app/events/projectors.py:1323-1332,1335-1380`,
  `app/store/core.py:6147-6152`, `app/store/memory.py:5636-5641,6172-6175,
  6204-6207`, `app/store/sqlite.py:7919-7927,8500-8504,8522-8525`, and
  `docs/spec/signal-seat/02-lifecycle.md:143-154`.
- **Cause:** the parser and shared contribution helper correctly admit
  `2**63 - 1`. A malformed release with that canonical, producer-bound key
  therefore consumes the globally unique key and raises the producer's
  high-water to the maximum. The ruling then requires recovery at
  `high-water + 1`, but `producer_released_event()` correctly refuses that
  out-of-domain value. The argument that the colliding sequence is reserved is
  locally true; the unstated assumption that a valid successor always exists
  is false.
- **Why it matters:** the human-gated release operation has no recovery path
  for a representable event-log state. The producer remains marked after live
  release attempts and replay on both stores. This contradicts the ratified
  claim that a marked producer restarts via a zero-width release at exactly
  `high-water + 1`.
- **Reproduced-live evidence:** on both stores, a malformed same-owner release
  with canonical sequence `9223372036854775807` produced a marker whose
  high-water was that value. A direct valid append at the same key returned the
  existing event and wrote nothing, confirming the collision argument. The
  actual human release then raised
  `ValueError: epoch_sequence must be an integer in [1, 9223372036854775807]`;
  the marker and replay refusal remained, with one event still present.
- **What resolves it:** ratify and implement a terminal-sequence recovery that
  does not require an out-of-domain successor. Align it with the actual global
  dedupe-key collision domain, then pin live/replay/restart agreement on both
  stores at the maximum and immediately below it.

### P1-4 — the single-source AST gate attests spelling, not derivation

- **Affected local file:** `tests/test_derived_truth_single_source.py:25,
  47-59,72-99`.
- **Cause:** the negative half recognizes only exact string constants
  `"epoch_sequence"` and `"producer_release:"`; the positive half requires
  only that each hard-coded store imports `contributed_epoch_sequence`. It
  neither proves that a derivation calls the helper nor rejects a dead import.
  The parser check also exempts any path whose name ends in `projectors.py`,
  rather than the one ratified module.
- **Why it matters:** a gate represented in the lifecycle spec as mechanical
  enforcement of single-source truth can stay green after the prohibited
  parallel derivation returns. This is the exact assurance class the gate is
  supposed to prevent.
- **Mutation-survived evidence:** the memory release floor was changed to read
  the payload via `event.payload.get("epoch_" + "sequence")` while retaining
  the helper import. All **3/3** AST tests passed. The file-copy backup was
  restored and the repository diff returned empty.
- **What resolves it:** inspect actual helper call sites and prohibited data
  flow, not literal spelling or import presence; discover applicable store
  modules instead of maintaining a closed tuple; restrict the parser exemption
  to the exact ratified module; and commit negative fixtures for split
  literals, dead imports, and a newly added store.

### P1-5 — the nightly mutation ratchet cannot reach its ratchet step

- **Affected local files:** `.github/workflows/mutation-nightly.yml:45-68`,
  `pyproject.toml:79-90`, and `requirements-mutation.txt:4`.
- **Cause:** line 55 counts only result lines beginning with an ASCII letter.
  The exactly pinned `mutmut 3.6.0` prints every result as
  `f"    {key}: {status}"` — four leading spaces — and hides killed mutants
  unless all results are requested. A run with survivors therefore counts
  zero; an all-killed run emits no default result lines and also counts zero.
  Both paths exit as `NO_MUTANTS` before the survivor ratchet.
- **Why it matters:** ADR-015's generated-mutation assurance cannot establish a
  baseline or detect a survivor regression. A permanently red scheduled job
  is not mutation evidence and is likely to be operationally ignored.
- **Reproduced-static evidence:** the inspected official wheel was
  `mutmut-3.6.0-py3-none-any.whl`, SHA-256
  `a9f5b8dcf6cbf9496769d7cf8bdbba37a0ec709ad98f88d103238b62f10bdf37`.
  Its `mutmut/__main__.py:1191-1200` contains the indented print and
  killed-result suppression described above. The workflow's anchored grep
  cannot match that output.
- **What resolves it:** obtain the generated population independently of
  presentation whitespace, include all statuses when deriving totals, keep
  tool failure distinct from survivor results, and add a workflow-level
  fixture for nonempty killed, nonempty survived, empty, and tool-error cases.

### P1-6 — blank/null dates bypass the ledger provenance ratchet

- **Affected local files:** `.ai-os/scripts/check_ledger.py:22-25,46-48,
  60-76` and `tests/test_assurance_gate_fixtures.py:48-60`.
- **Cause:** `date` is required only as a key. Both date-format validation and
  post-cutoff commit validation are guarded by `if date`, so `""` and `null`
  skip both checks.
- **Why it matters:** a newly appended ledger row can retain the exact
  unverifiable `commit: "HEAD"` form the P-6 ratchet was introduced to stop,
  while CI reports `LEDGER CHECK PASSED`.
- **Reproduced-live evidence:** minimal ledgers with all required keys,
  `commit: "HEAD"`, and respectively `date: ""` and `date: null` each returned
  `problems=[]`. The committed negative fixtures exercise a nonblank future
  date and a grandfathered date but not either bypass.
- **What resolves it:** require `date` to be a nonblank string matching
  `YYYY-MM-DD` before any cutoff comparison, then add blank, null, non-string,
  and `HEAD` combinations as committed negative fixtures.

## Prior P0 root-cause disposition

### P0-2 — **OPEN**

The repaired subtraction at `app/store/memory.py:399-401` and
`app/store/sqlite.py:1607-1609` is correct, and both requested known mutants
are now failure-capable:

- a flat seed made the named consecutive-epoch test fail at epoch 1 on both
  stores (**2 failed**);
- an epoch-1-only subtraction made it fail at epoch 2 on both stores
  (**2 failed**).

A new valid mutant survived: subtract only when the cached epoch is open **and**
`quarantine_breach_trigger == "rate_breach"`. The named test at
`tests/test_signal_rails_remediation.py:1479-1550` drives only the rate path.
The mutant passed both named parameters and the five-file rails set
(**163 passed**). A budget-exhaustion composition then recorded the bounded
verifier's `ProjectionError` on the first try on both stores; fallback
re-derived the right public result, leaving final sequence and marker
assertions green.

**Resolution:** parameterize the first-try/no-fallback property over both
ratified opener triggers (`rate_breach` and `budget_exhausted`) on both stores,
including consecutive epochs.

### P0-3 — **OPEN**

The numeric/NULL limbs are fixed:

- every current SQLite assignment into `_upsert_producer_log_rail()` reaches
  the sink through a bounded builder, helper, existing durable carrier, or
  literal;
- the sink at `app/store/sqlite.py:1724-1742` rejects bool, non-int, negative,
  and over-domain carriers with `InvalidEventError`;
- a NULL release key plus a valid sequence-2 opener produced floor 2 on both
  stores; neither floor raised or diverged.

The class remains open because the two floors apply the shared helper to
different event sets while dedupe uniqueness is global:

- memory scans every event and asks the helper whether it contributes to the
  requested producer (`app/store/memory.py:352-362`);
- SQLite first filters rows by payload owner
  (`app/store/sqlite.py:1706-1718`);
- tolerant replay first assigns an event to its payload owner and then invokes
  the helper (`app/events/projectors.py:1633-1642`);
- both append layers dedupe solely by the global key, without validating event
  type or payload ownership against that key
  (`app/store/memory.py:5636-5641`,
  `app/store/sqlite.py:7919-7927`; SQLite schema uniqueness at
  `app/store/sqlite.py:409-423`).

**Reproduced-live evidence:** after an invalid NULL-key release marked a victim
producer, a second malformed release named another payload owner but consumed
the victim's canonical sequence-1 key. SQLite computed victim floor 0, collided
when it attempted sequence 1, raised `InvalidEventError`, and remained marked.
Memory computed victim floor 1, released live at sequence 2 and cleared its
marker, but replay remained marked because sequence 2 was not the victim's
next contributed sequence. The same append-only facts therefore disagree
across stores and across memory live/replay.

**Resolution:** make append-layer key ownership and every consumer's event
selection share one ratified collision domain. Reject or quarantine
type/owner/key mismatches before they reserve a key, or define and test a
recovery/migration policy for already-written mismatches.

#### Exhaustive durable carrier map

`_upsert_producer_log_rail()` is the sole nonliteral SQLite durable sink.

| SQLite call | Source | Bound |
|---|---|---|
| `app/store/sqlite.py:1779-1788` | rate-bucket row creation | literal `0`; conflict branch leaves sequence unchanged |
| `app/store/sqlite.py:1813-1820` | rebuild reset before re-projection | literal `0` |
| `app/store/sqlite.py:1823` | strict/tolerant valid startup projection | shared helper and strict appliers |
| `app/store/sqlite.py:1825-1834` | invalid-marker startup carrier | bounded shared high-water plus prior SQLite carrier |
| `app/store/sqlite.py:8255` | budget ingest/open | validated builder and bounded increment |
| `app/store/sqlite.py:8257` | unchanged ingest rail | existing validated durable carrier |
| `app/store/sqlite.py:8396-8405` | rate opener | validated builder and bounded increment |
| `app/store/sqlite.py:8506` | interior log repair | strict fold |
| `app/store/sqlite.py:8547-8553` | final human release | `producer_released_event()`-validated carrier |

The memory assignments mirror those paths:

| Memory assignment | Source | Bound |
|---|---|---|
| `app/store/memory.py:340-348` | startup projection/marker | strict projection or bounded shared high-water |
| `app/store/memory.py:376,5900-5905` | incremental budget debit/open | validated plan and bounded increment |
| `app/store/memory.py:5928-5931` | unchanged ingest rail | existing validated carrier |
| `app/store/memory.py:6082` | rate opener | validated builder and bounded increment |
| `app/store/memory.py:6188-6190` | interior log repair | strict fold |
| `app/store/memory.py:6229` | final human release | `producer_released_event()`-validated carrier |
| `app/store/memory.py:734-760` | atomic rollback | exact copy of the pre-operation carrier map; no new ingress |

Replay high-water now advances only through
`contributed_epoch_sequence()` at `app/events/projectors.py:1633-1642`.
The remaining failure is not a missing numeric bound; it is inconsistent
ownership of the globally colliding key.

### P0-4 — **OPEN; OPERATOR RULING: UNSAFE**

The direct code path now advances tolerant high-water only through
`contributed_epoch_sequence()`. The ruling's ordinary same-owner collision
argument also reproduces on both stores: a malformed canonical sequence-1
release reserves that key; a direct valid append with the same key writes
nothing; the human release mints sequence 2; live and replay finish clean.

The ruling is nevertheless **UNSAFE**:

1. P0-3's cross-owner composition shows that global key reservation and
   producer attribution are not the same domain. One store consumes the
   reservation in its floor and the other does not.
2. P0-6 shows that a valid successor does not exist after a reservation at
   `2**63 - 1`.

The sentence in `docs/spec/signal-seat/02-lifecycle.md:152-154` is therefore
not a total recovery rule. It is faithful only for a same-owner,
below-maximum subset.

### P0-5 — **FIXED**

The decoder at `app/events/projectors.py:1238-1332` consumes declared character
lengths and is an inverse of the mint at `app/store/core.py:5643-5652`.

- Existing adversarial IDs (`|`, `:`, Unicode, and `10:team|alpha`) pass at
  sequences 1, 2, 42, and `2**63 - 1`.
- A generated parser probe checked **15,267** nonblank producer IDs across four
  sequences (**61,068 round trips**) with zero failures.
- Twelve adversarial IDs completed live release, projection, and restart on
  both memory and SQLite with no disagreement; wrong-owner parses remained
  refused.
- No producer ID that configuration admits was found to break the inverse.

## Eight named round-3 items

| Item | Verdict | Independent result |
|---|---|---|
| 1. P0-2 consecutive-epoch pins and new survivor | **FAIL** | Flat and epoch-1-only mutants both go red, but a trigger-specific seed mutant survives **163** focused tests and takes fallback on healthy budget-exhaustion epochs on both stores. |
| 2. P0-3 single source, all binds, sink, NULL parity | **FAIL** | Numeric bounds, sink typing, and NULL parity pass. Shared code is applied to different ownership sets while key uniqueness is global, producing SQLite refusal and memory live/replay divergence. |
| 3. P0-4 helper-only high-water and operator ruling | **FAIL — UNSAFE** | Helper-only high-water and the ordinary same-owner reservation case pass. Cross-owner reservation and the terminal maximum invalidate the universal ruling. |
| 4. P0-5 adversarial inverse and composition | **PASS** | **61,068** generated round trips plus dual-store live/replay/restart compositions found no break. |
| 5. Single-source AST gate | **FAIL** | A parallel payload derivation using a composed key passed all **3/3** gate tests in a listed store. |
| 6. Full battery and local gates | **PASS** | Exact counts and the required coverage line are recorded below. Formatter output is exactly the ten ratified debt files and no eleventh. |
| 7. ADR-014/015, CI, specs, templates, negative fixtures | **FAIL** | ADR-014 is behavior-free by identical pre/post batteries. ADR-015's workflow cannot count its tool output; ledger fixtures miss blank/null dates; lifecycle single-source/reservation claims are broader than code behavior. |
| 8. Cumulative test-edit audit | **PASS** | Closed-list changes plus disclosed assurance additions contain no removed `pytest.raises`, no deleted behavior without replacement, and no unauthorized weakening. |

## Post-remediation gated-surface audit

- **ADR-014 rename — PASS.** Exact pre-rename
  `2a1b860e45709deb00aaa68bbebc892cffadc342` and post-rename
  `a7d642d5419c2992361d19ae34854d9ce3779d96` worktrees each reported
  **4,736 passed, 11 skipped, 1 xfailed**, exit 0. The old/new mapping is
  structurally complete in the active code and tests.
- **ADR-015 mutation ratchet — FAIL.** P1-5 makes the survivor ratchet
  unreachable.
- **Lifecycle/spec alignment — FAIL.**
  `docs/spec/signal-seat/02-lifecycle.md:143-154` claims mechanically enforced
  single-source derivation and a total reservation recovery; P1-4,
  P0-3, and P0-6 disprove those claims. Internal contracts at
  `app/events/projectors.py:1585-1595` and
  `app/store/sqlite.py:1791-1802` also still describe marker high-water as
  payload-only even though releases now contribute through keys. That
  documentation drift is supporting evidence for still-open P0-3 and is not
  separately counted.
- **P-6 negative fixtures — PASS narrowly, incomplete.** All four committed
  fixtures pass and the two planted violations are refused. P1-6 is an
  untested sibling input that bypasses the same ledger gate.
- **Templates/protocol/CI shape — no additional finding.** The round/surface
  frontmatter and review-packet disposition checks are wired into committed
  tests; the conformance oracle appears once in CI. The defects above prevent
  an ACCEPT-class process verdict.

## Test-edit audit

The cumulative test diff is **+3,339 / -64** across ten files:

- three disclosed legacy JSON corpora;
- the remediation and two assurance modules; and
- the four adapted pre-existing signal-rail test modules.

There are **zero** removed `pytest.raises` contexts and **14** added ones.
Plain assertions are **153 added / 7 removed**. The sole removed test
definition was split from one combined cap/parser test into a malformed-payload
test and a builder-cap test; the behavior remains covered. The helper
adaptations supply newly required canonical keys or move assertions to the
ratified live seams. `git diff --check b48235e..HEAD -- tests/` passes.

## Reproduction record

- **Pinned tree:** local and fetched branch tip
  `14ff12fbf4667a1a23969d28446818cc010292b9`; clean before this reviewer-owned
  artifact.
- **Full Windows coverage battery:** **4,743 passed, 11 skipped, 1 xfailed,
  0 failed, 0 errors**, exit 0. Required line:
  `Required test coverage of 93.0% reached. Total coverage: 93.12%`.
- **Focused process/AST/oracle set:** **68 passed**. The oracle contributes
  **61/61** and was invoked through
  `python -m pytest -q tests/r2_conformance_oracle.py`.
- **Scaling gate:** **13 passed**.
- **Rails remediation module:** **38 passed** before mutations.
- **Static gates:** `ruff check .` passed; `mypy app` passed for **77** source
  files; import-linter kept **6/6** contracts.
- **Formatter baseline:** exit 1 with exactly the ten disclosed debt files:
  `app/recorder/__init__.py`, `app/recorder/models.py`,
  `app/recorder/store.py`, `harness/bootstrap.py`,
  `tests/test_signal_ingest_store.py`,
  `tests/test_signal_projector_forward_compat.py`,
  `tests/test_signal_seat_models.py`, `tests/test_tape_recorder.py`,
  `tests/test_wo0114_pd1_release_valve.py`, and
  `work/review/AUDIT-0002-priorwork/probe_review_integrity.py`. No eleventh
  file appeared.
- **AI-OS/contamination gates:** install, version consistency (`v0.9.1`),
  ledger, PKL, and work-order disposition checks passed; no tracked
  `.agents/` or `.codex/` paths exist and both ignore entries remain.
- **Range hygiene:** `git diff --check
  b48235e..14ff12fbf4667a1a23969d28446818cc010292b9` passed; the cumulative
  range contains no deleted files.

The external GitHub Actions scheduled mutation job was not executed from this
review seat; P1-5 is derived from the exact committed shell and the exact
pinned tool source. The suite's skips include credential-gated Alpaca
integrations and other ratified skip-gated cases; no live or paper broker call
was attempted.

## Counts and gate disposition

| Count | P0 | P1 |
|---|---:|---:|
| Round-3 delta | **1** | **3** |
| Cumulative REV-0045 | **6** | **6** |

- **Fixed P0s:** P0-1 and P0-5.
- **Open P0s:** P0-2, P0-3, P0-4, and new P0-6.
- **New P1s:** P1-4, P1-5, and P1-6.

**Verdict: BLOCK.** WO-0104a and WO-0140 do not receive an ACCEPT-class
disposition. R-1 and R-2 remain the gating pair; keep D-2a off and R6b blocked.

REV-0044 addendum-01's operator-database evidence remains **NOT AFFECTED** for
the inspected database and still changes urgency only. Because this verdict
does not clear the gate, its R-1 caveat is **not discharged and must carry into
the close-out**. It must not be silently dropped on the strength of today's
clean operator database.
