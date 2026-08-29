# REV-0117 — WO-0169 correction review R2 result

Reviewed range: `f8b14ae46d12319d1d4e33f9a5d8d643b0e8bb21..dee3533099bba6ffeaa3372d33b04c1513cd75b7`.

### [P1] The unresolved-generation boundary correction has no failure-capable test

- Location: `app/execution_core/persistence/checkpoint_codec.py:4883`
- Requirement: `correction-r2-request.md` requires the live and unresolved comparisons to use the durable `domain ordinal + 1` mapping, and requires failure-capable proof that removing the mapping fails.
- Evidence: `static-reasoning` — the changed unresolved comparison is reached only while iterating a non-empty `selection.unresolved_generations`. Every reviewed construction of that selection in `tests/execution_core` supplies `unresolved_generations=()` (`test_persistence_startup_hydration.py:235,689`; `test_persistence_runtime_checkpoint_pure.py:257,379`). The only calls to `_encode_runtime_checkpoint_acquisition` / `_decode_source_acquisition_checkpoint` are the live-only cases at `test_persistence_startup_hydration.py:551-607`. Reverting line 4883 alone to the predecessor's direct-equality comparison is therefore not detected by the reviewed tests.
- Impact: a regression can again authenticate an unresolved durable record in domain coordinates rather than its one-based durable coordinates, without a focused test preventing it.
- Resolution: add one pure, non-SQLite checkpoint fixture containing an unresolved retained generation and its stream route at a non-empty `unresolved_generations` selection. Assert the valid `binding.successor_ordinal + 1` row encodes, and that replacing it with the domain ordinal raises the existing `selected unresolved generation is spliced` error.

No P0 finding: the exact candidate/tree and the two-file-only range match the packet; `git diff --check` passed. Static source proof re-derived the zero-based acquisition domain (`initialize_acquisition_controller` creates genesis ordinal `0`) against the durable schema (`successor_ordinal >= 1`, with `NULL` predecessor exactly at durable ordinal `1`) and the M2-I4 unit-of-work's existing `binding.successor_ordinal + 1` checks. The candidate applies that mapping to the live checkpoint comparison (`checkpoint_codec.py:8965`) and unresolved comparison (`checkpoint_codec.py:4883`). The shared live fixtures now use durable ordinal `1`, `CONSISTENT`, and `NORMAL`, matching schema vocabulary and M2-I4 authority checks; their live negative control rejects the prior domain-coordinate row.

Protected artifacts were source-verified only: `schema.py` and the held SQLite test retain their pinned blobs across predecessor, candidate, and packet HEAD; `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` remains exact boolean `False`; source-only AST evaluation reproduced `SCHEMA_DDL` as 190,705 UTF-8 bytes with SHA-256 `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: No test command was run, including the ordinary pure suite, by the packet's finite static-review boundary. SQLite artifacts, held/gated tests, database access, DDL execution, and network/broker/order activity were not inspected or run.
