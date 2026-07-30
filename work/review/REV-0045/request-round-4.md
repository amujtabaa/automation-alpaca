---
type: Review Request (continuation)
rev_id: REV-0045
round: 4
title: "WO-0141R R6a-C1 — one rail sequence rule: kernel and both stores. Independent gate review."
requested_of: Codex (independent cross-model review seat)
implementer: "Claude seat (Opus 5) — the same seat that authored REV-0044 and the three prior remediation rounds"
references: "REV-0045 result.md + addenda 01/02/03; work/queue/R6A-CONSOLIDATION-PROGRAM.md (operator-ratified 2026-07-28, D-4 added 2026-07-29); docs/adr/ADR-016; docs/adr/ADR-009 (amended)"
branch: codex/signal-r6a-rails-store
base_sha: 14ff12fbf4667a1a23969d28446818cc010292b9
head_sha: "tip of codex/signal-r6a-rails-store — the commit that adds this file"
production_head_sha: 6e6c9ad
head_note: "6e6c9ad is the last commit that touches app/. Every commit after it carries tests, docs, pyproject selection and CI comments only — verify with `git diff --name-only 6e6c9ad..HEAD -- app/`, which is empty — so the app/ figures below are final at 6e6c9ad. Pin the exact tip SHA in your result."
range_size: "app/ 8 files +433/-68 — FINAL at 6e6c9ad. Everything after 6e6c9ad is tests, living docs, work artifacts and build/CI config; a commit count is deliberately not stated here because it goes stale on every push, and the head_note command settles the production boundary instead."
gate: "Unchanged. WO-0104a stays REVIEW; R6b and D-2a stay blocked; signal_seat_enabled stays false — now enforced in code, see §5."
---

# REV-0045 round 4 — request

## 0. The range, pinned

**Base `14ff12fbf4667a1a23969d28446818cc010292b9`** — your own addendum-03 head — **to the tip of
`codex/signal-r6a-rails-store`**. Everything below is inside that range; nothing outside it is being
asked for.

```
git diff --stat 14ff12f..6e6c9ad -- app/    # 8 files, +433 / -68   <- production, FINAL
git diff --stat 6e6c9ad..HEAD   -- app/     # EMPTY — verify this, do not take my word
git log --oneline 14ff12f..HEAD
```

**The production surface is 8 files / +433 / −68 lines, and it is final at `6e6c9ad`.** Every commit
above `6e6c9ad` carries tests, living docs, work artifacts, `pyproject.toml` config and CI comments —
no `app/` file — so you can bound the production review at `6e6c9ad` and read the tail as evidence,
disclosure and ratified-decision records. The rest of the range is tests (15 files, ≈3.3k lines),
living docs and work artifacts (14 files, ≈2k), and build/CI config (3 files). A commit count is
deliberately not quoted: this file has already been re-cut once for being stale against HEAD, and the
`--` `app/` command above settles the production boundary without going stale. If your round-3
criterion 1 was "state a range I can bound", that command is the bound.

## 1. What changed since addendum-03, in one paragraph

Addendum-03 returned **BLOCK** with 6 P0 / 6 P1 cumulative and fired the P-1 treadmill tripwire.
The operator ratified a consolidation program rather than a fourth patch round. This delivery
implements its §1 decision block: **D-1-a** (one attribution rule), **D-2-b** (only accepted events
prove anything — this *withdraws* the §2.6 reservation ruling you judged unsafe), **D-3-c** (a
write-capped sequence domain), and **D-4** (sequence the structural consolidation after review, not
before). The unifying idea: the code conflated two facts — *this event proves sequence N* and
*sequence N's dedupe key is taken* — and separating them is what makes D-2-b implementable without
recreating P0-6. Recorded as **ADR-016**.

## 2. Read this first: I found eight defects in my own work in this range

Two adversarial self-passes ran inside this range — one over my first implementation (`c20ca47`),
one an independent merge-readiness assessment of the whole delivery. Between them they found
**eight** defects in work I had already reported as green. **Do not assume the later commits are
polish.**

