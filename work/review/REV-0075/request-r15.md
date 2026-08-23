# REV-0075 R15 — reduced closed fixture grammar review

Return findings only. Do not edit source, tests, governance, request, or result files. Do not
commit, push, access SQLite, create a database, or invoke runtime composition, credentials,
network, broker, or order code.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Rejected R14 source: `564a3410b31a9f493dd1cd0443834c26fbfaf6c8`, tree
  `d0d2c4787fd9c219efb877d97cde90061af17ca2`
- Exact R15 correction: `06e125439edc200ad624b1362b1c2bd33b333768`, tree
  `3a35a543c55143b3b915fc590b33c143f763a76d`
- Review diff: `564a3410b31a9f493dd1cd0443834c26fbfaf6c8..06e125439edc200ad624b1362b1c2bd33b333768`

`result-r14.md` is findings input only. Re-derive the correction independently.

## Required read order

1. `AGENTS.md`, `CLAUDE.md` safety core, active WO-0168a, frozen R13/R13-R1 contract,
   `result-r13.md`, and `result-r14.md`.
2. This request, the exact diff, and final
   `tests/execution_core/test_persistence_write_capability.py`.
3. The three target fixtures only as needed to verify their actual syntax forms.
4. Reproduce only the named pure test command. SQLite activity is forbidden.

## Required adversarial checks

1. Verify the rejected partial alias/data-flow framework was actually removed and replaced by a
   materially smaller closed whitelist for the three fixture forms.
2. Try concrete ordinary-source bypasses through alternate repository/support imports,
   assignments/defaults, qualified or aliased getters, `vars`/`__dict__`/`__getattribute__`,
   callable containers, cross-scope sequence names, loop-carried aliases, direct calls with a
   missing/wrong capability, and direct or monkeypatched support-issuer rebinding.
3. Verify each accepted loop derives its callable rows from a literal sequence in the same lexical
   scope and permits only exact direct invocation or positional argument 1 to the exact
   `_apply_mutator` helper, plus diagnostic `operation.__name__` reads.
4. Verify all current fixture mutator routes are covered, the mutants are failure-capable, and no
   production code, DDL, SQLite, schema bytes, runtime capability, or safety boundary changed.
5. Judge complexity and maintainability independently. Do not accept a bypassable guard merely
   because the tests pass.

## Author evidence to reproduce or challenge

```text
.\\.venv\\Scripts\\python.exe -m pytest -q \\
  tests\\execution_core\\test_persistence_operations.py \\
  tests\\execution_core\\test_persistence_checkpoint_codec.py \\
  tests\\execution_core\\test_persistence_input_receipt.py \\
  tests\\execution_core\\test_persistence_write_capability.py
```

The command passed (79 tests). Ruff check/format on the four related files and
`git diff --check` passed. The corrected file is 689 lines versus 1,254 in R14. No
SQLite-bearing test ran.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, smallest complete root correction,
and evidence tag. End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` and counts. State anything
unverified. This review does not close WO-0168a or authorize DDL execution, SQLite activity,
runtime composition, external I/O, promotion, merge, or release.
