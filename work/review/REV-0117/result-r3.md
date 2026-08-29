# REV-0117 — R2 correction verification result

Reviewed delta: `112b66251d1b7abdfd8eeb2b1c499e9f10d22a7b..d1b0b26a55f8d45fa7b6bc7953c99f5a4fb78126`.

No findings.

Evidence:

- `reproduced-live` — `.\\.venv\\Scripts\\python.exe -B -m pytest -o addopts='' -p no:cacheprovider -q tests\\execution_core\\test_persistence_startup_hydration.py` completed with `23 passed in 1.75s`. The new test executes a non-empty `unresolved_generations` selection and its direct-domain-ordinal negative control raises `selected unresolved generation is spliced` as required.
- `static-reasoning` — `test_compact_projection_rejects_domain_ordinal_for_unresolved_generation` creates an applied successor, retrieves its actual retired predecessor, retains that predecessor's stream route, and supplies a durable ordinal of `retired.binding.successor_ordinal + 1` before asserting successful encoding. It then changes only the durable ordinal to the direct domain ordinal and asserts the splice refusal. Reverting the production check at `app/execution_core/persistence/checkpoint_codec.py:4883` to direct equality makes the valid setup fail; removing the check makes the negative control fail, so the test is failure-capable rather than vacuous.
- `static-reasoning` — the delta is limited to that pure hydration test and the WO-0169/REV-0117 disposition records. It does not change production code, DDL, held tests, the execution authorization flag, or any human-gated runtime surface. `git diff --check` passed.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: SQLite artifacts and held/gated tests were not inspected or run. No database access or creation, network/broker/order activity, commit, or push occurred.