| Defect | Found by | Fixed in |
|---|---|---|
| **P0-7.** The fold demanded `next_mintable`; both stores still minted at `release-floor + 1`, so the store's own recovery event was refused by the fold that gates recovery. The human release never survived a restart. | self-audit of `c20ca47` | `87d03c4`, dual-store in `6e6c9ad` |
| `occupied(p)` bucketed by the **payload** producer, so a key/payload-conflicted release consumed a key that entered nobody's set | self-audit | `729a7fb` |
| Occupancy leaked on the shape-refusal path, making the set order-dependent | self-audit | `729a7fb` |
| The cap bound the mint but not the minter's input → uncaught `ValueError` on the release path | self-audit | `87d03c4` |
| **P0-2 was never actually remediated.** The pin you named drove only the `rate_breach` opener; `budget_exhausted` — a separate path with its own counter cross-check — was never exercised. | merge-readiness assessment | `59414f1` |
| **The ADR-015 ratchet had never run.** Five independent defects, including one in my own classifier taxonomy. | running it | `c7094cc`, `f5b8227`, `2bdae6d` |
| **"Operator ruling D-A" had no provenance.** `grep -rn "D-A" work/ docs/ pkl/` returned exactly one hit — the citation in the artifact requesting your approval. The ruling was real and given in session, never recorded. | merge-readiness assessment | `59414f1` (now **D-4**, with date, ratifier, options, rationale) |
| **The enable gate was prose.** ADR-016's whole merge-safety argument rested on a document, and the only thing preventing enablement was a file that happened to be absent. | merge-readiness assessment | `6e6c9ad` (§5) |

**Root cause of the first four, and the thing most worth your scepticism.** WO-0141 was scoped
along a **file** boundary — "kernel now, stores in WO-0142". `contributed_epoch_sequence` is read by
both stores, so changing what it *means* is a store change regardless of which files the diff
touches. My scope table recorded "paired-store limb: 0" and that was wrong. The operator ratified a
P-3 amendment: *a limb is counted where a derived quantity is CONSUMED, not where files are edited.*
**Please check whether I have applied that rule or merely written it down.**

My first repair of P0-7 was **also** wrong: I let the stores pass their own `proven` value, and
SQLite's row-drift marker carries that value copied from the durable row, so a drifted row leaked
back into the mint. A pre-existing pin (`test_double_heal_mints_distinct_keys`) caught it.

**Two of the eight were found by a process audit, not by testing.** P0-2 and D-A are both cases
where the artifact asserting completion was the only evidence of it. That is the class I would most
like you to hunt for in what remains.

## 3. A load-bearing claim I made to you in round 3 is FALSE — correcting it now

`R6A-CONSOLIDATION-PROGRAM.md:375` argued R6a is safe to merge because *"the seat defaults to
`False` and the code is dormant"*. **The code is not dormant.**

```
grep -rn "signal_seat_enabled" app/store/   # → no matches
```

`SQLiteStore.initialize()` calls `_rebuild_producer_rails_locked` unconditionally
(`app/store/sqlite.py:705`); `MemoryStore.initialize()` calls `project_producer_rails_tolerant`
unconditionally (`app/store/memory.py:328`). **The tolerant fold, the occupancy computation, the
marker derivation and the durable-row upsert run on every store open, in both stores, flag on or
off.** The flag gates route mounting, rails-provider construction and launch bind validation
(`app/main.py`, `app/launch_guard.py`, `app/server.py`) — nothing in the store layer.

The correct merge-safety argument is narrower and I want it on the record in your words, not mine:

- With the flag off, **no writer can mint a `PRODUCER_*` event**, so the fold runs over an empty
  projection. That is an *emptiness* argument, not a dormancy one.
- It is therefore **only as strong as the F-1 append-caller enumeration** — which is now
  load-bearing for merge safety, not merely defence-in-depth for D-1-b as ADR-016 §1 describes it.
  `tests/test_wo0141_append_caller_gate.py` is the thing holding that claim up. **§6 asks you to
  attack it.**
- It does **not** insulate the merge from **P0-8**: a database that already contains `PRODUCER_*`
  rows gets the new fold applied on next open regardless of the flag.

**I have not edited that sentence out of the program.** It is what I told you in round 3, and
rewriting it silently is the class of thing this packet exists to prevent. It stands where it was,
with a dated correction block immediately beneath it; the same correction is in ADR-016 §1 (which had
described the F-1 enumeration as "defense in depth, not urgent") and in `SIGNAL-R6aR-STATE.md`.

## 4. Open defects — declared, not hidden

- **P0-8** (`tests/test_wo0141_persisted_carrier_divergence.py`, **strict xfail**) — the never-regress
  rule persists `max(prior_row, marker.last_known_epoch_sequence)`. D-2-b lowered `last_known`, so a
  pre-upgrade row higher than log truth wins the `max` forever. The durable row can hold a value no
  fold of the log produces, and the two stores disagree on a read surface. **Bounded:** the mint no
  longer consults the row, so recovery is unaffected. **Not bounded by the flag** — see §3.
  Routed to **`work/queue/WO-0142-r6a-c2-store-truth.md`** because the repair reverses WO-0140's
  ratified never-regress rule and therefore needs its own ratification.

  **The operator has ruled that R6a merges with this open — D-5(a), ratified 2026-07-29**, disclosed
  and strict-xfailed, rather than holding the merge for WO-0142. Two options were put; (a) was taken on
  the bound above plus the fact that the repair needs its own ratification. **You are not being asked
  to endorse that ruling** — it is the operator's — but you *are* being asked whether the bound is
  real, because the whole exception rests on it. If the mint does consult the durable row on any path I
  have missed, or if the two stores' disagreement is reachable on a surface that matters more than I
  think, the exception was granted on a false premise and should be revoked.

  Close-out step **1d-ter** now forces the exception to survive the merge as an *accepted risk*: the
  disposition must state the bound, the exception and the residual; it may not re-assert that the seat
  flag contains it (§3); **INV-099 stays recorded as VIOLATED** until WO-0142 closes it; and the
  close-out stops if WO-0142 has been dropped, since the exception was granted against that
  destination.
  Registered as **INV-099**, which `docs/INVARIANTS.md` records as **VIOLATED TODAY** — deliberately:
  an unregistered rule cannot be checked against.
