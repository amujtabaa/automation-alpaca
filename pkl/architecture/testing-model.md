---
type: Testing Rule
title: Testing Model and Determinism Rules
status: active
authority: high
owner: Ameen
last_verified: 2026-07-21
tags: [testing, determinism, ci]
source_refs: [docs/SPINE_EXECUTION_ARCHITECTURE_v2.md]
supersedes: []
superseded_by: null
---

# Testing Model and Determinism Rules

## Summary

Deterministic, dual-path testing posture inherited from the migration and kept permanently: engine logic must be replayable, and any state-touching change proves itself on both stores.

## Rules / facts

- Engine logic: injected clock only — no bare `datetime.now()` / `time.time()`. No unseeded randomness in engine/reconciliation tests. Deterministic IDs and queues.
- Dual-store parity: any change touching state, order, fill, position, reconciliation, kill switch, or the API boundary is tested on both in-memory and SQLite paths.
- The 61-case R2 conformance oracle is an explicit CI step because its historical filename is
  intentionally outside default pytest discovery; removal of that step is pinned by
  `tests/test_ci_lock_liveness_pins.py`.
- INV-051/052 lock liveness is executable: a bounded dual-store composite call fails on
  reentrant public lock acquisition, and an AST pin rejects every `await` nested under either
  store's `async with self._lock` block so broker/network latency cannot enter the lock.
- Dual-store parity is a **decision-structure** obligation, not only an equal-output
  assertion. A distinguishing-state test compares each twin's selection universe
  (immutable scope, raw cache, and event projection), predicate and branch ordering,
  cleanup trigger, audit/execution-event writes and ordering, exception domain,
  rollback boundary, and deterministic iteration/row order.
- Session bootstrap is prerequisite truth in both stores. Once a command legitimately
  reaches the bootstrap point, a later command failure rolls back that command's
  writes but not the existence of today's session: SQLite's bootstrap commits before
  the command transaction, and memory creates it outside the command's `_atomic()`
  snapshot. Tests cover reject/no-op paths separately when bootstrap must not occur.
- Safety-surface changes (overfill, timeout ambiguity, reconciliation, kill switch, manual flatten, position projection) expand tests in the same change — never deferred.
- Property tests cover spine invariants where behavior spans many interleavings; persist or print failing seeds/traces.
- Replay / parity verifier runs where implemented; event-log replay is regression evidence.
- Execution-envelope replay is a permanent dual-store read-model gate. The pure projector folds
  the complete explicit `envelope_*` vocabulary plus envelope-attributed canonical `FILL` facts,
  fails closed on identity/transition/debit-chain drift, and reconstructs mandate bounds, status,
  remaining quantity, and supersession linkage. The vocabulary pin must turn red when a new
  envelope event is introduced without an explicit replay classification.
- Scaling gates combine measured ratios with deterministic complexity/plan pins. An indexed seek is
  still an unrelated corpus walk when its only bound is a global event type; the R2 gate rejects the
  type-only `idx_exec_events_type_sequence` plan on symbol/owner projection paths. Migration loops
  use work counters where wall-clock thresholds alone cannot mutation-pin asymptotic behavior.
  Durable repair high-watermarks advance only after the selected tail validates completely; tests
  prove steady cadence starts after that sequence and that failure does not skip poison on restart.
- The beta R2 scaling budget is explicit and may not be silently loosened. The declared design target
  is 100 symbols / 1,001 Envelopes / 10,002 execution events / 1,000 recoveries; the required stress
  corpus is approximately 10x at 1,000 / 10,001 / 100,002 / 10,000. Runtime p95 growth remains capped
  at 3x, startup SELECT and elapsed growth at 12x, and canonical projection peak at 2 MiB. Every
  `R2_STRESS=1` run must retain constant query count, reject unrelated full scans, and enforce all
  three ratio ceilings; target/stress cardinality drift is itself a gate failure.
- WO-0118 measured this budget on 2026-07-21 in a fresh constrained CPython 3.12.13 environment
  (SQLite 3.50.4, Windows 11). Three canonical target runs passed with runtime growth 0.668–1.023x,
  startup elapsed growth 8.985–9.417x, and deterministic SELECT growth 9.102x. Three canonical stress
  runs passed with runtime growth 0.977–1.142x, startup elapsed growth 10.808–11.480x, SELECT growth
  9.901x, 18 runtime SELECTs at both realistic and stress scale, and zero unrelated scans. The
  Claude-ported target/stress cross-check also passed (stress startup 10.701x). The pre-Cluster-E
  72–76x stress convexity did not survive, so no Phase-2 store optimization or D9 index request was
  warranted. These are design-target results, not an observed-paper inventory: WO-0115 remains
  without a ratified source database path, and its future inventory must be compared to this budget
  without changing the limits automatically.
