# REV-0075 R14 — fixture capability root-correction review

Return findings only. Do not edit source, tests, governance files, request files, or result
files. Do not commit, push, access SQLite, create a database, or invoke runtime composition,
credentials, network, broker, or order code.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R13 candidate: `8019864fc3f34fe24801882848c37fcaf88bb517`, tree
  `b4c5ceaf0d1c19bfdcb71712f19a919b0a0dcd6c`
- Exact root-correction candidate: `564a3410b31a9f493dd1cd0443834c26fbfaf6c8`, tree
  `d0d2c4787fd9c219efb877d97cde90061af17ca2`
- Review diff: `8019864fc3f34fe24801882848c37fcaf88bb517..564a3410b31a9f493dd1cd0443834c26fbfaf6c8`

`result-r13.md` is findings input only. This is a fresh review of the correction; do not trust its
author's explanation or its passing tests.

## Required read order

1. `AGENTS.md`, `CLAUDE.md` safety core, active WO-0168a, frozen contract R13/R13-R1, and
   `result-r13.md`.
2. This request, exact diff, and the final form of
   `tests/execution_core/test_persistence_write_capability.py`.
3. Reproduce only the named pure test command if useful. SQLite activity is forbidden even for
   temporary files.

## Required adversarial checks

1. Re-derive whether a fixture can still obtain a valid setup capability or dispatch a repository
   mutator outside the named support route through qualified getter calls, aliases/defaults,
   module dictionaries, `vars`, `__getattribute__`, callable containers, or loop-carried
   callables. Identify concrete ordinary-source bypasses; do not demand hostile-Python security
   outside the frozen structural fixture contract.
2. Verify the sole allowed `setup_support` use in each target fixture is the exact issuer return,
   and that direct or monkeypatched rebinding of its issuer member fails the proof.
3. Verify valid existing fixture forms remain accepted and that the negative tests fail if the new
   guards are removed or weakened.
4. Judge proportionality independently. The correction must be a finite fixture grammar, not a
   general static-analysis framework. If a materially smaller complete root correction would cover
   the required grammar, report it as P1 with the smallest complete reduction.
5. Confirm no runtime capability, DDL, SQLite execution, schema bytes, safety boundary, or
   production code changed.

## Author evidence to reproduce or challenge

```text
.\\.venv\\Scripts\\python.exe -m pytest -q \\
  tests\\execution_core\\test_persistence_operations.py \\
  tests\\execution_core\\test_persistence_checkpoint_codec.py \\
  tests\\execution_core\\test_persistence_input_receipt.py \\
  tests\\execution_core\\test_persistence_write_capability.py
```

The command passed (78 tests). Ruff check/format on the four related fixture files and
`git diff --check` passed. No SQLite-bearing test has run.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, smallest complete root correction,
and evidence tag. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`) and counts.
State unverified checks. This review does not close WO-0168a or authorize DDL execution, SQLite
activity, runtime composition, external I/O, promotion, merge, or release.