- The pre-existing xfail from before this range, unchanged.

Both are strict xfails so a green suite cannot imply their absence.

## 5. The enable gate is now code, not prose

`app/server.py:enable_gate_refusal` — a pure predicate returning the refusal string or `None`.
`run()` calls it **last**, after bind validation, capability minting and the rails-presence guard,
and exits 2. Gated on `app/config.py:SIGNAL_SEAT_HUMAN_RECOVERY_AVAILABLE = False`. Registered as
**INV-100**; only WO-0104b (which now exists) may flip it, in the change that ships
`/api/producers`, the release route and the cockpit control.

Three placement mistakes preceded it, all caught by tests rather than by reasoning:

1. Gating app **construction** broke ~13 test modules that legitimately build a flag-on app to
   exercise ADR-009 wiring. Forcing all of them to bypass the gate would have made it ceremony.
2. Written inline in `run()` it was testable only by *calling* `run()`, which binds a socket and
   serves. The first test that tried hung. **A control exercisable only by doing the dangerous thing
   does not get exercised** — hence the pure predicate.
3. Placed **first** in `run()` it masked the A-1 bind reason and the rails diagnostic. Two launcher
   tests caught it. It now fires after every config-validity refusal.

**What I want judged:** whether refusing on the *launch* path rather than at construction is the
right seam, given that §3 establishes the store-side code runs regardless. My argument is that the
store-side code is inert-by-emptiness while no route can write, and that gating construction would
have produced a bypass-riddled gate. If you think the gate belongs at a different seam, say so —
this is a human-gated-surface control and I would rather move it now than after a merge.

## 6. What I am asking you to judge

1. **The four ratified rulings as implemented** — D-1-a, D-2-b, D-3-c, D-4 — and specifically
   whether `next_release_sequence` really is *one* rule with no second implementation anywhere.
2. **Each of REV-0045's open P0s by name** (P0-2, P0-3, P0-4, P0-6): fixed, partially fixed, or
   open. I am not claiming class-level closure. **I have claimed that twice and been refuted twice**,
   so treat any such claim in my commit messages as an assertion to test, not a finding.
3. **P0-7 and P0-8**, the two I introduced and declared, and **the §3 correction** — whether the
   emptiness argument actually holds.
4. **The assurance controls, adversarially.** I defeated my own append-caller gate **five ways** in
   one sitting — including the exact split-literal shape that defeated the derived-truth gate as your
   P1-4 — then a **sixth** (an f-string) after hardening. It now refuses what it cannot audit.
   **Please try to defeat it again.** Four gates this seat has built have now failed first contact,
   and per §3 this one is load-bearing for the merge-safety argument itself.
5. **Non-discriminating pins.** Five have been found on this surface, all by mutation, none by
   reading — pins exercised only at values where the correct and incorrect rules coincide. I swept
   the ones I found. Assume I missed some. The standing rule that came out of it is *reachability is
   not discrimination.*
6. **The `205` mutation baseline** (§7, §7a) — whether the number and the taxonomy change behind it are
   defensible.
7. **The independence limitation** (§9) — this is the one I most want a ruling on, and it has been
   open across all four rounds.

## 7. The mutation ratchet: five defects found by running it, and the scope question is now DECIDED

Your P1-5 identified that the workflow's grep could not match mutmut's indented output. I repaired
the *parser* against fixtures and never ran the real tool. Same mistake, new place. Running it
surfaced:

- `mutmut run` failed at stats collection — mutmut copies only `source_paths` into its working tree,
  so the rest of `app/` was unimportable. Fixed with `also_copy`.
- `mutmut results --all` is **not a valid invocation** in 3.6.0: `--all` takes a boolean argument.
  The CI step and my own classifier docstring both had it wrong, so the job could not have produced
  output even after the P1-5 fix.