- Never weaken a test to make code pass; never merge failing or newly-skipped tests. Phase-named tests remain active regression evidence unless replaced and reviewed.
- CI gate (as wired today): `ruff check`, `mypy app/`, `pytest` + coverage, import-linter (`lint-imports`) contracts, `pip-audit` where configured. Formatting authority: `ruff format`.
- `mypy` static typecheck (ADR-007, wired 2026-07-08; **burn-down complete 2026-07-09, WO-0012**): the grandfather list is EMPTY — the whole `app/` package is typechecked with no `ignore_errors` override (started 16 modules / ~187 baseline errors; every error fixed by triage, never silenced). `warn_unused_ignores = true` since 2026-07-11 (the ADR-007 follow-up flip; a stale `# type: ignore` now fails the gate). A line-level mypy-baseline (ADR-007's other documented future upgrade) is **moot** — with zero grandfathered errors there is nothing to baseline; revisit only if a future mypy/dep bump introduces a large new error class. Dependency closure pinned in `constraints.txt` (CI installs `-c constraints.txt`), so the gate can't drift out from under a green PR.

## Rationale

Determinism is what makes broker-edge-case behavior (timeouts, overfills, interleavings) reproducible enough to trust. Dual-path testing was the migration's parity guarantee and remains cheap insurance.

## Applies to

- All tests; CI configuration; every state-touching work order.

## Related pages

- `pkl/architecture/architecture-map.md`
- `pkl/safety/invariants-rationale.md`

## Change log

- 2026-07-07: Created from CLAUDE.md §7/§8 decomposition.
- 2026-07-08: Corrected the CI-gate list to what is actually wired (removed the unwired `mypy`); recorded `mypy` as a deferred gate with a measured baseline (193 errors) and a WO-0008 pointer. last_verified refreshed for the gate facts.
- 2026-07-11: mypy gate facts updated for the completed WO-0012 burn-down (grandfather list empty); `warn_unused_ignores` flipped true (WO-0100 — renumbered from WO-0016 on 2026-07-12 to clear the collision with feat/execution-envelope's WO-0016) and the one stale ignore removed (`app/broker/sim.py`); line-level baseline recorded as moot; constraints.txt lock noted. last_verified refreshed.
- 2026-07-18: WO-0109 Cluster E recorded the measured-plus-structural scaling posture: type-only
  event-index seeks count as unrelated history walks, and deterministic work counters backstop noisy
  wall-clock ratios. last_verified refreshed.
- 2026-07-19: WO-0113 converted dual-store parity from an outcome-only rule into a
  predicate/order/rollback/bootstrap decision-structure rule, with distinguishing-state tests as
  the required evidence, and added fail-closed durable-tail checkpoint pins for repair cadence.
  last_verified refreshed; final WO implementation SHA pending close-out.
- 2026-07-20: WO-0125 added complete execution-envelope replay to the dual-store read-model
  verifier, including canonical and repair-attribution fill debits plus an explicit event-family
  vocabulary ratchet. Store write/event truth remained unchanged.
- 2026-07-21: WO-0118 froze the explicit beta target/stress cardinalities and unchanged scaling
  limits, added a failure-capable shared budget contract to both R2 gates, and recorded fresh
  three-run target/stress headroom. Phase 2 was measurement-skipped because scaling was near-linear.
- 2026-07-28: three standing rules adopted from the REV-0045 round-2 retrospective (operator
  ratification; ADR-014/ADR-015). **(1) Derived truth is single-sourced or it is a defect:** any
  quantity more than one component reads has exactly one deriving function, and a structural gate
  (`tests/test_derived_truth_single_source.py`, AST-level) refuses parallel derivations at commit
  time — behavioral tests cannot see this class, which is exactly how "what epoch sequence does
  this history prove?" accumulated seven implementations and four P0s. **(2) Every mint/parse pair
  ships a total round-trip pin** (`parse(mint(x)) == x`) over the full admitted input domain with
  an adversarial alphabet (separators, length-prefix look-alikes, Unicode) — example:
  `test_release_key_parser_is_a_total_inverse_of_the_ratified_mint`. A pin over friendly inputs
  only is how the REV-0045 P0-5 decoder shipped. **(3) A mutation proof expires the moment its
  guarded path changes** and must be re-run, not trusted; pins over fallback-shadowed paths must
  assert the PATH (first-try success, spy on the fallback), never only the final state, because
  redundant recovery re-derives the correct answer and blinds outcome assertions. Generated
  mutation testing (ADR-015, nightly mutmut ratchet over the derived-truth kernel) backstops the
  mutants nobody hand-picked. last_verified refreshed.
- 2026-07-29: **standing rule (4), adopted from REV-0045 round 3 (WO-0141 §5.3): an obligation
  touching a ratified vocabulary must be parameterized over the WHOLE vocabulary, and the
  parameterization asserted non-vacuous.** A pin that drives one member proves nothing about the
  others. REV-0045 P0-2's surviving mutant was opener-trigger-specific precisely because the pin
  exercised only `rate_breach`; the `budget_exhausted` path is harder to set up honestly (the
  opener is only ratifiable once the attributable fold has actually reached the limit), and a
  fixture that skips that setup marks the producer for a counter mismatch while asserting nothing
  about sequences. Applies to opener triggers, release states, store kinds, and every future
  closed vocabulary in `app/models.py`.
- 2026-07-29: **a control is durable only when machine-consumed, semantically complete,
  failure-capable, exercised by a committed negative fixture, and current.** Corollary adopted with
  WO-0141: a hand-verified reachability enumeration recorded in a document is inert evidence — true
  at one SHA and silently false at the next. The F-1 append-seam enumeration is therefore enforced
  by `tests/test_wo0141_append_caller_gate.py`, which does not judge whether a new caller is safe
  but refuses to let one appear without a human re-deriving the argument. Mutation-verified: a
  seventh caller planted in a real module fails both the caller-set rule and the non-vacuity count.
- 2026-07-30: **a gate must not need an exemption to pass, and "documented residual" is usually a
  measurement away from "closed".** Two lessons from `tests/test_min_python_syntax_gate.py`, built to
  cover the class `ruff target-version` structurally cannot see — 3.12-only syntax inside a fixture
  string handed to `ast.parse`, the shape that took CI red for seven commits.
  1. **Measure the residual before writing it down.** The gap had already been written up as a
     permanent limitation ("the 3.11 CI leg is the only control") when one measurement — that ruff
     accepts `--target-version` on arbitrary paths, so no second interpreter is needed — turned it into
     a closed gate: every string literal in `tests/` that parses as Python, linted at the floor, ~11.7k
     candidates in one batched run under 0.3 s. Three alternatives were rejected on measurement, not
     taste: a "looks like code" heuristic (71 docstrings flagged, nothing real found),
     `ast.parse(feature_version=(3, 11))` (does **not** reject PEP 701 — verified), and shelling to a
     real `python3.11` (skips where absent, so inert on the other leg).
  2. **If a gate flags its own fixtures, restructure the fixtures — never add an allowlist.** This one
     failed on itself three times: its tripwire stored as a literal, then its self-check's assertion
     needle, then its own docstring example. The allowlist that would have silenced all three is
     exactly how the append-caller gate was defeated five times. The fixes were to assemble the
     construct at runtime and to make the self-check mirror the collector's criterion — a stricter
     self-check failed on documentation, which pushes the next maintainer toward deleting the
     explanation instead of keeping the gate honest.
  3. **PARSING A FILE IS NOT RUNNING ITS TESTS, and a test about interpreter differences must be
     EXECUTED on every interpreter it reasons about.** The fourth draft shipped and took the 3.11 CI
     leg red — inside the very gate built to prevent that. Its self-check asserted the tripwire
     `compile()`s on "the current interpreter", with a comment asserting that interpreter is 3.12+.
     True on one leg, a `SyntaxError` on the other. The verification claimed at commit time was
     "the new module AST-parses under python3.11", which was accurate and worthless: the illegal form
     is assembled at runtime, so the file always parses, and parsing never executes the assertion.
     The repaired assertion is version-conditional and therefore *stronger* — on 3.11 it now actively
     proves the construct is refused there. Standing consequence: **when a check reasons about a
     version, platform, or store, it is not verified until it has RUN under each one.** This is the
     same shape as the dual-store rule, one layer out; treat an interpreter matrix the way this repo
     already treats memory-vs-SQLite. A local venv for the minimum supported interpreter is cheap and
     removes the excuse — the failure recurred twice in one session for want of one.
- 2026-07-29: **pre-registration is not independence, and must not be reported as such.** A test
  oracle written by the implementing seat before the implementation (`tests/_rail_reference_model.py`)
  constrains one failure mode — shaping the oracle to fit the code — and constrains nothing about a
  common-mode blind spot shared by both. Such artifacts carry the distinction in their own header,
  and a reviewer may adopt or replace them; until then agreement with them is weak evidence, never
  a gate. Recorded because WO-0141's §5.1 called for reviewer-owned holdouts and the implementing
  seat could only supply pre-registered ones.
  **Ratified route (D-6(b), operator, 2026-07-29): the reviewer ADOPTS, in writing, in the result
  artifact.** Adoption is the standing mechanism for this class — an obligation whose *content* the
  implementing seat can meet but whose *ownership* it structurally cannot. Adoption discharges the
  ownership half and nothing more, and the record must keep saying so: **an adopted pre-registered
  oracle is not an independent one.** Two related unsatisfiable-precondition defects were found while
  applying this and are worth remembering as a class — the R6a merge criterion demanded the holdouts
  be certified "independent", and the close-out checklist gated on a verdict value that could never
  occur. **When an obligation can only be discharged by a party who is not the author, check that the
  artifact stating it does not also require the author to satisfy it.**
- 2026-07-29: **P-3 AMENDMENT (operator-ratified): a paired limb is counted where a derived
  quantity is CONSUMED, not where files are edited.** WO-0141 was cut along a file boundary —
  "kernel now, stores in WO-0142" — and its scope-budget table recorded "paired-store limb: 0"
  because the diff touched no adapter. That was wrong: `contributed_epoch_sequence` is read by
  both stores, so changing what it MEANS is a store change regardless of which files move. The
  delivered kernel demanded recovery at `next_mintable` while both stores still minted at
  `release-floor + 1`, so the store's own recovery event was refused by the fold that gates
  recovery and the human release never survived a restart (P0-7, found in self-audit).
  **Corollary: "change the shared derivation now, update its consumers later" is never a valid
  cut.** A shared derivation and every consumer that reads it are one limb and land together.
  Counting the limb correctly would have raised WO-0141's score from 4 to 6 at the planning gate
  and forced exactly the delivery that eventually had to be made anyway.
- 2026-07-29: **reachability is not discrimination — a pin must be exercised at values where the
  correct and incorrect rules DISAGREE.** Three pins on the WO-0141 surface were found by
  mutation to cover their rule only where both answers coincide: a metamorphic relation checked
  the tolerant fold (which buckets by payload producer, so the attribution rule cannot affect it)
  instead of the floors where the defect lived; and two occupancy pins placed the consumed key
  far above the high-water, where `next_mintable` and `high_water + 1` return the same value.
  All three were green against a mutant that deleted the rule entirely. This is the same shape as
  REV-0045 P0-2's trigger-specific survivor. When pinning a rule of the form "X, except where Y",
  the fixture must instantiate Y.
- 2026-07-29: **ADR-015 first recorded mutation baseline — and the ratchet had never worked.**
  Running it for the first time surfaced five independent defects, each of which alone prevented
  it producing evidence: `mutmut run` could not import the package (only `source_paths` is copied
  into the working tree; fixed with `also_copy`); `mutmut results --all` is an invalid invocation
  in 3.6.0 (`--all` takes a boolean argument), so the CI step and the P1-5 classifier docstring
  were both wrong; the test selection was a hard-coded four-file list written before WO-0141, so
  every pin added since was invisible and 270 mutants reported `no tests`; the classifier's
  taxonomy counted a hung mutant as unknown rather than detected; and `next_mintable_epoch_sequence`
  contained a structurally unbounded scan that a generated mutant found by hanging.
  **Baseline: generated 1223, killed 1017, detected-by-timeout 1, survived 205.** The 205 is a
  measurement, not a target — untriaged, with an unknown share equivalent.
  **The standing lesson:** REV-0045 P1-5 reported that this control could not parse its tool's
  output. The repair fixed the PARSER against committed fixtures and never ran the tool. Fixtures
  were faithful and the invocation above them was broken, so the control stayed dead in a new
  costume. **A control verified only against its own fixtures has been verified against nothing —
  every assurance control must be exercised end to end against the real tool at least once, and
  that run is part of the control's delivery, not a follow-up.**
- 2026-07-29: **enumerated lists rot; gate every one.** Three on this surface have now fallen
  behind — the F-1 append-caller table, the derived-truth store list, and the mutation ratchet's
  test selection. Each is now machine-consumed and failure-capable, and each states its own
  limitation rather than leaving it to be found (the selection gate cannot see
  `from app.events import projectors`, and pins that fact as a test). Where a list cannot be
  replaced by discovery, it must be guarded by something that fails the build when it drifts.
