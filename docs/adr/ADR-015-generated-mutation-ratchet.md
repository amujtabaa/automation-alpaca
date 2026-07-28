# ADR-015 — Generated mutation testing as a nightly ratchet

- **Status:** Accepted (operator ratification, Ameen, 2026-07-28 — "You can perform the
  rename and process changes")
- **Date:** 2026-07-28
- **Deciders:** Operator (human gate); Claude seat (proposal, after REV-0045 round 2)

## Context

This repo's testing discipline requires a mutation check on every decisive pin: revert
the control, watch the pin go red, restore, watch it go green. The discipline is real
but has a structural blind spot that has now produced recorded failures three times:

1. **REV-0045 P0-2 (round 2):** the flat-seed mutation was verified red at slice 4, the
   guarded path changed twice afterward, and the proof silently expired — the recorded
   mutant passed the full corpus. The replacement pins were then *again*
   mutation-incomplete: the independent reviewer constructed a seed conditioned on
   `sequence == 1` that passed both replacement pins and 161 rails tests.
2. **REV-0038 F4:** a load-bearing guard shipped with no committed red at all.
3. **REV-0041 C-3:** `red_green_verified: true` recorded for evidence that was
   live-control-only.

The common shape: **a hand-picked mutant proves only that the author thought of that
mutant.** The defects that survive are precisely the mutants nobody picked.

## Decision

Adopt `mutmut` (3.6.0, pinned in `requirements-mutation.txt` — a separate pin file so
the main `constraints.txt` closure is untouched) as a **nightly generated-mutation
ratchet**, scoped initially to `app/events/projectors.py` — the derived-truth kernel
where every REV-0045 P0 lived — with test selection scoped to the rails corpus
(`[tool.mutmut]` in `pyproject.toml`; CI job `.github/workflows/mutation-nightly.yml`).

Ratchet discipline mirrors the coverage floor (`fail_under`):

- The first recorded run establishes the surviving-mutant baseline; the CI threshold is
  then lowered to that number in the same change that records it.
- The threshold may only shrink. Raising it requires an ADR amendment, exactly like
  lowering the coverage floor.
- Scope may only widen (candidate next surfaces: the two stores' rail sections,
  `app/events/replay.py`).

Manual mutation checks on decisive pins remain mandatory — they run at development
speed and catch regressions the same day. The generated pass is the backstop for the
mutants nobody picked, and for proofs that expired when their guarded path changed.

## Consequences

- A surviving mutant in the nightly run is a finding, not noise: either a pin is
  missing, a pin is inert, or dead code exists. Triage lands in the ledger like any
  other defect.
- New dependency (dev-only, never imported by `app/`): `mutmut` and its transitive
  closure, pinned separately. It is not installed by `harness/bootstrap.py` and cannot
  affect the runtime import graph (`lint-imports` remains the authority there).
- First-baseline caveat: until the baseline run is recorded, the CI threshold is a
  permissive sentinel (999) — the job's value in that window is the report, not the
  gate. Recording the baseline is queued work, not optional.