- **The test selection had rotted.** The enumerated list named four files written before WO-0141, so
  every pin added since was invisible to the ratchet — a mutant inverting the dispatch in
  `contributed_epoch_sequence` survived a full run because the test that pins it was not selected.
  `tests/test_ratchet_selection_is_complete.py` now fails the build when a module imports
  `app.events.projectors` and is absent from the list. It found **14** unselected modules.
- **A taxonomy error in my own classifier.** A mutant that HUNG is a mutant whose fate is known —
  the suite detected it by failing to terminate. I had lumped `timeout` in with `not checked` on the
  reasoning that "a run that did not finish is not evidence", which is sound about a *run* and wrong
  about a *mutant*. `timeout` now counts as detected; `segfault`, `suspicious` and `not checked`
  stay unknown. **Corrected on the merits — but the correction also unblocked the baseline, so it
  deserves your scepticism.** The narrowness is pinned: only `timeout` moved, and a fixture asserts
  segfault/suspicious still force INDETERMINATE. The fixture that pinned the old behaviour is
  **re-derived, not edited to match**.
- **A real bug in production code, found by a mutant hanging.** `next_mintable_epoch_sequence`
  scanned with `while candidate in occupied` and checked the cap only *after* the loop, so the scan
  was structurally unbounded — terminating by luck of the predicate, over a caller-supplied set,
  inside startup. The cap now bounds the loop. This is the first thing generated mutation has caught
  here that human review did not.

**The scope question I asked you in the previous draft is withdrawn — I decided it.** Leaving it
open would have been an artifact asking you to rule on something a commit had already settled.
Selection widened from 4 to 24 modules; the ratchet runs on `survived` with `no tests` eliminated
rather than reported around.

```
generated 1223 | killed 1017 | detected_by_timeout 1 | survived 205
MAX_SURVIVORS: 999 (sentinel) -> 205.  Verified: passes at 205, fails at 204.
```

**205 is a MEASUREMENT, not a target.** The prior numbers are recorded next to it because they are
the instructive ones: with the old selection the same code measured 593 non-killed, **270 of them
`no tests`**. That number measured the *selection*, not the tests. Judge whether widening was the
right call and whether 205 is a floor you would accept as a ratchet.

### 7a. Triaging the survivors found a live crash path — and an unreachability result

I recorded 205 without triaging it. Triaging even the narrow slice that matters most — the two
functions **WO-0141R itself added or changed** — returned six survivors, and closing them is in
this delivery (`tests/test_wo0141_mutation_triage_gaps.py`, 21 pins, all six mutants certified
RED→GREEN).

Where the 205 sit, by function (my classification, from `mutmut results --all True`):

| Group | Survivors |
|---|---|
| Producer-rail surface — `_producer_id_from_event` 22, `_apply_producer_released` 19, `_decode_length_prefixed_parts` 15, `_apply_producer_quarantined` 14, `sequence_from_release_dedupe_key` 9, `project_producer_rails_tolerant` 9, `_validated_release_event_shape` 8, `fold_producer_rail` 4, `contributed_epoch_sequence` 3, `release_key_claim` 3 | **≈106** |
| Non-rail projectors — envelopes 42, fills 12, signal records 10, order status 2, positions 1, shared validators and the rest | **≈99** |

**More than half the surviving mutants are in the code this review is about.** That is the single
most useful thing the baseline told me, and it is an argument against treating 205 as a settled
floor.

The six I closed split into two classes, and the distinction is the finding:

- **`release_key_claim` (3) — a LIVE path.** The tolerant fold calls it unconditionally, first, for
  every event (`app/events/projectors.py:1855`), outside the applier's `try`. One mutant
  (`sequence is None or sequence < 1` → `and`) turns a release whose dedupe key has a non-canonical
  sequence part into an **uncaught `TypeError` inside tolerant startup** — `initialize()` raises and
  the backend does not start. Measured both directions:

  ```
  unmutated:  ({}, {'p': InvalidProjectionMarker(..., reason="release dedupe key
              'producer_release:1:p|3:abc' has a malformed sequence part", ...)})
  mutant:     TypeError: '<' not supported between instances of 'NoneType' and 'int'
  ```

  A tolerant fold that raises is not tolerant, and this is the class of log — legacy corpora,
  hand-edits — the tolerant fold exists for. Nothing pinned it before.

- **`contributed_epoch_sequence` (3) — REDUNDANT DEFENCE, which the survivor set is what proved.**
  It is called only in the fold's `else:` branch, after the applier accepted the event, and
  `_apply_producer_quarantined` already validates the same field with
  `_required_int(..., minimum=1, maximum=_SQLITE_MAX_SIGNED_INT)`. Every value these guards reject
  was rejected first — so the branches are unreachable through the fold, which is *why* no
  integration test could kill the mutants. They are pinned as the function's stated contract (it is
  documented as "the single source of derived sequence truth"), and the suite says explicitly that
  it is **not** claiming a live defect was closed. **Coverage cannot make that distinction; a
  survivor set can.** I had not appreciated that before running it.

