# REV-0075 R3 — WO-0168a authenticated-proof remediation review

Return findings only. Do not edit source, tests, governance files, request files, or result files.
Do not commit, push, access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Prior finding record: `work/review/REV-0075/result-r2.md`
- Remediation parent: `17bacd9d58f251037e989a5a7e20cc9ed9f7b841`, tree
  `96122883853e1b5403b14b9f5dfb88ed0084f430`
- Exact remediation candidate: `1c2debca303bd31d44474ae191ee20d9285cff1c`
- Candidate tree: `692238c679041cdf76878ef40239699e13b9caaa`
- Review diff: `17bacd9d58f251037e989a5a7e20cc9ed9f7b841..1c2debca303bd31d44474ae191ee20d9285cff1c`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0075/request-r2.md`, `result-r2.md`, and this request.
3. `work/review/REV-0074/result-r8.md`, `result-r9b.md`, `result-r10.md`, and
   `result-r11.md`; the active WO; and contract sections 4.1, 4.4, 5, 8, and 9.
4. The exact review diff, then the changed source and tests.
5. Reproduce focused pure evidence at the candidate only as needed. SQLite activity is forbidden.

## Candidate summary

The candidate replaces aggregate-only direct execution proof with a bounded radix witness that
retains the exact queried key and complete canonical labelled-child tuple at every visited node.
It adds the three map commitments to the retained execution state and validates one keyed
membership/nonmembership witness for each selected or absent prior observation, root head,
revision predecessor, and root-claim lookup.

It makes `CurrentProofSlice` opaque and repository-issued, binding the selected application,
profiles, scope, live acquisition generation, controller head, protection authority, and active
stream/cursor relationships. `checkpoint_codec.py` becomes the only production bridge that adapts
that sealed result into the private protection hydrator proof. The candidate does not add DDL,
execute SQLite, compose a runtime, or make any network/broker call.

## Author evidence to reproduce or challenge

- `pytest -q tests/execution_core/test_position.py` — 21 passed.
- `pytest -q tests/execution_core/test_protection.py` — passed.
- `pytest -q tests/execution_core/test_persistence_checkpoint_codec.py` — 3 passed.
- `pytest -q tests/execution_core/test_import_boundary.py` — 32 passed.
- Collection only, no fixture execution: `pytest --collect-only -q`
  `tests/execution_core/test_persistence_repository.py` (33) and
  `tests/execution_core/test_persistence_directness.py` (157).
- `ruff check` and `ruff format --check` on all ten changed paths, `mypy app`, and
  `git diff --check` — passed.

The focused pytest commands emitted only a pre-existing `.pytest_cache` permission warning.
No SQLite-bearing test was run.

## Required adversarial lenses

1. Re-derive the radix proof. In particular, challenge full-child tuple canonicality, authenticated
   path linkage, map/state commitment binding, all membership and both exact nonmembership cases,
   and the possibility of re-signing the outer proof around a wrong-key witness. Confirm that it
   retains no history-shaped map or arbitrary replay input.
2. Re-derive the repository-proof boundary. Challenge constructibility, issuer provenance, mutation
   after issuance, the binding of the request and all required currentness/authority relationships,
   stale/cross-profile/cross-scope selection, and whether an optional direct row can become an
   unauthenticated authority path. Do not treat a private Python spelling as a security claim;
   evaluate the stated structural and static boundary.
3. Re-derive the checkpoint bridge. Confirm that only the sealed `CurrentProofSlice`, not raw rows,
   a tuple, or an independently selected envelope, reaches protection-proof issuance; challenge
   every selected application/profile/scope/controller/live-generation/authority/stream/mandate/
   state/source coordinate.
4. Act as a test critic. Check whether the new tests would fail if any direct witness validation,
   terminal `has_value=False` check, proof issuer check, or production-route restriction were
   removed or weakened. Identify assertion-only tests that do not exercise the decisive path.
5. Check scope discipline and prohibited activity. Flag any added complexity that does not buy the
   required root fix, weakened historical boundary behavior, DDL/schema alteration, database
   execution, runtime composition, or external I/O.

## Result contract

Report each finding with P0/P1/P2 severity, file:line, mechanism, impact, and smallest complete
root correction. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`), P0/P1/P2
counts, and unverified items. This is a remediation review, not the final WO-0168a closure review.
