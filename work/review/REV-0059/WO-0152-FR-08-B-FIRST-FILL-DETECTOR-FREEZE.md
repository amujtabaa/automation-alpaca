# WO-0152 FR-08 B-first-fill detector freeze

## Frozen detector

- Observed: 2026-08-07
- Branch and local HEAD: `codex/arch-reset-2026-07-r1` at
  `3c8401e147e09f1dc49e2c10f7bbfa60a8ff859c`
- Frozen, unstaged detector: `tests/execution_core/test_acquisition_stateful.py`
- Detector source SHA-256:
  `c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186`
- Detector: `test_e3_late_a_fill_after_b_first_fill_preserves_b_generation_authority`
- Command:
  `./.venv/Scripts/python.exe -m pytest -q tests/execution_core/test_acquisition_stateful.py -k "late_a_fill_after_b" -p no:cacheprovider`
- Result: exit `1`, one failing selected test.

The failed assertion expects
`reduce_acquisition_controller(...)` to return `APPLIED` after B's authentic
first canonical BUY fill. It observed `REFUSED`.

## Minimized public trace

1. Build a rooted A lifecycle entirely through the public effect, claim, venue,
   first-fill, protection, terminal-observation, final-bust, and controller
   reducers.
2. Use the narrow test-only terminal certification fixture to close A while
   flat, then create the public B serial successor.
3. Create and claim B's specialized BUY effect.
4. Apply public B `ACKNOWLEDGED`, discovery, `NEEDS_REVIEW`, and one canonical
   BUY `FILL` with quantity delta `+1`.
5. Verify the fact projection, predecessor scope commitment, predecessor venue
   commitment, B request/effect lineage, and pre-fill B controller projection.
6. Invoke the public acquisition composite reducer. It returns `REFUSED`.

The preceding venue transition is `APPLIED`; the detector does not rely on a
private producer, a caller-shaped mandate, a history scan, a generic BUY, or
an E3 oracle mutation.

## Independent E2 classification

The independently re-derived causal chain is that successor registration
installs B controller/currentness authority but leaves the direct
venue-owned protection cursor bound to A. The ordinary B first-fill protection
projection requires cursor and B mandate identity to match, so the composite
reducer correctly refuses rather than silently accepting an unprotected B
exposure. This is a material E2 P0 integrity gap: the architecture requires a
fresh B protection authority for an accepted serial successor.

The required owner is the E2 authority-to-venue successor boundary. The
candidate correction must be a bounded, private, atomic A-to-B cursor rollover
with zero economic delta, not reuse of A's mandate, a weakened ordinary cursor
check, a mixed-recovery exception, or an E3 expectation change. This causal
classification is not an approval to implement it.

## FR-08 disposition and preservation

WO-0152 remains `ACTIVE` but implementation-`PAUSED`. This detector stays
unstaged and uncommitted at the recorded source hash. It must not be formatted,
rewritten, marked expected-failure, or used as E3 acceptance evidence. Earlier
`evidence.md` and its detector-confirmation record remain immutable historical
evidence.

The next allowed action is a bounded E2 re-gate with fresh independent
acceptance. Only after its accepted implementation and an unchanged rerun of
this detector may E3 resume. The paired E2/E3 93% exact-head closeout remains
unmet; no production, database/SQL/DDL, runtime, broker/network, credentials,
M2, merge, deletion, cleanup, force-push, or rebase authority is added.