**One correction, since I nearly reported the opposite.** I first read
`test_release_floors_agree_across_stores_on_adversarial_openers` as a seventh non-discriminating pin
— it feeds `True`, `"9"`, `3.5`, `2**63`, `None` and the loop asserts only that the two stores
agree, which unifying the two floors made true by construction. It is **not** vacuous: it also
asserts `answers == {1}` and carries a non-vacuity check. The reason a domain mutant survives it is
the reachability result above, not a weak pin. Recorded because the wrong version of this paragraph
was one commit away from being sent to you.

**`MAX_SURVIVORS` stays at 205 in this commit, and is now known-loose by at least six.** I have not
lowered it to 199, because that number would be arithmetic rather than measurement and the next
nightly produces the real one. Flagging rather than quietly leaving it.

## 8. Two measured assessments of my own delivery

Both are measurements, not opinions, and both are disclosures rather than repairs — I am not touching
either surface while the semantics are under review.

### 8a. `next_release_sequence` holds the SQLite write lock for O(log-length)

`_next_release_sequence_locked` runs `SELECT * FROM execution_events ORDER BY sequence` — **the whole
log, unfiltered** — materializes every row into an `ExecutionEvent`, and folds it twice
(`proven_epoch_high_water` + `occupied_release_sequences`). Under `self._lock`. Measured on this
machine, median of 3–5 runs, filler rows being ordinary non-rail events:

| log length | kernel only | full SQLite release path |
|---|---|---|
| 1,000 | 2.9 ms | 22.8 ms |
| 5,000 | 15.2 ms | 126.8 ms |
| 20,000 | 60.2 ms | 546.8 ms |
| 50,000 | 145.3 ms | 1,429 ms |
| 100,000 | 356.5 ms | 3,112 ms |

Cleanly linear: ≈3 µs/event in the kernel, ≈31 µs/event end-to-end. Extrapolating, a 1M-event log
means **~31 s of lock-held work**, and that lock serializes every other write — order submission
included.

**My assessment, for you to overturn if you disagree.** Not a correctness defect and not urgent: this
runs only on the human release path, once per stuck producer, and `initialize()` already folds the
whole log on every open, so O(n) at startup is inherent and accepted. What is new is O(n) *under the
write lock at runtime*. No scaling pin covers it — `tests/test_wo0113_repair_scaling.py` is about
repair cursors.

**Why I am not optimizing it in this commit, which is the part I want checked.** The obvious fix is a
`WHERE event_type IN (...)` pre-filter. That is the *same shape* as the payload pre-filter I deleted
from this exact query — deleting it was the P0-3 fix, because occupancy follows the KEY and a
conflicted release names different producers in key and payload. A type filter is a different
predicate and probably safe, but "probably safe filter on the rail read path" is precisely the
reasoning that produced P0-3, and the fold also consumes attributable *signal* events, so the
enumeration is wider than it looks. It needs the F-1 treatment — a machine-checked enumeration that
fails the build — not an inspection. Routed to **WO-0142**.

Worth noting the precedent: WO-0140 slice 3 fixed this identical shape on the *debit* path, where the
code re-folded the whole log per attributable rejection, and closed it with an incremental debit plus
a scaling pin. Same class, on a path many orders of magnitude less frequent.

### 8b. The coverage floor is a hair-trigger, and its own comment says otherwise

`pyproject.toml [tool.coverage.report] fail_under = 93`, and the comment above it reads *"Floor set a
few points under the current ~95% branch coverage so it catches a real regression without flaking on
normal churn."*

Measured at this working tree: **93.11%**. The margin is **0.11 points**, not "a few points", and
~95% is not the current figure. Against 14,404 statements + 5,332 branch outcomes, 0.11 points is on
the order of **twenty uncovered statements-or-branches** between green and red.

The trajectory across this delivery, read from the commit evidence lines: 93.14 (`c20ca47`) → 93.11
(`87d03c4`) → 93.10 (`8fa7122`, `f9f332c`, `2bdae6d`, `59414f1`) → 93.08 (`6e6c9ad`) → **93.11** (this
commit; the §7a triage pins and the new min-Python gate recovered it).

So the mechanism works and the number is currently fine. The finding is that the *description* is
false in a way that matters: anyone reading that comment believes there is slack for "normal churn"
and there is not. A ratchet with a two-point margin and a ratchet with a twenty-branch margin call
for different behaviour when a build goes red — the first says "you regressed", the second says "you
added code". Anyone trusting the old comment reaches for the wrong diagnosis.

