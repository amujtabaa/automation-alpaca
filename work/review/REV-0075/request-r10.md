# REV-0075 R10 — R13-S non-serving static-substrate review

Return findings only. Do not edit source, tests, governance files, request
files, or result files. Do not commit, push, access SQLite, create a database,
or invoke runtime composition, credentials, network, broker, or order code.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Earlier reviewed source candidate: `5932294ee28a848c58aa6bcfda665b96c42526e4`, tree
  `4b51e1c60d59d7d497f461cabae0b3fb574e10c5`
- R13-R1 documentation acceptance: `f38224861365a2d2210b7964b4709348ffd055cd`, tree
  `f1755a8db69a325f6d13d371ab7696f798fe2e3c`
- Exact source candidate: `341498c55af7a7f807c11be7287bd243c57aa8b8`, tree
  `890015aa5816938d255893ba4ebd21da4b26fea3`
- Primary implementation diff: `5932294ee28a848c58aa6bcfda665b96c42526e4..341498c55af7a7f807c11be7287bd243c57aa8b8`

The candidate must stand on current code and tests. Earlier R9 results are
findings input only, not acceptance authority.

## Required read order

1. `AGENTS.md`, the safety core in `CLAUDE.md`, active WO-0168a, and the R13-R1
   sections of the frozen operation-state contract.
2. `work/review/REV-0074/result-r13.md`, `result-r13-r1.md`, then R9 request and
   result files in this packet.
3. This request, the exact diff, and all affected source/tests at the candidate
   commit.
4. Reproduce only the named pure test command if useful. SQLite activity is
   forbidden even for temporary files.

## Scope under review

- R13-S static, uninstalled DDL for the accepted six R12 persistence families.
- Canonical durable-input, semantic-key, receipt/outcome, and broker-outbox
  records/repository boundary.
- Opaque runtime/setup write capability and its exact test-only issuer boundary.
- R13-R1 root correction: no serving checkpoint-payload record, no payload
  store/load API, and no public kernel-head store/advance/load route before
  R13-H/C complete owner-wire hydration.
- Pure tests and structural controls only.

## Required adversarial lenses

1. Re-derive whether any public or production-reachable source path can use a
   header-only kind-`0x02` payload or bare kernel-checkpoint header to create,
   advance, load, or serve restart/currentness authority. Do not treat an
   uninstalled DDL trigger as a substitute for this source boundary.
2. Attack the setup capability boundary through direct imports, aliases,
   `getattr`, constructor/`object.__new__` paths, wrong connections, and absent
   runtime issuance. Decide whether the source controls are real controls or
   cosmetic conventions.
3. Audit immutable operation binding and primary/semantic dedupe: canonical
   decode/re-encode, exact profile/application/scope/session/source coordinates,
   alternate-key collision domains, coherent receipt/outcome terminal states,
   and outbox snapshots. Challenge any self-consistent caller-shaped row.
4. Audit static DDL as authored text only: row relationships, uniqueness,
   immutability/transition intent, and any mismatch with the repository API.
   Do not install or execute it.
5. Test-critic pass: identify a concrete mutation/bypass that the named pure
   controls would fail to catch. Confirm existing repository fixture writes now
   pass a setup capability explicitly rather than relying on a default.
6. Check scope/safety: no reflection/pickle/repr persistence, no import I/O,
   no changed-DDL execution, no runtime composition/external I/O, no export
   drift, and no unnecessary abstraction.

## Author evidence to reproduce or challenge

```text
.\\.venv\\Scripts\\python.exe -m pytest -q \
  tests\\execution_core\\test_persistence_operations.py \
  tests\\execution_core\\test_persistence_checkpoint_codec.py \
  tests\\execution_core\\test_persistence_input_receipt.py \
  tests\\execution_core\\test_persistence_write_capability.py
```

The command passed. `ruff check`, `ruff format --check`, `mypy app`, and
`git diff --check` also passed for the candidate. A pre-existing pytest-cache
permission warning is non-semantic. No SQLite-bearing test has been run since
the recorded pre-gate deviation; database-bearing repository/directness/schema
tests remain deferred to the later exact DDL gate and R13-C complete payload
fixture.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, and the smallest
complete root correction. Explicitly distinguish reproduced-live from
reasoned-only evidence and state what you did not reproduce. End with one
verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`) and counts. This review
does not close WO-0168a or authorize DDL execution, SQLite activity, runtime
composition, external I/O, promotion, merge, or release.
