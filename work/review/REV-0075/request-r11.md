# REV-0075 R11 — R10 root-correction review

Return findings only. Do not edit source, tests, governance files, request
files, or result files. Do not commit, push, access SQLite, create a database,
or invoke runtime composition, credentials, network, broker, or order code.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R10-reviewed candidate: `341498c55af7a7f807c11be7287bd243c57aa8b8`, tree
  `890015aa5816938d255893ba4ebd21da4b26fea3`
- Exact corrective candidate: `5289f3a55544141763177b17c92bf1b88e8155c2`, tree
  `bb90cfbcbecccd9d14d5c847341eb85ad0de2d29`
- Review diff: `341498c55af7a7f807c11be7287bd243c57aa8b8..5289f3a55544141763177b17c92bf1b88e8155c2`

`result-r10.md` is findings input only. This is a fresh acceptance review of
the correction, not a request to trust the earlier result or author claim.

## Required read order

1. `AGENTS.md`, `CLAUDE.md` safety core, active WO-0168a, frozen contract
   R13/R13-R1, `request-r10.md`, and `result-r10.md`.
2. This request, exact diff, and affected source/tests at the corrective
   candidate.
3. Reproduce only the named pure test command if useful. SQLite activity is
   forbidden even for temporary files.

## Required adversarial checks

1. Confirm R13-S exposes no `RuntimeCheckpointEnvelope` class or export and
   no other public serving checkpoint envelope/payload substitute.
2. Confirm all retired kernel-header store/advance/load APIs are absent from
   repository code and every allowed persistence fixture; distinguish expected
   private current-proof internals from a public head API.
3. Confirm every direct repository mutator in repository and directness
   fixtures supplies an explicit connection-bound setup capability through the
   named support issuer. Attack aliases/defaults/proxies that could mask a
   missing capability.
4. Check that the correction did not weaken actual runtime-token enforcement,
   reintroduce SQLite/DDL activity, delete an unrelated safety control, or add
   needless abstraction.

## Author evidence to reproduce or challenge

```text
.\\.venv\\Scripts\\python.exe -m pytest -q \
  tests\\execution_core\\test_persistence_operations.py \
  tests\\execution_core\\test_persistence_checkpoint_codec.py \
  tests\\execution_core\\test_persistence_input_receipt.py \
  tests\\execution_core\\test_persistence_write_capability.py
```

The command passed. Ruff check/format, mypy `app`, and `git diff --check`
passed. No SQLite-bearing test has run.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, smallest complete
root correction, and evidence tag. End with one verdict (`BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`) and counts. State unverified checks. This
review does not close WO-0168a or authorize DDL execution, SQLite activity,
runtime composition, external I/O, promotion, merge, or release.