**Ruled D-8(a), 2026-07-29:** correct the comment, leave `fail_under = 93` untouched, and sequence
raising the floor to 93.1 to the R6a close-out — after an independent verdict has cleared the work the
number would be measuring. Three options were put (comment-only / raise to 93.1 now / lower to 92.5 to
restore real slack). The comment is corrected in this commit and carries the measured figures and the
trajectory; **the gate value is unchanged**, because moving a gate inside the change it would judge is
the pattern this packet exists to catch. Flagging the sequencing so you can object to it if you think
93.1 should land before the merge rather than at it.

## 9. Independence — the limitation that has been open all four rounds

`tests/_rail_reference_model.py` is **pre-registered, not independent** — written by me, from the
ratified decision block, before the implementation. It constrains shaping the oracle to fit the
code; it constrains **nothing** about a blind spot we might share. WO-0141R §5.1 asks for
reviewer-*owned* holdouts, which I cannot supply.

Round 4 is the fourth consecutive round in which the only independent judgement on this surface is
yours, and the failure mode the record now shows is **common-mode**: the eight defects in §2 include
two found only by a process audit and one found only by running a tool.

**The operator has now ruled on this — D-6(b), ratified 2026-07-29 — so it is a concrete ask rather
than an open question.** Four options were put: (a) you author holdouts inside this packet, (b) you
**adopt** the pre-registered model after reading it, recorded as adoption, (c) a third seat supplies
them, (d) accept pre-registered-only and stop calling it independence. **(b) is ratified.**

So what round 4 needs from you is a **recorded adoption decision** on
`tests/_rail_reference_model.py`:

- **Adopt** — you have read it against the ratified decision block and the spec, you accept it as
  expressing the intended semantics, and you say so in `result-addendum-04.md`. From that point it is
  a model the reviewer has independently accepted, and agreement between it and the kernel becomes
  meaningful evidence rather than a self-check. Name anything you had to change to adopt it.
- **Decline** — say what is wrong with it, and it goes back as a finding.

Adoption is deliberately weaker than (a): it constrains specification-reading errors and reviewer-side
disagreement about intent, and it still does **not** constrain a blind spot we both share. Please say
so explicitly in your result if you adopt, so the record does not later over-read it. If you would
rather author your own holdouts — option (a) — the operator's ruling does not prevent that; (b) was
chosen as the floor that does not stall the round, not as a ceiling.

Until adoption is recorded, agreement between the model and the kernel is weak evidence and must not
be reported as a gate. That sentence stays true and I am not asking you to soften it.

## 10. Process disclosure — CI was red for seven commits while I reported green

Not a code defect; disclosed because it bears on how much weight my evidence lines carry.

CI was **red from `8fa7122` through `2bdae6d` — seven consecutive commits**, single cause: an
adversarial fixture used `f"append_{"execution_event"}"`. Nested same-type quotes inside an f-string
are PEP 701, Python 3.12+ only; the fixture is a source string fed to `ast.parse`, so the 3.11
matrix job raised `SyntaxError` while my 3.12 `.venv` passed. **Three** of those seven commits
carried "0 failed / gates green" evidence lines. Fixed in `0dacf5b`; green on both legs at `0dacf5b`
and `59414f1`.

Two corrections to my own account of it:

- The commit message disclosing this says "five commits". **It is seven** (`8fa7122`, `205dd40`,
  `f9f332c`, `714dcc4`, `c7094cc`, `f5b8227`, `2bdae6d`). Verified against the Actions API.
- `python3.11` is installed on this machine. I could have caught it without CI and did not, because
  my verification loop only ever used the 3.12 `.venv`. **A matrix that exists is only a control if
  something exercises it before the claim is made.**

**The repo contract conflict behind it is now RESOLVED — D-7(a), ratified 2026-07-29.** `CLAUDE.md`,
the repo primer, `pkl/architecture/architecture-map.md` and ADR-009's context paragraph all said
"Python 3.12" while CI exercised 3.11 **and** 3.12. Two options were put — amend the docs to 3.11+ and
keep the matrix, or drop 3.11 and keep the pin. **(a) is ratified**, and it turned out to be the
option that makes the repo *self-consistent* rather than a new position: `[tool.mypy] python_version
= "3.11"` (ADR-007, ratified) and `constraints.txt` ("safe across the 3.11 / 3.12 CI matrix") already
behaved that way. Only four prose statements disagreed. All four are amended; ADR-009 carries an
amendment note rather than a silent rewrite, because the line there is context, not its decision.

**And the convention is now a gate, which is the part worth your scrutiny.** `[tool.ruff]
target-version = "py311"` was unset, so ruff assumed its newest target and accepted the offending
construct. Set, it refuses it — measured before adoption:

```
f"append_{"execution_event"}"  in a source FILE
  -> invalid-syntax: Cannot reuse outer quote character in f-strings on Python 3.11
     (syntax was added in Python 3.12)
```

Adopted with **zero** new findings on the tree. But that setting alone does **not** catch the shape
that actually caused the seven red builds — the same text inside a *string literal* fed to
`ast.parse`. Ruff lints a file's own syntax; a fixture stored as a string is opaque to it. Measured:

```
# a file whose only content is that fixture, as a string
$ ruff check tests/_probe_planted_fixture.py
All checks passed!
```

**So the residual is closed by a second gate rather than documented as a known hole:**
`tests/test_min_python_syntax_gate.py` collects every string literal in `tests/` that parses as
Python and lints all of them at `py311` in one batched ruff invocation — ~11.7k candidates in under
0.3 s — reporting the originating file and line. Planted in a real test module, it fires:

```
invalid-syntax: Cannot reuse outer quote character in f-strings on Python 3.11
  _probe_planted_fixture.py:4 — 'async def f(s, e):\n    return await getattr(...)'
```

Three design points I would rather you checked than took on trust:

- **No heuristic.** An earlier draft filtered to "strings that look like code" and was worthless — it
  flagged 71 docstrings and found nothing real. Linting *everything* that parses is cheap, and
  docstrings that happen to parse produce no syntax error at `py311`, so the filter that could hide a
  real fixture is gone.
- **No second interpreter, deliberately.** `ast.parse(src, feature_version=(3, 11))` does **not**
  reject the construct (measured on 3.12 — that parameter is best-effort and does not gate PEP 701),
  and shelling to a real `python3.11` would `skip` wherever 3.11 is absent, which is the inert-control
  class. Ruff's target is config, not runtime, so the gate has identical force on both legs.
- **No self-exemption.** The gate's own tripwire fixture is *assembled at runtime* from a substituted
  quote character, because stored as a literal it made the gate fail on itself — and the tempting fix,
  an allowlist, is precisely how the append-caller gate was defeated five times. Its own test asserts
  no parsing literal in that module carries the construct. Two drafts got this wrong before it held;
  both mistakes are recorded in the file.

The gate also pins the mechanism rather than assuming it: one test plants the real defect and requires
ruff to refuse it, so if ruff ever stops reporting version-aware syntax errors — `requirements.txt`
allows `ruff>=0.6`, only `constraints.txt` pins the verified `0.15.20` — the suite fails loudly instead
of the gate going quiet.

**What remains a process rule, not a gate:** reading CI before claiming green. That is now repo-primer
rule 5 and a `CLAUDE.md` line. It is deliberately not scoped to this defect — a matrix leg can fail for
reasons no local gate models — and it is the rule whose absence let seven red builds be reported green.

### 10a. The gate itself then took the 3.11 leg red. You will see the failed run; here it is.

`1ecfdc0` is **red on `test (3.11)`, green on `test (3.12)`** (run 30502139527, 1 failed / 4,865
passed). The failing test is in the file above, and the failing assertion was the gate's own
self-check:

```python
# It is real Python on the CURRENT interpreter — ...
# (It must NOT raise here: this runtime is 3.12+, where PEP 701 is legal.)
compile(_PLANTED_312_ONLY_SOURCE, "<tripwire>", "exec", dont_inherit=True)
```

The comment states the defect out loud. **"This runtime is 3.12+" is the assumption the gate exists to
eliminate, written into the gate.** Fixed in the following commit; the assertion is now
version-conditional and therefore *stronger* — on 3.11 it actively proves the construct is refused
there rather than merely not failing.

**Why my verification missed it, which is the part I would rather you judged than the typo.** The
commit message claimed "the new module AST-parses under `python3.11`". That was **true and worthless**:
the illegal construct is assembled at runtime precisely so no literal in the file is illegal, so the
file parses on every interpreter — and parsing it never executes the assertion. I checked the property
that was easy to check and reported it as covering the property that mattered. **Parsing a file is not
running its tests.** It is the second time in this delivery that "verified under 3.12 only" shipped a
3.11 break, and this time no 3.11 environment was even needed as an excuse.

Evidence for the repair, executed on both interpreters rather than parsed by one — a 3.11 venv built
from `requirements.txt -c constraints.txt` (Python 3.11.15, ruff 0.15.20):

```
gate on 3.11: 6/6 passed        gate on 3.12: 6/6 passed
RED/GREEN by reverting to the shipped form:
  3.11: FAILED test_the_planted_construct_is_assembled_not_stored (SyntaxError)
  3.12: 6/6 passed        <- exactly why it shipped
restored: green on both
```

**One more thing the failure exposed, and it limits the gate's claim.** The collector keeps only
strings that parse *on the running interpreter*, so on 3.11 a 3.12-only fixture is dropped as prose and
this gate is close to vacuous on that leg. That is the correct division of labour — on 3.11 the defect
is caught natively by whichever test parses the fixture — but it means a green 3.11 run of this gate
carries much less than a green 3.12 run, and **neither leg alone is the control.** Now stated in the
module docstring. If you think that asymmetry makes the gate weaker than I am presenting it, say so.

Standing rule added to `pkl/architecture/testing-model.md`: **when a check reasons about a version,
platform, or store, it is not verified until it has RUN under each one** — the dual-store rule, one
layer out.

## 11. Evidence at the reviewed head

Read every figure from output, not from this file.

- Battery on **3.12**: **4866 passed / 11 skipped / 2 xfailed / 0 failed**, branch coverage **93.11%**
  (floor 93.0)
- Battery on **3.11**, in a venv built from `requirements.txt -c constraints.txt` (Python 3.11.15):
  **4866 passed / 11 skipped / 2 xfailed / 0 failed**, branch coverage **93.10%**. See §10a for why
  this environment now exists and why its absence let a 3.12-only assumption ship
- **CI green on BOTH matrix legs at `586b675`** — run 30503366455, `test (3.11)` **success** and
  `test (3.12)` **success**, every step including ruff, mypy, import boundaries, the contamination
  guard, AI-OS hygiene and the R2 oracle. Read from the Actions API, not inferred from a local run.
  The preceding commit `1ecfdc0` is **red** on `test (3.11)` and that is deliberate history, not a
  loose end — §10a explains what failed and why the fix is stronger than what it replaced
- `ruff check .` clean; `ruff format --check .` — **exactly the ten disclosed debt files**
- `mypy app/` — 77 source files, no issues; `lint-imports` — **6 contracts kept, 0 broken**
- conformance oracle **61 passed**; AI-OS hygiene **×5 green** (install, version, ledger, pkl,
  work-order disposition)
- The six §7a mutants certified RED→GREEN individually; `python3.11 -m ast.parse` run on the new test
  module before claiming green, which is the control that was missing when CI went red for seven
  commits (§10)
- **CI green on both matrix legs (3.11 and 3.12)**, confirmed from the Actions API — not inferred from
  a local run — at `6e6c9ad`, `6624a62`, `9662b54` and `3154e6c`. Confirm the tip's run before any
  close-out step executes; that is now a repo rule, not a courtesy (`CLAUDE.md`, "Testing and CI")
- Mutation certificates for every decisive pin, recorded per commit
- `ruff target-version = "py311"` verified to fire on a real repo file and adopted with zero new
  findings; the `ast.parse(feature_version=...)` alternative measured and rejected (§10)

**Format-debt disclosure.** During this range a repo-wide `ruff format` reformatted five of the ten
files in your addendum-03 baseline as a side effect of an unrelated commit. I had caught and
reverted that class once already and did not catch it the second time. Those five are **restored**
to your recorded baseline, so `ruff format --check .` shows exactly the ten again. Flagged because
you re-check that number and would otherwise have found it yourself.

## 12. What is NOT in this delivery

Deferred by **D-4** (operator ruling, 2026-07-29, "review first" — now recorded with provenance in
`R6A-CONSOLIDATION-PROGRAM.md` §1 after §2 caught that it had none): the structural consolidation —
the typed `ProducerRailFact` union and one `ProducerRailMachine` — and the Hypothesis stateful
model. The rationale was that stacking a large refactor onto a semantic layer that has never had a
clean independent review is how a ninth P0 appears. **If you think that sequencing is wrong, say
so** — it is a decision, not a constraint.

Also out of scope, with destinations that now **exist as files**:

| Deferred | Destination |
|---|---|
| P0-8; D-1-b append-time binding validation; replay-vs-live for producer rails; REV-0044 R-1 caveat | `work/queue/WO-0142-r6a-c2-store-truth.md` |
| `/api/producers`, the release route, the cockpit control, sweeps, rate settings, flipping `SIGNAL_SEAT_HUMAN_RECOVERY_AVAILABLE` | `work/queue/WO-0104b-r6b-producer-recovery-surface.md` |

Until `6e6c9ad` both were routed to work orders that were not files. Routing to a nonexistent
destination reads as disposition without being it — found by the merge-readiness assessment, not by
this seat.

## 13. If the verdict is BLOCK

Per the P-1 tripwire and the operator pre-commitment of 2026-07-28, a further BLOCK on this surface
does **not** route to a fifth patch round. It routes to the kernel-consolidation program, or — under
the P-4 round budget — to a re-cut or a seat change. Two consecutive BLOCK/P0 rounds on one surface
force an AUDIT-0001-style root-cause audit before any further remediation. Say plainly which you
think applies.
